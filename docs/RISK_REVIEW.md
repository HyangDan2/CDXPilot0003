# Breakdown Risk Review

This project is designed as a simulator first. Real trading and KIS REST data
use require explicit verification of Korea Investment OpenAPI TR IDs from the
supplied manual.

## Main Failure Modes

- `config.yaml` is missing: copy `config.example.yaml` to `config.yaml`.
- Placeholder secrets are used while Telegram, LLM, or KIS REST mode is enabled.
- KIS REST adapter has documented REST endpoints, but response parsing still
  needs live-account verification.
- Korean exchange holiday list is incomplete unless configured in `data.holidays`.
- NXT data may be unavailable, delayed, rate-limited, or shaped differently from
  regular-market data.
- Production NXT accuracy depends on importing verified NXT snapshots from an
  external capture process or confirmed historical endpoint.
- REST overtime snapshots must not be treated as historical 08:50 NXT evidence.
- Market-cap top 10 from D-1 needs a reliable source before real data mode is used.
- Futures symbol and price convention must be mapped to the exact KIS futures API.
- Recent complete-data-day mode can return zero selected days until raw data has
  been collected or imported.
- Stored snapshot simulation can return zero selected days until `nxt_snapshots`,
  `daily_universe`, and `futures_prices` are populated.
- Recent complete-data-day mode is intentionally strict: any missing configured
  NXT signal time or futures price makes that date incomplete.
- Telegram Markdown can reject malformed markdown or messages above API limits.
  Raw/simulation reports are therefore sent as files, and LLM output is sent as
  plain text chunks without Telegram markdown parsing.
- Telegram photo upload can fail independently from report generation.
- LLM reports may time out or fail if the endpoint is not OpenAI-compatible at
  `/chat/completions`.
- LLM prompt context uses an auto-compression guard. If truncation occurs, the
  model must treat missing evidence as unavailable rather than zero.
- General strategy guidance in the LLM report may use general trading knowledge,
  but simulation conclusions must remain RAG/provided-context-only.
- Simulation output can be misleading if trade count is too small or if one
  outlier day dominates returns.
- Slippage, fees, tick value, and entry execution assumptions are simplified.

## Guardrails Already Implemented

- `config.yaml`, token caches, databases, raw data, reports, logs, and env files
  are ignored by git.
- Example config uses placeholders only.
- Prompt builder redacts configured secrets before building LLM context.
- LLM prompt instructs provided-context-only analysis and Korean markdown output.
- Mock provider is deterministic for repeatable tests.
- SQLite availability checks prevent recent-day simulations from using days with
  missing universe, NXT, or futures data.
- GUI runner executes pipeline in a worker thread and shows step status.
- GUI integration tests run in worker threads so slow network calls do not block
  the main run pipeline.
- Chart generation writes under `reports/charts/{run_tag}` and is ignored by git.
- Snapshot writes use primary-key `insert or ignore` semantics to avoid
  overwriting local data.
