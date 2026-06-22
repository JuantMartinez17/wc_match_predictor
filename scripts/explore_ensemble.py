"""
scripts/explore_ensemble.py
===========================
Explora ENSEMBLES de modelos (palanca del núcleo, validable por backtest).

Recolecta las probabilidades 1X2 de cada modelo (poisson_simple,
bivariate_poisson, dixon_coles, elo_pure) en un walk-forward incremental sobre
tune (WC 2014+2018) y holdout (WC 2022), y evalúa modelos individuales vs.
blends (promedios de probabilidad, renormalizados). Busca reducir varianza →
mejor RPS. Adoptar un blend SOLO si mejora el holdout vs. el mejor individual.

Correr (desde la raíz del repo):
    python scripts/explore_ensemble.py
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
from models.elo_model import EloBaseline  # noqa: E402
from prediction.predictor import MatchPredictor  # noqa: E402
from validation.metrics import evaluate_all  # noqa: E402
from scripts.tune_wc import _outcome, _wc_subset  # noqa: E402

MODELS = ("poisson_simple", "bivariate_poisson", "dixon_coles")


def collect_probs(all_sorted, dates_arr, test, config):
    """Walk-forward incremental: probs 1X2 por modelo + elo_pure y outcomes."""
    tracker = EloTracker(config.elo, config.importance)
    elo_base = EloBaseline(config.elo)
    need_tl = config.secondary.form_sensitivity > 0
    empty_tl = pd.DataFrame(columns=["date", "team", "rating"])
    cursor = 0
    out = {m: [] for m in MODELS}
    out["elo_pure"] = []
    outs: list[int] = []

    for d in sorted(test["date"].unique()):
        ref_ts = pd.Timestamp(d)
        j = int(np.searchsorted(dates_arr, np.datetime64(ref_ts), side="left"))
        if j > cursor:
            tracker.update(all_sorted.iloc[cursor:j])
            cursor = j
        if j < 30:
            continue
        train = all_sorted.iloc[:j]
        tl = tracker.timeline() if need_tl else empty_tl
        try:
            predictor = MatchPredictor(
                train, metadata=None, config=config,
                elo_state=(tracker.snapshot_ratings(), tl),
            )
        except Exception:
            continue
        ref = str(ref_ts.date())
        for row in test[test["date"] == ref_ts].itertuples(index=False):
            a, b = row.home_team, row.away_team
            neutral = bool(row.neutral)
            home = None if neutral else a
            perrow = {}
            ok = True
            for m in MODELS:
                try:
                    pr = predictor.predict(
                        a, b, ref, neutral=neutral, home_team=home,
                        model=m, use_simulation=False,
                    )
                    perrow[m] = [pr.p_a, pr.p_draw, pr.p_b]
                except Exception:
                    ok = False
                    break
            if not ok:
                continue
            ra = predictor.ratings.get(a, config.elo.base_rating)
            rb = predictor.ratings.get(b, config.elo.base_rating)
            elo_p = elo_base.predict_1x2(
                ra, rb, neutral=neutral, home_team=home, team_a=a
            )
            for m in MODELS:
                out[m].append(perrow[m])
            out["elo_pure"].append(list(elo_p))
            outs.append(_outcome(int(row.home_goals), int(row.away_goals)))

    arrs = {k: np.array(v, dtype=float) for k, v in out.items()}
    return arrs, np.array(outs, dtype=int)


def _blend(arrs, names, weights=None):
    """Promedio (ponderado) de probs y renormalización."""
    ws = weights or [1.0] * len(names)
    stacked = sum(w * arrs[n] for w, n in zip(ws, names))
    stacked = stacked / np.sum(ws)
    return stacked / stacked.sum(axis=1, keepdims=True)


def _report(label, arr, outs):
    m = evaluate_all(arr, outs)
    print(
        f"  {label:28s} RPS={m['rps']:.4f} brier={m['brier']:.4f} "
        f"logloss={m['log_loss']:.4f} acc={m['accuracy']:.3f}"
    )
    return m["rps"]


def main() -> None:
    print("Cargando dataset (desde 2006)...")
    all_matches = build_dataset(since_year=2006)
    all_sorted = all_matches.sort_values("date", kind="stable").reset_index(drop=True)
    dates_arr = all_sorted["date"].to_numpy()

    sets = (
        ("TUNE (2014+2018)", (2014, 2018)),
        ("HOLDOUT (2022)", (2022,)),
        ("WC POOLED (2010-2022)", (2010, 2014, 2018, 2022)),
    )
    for label, years in sets:
        test = _wc_subset(all_sorted, years)
        arrs, outs = collect_probs(all_sorted, dates_arr, test, DEFAULT_CONFIG)
        print(f"\n=== {label} | n={len(outs)} ===")
        print("  -- individuales --")
        for m in (*MODELS, "elo_pure"):
            _report(m, arrs[m], outs)
        print("  -- ensembles --")
        _report("DC+BP", _blend(arrs, ["dixon_coles", "bivariate_poisson"]), outs)
        _report("DC+elo", _blend(arrs, ["dixon_coles", "elo_pure"]), outs)
        _report("DC+BP+simple", _blend(arrs, list(MODELS)), outs)
        _report("DC+BP+elo", _blend(arrs, ["dixon_coles", "bivariate_poisson", "elo_pure"]), outs)
        _report("DC*2+elo", _blend(arrs, ["dixon_coles", "elo_pure"], [2.0, 1.0]), outs)
        _report("all4", _blend(arrs, [*MODELS, "elo_pure"]), outs)


if __name__ == "__main__":
    main()
