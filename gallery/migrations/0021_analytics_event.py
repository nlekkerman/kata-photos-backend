# Generated migration: 0021_analytics_event

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gallery', '0020_tag_seo_fields_mediaitem_tags_m2m'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalyticsEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(
                    choices=[('page_view', 'Page view'), ('video_play', 'Video play')],
                    max_length=40,
                )),
                ('page_path', models.CharField(blank=True, max_length=500)),
                ('video', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='analytics_events',
                    to='gallery.videoclip',
                )),
                ('album', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='analytics_events',
                    to='gallery.album',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(fields=['event_type'], name='analytics_event_type_idx'),
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(fields=['created_at'], name='analytics_created_at_idx'),
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(fields=['event_type', 'created_at'], name='analytics_type_created_idx'),
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(fields=['video', 'event_type'], name='analytics_video_type_idx'),
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(fields=['page_path', 'event_type'], name='analytics_path_type_idx'),
        ),
    ]
