# Generated 2026-06-01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gallery', '0008_videoclip'),
    ]

    operations = [
        migrations.AddField(
            model_name='album',
            name='gallery_type',
            field=models.CharField(
                choices=[('image', 'Image Gallery'), ('video', 'Video Gallery')],
                default='image',
                max_length=10,
            ),
        ),
    ]
