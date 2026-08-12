# Daytrading Signal Bot

Prüft zweimal täglich (8:00 und 15:30 Uhr deutsche Zeit) automatisch Gold, Öl,
Bitcoin, Ethereum, Tesla, Nvidia und den S&P 500 auf Basis von 15-Minuten-Kerzen
auf RSI-, MACD- und Bollinger-Band-Signale und schickt dir eine Zusammenfassung
per Telegram.

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
2. Workflow "Daytrading Market Signals" auswählen
3. "Run workflow" klicken (der Haken bei "force_send" ist standardmäßig gesetzt,
   damit auch außerhalb der Zielzeiten sofort eine Test-Nachricht kommt)
4. Nach ca. 1 Minute solltest du eine Telegram-Nachricht bekommen

Danach läuft es automatisch jeden Tag um 8:00 und 15:30 Uhr deutscher Zeit
(Sommer- wie Winterzeit werden automatisch berücksichtigt).

## 6. Backtest ausführen (um Strategien zu vergleichen)

**Über GitHub (empfohlen, kein eigener Rechner nötig):**
1. Im Repository auf "Actions" gehen
2. Workflow "Run Backtest" auswählen
3. "Run workflow" klicken
4. Nach ein paar Minuten kommt eine Telegram-Nachricht mit den Top-Kombinationen
5. Die komplette Ergebnistabelle (alle Instrumente/Strategien) kannst du zusätzlich
   als CSV-Datei herunterladen: auf der Workflow-Run-Seite ganz unten bei
   "Artifacts" → "backtest-results"

**Lokal (alternativ):**
```bash
pip install -r requirements.txt
python backtest.py
```

Das zeigt dir, welche Strategie (RSI/MACD/Bollinger/Kombi) auf welchem Instrument in den
letzten 60 Tagen (15-Minuten-Kerzen, 1 Stunde Haltedauer pro simuliertem Trade)
die beste durchschnittliche **Netto**-Rendite pro Trade gehabt hätte — geschätzte
Handelskosten (Standard: 0,10% pro Trade, Round-Trip) sind bereits abgezogen. Diesen
Wert kannst du in `backtest.py` bei `TRANSACTION_COST_PCT` an deinen echten Broker anpassen.

Die Strategie "Kombi (2 von 3)" handelt nur, wenn mindestens zwei der drei Indikatoren
gleichzeitig übereinstimmen — seltenere, aber potenziell verlässlichere Signale.
Das tägliche Signal-Skript markiert solche Übereinstimmungen ebenfalls als "🔥 Starkes Signal".

---

## Wichtiger Hinweis

Dies ist ein rein technisches Analyse-Tool, kein Finanzrat. Vergangene Performance
ist keine Garantie für zukünftige Ergebnisse. Nutze es als zusätzlichen Input für
deine eigenen Entscheidungen, nicht als alleinige Grundlage.
