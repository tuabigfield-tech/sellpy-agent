# Sellpy Bot — System Documentation

## Overview

The Sellpy Bot is an automated monitoring tool that logs in to sellpy.se, adds a product to the cart, waits 2 minutes, then removes it. Each run is logged to a Google Sheet. If a run fails, an alert email is sent automatically. The entire system runs in the cloud with no local infrastructure required.

---

## Architecture

```
Google Cloud Scheduler
        │
        │  POST /dispatches (every 20 min)
        ▼
GitHub Actions (sellpy_bot.yml)
        │
        │  runs sellpy_bot.py
        ▼
Playwright + Chromium (headless)
        │
        ├──► sellpy.se (login → add to cart → wait → remove)
        │
        └──► Google Sheets (log each run result)
                │
                ▼
        Google Apps Script (checks sheet every 30 min → sends alert email on failure)
```

---

## Components

### 1. Google Cloud Scheduler

**Project:** Google Cloud Console → Cloud Scheduler
**Job name:** `sellpy-bot-trigger`
**Region:** `europe-west1`
**Schedule:** `0,20,40 * * * *` (Europe/Stockholm) — runs at :00, :20, and :40 every hour

**What it does:** Sends an authenticated HTTP POST to the GitHub API to trigger a `workflow_dispatch` event on the bot workflow.

**Configuration:**
| Field | Value |
|---|---|
| URL | `https://api.github.com/repos/tuabigfield-tech/sellpy-agent/actions/workflows/sellpy_bot.yml/dispatches` |
| Method | `POST` |
| Header: Authorization | `Bearer <GITHUB_PAT>` |
| Header: Accept | `application/vnd.github+json` |
| Header: Content-Type | `application/json` |
| Body | `{"ref": "main"}` |

The GitHub PAT must have **Actions: Read and write** permission scoped to the `sellpy-agent` repository.

---

### 2. GitHub Actions — `sellpy_bot.yml`

**File:** `.github/workflows/sellpy_bot.yml`
**Trigger:** `workflow_dispatch` only (fired exclusively by Cloud Scheduler)
**Runner:** `ubuntu-latest`
**Timeout:** 12 minutes (protects against hangs)

**Steps:**
1. Checkout code
2. Set up Python 3.12 (with pip cache)
3. Install Python dependencies (`playwright`, `python-dotenv`, `gspread`)
4. Install Playwright Chromium + system dependencies
5. Run `sellpy_bot.py` with secrets injected as environment variables

**GitHub Secrets required:**
| Secret | Description |
|---|---|
| `SELLPY_EMAIL` | Sellpy account email |
| `SELLPY_PASSWORD` | Sellpy account password |
| `GOOGLE_CREDENTIALS_JSON` | Full JSON of the Google Service Account key |
| `GOOGLE_SHEET_ID` | ID of the Google Sheet used for run logging |

Secrets are managed at: GitHub repo → Settings → Secrets and variables → Actions

---

### 3. `sellpy_bot.py` — Main Bot Script

**Language:** Python 3.12
**Dependencies:** `playwright`, `python-dotenv`

**What it does in sequence:**
1. Loads credentials from environment variables
2. Launches headless Chromium via Playwright
3. Navigates to `sellpy.se/login`, dismisses cookie banner
4. Enters email → waits for password field → enters password → submits
5. Confirms login succeeded (checks URL left `/login`)
6. Navigates to homepage, collects up to 20 product links
7. Iterates through products until one with an active "Lägg i varukorg" (Add to cart) button is found
8. Clicks Add to cart
9. Navigates to `/checkout/cart`, verifies the item is present by matching `img[src*='<item_id>']`
10. Waits 2 minutes
11. Removes the exact item using its image selector to walk up to the item row and click the close button
12. Counts remaining cart items
13. Calls `sheets_log.log_run()` with result data
14. Closes the browser

On any failure, logs the error and calls `sheets_log.log_run()` with status `"failure"`.

---

### 4. `sheets_log.py` — Google Sheets Logger

**Dependencies:** `gspread`

