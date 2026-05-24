from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sorties", "0003_sortie_partner"),
    ]

    operations = [
        migrations.AddField(
            model_name="sortie",
            name="ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
