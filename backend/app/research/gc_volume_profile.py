from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


GATE_API_BASE = "https://api.gateio.ws/api/v4"
DEFAULT_SPOT_SYMBOL = "XAUUSD20"
DEFAULT_FUTURES_SYMBOL = "GC=F"
DEFAULT_PANIC_VOL_SYMBOL = "^GVZ"
DEFAULT_SPOT_TICK_DB_PATH = "/root/.gate/gate_tradfi_rm_xauusd_quotes.sqlite"
DEFAULT_GC_KLINE_CACHE_DIR = "/var/lib/fuxi/xau/gc_klines"
SUPPORTED_INTERVALS = {"1m": 60, "5m": 300, "1h": 3600}
CHART_INTERVALS = {"1m", "5m"}
SNAPSHOT_CACHE_TTL_SECONDS = 300.0
SNAPSHOT_REFRESH_AFTER_SECONDS = 15.0
TREND_CACHE_TTL_SECONDS = 300.0
PANIC_VOL_CACHE_TTL_SECONDS = 60.0
_CACHE: dict[tuple[Any, ...], tuple[float, Any]] = {}
_REFRESHING: set[tuple[Any, ...]] = set()


def _cache_get(key: tuple[Any, ...], ttl_seconds: float) -> Any | None:
    entry = _cache_lookup(key)
    if entry is None:
        return None
    age_seconds, value = entry
    if age_seconds > ttl_seconds:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_lookup(key: tuple[Any, ...]) -> tuple[float, Any] | None:
    cached = _CACHE.get(key)
    if not cached:
        return None
    created_at, value = cached
    return time.time() - created_at, deepcopy(value)


def _cache_set(key: tuple[Any, ...], value: Any) -> None:
    _CACHE[key] = (time.time(), deepcopy(value))


def _start_background_refresh(key: tuple[Any, ...], builder) -> None:
    if key in _REFRESHING:
        return
    _REFRESHING.add(key)

    def _run() -> None:
        try:
            value = builder()
            value["cache"] = {
                "hit": False,
                "refreshing": False,
                "age_seconds": 0.0,
                "ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
                "refresh_after_seconds": SNAPSHOT_REFRESH_AFTER_SECONDS,
            }
            _cache_set(key, value)
        finally:
            _REFRESHING.discard(key)

    threading.Thread(target=_run, name="xau-chart-cache-refresh", daemon=True).start()


def _fetch_json(url: str, *, timeout: float = 30.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "fuxi-gc-volume-profile/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _slug_symbol(symbol: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in symbol).strip("_") or "symbol"


def _gc_cache_dir() -> Path:
    return Path(os.getenv("FUXI_GC_KLINE_CACHE_DIR", DEFAULT_GC_KLINE_CACHE_DIR))


def _gc_cache_file(symbol: str, interval: str, range_days: int) -> Path:
    return _gc_cache_dir() / f"{_slug_symbol(symbol)}_{interval}_{int(range_days)}d.json"


def _gc_cache_candidates(symbol: str, interval: str, range_days: int) -> list[Path]:
    cache_dir = _gc_cache_dir()
    exact = _gc_cache_file(symbol, interval, range_days)
    candidates: list[Path] = [exact]
    if cache_dir.exists():
        prefix = f"{_slug_symbol(symbol)}_{interval}_"
        others = [
            path
            for path in cache_dir.glob(f"{prefix}*d.json")
            if path != exact
        ]

        def score(path: Path) -> tuple[int, float]:
            suffix = path.stem.removeprefix(prefix).removesuffix("d")
            try:
                days = int(suffix)
            except ValueError:
                days = 0
            enough_window = 0 if days >= range_days else 1
            return (enough_window, -path.stat().st_mtime)

        candidates.extend(sorted(others, key=score))
    return candidates


def _write_gc_payload_cache(symbol: str, interval: str, range_days: int, payload: dict[str, Any]) -> None:
    path = _gc_cache_file(symbol, interval, range_days)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        tmp_path.replace(path)
    except OSError:
        return


def _row_value(row: dict[str, Any], *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def _normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    return frame.reset_index(drop=True)


def _gate_tradfi_klines_to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    rows = ((payload.get("data") or {}).get("list") or []) if isinstance(payload, dict) else []
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime([row.get("t") for row in rows], unit="s", utc=True),
            "open": [_row_value(row, "o", "open") for row in rows],
            "high": [_row_value(row, "h", "high") for row in rows],
            "low": [_row_value(row, "l", "low") for row in rows],
            "close": [_row_value(row, "c", "close") for row in rows],
            "volume": [_row_value(row, "v", "volume", "vol", default=1.0) for row in rows],
        }
    )
    return _normalize_ohlcv(frame)


