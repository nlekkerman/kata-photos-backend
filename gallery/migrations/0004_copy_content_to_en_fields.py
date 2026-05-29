from django.db import migrations


def copy_to_en_fields(apps, schema_editor):
    Album = apps.get_model('gallery', 'Album')
    MediaItem = apps.get_model('gallery', 'MediaItem')

    for album in Album.objects.all():
        album.title_en = album.title
        album.description_en = album.description
        album.seo_title_en = album.seo_title
        album.seo_description_en = album.seo_description
        album.save(update_fields=[
            'title_en', 'description_en', 'seo_title_en', 'seo_description_en'
        ])

    for item in MediaItem.objects.all():
        item.title_en = item.title
        item.description_en = item.description
        item.alt_text_en = item.alt_text
        item.caption_en = item.caption
        item.save(update_fields=[
            'title_en', 'description_en', 'alt_text_en', 'caption_en'
        ])


def reverse_copy(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gallery', '0003_bilingual_fields'),
    ]

    operations = [
        migrations.RunPython(copy_to_en_fields, reverse_copy),
    ]
