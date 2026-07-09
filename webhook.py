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


@app.get("/")
async def health_check():
    return {"status": "ok"}
