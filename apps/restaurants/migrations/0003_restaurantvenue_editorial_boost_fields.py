from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0002_restaurantvenue_owner_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurantvenue",
            name="editorial_boost_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Montant paye pour la mise en avant editoriale (EUR).",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="restaurantvenue",
            name="editorial_boost_ends_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Fin de la mise en avant editoriale.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="restaurantvenue",
            name="editorial_boost_starts_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Debut de la mise en avant editoriale.",
                null=True,
            ),
        ),
    ]