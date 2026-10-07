from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Event
from typing import Callable

import numpy as np
import pandas as pd

from binance_client import BinancePublicClient


HIGHER_TF = {
    "15m": "1h",
    "1h": "4h",
    "4h": "1d",
    "1d": "1w",
}


@dataclass(frozen=True)
class RiskSettings:
    account_balance: float = 1000.0
    risk_per_trade_pct: float = 0.5
    max_position_pct: float = 20.0
    max_stop_pct: float = 5.0


@dataclass
class ScanResult:
    symbol: str
    price: float
    change_pct: float
    quote_volume: float
    trend_score: float
    setup_score: float
    entry_score: float
    general_score: float
    adx: float
    rsi: float
    rvol: float
    structure: str
    mtf_score: float
    regime: str
    signal: str
    warning: str
    atr: float
    stop_price: float
    stop_distance_pct: float
    risk_budget_usdt: float
    position_usdt: float
    position_pct: float
    risk_at_stop_usdt: float
    technical_ok: bool
    risk_ok: bool
    trade_permission: str
    reject_reason: str


def clamp(value: float) -> float:
    return float(max(0.0, min(100.0, value)))


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out.fillna(50.0)


def atr_adx(frame: pd.DataFrame, length: int = 14) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=frame.index)

    plus_sm = plus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    minus_sm = minus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

    plus_di = 100.0 * plus_sm / atr.replace(0, np.nan)
    minus_di = 100.0 * minus_sm / atr.replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    return atr.fillna(0.0), adx.fillna(0.0), plus_di.fillna(0.0), minus_di.fillna(0.0)


def confirmed_swings(frame: pd.DataFrame, window: int = 5) -> tuple[list[float], list[float]]:
    highs = frame["high"].to_numpy(dtype=float)
    lows = frame["low"].to_numpy(dtype=float)
    swing_highs: list[float] = []
    swing_lows: list[float] = []
    if len(frame) < window * 2 + 1:
        return swing_highs, swing_lows

    for i in range(window, len(frame) - window):
        high_slice = highs[i - window : i + window + 1]
        low_slice = lows[i - window : i + window + 1]
        if highs[i] >= np.max(high_slice):
            swing_highs.append(float(highs[i]))
        if lows[i] <= np.min(low_slice):
            swing_lows.append(float(lows[i]))
    return swing_highs, swing_lows


def calculate_stop(entry_price: float, atr_now: float, last_support: float | None) -> tuple[float, float]:
    """Long/spot için ATR + teyitli destek tabanlı teknik stop önerisi."""
    if entry_price <= 0 or atr_now <= 0:
        return 0.0, 0.0

    atr_stop = entry_price - 1.5 * atr_now
    stop = atr_stop

    if last_support is not None and np.isfinite(last_support) and 0 < last_support < entry_price:
        support_distance_pct = (entry_price - float(last_support)) / entry_price * 100.0
        if support_distance_pct <= 8.0:
            structure_stop = float(last_support) - 0.20 * atr_now
            stop = min(atr_stop, structure_stop)

    stop = max(0.0, stop)
    distance_pct = ((entry_price - stop) / entry_price * 100.0) if stop < entry_price else 0.0
    return float(stop), float(distance_pct)


