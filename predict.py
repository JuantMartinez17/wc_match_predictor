"""
predict.py
==========
CLI interactiva para predecir partidos del Mundial 2026.

Modos de uso:
  python predict.py                            # modo interactivo (pregunta equipos y fecha)
  python predict.py "Mexico" "Panama"          # directo, fecha = hoy
  python predict.py "Mexico" "Panama" --date 2026-06-15
  python predict.py "Argentina" "Francia" --knockout
  python predict.py --list                     # muestra los 48 equipos disponibles

Flags opcionales:
  --date YYYY-MM-DD   Fecha de referencia (default: hoy)
  --model             dixon_coles* | bivariate_poisson | poisson_simple
  --knockout          Modo eliminatoria (prórroga + penales)
  --synthetic         Usa datos sintéticos en lugar de datos reales

Ventaja de local:
  Se aplica automáticamente cuando uno de los equipos es México, Estados Unidos
  o Canadá (sedes del Mundial 2026). En cualquier otro caso se considera cancha
  neutral (hinchas equivalentes de ambos lados).
"""

from __future__ import annotations

import difflib
import sys
from datetime import date, timedelta

from data.ingest import WC2026_TEAMS

# ---------------------------------------------------------------------------
# Nombres en español — display e input
# ---------------------------------------------------------------------------

# Canónico (inglés) → español para mostrar en pantalla
TEAM_EN_TO_ES: dict[str, str] = {
    "Algeria": "Argelia",
    "Argentina": "Argentina",
    "Australia": "Australia",
    "Austria": "Austria",
    "Belgium": "Bélgica",
    "Bosnia and Herzegovina": "Bosnia y Herzegovina",
    "Brazil": "Brasil",
    "Cabo Verde": "Cabo Verde",
    "Canada": "Canadá",
    "Colombia": "Colombia",
    "Congo DR": "Congo RD",
    "Croatia": "Croacia",
    "Curaçao": "Curazao",
    "Czechia": "Chequia",
    "Côte d'Ivoire": "Costa de Marfil",
    "Ecuador": "Ecuador",
    "Egypt": "Egipto",
    "England": "Inglaterra",
    "France": "Francia",
    "Germany": "Alemania",
    "Ghana": "Ghana",
    "Haiti": "Haití",
    "Iran": "Irán",
    "Iraq": "Irak",
    "Japan": "Japón",
    "Jordan": "Jordania",
    "Korea Republic": "Corea del Sur",
    "Mexico": "México",
    "Morocco": "Marruecos",
    "Netherlands": "Países Bajos",
    "New Zealand": "Nueva Zelanda",
    "Norway": "Noruega",
    "Panama": "Panamá",
    "Paraguay": "Paraguay",
    "Portugal": "Portugal",
    "Qatar": "Catar",
    "Saudi Arabia": "Arabia Saudita",
    "Scotland": "Escocia",
    "Senegal": "Senegal",
    "South Africa": "Sudáfrica",
    "Spain": "España",
    "Sweden": "Suecia",
    "Switzerland": "Suiza",
    "Tunisia": "Túnez",
    "Turkey": "Turquía",
    "USA": "Estados Unidos",
    "Uruguay": "Uruguay",
    "Uzbekistan": "Uzbekistán",
}

# Español → canónico (inglés) para resolver input del usuario
TEAM_ES_TO_EN: dict[str, str] = {v.lower(): k for k, v in TEAM_EN_TO_ES.items()}

# Lista ordenada por nombre en español para el display
_TEAMS_SORTED = sorted(WC2026_TEAMS, key=lambda t: TEAM_EN_TO_ES.get(t, t))


# ---------------------------------------------------------------------------
# Resolución de nombre con fuzzy matching
# ---------------------------------------------------------------------------

