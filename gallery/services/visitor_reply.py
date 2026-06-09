"""
Service for preparing the email body sent to a visitor when Kata/admin replies.

Translation decision logic:

    visitor_language = detected language of original visitor message
    reply_language   = detected language of admin reply body

    LOCAL_REPLY_LANGUAGES = {bs, hr, sr, sh}  (Bosnian/Croatian/Serbian/Serbo-Croatian family)

    if visitor_language is unknown:
        send admin reply as-is
        record translation_skipped_reason

    elif reply_language == visitor_language:
        send admin reply as-is  (already the right language)

    elif visitor_language and reply_language are both in LOCAL_REPLY_LANGUAGES:
        send admin reply as-is  (same local language family — no translation needed)

    elif reply_language is in LOCAL_REPLY_LANGUAGES:
        translate reply from local language → visitor_language and send translated body

    else:
        send admin reply as-is
        record translation_skipped_reason (reply is not in local family, no rule covers it)

On translation failure: send the original admin reply and record the error.

Public API:
    prepare_visitor_reply_for_email(visitor_message, admin_reply_body) -> PreparedVisitorReply
"""

import dataclasses
import logging
import re

logger = logging.getLogger(__name__)

# Language codes treated as the same local admin language family for translation purposes.
LOCAL_REPLY_LANGUAGES: frozenset[str] = frozenset({"bs", "hr", "sr", "sh"})


def is_local_reply_language(language_code: str | None) -> bool:
    """Return True if *language_code* is in the Bosnian/Croatian/Serbian/Serbo-Croatian family."""
    return (language_code or "").lower() in LOCAL_REPLY_LANGUAGES


@dataclasses.dataclass
class PreparedVisitorReply:
    """Result of prepare_visitor_reply_for_email."""

    body_to_send: str
    visitor_language: str           # detected language of the original visitor message
    reply_language: str             # detected language of the admin reply
    translation_applied: bool       # True if a Bosnian reply was translated
    translation_skipped_reason: str # non-empty if translation was skipped for a reason
    translation_error: str          # non-empty if translation was attempted but failed


def prepare_visitor_reply_for_email(
    visitor_message,
    admin_reply_body: str,
) -> PreparedVisitorReply:
    """
    Decide whether to translate ``admin_reply_body`` before emailing it.

    Args:
        visitor_message:  A ``VisitorMessage`` instance.  Only ``message`` is read.
        admin_reply_body: The raw reply body written by Kata/admin.

    Returns:
        A ``PreparedVisitorReply`` with all decision fields populated.
        Never raises.
    """
    from .translation import detect_language, translate_bs_to_language

    visitor_text = (visitor_message.message or "").strip()
    reply_text   = (admin_reply_body or "").strip()

    # Detect languages — failures return 'unknown', never raise.
    visitor_language = detect_language(visitor_text) if visitor_text else 'unknown'
    reply_language   = detect_language(reply_text)   if reply_text   else 'unknown'

    # --- Decision logic ---

    if visitor_language == 'unknown':
        reason = 'visitor_language_unknown'
        logger.info(
            "Reply translation skipped for VisitorMessage pk=%s: %s",
            getattr(visitor_message, 'pk', '?'),
            reason,
        )
        return PreparedVisitorReply(
            body_to_send=admin_reply_body,
            visitor_language=visitor_language,
            reply_language=reply_language,
            translation_applied=False,
            translation_skipped_reason=reason,
            translation_error='',
        )

    if reply_language == visitor_language:
        # Admin already replied in the visitor's language.
        return PreparedVisitorReply(
            body_to_send=admin_reply_body,
            visitor_language=visitor_language,
            reply_language=reply_language,
            translation_applied=False,
            translation_skipped_reason='languages_already_match',
            translation_error='',
        )

    if is_local_reply_language(visitor_language) and is_local_reply_language(reply_language):
        # Both visitor and reply are in the local language family; no translation needed.
        return PreparedVisitorReply(
            body_to_send=admin_reply_body,
            visitor_language=visitor_language,
            reply_language=reply_language,
            translation_applied=False,
            translation_skipped_reason='visitor_and_reply_same_local_language_family',
            translation_error='',
        )

    if is_local_reply_language(reply_language):
        # Guard: visitor_language must be a simple valid code before calling translation.
        if not re.fullmatch(r'[a-z]{2,3}', visitor_language):
            reason = 'visitor_language_invalid'
            logger.warning(
                "Reply translation skipped for VisitorMessage pk=%s: %s (code=%r)",
                getattr(visitor_message, 'pk', '?'),
                reason,
                visitor_language,
            )
            return PreparedVisitorReply(
                body_to_send=admin_reply_body,
                visitor_language=visitor_language,
                reply_language=reply_language,
                translation_applied=False,
                translation_skipped_reason=reason,
                translation_error='',
            )
        # Admin replied in local language (bs/hr/sr/sh); visitor expects a different language — translate.
        translated_body, error = translate_bs_to_language(admin_reply_body, visitor_language)

        if error or not translated_body:
            err_msg = error or 'Translation returned empty content.'
            logger.error(
                "Reply translation failed for VisitorMessage pk=%s (%s→%s): %s",
                getattr(visitor_message, 'pk', '?'),
                reply_language,
                visitor_language,
                err_msg,
            )
            return PreparedVisitorReply(
                body_to_send=admin_reply_body,
                visitor_language=visitor_language,
                reply_language=reply_language,
                translation_applied=False,
                translation_skipped_reason='',
                translation_error=err_msg,
            )

        return PreparedVisitorReply(
            body_to_send=translated_body,
            visitor_language=visitor_language,
            reply_language=reply_language,
            translation_applied=True,
            translation_skipped_reason='',
            translation_error='',
        )

    # Reply is not in the local language family and not the visitor's language — send as-is.
    reason = f'reply_language_{reply_language}_not_local_and_not_visitor_language'
    logger.info(
        "Reply translation skipped for VisitorMessage pk=%s: %s",
        getattr(visitor_message, 'pk', '?'),
        reason,
    )
    return PreparedVisitorReply(
        body_to_send=admin_reply_body,
        visitor_language=visitor_language,
        reply_language=reply_language,
        translation_applied=False,
        translation_skipped_reason=reason,
        translation_error='',
    )
