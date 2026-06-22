"""
scripts/tune_wc.py
==================
Optimización offline de hiperparámetros del predictor por backtest walk-forward.

Protocolo train/holdout para no sobreajustar la elección de parámetros:
  - TUNE   sobre los Mundiales 2014 + 2018
  - VALIDA sobre el Mundial 2022 (holdout, nunca se mira para elegir)

Dos etapas (grid search), minimizando RPS en el conjunto de tuning:
  1) lambda_decay × elo_prior_blend
  2) elo_supremacy_exponent × form_sensitivity (fijando los ganadores de la etapa 1)

Al final se compara el holdout 2022 de los defaults vs. los parámetros tuneados.
Solo conviene adoptar los nuevos defaults en config.py si el holdout MEJORA.

Correr (desde la raíz del repo):
    python scripts/tune_wc.py
"""

from __future__ import annotations

import dataclasses
import itertools
import sys
import time
from pathlib import Path

# Permite ejecutar el script directamente (agrega la raíz del repo al path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from config import DEFAULT_CONFIG  # noqa: E402
from data.ingest import build_dataset  # noqa: E402
from features.elo import EloTracker  # noqa: E402
from prediction.predictor import MatchPredictor  # noqa: E402
from validation.metrics import evaluate_all  # noqa: E402


def _outcome(home_goals: int, away_goals: int) -> int:
    if home_goals > away_goals:
        return 0
    return 1 if home_goals == away_goals else 2


def fast_backtest(all_sorted, dates_arr, test, config, model="dixon_coles") -> dict:
    """
    Walk-forward rápido (Elo incremental, sin recomputar por partido) sobre los
    partidos de `test`. Entrena solo con datos anteriores a cada fecha. Devuelve
    el dict de métricas de `evaluate_all` (rps, brier, log_loss, accuracy, n).
    """
    need_timeline = config.secondary.form_sensitivity > 0
    empty_tl = pd.DataFrame(columns=["date", "team", "rating"])
    tracker = EloTracker(config.elo, config.importance)
    cursor = 0
    probs: list[list[float]] = []
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
        timeline = tracker.timeline() if need_timeline else empty_tl
        try:
            predictor = MatchPredictor(
                train,
                metadata=None,
                config=config,
                elo_state=(tracker.snapshot_ratings(), timeline),
            )
        except Exception:
            continue
        ref = str(ref_ts.date())
        for row in test[test["date"] == ref_ts].itertuples(index=False):
            a, b = row.home_team, row.away_team
            neutral = bool(row.neutral)
            home = None if neutral else a
            try:
                pr = predictor.predict(
                    a,
                    b,
                    ref,
                    neutral=neutral,
                    home_team=home,
                    model=model,
                    use_simulation=False,
                )
            except Exception:
                continue
            probs.append([pr.p_a, pr.p_draw, pr.p_b])
            outs.append(_outcome(int(row.home_goals), int(row.away_goals)))

    return evaluate_all(np.array(probs, dtype=float), np.array(outs, dtype=int))


def _wc_subset(all_sorted, years: tuple[int, ...]):
    return all_sorted[
        (all_sorted["competition"] == "world_cup")
        & (all_sorted["date"].dt.year.isin(years))
    ].reset_index(drop=True)


def _make_cfg(**kw):
    """Reconstruye Config (frozen) variando los parámetros dados."""
    dec = DEFAULT_CONFIG.decay
    st = DEFAULT_CONFIG.strength
    sec = DEFAULT_CONFIG.secondary
    if "lambda_decay" in kw:
        dec = dataclasses.replace(dec, lambda_decay=kw["lambda_decay"])
    if "elo_prior_blend" in kw or "elo_supremacy_exponent" in kw:
        st = dataclasses.replace(
            st,
            elo_prior_blend=kw.get("elo_prior_blend", st.elo_prior_blend),
            elo_supremacy_exponent=kw.get(
                "elo_supremacy_exponent", st.elo_supremacy_exponent
            ),
        )
    if "intratournament_boost" in kw:
        dec = dataclasses.replace(dec, intratournament_boost=kw["intratournament_boost"])
    if "form_sensitivity" in kw or "fatigue_sensitivity" in kw:
        sec = dataclasses.replace(
            sec,
            form_sensitivity=kw.get("form_sensitivity", sec.form_sensitivity),
            fatigue_sensitivity=kw.get("fatigue_sensitivity", sec.fatigue_sensitivity),
        )
    return dataclasses.replace(DEFAULT_CONFIG, decay=dec, strength=st, secondary=sec)


