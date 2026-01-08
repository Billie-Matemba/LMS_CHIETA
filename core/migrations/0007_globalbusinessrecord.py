from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_alter_examnode_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="GlobalBusinessRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("school", models.CharField(max_length=255)),
                ("country", models.CharField(blank=True, max_length=100)),
                ("continent", models.CharField(blank=True, max_length=100)),
                ("learners", models.PositiveIntegerField(default=0)),
                ("submissions", models.PositiveIntegerField(default=0)),
                (
                    "pass_rate",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=6, null=True
                    ),
                ),
                (
                    "average_score",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=6, null=True
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["school"],
            },
        ),
    ]
