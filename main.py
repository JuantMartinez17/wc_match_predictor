"""
main.py
=======
Demo de punta a punta del sistema de predicción.

Ejecuta:
  1. Carga de datos (reales o sintéticos según USE_REAL_DATA).
  2. Predicción de un partido concreto con Dixon-Coles + Monte Carlo (100k).
  3. Comparación de los tres modelos de marcador en el mismo partido.
  4. Backtesting walk-forward + tabla comparativa de métricas.
  5. Recalibrado por temperatura y curva de calibración.

Uso:
    python main.py              # datos sintéticos (no requiere red)
    python main.py --real       # descarga/usa datos reales (requiere red 1ª vez)
    python main.py --real --refresh   # fuerza re-descarga del dataset
"""

from __future__ import annotations

import sys

import numpy as np

from config import DEFAULT_CONFIG
from data.synthetic import (
    generate_match_history,
    generate_team_metadata,
    generate_availability,
)
from prediction.predictor import MatchPredictor
from simulation.montecarlo import exact_outcome
from validation.backtest import run_backtest, metrics_table
from validation.calibration import TemperatureScaler, reliability_curve
from validation.metrics import evaluate_all

# ---------------------------------------------------------------------------
# Flags de modo (se pueden pasar por argv o cambiando la constante aquí)
# ---------------------------------------------------------------------------
USE_REAL_DATA: bool = "--real" in sys.argv
FORCE_REFRESH: bool = "--refresh" in sys.argv


def _load_data() -> tuple:
    """Carga historial de partidos y metadatos según el modo configurado."""
    if USE_REAL_DATA:
        from data.ingest import build_dataset
        from data.synthetic import generate_team_metadata  # metadatos siguen siendo sintéticos

        print("\n[modo: datos REALES]")
        matches = build_dataset(since_year=2018, force_refresh=FORCE_REFRESH)
        # Los metadatos de plantilla/entrenador son sintéticos hasta integrar
        # Transfermarkt u otra fuente estructurada.
        metadata = generate_team_metadata(seed=11)
    else:
        print("\n[modo: datos SINTÉTICOS]")
        matches = generate_match_history(n_matches_per_team=30, seed=7)
        metadata = generate_team_metadata(seed=11)

    return matches, metadata


