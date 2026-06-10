# Predictor de partidos — Copa del Mundo 2026

Modelo de probabilidades 1X2 calibradas y explicables para los **48 equipos del Mundial 2026**, basado en datos históricos reales descargados automáticamente.

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

El programa pregunta el equipo local, visitante, fecha y si es eliminatoria.

### Directo con argumentos

```bash
# Partido de fase de grupos
python predict.py "México" "Panamá" --date 2026-06-15

# Acepta nombres en español, inglés, minúsculas o parciales
python predict.py "alemania" "brasil"
python predict.py "corea" "japón"

# Modo eliminatoria (prórroga + penales)
python predict.py "Argentina" "Francia" --knockout

# Ver los 48 equipos disponibles
python predict.py --list

# Cambiar modelo de marcador
python predict.py "España" "Alemania" --model poisson_simple
# Modelos: dixon_coles (default) | bivariate_poisson | poisson_simple
```

### Gestión de datos

```bash
# Descargar/actualizar el dataset de partidos reales (caché 24h)
python -m data.ingest

# Forzar re-descarga
python -m data.ingest --refresh

# Demo completa con datos reales (predicción + backtest + calibración)
python main.py --real
python main.py --real --refresh   # fuerza re-descarga
python main.py                    # versión sintética, no requiere red
```

---

## Arquitectura

```
wc_match_predictor/
├── config.py                  # Hiperparámetros (decay, Elo, blend, rho, MC...)
├── predict.py                 # CLI principal — modo interactivo y por argumentos
├── main.py                    # Demo end-to-end (predicción + backtest + calibración)
├── data/
│   ├── ingest.py              # Descarga datos reales (martj42/international_results)
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

## Fuente de datos

Los resultados históricos se descargan automáticamente de
[martj42/international\_results](https://github.com/martj42/international_results)
(CC BY 4.0), que cubre todos los partidos internacionales desde 1872 y se
actualiza tras cada fecha FIFA.

Los datos se cachean localmente en `data/cache/` con un TTL de 24 horas.

> Los metadatos de valor de plantilla (usados como señal secundaria) son actualmente
> sintéticos. Para mejorar esa señal, se pueden integrar datos de Transfermarkt.

---

## Uso programático

```python
from data.ingest import build_dataset
from data.synthetic import generate_team_metadata
from prediction.predictor import MatchPredictor

matches  = build_dataset(since_year=2018)      # datos reales
metadata = generate_team_metadata()

predictor = MatchPredictor(matches, metadata=metadata)
pred = predictor.predict("Argentina", "France", "2026-06-15",
                         neutral=True, model="dixon_coles")
print(pred.format_report())
```

---

## Decisiones de diseño clave

- **Dixon-Coles como modelo principal**: admite dependencia negativa entre marcadores bajos (0-0, 1-0, 0-1, 1-1), más fiel a los datos de fútbol que Poisson simple.
- **Shrinkage Elo↔GLM** (`config.strength.elo_prior_blend`): imprescindible con ~20 partidos por selección para no sobreajustar.
- **RPS** como métrica rectora del 1X2 (respeta el orden de resultados, penaliza menos los errores en resultados adyacentes).
- **Amistosos ponderados a 0.45** vs. partidos competitivos (1.00 para el Mundial).
- **H2H, DT y valor de plantilla** entran como ajustes acotados que nunca dominan sobre Elo/forma (ver `config.SecondaryWeights`).

Re-optimizar hiperparámetros con `validation/tuning.py` antes de producción.
