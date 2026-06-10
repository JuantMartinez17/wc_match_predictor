# Predictor de partidos — Copa del Mundo 2026

Modelo de probabilidades 1X2 calibradas y explicables para los **48 equipos del Mundial 2026**, basado en datos históricos reales y valoración real de plantillas.

Motor: **Elo + fuerza ofensiva/defensiva ajustada por rival (GLM Poisson con shrinkage) + modelo de marcador (Dixon-Coles / Poisson bivariado) + simulación Monte Carlo**, con backtesting walk-forward.

---

## Estructura del proyecto

```
wc_match_predictor/
├── backend/
│   ├── api/
│   │   ├── main.py            # FastAPI app (punto de entrada)
│   │   ├── schemas.py         # Pydantic request/response models
│   │   ├── constants.py       # Banderas emoji y helpers compartidos
│   │   └── routers/
│   │       ├── teams.py       # GET /api/teams
│   │       ├── fixture.py     # GET /api/fixture
│   │       └── predict.py     # POST /api/predict
│   └── requirements.txt       # Deps del servidor (sin Streamlit)
├── frontend/                  # Next.js + Tailwind + shadcn/ui
│   ├── app/
│   ├── components/ui/
│   ├── lib/api.ts             # Cliente tipado para la API
│   └── types/index.ts         # Tipos TypeScript espejo de schemas.py
├── config.py                  # Hiperparámetros del motor
├── predict.py                 # CLI (modo interactivo y por argumentos)
├── app.py                     # Streamlit (desarrollo local)
├── data/                      # Ingesta, jugadores, lineups, fixture
├── features/                  # Elo, decay, strength, availability
├── models/                    # Dixon-Coles, Bivariate Poisson, etc.
├── simulation/                # Monte Carlo
├── prediction/                # Orquestador
└── validation/                # Métricas, backtest, calibración
```

---

## Instalación local

```bash
# Engine + backend + Streamlit
python -m pip install -r requirements.txt

# Solo backend (servidor de producción)
python -m pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install
```

---

## Correr localmente

```bash
# Backend (desde la raíz del proyecto)
python -m uvicorn backend.api.main:app --reload --port 8000

# Frontend (en otra terminal)
cd frontend && npm run dev

# Streamlit (alternativa de desarrollo)
python -m streamlit run app.py
```

---

## API REST — Documentación para el frontend

> **Base URL local:** `http://localhost:8000`
> **Swagger UI:** `http://localhost:8000/docs`
> **ReDoc:** `http://localhost:8000/redoc`

El backend carga el modelo de predicción al arrancar (~30 segundos la primera vez que recibe un request). Mientras tanto, `/health` responde `"predictor": "loading"`.

---

### `GET /health`

Verifica que el servidor esté activo y el modelo cargado.

**Response:**
```json
{
  "status": "ok",
  "predictor": "ready"
}
```

`predictor` puede ser `"ready"` o `"loading"`. El frontend puede hacer polling a este endpoint al iniciar para mostrar un estado de carga.

---

### `GET /api/teams`

Lista los 48 equipos clasificados al Mundial 2026, ordenados alfabéticamente por nombre en español.

**Response:** `Team[]`

```json
[
  {
    "canonical": "Germany",
    "name_es": "Alemania",
    "flag": "🇩🇪"
  },
  {
    "canonical": "Saudi Arabia",
    "name_es": "Arabia Saudita",
    "flag": "🇸🇦"
  }
]
```

| Campo | Tipo | Descripción |
|---|---|---|
| `canonical` | `string` | Nombre interno en inglés — usar para llamar a `/api/predict` |
| `name_es` | `string` | Nombre en español para mostrar al usuario |
| `flag` | `string` | Emoji de la bandera del país |

---

### `GET /api/fixture`

Fixture oficial del Mundial 2026 desde ESPN API pública. Devuelve los partidos en la ventana `[hoy - 1 día, hoy + N días]`.

**Query params:**

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `days_ahead` | `int` | `10` | Días hacia adelante (1–30) |
| `include_past` | `int` | `1` | Días pasados a incluir (0–7) |

**Ejemplo:** `GET /api/fixture?days_ahead=7`

**Response:** `FixtureMatch[]`

