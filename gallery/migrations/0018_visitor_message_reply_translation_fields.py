# Generated migration: add translation audit fields to VisitorMessageReply

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gallery', '0017_visitor_message_comment_translation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='visitormessagereply',
            name='original_reply_body',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='visitormessagereply',
            name='sent_reply_body',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='visitormessagereply',
            name='visitor_language',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
        migrations.AddField(
            model_name='visitormessagereply',
            name='reply_language',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
        migrations.AddField(
            model_name='visitormessagereply',
            name='translation_applied',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='visitormessagereply',
            name='translation_skipped_reason',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='visitormessagereply',
            name='translation_error',
            field=models.TextField(blank=True, default=''),
        ),
    ]