def resolve_team(name: str) -> str:
    """
    Devuelve el nombre canónico (inglés interno) del equipo.
    Acepta input en español o inglés, con coincidencias exactas o aproximadas.
    """
    name_stripped = name.strip()
    lower_input = name_stripped.lower()

    # 1. Coincidencia exacta en español
    if lower_input in TEAM_ES_TO_EN:
        return TEAM_ES_TO_EN[lower_input]

    # 2. Coincidencia exacta en inglés (case-insensitive)
    for team in WC2026_TEAMS:
        if team.lower() == lower_input:
            return team

    # 3. Coincidencia parcial — busca en nombres en español e inglés
    all_names_es = list(TEAM_EN_TO_ES.values())
    partial_es = [n for n in all_names_es if lower_input in n.lower()]
    if len(partial_es) == 1:
        return TEAM_ES_TO_EN[partial_es[0].lower()]
    partial_en = [t for t in WC2026_TEAMS if lower_input in t.lower()]
    if len(partial_en) == 1:
        return partial_en[0]

    # 4. Fuzzy matching sobre nombres en español
    close_es = difflib.get_close_matches(name_stripped, all_names_es, n=3, cutoff=0.4)
    if close_es:
        suggestions = ", ".join(close_es)
        print(f"  '{name_stripped}' no encontrado. Quisiste decir: {suggestions}?")
        sys.exit(1)

    # 5. Fuzzy matching sobre nombres en inglés
    close_en = difflib.get_close_matches(name_stripped, list(WC2026_TEAMS), n=3, cutoff=0.4)
    if close_en:
        suggestions = ", ".join(TEAM_EN_TO_ES.get(t, t) for t in close_en)
        print(f"  '{name_stripped}' no encontrado. Quisiste decir: {suggestions}?")
        sys.exit(1)

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
# Detección automática de local (sedes del Mundial 2026)
# ---------------------------------------------------------------------------

_HOST_NATIONS = {"Mexico", "USA", "Canada"}  # nombres canónicos internos


def detect_venue(team_a: str, team_b: str) -> tuple[bool, str | None]:
    """
    Devuelve (neutral, home_team).

    - Si exactamente uno de los equipos es sede → neutral=False, home_team=ese equipo.
    - Si ambos son sedes o ninguno lo es → neutral=True, home_team=None.
    """
    a_is_host = team_a in _HOST_NATIONS
    b_is_host = team_b in _HOST_NATIONS

    if a_is_host and not b_is_host:
        return False, team_a
    if b_is_host and not a_is_host:
        return False, team_b
    return True, None


# ---------------------------------------------------------------------------
# Modo interactivo
# ---------------------------------------------------------------------------

def interactive_mode() -> dict:
    print("=" * 56)
    print(" PREDICTOR DE PARTIDOS — MUNDIAL 2026")
    print("=" * 56)
    print("(Escribe 'lista' para ver los 48 equipos)\n")

    while True:
        raw_a = input("Primer equipo : ").strip()
        if raw_a.lower() == "lista":
            _print_teams()
            continue
        if raw_a:
            break

    while True:
        raw_b = input("Segundo equipo: ").strip()
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
        nombre_es = TEAM_EN_TO_ES.get(t, t)
        print(f"  {i:2}. {nombre_es}")
    print()


# ---------------------------------------------------------------------------
# Predicción
# ---------------------------------------------------------------------------

def _venue_label(neutral: bool, home_team: str | None, team_a: str, team_b: str) -> str:
    if not neutral and home_team:
        nombre_es = TEAM_EN_TO_ES.get(home_team, home_team)
        return f"Local: {nombre_es} (sede del Mundial)"
    return "Cancha neutral"


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

    neutral, home_team = detect_venue(team_a, team_b)
    venue_label = _venue_label(neutral, home_team, team_a, team_b)

    nombre_a = TEAM_EN_TO_ES.get(team_a, team_a)
    nombre_b = TEAM_EN_TO_ES.get(team_b, team_b)

    print()
    if cfg.get("knockout"):
        ko = predictor.predict_knockout(
            team_a, team_b, ref_date, neutral=neutral, home_team=home_team, model=model
        )
        r = ko["regulation"]
        print(f"ELIMINATORIA — {nombre_a} vs {nombre_b}  [{ref_date}]  |  {venue_label}")
        print(f"  90 min:  {nombre_a} {r['p_a']*100:.1f}%  |  Empate {r['p_draw']*100:.1f}%  |  {nombre_b} {r['p_b']*100:.1f}%")
        print(f"  Prob. llegar a penales: {ko['p_penalties']*100:.1f}%")
        print(f"  AVANZA {nombre_a}: {ko['p_advance_a']*100:.1f}%")
        print(f"  AVANZA {nombre_b}: {ko['p_advance_b']*100:.1f}%")
    else:
        pred = predictor.predict(
            team_a, team_b, ref_date, neutral=neutral, home_team=home_team, model=model
        )
        print(f"[{venue_label}]")
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
