import sys
sys.path.insert(0, '.')
from config.config import CONFIG
from google_sheets.sheets_sender import send_trades

trades = [
    {'symbol': 'TEST', 'timeframe': '15m', 'date': '2026-06-29', 'direction': 'bullish',
     'entry': 100.0, 'stop_loss': 95.0, 'take_profit': 120.0, 'result': 'WIN',
     'profit': 500.0, 'r_multiple': 4.0, 'exit_date': '2026-06-29',
     'exit_price': 120.0, 'position_size': 100.0, 'run_tag': 'debug_test'}
]

cfg = CONFIG['google_sheets']
print('URL:', cfg['webapp_url'])
print('Enabled:', cfg['enabled'])
ok = send_trades(trades, cfg)
print('Result:', ok)
