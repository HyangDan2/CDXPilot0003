# Current Status

Updated: 2026-05-08

## Completed

- Created project skeleton under `src/kosim`.
- Added secret-safe `.gitignore`.
- Added `config.example.yaml` with placeholders only.
- Added `requirements.txt`, `pyproject.toml`, `LICENSE`, `README.md`.
- Added D-1 previous Korean trading day resolver.
- Added D-1 KOSPI market-cap top 10 universe resolver interface.
- Added deterministic mock market data provider.
- Added `KisRestClient` from the supplied Korea Investment OpenAPI manual:
  - `/oauth2/tokenP`
  - `/uapi/domestic-stock/v1/ranking/market-cap`
  - `/uapi/domestic-stock/v1/quotations/inquire-overtime-price`
  - `/uapi/domestic-futureoption/v1/quotations/inquire-price`
  - `/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice`
- Added `docs/KIS_MANUAL_NOTES.md` with relevant TR IDs and endpoint notes.
- Added sequential sweep simulator:
  - historical stored-snapshot signal time: 08:50
  - default condition branches: 5/10, 7/10, 10/10 positive
  - exit sweep: 09:00 to 15:20
  - condition threshold uses strict `return_pct > 0`
  - KOSPI200 futures long return calculation with fee/slippage assumptions
  - trade-level evidence with gross return, fee, slippage, net return, positive count, and triggered symbols
- Added expanded metrics:
  - profit probability
  - loss probability
  - p05/p25/p75/p95 return percentiles
  - exit-time summary
- Added SQLite raw data storage.
- Added SQLite raw data reload/list APIs.
- Added normalized SQLite stored-data tables:
  - `nxt_snapshots`
  - `futures_prices`
  - `daily_universe`
- Added no-overwrite snapshot persistence APIs using `insert or ignore`.
- Added complete-data availability scanner:
  - checks universe size
  - checks all configured NXT signal times
  - checks all configured futures signal and exit times
- Added recent complete-data-day simulation mode:
  - uses only already stored complete raw data
  - does not fetch new data
  - does not use calendar-only working-day guesses
- Added raw data markdown report.
- Added simulation markdown report.
- Added chart generation:
  - total return heatmap
  - win-rate heatmap
  - trade-count heatmap
  - loss-probability heatmap
  - selected case return distributions
- Added Telegram sender:
  - raw markdown files are sent as documents
  - simulation markdown files are sent as documents
  - charts are sent as inline photos
  - LLM report text is sent as plain raw text chunks
- Added stateless LLM prompt builder:
  - all instructions are written in English
  - output is explicitly requested in Korean Markdown
  - output is top-down, starting with conclusion
  - Top 5 conditions, strategy proposal, evidence, risks, and AI usage warning are required
  - provided-context-only policy
  - external knowledge and prior memory are prohibited
  - general trading guidance is allowed only in the strategy proposal section
  - context auto-compression guard is configured
  - secrets are redacted before prompt construction
- Added OpenAI-compatible LLM client configured for Nvidia Nemotron 120B style endpoints.
- Added PySide6 GUI:
  - menu bar for config control
  - integrated settings dialog
  - mock/KIS REST mode toggle
  - KIS REST, Telegram, and LLM connection tests
  - recent complete-data-day selection
  - step-by-step progress timeline
  - current status panel
  - run log panel
  - result table
  - markdown report viewer
- Added tests for calendar, signal condition, availability, metrics, multi-condition branching, sweep time generation, and pipeline execution.

## Verification Performed

- `python -m pytest`
  - Result: 12 passed
- `PYTHONPATH=src python -m kosim.app --example`
  - Result: mock pipeline completed successfully
  - Generated ignored runtime artifacts in `data/` and `reports/`
- Secret safety check:
  - local `config.yaml` exists and appears to contain private runtime values
  - `config.yaml` is explicitly ignored by `.gitignore`
  - local KIS token cache exists under `data/` and is ignored by `.gitignore`
  - no `.env`, key, or pem file was found
  - generated runtime artifacts are covered by `.gitignore`

## Not Implemented Yet

- Production KIS NXT websocket parser for true NXT live ticks.
  - Live updating/collector code was removed because it was unstable.
- Live-account verification of KIS response field parsing.
- Historical D-1 KOSPI market-cap archive for old simulation dates.
- Production Korean exchange holiday calendar.
- Live order placement.
- Advanced visualization such as heatmap and equity curve chart.
  - Heatmaps are implemented; equity curve chart remains future work.

## Known Breakdown Risks

- KIS REST mode may fail until KIS response parsing is tested against real API responses.
- Historical NXT snapshots are not available from the REST sheets inspected so far; import external snapshots or use stored raw data.
- The current Korean trading calendar only skips weekends unless `data.holidays` is configured.
- Mock data is deterministic but not market-realistic.
- Recent complete-data-day mode returns no dates until raw data has first been collected or imported.
- Stored snapshot mode returns no dates until `nxt_snapshots`, `daily_universe`, and `futures_prices` are populated.
- Chart generation depends on matplotlib; if chart generation fails, reports still remain usable.
- Telegram photo sending can hit API/network errors independently from markdown document sending.
- LLM text is sent as plain chunks, so very long responses can arrive as multiple messages.
- Telegram requires valid `bot_token` and `chat_id`; placeholders are rejected when enabled.
- LLM requires an OpenAI-compatible endpoint at `/chat/completions`.
- Telegram Markdown may reject malformed markdown or long messages; file sending is the preferred path.
- Strategy results can be misleading when trade count is low.
- Fee, slippage, tick value, and execution timing are simplified assumptions.
- `config.yaml` must remain local and untracked because it will contain API keys.

## Next Best Step

Stabilize the one-shot simulation path: add clearer complete-data diagnostics,
then add KOSPI200 front-month contract cache/fallback for KIS REST mode.