def fetch_gate_xau_klines(
    symbol: str = DEFAULT_SPOT_SYMBOL,
    *,
    interval: str = "5m",
    days: float = 3.0,
    end_time: datetime | None = None,
    limit: int = 500,
    sleep_seconds: float = 0.02,
) -> pd.DataFrame:
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")

    end = end_time or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = end - timedelta(days=float(days))
    cursor = int(start.timestamp())
    end_ts = int(end.timestamp())
    step_seconds = max(int(limit), 1) * SUPPORTED_INTERVALS[interval]
    frames: list[pd.DataFrame] = []

    while cursor < end_ts:
        chunk_end = min(cursor + step_seconds, end_ts)
        query = urllib.parse.urlencode(
            {
                "kline_type": interval,
                "begin_time": cursor,
                "end_time": chunk_end,
            }
        )
        url = f"{GATE_API_BASE}/tradfi/symbols/{urllib.parse.quote(symbol, safe='')}/klines?{query}"
        frame = _gate_tradfi_klines_to_frame(_fetch_json(url))
        if not frame.empty:
            frames.append(frame)
            last_ts = int(pd.Timestamp(frame["date"].iloc[-1]).timestamp()) + SUPPORTED_INTERVALS[interval]
            cursor = max(last_ts, chunk_end)
        else:
            cursor = chunk_end
        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

    if not frames:
        raise RuntimeError(f"Gate returned no klines for {symbol}")
    frame = _normalize_ohlcv(pd.concat(frames, ignore_index=True))
    frame.attrs["source"] = "Gate TradFi klines"
    return frame


def _tick_symbol_for_spot(symbol: str) -> str:
    return "XAUUSD" if symbol.upper() == "XAUUSD20" else symbol.upper()


def fetch_server_xau_tick_klines(
    symbol: str = DEFAULT_SPOT_SYMBOL,
    *,
    interval: str = "1m",
    days: float = 2.0,
    db_path: str | None = None,
) -> pd.DataFrame:
    if interval not in CHART_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")

    path = db_path or os.getenv("FUXI_XAU_TICK_DB", DEFAULT_SPOT_TICK_DB_PATH)
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"XAU tick DB not found: {path}")

    tick_symbol = _tick_symbol_for_spot(symbol)
    bucket_ms = SUPPORTED_INTERVALS[interval] * 1000
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0) as conn:
        latest_row = conn.execute(
            "select max(ts) from quote_samples where symbol = ? and mid > 0",
            (tick_symbol,),
        ).fetchone()
        latest_ts = int(latest_row[0] or 0) if latest_row else 0
        if latest_ts <= 0:
            raise RuntimeError(f"tick DB has no quote_samples for {tick_symbol}")

        cutoff_ts = latest_ts - int(float(days) * 86_400_000)
        query = """
            with q as (
                select
                    id,
                    ts,
                    mid,
                    (ts / ?) * ? as bucket_ms
                from quote_samples
                where symbol = ?
                  and ts >= ?
                  and mid is not null
                  and mid > 0
            ),
            ranked as (
                select
                    bucket_ms,
                    ts,
                    mid,
                    row_number() over (partition by bucket_ms order by ts asc, id asc) as rn_open,
                    row_number() over (partition by bucket_ms order by ts desc, id desc) as rn_close
                from q
            )
            select
                bucket_ms as date,
                max(case when rn_open = 1 then mid end) as open,
                max(mid) as high,
                min(mid) as low,
                max(case when rn_close = 1 then mid end) as close,
                count(*) as volume
            from ranked
            group by bucket_ms
            order by bucket_ms
        """
        frame = pd.read_sql_query(
            query,
            conn,
            params=(bucket_ms, bucket_ms, tick_symbol, cutoff_ts),
        )

    if frame.empty:
        raise RuntimeError(f"tick DB returned no {interval} bars for {tick_symbol}")
    frame["date"] = pd.to_datetime(frame["date"], unit="ms", utc=True)
    frame = _normalize_ohlcv(frame)
    frame.attrs["source"] = f"Server tick DB quote_samples ({tick_symbol})"
    frame.attrs["tick_db_path"] = path
    return frame


def fetch_spot_xau_klines(
    symbol: str = DEFAULT_SPOT_SYMBOL,
    *,
    interval: str = "5m",
    days: float = 3.0,
) -> pd.DataFrame:
    try:
        return fetch_server_xau_tick_klines(symbol, interval=interval, days=days)
    except Exception as exc:
        frame = fetch_gate_xau_klines(symbol, interval=interval, days=days)
        frame.attrs["source_error"] = str(exc)
        return frame


def fetch_yahoo_gc_klines(
    symbol: str = DEFAULT_FUTURES_SYMBOL,
    *,
    interval: str = "5m",
    days: float = 3.0,
) -> pd.DataFrame:
    if interval not in CHART_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")

    # Yahoo's chart API accepts short intraday ranges as "1d", "5d", etc.
    range_days = min(max(math.ceil(float(days)), 1), 7 if interval == "1m" else 60)
    payload = fetch_yahoo_gc_payload(symbol, interval=interval, range_days=range_days)
    frame = parse_yahoo_gc_payload(symbol, payload)
    frame.attrs["source"] = "Yahoo Finance chart GC=F"
    _write_gc_payload_cache(symbol, interval, range_days, payload)
    return frame


def fetch_yahoo_gc_payload(
    symbol: str = DEFAULT_FUTURES_SYMBOL,
    *,
    interval: str = "5m",
    range_days: int = 3,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "range": f"{int(range_days)}d",
            "interval": interval,
            "includePrePost": "true",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?{query}"
    return _fetch_json(url)


def parse_yahoo_gc_payload(symbol: str, payload: dict[str, Any]) -> pd.DataFrame:
    error = (payload.get("chart") or {}).get("error")
    if error:
        raise RuntimeError(f"Yahoo chart error for {symbol}: {error}")
    result = ((payload.get("chart") or {}).get("result") or [])
    if not result:
        raise RuntimeError(f"Yahoo returned no chart data for {symbol}")

    chart = result[0]
    timestamps = chart.get("timestamp") or []
    quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(timestamps, unit="s", utc=True),
            "open": quote.get("open") or [],
            "high": quote.get("high") or [],
            "low": quote.get("low") or [],
            "close": quote.get("close") or [],
            "volume": quote.get("volume") or [],
        }
    )
    frame = _normalize_ohlcv(frame)
    frame = frame[frame["volume"].fillna(0) > 0]
    if frame.empty:
        raise RuntimeError(f"Yahoo returned no non-zero volume bars for {symbol}")
    return frame.reset_index(drop=True)


