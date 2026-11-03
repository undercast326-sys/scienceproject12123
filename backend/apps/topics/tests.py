from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from apps.questions.models import Question
from apps.quizzes.tests import make_topic

from .models import Topic, Paragraph


class TopicListTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('student', password='pass12345')
        self.client.force_authenticate(self.user)
        self.topic = make_topic(3)
        Paragraph.objects.create(topic=self.topic, title='§1', order=1)
        Paragraph.objects.create(topic=self.topic, title='§2', order=2)
        # 60 more topics to prove the list is no longer capped at PAGE_SIZE.
        for i in range(60):
            Topic.objects.create(subject=self.topic.subject, name=f'Topic {i}', order=i + 1)

    def test_list_returns_all_topics_unpaginated(self):
        res = self.client.get('/api/topics/')
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.data, list)
        self.assertEqual(len(res.data), 61)

    def test_list_query_count_is_constant(self):
        with CaptureQueriesContext(connection) as ctx:
            self.client.get('/api/topics/')
        # topics + 3 grouped progress queries; nothing per-row.
        self.assertLessEqual(len(ctx.captured_queries), 5, [q['sql'] for q in ctx.captured_queries])

    def test_progress_fields_reflect_user_activity(self):
        paragraph = self.topic.paragraphs.first()
        self.client.post(f'/api/topics/{self.topic.id}/paragraphs/{paragraph.id}/read/')

        data = self.client.post('/api/quizzes/start/', {'topic_id': self.topic.id}, format='json').data
        sid = data['session_id']
        q = data['questions'][0]
        self.client.post(f'/api/quizzes/{sid}/submit-answer/', {'question_id': q['id'], 'answer': 'a'}, format='json')
        self.client.post(f'/api/quizzes/{sid}/finish/')

        res = self.client.get(f'/api/topics/{self.topic.id}/')
        self.assertEqual(res.data['paragraph_count'], 2)
        self.assertEqual(res.data['paragraphs_read_count'], 1)
        self.assertEqual(res.data['question_count'], 3)
        self.assertEqual(res.data['questions_solved_count'], 1)
        self.assertEqual(res.data['best_score'], 1)

        # Other users see their own (empty) progress, not this user's.
        self.client.force_authenticate(User.objects.create_user('other', password='pass12345'))
        res = self.client.get(f'/api/topics/{self.topic.id}/')
        self.assertEqual(res.data['paragraphs_read_count'], 0)
        self.assertEqual(res.data['best_score'], 0)

    def test_paragraph_list_marks_read_state(self):
        paragraph = self.topic.paragraphs.first()
        self.client.post(f'/api/topics/{self.topic.id}/paragraphs/{paragraph.id}/read/')
        res = self.client.get(f'/api/topics/{self.topic.id}/paragraphs/')
        self.assertEqual([p['is_read'] for p in res.data], [True, False])

    def test_subjects_list_with_counts(self):
        res = self.client.get('/api/subjects/')
        self.assertIsInstance(res.data, list)
        self.assertEqual(res.data[0]['topic_count'], 61)
        self.assertEqual(res.data[0]['mock_test_count'], 0)

    def test_topics_filter_by_subject(self):
        res = self.client.get(f'/api/topics/?subject={self.topic.subject_id}')
        self.assertEqual(len(res.data), 61)
        self.assertEqual(self.client.get('/api/topics/?subject=999').data, [])
