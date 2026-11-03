# Restructure: Subject -> Topic -> Paragraph (theory) + tasks. Grades are gone.
# Written by hand so existing rows are renamed, not dropped and recreated.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('topics', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(old_name='TheoryMaterial', new_name='Paragraph'),
        migrations.RenameModel(old_name='TheoryProgress', new_name='ParagraphProgress'),
        migrations.RenameField(model_name='paragraphprogress', old_name='theory', new_name='paragraph'),
        migrations.AlterField(
            model_name='paragraph',
            name='topic',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='paragraphs', to='topics.topic'),
        ),
        migrations.AlterField(
            model_name='paragraphprogress',
            name='user',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='paragraph_progress', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(name='paragraphprogress', unique_together={('user', 'paragraph')}),
        migrations.RemoveIndex(model_name='topic', name='topics_topi_subject_8dffad_idx'),
        migrations.RemoveField(model_name='topic', name='grade'),
        migrations.DeleteModel(name='Grade'),
        migrations.AlterModelOptions(name='topic', options={'ordering': ['order', 'id']}),
        migrations.AddIndex(
            model_name='topic',
            index=models.Index(fields=['subject', 'order'], name='topics_topi_subject_a5cd22_idx'),
        ),
        migrations.AddField(
            model_name='subject',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterModelOptions(name='subject', options={'ordering': ['order', 'name']}),
    ]
