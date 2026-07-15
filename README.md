# WhatsApp task reminder + auto-update bot

![Python](https://img.shields.io/badge/PYTHON-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FASTAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Meta](https://img.shields.io/badge/META-WHATSAPP-0668E1?style=for-the-badge&logo=meta&logoColor=white)
![Google Sheets](https://img.shields.io/badge/GOOGLE%20SHEETS-API-34A853?style=for-the-badge&logo=googlesheets&logoColor=white)
![Render](https://img.shields.io/badge/DEPLOYMENT-RENDER-000000?style=for-the-badge&logo=render&logoColor=white)

![Dashboard](assets/images/Task%20DashBoard.png)

Sends task reminders on WhatsApp, listens for replies, and updates a
Google Sheet (your Excel, but live and cloud-hosted) with status and
completion time automatically. Features a full operations dashboard for task creation and manual overrides.

## How it works
1. `send_reminders.py` reads open tasks from the sheet and sends each
   employee a WhatsApp message (via the official WhatsApp Meta API).
2. When they reply `ok` or `done`, Meta forwards that reply to
   `webhook.py`, which is deployed on Render and always listening.
3. The webhook updates the **Status**, **Received On**, and
   **Completed On** columns in the sheet — no manual work.
4. You can open the sheet anytime, or download it as `.xlsx`
   (File → Download → Microsoft Excel) for reporting.

---

## Step 1 — Set up WhatsApp Meta API
1. Create a Meta Developer Account and create an App (type: Business).
2. Add the **WhatsApp** product to your app.
3. In the WhatsApp API Setup section, you will be given a test phone number and a temporary access token.
4. (Recommended) Go to Meta Business Settings and create a System User to generate a **permanent access token**.
5. Note down your **Access Token**, the **Phone Number ID**, and make up a custom password for your **Verify Token**. You'll need these for your `.env` file.

## Step 2 — Set up the Google Sheet
1. Create a new Google Sheet, rename the tab to `Tasks`.
2. Row 1 headers (copy exactly):
   `Task ID | Date | Category | Task Description | Assigned To | Phone | Deadline | Priority | Status | Reminder Sent | Received On | Completed On | Time Taken`
3. Fill in your tasks (Phone should be like `1234567890` or `919876543210`, no `+`).
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
- `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`
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

## Step 5 — Connect Meta to your webhook
1. In the Meta App Dashboard → **WhatsApp → Configuration**.
2. Click **Edit** next to Webhook.
3. Enter your live Render URL: `https://your-app.onrender.com/whatsapp-webhook`
4. Enter your custom `WHATSAPP_VERIFY_TOKEN`. Click Verify and Save.
5. Under Webhook fields, click **Manage** and subscribe to **messages**.

## Step 6 — Send reminders
We have set up a **GitHub Action** (`send_reminders.yml`) that automatically runs this script every 15 minutes. 
To make it work, add your `.env` variables into your GitHub Repository under **Settings → Secrets and variables → Actions**.

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
- **24-Hour Rule**: Meta strictly enforces a 24-hour service window. Outbound free-form reminders will only reach users who have messaged the bot within the last 24 hours. For long-term production use without this restriction, you must create and use **Message Templates** in your WhatsApp Manager.
- Message format matches what you specified exactly — edit
  `build_message()` in `send_reminders.py` if you want to tweak wording.
