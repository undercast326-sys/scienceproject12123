import json
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.mocktests.models import MockQuestion, MockTest
from apps.questions.models import Question
from apps.topics.management.commands.import_content import validate
from apps.topics.models import ContentImport, Paragraph, Subject, Topic

CONTENT = Path(settings.BASE_DIR) / 'content'
MATH_JSON = CONTENT / 'math.json'
FRONTEND = Path(settings.BASE_DIR).parent / 'frontend'


def sample(**overrides):
    data = {
        'subject': {'name': 'Математика', 'icon': '🧮', 'description': 'd'},
        'topics': [{
            'name': 'Тригонометрические неравенства',
            'description': '12.01 · 12.02',
            'paragraphs': [{'title': '12.01 Простейшие', 'content': 'Теория $\\sin x>0$\n\n[table]\na\tb'}],
            'tasks': [{
                'type': 'single', 'prompt': 'Решите $\\sin x>0$',
                'options': ['$(0;\\pi)$', '$(\\pi;2\\pi)$'], 'correct_answer': '$(0;\\pi)$',
            }],
        }],
    }
    data.update(overrides)
    return data


class ImportContentTests(TestCase):
    def write(self, data):
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(data, f, ensure_ascii=False)
        f.close()
        self.addCleanup(Path(f.name).unlink)
        return f.name

    def test_import_replaces_subject_topics_and_keeps_other_subjects(self):
        math = Subject.objects.create(name='Математика')
        Topic.objects.create(subject=math, name='Тестовая тема 1')
        other = Subject.objects.create(name='Физика')
        Topic.objects.create(subject=other, name='Механика')

        call_command('import_content', self.write(sample()), stdout=open('/dev/null', 'w'))

        self.assertEqual(list(math.topics.values_list('name', flat=True)), ['Тригонометрические неравенства'])
        self.assertTrue(other.topics.filter(name='Механика').exists())
        topic = math.topics.get()
        self.assertEqual(topic.paragraphs.count(), 1)
        q = topic.questions.get()
        self.assertTrue(q.is_correct('$(0;\\pi)$'))

    def test_unchanged_file_is_skipped_and_force_reimports(self):
        path = self.write(sample())
        call_command('import_content', path, stdout=open('/dev/null', 'w'))
        topic_id = Topic.objects.get().id
        call_command('import_content', path, stdout=open('/dev/null', 'w'))
        self.assertEqual(Topic.objects.get().id, topic_id)  # untouched
        call_command('import_content', path, '--force', stdout=open('/dev/null', 'w'))
        self.assertNotEqual(Topic.objects.get().id, topic_id)
        self.assertEqual(ContentImport.objects.count(), 1)

    def test_invalid_file_imports_nothing(self):
        bad = sample()
        bad['topics'][0]['tasks'][0]['correct_answer'] = 'нет такого варианта'
        Subject.objects.create(name='Математика')
        with self.assertRaises(CommandError):
            call_command('import_content', self.write(bad), stdout=open('/dev/null', 'w'))
        self.assertEqual(Topic.objects.count(), 0)
        self.assertFalse(ContentImport.objects.exists())


def mock_sample():
    return {
        'subject': {'name': 'Математика'},
        'mock_tests': [{
            'title': 'Вариант 1', 'duration_minutes': 80,
            'questions': [
                {'type': 'single', 'prompt': 'Вычислить: $2+2$', 'options': ['3', '4'], 'correct_answer': '4'},
                {'type': 'multiple', 'prompt': 'Корни $x^2=4$', 'options': ['2', '-2', '0'], 'correct_answer': ['2', '-2']},
            ],
        }],
    }


class ImportMockTestsTests(ImportContentTests.__bases__[0]):
    write = ImportContentTests.write

    def test_mock_tests_replace_only_mock_tests(self):
        math = Subject.objects.create(name='Математика')
        Topic.objects.create(subject=math, name='Теория остаётся')
        MockTest.objects.create(subject=math, title='Пробный вариант')

        call_command('import_content', self.write(mock_sample()), stdout=open('/dev/null', 'w'))

        self.assertTrue(math.topics.filter(name='Теория остаётся').exists())
        self.assertEqual(list(math.mock_tests.values_list('title', flat=True)), ['Вариант 1'])
        test = math.mock_tests.get()
        self.assertEqual(test.duration_minutes, 80)
        multi = test.questions.get(type='multiple')
        self.assertTrue(multi.is_correct(['-2', '2']))

    def test_one_bad_file_does_not_block_the_others(self):
        bad = mock_sample()
        bad['mock_tests'][0]['questions'][0]['correct_answer'] = '5'
        good = sample()
        with self.assertRaises(CommandError):
            call_command('import_content', self.write(bad), self.write(good), stdout=open('/dev/null', 'w'),
                         stderr=open('/dev/null', 'w'))
        self.assertTrue(Topic.objects.filter(name='Тригонометрические неравенства').exists())
        self.assertFalse(MockTest.objects.exists())


class BundledMockContentTests(TestCase):
    """The committed mock-test files must import, and every figure they use must exist in the frontend."""

    def test_mock_files_are_valid_and_import(self):
        for name, subject, tests in [('math_mock.json', 'Математика', 5),
                                     ('matgram_mock.json', 'Математическая грамотность', 20)]:
            with self.subTest(file=name):
                path = CONTENT / name
                data = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(validate(data), [])
                for test in data['mock_tests']:
                    for q in test['questions']:
                        for text in [q['prompt'], *q['options']]:
                            self.assertEqual(text.count('$') % 2, 0, text)
                            for img in re.findall(r'\[img:([^\]]+)\]', text):
                                self.assertTrue((FRONTEND / img).is_file(), img)
                call_command('import_content', str(path), stdout=open('/dev/null', 'w'))
                self.assertEqual(MockTest.objects.filter(subject__name=subject).count(), tests)
        self.assertEqual(MockQuestion.objects.count(), 225 + 198)


class BundledMathContentTests(TestCase):
    """The committed backend/content/math.json must always be importable."""

    def test_math_json_is_valid_and_imports(self):
        data = json.loads(MATH_JSON.read_text(encoding='utf-8'))
        self.assertEqual(validate(data), [])
        for topic in data['topics']:
            for task in topic['tasks']:
                for text in [task['prompt'], *task['options']]:
                    self.assertEqual(text.count('$') % 2, 0, text)

        call_command('import_content', str(MATH_JSON), stdout=open('/dev/null', 'w'))
        subject = Subject.objects.get(name='Математика')
        self.assertEqual(subject.topics.count(), len(data['topics']))
        self.assertEqual(Question.objects.filter(topic__subject=subject).count(),
                         sum(len(t['tasks']) for t in data['topics']))
        self.assertGreater(Paragraph.objects.filter(topic__subject=subject).count(), 50)
