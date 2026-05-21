"""
Adds a single test failure row to the Google Sheet to verify the Apps Script alert fires.
Usage: python add_test_failure.py <path-to-service-account.json> <sheet-id>
"""
import datetime
import sys
from zoneinfo import ZoneInfo

import gspread

if len(sys.argv) != 3:
    print("Usage: python add_test_failure.py <path-to-service-account.json> <sheet-id>")
    sys.exit(1)

key_file = sys.argv[1]
sheet_id = sys.argv[2]

gc = gspread.service_account(filename=key_file)
ws = gc.open_by_key(sheet_id).sheet1

ts = datetime.datetime.now(ZoneInfo("Europe/Stockholm")).strftime("%Y-%m-%d %H:%M:%S")
row = [ts, "failure", "TEST_ITEM", 0.0, "", "Simulated failure — alert test"]

ws.append_row(row)
print(f"Test failure row added: {ts}")
print("Check your sheet and wait up to 30 min for the Apps Script alert email.")
