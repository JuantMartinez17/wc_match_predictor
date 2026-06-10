"""
predict.py
==========
CLI interactiva para predecir partidos del Mundial 2026.

Modos de uso:
  python predict.py                            # modo interactivo (pregunta equipos y fecha)
  python predict.py "Mexico" "Panama"          # directo, fecha = hoy
  python predict.py "Mexico" "Panama" --date 2026-06-15
  python predict.py "Argentina" "France" --knockout
  python predict.py --list                     # muestra los 48 equipos disponibles

Flags opcionales:
  --date YYYY-MM-DD   Fecha de referencia (default: hoy)
  --model             dixon_coles* | bivariate_poisson | poisson_simple
  --knockout          Modo eliminatoria (prórroga + penales)
  --synthetic         Usa datos sintéticos en lugar de datos reales
"""

from __future__ import annotations

import difflib
import sys
from datetime import date, timedelta

from data.ingest import WC2026_TEAMS

# Lista ordenada para mostrar y buscar
_TEAMS_SORTED = sorted(WC2026_TEAMS)


# ---------------------------------------------------------------------------
# Resolución de nombre con fuzzy matching
# ---------------------------------------------------------------------------

def resolve_team(name: str) -> str:
    """
    Devuelve el nombre canónico del equipo.
    Acepta coincidencias exactas (case-insensitive) o aproximadas.
    Aborta con mensaje claro si no hay match razonable.
    """
    name_stripped = name.strip()
    lower_input = name_stripped.lower()

    # 1. Coincidencia exacta (case-insensitive)
    for team in _TEAMS_SORTED:
        if team.lower() == lower_input:
            return team

    # 2. Coincidencia parcial (el input está contenido en el nombre)
    partial = [t for t in _TEAMS_SORTED if lower_input in t.lower()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        opts = ", ".join(partial)
        print(f"  '{name_stripped}' es ambiguo. Opciones: {opts}")
        sys.exit(1)

    # 3. Fuzzy matching
    close = difflib.get_close_matches(name_stripped, _TEAMS_SORTED, n=3, cutoff=0.4)
    if close:
        suggestions = ", ".join(close)
        print(f"  '{name_stripped}' no encontrado. Quizas quisiste: {suggestions}")
    else:
        print(f"  '{name_stripped}' no es un equipo del Mundial 2026.")
        print(f"  Usa  python predict.py --list  para ver los 48 equipos.")
    sys.exit(1)


def resolve_date(value: str) -> str:
    """Acepta YYYY-MM-DD, 'hoy', 'today', 'manana', 'tomorrow'."""
    low = value.strip().lower()
    if low in ("hoy", "today"):
        return str(date.today())
    if low in ("manana", "mañana", "tomorrow"):
        return str(date.today() + timedelta(days=1))
    # Validar formato básico
    try:
        date.fromisoformat(value.strip())
        return value.strip()
    except ValueError:
        print(f"  Fecha invalida: '{value}'. Formato esperado: YYYY-MM-DD")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Parseo de argumentos
# ---------------------------------------------------------------------------

def _get_flag(args: list[str], flag: str, default: str | None = None) -> str | None:
    try:
        idx = args.index(flag)
        return args[idx + 1]
    except (ValueError, IndexError):
        return default


def _is_flag_value(args: list[str], arg: str) -> bool:
    flags_with_values = {"--date", "--model"}
    try:
        idx = args.index(arg)
        return idx > 0 and args[idx - 1] in flags_with_values
    except ValueError:
        return False


def parse_args() -> dict:
    args = sys.argv[1:]

    if "--list" in args or "--list-teams" in args:
        return {"action": "list"}

    positional = [a for a in args if not a.startswith("--") and not _is_flag_value(args, a)]

    # Sin argumentos posicionales → modo interactivo
    if len(positional) == 0:
        return {"action": "interactive"}

    if len(positional) < 2:
        print("Uso: python predict.py \"Equipo A\" \"Equipo B\" [--date YYYY-MM-DD] [--knockout]")
        sys.exit(1)

    return {
        "action": "predict",
        "team_a": positional[0],
        "team_b": positional[1],
        "date": _get_flag(args, "--date", str(date.today())),
        "model": _get_flag(args, "--model", "dixon_coles"),
        "knockout": "--knockout" in args,
        "synthetic": "--synthetic" in args,
    }


# ---------------------------------------------------------------------------
# Modo interactivo
# ---------------------------------------------------------------------------

def interactive_mode() -> dict:
    print("=" * 56)
    print(" PREDICTOR DE PARTIDOS — MUNDIAL 2026")
    print("=" * 56)
    print("(Escribe 'lista' para ver los 48 equipos)\n")

    while True:
        raw_a = input("Equipo local / A: ").strip()
        if raw_a.lower() == "lista":
            _print_teams()
            continue
        if raw_a:
            break

    while True:
        raw_b = input("Equipo visitante / B: ").strip()
        if raw_b.lower() == "lista":
            _print_teams()
            continue
        if raw_b:
            break

    raw_date = input(f"Fecha [Enter = hoy {date.today()}]: ").strip() or str(date.today())

    knockout_input = input("Modo eliminatoria? (s/n) [n]: ").strip().lower()
    knockout = knockout_input in ("s", "si", "y", "yes")

    return {
        "action": "predict",
        "team_a": raw_a,
        "team_b": raw_b,
        "date": raw_date,
        "model": "dixon_coles",
        "knockout": knockout,
        "synthetic": False,
    }


# ---------------------------------------------------------------------------
# Helpers de display
# ---------------------------------------------------------------------------

def _print_teams() -> None:
    print("\nEquipos clasificados al Mundial 2026 (48):")
    for i, t in enumerate(_TEAMS_SORTED, 1):
        print(f"  {i:2}. {t}")
    print()


# ---------------------------------------------------------------------------
# Predicción
# ---------------------------------------------------------------------------

def run_prediction(cfg: dict) -> None:
    if cfg.get("synthetic"):
        from data.synthetic import generate_match_history, generate_team_metadata
        print("[modo: datos SINTETICOS]\n")
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

    team_a = resolve_team(cfg["team_a"])
    team_b = resolve_team(cfg["team_b"])
    ref_date = resolve_date(cfg["date"])
    model = cfg.get("model", "dixon_coles")

    print()
    if cfg.get("knockout"):
        ko = predictor.predict_knockout(team_a, team_b, ref_date, neutral=True, model=model)
        r = ko["regulation"]
        print(f"ELIMINATORIA — {team_a} vs {team_b}  [{ref_date}]")
        print(f"  90 min:  {team_a} {r['p_a']*100:.1f}%  |  Empate {r['p_draw']*100:.1f}%  |  {team_b} {r['p_b']*100:.1f}%")
        print(f"  Prob. llegar a penales: {ko['p_penalties']*100:.1f}%")
        print(f"  AVANZA {team_a}: {ko['p_advance_a']*100:.1f}%")
        print(f"  AVANZA {team_b}: {ko['p_advance_b']*100:.1f}%")
    else:
        pred = predictor.predict(team_a, team_b, ref_date, neutral=True, model=model)
        print(pred.format_report())


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    cfg = parse_args()

    if cfg["action"] == "list":
        _print_teams()
        return

    if cfg["action"] == "interactive":
        cfg = interactive_mode()

    run_prediction(cfg)


if __name__ == "__main__":
    main()
