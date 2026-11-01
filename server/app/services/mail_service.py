from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from ..core.config import settings

log = logging.getLogger("wewin.mail")


def send_password_reset_code(to_email: str, code: str, minutes_valid: int) -> None:
    body = (
        "Hello,\n\n"
        f"Use this code to reset your WeWin password: {code}\n\n"
        f"The code expires in {minutes_valid} minutes. If you did not request a reset, "
        "you can ignore this email.\n\n— WeWin"
    )

    if not settings.smtp_host:
        log.warning("SMTP not configured. Password reset code for %s: %s", to_email, code)
        return

    msg = EmailMessage()
    msg["Subject"] = "Your WeWin password reset code"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:  # noqa: BLE001 - delivery failures must not reach the client
        log.exception("Failed to send password reset email to %s", to_email)
