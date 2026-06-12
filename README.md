# WC 2026 Match Predictor — Backend

API REST de predicción de partidos para la **Copa del Mundo 2026**. Devuelve probabilidades 1X2 calibradas, goles esperados, marcadores más probables y narrativa en español para cualquier combinación de los 48 equipos clasificados.

Motor: **Elo + GLM Poisson con shrinkage + Dixon-Coles / Poisson Bivariado + Monte Carlo 100k**, con backtesting walk-forward y ajustes por lineup confirmado.

---

## Estructura del proyecto

```
wc_match_predictor/
│
├── backend/                         # Servidor FastAPI
│   └── api/
│       ├── main.py                  # App, lifespan, CORS, registro de routers
│       ├── schemas.py               # Modelos Pydantic (request/response)
│       ├── constants.py             # IDs numéricos de equipos y códigos de banderas
│       └── routers/
│           ├── teams.py             # GET  /api/teams
│           ├── fixture.py           # GET  /api/fixture
│           ├── predict.py           # POST /api/predict
│           └── accuracy.py          # GET  /api/accuracy
│
├── data/                            # Ingesta y datos externos
│   ├── ingest.py                    # Histórico martj42 (CC BY 4.0), caché 24 h
│   ├── fixture.py                   # ESPN API, caché 30 min
│   ├── players.py                   # Valores de mercado SofaScore/Transfermarkt, caché 7 días
│   ├── lineups.py                   # 11 inicial SofaScore, caché 1 h
│   └── cache/                       # Archivos de caché locales
│
├── features/                        # Ingeniería de variables
│   ├── elo.py                       # Rating Elo con decay por importancia y margen
│   ├── strength.py                  # GLM Poisson ataque/defensa ajustado por rival
│   ├── decay.py                     # Ponderación exponencial temporal
│   ├── availability.py              # Penalización por ausencias de titulares clave
│   └── context.py                   # Ajustes secundarios: valor plantilla, H2H, entrenador
│
├── models/                          # Modelos de marcador
│   ├── base.py                      # Interfaz abstracta ScoreModel
│   ├── dixon_coles.py               # Dixon-Coles 1997 (principal)
│   ├── bivariate_poisson.py         # Karlis & Ntzoufras 2003
│   ├── poisson_simple.py            # Baseline independiente
│   └── elo_model.py                 # Baseline Elo puro (solo 1X2)
│
├── prediction/
│   └── predictor.py                 # MatchPredictor: orquesta todo el motor
│
├── simulation/                      # Monte Carlo sobre la matriz de marcadores
├── validation/
│   ├── backtest.py                  # Walk-forward out-of-sample
│   ├── metrics.py                   # Log-loss, Brier, RPS, accuracy
│   └── calibration.py
│
├── config.py                        # Todos los hiperparámetros del motor
├── predict.py                       # CLI (texto libre + fuzzy matching)
│
├── requirements.txt                 # Dependencias completas
├── Procfile                         # Deploy en Render
└── .env.example                     # Variables de entorno del backend
```

---

## Setup local

### Requisitos

- Python 3.11+

### Instalación

```bash
git clone <url-del-repo>
cd wc_match_predictor
pip install -r requirements.txt
```

### Arrancar el servidor

```bash
python -m uvicorn backend.api.main:app --reload --port 8000
```

El predictor tarda ~30 s en cargar. Hacer polling a `/health` hasta que `predictor = "ready"` antes de enviar predicciones.

**Swagger UI:** `http://localhost:8000/docs`  
**ReDoc:** `http://localhost:8000/redoc`

### Solo CLI (sin servidor)

```bash
python predict.py                              # modo interactivo
python predict.py "Argentina" "Francia"        # con argumentos
python predict.py "Argentina" "Alemania" --knockout
python predict.py --list                       # ver todos los equipos
```

La CLI acepta texto libre con fuzzy matching. La API en cambio requiere IDs numéricos exactos (`GET /api/teams`).

---

## Variables de entorno

Copiar `.env.example` a `.env` y ajustar según necesidad.

| Variable | Default | Descripción |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | Orígenes permitidos, separados por coma |
| `CORS_ORIGIN_REGEX` | *(vacío)* | Regex para orígenes dinámicos (ej. Vercel preview deploys) |

---

## API REST

