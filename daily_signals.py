"""
Signal-Skript für Daytrading.
Prüft die Watchlist anhand von 15-Minuten-Kerzen auf aktuelle Kauf-/
Verkaufssignale und schickt eine Zusammenfassung per Telegram.

Läuft automatisch über GitHub Actions zweimal täglich, 8:00 und 15:30 Uhr
deutscher Zeit (siehe .github/workflows/daily.yml), oder manuell mit:
python daily_signals.py

Da geplante GitHub-Actions-Läufe oft verspätet starten, wird nicht streng
auf ein Zeitfenster geprüft, sondern in state/last_sent.json gemerkt, für
welche Zielzeit heute schon gesendet wurde (siehe get_due_slot()).

Benötigt zwei Umgebungsvariablen (als GitHub Secrets hinterlegen, s. Anleitung):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import os
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# Uhrzeiten (deutsche Zeit), zu denen tatsächlich gesendet werden soll.
# GitHub Actions läuft in UTC und kennt keine Sommer-/Winterzeit. Der
# Workflow (daily.yml) startet daher etwas öfter (rund um beide möglichen
# UTC-Offsets). Zusätzlich starten geplante GitHub-Actions-Läufe oft mit
# spürbarer Verspätung (teils über eine Stunde). Statt eines starren
# Zeitfensters merkt sich dieses Skript deshalb in einer kleinen
# Statusdatei (state/last_sent.json), für welche Zielzeit heute schon
# gesendet wurde. Der erste Lauf NACH einer Zielzeit sendet dann,
# unabhängig davon, wie stark er verspätet ist; alle weiteren Läufe für
# dieselbe Zielzeit am selben Tag werden übersprungen.
TARGET_TIMES_BERLIN = [(8, 0), (15, 30)]
STATE_FILE = Path(__file__).parent / "state" / "last_sent.json"


def _slot_label(h, m):
    return f"{h:02d}:{m:02d}"


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_state(today_str, sent_slots):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Es wird nur der heutige Tag gespeichert, damit die Datei klein bleibt.
    STATE_FILE.write_text(json.dumps({today_str: sent_slots}))


def get_due_slot():
    """
    Gibt die Zielzeit (z. B. "08:00") zurück, für die heute noch gesendet
    werden muss, oder None, wenn gerade nichts fällig ist. Ist mehr als
    eine Zielzeit bereits verstrichen und ungesendet (z. B. nach einer
    Pause), wird nur die zeitlich jüngste davon zurückgegeben.
    """
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    today_str = now.date().isoformat()
    state = _load_state()
    sent_today = state.get(today_str, [])
    now_minutes = now.hour * 60 + now.minute

    due = None
    for h, m in sorted(TARGET_TIMES_BERLIN):
        label = _slot_label(h, m)
        target_minutes = h * 60 + m
        if now_minutes >= target_minutes and label not in sent_today:
            due = label
    return due, today_str, sent_today


def mark_slot_sent(today_str, sent_today, slot_label):
    sent_today = sent_today + [slot_label]
    _save_state(today_str, sent_today)

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
    score = 0  # positive Zahl = mehrere Indikatoren zeigen "Kaufen", negativ = "Verkaufen"

    if last_rsi < 30:
        signals.append("RSI überverkauft (Kauf)")
        score += 1
    elif last_rsi > 70:
        signals.append("RSI überkauft (Verkauf)")
        score -= 1

    if macd_cross_up:
        signals.append("MACD Bullish Crossover (Kauf)")
        score += 1
    elif macd_cross_down:
        signals.append("MACD Bearish Crossover (Verkauf)")
        score -= 1

    if last_close < last_lower:
        signals.append("Kurs unter unterem Bollinger Band (Kauf)")
        score += 1
    elif last_close > last_upper:
        signals.append("Kurs über oberem Bollinger Band (Verkauf)")
        score -= 1

    is_strong = abs(score) >= 2  # mind. 2 von 3 Indikatoren stimmen überein

    return {
        "name": name,
        "close": round(last_close, 2),
        "rsi": round(last_rsi, 1),
        "signals": signals,
        "is_strong": is_strong,
    }


def build_message(results):
    lines = ["📊 *Daytrading Markt-Update (15-Min-Basis)*\n"]

    strong = [r for r in results if r and r["signals"] and r["is_strong"]]
    weak = [r for r in results if r and r["signals"] and not r["is_strong"]]

    if strong:
        lines.append("🔥 *Starke Signale (2+ Indikatoren stimmen überein):*")
        for r in strong:
            lines.append(f"*{r['name']}* — Kurs: {r['close']} | RSI: {r['rsi']}")
            for s in r["signals"]:
                lines.append(f"  ⚡ {s}")
            lines.append("")

    if weak:
        lines.append("_Schwächere Einzelsignale:_")
        for r in weak:
            lines.append(f"{r['name']} — Kurs: {r['close']} | RSI: {r['rsi']}")
            for s in r["signals"]:
                lines.append(f"  · {s}")
            lines.append("")

    if not strong and not weak:
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
    due_slot, today_str, sent_today = get_due_slot()

    if not force_send and due_slot is None:
        print("Für heute wurde bereits für alle fälligen Zielzeiten gesendet, "
              "oder die erste Zielzeit (8:00 Uhr) steht noch aus — kein Versand.")
        print("(Für einen manuellen Test unabhängig von Uhrzeit/Status: FORCE_SEND=true setzen)")
        return

    if force_send:
        print("FORCE_SEND aktiv — sende unabhängig von Uhrzeit und Sende-Status.")
    else:
        print(f"Zielzeit {due_slot} Uhr ist fällig und wurde heute noch nicht gesendet — sende jetzt.")

    results = []
    for name, ticker in WATCHLIST.items():
        try:
            results.append(analyze(name, ticker))
        except Exception as e:
            print(f"Fehler bei {name} ({ticker}): {e}")

    message = build_message(results)
    print(message)
    send_telegram(message)

    # Sende-Status nur bei echten (nicht erzwungenen) Läufen aktualisieren,
    # damit Testläufe die nächste reguläre Sendung nicht blockieren.
    if not force_send:
        mark_slot_sent(today_str, sent_today, due_slot)


if __name__ == "__main__":
    main()
