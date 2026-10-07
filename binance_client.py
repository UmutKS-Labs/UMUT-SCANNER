from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests


BASE_URL = "https://api.binance.com"
STABLE_BASES = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "TRY"}
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")


class BinancePublicClient:
    """Read-only Binance Spot public REST client. No API key is required."""

    def __init__(self, timeout: int = 12, retries: int = 3) -> None:
        self.timeout = timeout
        self.retries = retries
        self.headers = {"User-Agent": "UMUT-SCANNER/1.0"}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = requests.get(
                    f"{BASE_URL}{path}",
                    params=params,
                    timeout=self.timeout,
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # network / rate-limit / JSON failures
                last_error = exc
                if attempt < self.retries - 1:
                    time.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f"Binance isteği başarısız: {last_error}")

    def get_spot_usdt_symbols(self) -> set[str]:
        data = self._get("/api/v3/exchangeInfo")
        symbols: set[str] = set()
        for item in data.get("symbols", []):
            if item.get("status") != "TRADING":
                continue
            if item.get("quoteAsset") != "USDT":
                continue
            if item.get("isSpotTradingAllowed") is False:
                continue
            base = str(item.get("baseAsset", ""))
            if base in STABLE_BASES:
                continue
            if base.endswith(LEVERAGED_SUFFIXES):
                continue
            symbols.add(item["symbol"])
        return symbols

    def get_24h_tickers(self) -> list[dict[str, Any]]:
        data = self._get("/api/v3/ticker/24hr")
        return data if isinstance(data, list) else []

    def get_ranked_usdt_universe(
        self,
        max_symbols: int = 60,
        min_quote_volume: float = 10_000_000.0,
    ) -> list[dict[str, Any]]:
        tradable = self.get_spot_usdt_symbols()
        tickers = self.get_24h_tickers()
        rows: list[dict[str, Any]] = []
        for item in tickers:
            symbol = item.get("symbol")
            if symbol not in tradable:
                continue
            try:
                quote_volume = float(item.get("quoteVolume", 0.0))
                last_price = float(item.get("lastPrice", 0.0))
                change_pct = float(item.get("priceChangePercent", 0.0))
            except (TypeError, ValueError):
                continue
            if quote_volume < min_quote_volume or last_price <= 0:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "last_price": last_price,
                    "change_pct": change_pct,
                    "quote_volume": quote_volume,
                }
            )
        rows.sort(key=lambda x: x["quote_volume"], reverse=True)
        return rows[:max_symbols]

    def get_klines(self, symbol: str, interval: str, limit: int = 260) -> pd.DataFrame:
        data = self._get(
            "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"{symbol} için mum verisi alınamadı")

        columns = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "taker_base",
            "taker_quote",
            "ignore",
        ]
        frame = pd.DataFrame(data, columns=columns)
        for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
        frame = frame.dropna(subset=["open", "high", "low", "close", "volume"])
        return frame.reset_index(drop=True)
