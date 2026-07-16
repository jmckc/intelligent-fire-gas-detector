"""
server/services/notifier.py
Twilio SMS + SMTP email notifications.
"""

import os, logging, smtplib
from email.mime.text      import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest           import Client as TwilioClient
from server.models.database import Contact

logger = logging.getLogger(__name__)

TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID",  "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN",   "")
TWILIO_FROM  = os.getenv("TWILIO_FROM_NUMBER",  "")
SMTP_HOST    = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER",     "")
SMTP_PASS    = os.getenv("SMTP_PASS",     "")
SMTP_FROM    = os.getenv("SMTP_FROM",     SMTP_USER)


def dispatch_notifications(event, reading) -> dict:
    contacts = Contact.query.filter_by(active=True).all()
    sms_ok = email_ok = False
    subject, body = _build_message(event, reading)
    for contact in contacts:
        if contact.phone:  sms_ok   = send_sms(contact.phone, body)   or sms_ok
        if contact.email:  email_ok = send_email(contact.email, subject, body) or email_ok
    return {"sms": sms_ok, "email": email_ok}


def send_sms(to_number: str, body: str) -> bool:
    if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM]):
        logger.warning("Twilio not configured — SMS skipped")
        return False
    try:
        twilio = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
        msg = twilio.messages.create(body=body[:1600], from_=TWILIO_FROM, to=to_number)
        logger.info("SMS sent: %s", msg.sid)
        return True
    except Exception as e:
        logger.error("SMS failed: %s", e)
        return False


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not all([SMTP_USER, SMTP_PASS]):
        logger.warning("SMTP not configured — email skipped")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_FROM
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo(); server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info("Email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Email failed: %s", e)
        return False


def _build_message(event, reading) -> tuple:
    subject = f"[EMERGENCY] Fire/Gas Detected — {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    body = (
        f"EMERGENCY ALERT\n{'='*40}\n"
        f"Time:         {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"Trigger:      {event.trigger_reason}\n"
        f"AI Decision:  {event.ai_decision} ({event.ai_confidence:.0%})\n"
        f"Reasoning:    {event.ai_reasoning}\n\n"
        f"Sensor Readings:\n"
        f"  Gas ADC:     {reading.gas_adc} / 1023\n"
        f"  Temperature: {reading.temperature} °C\n"
        f"  Humidity:    {reading.humidity} %\n"
        f"  Flame:       {'YES' if reading.flame_detected else 'No'}\n\n"
        f"Please check the premises immediately.\n"
    )
    return subject, body
