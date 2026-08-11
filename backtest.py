"""
Backtesting-Skript für Daytrading: Vergleicht RSI-, MACD- und
Bollinger-Band-Strategien auf 15-Minuten-Kerzen einer Watchlist aus
Gold, Öl, Krypto und volatilen Aktien.

Läuft NICHT hier im Sandbox (kein Internetzugriff), sondern auf deinem
Rechner oder über GitHub Actions (siehe .github/workflows/backtest.yml).

Ausführen mit: python backtest.py
"""

import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# ------------------------------------------------------------------
# 1. WATCHLIST
# ------------------------------------------------------------------
# Tickerformat wie bei Yahoo Finance
WATCHLIST = {
    "Gold": "GC=F",
    "Oel WTI": "CL=F",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "Tesla": "TSLA",
    "Nvidia": "NVDA",
    "SP500": "^GSPC",
}

# yfinance erlaubt 15-Minuten-Daten nur für die letzten ca. 60 Tage
PERIOD = "60d"
INTERVAL = "15m"
HOLDING_BARS = 4  # 4 x 15 Min. = 1 Stunde Haltedauer pro simuliertem Trade

# Geschätzte Kosten pro Trade (Kauf + Verkauf zusammen), realistisch für
# Krypto-/CFD-Broker mit Spread + Gebühren. Passe das an deinen tatsächlichen
# Broker an, falls du genauere Zahlen hast.
TRANSACTION_COST_PCT = 0.10  # in Prozent, z.B. 0.10 = 0,10% pro Trade (Round-Trip)


# ------------------------------------------------------------------
# 2. INDIKATOREN
# ------------------------------------------------------------------
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def compute_bollinger(series, period=20, num_std=2):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    return upper, lower


# ------------------------------------------------------------------
# 3. STRATEGIEN (geben Kauf/Verkauf-Signale zurück: 1 = Kaufsignal, -1 = Verkaufsignal, 0 = nichts)
# ------------------------------------------------------------------
def strategy_rsi(df):
    df["RSI"] = compute_rsi(df["Close"])
    signal = np.where(df["RSI"] < 30, 1, np.where(df["RSI"] > 70, -1, 0))
    return pd.Series(signal, index=df.index)


def strategy_macd(df):
    macd_line, signal_line = compute_macd(df["Close"])
    cross_up = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    cross_down = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
    signal = np.where(cross_up, 1, np.where(cross_down, -1, 0))
    return pd.Series(signal, index=df.index)


def strategy_bollinger(df):
    upper, lower = compute_bollinger(df["Close"])
    signal = np.where(df["Close"] < lower, 1, np.where(df["Close"] > upper, -1, 0))
    return pd.Series(signal, index=df.index)


def strategy_combined(df):
    """
    Strengere Strategie: Es wird nur gehandelt, wenn mindestens 2 von 3
    Indikatoren (RSI, MACD, Bollinger) gleichzeitig in dieselbe Richtung
    zeigen. Soll seltenere, aber "überzeugendere" Signale liefern.
    """
    rsi_sig = strategy_rsi(df)
    macd_sig = strategy_macd(df)
    boll_sig = strategy_bollinger(df)

    total = rsi_sig + macd_sig + boll_sig
    # +2 oder +3 => mind. 2 Indikatoren sagen "Kaufen"
    signal = np.where(total >= 2, 1, np.where(total <= -2, -1, 0))
    return pd.Series(signal, index=df.index)


STRATEGIES = {
    "RSI": strategy_rsi,
    "MACD": strategy_macd,
    "Bollinger": strategy_bollinger,
    "Kombi (2 von 3)": strategy_combined,
}


