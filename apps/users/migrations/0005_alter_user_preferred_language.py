from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_user_preferred_language"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="preferred_language",
            field=models.CharField(
                blank=True,
                choices=[("fr", "Francais"), ("en", "English"), ("es", "Espanol")],
                default="",
                max_length=5,
            ),
        ),
    ]
