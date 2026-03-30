"""
SMS notification service via Twilio.
Відправляє SMS студентам при виставленні оцінки або пропуску.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(to_phone: str, message: str) -> bool:
    """
    Відправляє SMS на вказаний номер телефону.
    Повертає True при успіху, False при помилці.
    """
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", None)

    if not all([account_sid, auth_token, from_number]):
        logger.warning(
            "SMS не відправлено: Twilio не налаштовано (TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER)"
        )
        return False

    if not to_phone:
        logger.debug("SMS не відправлено: у студента не вказаний номер телефону")
        return False

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        client.messages.create(
            body=message,
            from_=from_number,
            to=to_phone,
        )
        logger.info("SMS успішно відправлено на %s", to_phone)
        return True
    except ImportError:
        logger.error(
            "SMS не відправлено: пакет 'twilio' не встановлено. Виконайте: pip install twilio"
        )
        return False
    except Exception:
        logger.exception("SMS не відправлено: помилка при відправці на %s", to_phone)
        return False


def notify_grade(student, subject_name: str, lesson_date: str, grade_value) -> bool:
    """Відправляє SMS студенту про нову оцінку."""
    if not student.phone:
        return False
    message = (
        f"MyBosco: Нова оцінка з {subject_name}\n"
        f"Дата: {lesson_date}\n"
        f"Оцінка: {grade_value} балів"
    )
    return send_sms(student.phone, message)


def notify_absence(
    student, subject_name: str, lesson_date: str, absence_name: str, absence_code: str
) -> bool:
    """Відправляє SMS студенту про відмічений пропуск."""
    if not student.phone:
        return False
    message = (
        f"MyBosco: Відмічено пропуск з {subject_name}\n"
        f"Дата: {lesson_date}\n"
        f"Причина: {absence_name} ({absence_code})"
    )
    return send_sms(student.phone, message)
