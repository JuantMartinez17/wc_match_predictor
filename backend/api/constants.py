"""
backend/api/constants.py
========================
Constantes compartidas entre routers: IDs de equipos, emojis de banderas.

El ID de cada equipo es un slug ASCII estable derivado del nombre canónico en
inglés. Es inmutable mientras el nombre canónico no cambie, lo que lo hace
seguro para usar como clave en la API y en el frontend.

Ejemplos:
  "Argentina"            → "argentina"
  "Korea Republic"       → "korea-republic"
  "Côte d'Ivoire"        → "cote-divoire"
  "Bosnia and Herzegovina" → "bosnia-and-herzegovina"
  "USA"                  → "usa"
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
# Emojis de banderas
# ---------------------------------------------------------------------------

FLAGS: dict[str, str] = {
    "Algeria": "🇩🇿",
    "Argentina": "🇦🇷",
    "Australia": "🇦🇺",
    "Austria": "🇦🇹",
    "Belgium": "🇧🇪",
    "Bosnia and Herzegovina": "🇧🇦",
    "Brazil": "🇧🇷",
    "Cabo Verde": "🇨🇻",
    "Canada": "🇨🇦",
    "Colombia": "🇨🇴",
    "Congo DR": "🇨🇩",
    "Croatia": "🇭🇷",
    "Curaçao": "🇨🇼",
    "Czechia": "🇨🇿",
    "Côte d'Ivoire": "🇨🇮",
    "Ecuador": "🇪🇨",
    "Egypt": "🇪🇬",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "France": "🇫🇷",
    "Germany": "🇩🇪",
    "Ghana": "🇬🇭",
    "Haiti": "🇭🇹",
    "Iran": "🇮🇷",
    "Iraq": "🇮🇶",
    "Japan": "🇯🇵",
    "Jordan": "🇯🇴",
    "Korea Republic": "🇰🇷",
    "Mexico": "🇲🇽",
    "Morocco": "🇲🇦",
    "Netherlands": "🇳🇱",
    "New Zealand": "🇳🇿",
    "Norway": "🇳🇴",
    "Panama": "🇵🇦",
    "Paraguay": "🇵🇾",
    "Portugal": "🇵🇹",
    "Qatar": "🇶🇦",
    "Saudi Arabia": "🇸🇦",
    "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "Senegal": "🇸🇳",
    "South Africa": "🇿🇦",
    "Spain": "🇪🇸",
    "Sweden": "🇸🇪",
    "Switzerland": "🇨🇭",
    "Tunisia": "🇹🇳",
    "Turkey": "🇹🇷",
    "USA": "🇺🇸",
    "Uruguay": "🇺🇾",
    "Uzbekistan": "🇺🇿",
}


def flag(canonical: str) -> str:
    return FLAGS.get(canonical, "🏳️")
