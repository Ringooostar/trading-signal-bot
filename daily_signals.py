"""
Signal-Skript für Daytrading.
Prüft die Watchlist anhand von 15-Minuten-Kerzen auf aktuelle Kauf-/
Verkaufssignale und schickt eine Zusammenfassung per Telegram.

Läuft automatisch über GitHub Actions zweimal täglich, 8:00 und 15:30 Uhr
deutscher Zeit (siehe .github/workflows/daily.yml), oder manuell mit:
python daily_signals.py

Benötigt zwei Umgebungsvariablen (als GitHub Secrets hinterlegen, s. Anleitung):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# Uhrzeiten (deutsche Zeit), zu denen tatsächlich gesendet werden soll.
# GitHub Actions läuft in UTC und kennt keine Sommer-/Winterzeit. Der
# Workflow (daily.yml) startet daher etwas öfter (rund um beide möglichen
# UTC-Offsets), und dieser Check lässt nur die Läufe durch, die zeitlich
# nah genug an 8:00 bzw. 15:30 deutscher Zeit liegen.
TARGET_TIMES_BERLIN = [(8, 0), (15, 30)]
TOLERANCE_MINUTES = 20


def is_target_time():
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    now_minutes = now.hour * 60 + now.minute
    for h, m in TARGET_TIMES_BERLIN:
        target_minutes = h * 60 + m
        if abs(now_minutes - target_minutes) <= TOLERANCE_MINUTES:
            return True
    return False

WATCHLIST = {
    "Gold": "GC=F",
    "Oel WTI": "CL=F",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "Tesla": "TSLA",
    "Nvidia": "NVDA",
    "SP500": "^GSPC",
}


def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def compute_bollinger(series, period=20, num_std=2):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    return sma + num_std * std, sma - num_std * std


def analyze(name, ticker):
    # yfinance erlaubt 15m-Daten nur für die letzten ca. 60 Tage
    df = yf.download(ticker, period="5d", interval="15m", progress=False)
    if df.empty or len(df) < 30:
        return None

    # Absicherung gegen neuere yfinance-Versionen, die manchmal
    # mehrdimensionale Spalten zurückgeben (MultiIndex).
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df["Close"]
    last_close = float(close.iloc[-1])

    rsi = compute_rsi(close)
    last_rsi = float(rsi.iloc[-1])

    macd_line, signal_line = compute_macd(close)
    macd_cross_up = bool(macd_line.iloc[-1] > signal_line.iloc[-1] and
                          macd_line.iloc[-2] <= signal_line.iloc[-2])
    macd_cross_down = bool(macd_line.iloc[-1] < signal_line.iloc[-1] and
                            macd_line.iloc[-2] >= signal_line.iloc[-2])

    upper, lower = compute_bollinger(close)
    last_upper = float(upper.iloc[-1])
    last_lower = float(lower.iloc[-1])

    signals = []
    if last_rsi < 30:
        signals.append("RSI überverkauft (mögliches Kaufsignal)")
    elif last_rsi > 70:
        signals.append("RSI überkauft (mögliches Verkaufsignal)")

    if macd_cross_up:
        signals.append("MACD Bullish Crossover (mögliches Kaufsignal)")
    elif macd_cross_down:
        signals.append("MACD Bearish Crossover (mögliches Verkaufsignal)")

    if last_close < last_lower:
        signals.append("Kurs unter unterem Bollinger Band (mögliches Kaufsignal)")
    elif last_close > last_upper:
        signals.append("Kurs über oberem Bollinger Band (mögliches Verkaufsignal)")

    return {
        "name": name,
        "close": round(last_close, 2),
        "rsi": round(last_rsi, 1),
        "signals": signals,
    }


def build_message(results):
    lines = ["📊 *Daytrading Markt-Update (15-Min-Basis)*\n"]
    any_signal = False

    for r in results:
        if r is None:
            continue
        if r["signals"]:
            any_signal = True
            lines.append(f"*{r['name']}* — Kurs: {r['close']} | RSI: {r['rsi']}")
            for s in r["signals"]:
                lines.append(f"  ⚡ {s}")
            lines.append("")

    if not any_signal:
        lines.append("Keine auffälligen Signale heute. Alle Werte im neutralen Bereich.")

    lines.append("\n_Kein Finanzrat. Nur automatisierte technische Analyse._")
    return "\n".join(lines)


def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt. Nachricht nicht gesendet.")
        print(message)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    })
    if resp.status_code != 200:
        print(f"Fehler beim Senden (Markdown): {resp.text}")
        print("Versuche erneut ohne Formatierung ...")
        resp2 = requests.post(url, data={
            "chat_id": chat_id,
            "text": message,
        })
        if resp2.status_code != 200:
            print(f"Fehler beim Senden (Klartext): {resp2.text}")
        else:
            print("Nachricht (als Klartext) erfolgreich an Telegram gesendet.")
    else:
        print("Nachricht erfolgreich an Telegram gesendet.")


def main():
    force_send = os.environ.get("FORCE_SEND") == "true"
    if not force_send and not is_target_time():
        print("Außerhalb der Zielzeiten (8:00 / 15:30 Uhr deutsche Zeit) — kein Versand.")
        print("(Für einen manuellen Test unabhängig von der Uhrzeit: FORCE_SEND=true setzen)")
        return

    results = []
    for name, ticker in WATCHLIST.items():
        try:
            results.append(analyze(name, ticker))
        except Exception as e:
            print(f"Fehler bei {name} ({ticker}): {e}")

    message = build_message(results)
    print(message)
    send_telegram(message)


if __name__ == "__main__":
    main()