> **Base URL local:** `http://localhost:8000`  
> **Swagger UI:** `http://localhost:8000/docs` *(con ejemplos interactivos)*  
> **ReDoc:** `http://localhost:8000/redoc`

### Convención de IDs de equipos

Todos los endpoints usan **IDs numéricos enteros (1–48)** como identificadores. Los IDs son estables mientras no cambie el conjunto de equipos. La lista completa se obtiene de `GET /api/teams`.

Ejemplos de referencia:

| Equipo | ID |
|---|---|
| Algeria | 1 |
| Argentina | 2 |
| Brazil | 7 |
| France | 18 |
| Germany | 19 |
| Korea Republic | 27 |
| Mexico | 28 |
| Spain | 41 |
| USA | 47 |

---

### `GET /health`

Estado del servidor y del predictor.

```json
{ "status": "ok", "predictor": "ready" }
```

`predictor` puede ser `"ready"` o `"loading"`. Hacer polling hasta `"ready"` antes de enviar predicciones.

---

### `GET /api/teams`

Los 48 equipos clasificados al Mundial 2026, ordenados por nombre en español.

**Response:** `Team[]`

```json
[
  {
    "id": 2,
    "canonical": "Argentina",
    "name_es": "Argentina",
    "flag": "ar"
  },
  {
    "id": 19,
    "canonical": "Germany",
    "name_es": "Alemania",
    "flag": "de"
  }
]
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `integer` | ID numérico estable — **usar en `/api/predict`** |
| `canonical` | `string` | Nombre canónico en inglés (referencia interna) |
| `name_es` | `string` | Nombre en español para mostrar |
| `flag` | `string` | Código ISO2 para [flagcdn.com](https://flagcdn.com) — `'ar'` → `flagcdn.com/w80/ar.png` |

---

### `GET /api/fixture`

Fixture oficial del Mundial 2026 vía ESPN API.

**Query params:**

| Param | Tipo | Default | Rango | Descripción |
|---|---|---|---|---|
| `days_ahead` | `integer` | `10` | 1–30 | Días hacia adelante desde hoy |
| `include_past` | `integer` | `1` | 0–7 | Días pasados a incluir |

**Ejemplo:** `GET /api/fixture?days_ahead=7&include_past=2`

**Response:** `FixtureMatch[]`

```json
[
  {
    "id": "726321",
    "date": "2026-06-15",
    "time_utc": "20:00",
    "team_a_id": 28,
    "team_b_id": 47,
    "team_a": "Mexico",
    "team_b": "USA",
    "team_a_es": "México",
    "team_b_es": "Estados Unidos",
    "flag_a": "mx",
    "flag_b": "us",
    "status": "programado",
    "score_a": "",
    "score_b": "",
    "neutral": false,
    "round": "group-stage",
    "venue": "Estadio Azteca"
  }
]
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `string` | ID del evento ESPN |
| `team_a_id` / `team_b_id` | `integer` | IDs numéricos — pasar directo a `/api/predict` |
| `date` | `string` | `YYYY-MM-DD` |
| `time_utc` | `string` | Hora UTC `HH:MM` |
| `status` | `string` | `programado` \| `en juego` \| `descanso` \| `finalizado` \| `postergado` \| `cancelado` \| `suspendido` |
| `score_a` / `score_b` | `string` | Marcador actual (vacío si no empezó) |
| `neutral` | `boolean` | `false` si el equipo A es sede anfitriona |
| `round` | `string` | Fase del torneo |
| `venue` | `string` | Estadio |

> Caché de 30 minutos. Si ESPN no responde, devuelve la última versión guardada.

---

### `POST /api/predict`

Motor de predicción completo para un partido.

**Request body:**

