"""
data/standings.py
=================
Tabla de posiciones de la fase de grupos del Mundial 2026.

El fixture (ESPN/API-Football) NO trae la letra de grupo, así que los grupos se
INFIEREN del propio calendario: en fase de grupos cada equipo juega exactamente
a los otros tres de su grupo, de modo que las componentes conexas del grafo de
enfrentamientos `group-stage` son los grupos (4 equipos, 6 partidos cada uno).

La tabla se computa solo con partidos finalizados, con los criterios de
desempate de FIFA: puntos, diferencia de goles, goles a favor y, si persiste el
empate, el resultado directo entre los equipos empatados.

Funciones puras sobre la lista de partidos del fixture (dicts con team_a,
team_b, status, score_a, score_b, round). `load_group_standings` añade la capa
de obtención del fixture completo de la fase de grupos.
"""

from __future__ import annotations

from pathlib import Path

_GROUP_ROUND = "group-stage"
_FINISHED = "finalizado"


def _is_finished(m: dict) -> bool:
    """True si el partido terminó y tiene marcador numérico."""
    if m.get("status") != _FINISHED:
        return False
    return str(m.get("score_a", "")).strip().isdigit() and str(m.get("score_b", "")).strip().isdigit()


def _group_stage(matches: list[dict]) -> list[dict]:
    return [m for m in matches if m.get("round") == _GROUP_ROUND and m.get("team_a") and m.get("team_b")]


def infer_groups(matches: list[dict]) -> list[list[str]]:
    """
    Infiere los grupos como componentes conexas del grafo de enfrentamientos de
    fase de grupos. Usa partidos programados y finalizados (para reconstruir los
    grupos completos aunque no se hayan jugado todos). Devuelve listas de equipos
    ordenadas alfabéticamente, ordenadas a su vez por el primer equipo.
    """
    gs = _group_stage(matches)
    adj: dict[str, set[str]] = {}
    for m in gs:
        a, b = m["team_a"], m["team_b"]
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    seen: set[str] = set()
    groups: list[list[str]] = []
    for team in adj:
        if team in seen:
            continue
        # BFS sobre la componente conexa.
        comp: set[str] = set()
        stack = [team]
        while stack:
            t = stack.pop()
            if t in comp:
                continue
            comp.add(t)
            stack.extend(adj[t] - comp)
        seen |= comp
        groups.append(sorted(comp))
    groups.sort(key=lambda g: g[0] if g else "")
    return groups


def _h2h_key(team: str, rivals: set[str], matches: list[dict]) -> tuple[int, int, int]:
    """Mini-clasificación (puntos, GD, GF) de `team` SOLO vs los `rivals` empatados."""
    pts = gf = ga = 0
    for m in matches:
        if not _is_finished(m):
            continue
        a, b = m["team_a"], m["team_b"]
        sa, sb = int(m["score_a"]), int(m["score_b"])
        if a == team and b in rivals:
            tf, ta = sa, sb
        elif b == team and a in rivals:
            tf, ta = sb, sa
        else:
            continue
        gf += tf
        ga += ta
        pts += 3 if tf > ta else (1 if tf == ta else 0)
    return (pts, gf - ga, gf)


