"""
Run this to send a WhatsApp message for every task that hasn't had a
reminder sent yet. Run manually, or schedule it (cron / Task Scheduler /
Render Cron Job) to run daily.

    python send_reminders.py
"""

import os
import requests
from sheet_utils import get_all_tasks, mark_reminder_sent
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")


def build_message(task):
    return (
        f"\U0001F4CB TASK {task['Task ID']}\n"
        f"Work: {task['Task Description']}\n"
        f"Category: {task.get('Category', '')}\n"
        f"Deadline: {task['Deadline']}\n"
        f"Priority: {task['Priority']}\n\n"
        f"Reply \"ok\" to confirm you received this.\n"
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

        # Ensure phone number is just digits
        phone = "".join(filter(str.isdigit, str(phone)))
        body = build_message(task)

        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": "task_reminder",
                "language": {
                    "code": "en"
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(task.get("Task ID", ""))},
                            {"type": "text", "text": str(task.get("Task Description", ""))},
                            {"type": "text", "text": str(task.get("Category", ""))},
                            {"type": "text", "text": str(task.get("Deadline", ""))},
                            {"type": "text", "text": str(task.get("Priority", ""))}
                        ]
                    }
                ]
            }
        }

        response = None
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            mark_reminder_sent(task["Task ID"])
            sent_count += 1
            print(f"Sent {task['Task ID']} to {phone}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send to {phone}. Error: {e}")
            if response is not None and response.content:
                print(f"Response content: {response.text}")

    print(f"Done. {sent_count} reminder(s) sent.")


if __name__ == "__main__":
    send_reminders()
