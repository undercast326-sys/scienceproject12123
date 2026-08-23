from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.topics.models import Subject


class Command(BaseCommand):
    help = (
        'Runs seed_test_data only if the Subject table is empty. Safe to run on '
        'every deploy - a no-op once any subject exists, so it never wipes real content.'
    )

    def handle(self, *args, **options):
        if Subject.objects.exists():
            self.stdout.write('Subjects already exist, skipping seed.')
            return

        self.stdout.write('No subjects found, running seed_test_data...')
        call_command('seed_test_data')
