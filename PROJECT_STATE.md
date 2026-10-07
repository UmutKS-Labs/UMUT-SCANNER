# UMUT Scanner — Current State

## Status

V1 desktop scanner is operational and Windows EXE build pipeline is green.

## Architecture

1. `binance_client.py` — read-only Binance Spot public market data
2. `scanner_engine.py` — technical indicators, market structure and scoring
3. `app.py` — Windows desktop GUI
4. `tests/` — offline scoring smoke tests
5. `.github/workflows/build-windows.yml` — automatic Windows EXE build

## V1 scoring core

- EMA 20 / 50 / 200
- ADX + DI
- RSI
- MACD histogram
- ROC
- RVOL
- ATR
- confirmed swing structure
- Bollinger squeeze bonus
- higher-timeframe confirmation

Outputs:

- Trend Score
- Setup Score
- Entry Score
- General Score
- Signal
- Regime
- Warning

## Safety boundary

- No Binance API key
- No account access
- No order placement
- Public market-data scanner only

## Next logical upgrades

- Per-symbol detail window with Entry / SL / TP plan
- Watchlist / favorites
- Desktop notifications for new strong candidates
- CSV export
- Additional Binance Alpha data layer where technically available
- Optional authenticated trading layer only as a separate module
