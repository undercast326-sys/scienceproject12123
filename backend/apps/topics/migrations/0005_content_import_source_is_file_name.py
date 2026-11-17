from django.db import migrations


def forwards(apps, schema_editor):
    # Imports used to be keyed by subject name; they are now keyed by file name.
    # Rename the existing maths record so math.json isn't re-imported (which would wipe progress).
    ContentImport = apps.get_model('topics', 'ContentImport')
    ContentImport.objects.filter(source='Математика').update(source='math.json')


def backwards(apps, schema_editor):
    ContentImport = apps.get_model('topics', 'ContentImport')
    ContentImport.objects.filter(source='math.json').update(source='Математика')


class Migration(migrations.Migration):
    dependencies = [('topics', '0004_content_import')]
    operations = [migrations.RunPython(forwards, backwards)]
