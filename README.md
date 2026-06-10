# Sistema de predicción de partidos — Copa del Mundo

Modelo de probabilidades 1X2 calibradas y explicables para selecciones, basado en
**Elo + fuerza ofensiva/defensiva ajustada por rival (GLM Poisson ponderado con
shrinkage) + modelo de marcador (Dixon-Coles / Poisson bivariado) + simulación
Monte Carlo**, con backtesting walk-forward.

## Instalación

```bash
pip install -r requirements.txt
python main.py        # demo end-to-end con datos sintéticos
```

> Los datos de `data/synthetic.py` son **de juguete**, sólo para que el pipeline
> corra. El rendimiento real depende de reemplazarlos por datos reales:
> resultados oficiales + Elo (eloratings.net), valores de plantilla
> (Transfermarkt) y partes médicos/suspensiones.

## Arquitectura

```
worldcup_predictor/
├── config.py                 # Hiperparámetros (decay, Elo, blend, rho, MC...)
├── data/
│   ├── loader.py             # Validación y ventaneo temporal
│   └── synthetic.py          # Generador de datos demo (reemplazar)
├── features/
│   ├── decay.py              # Decaimiento exponencial + importancia del partido
│   ├── elo.py                # Elo (margen de gol + importancia) y tendencia
│   ├── strength.py           # Ataque/defensa ajustado por rival (GLM + Elo)
│   ├── availability.py       # Availability Score por bajas
│   └── context.py            # Valor de plantilla, DT, H2H (secundarios)
├── models/
│   ├── base.py               # 1X2 y top-marcadores desde la matriz conjunta
│   ├── poisson_simple.py     # Poisson doble independiente (baseline)
│   ├── bivariate_poisson.py  # Karlis-Ntzoufras (λ1, λ2, λ3)
│   ├── dixon_coles.py        # Dixon-Coles (recomendado)
│   └── elo_model.py          # Elo puro (baseline)
├── simulation/montecarlo.py  # Monte Carlo (>=100k) + solución exacta
├── prediction/predictor.py   # Orquestador + reporte + explicación
├── validation/
│   ├── metrics.py            # Log Loss, Brier, RPS, Accuracy
│   ├── calibration.py        # Curva de calibración + temperature scaling
│   └── backtest.py           # Walk-forward + comparación de modelos
└── main.py
```

## Uso programático

```python
from prediction.predictor import MatchPredictor
from data.synthetic import generate_match_history, generate_team_metadata

matches  = generate_match_history()
metadata = generate_team_metadata()

predictor = MatchPredictor(matches, metadata=metadata)
pred = predictor.predict("Argentina", "France", "2026-06-01",
                         neutral=True, model="dixon_coles")
print(pred.format_report())
```

Partido del anfitrión (no neutral): `neutral=False, home_team="USA"`.

## Decisiones de diseño clave

- **Dixon-Coles es el modelo principal** (no el bivariado): admite dependencia
  negativa entre marcadores, más fiel a los datos de fútbol.
- **Shrinkage Elo↔GLM** (`config.strength.elo_prior_blend`): imprescindible con
  ~20 partidos por selección para no sobreajustar.
- **RPS** como métrica rectora del 1X2 (respeta el orden de resultados).
- **Amistosos ponderados a la baja** vs. partidos competitivos.
- **H2H, DT y valor de plantilla** entran como ajustes acotados que nunca
  dominan forma/Elo (ver `config.SecondaryWeights`).

Re-optimizar hiperparámetros con `validation/backtest.py` antes de producción.
```
