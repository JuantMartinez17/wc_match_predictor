"""
backend/api/constants.py
========================
Constantes compartidas entre routers: IDs de equipos y códigos de banderas.

ID de equipo
------------
Slug ASCII estable derivado del nombre canónico en inglés. Inmutable mientras
el nombre canónico no cambie, lo que lo hace seguro como clave en API y frontend.

  "Argentina"              → "argentina"
  "Korea Republic"         → "korea-republic"
  "Côte d'Ivoire"          → "cote-divoire"
  "Bosnia and Herzegovina" → "bosnia-and-herzegovina"
  "USA"                    → "usa"

Banderas
--------
Código ISO 3166-1 alpha-2 usado directamente por flagcdn.com
(ej. "ar" → flagcdn.com/w80/ar.png). England y Scotland usan las subdivisiones
de GB soportadas por flagcdn.
"""

from __future__ import annotations

import re
import unicodedata

from data.ingest import WC2026_TEAMS


# ---------------------------------------------------------------------------
# Generación de IDs
# ---------------------------------------------------------------------------

def _slug(canonical: str) -> str:
    """Convierte un nombre canónico en un slug ASCII único y URL-safe."""
    s = unicodedata.normalize("NFKD", canonical).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"['\"]", "", s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


# canonical (inglés) → id slug
TEAM_IDS: dict[str, str] = {canonical: _slug(canonical) for canonical in WC2026_TEAMS}

# id slug → canonical (inglés) — para resolver el request del frontend
CANONICAL_BY_ID: dict[str, str] = {v: k for k, v in TEAM_IDS.items()}


def team_id(canonical: str) -> str:
    """Devuelve el ID del equipo dado su nombre canónico."""
    return TEAM_IDS.get(canonical, _slug(canonical))


def canonical_from_id(tid: str) -> str | None:
    """Devuelve el nombre canónico dado un ID. None si no existe."""
    return CANONICAL_BY_ID.get(tid)


# ---------------------------------------------------------------------------
# Banderas (códigos ISO2 para flagcdn.com)
# ---------------------------------------------------------------------------

_FLAG_ISO2: dict[str, str] = {
    # CONMEBOL
    "Argentina":            "ar",
    "Brazil":               "br",
    "Colombia":             "co",
    "Ecuador":              "ec",
    "Paraguay":             "py",
    "Uruguay":              "uy",
    # UEFA
    "Austria":              "at",
    "Belgium":              "be",
    "Bosnia and Herzegovina": "ba",
    "Croatia":              "hr",
    "Czechia":              "cz",
    "England":              "gb-eng",
    "France":               "fr",
    "Germany":              "de",
    "Netherlands":          "nl",
    "Norway":               "no",
    "Portugal":             "pt",
    "Scotland":             "gb-sct",
    "Spain":                "es",
    "Sweden":               "se",
    "Switzerland":          "ch",
    "Turkey":               "tr",
    # CAF
    "Algeria":              "dz",
    "Cabo Verde":           "cv",
    "Congo DR":             "cd",
    "Côte d'Ivoire":        "ci",
    "Egypt":                "eg",
    "Ghana":                "gh",
    "Morocco":              "ma",
    "Senegal":              "sn",
    "South Africa":         "za",
    "Tunisia":              "tn",
    # AFC
    "Australia":            "au",
    "Iran":                 "ir",
    "Iraq":                 "iq",
    "Japan":                "jp",
    "Jordan":               "jo",
    "Korea Republic":       "kr",
    "Qatar":                "qa",
    "Saudi Arabia":         "sa",
    "Uzbekistan":           "uz",
    # CONCACAF
    "Canada":               "ca",
    "Curaçao":              "cw",
    "Haiti":                "ht",
    "Mexico":               "mx",
    "Panama":               "pa",
    "USA":                  "us",
    # OFC
    "New Zealand":          "nz",
}


def flag(team: str) -> str:
    """Devuelve el código ISO2 para usar con flagcdn.com. Fallback: 'un' (bandera de la ONU)."""
    return _FLAG_ISO2.get(team, "un")
