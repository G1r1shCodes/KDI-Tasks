"""
Shared helper functions to read/write the Google Sheet that acts as our
task database (mirrors the columns from your original Excel file).

Sheet columns (row 1 = headers, exact names matter):
Task ID | Date | Category | Task Description | Assigned To | Phone |
Deadline | Priority | Status | Reminder Sent | Received On | Completed On
"""

import os
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_ID = os.environ["SHEET_ID"]          # the long ID from the sheet URL
SHEET_TAB_NAME = os.environ.get("SHEET_TAB_NAME", "Tasks")

HEADERS = [
    "Task ID", "Date", "Category", "Task Description", "Assigned To",
    "Phone", "Deadline", "Priority", "Status", "Reminder Sent",
    "Received On", "Completed On", "Time Taken",
]


def _get_client():
    """Authenticate using a service account. Credentials come from the
    GOOGLE_CREDENTIALS_JSON env var (paste the full service-account JSON
    content as the value)."""
    creds_raw = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(creds_raw)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_worksheet():
    client = _get_client()
    sh = client.open_by_key(SHEET_ID)
    return sh.worksheet(SHEET_TAB_NAME)


def get_all_tasks():
    """Returns list of dicts, one per task row."""
    ws = get_worksheet()
    return ws.get_all_records()  # uses row 1 as keys


def _col_index(header_name):
    return HEADERS.index(header_name) + 1  # gspread is 1-indexed


def find_row_by_task_id(ws, task_id):
    """Returns the 1-indexed sheet row number for a given Task ID, or None."""
    col_values = ws.col_values(_col_index("Task ID"))
    for i, val in enumerate(col_values, start=1):
        if val.strip().upper() == task_id.strip().upper():
            return i
    return None


def find_latest_open_task_for_phone(ws, phone):
    """Used when an employee replies just '✅' without a task ID — finds
    their most recent task that hasn't been marked Done yet."""
    records = ws.get_all_records()
    candidates = [
        (i, r) for i, r in enumerate(records, start=2)  # data starts row 2
        if str(r.get("Phone")).strip() == phone.strip()
        and str(r.get("Status")).strip().lower() != "done"
    ]
    if not candidates:
        return None
    return candidates[-1]  # most recently added


def mark_reminder_sent(task_id):
    ws = get_worksheet()
    row = find_row_by_task_id(ws, task_id)
    if row:
        ws.update_cell(row, _col_index("Reminder Sent"), "TRUE")


def mark_received(task_id=None, phone=None):
    ws = get_worksheet()
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M")
    if task_id:
        row = find_row_by_task_id(ws, task_id)
    else:
        found = find_latest_open_task_for_phone(ws, phone)
        row = found[0] if found else None
        task_id = found[1]["Task ID"] if found else None
    if row:
        ws.update_cell(row, _col_index("Received On"), now)
        ws.update_cell(row, _col_index("Status"), "Acknowledged")
    return task_id


def mark_done(task_id=None, phone=None):
    ws = get_worksheet()
    now_dt = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    now = now_dt.strftime("%Y-%m-%d %H:%M")
    
    if task_id:
        row = find_row_by_task_id(ws, task_id)
    else:
        found = find_latest_open_task_for_phone(ws, phone)
        row = found[0] if found else None
        task_id = found[1]["Task ID"] if found else None

    if row:
        ws.update_cell(row, _col_index("Status"), "Done")
        ws.update_cell(row, _col_index("Completed On"), now)
        
        # Calculate Time Taken
        received_on = str(ws.cell(row, _col_index("Received On")).value or "").strip()
        if received_on:
            try:
                received_dt = datetime.datetime.strptime(received_on, "%Y-%m-%d %H:%M")
                # Make received_dt timezone-aware (IST) so we can subtract it from now_dt
                received_dt = received_dt.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
                delta = now_dt - received_dt
                
                total_seconds = int(delta.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                
                if hours > 0:
                    time_taken = f"{hours}h {minutes}m"
                else:
                    time_taken = f"{minutes}m"
                    
                ws.update_cell(row, _col_index("Time Taken"), time_taken)
            except Exception:
                pass
                
        return True
    return False

def add_task(task_data):
    ws = get_worksheet()
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
    
    row_data = [
        task_data.get("Task ID", ""),
        now,
        task_data.get("Category", ""),
        task_data.get("Task Description", ""),
        task_data.get("Assigned To", ""),
        task_data.get("Phone", ""),
        task_data.get("Deadline", ""),
        task_data.get("Priority", "Medium"),
        "Open",
        "FALSE",
        "",
        "",
        ""
    ]
    ws.append_row(row_data)
