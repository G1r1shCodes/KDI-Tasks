"""
FastAPI webhook that Meta calls every time an employee replies on
WhatsApp. Deploy this on Render (or any always-on host) and configure
your WhatsApp Webhook URL in the Meta App Dashboard to point to:

    https://kdi-tasks.onrender.com/whatsapp-webhook

Run locally with:
    uvicorn webhook:app --reload
"""

import re
import os
import requests
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from sheet_utils import mark_received, mark_done
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")

app = FastAPI()


def _get_team_members_from_sheet():
    """Read unique (Assigned To, Phone) pairs from the Google Sheet.
    No env config needed — the sheet IS the source of truth."""
    from sheet_utils import get_all_tasks
    tasks = get_all_tasks()
    seen = {}
    for t in tasks:
        name = str(t.get("Assigned To", "")).strip()
        phone = str(t.get("Phone", "")).strip()
        if name and phone and name not in seen:
            seen[name] = phone
    return [{"name": n, "phone": p} for n, p in seen.items()]

TASK_ID_PATTERN = re.compile(r"\bT-?(\d+)\b", re.IGNORECASE)


def _send_meta_reply(phone: str, text: str):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text
        }
    }
    try:
        requests.post(url, headers=headers, json=payload).raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send reply to {phone}: {e}")

@app.get("/whatsapp-webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)

@app.post("/whatsapp-webhook")
async def whatsapp_webhook(request: Request):
    data = await request.json()
    
    if data.get("object") == "whatsapp_business_account":
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for msg in value["messages"]:
                        from_number = msg.get("from", "")
                        body = ""
                        if msg.get("type") == "text":
                            body = msg.get("text", {}).get("body", "").strip()
                        elif msg.get("type") == "button":
                            # For template quick reply buttons
                            body = msg.get("button", {}).get("text", "").strip()
                        elif msg.get("type") == "interactive":
                            # For interactive message buttons
                            body = msg.get("interactive", {}).get("button_reply", {}).get("title", "").strip()

                        if body:
                            reply_text = _handle_incoming(body, from_number)
                            if reply_text:
                                _send_meta_reply(from_number, reply_text)

    # Always return 200 OK so Meta doesn't retry
    return Response(content="OK", status_code=200)


def _handle_incoming(body: str, phone: str) -> str:
    match = TASK_ID_PATTERN.search(body)
    is_done_reply = "done" in body.lower()

    if match:
        task_id = f"T-{match.group(1)}"
        if is_done_reply:
            ok = mark_done(task_id)
            return (
                f"Marked {task_id} as DONE. Great work!"
                if ok else
                f"Couldn't find task {task_id} in the sheet — please check the ID."
            )
        else:
            mark_received(task_id=task_id)
            return f"Got it — noted you received {task_id}."

    if is_done_reply and not match:
        ok = mark_done(phone=phone)
        return (
            "Marked your latest task as DONE. Great work!"
            if ok else
            "Couldn't find any open tasks for you in the sheet."
        )

    if body.lower() in ("\u2705", "yes", "ok", "received"):
        task_id = mark_received(phone=phone)
        return (
            f"Got it \u2014 noted you received {task_id}."
            if task_id else
            "Got your confirmation, but couldn't match it to an open task."
        )

    return (
        "Sorry, I didn't understand that. Reply \"ok\" to confirm receipt, "
        "or \"done\" when finished."
    )


import pathlib

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = pathlib.Path("templates/admin.html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Admin Dashboard (templates/admin.html missing)</h1>")


@app.get("/team-members")
async def team_members():
    """Return team members pulled from the Google Sheet (unique assignee-phone pairs)."""
    try:
        members = _get_team_members_from_sheet()
        return JSONResponse(content={"members": members})
    except Exception as e:
        return JSONResponse(content={"members": [], "error": str(e)})

@app.get("/send-reminders")
async def trigger_reminders():
    from send_reminders import send_reminders
    try:
        send_reminders()
        return {"status": "success", "message": "Reminders sent successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/add-task")
async def api_add_task(request: Request):
    form = await request.form()
    task_data = {
        "Task ID": form.get("task_id", "").strip(),
        "Category": form.get("category", "").strip(),
        "Task Description": form.get("description", "").strip(),
        "Assigned To": form.get("assigned_to", "").strip(),
        "Phone": form.get("phone", "").strip(),
        "Deadline": form.get("deadline", "").strip(),
        "Priority": form.get("priority", "Medium").strip()
    }

    # --- Server-side validation ---
    errors = []

    # Required fields
    if not task_data["Task ID"]:
        errors.append("Task ID is required.")
    elif not re.match(r"^T-\d+$", task_data["Task ID"], re.IGNORECASE):
        errors.append("Task ID must be in format T-101, T-102, etc.")

    if not task_data["Task Description"]:
        errors.append("Task Description is required.")

    if not task_data["Phone"]:
        errors.append("Phone number is required.")
    elif not re.match(r"^91\d{10}$", task_data["Phone"]):
        errors.append("Phone must be 12 digits starting with 91 (e.g. 919876543210).")

    if task_data["Priority"] not in ("Low", "Medium", "High"):
        errors.append("Priority must be Low, Medium, or High.")

    if task_data["Deadline"]:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", task_data["Deadline"]):
            errors.append("Deadline must be a valid date (YYYY-MM-DD).")

    if errors:
        return {"status": "error", "message": " | ".join(errors)}

    try:
        from sheet_utils import add_task
        add_task(task_data)
        return {"status": "success", "message": f"Task {task_data['Task ID']} added to sheet!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
