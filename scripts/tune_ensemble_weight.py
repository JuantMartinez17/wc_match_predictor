"""
scripts/tune_ensemble_weight.py
===============================
Sweep coarse de elo_ensemble_weight sobre el pool 2010-2022 (n grande, estable)
para confirmar que 0.5 (equal-weight, sin tuning) es robusto. NO se fina sobre el
holdout para no sobreajustar: 0.5 se mantiene salvo que esté claramente dominado.
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
    pool = _wc_subset(all_sorted, (2010, 2014, 2018, 2022))
    print(f"POOL 2010-2022 | n={len(pool)}\n")

    for w in (0.0, 0.3, 0.4, 0.5, 0.6, 0.7):
        cfg = dataclasses.replace(
            DEFAULT_CONFIG,
            strength=dataclasses.replace(DEFAULT_CONFIG.strength, elo_ensemble_weight=w),
        )
        m = fast_backtest(all_sorted, dates_arr, pool, cfg)
        print(f"  w={w:.1f} -> RPS={m['rps']:.4f} brier={m['brier']:.4f} logloss={m['log_loss']:.4f} acc={m['accuracy']:.3f}")


if __name__ == "__main__":
    main()
