import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.questions.models import Question
from apps.topics.management.commands.import_content import validate
from apps.topics.models import ContentImport, Paragraph, Subject, Topic

MATH_JSON = Path(settings.BASE_DIR) / 'content' / 'math.json'


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
