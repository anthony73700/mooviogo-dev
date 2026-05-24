from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("partners", "0006_backfill_partner_pro_offer_tier"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="partner",
            name="website",
        ),
    ]