def main() -> None:
    np.set_printoptions(precision=4, suppress=True)

    print("=" * 64)
    print(" SISTEMA DE PREDICCIÓN — COPA DEL MUNDO 2026")
    print("=" * 64)

    # 1) Datos -------------------------------------------------------------
    matches, metadata = _load_data()
    print(f"\nPartidos disponibles: {len(matches)}  |  Equipos: {metadata['team'].nunique()}")
    print(f"Rango de fechas: {matches['date'].min().date()} a {matches['date'].max().date()}")

    predictor = MatchPredictor(matches, metadata=metadata, config=DEFAULT_CONFIG)

    # 2) Predicción de un partido -----------------------------------------
    team_a, team_b = "Argentina", "France"
    ref = "2026-06-01"
    abs_a = generate_availability(team_a, "minor", seed=1)
    abs_b = generate_availability(team_b, "key_absences", seed=2)

    print("\n" + "-" * 64)
    pred = predictor.predict(
        team_a, team_b, ref, neutral=True,
        absences_a=abs_a, absences_b=abs_b, model="dixon_coles",
    )
    print(pred.format_report())

    # 2b) Consistencia Monte Carlo vs. exacto (misma matriz, con rho estimado) -
    dc_matrix = predictor._last_matrix
    ex_a, ex_d, ex_b = exact_outcome(dc_matrix)
    print(f"\nrho Dixon-Coles estimado desde datos: {predictor._last_rho:+.4f}")
    print("Chequeo MC vs exacto (1X2):")
    print(f"  Monte Carlo: {pred.p_a:.4f} / {pred.p_draw:.4f} / {pred.p_b:.4f}")
    print(f"  Exacto:      {ex_a:.4f} / {ex_d:.4f} / {ex_b:.4f}")

    # 3) Comparación de modelos en el mismo partido -----------------------
    print("\n" + "-" * 64)
    print("Mismo partido bajo cada modelo de marcador:")
    for m in ("poisson_simple", "bivariate_poisson", "dixon_coles"):
        p = predictor.predict(team_a, team_b, ref, neutral=True, model=m, use_simulation=False)
        print(f"  {m:18s}  A {p.p_a*100:5.1f}% | X {p.p_draw*100:5.1f}% | B {p.p_b*100:5.1f}%"
              f"   (xG {p.expected_goals_a:.2f}-{p.expected_goals_b:.2f})")

    # 3b) Modo eliminatoria (prórroga + penales) --------------------------
    print("\n" + "-" * 64)
    ko = predictor.predict_knockout(team_a, team_b, ref, neutral=True, model="dixon_coles")
    print(f"Modo eliminatoria — {team_a} vs {team_b}:")
    r = ko["regulation"]
    print(f"  90': A {r['p_a']*100:.1f}% | X {r['p_draw']*100:.1f}% | B {r['p_b']*100:.1f}%")
    print(f"  Prob. de llegar a penales: {ko['p_penalties']*100:.1f}%")
    print(f"  AVANZA {team_a}: {ko['p_advance_a']*100:.1f}%   |   AVANZA {team_b}: {ko['p_advance_b']*100:.1f}%")

    # 4) Backtesting ------------------------------------------------------
    print("\n" + "-" * 64)
    print("Backtesting walk-forward (out-of-sample):")
    bt = run_backtest(matches, metadata=metadata, config=DEFAULT_CONFIG,
                      test_size=120, warmup_months=14, verbose=False)
    table = metrics_table(bt)
    print(f"\nPartidos evaluados: {bt['n_test']}")
    print("\nComparativa de modelos (ordenado por RPS, menor = mejor):")
    print(table.to_string(float_format=lambda x: f"{x:.4f}"))

    # 5) Calibración ------------------------------------------------------
    print("\n" + "-" * 64)
    best_model = table.index[0]
    print(f"Calibración del mejor modelo ({best_model}):")
    probs = bt["probs"][best_model]
    outcomes = bt["outcomes"][: len(probs)]

    n_fit = len(probs) // 2
    scaler = TemperatureScaler().fit(probs[:n_fit], outcomes[:n_fit])
    raw = evaluate_all(probs[n_fit:], outcomes[n_fit:])
    cal = evaluate_all(scaler.transform(probs[n_fit:]), outcomes[n_fit:])
    print(f"  Temperatura óptima: {scaler.temperature:.3f}")
    print(f"  Log loss  crudo {raw['log_loss']:.4f} -> calibrado {cal['log_loss']:.4f}")
    print(f"  RPS       crudo {raw['rps']:.4f} -> calibrado {cal['rps']:.4f}")

    rc = reliability_curve(probs, outcomes, n_bins=8)
    print("\n  Curva de calibración (confianza predicha vs. acierto observado):")
    for mp, of, c in zip(rc["bin_mean_pred"], rc["bin_obs_freq"], rc["bin_count"]):
        if c > 0:
            print(f"    pred {mp:.2f} -> observado {of:.2f}  (n={c})")

    # 6) Optimización de hiperparámetros (grilla acotada) -----------------
    print("\n" + "-" * 64)
    print("Optimización de hiperparámetros (búsqueda en grilla por RPS):")
    from validation.tuning import tune_hyperparameters
    tuned = tune_hyperparameters(
        matches, metadata=metadata, base_config=DEFAULT_CONFIG,
        lambda_decay_grid=(0.45, 0.65, 0.85), blend_grid=(0.25, 0.40),
        test_size=50, warmup_months=14, verbose=True,
    )
    print(f"\n  Mejor combinación: {tuned['best_params']}  (RPS={tuned['best_rps']:.4f})")

    print("\n" + "=" * 64)
    print(" Demo completa.")
    print("=" * 64)


if __name__ == "__main__":
    main()
