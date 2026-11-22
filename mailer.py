"""Sähköpostin lähetys: Resend (RESEND_API_KEY) tai SMTP (SMTP_HOST, SMTP_USER, SMTP_PASS)."""
import base64, os, smtplib
from email.message import EmailMessage
import requests

MAIL_TO = os.environ.get("MAIL_TO", "samuli.riisio@nurminenlogistics.com")
XLSX_MIME = ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def configured():
    return bool(os.environ.get("RESEND_API_KEY") or os.environ.get("SMTP_HOST"))


def send(subject, body, attachment_path=None, to=None):
    to = to or MAIL_TO
    sender = os.environ.get("MAIL_FROM") or os.environ.get("SMTP_USER") or "rullat@localhost"
    name = os.path.basename(attachment_path) if attachment_path else None
    data = open(attachment_path, "rb").read() if attachment_path else None

    if os.environ.get("RESEND_API_KEY"):
        payload = {"from": sender, "to": [to], "subject": subject, "text": body}
        if data:
            payload["attachments"] = [{"filename": name, "content": base64.b64encode(data).decode()}]
        r = requests.post("https://api.resend.com/emails", json=payload, timeout=60,
                          headers={"Authorization": "Bearer " + os.environ["RESEND_API_KEY"]})
        if r.status_code >= 300:
            raise RuntimeError(f"Resend {r.status_code}: {r.text[:200]}")
        return

    host = os.environ.get("SMTP_HOST")
    if not host:
        raise RuntimeError("Sähköpostia ei ole määritetty (RESEND_API_KEY tai SMTP_HOST)")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg.set_content(body)
    if data:
        msg.add_attachment(data, maintype=XLSX_MIME[0], subtype=XLSX_MIME[1], filename=name)
    port = int(os.environ.get("SMTP_PORT", "587"))
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, timeout=60)
    else:
        s = smtplib.SMTP(host, port, timeout=60)
        s.starttls()
    try:
        if os.environ.get("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
        s.send_message(msg)
    finally:
        s.quit()
