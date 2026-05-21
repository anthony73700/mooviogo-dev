from django.db import migrations, models


def seed_esquinade_gallery(apps, schema_editor):
    RestaurantVenue = apps.get_model("restaurants", "RestaurantVenue")
    RestaurantVenuePhoto = apps.get_model("restaurants", "RestaurantVenuePhoto")

    venue = RestaurantVenue.objects.filter(slug="lesquinade", city_slug="marseille").first()
    if not venue:
        return

    if RestaurantVenuePhoto.objects.filter(venue=venue).exists():
        return

    photos = [
        {
            "position": 1,
            "image_url": "https://images.unsplash.com/photo-1559339352-11d035aa65de?auto=format&fit=crop&w=1400&q=80",
            "caption": "Salle principale",
        },
        {
            "position": 2,
            "image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1400&q=80",
            "caption": "Ambiance dinner",
        },
        {
            "position": 3,
            "image_url": "https://images.unsplash.com/photo-1550966871-3ed3cdb5ed0c?auto=format&fit=crop&w=1400&q=80",
            "caption": "Assiettes signature",
        },
    ]

    for payload in photos:
        RestaurantVenuePhoto.objects.create(venue=venue, **payload)


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0003_restaurantvenue_editorial_boost_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="RestaurantVenuePhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image_url", models.URLField()),
                ("caption", models.CharField(blank=True, max_length=140)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "venue",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="gallery_photos", to="restaurants.restaurantvenue"),
                ),
            ],
            options={
                "db_table": "restaurants_venue_photo",
                "ordering": ["position", "id"],
            },
        ),
        migrations.RunPython(seed_esquinade_gallery, migrations.RunPython.noop),
    ]