```json
{
  "team_a_id": 2,
  "team_b_id": 19,
  "date": "2026-06-28",
  "knockout": false,
  "model": "dixon_coles"
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `team_a_id` | `integer` | ✓ | ID numérico del equipo A (de `/api/teams`) |
| `team_b_id` | `integer` | ✓ | ID numérico del equipo B. Debe ser distinto de `team_a_id` |
| `date` | `string` | — | `YYYY-MM-DD`. Default: hoy |
| `knockout` | `boolean` | — | `true` = modo eliminatoria con prórroga y penales. Default: `false` |
| `model` | `string` | — | `"dixon_coles"` *(default)* \| `"bivariate_poisson"` \| `"poisson_simple"` |

**Response — fase de grupos (`knockout: false`):**

```json
{
  "team_a_id": 2,
  "team_b_id": 19,
  "team_a": "Argentina",
  "team_b": "Germany",
  "team_a_es": "Argentina",
  "team_b_es": "Alemania",
  "flag_a": "ar",
  "flag_b": "de",

  "p_a": 0.412,
  "p_draw": 0.261,
  "p_b": 0.327,

  "xg_a": 1.48,
  "xg_b": 1.21,

  "top_scorelines": [
    { "score_a": 1, "score_b": 0, "probability": 0.112 },
    { "score_a": 1, "score_b": 1, "probability": 0.098 },
    { "score_a": 2, "score_b": 1, "probability": 0.087 },
    { "score_a": 0, "score_b": 0, "probability": 0.074 },
    { "score_a": 2, "score_b": 0, "probability": 0.068 },
    { "score_a": 0, "score_b": 1, "probability": 0.066 },
    { "score_a": 1, "score_b": 2, "probability": 0.058 },
    { "score_a": 3, "score_b": 1, "probability": 0.041 }
  ],

  "neutral": true,
  "home_team_id": null,
  "venue_label": "Cancha neutral",

  "squad_desc_a": "XI confirmado (11 jugadores, 742M EUR)",
  "squad_desc_b": "plantel completo (510M EUR, XI estimado)",
  "lineup_confirmed_a": true,
  "lineup_confirmed_b": false,

  "narrative": "Argentina tiene una leve ventaja, pero el partido está abierto. Se anticipan entre 2 y 3 goles en total. El marcador más probable es 1-0 a favor de Argentina (11% de chances).",

  "is_knockout": false,
  "p_penalties": null,
  "p_advance_a": null,
  "p_advance_b": null
}
```

**Campos adicionales en modo eliminatoria (`knockout: true`):**

```json
{
  "is_knockout": true,
  "p_penalties": 0.243,
  "p_advance_a": 0.537,
  "p_advance_b": 0.463
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `p_a` / `p_draw` / `p_b` | `float` | Probabilidades 1X2 a 90 min. Suman 1 |
| `xg_a` / `xg_b` | `float` | Goles esperados (expected goals) |
| `top_scorelines` | `array` | Top 8 marcadores exactos más probables (desc) |
| `neutral` | `boolean` | `false` si hay ventaja de localía |
| `home_team_id` | `integer \| null` | ID del equipo local; `null` = cancha neutral |
| `venue_label` | `string` | Texto listo para mostrar |
| `squad_desc_a/b` | `string` | Fuente de datos de plantilla usada |
| `lineup_confirmed_a/b` | `boolean` | `true` si el XI inicial fue confirmado por SofaScore |
| `narrative` | `string` | Resumen en español sin jerga estadística |
| `p_penalties` | `float \| null` | Prob. de llegar a penales (solo knockout) |
| `p_advance_a/b` | `float \| null` | Prob. de clasificar incluyendo prórroga y penales |

**Tiempos de respuesta:**

| Situación | Tiempo |
|---|---|
| Primera predicción tras arrancar | 30–60 s (carga del modelo) |
| Predicciones siguientes | 1–4 s (Monte Carlo 100k iter.) |
| Con consulta de lineup a SofaScore | +1–2 s adicionales |

---

### `GET /api/accuracy`

Métricas de backtesting *walk-forward* fuera de muestra de cada modelo estadístico.

**Response:** `ModelAccuracy[]`

```json
[
  {
    "model": "dixon_coles",
    "label": "Dixon-Coles",
    "matches_evaluated": 118,
    "correct_result_pct": 0.559,
    "brier_score": 0.213,
    "dataset": "Mundiales 2018–2022"
  },
  {
    "model": "bivariate_poisson",
    "label": "Bivariate Poisson",
    "matches_evaluated": 118,
    "correct_result_pct": 0.542,
    "brier_score": 0.219,
    "dataset": "Mundiales 2018–2022"
  },
  {
    "model": "poisson_simple",
    "label": "Poisson Simple",
    "matches_evaluated": 118,
    "correct_result_pct": 0.525,
    "brier_score": 0.226,
    "dataset": "Mundiales 2018–2022"
  }
]
```

| Campo | Tipo | Descripción |
|---|---|---|
| `model` | `string` | Clave interna del modelo |
| `label` | `string` | Nombre legible para mostrar |
| `matches_evaluated` | `integer` | Partidos evaluados en el backtest |
| `correct_result_pct` | `float` | Acierto del resultado 1X2 (0–1) |
| `brier_score` | `float` | Calibración probabilística. Menor = mejor. Rango típico en fútbol: 0.19–0.24 |
| `dataset` | `string` | Dataset usado |

> Las métricas se calculan en background al arrancar el servidor (3–6 min la primera vez) y se cachean 30 días en disco. Si aún no están listas devuelve `503`.

---

### Errores

| Código | Causa |
|---|---|
| `422` | ID de equipo inválido, ambos equipos iguales, o body mal formado |
| `503` | El predictor o las métricas de accuracy aún se están cargando |
| `500` | Error interno del motor |

Ejemplo de `422`:
```json
{
  "detail": "ID de equipo inválido: '999'. Consultá /api/teams para ver los IDs válidos."
}
```

---

## Fuentes de datos

| Dato | Fuente | Caché local |
|---|---|---|
| Resultados históricos (1872–hoy) | [martj42/international_results](https://github.com/martj42/international_results) — CC BY 4.0 | 24 h |
| Fixture del Mundial | ESPN API pública | 30 min |
| Valores de mercado por jugador | SofaScore / Transfermarkt | 7 días |
| 11 inicial confirmado | SofaScore API | 1 h |

Todo el acceso a APIs externas tiene fallback: si no hay conexión, se usa la última versión cacheada (o valores sintéticos para el motor).

---

## Cómo funciona el motor

```
Datos históricos (2006–hoy)
        │
        ▼
   Elo ratings ──────────────────────┐
        │                            │
        ▼                            │ prior blend (35%)
   GLM Poisson ──► λ_a, λ_b ◄───────┘
   (ataque/defensa por rival)
        │
        ▼
   Ajustes secundarios
   ├─ Valor del XI (Transfermarkt)
   ├─ Disponibilidad (ausencias del top-15 por valor)
   ├─ Historial directo (H2H)
   └─ Factor entrenador
        │
        ▼
   Modelo de marcador
   (Dixon-Coles | Bivariate Poisson | Poisson Simple)
        │
        ▼
   Matriz P(i,j) — prob. de cada marcador
        │
        ▼
   Monte Carlo 100k ──► p_a, p_draw, p_b
                   └──► top_scorelines
```

### Ajuste por lineup confirmado

Cuando el 11 inicial está disponible en SofaScore (~1 h antes del partido), el motor:

1. Suma el valor de mercado real de los 11 titulares (`squad_value_a/b`).
2. Compara el top-15 del plantel por valor con los titulares confirmados.
3. Los jugadores top que **no están en el XI** se tratan como ausentes (probable lesión/suspensión en contexto de Mundial).
4. Aplica `availability_score` → reduce `λ` ofensivo en proporción a la importancia de los ausentes (`availability_sensitivity = 0.25`).

---

## Decisiones de diseño

| Decisión | Motivo |
|---|---|
| **Dixon-Coles como modelo principal** | Corrige la dependencia negativa entre marcadores bajos (0-0, 1-0, 0-1, 1-1); más fiel que Poisson simple |
| **Shrinkage Elo↔GLM (blend 35%)** | Con ~20 partidos por selección, el GLM puro sobreajusta; el prior Elo estabiliza |
| **RPS como métrica rectora** | Respeta el orden de resultados (una predicción en "empate" cuando ganó el local es menos grave que predecir "derrota del local") |
| **Amistosos ponderados a 0.45** | Los técnicos rotan y no compiten al 100%; los partidos competitivos aportan mucho más señal |
| **Valor del XI sobre valor del plantel** | Cuando hay lineup confirmado, la suma real de titulares es más precisa que el total del plantel |
| **IDs numéricos en la API** | Estables, tipo-seguros y sin ambigüedad de encoding. El texto libre queda en la CLI con fuzzy matching |
| **Narrativa generada en el backend** | El cliente recibe texto listo para mostrar sin necesidad de interpretar probabilidades |
| **Monte Carlo en thread pool** | Evita bloquear el event loop de FastAPI en el cómputo CPU-bound de 100k simulaciones |