def main() -> None:
    print("Cargando dataset (desde 2006)...")
    all_matches = build_dataset(since_year=2006)
    all_sorted = all_matches.sort_values("date", kind="stable").reset_index(drop=True)
    dates_arr = all_sorted["date"].to_numpy()

    tune_set = _wc_subset(all_sorted, (2014, 2018))
    holdout = _wc_subset(all_sorted, (2022,))
    print(
        f"Tune: {len(tune_set)} partidos (WC 2014+2018) | "
        f"Holdout: {len(holdout)} partidos (WC 2022)\n"
    )

    base_tune = fast_backtest(all_sorted, dates_arr, tune_set, DEFAULT_CONFIG)
    base_hold = fast_backtest(all_sorted, dates_arr, holdout, DEFAULT_CONFIG)
    print(
        f"DEFAULTS   tune  RPS={base_tune['rps']:.4f} brier={base_tune['brier']:.4f} "
        f"acc={base_tune['accuracy']:.3f}\n"
        f"           holdout RPS={base_hold['rps']:.4f} brier={base_hold['brier']:.4f} "
        f"acc={base_hold['accuracy']:.3f}"
    )

    # ---- Etapa 1: lambda_decay × elo_prior_blend ----
    print("\n=== Etapa 1: lambda_decay × elo_prior_blend (min RPS tune) ===")
    s1 = []
    # Grid ensanchado hacia donde ganaron los defaults adoptados (ld al mínimo,
    # blend al máximo de los grids previos): se explora ld más bajo y blend más alto.
    for ld, bl in itertools.product((0.25, 0.40, 0.55), (0.50, 0.65, 0.80)):
        t0 = time.time()
        m = fast_backtest(
            all_sorted,
            dates_arr,
            tune_set,
            _make_cfg(lambda_decay=ld, elo_prior_blend=bl),
        )
        s1.append((ld, bl, m["rps"], m["brier"]))
        print(
            f"  ld={ld:.2f} blend={bl:.2f} -> RPS={m['rps']:.4f} brier={m['brier']:.4f}  ({time.time() - t0:.0f}s)"
        )
    best_ld, best_bl, _, _ = min(s1, key=lambda r: r[2])
    print(f"  >> Ganador E1: lambda_decay={best_ld}  elo_prior_blend={best_bl}")

    # ---- Etapa 2: elo_supremacy_exponent × form_sensitivity ----
    print("\n=== Etapa 2: elo_supremacy_exponent × form_sensitivity (min RPS tune) ===")
    s2 = []
    # Grid ensanchado: exp y form también ganaron al máximo del grid previo.
    for ex, fs in itertools.product((2.0, 2.5, 3.0), (0.10, 0.15, 0.20)):
        t0 = time.time()
        cfg = _make_cfg(
            lambda_decay=best_ld,
            elo_prior_blend=best_bl,
            elo_supremacy_exponent=ex,
            form_sensitivity=fs,
        )
        m = fast_backtest(all_sorted, dates_arr, tune_set, cfg)
        s2.append((ex, fs, m["rps"], m["brier"]))
        print(
            f"  exp={ex:.1f} form={fs:.2f} -> RPS={m['rps']:.4f} brier={m['brier']:.4f}  ({time.time() - t0:.0f}s)"
        )
    best_ex, best_fs, _, _ = min(s2, key=lambda r: r[2])
    print(
        f"  >> Ganador E2: elo_supremacy_exponent={best_ex}  form_sensitivity={best_fs}"
    )

    # ---- Etapa 3: intratournament_boost (fijando ganadores de E1+E2) ----
    print("\n=== Etapa 3: intratournament_boost (min RPS tune) ===")
    s3 = []
    for boost in (1.0, 1.5, 2.0, 3.0):
        t0 = time.time()
        cfg = _make_cfg(
            lambda_decay=best_ld,
            elo_prior_blend=best_bl,
            elo_supremacy_exponent=best_ex,
            form_sensitivity=best_fs,
            intratournament_boost=boost,
        )
        m = fast_backtest(all_sorted, dates_arr, tune_set, cfg)
        s3.append((boost, m["rps"], m["brier"]))
        print(
            f"  boost={boost:.1f} -> RPS={m['rps']:.4f} brier={m['brier']:.4f}  ({time.time() - t0:.0f}s)"
        )
    best_boost, _, _ = min(s3, key=lambda r: r[1])
    print(f"  >> Ganador E3: intratournament_boost={best_boost}")

    # ---- Validación en holdout 2022 ----
    best_cfg = _make_cfg(
        lambda_decay=best_ld,
        elo_prior_blend=best_bl,
        elo_supremacy_exponent=best_ex,
        form_sensitivity=best_fs,
        intratournament_boost=best_boost,
    )
    tuned_hold = fast_backtest(all_sorted, dates_arr, holdout, best_cfg)

    print("\n" + "=" * 60)
    print("HOLDOUT 2022 — defaults vs tuneado")
    print(
        f"  DEFAULTS: RPS={base_hold['rps']:.4f} brier={base_hold['brier']:.4f} acc={base_hold['accuracy']:.3f}"
    )
    print(
        f"  TUNEADO:  RPS={tuned_hold['rps']:.4f} brier={tuned_hold['brier']:.4f} acc={tuned_hold['accuracy']:.3f}"
    )
    better = tuned_hold["rps"] < base_hold["rps"]
    print(
        f"\n  Parámetros tuneados: lambda_decay={best_ld} elo_prior_blend={best_bl} "
        f"elo_supremacy_exponent={best_ex} form_sensitivity={best_fs} "
        f"intratournament_boost={best_boost}"
    )
    print(
        f"  DECISIÓN: {'ADOPTAR (holdout mejora)' if better else 'NO adoptar (holdout no mejora)'}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