def compute_group_table(group_teams: list[str], matches: list[dict]) -> list[dict]:
    """
    Tabla de un grupo a partir de los partidos finalizados entre sus equipos.
    Cada fila: team, played, won, drawn, lost, gf, ga, gd, points.
    Ordenada por desempates FIFA (puntos, GD, GF, y resultado directo).
    """
    rows: dict[str, dict] = {
        t: {"team": t, "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "gf": 0, "ga": 0, "gd": 0, "points": 0}
        for t in group_teams
    }
    teamset = set(group_teams)
    for m in matches:
        if not _is_finished(m):
            continue
        a, b = m["team_a"], m["team_b"]
        if a not in teamset or b not in teamset:
            continue
        sa, sb = int(m["score_a"]), int(m["score_b"])
        for t, gf, ga in ((a, sa, sb), (b, sb, sa)):
            r = rows[t]
            r["played"] += 1
            r["gf"] += gf
            r["ga"] += ga
            if gf > ga:
                r["won"] += 1
                r["points"] += 3
            elif gf == ga:
                r["drawn"] += 1
                r["points"] += 1
            else:
                r["lost"] += 1
    for r in rows.values():
        r["gd"] = r["gf"] - r["ga"]

    ordered = list(rows.values())
    # Orden primario: puntos, GD, GF (desc). Desempate fino por resultado directo.
    ordered.sort(key=lambda r: (r["points"], r["gd"], r["gf"]), reverse=True)
    out: list[dict] = []
    i = 0
    while i < len(ordered):
        j = i + 1
        while (
            j < len(ordered)
            and (ordered[j]["points"], ordered[j]["gd"], ordered[j]["gf"])
            == (ordered[i]["points"], ordered[i]["gd"], ordered[i]["gf"])
        ):
            j += 1
        tied = ordered[i:j]
        if len(tied) > 1:
            rivals = {r["team"] for r in tied}
            tied.sort(key=lambda r: _h2h_key(r["team"], rivals - {r["team"]}, matches), reverse=True)
        out.extend(tied)
        i = j
    for rank, r in enumerate(out, 1):
        r["rank"] = rank
    return out


def compute_all_standings(matches: list[dict]) -> list[dict]:
    """
    Lista de grupos inferidos con su tabla. Cada elemento:
    {"group_index": int, "teams": [...], "table": [filas]}.
    `group_index` es un identificador estable por orden, NO la letra oficial
    (el fixture no expone la letra; los grupos se infieren del calendario).
    """
    groups = infer_groups(matches)
    return [
        {"group_index": idx, "teams": g, "table": compute_group_table(g, matches)}
        for idx, g in enumerate(groups, 1)
    ]


def is_last_group_matchday(group_table: list[dict]) -> bool:
    """True si el grupo está en (o entrando a) su última fecha: alguien jugó 2."""
    return any(r["played"] >= 2 for r in group_table)


def openness_factor(
    group_table: list[dict],
    team_a: str,
    team_b: str,
    sensitivity: float = 0.0,
) -> float:
    """
    [EXPERIMENTAL — default neutro] Factor de "apertura" del partido para
    escenarios must-win de última fecha de grupos. Si un equipo necesita ganar
    (está fuera del top-2 al entrar a la última fecha), el partido tiende a
    abrirse: ambas tasas de gol suben levemente. Devuelve un multiplicador >= 1.0,
    acotado a [1.0, 1.0 + sensitivity].

    No validado por backtest (no hay tablas históricas de grupo en los datos);
    `sensitivity=0.0` lo deja inerte. Pensado para uso en vivo, opt-in explícito.
    """
    if sensitivity <= 0 or not is_last_group_matchday(group_table):
        return 1.0
    rank = {r["team"]: r["rank"] for r in group_table}
    a_must = rank.get(team_a, 99) > 2
    b_must = rank.get(team_b, 99) > 2
    if not (a_must or b_must):
        return 1.0
    # Un equipo must-win -> medio efecto; ambos -> efecto completo.
    intensity = 1.0 if (a_must and b_must) else 0.5
    return 1.0 + sensitivity * intensity


def load_group_standings(cache_dir: str | Path = "data/cache") -> list[dict]:
    """
    Carga TODOS los partidos de fase de grupos cacheados (fixture_*.json) y
    computa las tablas. No hace red: usa lo que `data.fixture.get_fixture` haya
    ido cacheando. Si falta parte del calendario, los grupos pueden quedar
    incompletos (se computa con lo disponible).
    """
    import json

    cache_dir = Path(cache_dir)
    # Un registro por par de equipos, prefiriendo la versión finalizada (el mismo
    # partido puede aparecer en varios fixture_*.json a medida que se actualiza).
    by_pair: dict[frozenset, dict] = {}
    for path in sorted(cache_dir.glob("fixture_*.json")):
        try:
            day = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for m in day:
            if m.get("round") != _GROUP_ROUND or not m.get("team_a") or not m.get("team_b"):
                continue
            pair = frozenset((m["team_a"], m["team_b"]))
            prev = by_pair.get(pair)
            if prev is None or (_is_finished(m) and not _is_finished(prev)):
                by_pair[pair] = m
    return compute_all_standings(list(by_pair.values()))
