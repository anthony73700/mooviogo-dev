from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_user_phone_and_phone_verified_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="preferred_language",
            field=models.CharField(
                blank=True,
                choices=[("fr", "Francais"), ("en", "English")],
                default="",
                max_length=5,
            ),
        ),
    ]
