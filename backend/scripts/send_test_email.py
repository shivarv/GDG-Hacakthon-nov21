"""Send a test email to the support mailbox (GreenMail SMTP by default).

Usage:
    python scripts/send_test_email.py
    python scripts/send_test_email.py --subject "Re: [TCK-1] Login broken" --body "Still failing"
"""

import argparse
import smtplib
from email.message import EmailMessage

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="localhost")
parser.add_argument("--port", type=int, default=3025)
parser.add_argument("--to", default="support@helpdesk.local")
parser.add_argument("--from-addr", default="Jane Customer <jane@example.com>")
parser.add_argument("--subject", default="Urgent: cannot log in to my account")
parser.add_argument("--body", default="Hi team,\n\nI get an error every time I try to log in.\n\nThanks,\nJane")
args = parser.parse_args()

msg = EmailMessage()
msg["From"] = args.from_addr
msg["To"] = args.to
msg["Subject"] = args.subject
msg.set_content(args.body)

with smtplib.SMTP(args.host, args.port) as smtp:
    smtp.send_message(msg)
print(f"Sent '{args.subject}' to {args.to} via {args.host}:{args.port}")