def build_risk_plan(entry_price: float, stop_price: float, settings: RiskSettings) -> dict[str, float | bool | str]:
    balance = max(0.0, float(settings.account_balance))
    risk_pct = max(0.0, float(settings.risk_per_trade_pct))
    max_position_pct = max(0.0, min(100.0, float(settings.max_position_pct)))
    max_stop_pct = max(0.0, float(settings.max_stop_pct))

    if entry_price <= 0 or stop_price <= 0 or stop_price >= entry_price:
        return {
            "risk_budget_usdt": 0.0,
            "position_usdt": 0.0,
            "position_pct": 0.0,
            "risk_at_stop_usdt": 0.0,
            "risk_ok": False,
            "risk_reason": "STOP HESAPLANAMADI",
        }

    stop_fraction = (entry_price - stop_price) / entry_price
    stop_pct = stop_fraction * 100.0
    risk_budget = balance * risk_pct / 100.0
    raw_position = risk_budget / stop_fraction if stop_fraction > 0 else 0.0
    max_position_usdt = balance * max_position_pct / 100.0
    position_usdt = min(raw_position, max_position_usdt, balance)
    position_pct = (position_usdt / balance * 100.0) if balance > 0 else 0.0
    risk_at_stop = position_usdt * stop_fraction

    risk_ok = balance > 0 and risk_budget > 0 and position_usdt > 0 and 0 < stop_pct <= max_stop_pct
    if balance <= 0:
        reason = "BAKİYE GİR"
    elif risk_budget <= 0:
        reason = "RİSK % GİR"
    elif stop_pct > max_stop_pct:
        reason = f"STOP %{stop_pct:.2f} > LİMİT %{max_stop_pct:.2f}"
    elif stop_pct <= 0:
        reason = "STOP GEÇERSİZ"
    elif position_usdt <= 0:
        reason = "POZİSYON HESAPLANAMADI"
    else:
        reason = "UYGUN"

    return {
        "risk_budget_usdt": float(risk_budget),
        "position_usdt": float(position_usdt),
        "position_pct": float(position_pct),
        "risk_at_stop_usdt": float(risk_at_stop),
        "risk_ok": bool(risk_ok),
        "risk_reason": reason,
    }


