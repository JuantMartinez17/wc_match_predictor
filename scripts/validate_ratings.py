"""
scripts/validate_ratings.py
==========================
Valida la calidad y cobertura de data/wc2026_ratings.json (ratings EA FC 25,
fuente de valores de plantilla del predictor).

Chequea, para los 48 equipos del Mundial 2026:
  - que cada equipo tenga cobertura suficiente (>= MIN_PLAYERS jugadores) para
    valuar el XI y detectar ausencias (derive_absences usa top_n=11),
  - que todos los ratings estén en rango válido (40-99),
  - reporta el jugador top y el promedio por equipo (sanity check),
  - señala equipos faltantes o con cobertura fina.

Sale con código 1 si hay equipos faltantes o por debajo del mínimo, para poder
usarlo como gate (CI/pre-commit). Correr:
    python scripts/validate_ratings.py
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.constants import CANONICAL_BY_ID  # noqa: E402
from data.player_ratings import _load_ratings, get_player_ratings  # noqa: E402

MIN_PLAYERS = 12  # piso duro (gate); 15+ es lo recomendable
RECOMMENDED = 15
RATING_MIN, RATING_MAX = 40, 99


def _find_dupes(names: list[str]) -> list[tuple[str, str]]:
    """Nombres distintos pero muy similares = probable mismo jugador cargado 2x."""
    dupes = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            # subcadena (ej. 'Trezeguet' vs 'Mahmoud Trezeguet') o alta similitud
            if a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() > 0.85:
                dupes.append((a, b))
    return dupes


def main() -> int:
    raw = _load_ratings()
    wc_teams = sorted(CANONICAL_BY_ID.values())

    missing: list[str] = []
    thin: list[tuple[str, int]] = []
    below_floor: list[tuple[str, int]] = []
    bad_values: list[str] = []
    dupes: list[str] = []
    rows: list[tuple[str, int, float, str, int]] = []

    for team in wc_teams:
        team_data = {k: v for k, v in raw.get(team, {}).items() if k != "_meta"}
        n = len(team_data)
        if n == 0:
            missing.append(team)
            continue
        for name, r in team_data.items():
            if not (RATING_MIN <= float(r) <= RATING_MAX):
                bad_values.append(f"{team}: {name}={r}")
        for a, b in _find_dupes(list(team_data.keys())):
            dupes.append(f"{team}: '{a}' ~ '{b}'")
        if n < MIN_PLAYERS:
            below_floor.append((team, n))
        elif n < RECOMMENDED:
            thin.append((team, n))
        vals = get_player_ratings(team)
        top_name = max(vals, key=vals.get)
        rows.append((team, n, sum(vals.values()), top_name, max(raw[team].values())))

    print(f"Equipos WC2026: {len(wc_teams)}  |  con datos: {len(wc_teams) - len(missing)}")
    print(f"Cobertura mínima exigida: {MIN_PLAYERS} jugadores/equipo\n")

    print(f"{'Equipo':<26}{'N':>4}{'SquadM':>9}  Top (rating)")
    for team, n, squad, top_name, top_rating in sorted(rows, key=lambda r: -r[2]):
        flag = "  <-- FINO" if n < MIN_PLAYERS else ""
        print(f"{team:<26}{n:>4}{squad:>9.0f}  {top_name} ({top_rating}){flag}")

    ok = True
    if missing:
        ok = False
        print(f"\n[ERROR] Equipos SIN datos ({len(missing)}): {missing}")
    if below_floor:
        ok = False
        print(f"\n[ERROR] Equipos por debajo del piso de {MIN_PLAYERS} ({len(below_floor)}):")
        for team, n in sorted(below_floor, key=lambda t: t[1]):
            print(f"   {team}: {n}")
    if dupes:
        ok = False
        print(f"\n[ERROR] Posibles jugadores duplicados ({len(dupes)}):")
        for d in dupes:
            print(f"   {d}")
    if bad_values:
        ok = False
        print(f"\n[ERROR] Ratings fuera de rango [{RATING_MIN},{RATING_MAX}]:")
        for b in bad_values:
            print(f"   {b}")
    if thin:
        print(f"\n[AVISO] Cobertura entre {MIN_PLAYERS} y {RECOMMENDED} ({len(thin)} equipos, ideal >={RECOMMENDED}):")
        print("   " + ", ".join(f"{t}({n})" for t, n in sorted(thin, key=lambda t: t[1])))

    print("\n" + ("OK: dataset válido (gate)." if ok else "FALLA: corregir errores arriba."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
