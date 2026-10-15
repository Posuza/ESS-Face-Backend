from __future__ import annotations

import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.shared.config import settings


_logger = logging.getLogger(__name__)
SMTP_TIMEOUT_SECONDS = 10


def email_delivery_configured() -> bool:
    return bool(
        settings.SMTP_HOST
        and settings.SMTP_PORT
        and (settings.EMAIL_FROM or settings.SMTP_USER)
    )


def _employee_name(value: str) -> str:
    name = (value or "").strip()
    if not name:
        return "คุณ"
    return name if name.startswith("คุณ") else f"คุณ{name}"


def _send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> bool:
    sender = settings.EMAIL_FROM or settings.SMTP_USER
    if not email_delivery_configured():
        _logger.error("SMTP is not configured for password email delivery")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_email
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=SMTP_TIMEOUT_SECONDS,
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if settings.SMTP_USER and settings.SMTP_PASS:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.sendmail(sender, [to_email], message.as_string())
        return True
    except (OSError, smtplib.SMTPException):
        _logger.exception("Unable to deliver password email to %s", to_email)
        return False


def send_password_email(
    *,
    to_email: str,
    employee_name: str,
    employee_code: str,
    password: str,
    changed: bool = False,
) -> bool:
    display_name = _employee_name(employee_name)
    heading = "รหัสผ่านของคุณได้รับการเปลี่ยนแล้ว" if changed else "ข้อมูลการเข้าสู่ระบบของคุณ"
    subject = "ระบบให้บริการตนเอง GUTS ESS (Employee Self Service)"
    text_body = (
        f"เรียน {display_name}\n\n"
        f"{heading}\n\n"
        f"รหัสพนักงาน: {employee_code}\n"
        f"รหัสผ่าน: {password}\n\n"
        "หากพบปัญหา กรุณาติดต่อกลุ่มไลน์ GUTS ESS"
    )
    html_body = (
        "<html><body style=\"font-family:Arial,'Sarabun',sans-serif;line-height:1.7;color:#222\">"
        f"<p>เรียน <strong>{html.escape(display_name)}</strong></p>"
        f"<p><strong>{html.escape(heading)}</strong></p>"
        f"<p>รหัสพนักงาน: <strong>{html.escape(employee_code)}</strong><br>"
        f"รหัสผ่าน: <strong style=\"font-size:28px;color:#07577d\">{html.escape(password)}</strong></p>"
        "<p>หากพบปัญหา กรุณาติดต่อกลุ่มไลน์ <strong>GUTS ESS</strong></p>"
        "</body></html>"
    )
    return _send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
