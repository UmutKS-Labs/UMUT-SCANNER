import unittest

import numpy as np
import pandas as pd

from scanner_engine import RiskSettings, build_risk_plan, score_market


class ScoreMarketTests(unittest.TestCase):
    @staticmethod
    def make_frame(rows: int = 260, drift: float = 0.25) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        base = 100 + np.arange(rows) * drift
        noise = rng.normal(0, 0.35, rows)
        close = base + noise
        open_ = close + rng.normal(0, 0.2, rows)
        high = np.maximum(open_, close) + rng.uniform(0.2, 0.8, rows)
        low = np.minimum(open_, close) - rng.uniform(0.2, 0.8, rows)
        volume = 1_000_000 + np.arange(rows) * 2_000 + rng.normal(0, 50_000, rows)
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.maximum(volume, 10_000),
            }
        )

    def test_scores_stay_in_range(self) -> None:
        frame = self.make_frame()
        result = score_market(frame, frame.copy())
        for key in ["trend_score", "setup_score", "entry_score", "general_score", "mtf_score"]:
            self.assertGreaterEqual(float(result[key]), 0.0)
            self.assertLessEqual(float(result[key]), 100.0)

    def test_signal_is_known_value(self) -> None:
        frame = self.make_frame()
        result = score_market(frame, frame.copy())
        self.assertIn(result["signal"], {"GÜÇLÜ AL", "AL", "NÖTR", "SAT", "GÜÇLÜ SAT"})

    def test_stop_is_below_entry_when_available(self) -> None:
        frame = self.make_frame()
        result = score_market(frame, frame.copy())
        self.assertGreater(float(result["stop_price"]), 0.0)
        self.assertLess(float(result["stop_price"]), float(frame["close"].iloc[-1]))
        self.assertGreater(float(result["stop_distance_pct"]), 0.0)

    def test_risk_plan_respects_position_cap(self) -> None:
        settings = RiskSettings(
            account_balance=1000.0,
            risk_per_trade_pct=0.5,
            max_position_pct=20.0,
            max_stop_pct=5.0,
        )
        plan = build_risk_plan(entry_price=100.0, stop_price=98.0, settings=settings)
        self.assertTrue(plan["risk_ok"])
        self.assertLessEqual(float(plan["position_usdt"]), 200.0)
        self.assertLessEqual(float(plan["risk_at_stop_usdt"]), 5.0)

    def test_risk_plan_rejects_wide_stop(self) -> None:
        settings = RiskSettings(
            account_balance=1000.0,
            risk_per_trade_pct=0.5,
            max_position_pct=20.0,
            max_stop_pct=5.0,
        )
        plan = build_risk_plan(entry_price=100.0, stop_price=90.0, settings=settings)
        self.assertFalse(plan["risk_ok"])
        self.assertIn("STOP", str(plan["risk_reason"]))

    def test_requires_enough_history(self) -> None:
        frame = self.make_frame(rows=100)
        with self.assertRaises(ValueError):
            score_market(frame, frame.copy())


if __name__ == "__main__":
    unittest.main()
