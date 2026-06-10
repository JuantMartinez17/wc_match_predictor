# Predictor de partidos — Copa del Mundo 2026

Modelo de probabilidades 1X2 calibradas y explicables para los **48 equipos del Mundial 2026**, basado en datos históricos reales y valoración real de plantillas.

Motor: **Elo + fuerza ofensiva/defensiva ajustada por rival (GLM Poisson con shrinkage) + modelo de marcador (Dixon-Coles / Poisson bivariado) + simulación Monte Carlo**, con backtesting walk-forward.

---

## Instalación

```bash
python -m pip install -r requirements.txt
```

---

## Uso desde consola

### Modo interactivo (recomendado)

```bash
python predict.py
```

Pregunta los dos equipos, la fecha y si es eliminatoria. Acepta nombres en español o inglés.

### Directo con argumentos

```bash
# Partido de fase de grupos
python predict.py "México" "Panamá" --date 2026-06-15

# Acepta nombres en español, inglés, minúsculas o parciales
python predict.py "alemania" "brasil"
python predict.py "corea" "japón"

# Modo eliminatoria (prórroga + penales)
python predict.py "Argentina" "Francia" --knockout

# Ver los 48 equipos clasificados
python predict.py --list

# Cambiar modelo de marcador
python predict.py "España" "Alemania" --model poisson_simple
# Modelos: dixon_coles (default) | bivariate_poisson | poisson_simple
```

### Ventaja de local

Se aplica automáticamente cuando uno de los equipos es **México, Estados Unidos o Canadá** (sedes del torneo) y el rival no lo es. En cualquier otro caso se considera cancha neutral.

### Valoración de plantilla

El predictor obtiene automáticamente los valores de mercado (Transfermarkt vía SofaScore):

- **Si el 11 inicial ya está confirmado** (~1h antes del partido): usa la suma de los valores de los titulares.
- **Si el lineup no está disponible**: estima el XI como el 55% del valor total del plantel.
- **Sin conexión**: cae a valores sintéticos sin interrumpir la predicción.

El resultado siempre indica qué fuente se usó:

```
[Plantilla México: XI confirmado (11 jugadores, 342M EUR)]
[Plantilla Panamá: plantel completo (89M EUR, XI estimado)]
```

### Gestión de datos

```bash
# Descargar/actualizar resultados históricos (caché 24h)
python -m data.ingest
python -m data.ingest --refresh        # fuerza re-descarga

# Consultar valores de plantilla de un equipo
python -m data.players "Argentina"

# Consultar lineup confirmado de un partido
python -m data.lineups "Argentina" "Francia" 2026-06-15

# Demo completa con datos reales (predicción + backtest + calibración)
python main.py --real
python main.py --real --refresh
python main.py                          # versión sintética, no requiere red
```

---

## Arquitectura

```
wc_match_predictor/
├── config.py                  # Hiperparámetros (decay, Elo, blend, rho, MC...)
├── predict.py                 # CLI principal — modo interactivo y por argumentos
├── main.py                    # Demo end-to-end (predicción + backtest + calibración)
├── data/
│   ├── ingest.py              # Resultados históricos (martj42/international_results)
│   ├── players.py             # Valores de mercado por jugador (SofaScore/Transfermarkt)
│   ├── lineups.py             # 11 inicial confirmado (SofaScore API)
│   ├── loader.py              # Validación y ventaneo temporal
│   └── synthetic.py           # Generador de datos demo
├── features/
│   ├── decay.py               # Decaimiento exponencial + importancia del partido
│   ├── elo.py                 # Elo (margen de gol + importancia) y tendencia
│   ├── strength.py            # Ataque/defensa ajustado por rival (GLM + Elo prior)
│   ├── availability.py        # Availability Score por bajas
│   └── context.py             # Valor de plantilla, DT, H2H (secundarios)
├── models/
│   ├── base.py                # 1X2 y top-marcadores desde la matriz conjunta
│   ├── poisson_simple.py      # Poisson doble independiente (baseline)
│   ├── bivariate_poisson.py   # Karlis-Ntzoufras (λ1, λ2, λ3)
│   ├── dixon_coles.py         # Dixon-Coles con corrección de marcadores bajos
│   └── elo_model.py           # Elo puro (baseline)
├── simulation/montecarlo.py   # Monte Carlo (100k iteraciones) + solución exacta
├── prediction/predictor.py    # Orquestador: combina features, modelo y reporte
└── validation/
    ├── metrics.py             # Log Loss, Brier, RPS, Accuracy
    ├── calibration.py         # Curva de calibración + temperature scaling
    ├── backtest.py            # Walk-forward + comparación de modelos
    └── tuning.py              # Búsqueda en grilla de hiperparámetros
```

---

## Fuentes de datos

| Dato | Fuente | Caché |
|---|---|---|
| Resultados históricos (1872–hoy) | [martj42/international_results](https://github.com/martj42/international_results) (CC BY 4.0) | 24 h |
| Valores de mercado por jugador | SofaScore / Transfermarkt | 7 días |
| 11 inicial confirmado | SofaScore API | 1 h |

Todos los datos se cachean en `data/cache/`. Sin conexión, el sistema usa los últimos datos disponibles o cae a valores sintéticos.

---

## Uso programático

```python
from data.ingest import build_dataset
from data.players import get_squad_values, compute_xi_value
from data.lineups import get_lineup
from data.synthetic import generate_team_metadata
from prediction.predictor import MatchPredictor

matches  = build_dataset(since_year=2018)
metadata = generate_team_metadata()
predictor = MatchPredictor(matches, metadata=metadata)

# Con XI confirmado
lineup = get_lineup("Argentina", "France", "2026-06-28")
squad_a = get_squad_values("Argentina")
squad_b = get_squad_values("France")
xi_a = compute_xi_value(lineup["team_a"], squad_a) if lineup else None
xi_b = compute_xi_value(lineup["team_b"], squad_b) if lineup else None

pred = predictor.predict(
    "Argentina", "France", "2026-06-28",
    neutral=True, model="dixon_coles",
    squad_value_a=xi_a, squad_value_b=xi_b,
)
print(pred.format_report())
```

---

## Decisiones de diseño clave

- **Dixon-Coles como modelo principal**: admite dependencia negativa entre marcadores bajos (0-0, 1-0, 0-1, 1-1), más fiel a los datos de fútbol que Poisson simple.
- **Shrinkage Elo↔GLM** (`config.strength.elo_prior_blend`): imprescindible con ~20 partidos por selección para no sobreajustar.
- **RPS** como métrica rectora del 1X2 (respeta el orden de resultados, penaliza menos los errores en resultados adyacentes).
- **Amistosos ponderados a 0.45** vs. partidos competitivos (1.00 para el Mundial).
- **Valor del XI sobre valor de plantilla**: cuando el lineup está confirmado, usar la suma real de los titulares es más preciso que el total del plantel.
- **H2H, DT y valor de plantilla** entran como ajustes acotados que nunca dominan sobre Elo/forma (ver `config.SecondaryWeights`).

Re-optimizar hiperparámetros con `validation/tuning.py` antes de producción.
