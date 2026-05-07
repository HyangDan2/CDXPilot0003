# KOSPI NXT Sweep Simulator

PySide6 GUI and CLI simulator for testing KOSPI200 futures long entries based on
NXT pre-market returns of the previous-trading-day KOSPI market-cap top 10.

## What It Does

- Resolves the simulation date `D`.
- Resolves `D-1`, the previous Korean trading day.
- Selects the KOSPI market-cap top 10 from `D-1`.
- Fetches NXT stock return snapshots for `D`.
- Fetches KOSPI200 futures prices for `D`.
- Sends raw data to Telegram before LLM analysis when enabled.
- Runs sequential sweep simulations across signal and exit times.
- Generates markdown reports.
- Generates a compact raw report plus an LLM bridge evidence report.
- Generates return distribution and signal/exit heatmap charts.
- Builds a stateless, provided-context-only LLM prompt.
- Calls an OpenAI-compatible Nvidia Nemotron 120B endpoint when enabled.
- Sends raw/simulation markdown files to Telegram as documents.
- Sends chart images to Telegram as photos.
- Sends the LLM report to Telegram as plain raw text chunks.
- Visualizes step-by-step progress in the PySide6 GUI.
- Lets you edit key config values from the GUI menu bar.
- Supports recent complete-data-day simulations from stored SQLite raw data.
- Historical stored-snapshot simulation uses the 08:50 NXT snapshot by default.
- Runs default positive-count branches: 5/10, 7/10, and 10/10 positive.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp config.example.yaml config.yaml
```

Fill `config.yaml` with private values only on your machine.

`config.yaml` is intentionally ignored by git.

## Run CLI With Mock Data

```bash
python -m kosim.app --example
```

## Run GUI

```bash
python -m kosim.app --gui
```

If `config.yaml` does not exist, the GUI falls back to `config.example.yaml` in
mock mode.

## GUI Menu Features

- `File`: open, save, save-as, and reload config.
- `File > Settings`: integrated settings dialog for General, KIS, Telegram, LLM, Market, Simulation, and Data.
- `Mode`: toggle Mock Mode or KIS REST Mode.
- `Integrations`: test KIS REST, Telegram, and LLM connectivity.
- `Simulation`: select date range mode or recent complete-data-day mode.
- `Help`: view current status, risk review, and KIS manual notes.

`Save Config` writes to `config.yaml` by default. The GUI blocks overwriting
`config.example.yaml`.

## Recent Complete Data Days

Recent-day simulation does not guess by calendar or working-day rules. It scans
the SQLite raw data store and selects only dates with complete data:

- D-1 universe exists and has at least Top N members.
- Every configured NXT signal time has all required universe symbols.
- Every configured futures signal/exit time has a stored price.

If fewer complete days exist than requested, the pipeline warns and uses only
the complete days that are available.

## Stored Snapshot Simulation

Use `simulation.date_selection.mode: "stored_snapshots"` only when normalized
SQLite snapshots have been imported or written by a separate external process.
The application does not run an in-app NXT collector; stored snapshots must come
from import files or a separate capture process.

Defaults:

- signal time: `08:50`
- conditions: `top10_5_positive`, `top10_7_positive`, `top10_10_positive`
- exits: `09:00` through `15:20`

## Telegram Delivery

- Raw data markdown is sent as a document.
- Simulation result markdown is sent as a document.
- LLM bridge evidence is generated for prompt input and is not sent to Telegram unless `telegram.delivery.send_llm_bridge_file` is enabled.
- Charts are sent as Telegram photos so they render inline.
- LLM output is sent as plain text chunks without Telegram markdown parsing.

## Report Files

Each run writes these markdown artifacts:

- `raw_data_*.md`: compact human review report with NXT signal summary, key futures prices, and each date's best entry-exit cases.
- `llm_bridge_*.md`: compact evidence bridge used by the LLM prompt. It selects date-by-date best cases and aggregate evidence instead of passing a full raw ledger.
- `simulation_report_*.md`: sweep metrics, exit summaries, and trade evidence.

The full `09:00~15:20` 10-minute exit sweep is still simulated. The raw report intentionally shows only selected daily best cases so it stays readable; the bridge markdown gives the LLM enough evidence without forcing a huge raw ledger into the prompt.

Daily best-case rows include `Signal Date`. By default, the raw report and LLM
bridge keep only one best case per signal date to avoid double-counting the same
day across overlapping conditions.

## Real Data Rules

- `mock` mode is for development and UI testing only.
- `kis_rest` mode never falls back to mock data.
- KIS REST mode rejects multi-time NXT signal replication because the inspected REST endpoint does not provide historical `08:00~08:50` NXT snapshots.
- KIS futures minute rows are selected by the nearest row at or before the requested time.
- Current futures price fallback is disabled for historical simulation. Missing minute data should make the affected date/time incomplete instead of silently mixing in current prices.

## LLM Prompt Policy

- LLM calls are stateless.
- Instructions are written in English.
- Output is Korean Markdown.
- Simulation interpretation must use only provided context.
- LLM prompt input uses `llm_bridge_*.md` style evidence, not the full raw report.
- General trading/risk-management guidance is allowed only in the strategy proposal section and must be labeled as general guidance.
- The output starts with a conclusion first, then Top 5 conditions, strategy proposal, evidence, risks, and AI usage warning.

## Secret Safety

The following are excluded from git:

- `config.yaml`
- `.env`
- API keys and key files
- SQLite databases
- token caches
- generated raw data
- logs
- generated reports

Do not put real API keys into `config.example.yaml`.

## Current Implementation Status

Implemented:

- Secret-safe config example
- Mock deterministic market data provider
- Korea Investment REST client for token issuance, market-cap ranking, overtime price, futures price, and futures minute chart endpoints identified from the supplied manual
- KIS REST futures minute selection uses the nearest row at or before the requested time and disables current-price fallback for historical simulation
- D-1 previous trading day universe resolver
- Sequential signal-time and exit-time sweep engine
- Markdown raw/simulation reports
- LLM bridge evidence markdown for prompt input
- Telegram sender
- Stateless LLM prompt builder
- OpenAI-compatible LLM client
- PySide6 progress GUI
- GUI menu controls for config, mock/KIS REST mode, recent complete-data selection, and integration tests
- Integrated settings dialog
- SQLite complete-data availability scanner
- Normalized SQLite tables for `nxt_snapshots`, `futures_prices`, and `daily_universe`
- Chart generation for heatmaps and case return distributions
- Basic tests

Not yet implemented:

- Historical NXT snapshot importer or external capture process.
- Fully verified real KIS response parsing against a live account
- Real historical D-1 KOSPI market-cap archive for old simulation dates
- Production-grade Korean holiday calendar
- Order placement

## Important

This is research software, not investment advice. The KIS REST adapter must be
filled and verified from the supplied Korea Investment OpenAPI manual before
using real market data.
