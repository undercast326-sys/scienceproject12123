from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.topics.models import Subject
from apps.users.models import UserProfile

from .models import MockTest, MockQuestion, MockAttempt


def make_mock_test(question_count=3, duration=30):
    subject, _ = Subject.objects.get_or_create(name='Математика')
    test = MockTest.objects.create(subject=subject, title='Вариант 1', duration_minutes=duration)
    for i in range(question_count):
        MockQuestion.objects.create(
            mock_test=test, type='single', prompt=f'Q{i}', options=['a', 'b'], correct_answer='a', order=i,
        )
    return test


class MockTestFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('student', password='pass12345')
        self.client.force_authenticate(self.user)
        self.test = make_mock_test()

    def start(self, expected_status=201):
        res = self.client.post(f'/api/mock-tests/{self.test.id}/start/')
        self.assertEqual(res.status_code, expected_status)
        return res.data

    def test_list_shows_counts_and_personal_best(self):
        res = self.client.get('/api/mock-tests/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data[0]['question_count'], 3)
        self.assertEqual(res.data[0]['best_score'], 0)

    def test_start_hides_answers_and_sets_deadline(self):
        data = self.start()
        self.assertEqual(len(data['questions']), 3)
        self.assertNotIn('correct_answer', data['questions'][0])
        self.assertIn('expires_at', data)
        attempt = MockAttempt.objects.get(id=data['attempt_id'])
        self.assertAlmostEqual(
            (attempt.expires_at - attempt.started_at).total_seconds(), 30 * 60, delta=2,
        )

    def test_start_resumes_unfinished_attempt(self):
        first = self.start()
        q = first['questions'][0]
        self.client.post(f"/api/mock-attempts/{first['attempt_id']}/answer/", {'question_id': q['id'], 'answer': 'a'}, format='json')
        second = self.start(expected_status=200)
        self.assertEqual(first['attempt_id'], second['attempt_id'])
        self.assertEqual(second['answers'], {q['id']: 'a'})

    def test_answer_gives_no_feedback_and_finish_reveals_review(self):
        data = self.start()
        aid = data['attempt_id']
        q1, q2, q3 = data['questions']
        res = self.client.post(f'/api/mock-attempts/{aid}/answer/', {'question_id': q1['id'], 'answer': 'a'}, format='json')
        self.assertEqual(res.data, {'saved': True})
        self.client.post(f'/api/mock-attempts/{aid}/answer/', {'question_id': q2['id'], 'answer': 'b'}, format='json')

        res = self.client.post(f'/api/mock-attempts/{aid}/finish/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data['score'], res.data['total'], res.data['wrong']), (1, 3, 2))
        self.assertEqual(res.data['xp'], 10)
        review = {r['id']: r for r in res.data['review']}
        self.assertTrue(review[q1['id']]['is_correct'])
        self.assertFalse(review[q2['id']]['is_correct'])
        self.assertIsNone(review[q3['id']]['user_answer'])
        self.assertEqual(review[q3['id']]['correct_answer'], 'a')

        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual((profile.solved, profile.correct, profile.wrong), (3, 1, 2))

    def test_finish_is_idempotent(self):
        data = self.start()
        aid = data['attempt_id']
        for q in data['questions']:
            self.client.post(f'/api/mock-attempts/{aid}/answer/', {'question_id': q['id'], 'answer': 'a'}, format='json')
        first = self.client.post(f'/api/mock-attempts/{aid}/finish/').data
        second = self.client.post(f'/api/mock-attempts/{aid}/finish/').data
        self.assertEqual(first['score'], second['score'])
        self.assertEqual(first['xp_gained'], second['xp_gained'])
        self.assertEqual(UserProfile.objects.get(user=self.user).xp, 30)

    def test_retake_gives_xp_only_for_newly_solved_questions(self):
        data = self.start()
        aid = data['attempt_id']
        q1 = data['questions'][0]
        self.client.post(f'/api/mock-attempts/{aid}/answer/', {'question_id': q1['id'], 'answer': 'a'}, format='json')
        first = self.client.post(f'/api/mock-attempts/{aid}/finish/').data
        self.assertEqual(first['xp_gained'], 10)

        data = self.start()
        aid = data['attempt_id']
        for q in data['questions']:
            self.client.post(f'/api/mock-attempts/{aid}/answer/', {'question_id': q['id'], 'answer': 'a'}, format='json')
        second = self.client.post(f'/api/mock-attempts/{aid}/finish/').data
        self.assertEqual(second['score'], 3)
        self.assertEqual((second['xp_gained'], second['xp']), (20, 30))

    def test_answers_rejected_after_deadline_but_finish_still_works(self):
        data = self.start()
        aid = data['attempt_id']
        MockAttempt.objects.filter(id=aid).update(expires_at=timezone.now() - timedelta(minutes=1))
        res = self.client.post(f'/api/mock-attempts/{aid}/answer/', {'question_id': data['questions'][0]['id'], 'answer': 'a'}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post(f'/api/mock-attempts/{aid}/finish/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['score'], 0)

    def test_unpublished_tests_are_hidden(self):
        self.test.is_published = False
        self.test.save()
        self.assertEqual(self.client.get('/api/mock-tests/').data, [])
        self.assertEqual(self.client.post(f'/api/mock-tests/{self.test.id}/start/').status_code, 404)

    def test_my_attempts_history(self):
        data = self.start()
        self.client.post(f"/api/mock-attempts/{data['attempt_id']}/finish/")
        res = self.client.get('/api/mock-attempts/mine/')
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['mock_test_title'], 'Вариант 1')
