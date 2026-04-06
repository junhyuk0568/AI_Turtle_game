from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0002_gamesession"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_text", models.TextField()),
                ("answer_label", models.CharField(default="AMBIGUOUS", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "game_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="question_logs",
                        to="game.gamesession",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
