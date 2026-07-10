"""
FastAPI webhook that Twilio calls every time an employee replies on
WhatsApp. Deploy this on Render (or any always-on host) and point
Twilio's "WHEN A MESSAGE COMES IN" webhook URL at:

    https://<your-render-app>.onrender.com/whatsapp-webhook

Run locally with:
    uvicorn webhook:app --reload
"""

import re
import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from twilio.twiml.messaging_response import MessagingResponse
from sheet_utils import mark_received, mark_done
from dotenv import load_dotenv

load_dotenv()

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


@app.post("/whatsapp-webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    from_number = form.get("From", "").replace("whatsapp:", "").replace("+", "").strip()
    body = form.get("Body", "").strip()

    reply_text = _handle_incoming(body, from_number)

    twiml = MessagingResponse()
    twiml.message(reply_text)
    return Response(content=str(twiml), media_type="application/xml")


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