def fetch_cached_gc_klines(
    symbol: str = DEFAULT_FUTURES_SYMBOL,
    *,
    interval: str = "5m",
    days: float = 3.0,
    live_error: str | None = None,
) -> pd.DataFrame:
    range_days = min(max(math.ceil(float(days)), 1), 7 if interval == "1m" else 60)
    errors: list[str] = []
    for path in _gc_cache_candidates(symbol, interval, range_days):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            frame = parse_yahoo_gc_payload(symbol, payload)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        if not frame.empty:
            latest = pd.Timestamp(frame["date"].max())
            cutoff = latest - pd.Timedelta(days=float(days))
            frame = frame[frame["date"] >= cutoff].reset_index(drop=True)
        if frame.empty:
            errors.append(f"{path.name}: no rows in requested window")
            continue

        frame.attrs["source"] = "Yahoo Finance chart GC=F cached"
        frame.attrs["source_error"] = live_error
        frame.attrs["cache_path"] = str(path)
        frame.attrs["cache_mtime"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        return frame

    detail = "; ".join(errors) if errors else "no cache files"
    raise RuntimeError(f"Yahoo GC live unavailable and cached GC data unavailable: {live_error}; {detail}")


def fetch_gc_klines_with_cache(
    symbol: str = DEFAULT_FUTURES_SYMBOL,
    *,
    interval: str = "5m",
    days: float = 3.0,
) -> pd.DataFrame:
    try:
        return fetch_yahoo_gc_klines(symbol, interval=interval, days=days)
    except Exception as exc:
        return fetch_cached_gc_klines(symbol, interval=interval, days=days, live_error=str(exc))


def fetch_yahoo_daily_index(
    symbol: str,
    *,
    range_window: str = "1y",
) -> pd.DataFrame:
    query = urllib.parse.urlencode(
        {
            "range": range_window,
            "interval": "1d",
            "includePrePost": "false",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?{query}"
    payload = _fetch_json(url)
    error = (payload.get("chart") or {}).get("error")
    if error:
        raise RuntimeError(f"Yahoo chart error for {symbol}: {error}")
    result = ((payload.get("chart") or {}).get("result") or [])
    if not result:
        raise RuntimeError(f"Yahoo returned no chart data for {symbol}")

    chart = result[0]
    timestamps = chart.get("timestamp") or []
    quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(timestamps, unit="s", utc=True),
            "open": quote.get("open") or [],
            "high": quote.get("high") or [],
            "low": quote.get("low") or [],
            "close": quote.get("close") or [],
            "volume": quote.get("volume") or [],
        }
    )
    return _normalize_ohlcv(frame)


def fetch_gold_panic_volatility(
    symbol: str = DEFAULT_PANIC_VOL_SYMBOL,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    cache_key = ("panic_volatility", symbol)
    if not force_refresh:
        cached = _cache_get(cache_key, PANIC_VOL_CACHE_TTL_SECONDS)
        if cached is not None:
            cached["cache"] = {"hit": True, "ttl_seconds": PANIC_VOL_CACHE_TTL_SECONDS}
            return cached

    frame = fetch_yahoo_daily_index(symbol, range_window="1y")
    frame = frame.dropna(subset=["close"]).reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"Yahoo returned no valid volatility rows for {symbol}")

    latest_row = frame.iloc[-1]
    previous_row = frame.iloc[-2] if len(frame) > 1 else latest_row
    latest = float(latest_row["close"])
    previous = float(previous_row["close"])
    change = latest - previous
    change_pct = change / previous * 100 if previous else None
    percentile_1y = float((frame["close"] <= latest).mean())

    if percentile_1y >= 0.85:
        state = "panic"
    elif percentile_1y >= 0.65:
        state = "elevated"
    elif percentile_1y <= 0.25:
        state = "calm"
    else:
        state = "normal"

    result = {
        "visible": True,
        "symbol": symbol,
        "name": "Cboe Gold ETF Volatility Index",
        "source": "Yahoo Finance / Cboe GVZ",
        "definition": "30-day implied volatility estimate for GLD options, VIX-style gold fear gauge",
        "latest": latest,
        "previous_close": previous,
        "change": float(change),
        "change_pct": None if change_pct is None else float(change_pct),
        "percentile_1y": percentile_1y,
        "state": state,
        "asof": pd.Timestamp(latest_row["date"]).isoformat(),
        "points": [
            {
                "time": int(pd.Timestamp(row.date).timestamp()),
                "value": float(row.close),
            }
            for row in frame.itertuples(index=False)
            if pd.notna(row.close)
        ],
        "cache": {"hit": False, "ttl_seconds": PANIC_VOL_CACHE_TTL_SECONDS},
    }
    _cache_set(cache_key, result)
    return result


def _round_to_step(value: float, step: float) -> float:
    return round(round(float(value) / step) * step, 10)


def _aligned_gc_xau(gc_frame: pd.DataFrame, xau_frame: pd.DataFrame, interval: str) -> pd.DataFrame:
    tolerance = pd.Timedelta(seconds=SUPPORTED_INTERVALS[interval])
    left = gc_frame.sort_values("date").copy()
    right = xau_frame[["date", "close"]].sort_values("date").rename(columns={"close": "xau_close"})
    aligned = pd.merge_asof(left, right, on="date", direction="nearest", tolerance=tolerance)
    aligned = aligned.dropna(subset=["xau_close", "close", "volume"])
    if aligned.empty:
        raise RuntimeError("GC and XAU windows do not overlap")
    aligned["basis"] = aligned["xau_close"] - aligned["close"]
    aligned["ratio"] = np.where(aligned["close"] != 0, aligned["xau_close"] / aligned["close"], np.nan)
    return aligned.reset_index(drop=True)


def build_mapped_volume_profile(
    gc_frame: pd.DataFrame,
    xau_frame: pd.DataFrame,
    *,
    interval: str = "5m",
    lookback_bars: int = 240,
    price_step: float = 0.5,
    mapping_method: str = "additive",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if interval not in CHART_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    if price_step <= 0:
        raise ValueError("price_step must be positive")
    if mapping_method not in {"additive", "ratio"}:
        raise ValueError(f"unsupported mapping_method: {mapping_method}")

    gc_window = gc_frame.tail(max(int(lookback_bars), 1)).copy()
    aligned = _aligned_gc_xau(gc_window, xau_frame, interval)
    buckets: dict[float, float] = {}

    for row in aligned.itertuples(index=False):
        low = min(float(row.low), float(row.high))
        high = max(float(row.low), float(row.high))
        volume = max(float(row.volume or 0.0), 0.0)
        if volume <= 0:
            continue
        start = math.floor(low / price_step) * price_step
        end = math.ceil(high / price_step) * price_step
        gc_prices = np.arange(start, end + price_step * 0.5, price_step)
        if len(gc_prices) == 0:
            gc_prices = np.array([float(row.close)])
        share = volume / len(gc_prices)
        for gc_price in gc_prices:
            if mapping_method == "ratio":
                mapped = float(gc_price) * float(row.ratio)
            else:
                mapped = float(gc_price) + float(row.basis)
            bucket = _round_to_step(mapped, price_step)
            buckets[bucket] = buckets.get(bucket, 0.0) + share

    if not buckets:
        raise RuntimeError("mapped profile is empty")

    profile = pd.DataFrame(
        [{"price": price, "volume": volume} for price, volume in sorted(buckets.items())]
    )
    total_volume = float(profile["volume"].sum())
    profile["volume_pct"] = profile["volume"] / total_volume if total_volume > 0 else 0.0
    profile["lower"] = profile["price"] - price_step / 2
    profile["upper"] = profile["price"] + price_step / 2

    metadata = {
        "aligned_rows": int(len(aligned)),
        "gc_rows": int(len(gc_window)),
        "xau_rows": int(len(xau_frame)),
        "start": aligned["date"].min().isoformat(),
        "end": aligned["date"].max().isoformat(),
        "median_basis": float(aligned["basis"].median()),
        "mean_basis": float(aligned["basis"].mean()),
        "median_ratio": float(aligned["ratio"].median()),
        "mapping_method": mapping_method,
    }
    return profile, metadata


def detect_profile_zones(
    profile: pd.DataFrame,
    *,
    price_step: float = 0.5,
    value_area_pct: float = 0.7,
    max_zones: int = 6,
    gap_steps: int = 1,
    current_price: float | None = None,
) -> list[dict[str, Any]]:
    if profile.empty:
        return []
    value_area_pct = min(max(float(value_area_pct), 0.05), 1.0)
    total_volume = float(profile["volume"].sum())
    sorted_profile = profile.sort_values("volume", ascending=False).copy()
    sorted_profile["cum_pct"] = sorted_profile["volume"].cumsum() / total_volume
    selected = sorted_profile[sorted_profile["cum_pct"] <= value_area_pct].copy()
    if selected.empty:
        selected = sorted_profile.head(1).copy()

    selected = selected.sort_values("price")
    zones: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    max_gap = price_step * max(int(gap_steps), 0) + price_step * 0.01
    last_price: float | None = None
    for row in selected.to_dict("records"):
        price = float(row["price"])
        if current and last_price is not None and price - last_price > max_gap + price_step:
            zones.append(current)
            current = []
        current.append(row)
        last_price = price
    if current:
        zones.append(current)

    zone_rows: list[dict[str, Any]] = []
    for rows in zones:
        frame = pd.DataFrame(rows)
        if frame.empty:
            continue
        peak = frame.sort_values("volume", ascending=False).iloc[0]
        lower = float(frame["lower"].min())
        upper = float(frame["upper"].max())
        volume = float(frame["volume"].sum())
        center = (lower + upper) / 2
        zone = {
            "lower": lower,
            "upper": upper,
            "center": center,
            "poc": float(peak["price"]),
            "volume": volume,
            "volume_pct": volume / total_volume if total_volume > 0 else 0.0,
            "bucket_count": int(len(frame)),
            "width": upper - lower,
            "distance_to_price": None if current_price is None else center - float(current_price),
        }
        zone_rows.append(zone)

    zone_rows.sort(key=lambda item: item["volume"], reverse=True)
    for idx, zone in enumerate(zone_rows[:max_zones], start=1):
        zone["rank"] = idx
    return zone_rows[:max_zones]


def _frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        dt = pd.Timestamp(row["date"])
        records.append(
            {
                "date": dt.isoformat(),
                "time": int(dt.timestamp()),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume") or 0.0),
            }
        )
    return records


def build_gc_volume_profile_snapshot(
    *,
    spot_symbol: str = DEFAULT_SPOT_SYMBOL,
    futures_symbol: str = DEFAULT_FUTURES_SYMBOL,
    interval: str = "5m",
    days: float = 3.0,
    lookback_bars: int = 240,
    price_step: float = 0.5,
    value_area_pct: float = 0.7,
    max_zones: int = 6,
    mapping_method: str = "additive",
) -> dict[str, Any]:
    if interval not in CHART_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")

    xau_frame = fetch_spot_xau_klines(spot_symbol, interval=interval, days=days)
    current_price = float(xau_frame["close"].iloc[-1])
    futures_error: str | None = None
    futures_source = "Yahoo Finance chart GC=F"
    futures_cache: dict[str, Any] | None = None
    try:
        gc_frame = fetch_gc_klines_with_cache(futures_symbol, interval=interval, days=days)
        futures_source = gc_frame.attrs.get("source", futures_source)
        futures_error = gc_frame.attrs.get("source_error")
        if gc_frame.attrs.get("cache_path"):
            futures_cache = {
                "path": gc_frame.attrs.get("cache_path"),
                "mtime": gc_frame.attrs.get("cache_mtime"),
            }
        profile, mapping = build_mapped_volume_profile(
            gc_frame,
            xau_frame,
            interval=interval,
            lookback_bars=lookback_bars,
            price_step=price_step,
            mapping_method=mapping_method,
        )
        zones = detect_profile_zones(
            profile,
            price_step=price_step,
            value_area_pct=value_area_pct,
            max_zones=max_zones,
            current_price=current_price,
        )
        poc_row = profile.sort_values("volume", ascending=False).iloc[0]
        profile_payload = {
            "poc": float(poc_row["price"]),
            "total_volume": float(profile["volume"].sum()),
            "bucket_count": int(len(profile)),
            "buckets": [
                {
                    "price": float(row["price"]),
                    "lower": float(row["lower"]),
                    "upper": float(row["upper"]),
                    "volume": float(row["volume"]),
                    "volume_pct": float(row["volume_pct"]),
                }
                for row in profile.sort_values("price").to_dict("records")
            ],
        }
    except Exception as exc:
        futures_error = str(exc)
        zones = []
        mapping = {
            "aligned_rows": 0,
            "gc_rows": 0,
            "xau_rows": int(len(xau_frame)),
            "start": pd.Timestamp(xau_frame["date"].min()).isoformat(),
            "end": pd.Timestamp(xau_frame["date"].max()).isoformat(),
            "median_basis": None,
            "mean_basis": None,
            "median_ratio": None,
            "mapping_method": mapping_method,
            "error": futures_error,
        }
        profile_payload = {
            "poc": None,
            "total_volume": 0.0,
            "bucket_count": 0,
            "buckets": [],
            "error": futures_error,
        }

    return {
        "spot_symbol": spot_symbol,
        "futures_symbol": futures_symbol,
        "interval": interval,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "spot": xau_frame.attrs.get("source", "Gate TradFi klines"),
            "futures": futures_source,
            "volume_owner": "COMEX GC futures",
            "spot_fallback": xau_frame.attrs.get("source_error"),
            "futures_error": futures_error,
            "futures_cache": futures_cache,
        },
        "window": mapping,
        "settings": {
            "days": float(days),
            "lookback_bars": int(lookback_bars),
            "price_step": float(price_step),
            "value_area_pct": float(value_area_pct),
            "max_zones": int(max_zones),
        },
        "last_price": current_price,
        "candles": _frame_to_records(xau_frame),
        "profile": profile_payload,
        "zones": zones,
    }


def resample_to_120m(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    indexed = frame.copy()
    indexed["date"] = pd.to_datetime(indexed["date"], utc=True)
    indexed = indexed.set_index("date").sort_index()
    resampled = indexed.resample("120min", origin="epoch").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return _normalize_ohlcv(resampled.dropna(subset=["open", "high", "low", "close"]).reset_index())


def _atr(frame: pd.DataFrame, period: int = 14) -> float:
    if frame.empty:
        return 0.0
    prev_close = frame["close"].shift(1)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    value = float(tr.tail(period).mean())
    return value if math.isfinite(value) else 0.0


def _find_swings(frame: pd.DataFrame, *, wing: int = 2) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lows: list[dict[str, Any]] = []
    highs: list[dict[str, Any]] = []
    if len(frame) < wing * 2 + 1:
        return lows, highs

    for idx in range(wing, len(frame) - wing):
        row = frame.iloc[idx]
        left = frame.iloc[idx - wing:idx]
        right = frame.iloc[idx + 1:idx + wing + 1]
        low = float(row["low"])
        high = float(row["high"])
        body_low = float(min(row["open"], row["close"]))
        body_high = float(max(row["open"], row["close"]))
        ts = pd.Timestamp(row["date"])
        if low < float(left["low"].min()) and low <= float(right["low"].min()):
            lows.append(
                {
                    "index": idx,
                    "time": int(ts.timestamp()),
                    "date": ts.isoformat(),
                    "price": low,
                    "body_price": body_low,
                }
            )
        if high > float(left["high"].max()) and high >= float(right["high"].max()):
            highs.append(
                {
                    "index": idx,
                    "time": int(ts.timestamp()),
                    "date": ts.isoformat(),
                    "price": high,
                    "body_price": body_high,
                }
            )
    return lows, highs


def _line_value(anchor_a: dict[str, Any], anchor_b: dict[str, Any], ts: int, *, key: str = "price") -> float:
    t1 = int(anchor_a["time"])
    t2 = int(anchor_b["time"])
    y1 = float(anchor_a[key])
    y2 = float(anchor_b[key])
    if t2 == t1:
        return y2
    return y1 + (y2 - y1) * ((int(ts) - t1) / (t2 - t1))


def _candidate_trend(
    frame: pd.DataFrame,
    swings: list[dict[str, Any]],
    *,
    direction: str,
    tolerance: float,
) -> dict[str, Any] | None:
    if len(swings) < 2:
        return None

    best: dict[str, Any] | None = None
    recent_swings = swings[-12:]
    for left_idx in range(len(recent_swings) - 1):
        for right_idx in range(left_idx + 1, len(recent_swings)):
            a = recent_swings[left_idx]
            b = recent_swings[right_idx]
            if direction == "up" and float(b["price"]) <= float(a["price"]):
                continue
            if direction == "down" and float(b["price"]) >= float(a["price"]):
                continue
            if int(b["time"]) <= int(a["time"]):
                continue

            touches = 0
            violations = 0
            touch_points: list[dict[str, Any]] = []
            scan = frame.iloc[int(a["index"]):].copy()
            for row in scan.itertuples(index=False):
                ts = int(pd.Timestamp(row.date).timestamp())
                line_price = _line_value(a, b, ts)
                if direction == "up":
                    distance = float(row.low) - line_price
                    if abs(distance) <= tolerance:
                        touches += 1
                        touch_points.append({"time": ts, "price": float(row.low)})
                    if float(row.close) < line_price - tolerance:
                        violations += 1
                else:
                    distance = float(row.high) - line_price
                    if abs(distance) <= tolerance:
                        touches += 1
                        touch_points.append({"time": ts, "price": float(row.high)})
                    if float(row.close) > line_price + tolerance:
                        violations += 1

            duration_days = (int(frame["date"].iloc[-1].timestamp()) - int(a["time"])) / 86400
            slope_per_day = (_line_value(a, b, int(a["time"]) + 86400) - float(a["price"]))
            slope_abs = abs(slope_per_day)
            slope_penalty = 0.0
            if slope_abs > tolerance * 6:
                slope_penalty = 5.0
            score = touches * 10 + duration_days * 0.25 - violations * 4 - slope_penalty
            candidate = {
                "direction": direction,
                "anchor_a": a,
                "anchor_b": b,
                "touches": int(touches),
                "violations": int(violations),
                "touch_points": touch_points[-8:],
                "duration_days": float(duration_days),
                "slope_per_day": float(slope_per_day),
                "score": float(score),
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
    return best


def _cluster_swing_levels(
    swings: list[dict[str, Any]],
    *,
    tolerance: float,
    kind: str,
) -> list[dict[str, Any]]:
    if not swings:
        return []
    sorted_swings = sorted(swings, key=lambda item: float(item["price"]))
    clusters: list[list[dict[str, Any]]] = []
    for swing in sorted_swings:
        price = float(swing["price"])
        if not clusters:
            clusters.append([swing])
            continue
        center = sum(float(item["price"]) for item in clusters[-1]) / len(clusters[-1])
        if abs(price - center) <= tolerance:
            clusters[-1].append(swing)
        else:
            clusters.append([swing])

    levels: list[dict[str, Any]] = []
    for rows in clusters:
        prices = [float(item["price"]) for item in rows]
        center = sum(prices) / len(prices)
        lower = min(prices) - tolerance * 0.35
        upper = max(prices) + tolerance * 0.35
        latest = max(rows, key=lambda item: int(item["time"]))
        first = min(rows, key=lambda item: int(item["time"]))
        levels.append(
            {
                "kind": kind,
                "center": float(center),
                "lower": float(lower),
                "upper": float(upper),
                "touches": int(len(rows)),
                "first_time": int(first["time"]),
                "last_time": int(latest["time"]),
                "points": rows[-6:],
            }
        )
    return levels


def detect_120m_support_resistance(
    frame_120m: pd.DataFrame,
    lows: list[dict[str, Any]],
    highs: list[dict[str, Any]],
    *,
    atr: float,
) -> dict[str, Any]:
    if frame_120m.empty:
        return {"visible": False, "status": "insufficient_data"}

    current_price = float(frame_120m["close"].iloc[-1])
    tolerance = max(float(atr) * 0.28, 1.0)
    support_levels = _cluster_swing_levels(lows[-24:], tolerance=tolerance, kind="support")
    resistance_levels = _cluster_swing_levels(highs[-24:], tolerance=tolerance, kind="resistance")

    support_candidates = [level for level in support_levels if float(level["center"]) <= current_price + tolerance]
    resistance_candidates = [level for level in resistance_levels if float(level["center"]) >= current_price - tolerance]
    support = max(support_candidates, key=lambda item: (float(item["center"]), int(item["touches"])), default=None)
    resistance = min(resistance_candidates, key=lambda item: (float(item["center"]), -int(item["touches"])), default=None)

    recent = frame_120m.tail(48)
    if support is None and not recent.empty:
        low_row = recent.loc[recent["low"].idxmin()]
        support = {
            "kind": "support",
            "center": float(low_row["low"]),
            "lower": float(low_row["low"] - tolerance * 0.35),
            "upper": float(low_row["low"] + tolerance * 0.35),
            "touches": 1,
            "first_time": int(pd.Timestamp(low_row["date"]).timestamp()),
            "last_time": int(pd.Timestamp(low_row["date"]).timestamp()),
            "points": [],
        }
    if resistance is None and not recent.empty:
        high_row = recent.loc[recent["high"].idxmax()]
        resistance = {
            "kind": "resistance",
            "center": float(high_row["high"]),
            "lower": float(high_row["high"] - tolerance * 0.35),
            "upper": float(high_row["high"] + tolerance * 0.35),
            "touches": 1,
            "first_time": int(pd.Timestamp(high_row["date"]).timestamp()),
            "last_time": int(pd.Timestamp(high_row["date"]).timestamp()),
            "points": [],
        }

    if support is None or resistance is None:
        return {
            "visible": False,
            "status": "no_level_pair",
            "current_price": current_price,
            "support": support,
            "resistance": resistance,
        }

    support_price = float(support["center"])
    resistance_price = float(resistance["center"])
    if resistance_price <= support_price:
        lower = min(float(frame_120m["low"].tail(48).min()), support_price, resistance_price)
        upper = max(float(frame_120m["high"].tail(48).max()), support_price, resistance_price)
        support["center"] = lower
        support["lower"] = lower - tolerance * 0.35
        support["upper"] = lower + tolerance * 0.35
        resistance["center"] = upper
        resistance["lower"] = upper - tolerance * 0.35
        resistance["upper"] = upper + tolerance * 0.35
        support_price = float(support["center"])
        resistance_price = float(resistance["center"])

    range_width = resistance_price - support_price
    range_position = (current_price - support_price) / range_width if range_width > 0 else None
    if range_position is None:
        directional_context = "unknown"
        bias = "neutral"
    elif range_position <= 0.35:
        directional_context = "near_support"
        bias = "long_reclaim_5m_lower"
    elif range_position >= 0.65:
        directional_context = "near_resistance"
        bias = "short_break_5m_upper"
    else:
        directional_context = "middle_range"
        bias = "wait"

    return {
        "visible": True,
        "status": "valid",
        "timeframe": "120m",
        "current_price": current_price,
        "support": support,
        "resistance": resistance,
        "range_width": float(range_width),
        "range_position": None if range_position is None else float(range_position),
        "directional_context": directional_context,
        "bias": bias,
        "tolerance": float(tolerance),
    }


def detect_120m_trend_region(frame_120m: pd.DataFrame, *, wing: int = 2) -> dict[str, Any]:
    if frame_120m.empty or len(frame_120m) < wing * 2 + 8:
        return {"status": "insufficient_data", "timeframe": "120m", "visible": False}

    lows, highs = _find_swings(frame_120m, wing=wing)
    atr = _atr(frame_120m, 14)
    tolerance = max(atr * 0.35, 0.8)
    support_resistance = detect_120m_support_resistance(frame_120m, lows, highs, atr=atr)
    up = _candidate_trend(frame_120m, lows, direction="up", tolerance=tolerance)
    down = _candidate_trend(frame_120m, highs, direction="down", tolerance=tolerance)

    candidates = [item for item in (up, down) if item is not None]
    if not candidates:
        return {
            "status": "no_valid_trend",
            "timeframe": "120m",
            "visible": False,
            "support_resistance": support_resistance,
            "swing_lows": lows[-8:],
            "swing_highs": highs[-8:],
        }

    best = max(candidates, key=lambda item: item["score"])
    valid = best["touches"] >= 3 and best["duration_days"] >= 7 and best["violations"] <= 2
    first_ts = int(pd.Timestamp(frame_120m["date"].iloc[max(0, int(best["anchor_a"]["index"]) - 2)]).timestamp())
    last_ts = int(pd.Timestamp(frame_120m["date"].iloc[-1]).timestamp())
    extend_ts = last_ts + 120 * 60 * 4
    times = [first_ts, last_ts, extend_ts]
    wick_points = [{"time": ts, "value": _line_value(best["anchor_a"], best["anchor_b"], ts)} for ts in times]
    body_points = [{"time": ts, "value": _line_value(best["anchor_a"], best["anchor_b"], ts, key="body_price")} for ts in times]

    direction = str(best["direction"])
    if direction == "up":
        lower_points = wick_points
        upper_points = body_points
    else:
        lower_points = body_points
        upper_points = wick_points

    latest_lower = lower_points[1]["value"]
    latest_upper = upper_points[1]["value"]
    if latest_lower > latest_upper:
        latest_lower, latest_upper = latest_upper, latest_lower

    last_close = float(frame_120m["close"].iloc[-1])
    if direction == "up":
        state = "intact" if last_close >= latest_lower - tolerance else "broken"
    else:
        state = "intact" if last_close <= latest_upper + tolerance else "broken"

    return {
        "status": "valid" if valid else "tentative",
        "state": state,
        "timeframe": "120m",
        "visible": True,
        "direction": direction,
        "touches": int(best["touches"]),
        "violations": int(best["violations"]),
        "duration_days": float(best["duration_days"]),
        "slope_per_day": float(best["slope_per_day"]),
        "atr": float(atr),
        "tolerance": float(tolerance),
        "latest_lower": float(latest_lower),
        "latest_upper": float(latest_upper),
        "lower_line": lower_points,
        "upper_line": upper_points,
        "anchor_a": best["anchor_a"],
        "anchor_b": best["anchor_b"],
        "touch_points": best["touch_points"],
        "support_resistance": support_resistance,
        "swing_lows": lows[-8:],
        "swing_highs": highs[-8:],
    }


def fetch_120m_trend_region(
    symbol: str = DEFAULT_SPOT_SYMBOL,
    *,
    days: float = 45.0,
    force_refresh: bool = False,
) -> dict[str, Any]:
    cache_key = ("trend_120m", symbol, round(float(days), 4))
    if not force_refresh:
        cached = _cache_get(cache_key, TREND_CACHE_TTL_SECONDS)
        if cached is not None:
            cached["cache"] = {"hit": True, "ttl_seconds": TREND_CACHE_TTL_SECONDS}
            return cached

    hourly = fetch_gate_xau_klines(symbol, interval="1h", days=days, sleep_seconds=0.02)
    frame_120m = resample_to_120m(hourly)
    result = detect_120m_trend_region(frame_120m)
    result["source"] = "Gate TradFi 1h klines resampled to 120m"
    result["rows_120m"] = int(len(frame_120m))
    if not frame_120m.empty:
        result["start"] = pd.Timestamp(frame_120m["date"].iloc[0]).isoformat()
        result["end"] = pd.Timestamp(frame_120m["date"].iloc[-1]).isoformat()
    result["cache"] = {"hit": False, "ttl_seconds": TREND_CACHE_TTL_SECONDS}
    _cache_set(cache_key, result)
    return result


def build_xau_chart_snapshot(
    *,
    spot_symbol: str = DEFAULT_SPOT_SYMBOL,
    futures_symbol: str = DEFAULT_FUTURES_SYMBOL,
    interval: str = "5m",
    days: float | None = None,
    trend_days: float = 45.0,
    lookback_bars: int | None = None,
    price_step: float = 0.5,
    value_area_pct: float = 0.7,
    max_zones: int = 5,
    mapping_method: str = "additive",
    force_refresh: bool = False,
) -> dict[str, Any]:
    if interval not in CHART_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    effective_days = float(days if days is not None else (2.0 if interval == "1m" else 7.0))
    effective_lookback = int(lookback_bars if lookback_bars is not None else (720 if interval == "1m" else 240))
    cache_key = (
        "xau_snapshot",
        spot_symbol,
        futures_symbol,
        interval,
        round(effective_days, 4),
        round(float(trend_days), 4),
        effective_lookback,
        round(float(price_step), 6),
        round(float(value_area_pct), 6),
        int(max_zones),
        mapping_method,
    )
    def build_live_snapshot() -> dict[str, Any]:
        live_snapshot = build_gc_volume_profile_snapshot(
            spot_symbol=spot_symbol,
            futures_symbol=futures_symbol,
            interval=interval,
            days=effective_days,
            lookback_bars=effective_lookback,
            price_step=price_step,
            value_area_pct=value_area_pct,
            max_zones=max_zones,
            mapping_method=mapping_method,
        )
        live_snapshot["trend_120m"] = fetch_120m_trend_region(
            spot_symbol,
            days=trend_days,
            force_refresh=force_refresh,
        )
        try:
            live_snapshot["panic_volatility"] = fetch_gold_panic_volatility(force_refresh=force_refresh)
        except Exception as exc:
            live_snapshot["panic_volatility"] = {
                "visible": False,
                "symbol": DEFAULT_PANIC_VOL_SYMBOL,
                "name": "Cboe Gold ETF Volatility Index",
                "source": "Yahoo Finance / Cboe GVZ",
                "definition": "30-day implied volatility estimate for GLD options, VIX-style gold fear gauge",
                "error": str(exc),
            }
        return live_snapshot

    cached_entry = None if force_refresh else _cache_lookup(cache_key)
    if cached_entry is not None:
        age_seconds, cached_snapshot = cached_entry
        if age_seconds <= SNAPSHOT_CACHE_TTL_SECONDS:
            should_refresh = age_seconds >= SNAPSHOT_REFRESH_AFTER_SECONDS
            if should_refresh:
                _start_background_refresh(cache_key, build_live_snapshot)
            cached_snapshot["cache"] = {
                "hit": True,
                "refreshing": cache_key in _REFRESHING,
                "age_seconds": float(age_seconds),
                "ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
                "refresh_after_seconds": SNAPSHOT_REFRESH_AFTER_SECONDS,
            }
            return cached_snapshot

    snapshot = build_live_snapshot()
    snapshot["cache"] = {
        "hit": False,
        "refreshing": False,
        "age_seconds": 0.0,
        "ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
        "refresh_after_seconds": SNAPSHOT_REFRESH_AFTER_SECONDS,
    }
    _cache_set(cache_key, snapshot)
    return snapshot
