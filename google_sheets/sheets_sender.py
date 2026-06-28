"""
sheets_sender.py
-------------------
Pushes trade journal rows and daily report summaries to a Google Sheet,
via a Google Apps Script Web App endpoint (see
google_sheets/AppsScript_Code.gs for the script to paste into Google
Sheets -> Extensions -> Apps Script).

This approach needs NO Google Cloud project, NO service account JSON
key, and NO OAuth consent flow -- just a deployed Apps Script Web App
URL. The script is responsible for appending rows to the spreadsheet.

Disabled by default (config/settings.json -> google_sheets.enabled =
false). Fails silently-but-loudly (logs the error) rather than
crashing the pipeline if the webapp is unreachable or misconfigured.
"""

import logging
from typing import List

import requests

logger = logging.getLogger("rsi_divergence")

TIMEOUT_SECONDS = 20


def _post(webapp_url: str, payload: dict) -> bool:
    try:
        resp = requests.post(webapp_url, json=payload, timeout=TIMEOUT_SECONDS)
        if resp.status_code != 200:
            logger.error(f"Google Sheets webapp returned HTTP {resp.status_code}: {resp.text[:300]}")
            return False
        try:
            body = resp.json()
        except ValueError:
            logger.error(f"Google Sheets webapp returned non-JSON response: {resp.text[:300]}")
            return False
        if body.get("status") != "ok":
            logger.error(f"Google Sheets webapp reported an error: {body}")
            return False
        return True
    except requests.RequestException as e:
        logger.error(f"Google Sheets send failed: {e}")
        return False


def send_trades(trades: List[dict], sheets_config: dict) -> bool:
    """POST closed trades to the 'Trades' tab of the configured Google Sheet."""
    if not sheets_config.get("enabled", False):
        logger.info("Google Sheets sync disabled in settings.json -- skipping trades push.")
        return False
    webapp_url = sheets_config.get("webapp_url", "")
    if not webapp_url or webapp_url == "YOUR_WEBAPP_URL_HERE":
        logger.warning("Google Sheets webapp_url not configured -- skipping trades push.")
        return False
    if not trades:
        return True

    payload = {
        "secret": sheets_config.get("shared_secret", ""),
        "type": "trades",
        "trades": trades,
    }
    ok = _post(webapp_url, payload)
    if ok:
        logger.info(f"Pushed {len(trades)} trade(s) to Google Sheets.")
    return ok


def send_report(report_dict: dict, sheets_config: dict) -> bool:
    """POST a daily report summary row to the 'DailyReports' tab of the configured Google Sheet."""
    if not sheets_config.get("enabled", False):
        logger.info("Google Sheets sync disabled in settings.json -- skipping report push.")
        return False
    webapp_url = sheets_config.get("webapp_url", "")
    if not webapp_url or webapp_url == "YOUR_WEBAPP_URL_HERE":
        logger.warning("Google Sheets webapp_url not configured -- skipping report push.")
        return False

    payload = {
        "secret": sheets_config.get("shared_secret", ""),
        "type": "report",
        "report": report_dict,
    }
    ok = _post(webapp_url, payload)
    if ok:
        logger.info("Pushed daily report summary to Google Sheets.")
    return ok
