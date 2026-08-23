from django.core.management.base import BaseCommand
from django.db import transaction

from apps.topics.models import Subject, Grade, Topic, TheoryMaterial
from apps.questions.models import Question


class Command(BaseCommand):
    help = (
        'Wipes Subject/Grade/Topic/TheoryMaterial/Question data (and anything that cascades '
        'from it - quiz sessions, answers, theory progress) and reseeds minimal placeholder '
        'test data: Математика + Математическая грамотность, grades 1-11, and a couple of '
        'test topics per subject with a theory block and dummy questions. Not real content - '
        'just enough to exercise the full API/UI wiring.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        Subject.objects.all().delete()
        Grade.objects.all().delete()

        self.stdout.write('Wiped existing curriculum data.')

        grades = {n: Grade.objects.create(number=n) for n in range(1, 12)}

        subjects = {
            'math': Subject.objects.create(
                name='Математика',
                icon='🧮',
                description='Алгебра, геометрия и арифметика.',
            ),
            'literacy': Subject.objects.create(
                name='Математическая грамотность',
                icon='📊',
                description='Практические задачи на проценты, пропорции и работу с данными.',
            ),
        }

        test_grade_numbers = [5, 8]

        for subject_key, subject in subjects.items():
            for i, grade_number in enumerate(test_grade_numbers, start=1):
                topic = Topic.objects.create(
                    subject=subject,
                    grade=grades[grade_number],
                    name='Тестовая тема',
                    description='Заглушка для проверки структуры раздела. Реальный материал появится позже.',
                    difficulty='easy',
                    order=1,
                )

                TheoryMaterial.objects.create(
                    topic=topic,
                    title='Тестовый теоретический материал',
                    content=(
                        'Это тестовый текст теоретического блока. Здесь появится реальная '
                        'учебная теория, которую студент должен прочитать перед практикой.'
                    ),
                    order=1,
                )

                Question.objects.create(
                    topic=topic,
                    type='single',
                    prompt='Тестовый вопрос 1 (заглушка, один правильный ответ)',
                    options=['Вариант A', 'Вариант B', 'Вариант C', 'Вариант D'],
                    correct_answer='Вариант A',
                    explanation='Это тестовое объяснение для проверки практики.',
                    order=1,
                )
                Question.objects.create(
                    topic=topic,
                    type='text',
                    prompt='Тестовый вопрос 2 (заглушка, текстовый ответ)',
                    options=[],
                    correct_answer='тест',
                    explanation='Это тестовое объяснение для текстового вопроса.',
                    order=2,
                )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {Subject.objects.count()} subjects, {Grade.objects.count()} grades, '
            f'{Topic.objects.count()} topics, {TheoryMaterial.objects.count()} theory blocks, '
            f'{Question.objects.count()} questions.'
        ))
