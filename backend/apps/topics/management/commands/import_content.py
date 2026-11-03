import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.questions.models import Question, answer_key_errors
from apps.topics.models import ContentImport, Paragraph, Subject, Topic


def validate(data):
    """Return a list of human-readable problems; empty means the file can be imported."""
    problems = []
    subject = data.get('subject') or {}
    if not subject.get('name'):
        problems.append('subject.name is missing')
    for ti, topic in enumerate(data.get('topics') or []):
        where = f"topic {ti + 1} ({topic.get('name', '?')})"
        if not topic.get('name') or len(topic['name']) > 200:
            problems.append(f'{where}: name must be 1-200 characters')
        for pi, para in enumerate(topic.get('paragraphs') or []):
            if not para.get('title') or len(para['title']) > 200:
                problems.append(f'{where}, paragraph {pi + 1}: title must be 1-200 characters')
        for qi, task in enumerate(topic.get('tasks') or []):
            errors = answer_key_errors(task.get('type', 'single'), task.get('options', []), task.get('correct_answer'))
            if not str(task.get('prompt', '')).strip():
                errors['prompt'] = 'empty'
            if errors:
                problems.append(f'{where}, task {qi + 1}: {errors}')
    return problems


class Command(BaseCommand):
    help = (
        "Load a subject's topics, theory paragraphs and tasks from a JSON file "
        '(see backend/content/). Replaces that subject\'s topics - and with them the '
        "students' progress on those topics - so it runs only when the file changed "
        'since the last import (use --force to reload anyway). Other subjects are untouched.'
    )

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--force', action='store_true', help='Import even if this exact file was already imported.')

    def handle(self, path, force=False, **options):
        raw = Path(path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw)
        name = data['subject']['name']

        if not force and ContentImport.objects.filter(source=name, sha256=digest).exists():
            self.stdout.write(f'"{name}": {path} is unchanged since the last import, skipping.')
            return

        problems = validate(data)
        if problems:
            shown = '\n'.join(problems[:20])
            raise CommandError(f'{len(problems)} problem(s) in {path}, nothing imported:\n{shown}')

        with transaction.atomic():
            s = data['subject']
            subject, _ = Subject.objects.update_or_create(
                name=name,
                defaults={k: s[k] for k in ('icon', 'description', 'order') if k in s},
            )
            subject.topics.all().delete()

            paragraphs, questions = [], []
            for order, t in enumerate(data['topics'], start=1):
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
            ContentImport.objects.update_or_create(source=name, defaults={'sha256': digest})

        self.stdout.write(self.style.SUCCESS(
            f'"{name}": imported {len(data["topics"])} topics, {len(paragraphs)} paragraphs, {len(questions)} tasks.'
        ))