```json
[
  {
    "id": "726321",
    "date": "2026-06-15",
    "time_utc": "20:00",
    "team_a": "Mexico",
    "team_b": "USA",
    "team_a_es": "México",
    "team_b_es": "Estados Unidos",
    "flag_a": "🇲🇽",
    "flag_b": "🇺🇸",
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
| `id` | `string` | ID del evento en ESPN — puede usarse como key de React |
| `date` | `string` | Fecha en formato `YYYY-MM-DD` |
| `time_utc` | `string` | Hora en UTC, formato `HH:MM` |
| `team_a` / `team_b` | `string` | Nombre canónico en inglés |
| `team_a_es` / `team_b_es` | `string` | Nombre en español para mostrar |
| `flag_a` / `flag_b` | `string` | Emoji bandera |
| `status` | `string` | Ver valores posibles abajo |
| `score_a` / `score_b` | `string` | Marcador (vacío si no empezó) |
| `neutral` | `boolean` | `false` solo cuando uno de los equipos es sede |
| `round` | `string` | Fase del torneo (`group-stage`, `round-of-16`, etc.) |
| `venue` | `string` | Nombre del estadio |

**Valores de `status`:**

| Valor | Significado |
|---|---|
| `"programado"` | Todavía no empezó |
| `"en juego"` | En curso (90 min) |
| `"descanso"` | Entretiempo |
| `"finalizado"` | Terminó |
| `"postergado"` | Postergado |
| `"cancelado"` | Cancelado |

> El fixture se cachea 30 minutos localmente. Si ESPN no está disponible, el backend devuelve la última versión cacheada.

---

### `POST /api/predict`

Corre el modelo y devuelve la predicción completa para un partido. Es el endpoint principal de la herramienta.

**Request body:**

```json
{
  "team_a": "Argentina",
  "team_b": "France",
  "date": "2026-06-28",
  "knockout": false,
  "model": "dixon_coles"
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `team_a` | `string` | Sí | Nombre del equipo A (inglés o español, acepta fuzzy matching) |
| `team_b` | `string` | Sí | Nombre del equipo B (inglés o español, acepta fuzzy matching) |
| `date` | `string` | No | Fecha `YYYY-MM-DD`. Default: hoy |
| `knockout` | `boolean` | No | `true` = modo eliminatoria con prórroga y penales. Default: `false` |
| `model` | `string` | No | `"dixon_coles"` (default) \| `"bivariate_poisson"` \| `"poisson_simple"` |

> `team_a` y `team_b` aceptan el nombre canónico en inglés (campo `canonical` de `/api/teams`) o el nombre en español. El backend hace fuzzy matching: `"brasil"`, `"Brazil"`, `"BRASIL"` son equivalentes. **Para el fixture, lo más seguro es pasar directamente `team_a` y `team_b` tal como vienen en la respuesta de `/api/fixture`.**

**Response:**

```json
{
  "team_a": "Argentina",
  "team_b": "France",
  "team_a_es": "Argentina",
  "team_b_es": "Francia",
  "flag_a": "🇦🇷",
  "flag_b": "🇫🇷",

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
  "home_team": null,
  "venue_label": "Cancha neutral",

  "squad_desc_a": "XI confirmado (11 jugadores, 742M EUR)",
  "squad_desc_b": "plantel completo (680M EUR, XI estimado)",

  "narrative": "Argentina tiene una leve ventaja, pero el partido está abierto. Se anticipan entre 2 y 3 goles en total. El marcador más probable es 1-0 a favor de Argentina (11% de chances).",

  "is_knockout": false,
  "p_penalties": null,
  "p_advance_a": null,
  "p_advance_b": null
}
```

**Campos de la respuesta:**

| Campo | Tipo | Descripción |
|---|---|---|
| `team_a` / `team_b` | `string` | Nombre canónico resuelto (puede diferir del input si hubo fuzzy match) |
| `team_a_es` / `team_b_es` | `string` | Nombre en español para mostrar |
| `flag_a` / `flag_b` | `string` | Emoji bandera |
| `p_a` | `float` | Probabilidad de que gane el equipo A a 90 min (0–1) |
| `p_draw` | `float` | Probabilidad de empate a 90 min (0–1) |
| `p_b` | `float` | Probabilidad de que gane el equipo B a 90 min (0–1) |
| `xg_a` / `xg_b` | `float` | Goles esperados para cada equipo |
| `top_scorelines` | `ScoreProbability[]` | 8 marcadores más probables, ordenados por probabilidad desc |
| `neutral` | `boolean` | `false` si uno de los equipos juega como local (sedes del Mundial) |
| `home_team` | `string \| null` | Nombre canónico del equipo local si `neutral=false` |
| `venue_label` | `string` | Texto listo para mostrar: `"Cancha neutral"` o `"Local: México (sede del Mundial)"` |
| `squad_desc_a` / `squad_desc_b` | `string` | Fuente de datos de plantilla usada (para mostrar en UI si se quiere) |
| `narrative` | `string` | Resumen en español sin jerga estadística, listo para mostrar al usuario |
| `is_knockout` | `boolean` | `true` si se llamó con `knockout: true` |
| `p_penalties` | `float \| null` | Probabilidad de llegar a penales (solo en modo knockout) |
| `p_advance_a` | `float \| null` | Probabilidad de que avance el equipo A incluyendo prórroga y penales |
| `p_advance_b` | `float \| null` | Probabilidad de que avance el equipo B incluyendo prórroga y penales |

**Tiempos de respuesta:**

| Situación | Tiempo aproximado |
|---|---|
| Primera predicción tras arrancar | 30–60 s (carga del modelo) |
| Predicciones siguientes | 1–4 s (Monte Carlo 100k iteraciones) |
| Con lineup confirmado disponible | +1–2 s (fetch SofaScore) |

---

### Errores

La API devuelve errores estándar HTTP con este body:

```json
{ "detail": "Equipo no encontrado: 'Alemanía'" }
```

| Código | Causa |
|---|---|
| `422` | Equipo no encontrado, equipos iguales, o body inválido |
| `500` | Error interno del modelo (raro, revisar logs del servidor) |

---

### Flujo recomendado para el frontend

```
Al cargar la app:
  1. GET /health → esperar hasta que predictor = "ready"
  2. GET /api/teams → guardar lista en estado global (para selector manual)
  3. GET /api/fixture → mostrar partidos agrupados por día

Al hacer click en un partido:
  4. POST /api/predict con { team_a, team_b, date } del fixture
  5. Mostrar narrative, barras de p_a/p_draw/p_b, grid de scorelines

Para selector manual:
  4. Usar la lista de /api/teams como opciones de los selects
  5. POST /api/predict con los equipos elegidos
```

---

### Cliente TypeScript incluido

El cliente ya está implementado en [`frontend/lib/api.ts`](frontend/lib/api.ts):

```typescript
import { fetchTeams, fetchFixture, predictMatch } from "@/lib/api";

// Fixture
const matches = await fetchFixture(10);

// Predicción desde un partido del fixture
const result = await predictMatch({
  team_a: match.team_a,   // canónico, viene directo del fixture
  team_b: match.team_b,
  date: match.date,
  knockout: false,
});

// Selector manual
const teams = await fetchTeams();
const result = await predictMatch({ team_a: "Argentina", team_b: "Francia" });
```

La URL base se configura con la variable de entorno `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`).

