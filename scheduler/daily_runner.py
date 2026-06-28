"""
daily_runner.py
------------------
Entry point intended to be invoked once per day by Windows Task
Scheduler (see README.md for the exact `schtasks` command / GUI steps).

It wraps main.run_pipeline() with extra error handling so that any
failure (network issue, data source outage, bad config, etc.) is
logged AND reported to Telegram (if configured) instead of failing
silently overnight.

Run manually with:
    python scheduler/daily_runner.py
"""

import sys
import traceback
from pathlib import Path

# Ensure project root is importable when this script is launched directly
# (e.g. by Task Scheduler with a working directory that isn't the project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.config import CONFIG, setup_logging  # noqa: E402
from main import run_pipeline  # noqa: E402
from telegram.telegram_sender import send_message  # noqa: E402

logger = setup_logging()


def main():
    logger.info("=== Daily automated run starting ===")
    try:
        run_tag = run_pipeline(markets="all", allow_download=True, mode="backtest", skip_telegram=False)
        logger.info(f"=== Daily automated run completed successfully (run_tag={run_tag}) ===")
    except Exception as e:
        error_text = (
            "RSI Divergence System -- DAILY RUN FAILED\n\n"
            f"Error: {e}\n\n"
            f"{traceback.format_exc()[-1500:]}"
        )
        logger.exception("Daily automated run failed.")
        telegram_cfg = CONFIG.get("telegram", {})
        send_message(
            text=error_text,
            bot_token=telegram_cfg.get("bot_token", ""),
            chat_id=telegram_cfg.get("chat_id", ""),
            enabled=telegram_cfg.get("enabled", False),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
