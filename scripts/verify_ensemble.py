"""
scripts/verify_ensemble.py
==========================
Verifica que el ensemble Elo implementado en el predictor (elo_ensemble_weight)
reproduce los números del experimento y cuantifica el antes/después de adoptarlo.

Compara, sobre holdout 2022 y pool 2010-2022:
  - weight=0.5 (DEFAULT_CONFIG, ya adoptado)  vs  weight=0.0 (modelo solo).
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DEFAULT_CONFIG  # noqa: E402
from data.ingest import build_dataset  # noqa: E402
from scripts.tune_wc import _wc_subset, fast_backtest  # noqa: E402


def main() -> None:
    all_matches = build_dataset(since_year=2006)
    all_sorted = all_matches.sort_values("date", kind="stable").reset_index(drop=True)
    dates_arr = all_sorted["date"].to_numpy()

    cfg_off = dataclasses.replace(
        DEFAULT_CONFIG,
        strength=dataclasses.replace(DEFAULT_CONFIG.strength, elo_ensemble_weight=0.0),
    )

    for label, years in (("HOLDOUT 2022", (2022,)), ("POOL 2010-2022", (2010, 2014, 2018, 2022))):
        test = _wc_subset(all_sorted, years)
        on = fast_backtest(all_sorted, dates_arr, test, DEFAULT_CONFIG)
        off = fast_backtest(all_sorted, dates_arr, test, cfg_off)
        print(f"\n=== {label} | n={on['n']} ===")
        print(f"  OFF (DC solo, w=0.0): RPS={off['rps']:.4f} acc={off['accuracy']:.3f} logloss={off['log_loss']:.4f}")
        print(f"  ON  (DC+elo, w=0.5):  RPS={on['rps']:.4f} acc={on['accuracy']:.3f} logloss={on['log_loss']:.4f}")
        print(f"  delta RPS={on['rps'] - off['rps']:+.4f} (negativo = mejora)")


if __name__ == "__main__":
    main()