---

## Uso desde consola (CLI)

### Modo interactivo (recomendado)

```bash
python predict.py
```

### Directo con argumentos

```bash
python predict.py "México" "Panamá" --date 2026-06-15
python predict.py "alemania" "brasil"
python predict.py "Argentina" "Francia" --knockout
python predict.py --list
python predict.py "España" "Alemania" --model poisson_simple
```

---

## Fuentes de datos

| Dato | Fuente | Caché |
|---|---|---|
| Resultados históricos (1872–hoy) | [martj42/international_results](https://github.com/martj42/international_results) (CC BY 4.0) | 24 h |
| Fixture del Mundial | ESPN API pública | 30 min |
| Valores de mercado por jugador | SofaScore / Transfermarkt | 7 días |
| 11 inicial confirmado | SofaScore API | 1 h |

---

## Deploy

### Backend (Render)

- **Build command:** `pip install -r backend/requirements.txt`
- **Start command:** `python -m uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`
- **Variables de entorno:** `CORS_ORIGINS=https://tu-frontend.vercel.app`

### Frontend (Vercel)

- Root directory: `frontend`
- **Variables de entorno:** `NEXT_PUBLIC_API_URL=https://tu-backend.onrender.com`

---

## Decisiones de diseño clave

- **Dixon-Coles como modelo principal**: admite dependencia negativa entre marcadores bajos (0-0, 1-0, 0-1, 1-1), más fiel a los datos de fútbol que Poisson simple.
- **Shrinkage Elo↔GLM** (`config.strength.elo_prior_blend`): imprescindible con ~20 partidos por selección para no sobreajustar.
- **RPS** como métrica rectora del 1X2 (respeta el orden de resultados, penaliza menos los errores en resultados adyacentes).
- **Amistosos ponderados a 0.45** vs. partidos competitivos (1.00 para el Mundial).
- **Valor del XI sobre valor de plantilla**: cuando el lineup está confirmado, usar la suma real de los titulares es más preciso que el total del plantel.
- **La narrativa se genera en el backend**: el frontend recibe texto listo para mostrar, sin necesidad de interpretar probabilidades.
