from django.db import connection, migrations


def add_website_column_if_missing(apps, schema_editor):
    table_name = "partners_partner"
    column_name = "website"

    with connection.cursor() as cursor:
        table_info = connection.introspection.get_table_description(cursor, table_name)
        existing_columns = {col.name for col in table_info}
        if column_name in existing_columns:
            return

        # Compatibility column for legacy processes/queries still selecting website.
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} varchar(200) NOT NULL DEFAULT ''")


def noop_reverse(apps, schema_editor):
    # Keep compatibility column on rollback to avoid reintroducing runtime breakages.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("partners", "0007_remove_partner_website"),
    ]

    operations = [
        migrations.RunPython(add_website_column_if_missing, noop_reverse),
    ]
