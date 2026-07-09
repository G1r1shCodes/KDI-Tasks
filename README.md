# WhatsApp task reminder + auto-update bot

![Python](https://img.shields.io/badge/PYTHON-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FASTAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Twilio](https://img.shields.io/badge/TWILIO-WHATSAPP-F22F46?style=for-the-badge&logo=twilio&logoColor=white)
![Google Sheets](https://img.shields.io/badge/GOOGLE%20SHEETS-API-34A853?style=for-the-badge&logo=googlesheets&logoColor=white)
![Render](https://img.shields.io/badge/DEPLOYMENT-RENDER-000000?style=for-the-badge&logo=render&logoColor=white)

Sends task reminders on WhatsApp, listens for replies, and updates a
Google Sheet (your Excel, but live and cloud-hosted) with status and
completion time automatically.

## How it works
1. `send_reminders.py` reads open tasks from the sheet and sends each
   employee a WhatsApp message (via Twilio).
2. When they reply `ok` or `done`, Twilio forwards that reply to
   `webhook.py`, which is deployed on Render and always listening.
3. The webhook updates the **Status**, **Received On**, and
   **Completed On** columns in the sheet — no manual work.
4. You can open the sheet anytime, or download it as `.xlsx`
   (File → Download → Microsoft Excel) for reporting.

---

## Step 1 — Set up Twilio WhatsApp (free sandbox)
1. Create a free account at twilio.com.
2. In the Console, go to **Messaging → Try it out → Send a WhatsApp message**.
3. It gives you a sandbox number (usually `+14155238886`) and a join
   code like `join xxxx-xxxx`.
4. Every employee must send that join code once to that number on
   WhatsApp — this is a sandbox limitation. (For production without
   this step, you'd apply for a permanent Twilio WhatsApp number later —
   same code, just swap the number.)
5. Copy your **Account SID** and **Auth Token** from the Twilio Console
   dashboard — you'll need them for `.env`.

## Step 2 — Set up the Google Sheet
1. Create a new Google Sheet, rename the tab to `Tasks`.
2. Row 1 headers (copy exactly):
   `Task ID | Date | Category | Task Description | Assigned To | Phone | Deadline | Priority | Status | Reminder Sent | Received On | Completed On | Time Taken`
3. Fill in your tasks (Phone should be like `1234567890`, no `+`).
4. Go to **Google Cloud Console** → create a project → enable the
   **Google Sheets API** → create a **Service Account** → create a JSON
   key and download it.
5. Open the JSON file, copy its entire contents.
6. Share your Google Sheet with the service account's email address
   (found in the JSON, looks like `xxx@xxx.iam.gserviceaccount.com`) —
   give it **Editor** access.
7. Copy the Sheet ID from its URL:
   `docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

## Step 3 — Configure environment variables
Copy `.env.example` to `.env` and fill in:
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`
- `SHEET_ID`
- `GOOGLE_CREDENTIALS_JSON` — paste the full JSON key content as one line

## Step 4 — Deploy the webhook to Render (free)
1. Push this folder to a GitHub repo.
2. On render.com → **New → Web Service** → connect your repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn webhook:app --host 0.0.0.0 --port $PORT`
5. Under **Environment**, add all the variables from your `.env`.
6. Deploy. Render gives you a URL like `https://your-app.onrender.com`.

   Note: We have added a GitHub Action (`keep_alive.yml`) that automatically pings your Render URL every 10 minutes, so your free server will never go to sleep!

## Step 5 — Connect Twilio to your webhook
1. In Twilio Console → **Messaging → WhatsApp Sandbox Settings**.
2. Set "WHEN A MESSAGE COMES IN" to:
   `https://your-app.onrender.com/whatsapp-webhook`
3. Method: `HTTP POST`. Save.

## Step 6 — Send reminders
We have set up a **GitHub Action** (`send_reminders.yml`) that automatically runs this script every 15 minutes. 
To make it work, add your 5 `.env` variables into your GitHub Repository under **Settings → Secrets and variables → Actions**.

To run it manually on your computer for testing:
```bash
pip install -r requirements.txt
python send_reminders.py
```
*(It will automatically read your local `.env` file!)*

## Testing it end-to-end
1. Run `send_reminders.py` — you should get a WhatsApp message.
2. Reply `ok` — check the sheet, "Received On" should fill in with the current Indian Standard Time (IST).
3. Reply `done` — check the sheet, "Status" becomes `Done` and
   "Completed On" and "Time Taken" fill in.

## Notes
- Message format matches what you specified exactly — edit
  `build_message()` in `send_reminders.py` if you want to tweak wording.
- To move off the Twilio sandbox for full production use later (no
  join-code step for employees), apply for a Twilio WhatsApp Sender —
  same code works, just update `TWILIO_WHATSAPP_NUMBER`.
