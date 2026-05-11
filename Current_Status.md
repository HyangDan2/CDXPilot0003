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
  - Mock futures prices now avoid forced one-way intraday upward drift.
- Refactored market data providers into `kosim.data.providers`.
  - `kosim.data.fetcher` remains as a compatibility export layer.
- Added `KisRestClient` from the supplied Korea Investment OpenAPI manual:
  - `/oauth2/tokenP`
  - `/uapi/domestic-stock/v1/ranking/market-cap`
  - `/uapi/domestic-stock/v1/quotations/inquire-overtime-price`
  - `/uapi/domestic-futureoption/v1/quotations/inquire-price`
  - `/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice`
- Hardened KIS REST simulation data rules:
  - multi-time NXT replication is rejected in KIS REST mode
  - futures minute chart rows are selected by nearest time at or before target
  - current futures price fallback is disabled for historical simulation
- Added `docs/KIS_MANUAL_NOTES.md` with relevant TR IDs and endpoint notes.
- Added sequential sweep simulator:
  - historical stored-snapshot signal time: 08:50
  - default condition branches: 5/10, 7/10, 10/10 up-long
  - default inverse branches: 5/10, 7/10, 10/10 down-inverse
  - inverse means KOSPI200 futures short, not an inverse ETF/ETN
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
- Added compact raw data markdown report:
  - NXT signal summary
  - key futures prices
  - each date's best entry-exit cases
  - Signal Date column
  - one best case per date by default
- Added LLM bridge markdown report:
  - compact evidence layer for prompt input
  - aggregate best evidence
  - date-by-date selected best cases
  - Signal Date column
  - one best case per date by default
- Refactored report evidence helpers into a shared module used by raw reports
  and LLM bridge generation.
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
  - uses LLM bridge evidence instead of full raw report content
  - secrets are redacted before prompt construction
- Added OpenAI-compatible LLM client configured for Nvidia Nemotron 120B style endpoints.
- Added PySide6 GUI:
  - menu bar for config control
  - integrated settings dialog
  - mock/KIS REST mode toggle
  - KIS REST, Telegram, and LLM connection tests
  - recent complete-data-day selection
  - scheduler enable/disable toggle
  - macOS launchd schedule install/uninstall actions
  - manual scheduled job execution
  - scheduler status viewer
  - Conditions menu for multi-condition editing and LLM queue selection
  - step-by-step progress timeline
  - current status panel
  - run log panel
  - result table
  - markdown report viewer
- Added scheduler support:
  - default run times: 08:50, 12:50, 16:50, 20:50
  - startup delay: 30 seconds
  - each job performs one-shot re-fetch and re-analysis
  - lock file prevents overlapping scheduled jobs
  - state file records last status/report/error
  - launchd plist generation uses config path only, not secrets
- Added condition queue support:
  - `simulation.strategy_conditions` controls enabled simulation cases
  - `llm_queue` controls which conditions get stateless LLM reports
  - condition names are normalized to lowercase/number/underscore style
  - one raw fetch is reused across enabled conditions in the same run
  - condition-level reports are written under `reports/run_*/conditions/*`
- Added tests for calendar, signal condition, availability, metrics, multi-condition branching, sweep time generation, and pipeline execution.

## Verification Performed

- `python -m pytest`
  - Result: 21 passed
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

- Production NXT snapshot importer or separate capture-process integration.
- Live-account verification of KIS response field parsing.
- Historical D-1 KOSPI market-cap archive for old simulation dates.
- Production Korean exchange holiday calendar.
- Live order placement.
- Advanced visualization such as equity curve charts.

## Known Breakdown Risks

- KIS REST mode may fail or mark dates incomplete until KIS response parsing is tested against real API responses.
- KIS REST historical simulation intentionally fails when futures minute data is missing instead of falling back to current price.
- KIS REST does not support historical multi-time NXT `08:00~08:50` replication through the inspected REST endpoint.
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
- Scheduler launchd jobs can fail if the Python interpreter path, working directory, or PYTHONPATH changes after installation.
- Scheduler jobs intentionally skip when `schedule.enabled` is false, even if launchd is installed.
- Manual scheduled jobs in the GUI still wait the configured startup delay before running.
- Strategy results can be misleading when trade count is low.
- Long and inverse conditions can both trigger on the same date for looser thresholds; simulation records both and leaves conflict interpretation to reports.
- Condition-level LLM reports are independent and do not compare against prior LLM calls.
- Fee, slippage, tick value, and execution timing are simplified assumptions.
- `config.yaml` must remain local and untracked because it will contain API keys.

## Next Best Step

Stabilize the one-shot simulation path further by adding clearer complete-data
diagnostics and KOSPI200 front-month contract cache with explicit next-month
fallback only for contract resolution errors, not for missing historical prices.
