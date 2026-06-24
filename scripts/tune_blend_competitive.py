"""
scripts/tune_blend_competitive.py
=================================
Sweep acotado de `elo_prior_blend` sobre el set competitivo (eficiente), para
testear si dar MÁS peso al prior de Elo en la mezcla de lambdas mejora la config
de PRODUCCIÓN (ensemble DC+Elo con w=0.5).

Motivación: en el backtest a escala, Elo puro (RPS 0.3429) supera a Dixon-Coles
solo (0.3493) en partidos competitivos -> el prior de Elo podría estar
subponderado (elo_prior_blend=0.50).

Eficiencia: una pasada walk-forward por valor de blend (reusa collect_probs_fast
de backtest_all). Acotado a 2016+ (poder de sobra, ~mitad del costo del set full).
El ensemble (w=0.5) se evalúa post-hoc en cada pasada.

Correr (desde la raíz del repo):
    python scripts/tune_blend_competitive.py [since_year]
"""

from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DEFAULT_CONFIG  # noqa: E402
from data.ingest import build_dataset  # noqa: E402
from scripts.backtest_all import _COMPETITIVE, _blend, _report, collect_probs_fast  # noqa: E402

_W = 0.5  # peso del ensemble en producción


def main() -> None:
    since = int(sys.argv[1]) if len(sys.argv) > 1 else 2016
    df = build_dataset(since_year=2006).sort_values("date", kind="stable").reset_index(drop=True)
    test = df[
        df["competition"].isin(_COMPETITIVE) & (df["date"].dt.year >= since)
    ].reset_index(drop=True)
    print(f"Test: competitivos desde {since} | {len(test)} partidos | {test['date'].nunique()} fechas\n")

    results = []
    for blend in (0.50, 0.65, 0.80):
        cfg = dataclasses.replace(
            DEFAULT_CONFIG,
            strength=dataclasses.replace(DEFAULT_CONFIG.strength, elo_prior_blend=blend),
        )
        t0 = time.time()
        arrs, outs = collect_probs_fast(df, test, cfg)
        ens = _blend(arrs["dixon_coles"], arrs["elo_pure"], _W)
        print(f"--- elo_prior_blend={blend:.2f}  (n={len(outs)}, {time.time() - t0:.0f}s) ---")
        _report("  DC solo", arrs["dixon_coles"], outs)
        m = _report(f"  DC+elo(w={_W})", ens, outs)
        results.append((blend, m["rps"], m["accuracy"]))

    print("\n=== Resumen (ensemble de producción) ===")
    for blend, rps, acc in results:
        print(f"  elo_prior_blend={blend:.2f} -> RPS={rps:.4f} acc={acc:.3f}")
    base = next(r[1] for r in results if r[0] == 0.50)
    best = min(results, key=lambda r: r[1])
    print(f"\n  Actual (0.50): RPS={base:.4f} | Mejor: blend={best[0]:.2f} RPS={best[1]:.4f}")
    delta = best[1] - base
    print(f"  Delta={delta:+.4f}. {'ADOPTAR ' + format(best[0], '.2f') if delta < -0.001 else 'MANTENER 0.50 (mejora trivial o nula)'}")


if __name__ == "__main__":
    main()
