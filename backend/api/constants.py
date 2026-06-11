"""
backend/api/constants.py
========================
Constantes compartidas entre routers: códigos ISO 3166-1 alpha-2 de banderas.
Los valores se usan como código para flagcdn.com (ej. "ar" → flagcdn.com/w80/ar.png).
England y Scotland usan subdivisiones de GB soportadas por flagcdn.
"""

# ISO2 codes para los 48 equipos del Mundial 2026
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
