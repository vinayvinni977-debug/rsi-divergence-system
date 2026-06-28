/*
 * AppsScript_Code.gs
 * --------------------
 * Paste this entire file into Extensions -> Apps Script on the Google
 * Sheet you want to use as your trade journal mirror, then deploy it
 * as a Web App (see README.md, "Google Sheets Integration" section).
 *
 * It receives JSON POST requests from sheets_sender.py and appends
 * rows to two tabs:
 *   - "Trades"        : one row per closed trade
 *   - "DailyReports"  : one row per daily run summary
 *
 * SHARED_SECRET below must match "shared_secret" in config/settings.json
 * under the "google_sheets" block -- this stops random people from
 * spamming your sheet if the webapp URL ever leaks.
 */

var SHARED_SECRET = "CHANGE_ME_TO_A_RANDOM_STRING";

var TRADE_HEADERS = [
  "symbol", "timeframe", "date", "direction", "entry", "stop_loss",
  "take_profit", "result", "profit", "r_multiple", "exit_date",
  "exit_price", "position_size", "run_tag"
];

var REPORT_HEADERS = [
  "date", "run_tag", "markets_tested", "total_trades", "wins", "losses",
  "win_rate_pct", "profit_factor", "total_return_pct", "total_profit",
  "max_drawdown_pct", "expectancy_r", "average_r",
  "max_consecutive_losses", "max_consecutive_wins"
];

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    if (data.secret !== SHARED_SECRET) {
      return jsonOutput({ status: "error", message: "Invalid secret" });
    }

    if (data.type === "trades") {
      appendTrades(data.trades || []);
    } else if (data.type === "report") {
      appendReport(data.report || {});
    } else {
      return jsonOutput({ status: "error", message: "Unknown type: " + data.type });
    }

    return jsonOutput({ status: "ok" });
  } catch (err) {
    return jsonOutput({ status: "error", message: String(err) });
  }
}

function doGet(e) {
  return jsonOutput({ status: "ok", message: "RSI Divergence Sheets endpoint is live" });
}

function getOrCreateSheet(name, headers) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");
  }
  return sheet;
}

function appendTrades(trades) {
  var sheet = getOrCreateSheet("Trades", TRADE_HEADERS);
  trades.forEach(function (t) {
    var row = TRADE_HEADERS.map(function (h) { return t[h] !== undefined ? t[h] : ""; });
    sheet.appendRow(row);
  });
}

function appendReport(report) {
  var sheet = getOrCreateSheet("DailyReports", REPORT_HEADERS);
  var row = REPORT_HEADERS.map(function (h) { return report[h] !== undefined ? report[h] : ""; });
  sheet.appendRow(row);
}

function jsonOutput(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