def score_market(frame: pd.DataFrame, mtf_frame: pd.DataFrame) -> dict[str, float | str | bool]:
    if len(frame) < 210 or len(mtf_frame) < 210:
        raise ValueError("Skor için en az 210 mum gerekir")

    close = frame["close"]
    volume = frame["volume"]
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    rsi_series = rsi(close, 14)

    macd_line = ema(close, 12) - ema(close, 26)
    macd_signal = ema(macd_line, 9)
    macd_hist = macd_line - macd_signal
    roc = close.pct_change(10) * 100.0
    atr, adx, plus_di, minus_di = atr_adx(frame, 14)

    volume_ma = volume.rolling(20, min_periods=20).mean()
    rvol_series = volume / volume_ma.replace(0, np.nan)

    last_close = float(close.iloc[-1])
    e20 = float(ema20.iloc[-1])
    e50 = float(ema50.iloc[-1])
    e200 = float(ema200.iloc[-1])
    rsi_now = float(rsi_series.iloc[-1])
    adx_now = float(adx.iloc[-1])
    plus_now = float(plus_di.iloc[-1])
    minus_now = float(minus_di.iloc[-1])
    atr_now = float(atr.iloc[-1])
    rvol = float(rvol_series.iloc[-1]) if pd.notna(rvol_series.iloc[-1]) else 1.0
    roc_now = float(roc.iloc[-1]) if pd.notna(roc.iloc[-1]) else 0.0
    hist_now = float(macd_hist.iloc[-1]) if pd.notna(macd_hist.iloc[-1]) else 0.0
    hist_prev = float(macd_hist.iloc[-2]) if pd.notna(macd_hist.iloc[-2]) else 0.0

    trend = 50.0
    trend += 15.0 if last_close > e200 else -15.0
    if e20 > e50 > e200:
        trend += 20.0
    elif e20 < e50 < e200:
        trend -= 20.0
    trend += 10.0 if ema20.iloc[-1] > ema20.iloc[-6] else -10.0
    trend += 5.0 if ema50.iloc[-1] > ema50.iloc[-6] else -5.0
    trend = clamp(trend)

    momentum = 50.0
    if 55 <= rsi_now <= 70:
        momentum += 15.0
    elif 70 < rsi_now <= 75:
        momentum += 5.0
    elif rsi_now < 45:
        momentum -= 15.0

    if hist_now > 0 and hist_now > hist_prev:
        momentum += 15.0
    elif hist_now > 0:
        momentum += 8.0
    elif hist_now < 0 and hist_now < hist_prev:
        momentum -= 15.0
    else:
        momentum -= 8.0
    momentum += 10.0 if roc_now > 0 else -10.0
    momentum = clamp(momentum)

    up_bar = close.iloc[-1] >= close.iloc[-2]
    volume_score = 50.0
    if rvol >= 1.5:
        volume_score += 35.0 if up_bar else -30.0
    elif rvol >= 1.2:
        volume_score += 25.0 if up_bar else -20.0
    elif rvol >= 1.0:
        volume_score += 10.0
    elif rvol < 0.7:
        volume_score -= 20.0
    volume_score = clamp(volume_score)

    swing_highs, swing_lows = confirmed_swings(frame, 5)
    bull_structure = len(swing_highs) >= 2 and len(swing_lows) >= 2 and swing_highs[-1] > swing_highs[-2] and swing_lows[-1] > swing_lows[-2]
    bear_structure = len(swing_highs) >= 2 and len(swing_lows) >= 2 and swing_highs[-1] < swing_highs[-2] and swing_lows[-1] < swing_lows[-2]
    last_resistance = swing_highs[-1] if swing_highs else np.nan
    last_support = swing_lows[-1] if swing_lows else np.nan
    breakout = np.isfinite(last_resistance) and last_close > float(last_resistance)
    breakdown = np.isfinite(last_support) and last_close < float(last_support)

    structure_score = 85.0 if bull_structure else 15.0 if bear_structure else 60.0 if last_close > e50 else 40.0
    if breakout:
        structure_score += 10.0
    if breakdown:
        structure_score -= 10.0
    structure_score = clamp(structure_score)
    structure = "HH/HL" if bull_structure else "LH/LL" if bear_structure else "KARMA"

    mtf_close = mtf_frame["close"]
    confirmed_mtf = mtf_close.iloc[:-1] if len(mtf_close) > 210 else mtf_close
    mtf_e20_series = ema(confirmed_mtf, 20)
    mtf_e50_series = ema(confirmed_mtf, 50)
    mtf_e200_series = ema(confirmed_mtf, 200)
    mtf_last = float(confirmed_mtf.iloc[-1])
    mtf_e20 = float(mtf_e20_series.iloc[-1])
    mtf_e50 = float(mtf_e50_series.iloc[-1])
    mtf_e200 = float(mtf_e200_series.iloc[-1])
    if mtf_last > mtf_e200 and mtf_e20 > mtf_e50:
        mtf_score = 80.0
    elif mtf_last < mtf_e200 and mtf_e20 < mtf_e50:
        mtf_score = 20.0
    else:
        mtf_score = 50.0

    basis = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    upper = basis + 2.0 * std
    lower = basis - 2.0 * std
    width = ((upper - lower) / basis.replace(0, np.nan)) * 100.0
    width_avg = width.rolling(50, min_periods=20).mean()
    squeeze = pd.notna(width.iloc[-1]) and pd.notna(width_avg.iloc[-1]) and width.iloc[-1] < width_avg.iloc[-1] * 0.80

    setup = trend * 0.30 + momentum * 0.25 + structure_score * 0.25 + volume_score * 0.20
    if squeeze and trend >= 60:
        setup += 5.0
    if breakout and rvol >= 1.2:
        setup += 8.0
    setup = clamp(setup)

    entry = 50.0
    if trend >= 70:
        entry += 15.0
    elif trend < 45:
        entry -= 15.0

    if adx_now >= 25 and plus_now > minus_now:
        entry += 15.0
    elif adx_now >= 20 and plus_now > minus_now:
        entry += 10.0
    elif adx_now >= 25 and minus_now > plus_now:
        entry -= 15.0
    elif adx_now < 15:
        entry -= 15.0

    if rvol >= 1.2:
        entry += 15.0
    elif rvol >= 1.0:
        entry += 8.0
    elif rvol < 0.7:
        entry -= 15.0

    if 52 <= rsi_now <= 68:
        entry += 10.0
    elif rsi_now > 75:
        entry -= 10.0

    distance_atr = abs(last_close - e20) / atr_now if atr_now > 0 else 0.0
    if distance_atr <= 1.0:
        entry += 10.0
    elif distance_atr > 2.5:
        entry -= 20.0

    if breakout and rvol >= 1.2:
        entry += 10.0
    entry = clamp(entry)

    general = clamp(trend * 0.35 + setup * 0.30 + entry * 0.25 + mtf_score * 0.10)

    if general >= 80 and trend >= 70 and setup >= 75 and entry >= 65:
        signal = "GÜÇLÜ AL"
    elif general >= 70 and trend >= 60 and setup >= 65:
        signal = "AL"
    elif general <= 25 and trend <= 30:
        signal = "GÜÇLÜ SAT"
    elif general <= 40 and trend <= 45:
        signal = "SAT"
    else:
        signal = "NÖTR"

    if trend >= 80 and adx_now >= 25:
        regime = "GÜÇLÜ YÜKSELİŞ"
    elif trend >= 65:
        regime = "YÜKSELİŞ"
    elif trend <= 20 and adx_now >= 25:
        regime = "GÜÇLÜ DÜŞÜŞ"
    elif trend <= 35:
        regime = "DÜŞÜŞ"
    else:
        regime = "YATAY / GEÇİŞ"

    if distance_atr > 2.5:
        warning = "KOVALAMA RİSKİ"
    elif rvol < 0.7:
        warning = "DÜŞÜK HACİM"
    elif adx_now < 15:
        warning = "ZAYIF TREND"
    else:
        warning = "NORMAL"

    stop_price, stop_distance_pct = calculate_stop(
        last_close,
        atr_now,
        float(last_support) if np.isfinite(last_support) else None,
    )

    technical_ok = (
        trend >= 70
        and setup >= 70
        and entry >= 65
        and general >= 72
        and adx_now >= 20
        and rvol >= 1.0
        and mtf_score >= 50
        and signal in {"AL", "GÜÇLÜ AL"}
        and warning != "KOVALAMA RİSKİ"
    )

    technical_reasons: list[str] = []
    if trend < 70:
        technical_reasons.append("TREND<70")
    if setup < 70:
        technical_reasons.append("SETUP<70")
    if entry < 65:
        technical_reasons.append("ENTRY<65")
    if general < 72:
        technical_reasons.append("GENEL<72")
    if adx_now < 20:
        technical_reasons.append("ADX<20")
    if rvol < 1.0:
        technical_reasons.append("RVOL<1")
    if mtf_score < 50:
        technical_reasons.append("MTF ZAYIF")
    if signal not in {"AL", "GÜÇLÜ AL"}:
        technical_reasons.append("SİNYAL YETERSİZ")
    if warning == "KOVALAMA RİSKİ":
        technical_reasons.append("GİRİŞ UZAK")

    return {
        "trend_score": trend,
        "setup_score": setup,
        "entry_score": entry,
        "general_score": general,
        "adx": adx_now,
        "rsi": rsi_now,
        "rvol": rvol,
        "structure": structure,
        "mtf_score": mtf_score,
        "regime": regime,
        "signal": signal,
        "warning": warning,
        "atr": atr_now,
        "stop_price": stop_price,
        "stop_distance_pct": stop_distance_pct,
        "technical_ok": technical_ok,
        "technical_reason": "UYGUN" if technical_ok else ", ".join(technical_reasons),
    }


