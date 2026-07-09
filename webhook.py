"""
FastAPI webhook that Twilio calls every time an employee replies on
WhatsApp. Deploy this on Render (or any always-on host) and point
Twilio's "WHEN A MESSAGE COMES IN" webhook URL at:

    https://<your-render-app>.onrender.com/whatsapp-webhook

Run locally with:
    uvicorn webhook:app --reload
"""

import re
from fastapi import FastAPI, Request, Response
from twilio.twiml.messaging_response import MessagingResponse
from sheet_utils import mark_received, mark_done

app = FastAPI()

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


from fastapi.responses import HTMLResponse
import pathlib

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = pathlib.Path("admin.html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content="<h1>Admin Dashboard (admin.html missing)</h1>")

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
    
    if not task_data["Task ID"] or not task_data["Task Description"] or not task_data["Phone"]:
        return {"status": "error", "message": "Task ID, Description, and Phone are required."}
    
    try:
        from sheet_utils import add_task
        add_task(task_data)
        return {"status": "success", "message": f"Task {task_data['Task ID']} added to sheet!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