# ------------------------------------------------------------------
# 4. EINFACHER BACKTEST (Long-only, keine Hebel, keine Gebühren berücksichtigt)
# ------------------------------------------------------------------
def backtest_signal(df, signal, holding_bars=HOLDING_BARS, cost_pct=TRANSACTION_COST_PCT):
    """
    Simuliert: bei Kaufsignal wird gekauft und nach `holding_bars` Kerzen
    (bei 15-Min.-Kerzen z.B. 4 = 1 Stunde) wieder verkauft.
    Zieht geschätzte Handelskosten (`cost_pct`, Round-Trip) von jedem
    Trade ab. Gibt die durchschnittliche Netto-Rendite pro Trade zurück.
    """
    returns = []
    close = df["Close"]
    buy_indices = np.where(signal == 1)[0]
    cost_fraction = cost_pct / 100

    for idx in buy_indices:
        if idx + holding_bars < len(close):
            entry = close.iloc[idx]
            exit_ = close.iloc[idx + holding_bars]
            ret = (exit_ - entry) / entry - cost_fraction
            returns.append(ret)

    if not returns:
        return {"n_trades": 0, "avg_return": None, "win_rate": None}

    returns = np.array(returns)
    return {
        "n_trades": len(returns),
        "avg_return": round(float(returns.mean()) * 100, 2),   # in %
        "win_rate": round(float((returns > 0).mean()) * 100, 1),  # in %
    }


def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt. Nachricht nicht gesendet.")
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
            print("Backtest-Ergebnisse (als Klartext) erfolgreich an Telegram gesendet.")
    else:
        print("Backtest-Ergebnisse erfolgreich an Telegram gesendet.")


def build_telegram_summary(results_df, top_n=8):
    valid = results_df[results_df["n_trades"] > 0].sort_values(by="avg_return", ascending=False)
    lines = [f"📈 *Backtest-Ergebnisse (letzte {PERIOD}, 15-Min-Kerzen)*\n"]
    lines.append(f"Haltedauer/Trade: {HOLDING_BARS * 15} Min. | "
                 f"Kosten/Trade bereits abgezogen: {TRANSACTION_COST_PCT}%\n")

    if valid.empty:
        lines.append("Keine auswertbaren Trades gefunden.")
    else:
        lines.append("*Top Kombinationen (Ø Rendite pro Trade):*")
        for _, row in valid.head(top_n).iterrows():
            lines.append(
                f"{row['Instrument']} / {row['Strategie']}: "
                f"{row['avg_return']}% | Trades: {row['n_trades']} | "
                f"Trefferquote: {row['win_rate']}%"
            )

    lines.append("\n_Vergangene Performance ist keine Garantie für die Zukunft. Kein Finanzrat._")
    return "\n".join(lines)


# ------------------------------------------------------------------
# 5. HAUPTPROGRAMM
# ------------------------------------------------------------------
def main():
    results = []

    for name, ticker in WATCHLIST.items():
        print(f"Lade Daten für {name} ({ticker}) ...")
        try:
            df = yf.download(ticker, period=PERIOD, interval=INTERVAL, progress=False)
        except Exception as e:
            print(f"  Fehler beim Laden von {ticker}: {e}")
            continue

        if df.empty or len(df) < 50:
            print(f"  Zu wenig Daten für {name}, überspringe.")
            continue

        # Absicherung gegen neuere yfinance-Versionen, die manchmal
        # mehrdimensionale Spalten zurückgeben (MultiIndex).
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        for strat_name, strat_func in STRATEGIES.items():
            signal = strat_func(df)
            stats = backtest_signal(df, signal)
            results.append({
                "Instrument": name,
                "Strategie": strat_name,
                **stats,
            })

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by="avg_return", ascending=False)

    print("\n=== BACKTEST-ERGEBNISSE (sortiert nach Ø Rendite pro Trade) ===\n")
    print(results_df.to_string(index=False))

    results_df.to_csv("backtest_results.csv", index=False)
    print("\nErgebnisse gespeichert in backtest_results.csv")

    summary = build_telegram_summary(results_df)
    send_telegram(summary)


if __name__ == "__main__":
    main()
