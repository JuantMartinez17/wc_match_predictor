"""
scripts/check_calibration.py
===========================
Diagnóstico: ¿conviene aplicar calibración por temperatura a las probabilidades
1X2 en producción?

Corre un walk-forward de dixon_coles sobre los Mundiales 2018+2022, ajusta un
`TemperatureScaler` en la primera mitad (≈2018) y lo evalúa OUT-OF-SAMPLE en la
segunda (≈2022). Reporta RPS/Brier/log_loss crudo vs. calibrado.

Conclusión al 2026-06 (config tuneada): T óptimo ≈ 1.0 y la mejora out-of-sample
es ~0.2% (despreciable). El modelo ya está bien calibrado; NO se cablea
calibración en producción. Re-correr este script si crece el dataset o cambia el
modelo, para decidir si en algún momento pasa a valer la pena.

Correr:
    python scripts/check_calibration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from config import DEFAULT_CONFIG  # noqa: E402
from data.ingest import build_dataset  # noqa: E402
from features.elo import EloTracker  # noqa: E402
from prediction.predictor import MatchPredictor  # noqa: E402
from validation.calibration import TemperatureScaler  # noqa: E402
from validation.metrics import evaluate_all  # noqa: E402


def _outcome(h: int, a: int) -> int:
    return 0 if h > a else (1 if h == a else 2)


def walk_forward_probs(model: str = "dixon_coles", years=(2018, 2022)):
    cfg = DEFAULT_CONFIG
    allm = build_dataset(since_year=2006)
    alls = allm.sort_values("date", kind="stable").reset_index(drop=True)
    darr = alls["date"].to_numpy()
    test = alls[
        (alls["competition"] == "world_cup") & (alls["date"].dt.year.isin(years))
    ].reset_index(drop=True)
    empty = pd.DataFrame(columns=["date", "team", "rating"])
    need_tl = cfg.secondary.form_sensitivity > 0

    tr = EloTracker(cfg.elo, cfg.importance)
    cur = 0
    probs, outs = [], []
    for d in sorted(test["date"].unique()):
        ts = pd.Timestamp(d)
        j = int(np.searchsorted(darr, np.datetime64(ts), side="left"))
        if j > cur:
            tr.update(alls.iloc[cur:j])
            cur = j
        if j < 30:
            continue
        tl = tr.timeline() if need_tl else empty
        pred = MatchPredictor(
            alls.iloc[:j], metadata=None, config=cfg,
            elo_state=(tr.snapshot_ratings(), tl),
        )
        for row in test[test["date"] == ts].itertuples(index=False):
            a, b = row.home_team, row.away_team
            neu = bool(row.neutral)
            hm = None if neu else a
            try:
                pr = pred.predict(a, b, str(ts.date()), neutral=neu, home_team=hm,
                                  model=model, use_simulation=False)
            except Exception:
                continue
            probs.append([pr.p_a, pr.p_draw, pr.p_b])
            outs.append(_outcome(int(row.home_goals), int(row.away_goals)))
    return np.array(probs), np.array(outs)


def main() -> None:
    probs, outs = walk_forward_probs()
    n = len(outs)
    print(f"dixon_coles · WC2018+2022 · n={n}")
    print("RAW global:", {k: round(v, 4) for k, v in evaluate_all(probs, outs).items()})

    h = n // 2
    sc = TemperatureScaler().fit(probs[:h], outs[:h])
    raw = evaluate_all(probs[h:], outs[h:])
    cal = evaluate_all(sc.transform(probs[h:]), outs[h:])
    keys = ["log_loss", "brier", "rps", "accuracy"]
    print(f"\nT óptimo (fit 1ª mitad ≈2018) = {sc.temperature:.3f}")
    print("Held-out 2ª mitad  RAW:", {k: round(raw[k], 4) for k in keys})
    print("Held-out 2ª mitad  CAL:", {k: round(cal[k], 4) for k in keys})

    drps = raw["rps"] - cal["rps"]
    verdict = "SÍ conviene" if drps > 0.005 else "NO conviene (mejora despreciable)"
    print(f"\nΔRPS out-of-sample = {drps:+.4f}  ->  {verdict}")


if __name__ == "__main__":
    main()
