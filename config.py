"""
config.py
=========
Hiperparámetros centralizados del sistema de predicción.

Todos los valores son configurables. Los defaults provienen de la literatura
de analítica futbolística (Dixon & Coles 1997; Karlis & Ntzoufras 2003;
Hvattum & Arntzen 2010 para Elo) y de calibraciones empíricas razonables.
Para producción, estos parámetros deberían re-optimizarse por validación
cruzada temporal (ver validation/backtest.py).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DecayConfig:
    """Parámetros del decaimiento temporal exponencial."""

    # lambda del decaimiento: peso = exp(-lambda_decay * antiguedad_anios).
    # Con 0.40 un partido de hace 12 meses pesa ~0.67, y uno de hace 24 meses ~0.45
    # (olvido más lento -> más datos efectivos, útil con selecciones).
    # Valor optimizado por backtest train/holdout (scripts/tune_wc.py).
    lambda_decay: float = 0.40
    # Ventana dura máxima de partidos considerados.
    max_matches: int = 20
    # Ventana dura máxima en meses.
    max_months: int = 24
    # Boost de recencia "in-torneo": pondera extra los partidos de un torneo
    # mayor EN CURSO (mismos últimos `intratournament_days` y competición de tier
    # alto). Captura la forma/fitness/ajuste táctico del torneo actual, que el
    # decay temporal solo no distingue de un amistoso reciente. 1.0 = desactivado
    # (default neutro hasta validar por backtest; ver scripts/tune_wc.py).
    intratournament_boost: float = 1.0
    intratournament_days: int = 45
    intratournament_competitions: tuple = ("world_cup", "continental_cup")


@dataclass(frozen=True)
class MatchImportanceConfig:
    """
    Peso por tipo de competición. Un amistoso aporta MUCHO menos información
    que un partido competitivo: los equipos rotan, prueban y no compiten al 100%.
    Esta ponderación suele tener más poder predictivo que varias de las
    variables 'de contexto' del enunciado.
    """

    weights: dict = field(
        default_factory=lambda: {
            "world_cup": 1.00,
            "continental_cup": 0.95,  # Euro, Copa América
            "qualifier": 0.85,
            "nations_league": 0.80,
            "friendly": 0.45,
        }
    )
    default: float = 0.60


@dataclass(frozen=True)
class EloConfig:
    """Parámetros del rating Elo (World Football Elo style)."""

    base_rating: float = 1500.0
    # K base; se escala por importancia del partido y margen de goles.
    k_base: float = 40.0
    home_advantage: float = 65.0  # puntos Elo de ventaja de localía
    # Divisor de la curva logística estándar de Elo.
    scale: float = 400.0


@dataclass(frozen=True)
class StrengthConfig:
    """Modelo de fuerza ofensiva/defensiva ajustada por rival."""

    # Peso asignado al PRIOR derivado de Elo en la mezcla geométrica con el GLM:
    # log(lambda) = (1 - blend)*log(lambda_GLM) + blend*log(lambda_Elo).
    # blend=0.0 -> sólo GLM ; blend=1.0 -> sólo Elo. Actúa como shrinkage ante
    # muestras pequeñas (clave en selecciones, ~20 partidos).
    # Valor optimizado por backtest train/holdout (scripts/tune_wc.py).
    elo_prior_blend: float = 0.50
    # Goles esperados de referencia por equipo en partido neutro/promedio.
    league_avg_goals: float = 1.35
    # Exponente que mapea la superioridad Elo (en [-0.5, 0.5]) a la ventaja
    # multiplicativa de goles del prior: lambda_Elo = league_avg * exp(exp * sup).
    # Mayor -> el prior Elo separa más a favoritos/débiles. Optimizado por backtest.
    elo_supremacy_exponent: float = 2.0
    # Ensemble a nivel de PROBABILIDAD 1X2: mezcla la salida del modelo de marcador
    # con la del Elo puro -> p = (1-w)*p_modelo + w*p_elo (renormalizado). Reduce
    # varianza en muestras chicas/ruidosas (Mundial). Validado por backtest: mejora
    # RPS/accuracy/log-loss en holdout 2022 y en el pool 2010-2022 (DC+elo, w=0.5).
    # 0.0 = solo modelo de marcador (comportamiento previo).
    elo_ensemble_weight: float = 0.5


@dataclass(frozen=True)
class BivariateConfig:
    """Parámetros del Poisson Bivariado (Karlis & Ntzoufras)."""

    # Parámetro de dependencia lambda3 (covarianza). En fútbol la dependencia
    # real es leve; lambda3 está acotado a [0, min(lambda1, lambda2)].
    lambda3_default: float = 0.12
    # Si True, intenta estimar lambda3 por máxima verosimilitud en backtest.
    estimate_lambda3: bool = False


@dataclass(frozen=True)
class DixonColesConfig:
    """Parámetro de corrección de marcadores bajos."""

    # rho ligeramente negativo: corrige el exceso/defecto de 0-0,1-0,0-1,1-1.
    # Se usa como valor por defecto / fallback; si estimate_rho=True se estima
    # por máxima verosimilitud ponderada sobre la ventana de entrenamiento.
    rho: float = -0.08
    estimate_rho: bool = True
    # Cota dura de rho durante la estimación (estabilidad numérica de tau).
    rho_bounds: tuple = (-0.20, 0.20)


@dataclass(frozen=True)
class SimulationConfig:
    n_simulations: int = 100_000
    max_goals: int = 12  # truncado de la grilla de marcadores
    random_seed: int = 42


@dataclass(frozen=True)
class KnockoutConfig:
    """Parámetros del modo eliminatoria (prórroga + penales)."""

    # Duración de la prórroga relativa a los 90'. ET = 30' -> 1/3 de la tasa.
    extra_time_fraction: float = 1.0 / 3.0
    # Probabilidad base de que el equipo A gane la tanda de penales (0.5 = parejo).
    # Se puede inclinar levemente por Elo con penalty_elo_tilt.
    penalty_base: float = 0.5
    # Inclinación máxima por superioridad Elo en la tanda (acotada y pequeña:
    # la evidencia de 'habilidad de penales' sostenida es débil).
    penalty_elo_tilt: float = 0.10


@dataclass(frozen=True)
class SecondaryWeights:
    """
    Ajustes secundarios (multiplicativos sobre lambda). Acotados a rangos
    estrechos para que NUNCA dominen sobre forma/Elo, según principio de diseño.
    """

    # Sensibilidad del Availability Score sobre lambda ofensivo del equipo.
    availability_sensitivity: float = 0.25
    # Sensibilidad del valor de plantilla (variable secundaria).
    squad_value_sensitivity: float = 0.10
    # Sensibilidad del factor de forma (tendencia Elo reciente). 0.0 = desactivado.
    # adj = sens * tanh((trend_a - trend_b) / 150). Activado en 0.10: el backtest
    # train/holdout (scripts/tune_wc.py) mostró mejora consistente al incorporarlo.
    form_sensitivity: float = 0.10
    # Sensibilidad del factor entrenador (muy baja: señal débil y redundante).
    coach_sensitivity: float = 0.04
    # Peso del historial directo como pequeño ajuste del prior (muy bajo).
    h2h_weight: float = 0.05
    # Sensibilidad de la fatiga (días de descanso relativos). El equipo más
    # descansado recibe un leve empujón ofensivo; acotado por tanh. Los descansos
    # se topean a `fatigue_max_days` (más allá, equipo "fresco": sin congestión,
    # típico fuera de torneos). 0.0 = desactivado (default neutro hasta validar).
    fatigue_sensitivity: float = 0.0
    fatigue_max_days: int = 14


@dataclass(frozen=True)
class Config:
    decay: DecayConfig = field(default_factory=DecayConfig)
    importance: MatchImportanceConfig = field(default_factory=MatchImportanceConfig)
    elo: EloConfig = field(default_factory=EloConfig)
    strength: StrengthConfig = field(default_factory=StrengthConfig)
    bivariate: BivariateConfig = field(default_factory=BivariateConfig)
    dixon_coles: DixonColesConfig = field(default_factory=DixonColesConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    knockout: KnockoutConfig = field(default_factory=KnockoutConfig)
    secondary: SecondaryWeights = field(default_factory=SecondaryWeights)


# Instancia por defecto reutilizable.
DEFAULT_CONFIG = Config()
