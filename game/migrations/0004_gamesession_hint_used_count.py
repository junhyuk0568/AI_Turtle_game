from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0003_questionlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="hint_used_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
