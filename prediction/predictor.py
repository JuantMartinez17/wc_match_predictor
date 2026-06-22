"""
prediction/predictor.py
=======================
Orquestador. Combina features (Elo, fuerza ajustada por rival, disponibilidad,
contexto) con un modelo de marcador y la simulación Monte Carlo para producir
la predicción final de un partido, con explicación de los factores influyentes.

Flujo:
  1. Elo histórico + tendencia (sobre todo el historial).
  2. Ventana de entrenamiento = partidos en los últimos `max_months`.
  3. Pesos = decaimiento temporal * importancia.
  4. GLM de fuerza ofensiva/defensiva (con shrinkage hacia Elo) -> lambda base.
  5. Ajustes secundarios acotados (disponibilidad, valor, DT, H2H).
  6. Matriz de marcadores (modelo elegido) -> Monte Carlo -> 1X2 + marcadores.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, Config, DixonColesConfig
from data.loader import validate_matches, validate_metadata
from features.availability import availability_score, describe_absences
from features.context import (
    coach_multiplier,
    fatigue_multiplier,
    head_to_head_adjustment,
    rest_days,
    squad_value_multiplier,
)
from features.decay import combined_weights
from features.elo import compute_elo_history, elo_trend, elo_win_probabilities
from features.strength import StrengthModel
from models.base import ScoreModel, outcome_probabilities, top_scorelines
from models.bivariate_poisson import BivariatePoissonModel
from models.dixon_coles import DixonColesModel
from models.poisson_simple import SimplePoissonModel
from simulation.montecarlo import simulate

_MODELS = {
    "dixon_coles": "dixon_coles",
    "bivariate_poisson": "bivariate_poisson",
    "poisson_simple": "poisson_simple",
}

# Máximo de fechas de referencia con artefactos de ventana cacheados.
_WINDOW_CACHE_MAX = 64


@dataclass
class _WindowArtifacts:
    """Artefactos derivados de la ventana de entrenamiento de una fecha.

    Dependen únicamente de la fecha de referencia (no de los equipos), por lo
    que se cachean por día: el fit del GLM es el costo dominante por predicción.

    Solo se retiene lo necesario para predecir: el modelo de fuerza ya ajustado
    y el rho de Dixon-Coles ya estimado. No se guardan `train`/`weights` (la
    ventana de partidos): solo harían falta para estimar rho, que ya viene hecho.
    Evitarlos ahorra ~15 MB con la caché de ventanas llena.
    """

    strength: StrengthModel
    rho: float | None  # rho de Dixon-Coles estimado en esta ventana; None si no se estimó


@dataclass
class Prediction:
    team_a: str
    team_b: str
    p_a: float
    p_draw: float
    p_b: float
    expected_goals_a: float
    expected_goals_b: float
    top_scorelines: list[tuple[int, int, float]]
    explanation: dict = field(default_factory=dict)
    model_name: str = ""

    def format_report(self) -> str:
        """Genera el reporte de texto con el formato de salida solicitado."""
        lines = []
        lines.append(f"PARTIDO: {self.team_a} vs {self.team_b}   [modelo: {self.model_name}]")
        lines.append("=" * 56)
        lines.append("Probabilidades")
        lines.append(f"  Victoria {self.team_a}: {self.p_a * 100:5.1f}%")
        lines.append(f"  Empate:            {self.p_draw * 100:5.1f}%")
        lines.append(f"  Victoria {self.team_b}: {self.p_b * 100:5.1f}%")
        lines.append("")
        lines.append("Goles esperados")
        lines.append(f"  {self.team_a}: {self.expected_goals_a:.2f}")
        lines.append(f"  {self.team_b}: {self.expected_goals_b:.2f}")
        lines.append("")
        lines.append("Marcadores más probables")
        for n, (ga, gb, p) in enumerate(self.top_scorelines, 1):
            lines.append(f"  {n:2d}. {ga}-{gb}  ({p * 100:4.1f}%)")
        lines.append("")
        lines.append("Explicación (factores de mayor influencia)")
        for k, v in self.explanation.get("drivers", []):
            lines.append(f"  - {k}: {v}")
        return "\n".join(lines)


class MatchPredictor:
    """Predictor de partidos de selección para Copa del Mundo."""

    def __init__(
        self,
        matches: pd.DataFrame,
        metadata: pd.DataFrame | None = None,
        config: Config = DEFAULT_CONFIG,
        elo_state: tuple[dict[str, float], pd.DataFrame] | None = None,
    ) -> None:
        self.cfg = config
        self.matches = validate_matches(matches)
        self.metadata = validate_metadata(metadata) if metadata is not None else None
        # Elo histórico. Normalmente se computa una vez sobre todo el historial;
        # en backtests walk-forward se puede inyectar un estado ya avanzado a la
        # fecha (ratings as-of-fecha + timeline) para no recomputarlo por fecha.
        if elo_state is not None:
            self.ratings, self.elo_timeline = elo_state
        else:
            self.ratings, self.elo_timeline = compute_elo_history(
                self.matches, self.cfg.elo, self.cfg.importance
            )
        self._last_matrix = None
        self._last_rho: float = self.cfg.dixon_coles.rho
        # Caché de artefactos de ventana por fecha (asume self.matches inmutable).
        self._window_cache: OrderedDict[pd.Timestamp, _WindowArtifacts] = OrderedDict()
        self._window_lock = threading.Lock()

    # ---------------------------------------------------------------- model
    def _build_model(
        self,
        name: str,
        rho: float | None = None,
    ) -> ScoreModel:
        """Construye el modelo de marcador. `rho` ya estimado en la ventana."""
        if name == "dixon_coles":
            dc_cfg = self.cfg.dixon_coles
            if dc_cfg.estimate_rho and rho is not None:
                # DixonColesConfig es frozen -> instancia nueva con rho estimado.
                dc_cfg = DixonColesConfig(
                    rho=rho, estimate_rho=False, rho_bounds=dc_cfg.rho_bounds
                )
            self._last_rho = dc_cfg.rho
            return DixonColesModel(dc_cfg)
        if name == "bivariate_poisson":
            return BivariatePoissonModel(self.cfg.bivariate)
        if name == "poisson_simple":
            return SimplePoissonModel()
        raise ValueError(f"Modelo desconocido: {name}. Opciones: {list(_MODELS)}")

    def _training_window(self, reference_date: pd.Timestamp) -> pd.DataFrame:
        """Partidos dentro de la ventana dura de `max_months` antes del partido."""
        ref = pd.Timestamp(reference_date)
        cutoff = ref - pd.DateOffset(months=self.cfg.decay.max_months)
        mask = (self.matches["date"] >= cutoff) & (self.matches["date"] < ref)
        return self.matches.loc[mask].reset_index(drop=True)

    def _window_artifacts(self, ref: pd.Timestamp) -> _WindowArtifacts:
        """
        Ventana de entrenamiento + GLM de fuerza + rho DC, cacheados por fecha
        (granularidad día). El fit del GLM depende sólo de la fecha de
        referencia, así que requests sucesivos a la misma fecha lo reutilizan.

        El fit se mantiene bajo el lock a propósito: dos requests concurrentes
        a la misma fecha no deben pagar el fit dos veces.
        """
        key = pd.Timestamp(ref).normalize()
        with self._window_lock:
            cached = self._window_cache.get(key)
            if cached is not None:
                self._window_cache.move_to_end(key)
                return cached

            train = self._training_window(key)
            weights = combined_weights(train, key, self.cfg.decay, self.cfg.importance)
            strength = StrengthModel(self.cfg.strength, self.cfg.elo).fit(train, weights)
            rho = None
            if self.cfg.dixon_coles.estimate_rho:
                rho = strength.estimate_dixon_coles_rho(
                    train,
                    weights,
                    bounds=self.cfg.dixon_coles.rho_bounds,
                    default=self.cfg.dixon_coles.rho,
                )
            art = _WindowArtifacts(strength=strength, rho=rho)
            self._window_cache[key] = art
            while len(self._window_cache) > _WINDOW_CACHE_MAX:
                self._window_cache.popitem(last=False)
            return art

    def warm_window(self, reference_date: str | pd.Timestamp) -> None:
        """Pre-ajusta y cachea el modelo de fuerza para una fecha dada."""
        self._window_artifacts(pd.Timestamp(reference_date))

    # ---------------------------------------------------------- core común
    def _match_core(
        self,
        team_a: str,
        team_b: str,
        ref: pd.Timestamp,
        neutral: bool,
        home_team: str | None,
        absences_a: pd.DataFrame | None,
        absences_b: pd.DataFrame | None,
        model: str,
        squad_value_a: float | None = None,
        squad_value_b: float | None = None,
    ) -> dict:
        """
        Calcula lambdas finales, modelo de marcador y matriz conjunta para un
        partido. Reutilizado por `predict` (resultado a 90') y `predict_knockout`.
        """
        art = self._window_artifacts(ref)
        strength = art.strength
        lam_a, lam_b = strength.expected_goals(team_a, team_b, self.ratings, neutral, home_team)
        base_la, base_lb = lam_a, lam_b

        sec = self.cfg.secondary
        avail_a = availability_score(absences_a)
        avail_b = availability_score(absences_b)
        lam_a *= 1.0 - sec.availability_sensitivity * (1.0 - avail_a)
        lam_b *= 1.0 - sec.availability_sensitivity * (1.0 - avail_b)

        m_val_a = m_val_b = 1.0
        m_coach_a = m_coach_b = 1.0
        # squad_value_a/b override: valor real del 11 inicial (o plantilla real).
        # Si no se provee, se usa el valor de metadata.
        _va = squad_value_a
        _vb = squad_value_b
        if _va is None and self.metadata is not None and team_a in self.metadata.index:
            _va = float(self.metadata.loc[team_a, "squad_value_m"])
        if _vb is None and self.metadata is not None and team_b in self.metadata.index:
            _vb = float(self.metadata.loc[team_b, "squad_value_m"])
        if _va is not None and _vb is not None:
            m_val_a, m_val_b = squad_value_multiplier(_va, _vb, sec)
        # Factor entrenador: solo si la metadata trae datos del DT para ambos
        # equipos. Con metadata real (ratings FIFA) no hay columnas de DT, así
        # que coach_multiplier devuelve (1.0, 1.0) y el factor queda neutro.
        if (
            self.metadata is not None
            and team_a in self.metadata.index
            and team_b in self.metadata.index
        ):
            m_coach_a, m_coach_b = coach_multiplier(
                self.metadata.loc[team_a].to_dict(),
                self.metadata.loc[team_b].to_dict(),
                sec,
            )
        lam_a *= m_val_a * m_coach_a
        lam_b *= m_val_b * m_coach_b

        m_h2h_a, m_h2h_b = head_to_head_adjustment(self.matches, team_a, team_b, ref, sec)
        lam_a *= m_h2h_a
        lam_b *= m_h2h_b

        # Factor de forma: tendencia Elo reciente relativa. Desactivado salvo
        # form_sensitivity>0 (se valida por backtest; ver config).
        m_form_a = m_form_b = 1.0
        if sec.form_sensitivity > 0:
            trend_a = elo_trend(self.elo_timeline, team_a, ref)
            trend_b = elo_trend(self.elo_timeline, team_b, ref)
            form_adj = sec.form_sensitivity * np.tanh((trend_a - trend_b) / 150.0)
            m_form_a = float(np.exp(form_adj))
            m_form_b = float(np.exp(-form_adj))
        lam_a *= m_form_a
        lam_b *= m_form_b

        # Factor de fatiga: descanso relativo (días desde el último partido).
        # Desactivado salvo fatigue_sensitivity>0 (se valida por backtest; ver config).
        m_fat_a = m_fat_b = 1.0
        if sec.fatigue_sensitivity > 0:
            rest_a = rest_days(self.matches, team_a, ref, sec.fatigue_max_days)
            rest_b = rest_days(self.matches, team_b, ref, sec.fatigue_max_days)
            m_fat_a, m_fat_b = fatigue_multiplier(rest_a, rest_b, sec)
        lam_a *= m_fat_a
        lam_b *= m_fat_b

        lam_a = max(lam_a, 0.05)
        lam_b = max(lam_b, 0.05)

        score_model = self._build_model(model, rho=art.rho)
        matrix = score_model.score_matrix(lam_a, lam_b, self.cfg.simulation.max_goals)
        self._last_matrix = matrix

        return {
            "lam_a": lam_a, "lam_b": lam_b, "base_la": base_la, "base_lb": base_lb,
            "avail_a": avail_a, "avail_b": avail_b,
            "m_val_a": m_val_a, "m_coach_a": m_coach_a, "m_h2h_a": m_h2h_a,
            "m_form_a": m_form_a,
            "strength": strength, "score_model": score_model, "matrix": matrix,
        }

    def _ensemble_elo(
        self,
        p_a: float,
        p_draw: float,
        p_b: float,
        team_a: str,
        team_b: str,
        neutral: bool,
        home_team: str | None,
    ) -> tuple[float, float, float]:
        """
        Mezcla las probabilidades 1X2 del modelo de marcador con las del Elo puro
        (peso `elo_ensemble_weight`). Reduce varianza en muestras chicas/ruidosas.
        Validado por backtest (DC+elo, w=0.5). w=0 deja las probs del modelo intactas.
        """
        w = self.cfg.strength.elo_ensemble_weight
        if w <= 0:
            return p_a, p_draw, p_b
        ra = self.ratings.get(team_a, self.cfg.elo.base_rating)
        rb = self.ratings.get(team_b, self.cfg.elo.base_rating)
        e_a, e_draw, e_b = elo_win_probabilities(
            ra, rb, self.cfg.elo, home_team=home_team, team_a=team_a, neutral=neutral
        )
        pa = (1.0 - w) * p_a + w * e_a
        pd_ = (1.0 - w) * p_draw + w * e_draw
        pb = (1.0 - w) * p_b + w * e_b
        total = pa + pd_ + pb
        return pa / total, pd_ / total, pb / total

    # -------------------------------------------------------------- predict
    def predict(
        self,
        team_a: str,
        team_b: str,
        reference_date: str | pd.Timestamp,
        neutral: bool = True,
        home_team: str | None = None,
        absences_a: pd.DataFrame | None = None,
        absences_b: pd.DataFrame | None = None,
        model: str = "dixon_coles",
        use_simulation: bool = True,
        squad_value_a: float | None = None,
        squad_value_b: float | None = None,
    ) -> Prediction:
        """
        Predice un partido. `reference_date` es la fecha del encuentro (sólo se
        usan datos anteriores). En Mundial usar neutral=True salvo para el/los
        anfitrión(es), donde neutral=False y home_team = anfitrión.

        squad_value_a/b: valor del 11 inicial en M EUR (override del metadata).
            Si se provee, reemplaza el squad_value_m sintético. Usar cuando el
            lineup está confirmado (sum de valores Transfermarkt de los titulares).
        """
        ref = pd.Timestamp(reference_date)
        core = self._match_core(
            team_a, team_b, ref, neutral, home_team, absences_a, absences_b, model,
            squad_value_a=squad_value_a, squad_value_b=squad_value_b,
        )
        lam_a, lam_b, matrix = core["lam_a"], core["lam_b"], core["matrix"]
        score_model = core["score_model"]

        if use_simulation:
            sim = simulate(
                matrix,
                n_simulations=self.cfg.simulation.n_simulations,
                seed=self.cfg.simulation.random_seed,
            )
            p_a, p_draw, p_b = sim.p_home, sim.p_draw, sim.p_away
            tops = sim.top_scorelines
        else:
            # Camino exacto (rápido, determinista) para backtesting masivo.
            p_a, p_draw, p_b = outcome_probabilities(matrix)
            tops = top_scorelines(matrix, k=10)

        p_a, p_draw, p_b = self._ensemble_elo(
            p_a, p_draw, p_b, team_a, team_b, neutral, home_team
        )

        explanation = self._explain(
            team_a, team_b, ref, core["base_la"], core["base_lb"], lam_a, lam_b,
            core["avail_a"], core["avail_b"], absences_a, absences_b,
            core["m_val_a"], core["m_coach_a"], core["m_h2h_a"], core["m_form_a"],
            core["strength"],
        )

        return Prediction(
            team_a=team_a,
            team_b=team_b,
            p_a=p_a,
            p_draw=p_draw,
            p_b=p_b,
            expected_goals_a=lam_a,
            expected_goals_b=lam_b,
            top_scorelines=tops,
            explanation=explanation,
            model_name=score_model.name,
        )

    # ------------------------------------------------------------ knockout
    def predict_knockout(
        self,
        team_a: str,
        team_b: str,
        reference_date: str | pd.Timestamp,
        neutral: bool = True,
        home_team: str | None = None,
        absences_a: pd.DataFrame | None = None,
        absences_b: pd.DataFrame | None = None,
        model: str = "dixon_coles",
        squad_value_a: float | None = None,
        squad_value_b: float | None = None,
    ) -> dict:
        """
        Predicción para partido de ELIMINATORIA: probabilidad de que cada equipo
        AVANCE, modelando los 90', luego prórroga y luego penales.

        - 90': distribución de marcadores del modelo elegido.
        - Si hay empate en los 90' (prob p_draw), se juega prórroga: se asume
          que las tasas de gol escalan por `extra_time_fraction` (30'/90').
        - Si persiste el empate tras la prórroga, penales: probabilidad base
          0.5 inclinada levemente por Elo (`penalty_elo_tilt`).

        Returns
        -------
        dict con probabilidades de regulación y de avance, y goles esperados.
        """
        ref = pd.Timestamp(reference_date)
        core = self._match_core(
            team_a, team_b, ref, neutral, home_team, absences_a, absences_b, model,
            squad_value_a=squad_value_a, squad_value_b=squad_value_b,
        )
        matrix = core["matrix"]
        p_a_reg, p_draw_reg, p_b_reg = outcome_probabilities(matrix)
        p_a_reg, p_draw_reg, p_b_reg = self._ensemble_elo(
            p_a_reg, p_draw_reg, p_b_reg, team_a, team_b, neutral, home_team
        )

        # ----- Prórroga: mismo modelo con tasas reducidas -----
        kcfg = self.cfg.knockout
        et_model = core["score_model"]
        et_matrix = et_model.score_matrix(
            core["lam_a"] * kcfg.extra_time_fraction,
            core["lam_b"] * kcfg.extra_time_fraction,
            self.cfg.simulation.max_goals,
        )
        p_a_et, p_draw_et, p_b_et = outcome_probabilities(et_matrix)

        # ----- Penales: 0.5 +/- inclinación por Elo (acotada) -----
        ra = self.ratings.get(team_a, self.cfg.elo.base_rating)
        rb = self.ratings.get(team_b, self.cfg.elo.base_rating)
        tilt = kcfg.penalty_elo_tilt * np.tanh((ra - rb) / 400.0)
        p_a_pen = float(np.clip(kcfg.penalty_base + tilt, 0.05, 0.95))

        # ----- Composición -----
        p_a_advance = p_a_reg + p_draw_reg * (p_a_et + p_draw_et * p_a_pen)
        p_b_advance = p_b_reg + p_draw_reg * (p_b_et + p_draw_et * (1.0 - p_a_pen))
        total = p_a_advance + p_b_advance
        p_a_advance, p_b_advance = p_a_advance / total, p_b_advance / total

        # Predicción completa de los 90' (marcadores + explicación), con el
        # mismo formato que `predict`. La clave "regulation" se mantiene como
        # dict por compatibilidad con el CLI.
        explanation = self._explain(
            team_a, team_b, ref, core["base_la"], core["base_lb"],
            core["lam_a"], core["lam_b"], core["avail_a"], core["avail_b"],
            absences_a, absences_b,
            core["m_val_a"], core["m_coach_a"], core["m_h2h_a"], core["m_form_a"],
            core["strength"],
        )
        prediction = Prediction(
            team_a=team_a,
            team_b=team_b,
            p_a=p_a_reg,
            p_draw=p_draw_reg,
            p_b=p_b_reg,
            expected_goals_a=core["lam_a"],
            expected_goals_b=core["lam_b"],
            top_scorelines=top_scorelines(matrix, k=10),
            explanation=explanation,
            model_name=core["score_model"].name,
        )

        return {
            "team_a": team_a,
            "team_b": team_b,
            "regulation": {"p_a": p_a_reg, "p_draw": p_draw_reg, "p_b": p_b_reg},
            "prediction": prediction,
            "p_advance_a": p_a_advance,
            "p_advance_b": p_b_advance,
            "p_penalties": p_draw_reg * p_draw_et,
            "expected_goals": (core["lam_a"], core["lam_b"]),
            "model_name": core["score_model"].name,
        }

    # -------------------------------------------------------------- explain
    def _explain(
        self, team_a, team_b, ref, base_la, base_lb, lam_a, lam_b,
        avail_a, avail_b, abs_a, abs_b, m_val_a, m_coach_a, m_h2h_a, m_form_a, strength,
    ) -> dict:
        """Construye una explicación ordenada por magnitud de efecto."""
        ra = self.ratings.get(team_a, self.cfg.elo.base_rating)
        rb = self.ratings.get(team_b, self.cfg.elo.base_rating)
        trend_a = elo_trend(self.elo_timeline, team_a, ref)
        trend_b = elo_trend(self.elo_timeline, team_b, ref)

        # Magnitud (en log) de cada ajuste secundario sobre la ventaja de A.
        effects = {
            "Elo (fuerza base)": abs(np.log((base_la / base_lb) if base_lb > 0 else 1.0)),
            "Disponibilidad": abs(np.log((1 - self.cfg.secondary.availability_sensitivity * (1 - avail_a))
                                         / (1 - self.cfg.secondary.availability_sensitivity * (1 - avail_b)))),
            "Valor de plantilla": abs(np.log(m_val_a ** 2)),
            "Forma reciente": abs(np.log(m_form_a ** 2)),
            "Entrenador": abs(np.log(m_coach_a ** 2)),
            "Historial directo": abs(np.log(m_h2h_a ** 2)),
        }
        drivers = sorted(effects.items(), key=lambda kv: kv[1], reverse=True)
        drivers_fmt = []
        drivers_fmt.append((f"Elo {team_a}", f"{ra:.0f} (tendencia {trend_a:+.0f}/año)"))
        drivers_fmt.append((f"Elo {team_b}", f"{rb:.0f} (tendencia {trend_b:+.0f}/año)"))
        for name, mag in drivers[:3]:
            drivers_fmt.append((name, f"efecto relativo {mag:.3f} (log)"))
        drivers_fmt.append((f"Bajas {team_a}", describe_absences(abs_a)))
        drivers_fmt.append((f"Bajas {team_b}", describe_absences(abs_b)))

        return {
            "elo_a": ra,
            "elo_b": rb,
            "trend_a": trend_a,
            "trend_b": trend_b,
            "lambda_base": (base_la, base_lb),
            "lambda_final": (lam_a, lam_b),
            "availability": (avail_a, avail_b),
            "drivers": drivers_fmt,
        }
