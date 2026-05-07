from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from kosim.data.calendar import parse_date
from datetime import date, timedelta

from kosim.data.models import FuturesPrice, NxtSnapshot, RawMarketData, StockReturn, UniverseMember


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save_raw_data(self, raw: RawMarketData) -> None:
        payload = {
            "simulation_date": raw.simulation_date.isoformat(),
            "universe_basis_date": raw.universe_basis_date.isoformat(),
            "universe": [member.__dict__ for member in raw.universe],
            "stock_returns": [row.__dict__ for row in raw.stock_returns],
            "futures_prices": [row.__dict__ for row in raw.futures_prices],
        }
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                insert or replace into raw_market_data(simulation_date, payload_json)
                values(?, ?)
                """,
                (raw.simulation_date.isoformat(), json.dumps(payload, ensure_ascii=False)),
            )

    def save_universe(self, simulation_date, basis_date, members: list[UniverseMember]) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executemany(
                """
                insert or ignore into daily_universe(
                    simulation_date, basis_date, symbol, name, rank, market_cap
                ) values(?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        parse_date(simulation_date).isoformat(),
                        parse_date(basis_date).isoformat(),
                        member.symbol,
                        member.name,
                        member.rank,
                        member.market_cap,
                    )
                    for member in members
                ],
            )

    def save_nxt_snapshots(self, snapshots: list[NxtSnapshot]) -> int:
        with sqlite3.connect(self.path) as conn:
            before = conn.total_changes
            conn.executemany(
                """
                insert or ignore into nxt_snapshots(
                    simulation_date, snapshot_time, universe_basis_date, symbol, name,
                    price, return_pct, volume, source
                ) values(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.simulation_date.isoformat(),
                        item.snapshot_time,
                        item.universe_basis_date.isoformat(),
                        item.symbol,
                        item.name,
                        item.price,
                        item.return_pct,
                        item.volume,
                        item.source,
                    )
                    for item in snapshots
                ],
            )
            return conn.total_changes - before

    def save_futures_prices(self, simulation_date, prices: list[FuturesPrice], source: str = "kis") -> int:
        with sqlite3.connect(self.path) as conn:
            before = conn.total_changes
            conn.executemany(
                """
                insert or ignore into futures_prices(
                    simulation_date, price_time, symbol, price, source
                ) values(?, ?, ?, ?, ?)
                """,
                [
                    (
                        parse_date(simulation_date).isoformat(),
                        item.time,
                        item.symbol,
                        item.price,
                        source,
                    )
                    for item in prices
                ],
            )
            return conn.total_changes - before

    def build_raw_from_snapshots(self, simulation_date, signal_times: list[str], futures_times: list[str], futures_symbol: str) -> RawMarketData | None:
        day = parse_date(simulation_date)
        with sqlite3.connect(self.path) as conn:
            universe_rows = conn.execute(
                """
                select basis_date, symbol, name, rank, market_cap
                from daily_universe
                where simulation_date = ?
                order by rank
                """,
                (day.isoformat(),),
            ).fetchall()
            stock_rows = conn.execute(
                """
                select snapshot_time, symbol, name, price, return_pct
                from nxt_snapshots
                where simulation_date = ? and snapshot_time in ({})
                """.format(",".join("?" for _ in signal_times)),
                (day.isoformat(), *signal_times),
            ).fetchall()
            futures_rows = conn.execute(
                """
                select price_time, symbol, price
                from futures_prices
                where simulation_date = ? and price_time in ({}) and symbol = ?
                """.format(",".join("?" for _ in futures_times)),
                (day.isoformat(), *futures_times, futures_symbol),
            ).fetchall()
        if not universe_rows:
            return None
        basis_date = parse_date(universe_rows[0][0])
        return RawMarketData(
            simulation_date=day,
            universe_basis_date=basis_date,
            universe=[
                UniverseMember(symbol=row[1], name=row[2], rank=int(row[3]), market_cap=float(row[4]))
                for row in universe_rows
            ],
            stock_returns=[
                StockReturn(symbol=row[1], name=row[2], signal_time=row[0], price=float(row[3]), return_pct=float(row[4]))
                for row in stock_rows
            ],
            futures_prices=[
                FuturesPrice(time=row[0], symbol=row[1], price=float(row[2]))
                for row in futures_rows
            ],
        )

    def purge_old_snapshots(self, keep_days: int, today: date) -> None:
        cutoff = today - timedelta(days=keep_days)
        with sqlite3.connect(self.path) as conn:
            conn.execute("delete from nxt_snapshots where simulation_date < ?", (cutoff.isoformat(),))
            conn.execute("delete from futures_prices where simulation_date < ?", (cutoff.isoformat(),))
            conn.execute("delete from daily_universe where simulation_date < ?", (cutoff.isoformat(),))

    def list_raw_data_dates(self) -> list:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute("select simulation_date from raw_market_data order by simulation_date").fetchall()
        return [parse_date(row[0]) for row in rows]

    def load_raw_data(self, simulation_date) -> RawMarketData | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "select payload_json from raw_market_data where simulation_date = ?",
                (parse_date(simulation_date).isoformat(),),
            ).fetchone()
        if row is None:
            return None
        return _raw_from_payload(json.loads(row[0]))

    def load_raw_data_many(self, simulation_dates) -> list[RawMarketData]:
        items: list[RawMarketData] = []
        for simulation_date in simulation_dates:
            raw = self.load_raw_data(simulation_date)
            if raw is not None:
                items.append(raw)
        return items

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                create table if not exists raw_market_data(
                    simulation_date text primary key,
                    payload_json text not null,
                    created_at text default current_timestamp
                )
                """
            )
            conn.execute(
                """
                create table if not exists nxt_snapshots(
                    simulation_date text not null,
                    snapshot_time text not null,
                    universe_basis_date text not null,
                    symbol text not null,
                    name text not null,
                    price real not null,
                    return_pct real not null,
                    volume real default 0,
                    source text not null,
                    created_at text default current_timestamp,
                    primary key(simulation_date, snapshot_time, symbol)
                )
                """
            )
            conn.execute(
                """
                create table if not exists futures_prices(
                    simulation_date text not null,
                    price_time text not null,
                    symbol text not null,
                    price real not null,
                    source text not null,
                    created_at text default current_timestamp,
                    primary key(simulation_date, price_time, symbol)
                )
                """
            )
            conn.execute(
                """
                create table if not exists daily_universe(
                    simulation_date text not null,
                    basis_date text not null,
                    symbol text not null,
                    name text not null,
                    rank integer not null,
                    market_cap real not null,
                    created_at text default current_timestamp,
                    primary key(simulation_date, symbol)
                )
                """
            )


def _raw_from_payload(payload: dict) -> RawMarketData:
    return RawMarketData(
        simulation_date=parse_date(payload["simulation_date"]),
        universe_basis_date=parse_date(payload["universe_basis_date"]),
        universe=[
            UniverseMember(
                symbol=str(item["symbol"]),
                name=str(item["name"]),
                market_cap=float(item.get("market_cap", 0.0)),
                rank=int(item.get("rank", index)),
            )
            for index, item in enumerate(payload.get("universe", []), start=1)
        ],
        stock_returns=[
            StockReturn(
                symbol=str(item["symbol"]),
                name=str(item.get("name", item["symbol"])),
                signal_time=str(item["signal_time"]),
                return_pct=float(item["return_pct"]),
                price=float(item.get("price", 0.0)),
            )
            for item in payload.get("stock_returns", [])
        ],
        futures_prices=[
            FuturesPrice(
                symbol=str(item["symbol"]),
                time=str(item["time"]),
                price=float(item["price"]),
            )
            for item in payload.get("futures_prices", [])
        ],
    )
