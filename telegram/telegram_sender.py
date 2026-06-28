"""
telegram_sender.py
---------------------
Sends text reports to a Telegram chat via the Bot API. Disabled by
default (config/settings.json -> telegram.enabled = false). Fails
silently-but-loudly (logs the error) rather than crashing the whole
pipeline if Telegram is unreachable or misconfigured.

Setup:
  1. Create a bot via @BotFather on Telegram, get the bot token.
  2. Message your bot once, then visit
     https://api.telegram.org/bot<TOKEN>/getUpdates to find your chat_id.
  3. Put both values into config/settings.json under "telegram".
  4. Set "enabled": true.
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger("rsi_divergence")

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LEN = 4000  # Telegram hard limit is 4096; leave margin


def send_message(text: str, bot_token: str, chat_id: str, enabled: bool = True) -> bool:
    """
    Send `text` to the configured Telegram chat. Returns True on success,
    False otherwise (never raises -- this should never crash the main
    pipeline).
    """
    if not enabled:
        logger.info("Telegram notifications disabled in settings.json -- skipping send.")
        return False

    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        logger.warning("Telegram bot_token not configured -- skipping send.")
        return False
    if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
        logger.warning("Telegram chat_id not configured -- skipping send.")
        return False

    url = TELEGRAM_API_URL.format(token=bot_token)
    chunks = [text[i:i + MAX_MESSAGE_LEN] for i in range(0, len(text), MAX_MESSAGE_LEN)] or [""]

    success = True
    for chunk in chunks:
        try:
            resp = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=15)
            if resp.status_code != 200:
                logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
                success = False
        except requests.RequestException as e:
            logger.error(f"Telegram send failed: {e}")
            success = False

    if success:
        logger.info("Telegram report sent successfully.")
    return success


def send_report(report_text: str, telegram_config: dict) -> bool:
    """Convenience wrapper that reads bot_token/chat_id/enabled from a config dict."""
    return send_message(
        text=report_text,
        bot_token=telegram_config.get("bot_token", ""),
        chat_id=telegram_config.get("chat_id", ""),
        enabled=telegram_config.get("enabled", False),
    )