class UmutScanner:
    def __init__(self, client: BinancePublicClient | None = None, workers: int = 6) -> None:
        self.client = client or BinancePublicClient()
        self.workers = max(1, min(workers, 10))

    def _scan_one(self, ticker: dict, interval: str, risk_settings: RiskSettings) -> ScanResult:
        symbol = str(ticker["symbol"])
        higher_tf = HIGHER_TF.get(interval, "4h")
        frame = self.client.get_klines(symbol, interval, 260)
        mtf_frame = self.client.get_klines(symbol, higher_tf, 260)
        scored = score_market(frame, mtf_frame)

        risk = build_risk_plan(
            entry_price=float(ticker["last_price"]),
            stop_price=float(scored["stop_price"]),
            settings=risk_settings,
        )
        technical_ok = bool(scored["technical_ok"])
        risk_ok = bool(risk["risk_ok"])
        permission = "İZİN" if technical_ok and risk_ok else "RET"

        reject_reasons: list[str] = []
        if not technical_ok:
            reject_reasons.append(str(scored["technical_reason"]))
        if not risk_ok:
            reject_reasons.append(str(risk["risk_reason"]))
        reject_reason = "UYGUN" if permission == "İZİN" else " | ".join(reject_reasons)

        return ScanResult(
            symbol=symbol,
            price=float(ticker["last_price"]),
            change_pct=float(ticker["change_pct"]),
            quote_volume=float(ticker["quote_volume"]),
            trend_score=float(scored["trend_score"]),
            setup_score=float(scored["setup_score"]),
            entry_score=float(scored["entry_score"]),
            general_score=float(scored["general_score"]),
            adx=float(scored["adx"]),
            rsi=float(scored["rsi"]),
            rvol=float(scored["rvol"]),
            structure=str(scored["structure"]),
            mtf_score=float(scored["mtf_score"]),
            regime=str(scored["regime"]),
            signal=str(scored["signal"]),
            warning=str(scored["warning"]),
            atr=float(scored["atr"]),
            stop_price=float(scored["stop_price"]),
            stop_distance_pct=float(scored["stop_distance_pct"]),
            risk_budget_usdt=float(risk["risk_budget_usdt"]),
            position_usdt=float(risk["position_usdt"]),
            position_pct=float(risk["position_pct"]),
            risk_at_stop_usdt=float(risk["risk_at_stop_usdt"]),
            technical_ok=technical_ok,
            risk_ok=risk_ok,
            trade_permission=permission,
            reject_reason=reject_reason,
        )

    def scan(
        self,
        interval: str = "1h",
        max_symbols: int = 60,
        min_quote_volume: float = 10_000_000.0,
        min_score: float = 0.0,
        risk_settings: RiskSettings | None = None,
        progress: Callable[[int, int, str, ScanResult | None, str | None], None] | None = None,
        cancel_event: Event | None = None,
    ) -> tuple[list[ScanResult], int]:
        settings = risk_settings or RiskSettings()
        universe = self.client.get_ranked_usdt_universe(max_symbols, min_quote_volume)
        total = len(universe)
        if total == 0:
            return [], 0

        results: list[ScanResult] = []
        errors = 0
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(self._scan_one, ticker, interval, settings): ticker["symbol"]
                for ticker in universe
            }
            done = 0
            for future in as_completed(futures):
                if cancel_event is not None and cancel_event.is_set():
                    for pending in futures:
                        pending.cancel()
                    break

                symbol = str(futures[future])
                result: ScanResult | None = None
                error_text: str | None = None
                try:
                    candidate = future.result()
                    if candidate.general_score >= min_score:
                        result = candidate
                        results.append(candidate)
                except Exception as exc:
                    errors += 1
                    error_text = str(exc)
                done += 1
                if progress is not None:
                    progress(done, total, symbol, result, error_text)

        results.sort(
            key=lambda x: (x.trade_permission == "İZİN", x.general_score, x.entry_score),
            reverse=True,
        )
        return results, errors
