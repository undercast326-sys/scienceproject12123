from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from apps.questions.models import Question
from apps.topics.models import Subject, Topic
from apps.users.models import UserProfile

from .models import QuizSession


def make_topic(question_count=5, name='Дроби'):
    subject, _ = Subject.objects.get_or_create(name='Математика')
    topic = Topic.objects.create(subject=subject, name=name)
    for i in range(question_count):
        Question.objects.create(
            topic=topic, type='single', prompt=f'Q{i}',
            options=['a', 'b'], correct_answer='a', order=i,
        )
    return topic


class QuizFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('student', password='pass12345')
        self.client.force_authenticate(self.user)
        self.topic = make_topic()

    def start(self, topic=None):
        topic = topic or self.topic
        res = self.client.post('/api/quizzes/start/', {'topic_id': topic.id}, format='json')
        self.assertEqual(res.status_code, 201)
        return res.data

    def test_start_hides_answers_and_serves_five(self):
        data = self.start()
        self.assertEqual(len(data['questions']), 5)
        self.assertNotIn('correct_answer', data['questions'][0])
        self.assertNotIn('explanation', data['questions'][0])

    def test_submit_rejects_question_outside_session(self):
        data = self.start()
        other = make_topic(1).questions.first()
        res = self.client.post(
            f"/api/quizzes/{data['session_id']}/submit-answer/",
            {'question_id': other.id, 'answer': 'a'}, format='json',
        )
        self.assertEqual(res.status_code, 404)

    def test_unanswered_questions_count_as_wrong(self):
        data = self.start()
        sid = data['session_id']
        # Answer only two of five, one right, one wrong.
        q1, q2 = data['questions'][:2]
        self.client.post(f'/api/quizzes/{sid}/submit-answer/', {'question_id': q1['id'], 'answer': 'a'}, format='json')
        self.client.post(f'/api/quizzes/{sid}/submit-answer/', {'question_id': q2['id'], 'answer': 'b'}, format='json')

        res = self.client.post(f'/api/quizzes/{sid}/finish/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {'score': 1, 'total': 5, 'correct': 1, 'wrong': 4, 'xp_gained': 10, 'xp': 10, 'level': 1})

        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual((profile.solved, profile.correct, profile.wrong, profile.xp), (5, 1, 4, 10))

    def test_finish_is_idempotent(self):
        data = self.start()
        sid = data['session_id']
        for q in data['questions']:
            self.client.post(f'/api/quizzes/{sid}/submit-answer/', {'question_id': q['id'], 'answer': 'a'}, format='json')

        first = self.client.post(f'/api/quizzes/{sid}/finish/').data
        second = self.client.post(f'/api/quizzes/{sid}/finish/').data
        self.assertEqual(first, second)
        self.assertEqual(first['xp'], 50)

        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.xp, 50)
        self.assertEqual(profile.solved, 5)
        self.assertEqual(QuizSession.objects.get(id=sid).score, 5)

    def answer_all(self, data, answer='a'):
        sid = data['session_id']
        for q in data['questions']:
            self.client.post(f'/api/quizzes/{sid}/submit-answer/', {'question_id': q['id'], 'answer': answer}, format='json')
        return self.client.post(f'/api/quizzes/{sid}/finish/').data

    def test_level_advances_across_sessions(self):
        for i in range(10):
            res = self.answer_all(self.start(make_topic(name=f'Тема {i}')))
        self.assertEqual(res['xp'], 500)
        self.assertEqual(res['level'], 6)

    def test_answer_cannot_be_changed_after_feedback(self):
        data = self.start()
        sid = data['session_id']
        qid = data['questions'][0]['id']
        first = self.client.post(f'/api/quizzes/{sid}/submit-answer/', {'question_id': qid, 'answer': 'b'}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.data['is_correct'])

        retry = self.client.post(f'/api/quizzes/{sid}/submit-answer/', {'question_id': qid, 'answer': 'a'}, format='json')
        self.assertEqual(retry.status_code, 400)

        res = self.client.post(f'/api/quizzes/{sid}/finish/').data
        self.assertEqual((res['correct'], res['xp_gained']), (0, 0))

    def test_replaying_solved_questions_gives_no_xp(self):
        first = self.answer_all(self.start())
        self.assertEqual((first['xp_gained'], first['xp']), (50, 50))

        second = self.answer_all(self.start())
        self.assertEqual(second['correct'], 5)
        self.assertEqual((second['xp_gained'], second['xp']), (0, 50))

        profile = UserProfile.objects.get(user=self.user)
        # Stats still count every answer; only XP is first-time-only.
        self.assertEqual((profile.solved, profile.correct, profile.xp), (10, 10, 50))

    def test_question_failed_before_still_earns_xp_when_solved(self):
        self.answer_all(self.start(), answer='b')
        res = self.answer_all(self.start())
        self.assertEqual(res['xp_gained'], 50)

    def test_unfinished_session_does_not_block_xp(self):
        abandoned = self.start()
        for q in abandoned['questions']:
            self.client.post(f"/api/quizzes/{abandoned['session_id']}/submit-answer/", {'question_id': q['id'], 'answer': 'a'}, format='json')
        res = self.answer_all(self.start())
        self.assertEqual(res['xp_gained'], 50)

    def test_cannot_submit_after_finish(self):
        data = self.start()
        sid = data['session_id']
        self.client.post(f'/api/quizzes/{sid}/finish/')
        res = self.client.post(
            f'/api/quizzes/{sid}/submit-answer/',
            {'question_id': data['questions'][0]['id'], 'answer': 'a'}, format='json',
        )
        self.assertEqual(res.status_code, 400)

    def test_other_users_session_is_hidden(self):
        data = self.start()
        other = User.objects.create_user('other', password='pass12345')
        self.client.force_authenticate(other)
        res = self.client.post(f"/api/quizzes/{data['session_id']}/finish/")
        self.assertEqual(res.status_code, 404)
