import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.mocktests.models import MockQuestion, MockTest
from apps.questions.models import Question, answer_key_errors
from apps.topics.models import ContentImport, Paragraph, Subject, Topic


def _question_problems(where, q):
    errors = answer_key_errors(q.get('type', 'single'), q.get('options', []), q.get('correct_answer'))
    if not str(q.get('prompt', '')).strip():
        errors['prompt'] = 'empty'
    return [f'{where}: {errors}'] if errors else []


def validate(data):
    """Return a list of human-readable problems; empty means the file can be imported."""
    problems = []
    subject = data.get('subject') or {}
    if not subject.get('name'):
        problems.append('subject.name is missing')
    if 'topics' not in data and 'mock_tests' not in data:
        problems.append('the file has neither "topics" nor "mock_tests"')
    for ti, topic in enumerate(data.get('topics') or []):
        where = f"topic {ti + 1} ({topic.get('name', '?')})"
        if not topic.get('name') or len(topic['name']) > 200:
            problems.append(f'{where}: name must be 1-200 characters')
        for pi, para in enumerate(topic.get('paragraphs') or []):
            if not para.get('title') or len(para['title']) > 200:
                problems.append(f'{where}, paragraph {pi + 1}: title must be 1-200 characters')
        for qi, task in enumerate(topic.get('tasks') or []):
            problems += _question_problems(f'{where}, task {qi + 1}', task)
    for mi, test in enumerate(data.get('mock_tests') or []):
        where = f"mock test {mi + 1} ({test.get('title', '?')})"
        if not test.get('title') or len(test['title']) > 200:
            problems.append(f'{where}: title must be 1-200 characters')
        if not test.get('questions'):
            problems.append(f'{where}: no questions')
        for qi, q in enumerate(test.get('questions') or []):
            problems += _question_problems(f'{where}, question {qi + 1}', q)
    return problems


class Command(BaseCommand):
    help = (
        'Load a subject\'s content from JSON files (see backend/content/). A file may hold "topics" '
        '(with theory paragraphs and tasks) and/or "mock_tests"; each section present in the file replaces '
        "that section of the subject - and with it the students' progress there - so a file is imported only "
        'when it changed since its last import (use --force to reload anyway). Other subjects and sections '
        'missing from the file are untouched.'
    )

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+')
        parser.add_argument('--force', action='store_true', help='Import even if this exact file was already imported.')

    def handle(self, paths, force=False, **options):
        failed = []
        for path in paths:
            try:
                self.import_file(path, force)
            except CommandError as exc:
                failed.append(path)
                self.stderr.write(str(exc))
        if failed:
            raise CommandError(f'Not imported: {", ".join(failed)}')

    def import_file(self, path, force):
        raw = Path(path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw)
        source = Path(path).name
        name = data['subject']['name']

        if not force and ContentImport.objects.filter(source=source, sha256=digest).exists():
            self.stdout.write(f'{source}: unchanged since the last import, skipping.')
            return

        problems = validate(data)
        if problems:
            shown = '\n'.join(problems[:20])
            raise CommandError(f'{len(problems)} problem(s) in {path}, nothing imported from it:\n{shown}')

        summary = []
        with transaction.atomic():
            s = data['subject']
            subject, _ = Subject.objects.update_or_create(
                name=name,
                defaults={k: s[k] for k in ('icon', 'description', 'order') if k in s},
            )
            if 'topics' in data:
                summary.append(self.replace_topics(subject, data['topics']))
            if 'mock_tests' in data:
                summary.append(self.replace_mock_tests(subject, data['mock_tests']))
            ContentImport.objects.update_or_create(source=source, defaults={'sha256': digest})

        self.stdout.write(self.style.SUCCESS(f'{source} → "{name}": imported {", ".join(summary)}.'))

    def replace_topics(self, subject, topics):
        subject.topics.all().delete()
        paragraphs, questions = [], []
        for order, t in enumerate(topics, start=1):
            topic = Topic.objects.create(
                subject=subject, name=t['name'], description=t.get('description', ''),
                difficulty=t.get('difficulty', 'medium'), order=order,
            )
            paragraphs += [
                Paragraph(topic=topic, title=p['title'], content=p.get('content', ''), order=i)
                for i, p in enumerate(t.get('paragraphs', []), start=1)
            ]
            questions += [
                Question(
                    topic=topic, type=q.get('type', 'single'), prompt=q['prompt'], options=q.get('options', []),
                    correct_answer=q['correct_answer'], explanation=q.get('explanation', ''), order=i,
                )
                for i, q in enumerate(t.get('tasks', []), start=1)
            ]
        Paragraph.objects.bulk_create(paragraphs, batch_size=500)
        Question.objects.bulk_create(questions, batch_size=500)
        return f'{len(topics)} topics, {len(paragraphs)} paragraphs, {len(questions)} tasks'

    def replace_mock_tests(self, subject, tests):
        subject.mock_tests.all().delete()
        questions = []
        for order, t in enumerate(tests, start=1):
            test = MockTest.objects.create(
                subject=subject, title=t['title'], description=t.get('description', ''),
                duration_minutes=t.get('duration_minutes', 60), order=order, is_published=t.get('is_published', True),
            )
            questions += [
                MockQuestion(
                    mock_test=test, type=q.get('type', 'single'), prompt=q['prompt'], options=q.get('options', []),
                    correct_answer=q['correct_answer'], explanation=q.get('explanation', ''), order=i,
                )
                for i, q in enumerate(t['questions'], start=1)
            ]
        MockQuestion.objects.bulk_create(questions, batch_size=500)
        return f'{len(tests)} mock tests with {len(questions)} questions'
