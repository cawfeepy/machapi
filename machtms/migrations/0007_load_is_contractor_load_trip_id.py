from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('machtms', '0006_parsingsession_is_hidden'),
    ]

    operations = [
        migrations.AddField(
            model_name='load',
            name='is_contractor',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='load',
            name='trip_id',
            field=models.CharField(default='', max_length=50),
            preserve_default=False,
        ),
    ]
