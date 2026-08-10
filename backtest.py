"""
Backtesting-Skript: Vergleicht RSI-, MACD- und Bollinger-Band-Strategien
auf einer Watchlist aus Gold, Öl, Krypto und volatilen Aktien.

Läuft NICHT hier im Sandbox (kein Internetzugriff), sondern auf deinem
Rechner oder über GitHub Actions.

Ausführen mit: python backtest.py
"""

import yfinance as yf
import pandas as pd
import numpy as np

# ------------------------------------------------------------------
# 1. WATCHLIST
# ------------------------------------------------------------------
# Tickerformat wie bei Yahoo Finance
WATCHLIST = {
    "Gold": "GC=F",
    "Oel_WTI": "CL=F",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "Tesla": "TSLA",
    "Nvidia": "NVDA",
    "SP500": "^GSPC",
}

PERIOD = "1y"      # Zeitraum für Backtest
INTERVAL = "1d"    # Tagesdaten (für Daytrading später auf "1h" oder "15m" umstellen)


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


STRATEGIES = {
    "RSI": strategy_rsi,
    "MACD": strategy_macd,
    "Bollinger": strategy_bollinger,
}


# ------------------------------------------------------------------
# 4. EINFACHER BACKTEST (Long-only, keine Hebel, keine Gebühren berücksichtigt)
# ------------------------------------------------------------------
def backtest_signal(df, signal, holding_days=5):
    """
    Simuliert: bei Kaufsignal wird gekauft und nach `holding_days` wieder verkauft.
    Gibt die durchschnittliche Rendite pro Trade zurück.
    """
    returns = []
    close = df["Close"]
    buy_indices = np.where(signal == 1)[0]

    for idx in buy_indices:
        if idx + holding_days < len(close):
            entry = close.iloc[idx]
            exit_ = close.iloc[idx + holding_days]
            ret = (exit_ - entry) / entry
            returns.append(ret)

    if not returns:
        return {"n_trades": 0, "avg_return": None, "win_rate": None}

    returns = np.array(returns)
    return {
        "n_trades": len(returns),
        "avg_return": round(float(returns.mean()) * 100, 2),   # in %
        "win_rate": round(float((returns > 0).mean()) * 100, 1),  # in %
    }


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


if __name__ == "__main__":
    main()
