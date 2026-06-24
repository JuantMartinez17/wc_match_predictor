"""
data/instances.py
=================
Clasificación de los partidos del Mundial por INSTANCIA (jornada / ronda):

  - Fase de grupos: `fecha-1`, `fecha-2`, `fecha-3`. ESPN no expone la jornada
    (siempre `group-stage`), así que se DERIVA del calendario usando la inferencia
    de grupos de `data/standings.infer_groups`: en un grupo de 4, las 6 fechas en
    orden cronológico van de a 2 por jornada.
  - Eliminatoria: `dieciseisavos`, `octavos`, `cuartos`, `semis`, `tercer-puesto`,
    `final`. Directo del slug de ESPN (campo `round`; ver data/fixture).

`get_fixture_by_instance` trae el torneo completo (UNA llamada cacheada) y devuelve
solo los partidos de la instancia pedida.
"""

from __future__ import annotations

from pathlib import Path

from data.fixture import get_tournament_fixture
from data.standings import infer_groups

# Instancia (parámetro público) -> slug de ESPN de la ronda de eliminatoria.
_KNOCKOUT_INSTANCE_TO_SLUG: dict[str, str] = {
    "dieciseisavos": "round-of-32",
    "octavos": "round-of-16",
    "cuartos": "quarterfinals",
    "semis": "semifinals",
    "tercer-puesto": "3rd-place-match",
    "final": "final",
}
_GROUP_INSTANCES = ("fecha-1", "fecha-2", "fecha-3")
VALID_INSTANCES: tuple[str, ...] = (*_GROUP_INSTANCES, *_KNOCKOUT_INSTANCE_TO_SLUG)

_GROUP_ROUND = "group-stage"


def assign_group_matchdays(matches: list[dict]) -> dict[str, int]:
    """
    Mapea `id` de partido -> jornada (1/2/3) para la fase de grupos. En un grupo de
    4 las 6 fechas, en orden cronológico, son 2 por jornada: se ordena cada grupo
    por (date, time_utc) y se asigna de a pares.
    """
    gs = [m for m in matches if m.get("round") == _GROUP_ROUND]
    md: dict[str, int] = {}
    for teams in infer_groups(gs):
        ts = set(teams)
        gm = sorted(
            (m for m in gs if m.get("team_a") in ts and m.get("team_b") in ts),
            key=lambda m: (m.get("date", ""), m.get("time_utc", "")),
        )
        for i, m in enumerate(gm):
            md[m.get("id")] = i // 2 + 1
    return md


def get_fixture_by_instance(
    instance: str,
    cache_dir: str | Path = "data/cache",
) -> list[dict]:
    """
    Devuelve los partidos de una instancia/jornada. `instance` debe estar en
    `VALID_INSTANCES` (si no, ValueError). Trae el torneo completo (una llamada
    cacheada) y filtra. Knockout no resuelto aún (equipos por definir) puede venir
    vacío hasta que se conozcan los clasificados.
    """
    inst = instance.lower()
    if inst not in VALID_INSTANCES:
        raise ValueError(
            f"Instancia inválida: '{instance}'. Opciones: {', '.join(VALID_INSTANCES)}."
        )
    matches = get_tournament_fixture(cache_dir)

    if inst in _KNOCKOUT_INSTANCE_TO_SLUG:
        slug = _KNOCKOUT_INSTANCE_TO_SLUG[inst]
        out = [m for m in matches if m.get("round") == slug]
    else:
        n = int(inst.split("-")[1])
        md = assign_group_matchdays(matches)
        out = [m for m in matches if md.get(m.get("id")) == n]

    return sorted(out, key=lambda m: (m.get("date", ""), m.get("time_utc", "")))
