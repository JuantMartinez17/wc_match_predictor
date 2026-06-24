"""
scripts/backtest_all.py
=======================
Backtest walk-forward sobre TODOS los partidos competitivos (no solo Mundiales),
para ganar poder estadístico: ~5100 partidos vs ~250 del pool de Mundiales.

Eficiencia (clave por límites de servidor):
  - UN solo MatchPredictor reutilizado sobre el historial completo; el Elo
    as-of-fecha se inyecta por día (EloTracker incremental). Evita reconstruir el
    predictor, re-validar el DataFrame y recomputar el Elo histórico en cada fecha.
  - El GLM se cachea por fecha (1 fit por fecha, costo dominante e irreducible).
  - UNA sola pasada recolecta las probs de cada modelo + Elo puro; los ensembles
    y el sweep de peso se evalúan post-hoc (sin pasadas extra).

Correr (desde la raíz del repo):
    python scripts/backtest_all.py [since_year]
"""

from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from config import DEFAULT_CONFIG, Config  # noqa: E402
from data.ingest import build_dataset  # noqa: E402
from features.elo import EloTracker  # noqa: E402
from models.elo_model import EloBaseline  # noqa: E402
from prediction.predictor import MatchPredictor  # noqa: E402
from validation.metrics import evaluate_all  # noqa: E402

_COMPETITIVE = ("world_cup", "continental_cup", "qualifier", "nations_league")
_MODELS = ("dixon_coles", "poisson_simple")


def _outcome(hg: int, ag: int) -> int:
    return 0 if hg > ag else (1 if hg == ag else 2)


def collect_probs_fast(history: pd.DataFrame, test: pd.DataFrame, config: Config) -> tuple[dict, np.ndarray]:
    """
    Una pasada walk-forward eficiente. Recolecta probs PURAS (sin ensemble) de
    cada modelo de _MODELS y de Elo puro, más los resultados. El blend con Elo se
    hace post-hoc, así que se colecta con elo_ensemble_weight=0.

    Reutiliza un único predictor: self.matches = historial completo (el fit del
    GLM filtra siempre a [ref-ventana, ref), sin fuga), y self.ratings se sobre-
    escribe con el snapshot Elo as-of-fecha por día.
    """
    dates_arr = history["date"].to_numpy()
    empty_tl = pd.DataFrame(columns=["date", "team", "rating"])

    cfg0 = dataclasses.replace(
        config, strength=dataclasses.replace(config.strength, elo_ensemble_weight=0.0)
    )
    predictor = MatchPredictor(history, metadata=None, config=cfg0, elo_state=({}, empty_tl))
    tracker = EloTracker(cfg0.elo, cfg0.importance)
    elo_base = EloBaseline(cfg0.elo)
    need_tl = cfg0.secondary.form_sensitivity > 0

    out: dict[str, list] = {m: [] for m in _MODELS}
    out["elo_pure"] = []
    outs: list[int] = []

    cursor = 0
    test_by_date = {d: g for d, g in test.groupby("date")}
    for d in sorted(test_by_date):
        ref_ts = pd.Timestamp(d)
        j = int(np.searchsorted(dates_arr, np.datetime64(ref_ts), side="left"))
        if j > cursor:
            tracker.update(history.iloc[cursor:j])
            cursor = j
        if j < 30:
            continue
        predictor.ratings = tracker.snapshot_ratings()
        predictor.elo_timeline = tracker.timeline() if need_tl else empty_tl
        ref = str(ref_ts.date())
        for row in test_by_date[d].itertuples(index=False):
            a, b = row.home_team, row.away_team
            neutral = bool(row.neutral)
            home = None if neutral else a
            per = {}
            ok = True
            for m in _MODELS:
                try:
                    pr = predictor.predict(
                        a, b, ref, neutral=neutral, home_team=home,
                        model=m, use_simulation=False,
                    )
                    per[m] = [pr.p_a, pr.p_draw, pr.p_b]
                except Exception:  # noqa: BLE001
                    ok = False
                    break
            if not ok:
                continue
            ra = predictor.ratings.get(a, cfg0.elo.base_rating)
            rb = predictor.ratings.get(b, cfg0.elo.base_rating)
            elo_p = elo_base.predict_1x2(ra, rb, neutral=neutral, home_team=home, team_a=a)
            for m in _MODELS:
                out[m].append(per[m])
            out["elo_pure"].append(list(elo_p))
            outs.append(_outcome(int(row.home_goals), int(row.away_goals)))

    arrs = {k: np.asarray(v, dtype=float) for k, v in out.items()}
    return arrs, np.asarray(outs, dtype=int)


def _blend(p_model: np.ndarray, p_elo: np.ndarray, w: float) -> np.ndarray:
    m = (1.0 - w) * p_model + w * p_elo
    return m / m.sum(axis=1, keepdims=True)


def _report(label: str, arr: np.ndarray, outs: np.ndarray) -> dict:
    m = evaluate_all(arr, outs)
    print(
        f"  {label:24s} RPS={m['rps']:.4f} brier={m['brier']:.4f} "
        f"logloss={m['log_loss']:.4f} acc={m['accuracy']:.3f}"
    )
    return m


def main() -> None:
    since = int(sys.argv[1]) if len(sys.argv) > 1 else 2006
    print(f"Cargando dataset (desde 2006)... | test: competitivos desde {since}")
    df = build_dataset(since_year=2006).sort_values("date", kind="stable").reset_index(drop=True)
    test = df[
        df["competition"].isin(_COMPETITIVE) & (df["date"].dt.year >= since)
    ].reset_index(drop=True)
    print(f"Partidos de test: {len(test)} | fechas únicas: {test['date'].nunique()}")

    t0 = time.time()
    arrs, outs = collect_probs_fast(df, test, DEFAULT_CONFIG)
    print(f"Pasada walk-forward: {len(outs)} partidos evaluados en {time.time() - t0:.0f}s\n")

    print("=== Modelos individuales ===")
    for m in (*_MODELS, "elo_pure"):
        _report(m, arrs[m], outs)

    print("\n=== Ensemble DC+Elo: sweep de peso (post-hoc) ===")
    base = _report("DC (w=0.0)", arrs["dixon_coles"], outs)
    best = (0.0, base["rps"])
    for w in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        m = _report(f"DC+elo (w={w:.1f})", _blend(arrs["dixon_coles"], arrs["elo_pure"], w), outs)
        if m["rps"] < best[1]:
            best = (w, m["rps"])
    print(f"\n  Mejor peso por RPS: w={best[0]:.1f} (RPS={best[1]:.4f}) | adoptado actual: 0.5")
    print("  (DC=0.0 es el comportamiento sin ensemble)")


if __name__ == "__main__":
    main()
