from django.contrib.auth.models import User
from django.forms import modelform_factory
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.quizzes.tests import make_topic

from .forms import AnswerKeyForm
from .models import Question, answer_key_errors


class QuestionEndpointTests(APITestCase):
    def setUp(self):
        self.topic = make_topic(2)

    def test_students_cannot_read_answers(self):
        student = User.objects.create_user('student', password='pass12345')
        self.client.force_authenticate(student)
        self.assertEqual(self.client.get('/api/questions/').status_code, 403)
        q = self.topic.questions.first()
        self.assertEqual(self.client.delete(f'/api/questions/{q.id}/').status_code, 403)
        self.assertEqual(self.topic.questions.count(), 2)

    def test_staff_can_manage_questions(self):
        staff = User.objects.create_user('staff', password='pass12345', is_staff=True)
        self.client.force_authenticate(staff)
        res = self.client.get(f'/api/questions/?topic={self.topic.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['results']), 2)
        self.assertIn('correct_answer', res.data['results'][0])


class AnswerCheckingTests(TestCase):
    def setUp(self):
        self.topic = make_topic(0)

    def q(self, **kw):
        return Question(topic=self.topic, prompt='?', **kw)

    def test_multiple_requires_a_list(self):
        q = self.q(type='multiple', options=['A', 'B', 'C'], correct_answer=['A', 'B'])
        self.assertTrue(q.is_correct(['B', 'A']))
        self.assertFalse(q.is_correct('AB'))
        self.assertFalse(q.is_correct('BA'))
        self.assertFalse(q.is_correct({'A': 1, 'B': 2}))
        self.assertFalse(q.is_correct(['A', 'B', 'B']))
        self.assertFalse(q.is_correct(None))

    def test_single_and_text_require_a_string(self):
        single = self.q(type='single', options=['A', 'B'], correct_answer='A')
        self.assertTrue(single.is_correct('A'))
        self.assertFalse(single.is_correct(['A']))
        text = self.q(type='text', options=[], correct_answer='Фотосинтез')
        self.assertTrue(text.is_correct('  фотосинтез '))
        self.assertFalse(text.is_correct(['фотосинтез']))


class AnswerKeyValidationTests(TestCase):
    def test_model_clean_rejects_inconsistent_keys(self):
        bad = [
            ('single', ['A', 'B'], 'C'),
            ('single', ['A'], 'A'),
            ('single', ['A', 'A'], 'A'),
            ('multiple', ['A', 'B'], 'A'),
            ('multiple', ['A', 'B'], []),
            ('multiple', ['A', 'B'], ['A', 'Z']),
            ('text', ['A'], 'A'),
            ('text', [], ''),
        ]
        for qtype, options, answer in bad:
            with self.subTest(qtype=qtype, options=options, answer=answer):
                self.assertTrue(answer_key_errors(qtype, options, answer))
        self.assertEqual(answer_key_errors('multiple', ['A', 'B', 'C'], ['A', 'C']), {})

    def form(self, **data):
        topic = make_topic(0)
        payload = {'topic': topic.id, 'type': 'single', 'prompt': '?', 'order': 0, 'explanation': ''}
        payload.update(data)
        Form = modelform_factory(Question, form=AnswerKeyForm, fields=list(payload))
        return Form(data=payload)

    def test_admin_form_takes_plain_text(self):
        form = self.form(options='Кислород\nВодород\n\n', correct_answer=' Водород ')
        self.assertTrue(form.is_valid(), form.errors)
        q = form.save()
        self.assertEqual((q.options, q.correct_answer), (['Кислород', 'Водород'], 'Водород'))

        form = self.form(type='multiple', options='A\nB\nC', correct_answer='A\nC')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().correct_answer, ['A', 'C'])

    def test_admin_form_rejects_answer_not_in_options(self):
        form = self.form(options='A\nB', correct_answer='C')
        self.assertFalse(form.is_valid())
        self.assertIn('correct_answer', form.errors)

    def test_admin_form_shows_stored_json_as_lines(self):
        q = Question.objects.create(
            topic=make_topic(0), type='multiple', prompt='?', options=['A', 'B'], correct_answer=['A', 'B'],
        )
        Form = modelform_factory(Question, form=AnswerKeyForm, fields=['type', 'options', 'correct_answer'])
        bound = Form(instance=q)
        self.assertEqual(bound.initial['options'], 'A\nB')
        self.assertEqual(bound.initial['correct_answer'], 'A\nB')


class StaffApiValidationTests(APITestCase):
    def test_staff_api_rejects_bad_answer_key(self):
        topic = make_topic(0)
        staff = User.objects.create_user('staff', password='x', is_staff=True)
        self.client.force_authenticate(staff)
        res = self.client.post('/api/questions/', {
            'topic': topic.id, 'type': 'single', 'prompt': '?', 'options': ['A', 'B'], 'correct_answer': 'C',
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('correct_answer', res.data)


# Tests run without collectstatic, so skip the hashed-manifest storage used in production.
@override_settings(STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class AdminInlineSmokeTests(TestCase):
    def test_topic_admin_renders_and_saves_inline_tasks(self):
        topic = make_topic(1)
        q = topic.questions.first()
        admin_user = User.objects.create_superuser('root', password='x')
        self.client.force_login(admin_user)

        url = f'/admin/topics/topic/{topic.id}/change/'
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'a\nb</textarea>')

        prefix = 'questions'
        res = self.client.post(url, {
            'subject': topic.subject_id, 'name': topic.name, 'description': '', 'difficulty': 'easy', 'order': 0,
            'paragraphs-TOTAL_FORMS': 0, 'paragraphs-INITIAL_FORMS': 0,
            f'{prefix}-TOTAL_FORMS': 1, f'{prefix}-INITIAL_FORMS': 1,
            f'{prefix}-0-id': q.id, f'{prefix}-0-topic': topic.id, f'{prefix}-0-order': 0,
            f'{prefix}-0-type': 'multiple', f'{prefix}-0-prompt': 'Q0',
            f'{prefix}-0-options': 'a\nb\nc', f'{prefix}-0-correct_answer': 'a\nc', f'{prefix}-0-explanation': '',
        })
        self.assertEqual(res.status_code, 302, getattr(res, 'context', None) and res.context['errors'])
        q.refresh_from_db()
        self.assertEqual((q.type, q.options, q.correct_answer), ('multiple', ['a', 'b', 'c'], ['a', 'c']))
