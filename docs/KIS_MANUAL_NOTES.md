# Korea Investment OpenAPI Manual Notes

Source workbook:
`한국투자증권_오픈API_전체문서_20260507_030000.xlsx`

Inspected on 2026-05-07.

## Relevant Sheets

| Purpose | Sheet | Method | TR ID | URL |
|---|---|---|---|---|
| OAuth token | 접근토큰발급(P) | POST | n/a | `/oauth2/tokenP` |
| KOSPI market-cap top list | 국내주식 시가총액 상위 | GET | `FHPST01740000` | `/uapi/domestic-stock/v1/ranking/market-cap` |
| Overtime current price | 국내주식 시간외현재가 | GET | `FHPST02300000` | `/uapi/domestic-stock/v1/quotations/inquire-overtime-price` |
| Overtime fluctuation ranking | 국내주식 시간외등락율순위 | GET | `FHPST02340000` | `/uapi/domestic-stock/v1/ranking/overtime-fluctuation` |
| NXT realtime stock tick | 국내주식 실시간체결가 (NXT) | WEBSOCKET | `H0NXCNT0` | websocket |
| Futures current price | 선물옵션 시세 | GET | `FHMIF10000000` | `/uapi/domestic-futureoption/v1/quotations/inquire-price` |
| Futures minute chart | 선물옵션 분봉조회 | GET | `FHKIF03020200` | `/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice` |

## Implementation Notes

- Token issuance is implemented in `KisRestClient.access_token()`.
- Token cache path is configured by `kis.token_cache_path` and ignored by git.
- Market-cap top list is implemented through `FHPST01740000`.
- Futures current/minute REST access is implemented.
- NXT realtime sheet is websocket-only in the inspected manual.
- Historical NXT snapshots by specific `08:00`, `08:10`, etc. require an
  external data import or a confirmed historical endpoint not yet mapped from
  the workbook. The application does not run an in-app NXT collector.
- KIS REST mode must not fabricate historical multi-time NXT snapshots by
  copying one overtime/current value across multiple signal times.
- Futures minute chart parsing should use the nearest row at or before the
  target time. Current-price fallback is disabled for historical simulation.

## Breakdown Risk

The simulator can run fully in mock mode for development. Real historical
simulation is not complete until NXT snapshots and D-1 historical market-cap
data are captured/imported or provided by a confirmed historical endpoint.
