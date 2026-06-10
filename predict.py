"""
predict.py
==========
CLI para predecir un partido concreto.

Uso:
    python predict.py "Mexico" "South Africa"
    python predict.py "Mexico" "South Africa" --date 2026-06-11
    python predict.py "Argentina" "France" --knockout
    python predict.py "Brazil" "Germany" --model poisson_simple
    python predict.py --list-teams

Flags:
    --date YYYY-MM-DD   Fecha del partido (default: hoy)
    --model             poisson_simple | bivariate_poisson | dixon_coles (default)
    --knockout          Modo eliminatoria (prórroga + penales)
    --synthetic         Usa datos sintéticos en vez de datos reales
"""

from __future__ import annotations

import sys
from datetime import date


def _parse_args() -> dict:
    args = sys.argv[1:]

    if "--list-teams" in args:
        return {"action": "list"}

    # Equipos: primeros dos argumentos que no empiezan con --
    teams = [a for a in args if not a.startswith("--") and not _is_flag_value(args, a)]
    if len(teams) < 2:
        print("Uso: python predict.py \"Equipo A\" \"Equipo B\" [opciones]")
        print("     python predict.py --list-teams")
        sys.exit(1)

    team_a, team_b = teams[0], teams[1]

    match_date = _get_flag(args, "--date", str(date.today()))
    model = _get_flag(args, "--model", "dixon_coles")
    knockout = "--knockout" in args
    synthetic = "--synthetic" in args

    return {
        "action": "predict",
        "team_a": team_a,
        "team_b": team_b,
        "date": match_date,
        "model": model,
        "knockout": knockout,
        "synthetic": synthetic,
    }


def _is_flag_value(args: list[str], arg: str) -> bool:
    """True si el argumento es el valor de un flag como --date o --model."""
    flags_with_values = {"--date", "--model"}
    idx = args.index(arg)
    return idx > 0 and args[idx - 1] in flags_with_values


def _get_flag(args: list[str], flag: str, default: str) -> str:
    try:
        idx = args.index(flag)
        return args[idx + 1]
    except (ValueError, IndexError):
        return default


def main() -> None:
    cfg = _parse_args()

    if cfg["action"] == "list":
        from data.ingest import WC2026_TEAMS
        print("Equipos disponibles (Mundial 2026):")
        for t in sorted(WC2026_TEAMS):
            print(f"  {t}")
        return

    # Cargar datos
    if cfg["synthetic"]:
        from data.synthetic import generate_match_history, generate_team_metadata
        print("[modo: datos SINTETICOS]")
        matches = generate_match_history(n_matches_per_team=30, seed=7)
        metadata = generate_team_metadata(seed=11)
    else:
        from data.ingest import build_dataset
        from data.synthetic import generate_team_metadata
        matches = build_dataset(since_year=2018)
        metadata = generate_team_metadata(seed=11)

    from config import DEFAULT_CONFIG
    from prediction.predictor import MatchPredictor

    predictor = MatchPredictor(matches, metadata=metadata, config=DEFAULT_CONFIG)

    team_a = cfg["team_a"]
    team_b = cfg["team_b"]
    ref_date = cfg["date"]
    model = cfg["model"]

    print()
    if cfg["knockout"]:
        ko = predictor.predict_knockout(team_a, team_b, ref_date, neutral=True, model=model)
        r = ko["regulation"]
        print(f"MODO ELIMINATORIA — {team_a} vs {team_b}  [{ref_date}]")
        print(f"  90 min:  {team_a} {r['p_a']*100:.1f}%  |  Empate {r['p_draw']*100:.1f}%  |  {team_b} {r['p_b']*100:.1f}%")
        print(f"  Prob. penales: {ko['p_penalties']*100:.1f}%")
        print(f"  AVANZA {team_a}: {ko['p_advance_a']*100:.1f}%")
        print(f"  AVANZA {team_b}: {ko['p_advance_b']*100:.1f}%")
    else:
        pred = predictor.predict(team_a, team_b, ref_date, neutral=True, model=model)
        print(pred.format_report())


if __name__ == "__main__":
    main()
