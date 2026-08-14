import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.core.registries.service.email_message import (
    EMAIL_SEND_ATTEMPT,
    EMAIL_SEND_SUCCESS,
    EMAIL_SEND_FAILED,
)

_logger = logging.getLogger(__name__)

SMTP_TIMEOUT = 10  # seconds


def _format_employee_name(employee_name: str) -> str:
    display_name = (employee_name or "").strip()

    if not display_name:
        return "คุณ"

    if display_name.startswith("คุณ"):
        return display_name

    return f"คุณ{display_name}"


def _build_message(
    to_email: str,
    email_from: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> MIMEMultipart:
    """Build a multipart email message with plain text and HTML alternatives."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> bool:
    """Low-level SMTP send. Returns True on success, False on failure."""
    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_user = settings.SMTP_USER
    smtp_pass = settings.SMTP_PASS
    email_from = settings.EMAIL_FROM or smtp_user

    if not smtp_host or not smtp_port:
        _logger.error(
            "SMTP not configured (SMTP_HOST=%s, SMTP_PORT=%s)", smtp_host, smtp_port
        )
        return False

    msg = _build_message(to_email, email_from, subject, text_body, html_body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(email_from, to_email, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        _logger.error("SMTP authentication failed for user=%s", smtp_user)
    except smtplib.SMTPConnectError:
        _logger.error("SMTP connection refused %s:%s", smtp_host, smtp_port)
    except smtplib.SMTPException as exc:
        _logger.error("SMTP error: %s", exc)
    except TimeoutError:
        _logger.error(
            "SMTP timeout after %ss connecting to %s:%s",
            SMTP_TIMEOUT,
            smtp_host,
            smtp_port,
        )
    except OSError as exc:
        _logger.error("SMTP network error: %s", exc)
    return False


def send_plain_password_email(
    to_email: str, employee_name: str, password: str, employee_id: str | None = None
) -> bool:
    """
    Send plain password via email (legacy/insecure method).

    WARNING: This is insecure. Only use for backwards compatibility.

    Returns True if the email was sent successfully, False otherwise.
    """
    subject = "ระบบให้บริการตนเอง GUTS ESS (Employee Self Service)"

    display_name = _format_employee_name(employee_name)
    emp_code = employee_id or "-"

    text_body = (
        f"เรียน {display_name}\n\n"
        f"ระบบให้บริการตนเอง\n"
        f"GUTS ESS (Employee Self Service)\n\n"
        f"ข้อมูลการเข้าระบบของท่านคือ\n\n"
        f"รหัสพนักงาน : {emp_code}\n"
        f"รหัสผ่าน : {password}\n\n"
        f"ระหว่างการทดสอบระบบ\n"
        f"หากท่านพบปัญหาการใช้งาน\n"
        f"ติดต่อช่องทางที่กำหนด\n"
        f"กลุ่มไลน์ \"GUTS ESS\" เท่านั้น\n\n"
        f"ขอแสดงความนับถือ\n"
        f"GUTS ESS"
    )
    
    html_body = f"""<html>
  <body style="font-family: Arial, 'Sarabun', sans-serif; line-height: 1.7; color: #222;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <p style="font-size: 18px; margin: 0 0 28px 0;">
        เรียน <strong>{display_name}</strong>
      </p>

      <p style="font-size: 20px; font-weight: 700; margin: 0 0 28px 0;">
        ระบบให้บริการตนเอง<br/>
        GUTS ESS (Employee Self Service)
      </p>

      <p style="font-size: 18px; margin: 0 0 18px 0;">
        ข้อมูลการเข้าระบบของท่านคือ
      </p>

      <p style="font-size: 18px; margin: 0 0 32px 0;">
        <strong>รหัสพนักงาน :</strong> {emp_code}<br/>
        <strong>รหัสผ่าน :</strong>
        <span style="font-size: 42px; color: #0047b3; font-weight: 700;">
          {password}
        </span>
      </p>

      <p style="font-size: 18px; margin: 0 0 32px 0;">
        ระหว่างการทดสอบระบบ<br/>
        หากท่านพบปัญหาการใช้งาน<br/>
        ติดต่อช่องทางที่กำหนด<br/>
        กลุ่มไลน์ <strong>"GUTS ESS"</strong> เท่านั้น
      </p>

      <p style="font-size: 18px; margin: 0;">
        ขอแสดงความนับถือ<br/>
        <strong>GUTS ESS</strong>
      </p>
    </div>
  </body>
</html>"""

    _logger.info(EMAIL_SEND_ATTEMPT.format(resource="Forgot-password", email=to_email))
    success = _send_email(to_email, subject, text_body, html_body)
    if success:
        _logger.info(EMAIL_SEND_SUCCESS.format(resource="Forgot-password", email=to_email))
    else:
        _logger.warning(EMAIL_SEND_FAILED.format(resource="Forgot-password", email=to_email))
    return success


def send_change_password_notification_email(
    to_email: str, employee_name: str, new_password: str, employee_id: str | None = None
) -> bool:
    """
    Send an email notifying the employee that their password has been changed,
    with the new password included.

    Returns True if the email was sent successfully, False otherwise.
    """
    subject = "ระบบให้บริการตนเอง GUTS ESS (Employee Self Service)"

    display_name = _format_employee_name(employee_name)
    emp_code = employee_id or "-"

    text_body = (
        f"เรียน {display_name}\n\n"
        f"ระบบให้บริการตนเอง\n"
        f"GUTS ESS (Employee Self Service)\n\n"
        f"ข้อมูลการเข้าระบบของท่านคือ\n\n"
        f"รหัสพนักงาน : {emp_code}\n"
        f"รหัสผ่าน : {new_password}\n\n"
        f"ระหว่างการทดสอบระบบ\n"
        f"หากท่านพบปัญหาการใช้งาน\n"
        f"ติดต่อช่องทางที่กำหนด\n"
        f"กลุ่มไลน์ \"GUTS ESS\" เท่านั้น\n\n"
        f"ขอแสดงความนับถือ\n"
        f"GUTS ESS"
    )
    
    html_body = f"""<html>
  <body style="font-family: Arial, 'Sarabun', sans-serif; line-height: 1.7; color: #222;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <p style="font-size: 18px; margin: 0 0 28px 0;">
        เรียน <strong>{display_name}</strong>
      </p>

      <p style="font-size: 20px; font-weight: 700; margin: 0 0 28px 0;">
        ระบบให้บริการตนเอง<br/>
        GUTS ESS (Employee Self Service)
      </p>

      <p style="font-size: 18px; margin: 0 0 18px 0;">
        ข้อมูลการเข้าระบบของท่านคือ
      </p>

      <p style="font-size: 18px; margin: 0 0 32px 0;">
        <strong>รหัสพนักงาน :</strong> {emp_code}<br/>
        <strong>รหัสผ่าน :</strong>
        <span style="font-size: 42px; color: #0047b3; font-weight: 700;">
          {new_password}
        </span>
      </p>

      <p style="font-size: 18px; margin: 0 0 32px 0;">
        ระหว่างการทดสอบระบบ<br/>
        หากท่านพบปัญหาการใช้งาน<br/>
        ติดต่อช่องทางที่กำหนด<br/>
        กลุ่มไลน์ <strong>"GUTS ESS"</strong> เท่านั้น
      </p>

      <p style="font-size: 18px; margin: 0;">
        ขอแสดงความนับถือ<br/>
        <strong>GUTS ESS</strong>
      </p>
    </div>
  </body>
</html>"""

    _logger.info(EMAIL_SEND_ATTEMPT.format(resource="Change-password", email=to_email))
    success = _send_email(to_email, subject, text_body, html_body)
    if success:
        _logger.info(EMAIL_SEND_SUCCESS.format(resource="Change-password", email=to_email))
    else:
        _logger.warning(EMAIL_SEND_FAILED.format(resource="Change-password", email=to_email))
    return success
