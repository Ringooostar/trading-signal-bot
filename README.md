# Daily Market Signal Bot

Prüft täglich automatisch Gold, Öl, Bitcoin, Ethereum, Tesla, Nvidia und den S&P 500
auf RSI-, MACD- und Bollinger-Band-Signale und schickt dir eine Zusammenfassung per Telegram.

**Wichtig:** Dieser Bot handelt NICHT automatisch. Er liefert nur Informationen/Signale.
Die Kauf-/Verkaufsentscheidung triffst du selbst.

---

## 1. Repository auf GitHub erstellen

1. Auf github.com einloggen
2. Oben rechts auf "+" → "New repository"
3. Name z. B. `trading-signal-bot`
4. "Create repository" klicken

## 2. Dateien hochladen

Auf der neuen Repo-Seite: "uploading an existing file" klicken und alle Dateien aus
diesem Ordner hochladen (inkl. des `.github/workflows/daily.yml` — Ordnerstruktur bleibt
erhalten, wenn du den ganzen Ordner ziehst).

## 3. Telegram-Bot erstellen (2 Minuten)

1. In Telegram nach **@BotFather** suchen und Chat öffnen
2. `/newbot` senden, Namen vergeben
3. Du bekommst einen **Bot-Token** (sieht aus wie `123456:ABC-DEF...`) — kopieren
4. Deinem neuen Bot eine Nachricht schicken (z. B. "Hallo"), damit er deine Chat-ID sehen kann
5. Im Browser aufrufen: `https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates`
6. Darin die `"chat":{"id": ...}` Zahl kopieren — das ist deine **Chat-ID**

## 4. Secrets in GitHub hinterlegen

1. Im Repository: Settings → Secrets and variables → Actions
2. "New repository secret":
   - Name: `TELEGRAM_BOT_TOKEN`, Wert: dein Bot-Token
   - Name: `TELEGRAM_CHAT_ID`, Wert: deine Chat-ID

## 5. Testen

1. Im Repository auf "Actions" gehen
2. Workflow "Daily Market Signals" auswählen
3. "Run workflow" klicken (manueller Test)
4. Nach ca. 1 Minute solltest du eine Telegram-Nachricht bekommen

Danach läuft es automatisch jeden Tag um 7:00 Uhr UTC (9:00 Uhr deutsche Sommerzeit).

## 6. Backtest lokal ausführen (optional, um Strategien zu vergleichen)

```bash
pip install -r requirements.txt
python backtest.py
```

Das zeigt dir, welche Strategie (RSI/MACD/Bollinger) auf welchem Instrument in den
letzten 12 Monaten die beste durchschnittliche Rendite pro Trade gehabt hätte.

---

## Wichtiger Hinweis

Dies ist ein rein technisches Analyse-Tool, kein Finanzrat. Vergangene Performance
ist keine Garantie für zukünftige Ergebnisse. Nutze es als zusätzlichen Input für
deine eigenen Entscheidungen, nicht als alleinige Grundlage.
