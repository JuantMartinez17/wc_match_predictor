"""
scripts/tune_fatigue.py
=======================
Sweep AISLADO de `fatigue_sensitivity` (Fase 2) sobre los defaults adoptados.

A diferencia de la selección greedy de tune_wc.py, acá se fija todo en
DEFAULT_CONFIG y solo se varía la fatiga, reportando tune (WC 2014+2018) y
holdout (WC 2022) por valor. Así se aísla el efecto de la fatiga sin arrastrar
otros parámetros sobreajustados.

Decisión: adoptar fatigue_sensitivity>0 SOLO si su holdout RPS < el de 0.00.

Correr (desde la raíz del repo):
    python scripts/tune_fatigue.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.tune_wc import _make_cfg, _wc_subset, fast_backtest  # noqa: E402
from data.ingest import build_dataset  # noqa: E402


def main() -> None:
    print("Cargando dataset (desde 2006)...")
    all_matches = build_dataset(since_year=2006)
    all_sorted = all_matches.sort_values("date", kind="stable").reset_index(drop=True)
    dates_arr = all_sorted["date"].to_numpy()

    tune = _wc_subset(all_sorted, (2014, 2018))
    hold = _wc_subset(all_sorted, (2022,))
    print(f"Tune: {len(tune)} (WC 2014+2018) | Holdout: {len(hold)} (WC 2022)\n")
    print("=== Sweep fatigue_sensitivity (resto en defaults) ===")

    rows = []
    for fs in (0.0, 0.05, 0.10, 0.15, 0.20):
        cfg = _make_cfg(fatigue_sensitivity=fs)
        t = fast_backtest(all_sorted, dates_arr, tune, cfg)
        h = fast_backtest(all_sorted, dates_arr, hold, cfg)
        rows.append((fs, t["rps"], h["rps"], h["brier"], h["accuracy"]))
        print(
            f"  fatigue={fs:.2f} -> tune RPS={t['rps']:.4f} | "
            f"holdout RPS={h['rps']:.4f} brier={h['brier']:.4f} acc={h['accuracy']:.3f}"
        )

    base_hold = next(r[2] for r in rows if r[0] == 0.0)
    best = min((r for r in rows if r[0] > 0.0), key=lambda r: r[2])
    print("\n" + "=" * 60)
    print(f"  Holdout fatigue=0.00: RPS={base_hold:.4f}")
    print(f"  Mejor fatigue>0:      fatigue={best[0]:.2f} holdout RPS={best[2]:.4f}")
    better = best[2] < base_hold
    print(
        f"  DECISIÓN: {'ADOPTAR fatigue=%.2f (holdout mejora)' % best[0] if better else 'NO adoptar (holdout no mejora)'}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
