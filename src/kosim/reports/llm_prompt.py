from __future__ import annotations

import json

from kosim.reports.raw_markdown import raw_data_markdown
from kosim.reports.simulation_markdown import metrics_to_csv, trade_evidence_to_csv
from kosim.simulation.engine import SimulationResult


def build_llm_prompt(config_snapshot: dict, result: SimulationResult, data_limitations: list[str] | None = None) -> str:
    limitations = data_limitations or []
    budget = config_snapshot.get("llm", {}).get("context_budget", {})
    max_prompt_chars = int(budget.get("max_prompt_chars", 120000))
    max_raw_summary_chars = int(budget.get("max_raw_summary_chars", 30000))
    max_sweep_csv_chars = int(budget.get("max_sweep_csv_chars", 50000))
    top_conditions = result.metrics[:20]
    stable_conditions = sorted(
        result.metrics,
        key=lambda item: (item.stability_score, item.trade_count, -abs(item.max_drawdown_pct)),
        reverse=True,
    )[:20]
    worst_conditions = sorted(result.metrics, key=lambda item: item.total_return_pct)[:20]

    raw_summary = _cap_section(raw_data_markdown(result.raw_data), max_raw_summary_chars, "RAW_DATA_SUMMARY")
    sweep_csv = _cap_section(metrics_to_csv(result.metrics), max_sweep_csv_chars, "SWEEP_RESULTS_CSV")
    trade_evidence = trade_evidence_to_csv(result, limit=500)
    prompt = "\n\n".join(
        [
            _instructions(len(result.raw_data)),
            "[CONFIG_SNAPSHOT]\n" + json.dumps(_redacted_config(config_snapshot), ensure_ascii=False, indent=2),
            "[RAW_DATA_SUMMARY]\n" + raw_summary,
            "[SWEEP_RESULTS_CSV]\n" + sweep_csv,
            "[TOP_CONDITIONS_CSV]\n" + metrics_to_csv(top_conditions),
            "[STABLE_CONDITIONS_CSV]\n" + metrics_to_csv(stable_conditions),
            "[WORST_CONDITIONS_CSV]\n" + metrics_to_csv(worst_conditions),
            "[TRADE_EVIDENCE_CSV]\n" + trade_evidence,
            "[DATA_LIMITATIONS]\n" + ("\n".join(f"- {item}" for item in limitations) if limitations else "- No known limitations reported."),
        ]
    )
    if len(prompt) > max_prompt_chars:
        prompt = prompt[:max_prompt_chars] + "\n\n[TRUNCATION_NOTICE]\nPrompt exceeded configured max_prompt_chars and was truncated. Treat missing evidence as unavailable, not as zero."
    return prompt


def _instructions(complete_data_days: int) -> str:
    return """You are a quantitative trading strategy analyst.

You must separate evidence-based simulation analysis from general trading guidance.

For all simulation result interpretation, use ONLY the provided context in this prompt.
Do not use external market data, news, macroeconomic assumptions, company fundamentals, or prior memory for evidence-based analysis.
Do not invent missing values or missing metrics.
If the provided data is insufficient, explicitly say so.

For the "매매전략 제안" section only, you may use general trading and risk-management knowledge.
If you use general knowledge, clearly label it as general guidance.
Do not present general guidance as proven by the provided simulation unless evidence exists in the provided context.

Analyze the sweep simulation results for a KOSPI200 futures long strategy based on stored NXT pre-market stock movement snapshots.

Strategy definition:
- For each simulation date D, the stock universe is selected immediately before data fetching.
- The universe is the KOSPI market-cap top N stocks from D-1, where D-1 means the previous Korean trading day.
- Historical simulation uses the configured 08:50 NXT snapshot as the signal unless the provided config says otherwise.
- Default signal conditions are top10_5_positive, top10_7_positive, and top10_10_positive.
- If a condition is satisfied at the signal time, the strategy enters a long position in KOSPI200 futures.
- The position is closed at each tested exit time from the provided sweep table.
- The result is evaluated by condition_name, signal_time, and exit_time.

Decision principles:
- Do not recommend the condition with the highest total return if it appears unstable or overfit.
- Prefer conditions that are robust across neighboring signal times and nearby exit times.
- Penalize low trade count, high drawdown, weak win rate, unstable performance, and outlier-driven results.
- Consider practical execution timing.
- Focus on repeatability, robustness, and downside control.
- If a condition appears in metrics, verify it against the TRADE_EVIDENCE_CSV table.
- Do not claim a condition is unexplained unless it is absent from TRADE_EVIDENCE_CSV.

Output language: Korean.
Output format: Markdown.
Writing style: top-down. Start with the conclusion first.

The first sentence after "# 결론" must follow this structure:
"최근 """ + str(complete_data_days) + """개 complete-data 거래일의 08:50 NXT 스냅샷을 기준으로 시뮬레이션한 결과, {best_condition_name} 조건에서 {best_exit_time} 청산이 최적임을 확인했다."

If the data is insufficient or the best condition is unreliable, still state the best observed condition, but immediately qualify it:
"다만 trade_count가 {trade_count}회에 불과해 신뢰도는 낮다."

The report must contain exactly these sections in this order:
# 결론
# 최적 조건 Top 5
# 매매전략 제안
# 에비던스
# 리스크
# AI 사용 위험 고지

For "# 최적 조건 Top 5":
- Select about 5 best candidate condition/exit combinations from the provided tables.
- Do not choose conditions with zero trade_count unless every condition has zero trades.
- Prefer robust conditions over highest total_return only.
- If all candidates have too few trades, list the observed top 5 and mark reliability as low.

For "# AI 사용 위험 고지", include this meaning in Korean:
This analysis is AI-assisted and based on provided simulation data and settings. AI cannot fully judge missing data, calculation errors, overfitting, market structure changes, execution costs, or real-time liquidity. This is not investment advice and requires independent verification and risk management before live trading."""


def _cap_section(text: str, max_chars: int, section_name: str) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return (
        f"{head}\n\n[{section_name}_COMPRESSION_NOTICE]\n"
        f"This section exceeded {max_chars} chars. Middle rows were omitted; use provided top/stable/worst/trade evidence tables for decisions.\n\n"
        f"{tail}"
    )


def _redacted_config(config: dict) -> dict:
    secret_keys = {"app_key", "app_secret", "account_no", "bot_token", "chat_id", "api_key"}

    def scrub(value):
        if isinstance(value, dict):
            return {key: ("<redacted>" if key in secret_keys else scrub(nested)) for key, nested in value.items()}
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    return scrub(config)
