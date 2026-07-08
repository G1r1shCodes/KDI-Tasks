"""
Run this to send a WhatsApp message for every task that hasn't had a
reminder sent yet. Run manually, or schedule it (cron / Task Scheduler /
Render Cron Job) to run daily.

    python send_reminders.py
"""

import os
from twilio.rest import Client
from sheet_utils import get_all_tasks, mark_reminder_sent
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_NUMBER = os.environ["TWILIO_WHATSAPP_NUMBER"]  # e.g. "whatsapp:+14155238886"

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def build_message(task):
    return (
        f"\U0001F4CB TASK {task['Task ID']}\n"
        f"Work: {task['Task Description']}\n"
        f"Category: {task.get('Category', '')}\n"
        f"Deadline: {task['Deadline']}\n"
        f"Priority: {task['Priority']}\n\n"
        f"Reply \u2705 to confirm you received this.\n"
        f"Reply \"done\" when finished."
    )


def send_reminders():
    tasks = get_all_tasks()
    sent_count = 0
    for task in tasks:
        already_sent = str(task.get("Reminder Sent", "")).strip().upper() == "TRUE"
        phone = str(task.get("Phone", "")).strip()
        if already_sent or not phone:
            continue

        to_number = f"whatsapp:+{phone}" if not phone.startswith("+") else f"whatsapp:{phone}"
        body = build_message(task)

        client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number,
            body=body,
        )
        mark_reminder_sent(task["Task ID"])
        sent_count += 1
        print(f"Sent {task['Task ID']} to {to_number}")

    print(f"Done. {sent_count} reminder(s) sent.")


if __name__ == "__main__":
    send_reminders()
