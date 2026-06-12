from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('machtms', '0005_add_presigned_url_entry_point'),
    ]

    operations = [
        migrations.AddField(
            model_name='parsingsession',
            name='is_hidden',
            field=models.BooleanField(default=False),
        ),
    ]
