"""
data/loader.py
==============
Carga y validación de datos crudos. Define el contrato de columnas que el
resto del sistema espera y normaliza tipos. En producción, las funciones
`load_*` leerían CSV/Parquet/API; aquí validan un DataFrame ya provisto.
"""

from __future__ import annotations

import pandas as pd


REQUIRED_MATCH_COLUMNS = {
    "date",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
    "competition",
    "neutral",
}


class DataValidationError(ValueError):
    """Error de validación de datos de entrada."""


def validate_matches(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valida y normaliza el historial de partidos.

    Raises
    ------
    DataValidationError
        Si faltan columnas o hay tipos/valores inválidos.
    """
    if df is None or len(df) == 0:
        raise DataValidationError("El historial de partidos está vacío.")

    missing = REQUIRED_MATCH_COLUMNS - set(df.columns)
    if missing:
        raise DataValidationError(f"Faltan columnas en matches: {sorted(missing)}")

    out = df.copy()
    try:
        out["date"] = pd.to_datetime(out["date"])
    except Exception as exc:  # noqa: BLE001
        raise DataValidationError(f"Columna 'date' no convertible a fecha: {exc}") from exc

    for col in ("home_goals", "away_goals"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
        if out[col].isna().any():
            raise DataValidationError(f"Valores no numéricos en '{col}'.")
        if (out[col] < 0).any():
            raise DataValidationError(f"Goles negativos en '{col}'.")
        out[col] = out[col].astype(int)

    out["neutral"] = out["neutral"].astype(bool)
    out["competition"] = out["competition"].astype(str)
    out["home_team"] = out["home_team"].astype(str)
    out["away_team"] = out["away_team"].astype(str)

    if (out["home_team"] == out["away_team"]).any():
        raise DataValidationError("Hay partidos con el mismo equipo de local y visitante.")

    return out.sort_values("date").reset_index(drop=True)


def validate_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Valida metadatos por equipo (valor de plantilla, entrenador)."""
    required = {"team", "squad_value_m"}
    missing = required - set(df.columns)
    if missing:
        raise DataValidationError(f"Faltan columnas en metadata: {sorted(missing)}")
    out = df.copy()
    out["team"] = out["team"].astype(str)
    return out.set_index("team")


def filter_recent(
    matches: pd.DataFrame,
    team: str,
    reference_date: pd.Timestamp,
    max_matches: int,
    max_months: int,
) -> pd.DataFrame:
    """
    Devuelve los partidos recientes de un equipo respetando AMBAS ventanas
    (cantidad y antigüedad). Implementa el principio: nada con >24 meses.
    """
    ref = pd.Timestamp(reference_date)
    cutoff = ref - pd.DateOffset(months=max_months)
    mask = (
        ((matches["home_team"] == team) | (matches["away_team"] == team))
        & (matches["date"] < ref)
        & (matches["date"] >= cutoff)
    )
    subset = matches.loc[mask].sort_values("date", ascending=False)
    return subset.head(max_matches).reset_index(drop=True)
