from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0009_openaiusagelog"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="OpenAIUsageLog",
            new_name="AIUsageLog",
        ),
        migrations.AddField(
            model_name="puzzle",
            name="checkpoint_hints",
            field=models.TextField(
                blank=True,
                help_text="정답 체크포인트와 같은 순서로, 각 체크포인트 쪽으로 이끄는 힌트를 줄마다 하나씩 입력하세요.",
            ),
        ),
        migrations.AddField(
            model_name="gamesession",
            name="revealed_hint_texts",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="questionlog",
            name="revealed_checkpoints",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="questionlog",
            name="reported_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="questiontestcase",
            name="expected_label",
            field=models.CharField(
                choices=[
                    ("맞습니다", "맞습니다"),
                    ("일부만 맞습니다", "일부만 맞습니다"),
                    ("아닙니다", "아닙니다"),
                    ("질문이 모호합니다", "질문이 모호합니다"),
                    ("관계없습니다", "관계없습니다"),
                ],
                max_length=20,
            ),
        ),
    ]