**What it does:** Appends one row to the first sheet of the configured Google Sheet after every run.

**Columns logged:**
| Column | Description |
|---|---|
| `timestamp_stockholm` | Run time in Europe/Stockholm timezone |
| `status` | `"success"` or `"failure"` |
| `item_id_added` | ID of the product added to cart |
| `item_id_removed` | ID of the product successfully removed |
| `duration_seconds` | Total run duration in seconds |
| `cart_items` | Number of items remaining in cart after removal |
| `error` | Error message if the run failed |

If the sheet is empty, a header row is written automatically on the first run.
If `GOOGLE_CREDENTIALS_JSON` or `GOOGLE_SHEET_ID` are missing, logging is silently skipped — the bot never crashes because of this.

**Authentication:** Uses a Google Service Account via `gspread.service_account_from_dict()`. The full service account JSON is passed via the `GOOGLE_CREDENTIALS_JSON` environment variable.

---

### 5. Google Apps Script — Alert System

**Location:** Configured directly inside the Google Sheet (Extensions → Apps Script)
**Trigger:** Time-driven, every 30 minutes

**What it does:**
1. Reads the last row of the log sheet
2. If status is `"success"` — does nothing
3. If status is not `"success"` — checks if an alert was already sent for this timestamp (stored in Script Properties to avoid duplicate emails)
4. If not already alerted — sends an email with run details and a link to GitHub Actions

**Alert email recipient:** Configured in a separate **Config** sheet, cell `B1`. Update that cell to change the recipient without touching the script code.

**Email content includes:** timestamp, status, item ID, duration, cart items, error message, and a direct link to the GitHub Actions run log.

---

## Repository

**GitHub:** `https://github.com/tuabigfield-tech/sellpy-agent`
**Visibility:** Public (required for unlimited GitHub Actions minutes on the free tier)
**Branch:** `main`

**Files:**
| File | Purpose |
|---|---|
| `sellpy_bot.py` | Main bot logic |
| `sheets_log.py` | Google Sheets logging |
| `requirements.txt` | Python dependencies |
| `.github/workflows/sellpy_bot.yml` | GitHub Actions workflow |
| `.gitignore` | Excludes `.env`, screenshots, cache, debug files |
| `.env` | Local credentials (gitignored, never committed) |

---

## Credentials & Secrets Summary

| Credential | Where stored | Used by |
|---|---|---|
| Sellpy email & password | GitHub Secrets | `sellpy_bot.py` via env vars |
| Google Service Account JSON | GitHub Secrets | `sheets_log.py` via env vars |
| Google Sheet ID | GitHub Secrets | `sheets_log.py` via env vars |
| GitHub PAT (Actions write) | Google Cloud Scheduler job config | Cloud Scheduler → GitHub API |
| Alert email address | Google Sheet → Config tab → B1 | Google Apps Script |

---

## Failure Handling

| Failure point | Behaviour |
|---|---|
| Login fails | Logs error, exits, row written to sheet with `"failure"` |
| No product with add-to-cart found | Logs error, exits, row written with `"failure"` |
| Cart verification times out | Logs warning, continues (lazy load tolerance) |
| Item removal fails | Saves `debug_cart.png` screenshot, logs warning |
| Sheets logging fails | Non-fatal warning, bot result is unaffected |
| Workflow hangs | GitHub Actions kills the job at 12 minutes |
| Cloud Scheduler job fails | Visible in Google Cloud Console; next trigger fires in 20 min |

---

## Runbook

### Check if the bot is running
Go to: `https://github.com/tuabigfield-tech/sellpy-agent/actions`

### Manually trigger a run
GitHub Actions tab → "Sellpy Cart Bot" → Run workflow → Branch: main

### Check run logs
Google Sheet → sheet1 — most recent row is the latest run

### Change the alert email recipient
Google Sheet → Config tab → cell B1

### Update credentials
GitHub repo → Settings → Secrets and variables → Actions → update the relevant secret

### Change the run frequency
Google Cloud Console → Cloud Scheduler → `sellpy-bot-trigger` → Edit → update the cron expression
