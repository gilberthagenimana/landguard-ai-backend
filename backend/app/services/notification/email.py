
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send a plain-text email through the configured SMTP provider."""

    if not settings.smtp_user or not settings.smtp_pass:
        raise RuntimeError("SMTP credentials are not configured.")

    if not settings.smtp_from_email:
        raise RuntimeError("SMTP sender email is not configured.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(
        (settings.smtp_from_name, settings.smtp_from_email)
    )
    message["To"] = to_email
    message.set_content(body)

    try:
        if settings.smtp_secure:
            with smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=20,
                context=ssl.create_default_context(),
            ) as server:
                server.login(settings.smtp_user, settings.smtp_pass)
                server.send_message(message)
        else:
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=20,
            ) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(settings.smtp_user, settings.smtp_pass)
                server.send_message(message)

        logger.info("Email successfully sent to %s", to_email)

    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send email to %s", to_email)
        raise
