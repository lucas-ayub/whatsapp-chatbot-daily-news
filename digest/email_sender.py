"""Sends the digest by e-mail through Gmail (SMTP + an App Password).

Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD (https://myaccount.google.com/apppasswords).
The message goes from that address to itself, or to EMAIL_TO if set.
"""
import html
import logging
import os
import re
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage

log = logging.getLogger(__name__)

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465
_URL = re.compile(r"https?://[^\s<]+")
_BOLD = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")


def email_configured() -> bool:
    return bool(os.getenv("GMAIL_ADDRESS") and os.getenv("GMAIL_APP_PASSWORD"))


def to_html(text: str) -> str:
    """WhatsApp-style text -> simple HTML: *bold*, clickable links, line breaks."""
    out = html.escape(text, quote=False)
    out = _BOLD.sub(r"<b>\1</b>", out)
    out = _URL.sub(lambda m: f'<a href="{m.group(0)}">{m.group(0)}</a>', out)
    out = out.replace("\n", "<br>\n")
    return ('<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
            f'font-size:15px;line-height:1.5;max-width:720px">{out}</div>')


def build_email(text: str, d: date, sender: str, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"☀️ Resumo do dia {d:%d/%m/%Y}"
    msg["From"] = f"Resumo diário <{sender}>"
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(to_html(text), subtype="html")
    return msg


def send_email(text: str, d: date) -> None:
    sender = os.getenv("GMAIL_ADDRESS")
    password = (os.getenv("GMAIL_APP_PASSWORD") or "").replace(" ", "")
    if not sender or not password:
        raise RuntimeError("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD (in .env or GitHub Secrets).")
    to = os.getenv("EMAIL_TO") or sender
    msg = build_email(text, d, sender, to)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context(), timeout=60) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)
    log.info("E-mail sent to %s (%d chars).", to, len(text))
