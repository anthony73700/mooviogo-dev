from django.db import migrations


def seed_more_lesquinade_photos(apps, schema_editor):
    RestaurantVenue = apps.get_model("restaurants", "RestaurantVenue")
    RestaurantVenuePhoto = apps.get_model("restaurants", "RestaurantVenuePhoto")

    venue = RestaurantVenue.objects.filter(slug="lesquinade", city_slug="marseille").first()
    if not venue:
        return

    existing_urls = set(
        RestaurantVenuePhoto.objects.filter(venue=venue).values_list("image_url", flat=True)
    )

    photos = [
        {
            "position": 4,
            "image_url": "https://images.unsplash.com/photo-1544148103-0773bf10d330?auto=format&fit=crop&w=1400&q=80",
            "caption": "Cuisine ouverte",
        },
        {
            "position": 5,
            "image_url": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=1400&q=80",
            "caption": "Terrasse en soirée",
        },
        {
            "position": 6,
            "image_url": "https://images.unsplash.com/photo-1551218808-94e220e084d2?auto=format&fit=crop&w=1400&q=80",
            "caption": "Plats signature",
        },
    ]

    for payload in photos:
        if payload["image_url"] in existing_urls:
            continue
        RestaurantVenuePhoto.objects.create(venue=venue, **payload)


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0004_restaurantvenuephoto"),
    ]

    operations = [
        migrations.RunPython(seed_more_lesquinade_photos, migrations.RunPython.noop),
    ]
