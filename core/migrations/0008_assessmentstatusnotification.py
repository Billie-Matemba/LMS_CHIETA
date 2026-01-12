from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_globalbusinessrecord'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssessmentStatusNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(max_length=120)),
                ('notified_at', models.DateTimeField(auto_now_add=True)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='status_notifications', to='core.assessment')),
            ],
            options={
                'ordering': ['-notified_at'],
                'unique_together': {('assessment', 'status')},
            },
        ),
    ]
