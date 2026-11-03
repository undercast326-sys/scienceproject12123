from django.core.management.base import BaseCommand
from django.db import transaction

from apps.topics.models import Subject, Topic, Paragraph
from apps.questions.models import Question
from apps.mocktests.models import MockTest, MockQuestion


class Command(BaseCommand):
    help = (
        'Wipes Subject/Topic/Paragraph/Question/MockTest data (and anything that cascades '
        'from it - quiz sessions, answers, paragraph progress, mock attempts) and reseeds minimal '
        'placeholder test data: two subjects, a couple of test topics each with paragraphs and '
        'tasks, and one mock test per subject. Not real content - just enough to exercise the '
        'full API/UI wiring.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        Subject.objects.all().delete()
        self.stdout.write('Wiped existing curriculum data.')

        subjects = [
            Subject.objects.create(
                name='Математика', icon='🧮', order=1,
                description='Алгебра, геометрия и арифметика.',
            ),
            Subject.objects.create(
                name='Математическая грамотность', icon='📊', order=2,
                description='Практические задачи на проценты, пропорции и работу с данными.',
            ),
        ]

        for subject in subjects:
            for t in range(1, 3):
                topic = Topic.objects.create(
                    subject=subject,
                    name=f'Тестовая тема {t}',
                    description='Заглушка для проверки структуры раздела. Реальный материал появится позже.',
                    difficulty='easy' if t == 1 else 'medium',
                    order=t,
                )
                for p in range(1, 3):
                    Paragraph.objects.create(
                        topic=topic,
                        title=f'§{p}. Тестовый параграф',
                        content=(
                            'Это тестовый текст параграфа. Здесь появится реальная учебная теория, '
                            'которую нужно прочитать перед выполнением заданий.\n\n'
                            'Второй абзац — чтобы проверить разбиение текста на абзацы.'
                        ),
                        order=p,
                    )
                Question.objects.create(
                    topic=topic, type='single', order=1,
                    prompt='Тестовое задание 1 (один правильный ответ)',
                    options=['Вариант A', 'Вариант B', 'Вариант C', 'Вариант D'],
                    correct_answer='Вариант A',
                    explanation='Это тестовое объяснение для проверки практики.',
                )
                Question.objects.create(
                    topic=topic, type='multiple', order=2,
                    prompt='Тестовое задание 2 (несколько правильных ответов)',
                    options=['Вариант A', 'Вариант B', 'Вариант C', 'Вариант D'],
                    correct_answer=['Вариант A', 'Вариант C'],
                    explanation='Верны A и C.',
                )
                Question.objects.create(
                    topic=topic, type='text', order=3,
                    prompt='Тестовое задание 3 (текстовый ответ)',
                    options=[],
                    correct_answer='тест',
                    explanation='Это тестовое объяснение для текстового задания.',
                )

            mock = MockTest.objects.create(
                subject=subject,
                title='Пробный вариант 1',
                description='Тестовый пробный вариант. Настоящие варианты появятся позже.',
                duration_minutes=10,
                order=1,
            )
            for i in range(1, 6):
                MockQuestion.objects.create(
                    mock_test=mock, type='single', order=i,
                    prompt=f'Вопрос пробного теста {i}',
                    options=['Вариант A', 'Вариант B', 'Вариант C', 'Вариант D'],
                    correct_answer='Вариант A',
                    explanation=f'Пояснение к вопросу {i}.',
                )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {Subject.objects.count()} subjects, {Topic.objects.count()} topics, '
            f'{Paragraph.objects.count()} paragraphs, {Question.objects.count()} tasks, '
            f'{MockTest.objects.count()} mock tests with {MockQuestion.objects.count()} questions.'
        ))
