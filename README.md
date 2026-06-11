# Predictor de partidos — Copa del Mundo 2026

Modelo de probabilidades 1X2 calibradas y explicables para los **48 equipos del Mundial 2026**, basado en datos históricos reales y valoración real de plantillas.

Motor: **Elo + fuerza ofensiva/defensiva ajustada por rival (GLM Poisson con shrinkage) + modelo de marcador (Dixon-Coles / Poisson bivariado) + simulación Monte Carlo**, con backtesting walk-forward.

---

## Estructura del proyecto

```
wc_match_predictor/
├── backend/                        # Servidor FastAPI
│   ├── api/
│   │   ├── main.py                 # App FastAPI, lifespan, CORS, routers
│   │   ├── schemas.py              # Pydantic request/response models
│   │   ├── constants.py            # IDs de equipos (slugs) y emojis de banderas
│   │   └── routers/
│   │       ├── teams.py            # GET /api/teams
│   │       ├── fixture.py          # GET /api/fixture
│   │       └── predict.py          # POST /api/predict
│   └── requirements.txt            # Deps del servidor (sin Streamlit)
│
├── frontend/                       # Next.js 16 + Tailwind v4 + shadcn/ui
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/ui/              # Componentes shadcn/ui
│   ├── lib/
│   │   ├── api.ts                  # Cliente tipado para la API
│   │   └── utils.ts
│   ├── types/
│   │   └── index.ts                # Tipos TypeScript espejo de schemas.py
│   └── .env.local.example
│
├── data/                           # Ingesta, jugadores, lineups, fixture
├── features/                       # Elo, decay, strength, availability
├── models/                         # Dixon-Coles, Bivariate Poisson, etc.
├── simulation/                     # Monte Carlo
├── prediction/                     # Orquestador del motor
├── validation/                     # Métricas, backtest, calibración
│
├── config.py                       # Hiperparámetros del motor
├── predict.py                      # CLI (modo interactivo y por argumentos)
├── app.py                          # Streamlit (desarrollo local alternativo)
├── main.py                         # Punto de entrada CLI simplificado
│
├── requirements.txt                # Deps completas (engine + backend + streamlit)
├── requirements-cli.txt            # Solo engine (sin servidor ni UI)
├── Procfile                        # Para deploy en Render
└── .env.example                    # Variables de entorno del backend
```

---

## Setup local

### Requisitos

- Python 3.11+
- Node.js 18+

### Backend

```bash
# Clonar y entrar al proyecto
git clone <url-del-repo>
cd wc_match_predictor

# Instalar dependencias
pip install -r requirements.txt

# Arrancar el servidor
python -m uvicorn backend.api.main:app --reload --port 8000
```

El modelo tarda ~30 segundos en cargar la primera vez. El endpoint `/health` indica cuándo está listo.

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # editar si el backend no corre en :8000
npm run dev
```

Abre en `http://localhost:3000`.

### Solo CLI (sin servidor)

```bash
pip install -r requirements-cli.txt
python predict.py
```

---

## Variables de entorno

### Backend (`.env` en la raíz)

| Variable | Default | Descripción |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | Orígenes permitidos, separados por coma |

### Frontend (`frontend/.env.local`)

| Variable | Default | Descripción |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL base del backend |

---

## API REST — Documentación

> **Base URL local:** `http://localhost:8000`
> **Swagger UI:** `http://localhost:8000/docs`
> **ReDoc:** `http://localhost:8000/redoc`

### Convención de IDs de equipos

Todos los endpoints usan **slugs ASCII estables** como identificadores de equipos, no texto libre. Los IDs se obtienen de `GET /api/teams`.

| Nombre canónico | ID (slug) |
|---|---|
| Argentina | `argentina` |
| Korea Republic | `korea-republic` |
| Côte d'Ivoire | `cote-divoire` |
| Bosnia and Herzegovina | `bosnia-and-herzegovina` |
| USA | `usa` |
| Congo DR | `congo-dr` |
| Curaçao | `curacao` |

El backend resuelve IDs a nombres canónicos con un lookup O(1). Si el ID no existe, devuelve `422` indicando que hay que consultar `/api/teams`.

---

### `GET /health`

Verifica que el servidor esté activo y el modelo cargado.

```json
{
  "status": "ok",
  "predictor": "ready"
}
```

`predictor` puede ser `"ready"` o `"loading"`. Hacer polling a este endpoint al iniciar para mostrar estado de carga en el frontend.

---

### `GET /api/teams`

Lista los 48 equipos clasificados al Mundial 2026, ordenados por nombre en español.

**Response:** `Team[]`

```json
[
  {
    "id": "alemania",
    "canonical": "Germany",
    "name_es": "Alemania",
    "flag": "🇩🇪"
  },
  {
    "id": "argentina",
    "canonical": "Argentina",
    "name_es": "Argentina",
    "flag": "🇦🇷"
  }
]
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `string` | Slug estable — **usar este valor en `/api/predict`** |
| `canonical` | `string` | Nombre interno en inglés (para debugging) |
| `name_es` | `string` | Nombre en español para mostrar al usuario |
| `flag` | `string` | Emoji de la bandera |

---

### `GET /api/fixture`

Fixture oficial del Mundial 2026 (vía ESPN API). Devuelve partidos en la ventana `[hoy - include_past días, hoy + days_ahead días]`.

**Query params:**

| Param | Tipo | Default | Rango | Descripción |
|---|---|---|---|---|
| `days_ahead` | `int` | `10` | 1–30 | Días hacia adelante |
| `include_past` | `int` | `1` | 0–7 | Días pasados a incluir |

**Ejemplo:** `GET /api/fixture?days_ahead=7`

**Response:** `FixtureMatch[]`

```json
[
  {
    "id": "726321",
    "date": "2026-06-15",
    "time_utc": "20:00",
    "team_a_id": "mexico",
    "team_b_id": "usa",
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
| `id` | `string` | ID del evento ESPN — usar como `key` en React |
| `team_a_id` / `team_b_id` | `string` | IDs slug — pasar directo a `/api/predict` |
| `date` | `string` | `YYYY-MM-DD` |
| `time_utc` | `string` | Hora UTC en formato `HH:MM` |
| `team_a` / `team_b` | `string` | Nombre canónico en inglés (debugging) |
| `team_a_es` / `team_b_es` | `string` | Nombre en español para mostrar |
| `flag_a` / `flag_b` | `string` | Emoji bandera |
| `status` | `string` | Ver tabla abajo |
| `score_a` / `score_b` | `string` | Marcador (vacío si no empezó) |
| `neutral` | `boolean` | `false` si uno de los equipos es sede |
| `round` | `string` | Fase del torneo (`group-stage`, `round-of-16`, etc.) |
| `venue` | `string` | Nombre del estadio |

**Valores de `status`:**

| Valor | Significado |
|---|---|
| `"programado"` | No empezó |
| `"en juego"` | En curso |
| `"descanso"` | Entretiempo |
| `"finalizado"` | Terminó |
| `"postergado"` | Postergado |
| `"cancelado"` | Cancelado |
| `"suspendido"` | Suspendido |

> El fixture se cachea 30 minutos. Si ESPN no está disponible, el backend devuelve la última versión cacheada.

---

### `POST /api/predict`

Corre el motor de predicción y devuelve resultado completo para un partido.

**Request body:**

```json
{
  "team_a_id": "argentina",
  "team_b_id": "france",
  "date": "2026-06-28",
  "knockout": false,
  "model": "dixon_coles"
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `team_a_id` | `string` | Sí | ID del equipo A (campo `id` de `/api/teams`) |
| `team_b_id` | `string` | Sí | ID del equipo B |
| `date` | `string` | No | Fecha `YYYY-MM-DD`. Default: hoy |
| `knockout` | `boolean` | No | `true` = modo eliminatoria con prórroga y penales. Default: `false` |
| `model` | `string` | No | `"dixon_coles"` (default) \| `"bivariate_poisson"` \| `"poisson_simple"` |

**Response:**

```json
{
  "team_a_id": "argentina",
  "team_b_id": "france",
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
  "home_team_id": null,
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

| Campo | Tipo | Descripción |
|---|---|---|
| `team_a_id` / `team_b_id` | `string` | Slugs — mismos que en el request |
| `team_a` / `team_b` | `string` | Nombre canónico en inglés (debugging) |
| `team_a_es` / `team_b_es` | `string` | Nombre en español para mostrar |
| `flag_a` / `flag_b` | `string` | Emoji bandera |
| `p_a` | `float` | Probabilidad victoria equipo A a 90 min (0–1) |
| `p_draw` | `float` | Probabilidad empate a 90 min (0–1) |
| `p_b` | `float` | Probabilidad victoria equipo B a 90 min (0–1) |
| `xg_a` / `xg_b` | `float` | Goles esperados |
| `top_scorelines` | `ScoreProbability[]` | Top 8 marcadores más probables (desc por probabilidad) |
| `neutral` | `boolean` | `false` si uno de los equipos juega como local |
| `home_team_id` | `string \| null` | Slug del equipo local; `null` si es cancha neutral |
| `venue_label` | `string` | Texto listo para mostrar (`"Cancha neutral"` o `"Local: México (sede del Mundial)"`) |
| `squad_desc_a` / `squad_desc_b` | `string` | Descripción de la fuente de plantilla usada |
| `narrative` | `string` | Resumen en español sin jerga estadística, listo para mostrar |
| `is_knockout` | `boolean` | `true` si se pidió modo eliminatoria |
| `p_penalties` | `float \| null` | Probabilidad de llegar a penales (solo knockout) |
| `p_advance_a` / `p_advance_b` | `float \| null` | Probabilidad de clasificar incluyendo prórroga y penales |

**Tiempos de respuesta:**

| Situación | Tiempo |
|---|---|
| Primera predicción tras arrancar | 30–60 s (carga del modelo) |
| Predicciones siguientes | 1–4 s (Monte Carlo 100k iter.) |
| Con lineup confirmado disponible | +1–2 s extra (fetch SofaScore) |

---

### Errores

```json
{ "detail": "ID de equipo inválido: 'alemanía'. Consultá /api/teams para ver los IDs válidos." }
```

| Código | Causa |
|---|---|
| `422` | ID de equipo inválido, equipos iguales, o body mal formado |
| `500` | Error interno del motor |

---

### Flujo recomendado para el frontend

```
Al iniciar la app:
  1. GET /health  → polling hasta que predictor = "ready"
  2. GET /api/teams   → guardar en estado global (para selector manual)
  3. GET /api/fixture → mostrar partidos del día agrupados

Al hacer click en un partido del fixture:
  4. POST /api/predict con { team_a_id, team_b_id, date } del fixture
  5. Mostrar narrative + barras p_a/p_draw/p_b + grid de scorelines

Para selector manual:
  4. Usar lista de /api/teams como opciones de los selects
  5. POST /api/predict con los equipos elegidos
```

---

### Cliente TypeScript

Implementado en [`frontend/lib/api.ts`](frontend/lib/api.ts). Los tipos están en [`frontend/types/index.ts`](frontend/types/index.ts).

```typescript
import { fetchTeams, fetchFixture, predictMatch, checkHealth } from "@/lib/api";

// Desde un partido del fixture (los IDs vienen incluidos)
const matches = await fetchFixture(10);
const result = await predictMatch({
  team_a_id: match.team_a_id,
  team_b_id: match.team_b_id,
  date: match.date,
  knockout: false,
});

// Selector manual
const teams = await fetchTeams();
const result = await predictMatch({ team_a_id: "argentina", team_b_id: "france" });
```

La URL base se configura con `NEXT_PUBLIC_API_URL` en `frontend/.env.local`.

---

## CLI

### Modo interactivo

```bash
python predict.py
```

### Con argumentos

```bash
python predict.py "México" "Panamá" --date 2026-06-15
python predict.py "alemania" "brasil"
python predict.py "Argentina" "Francia" --knockout
python predict.py --list
python predict.py "España" "Alemania" --model poisson_simple
```

> La CLI acepta texto libre con fuzzy matching. La API en cambio requiere IDs exactos (`/api/teams`).

---

## Fuentes de datos

| Dato | Fuente | Caché |
|---|---|---|
| Resultados históricos (1872–hoy) | [martj42/international_results](https://github.com/martj42/international_results) (CC BY 4.0) | 24 h |
| Fixture del Mundial | ESPN API pública | 30 min |
| Valores de mercado por jugador | SofaScore / Transfermarkt | 7 días |
| 11 inicial confirmado | SofaScore API | 1 h |

---

## Decisiones de diseño

- **Dixon-Coles como modelo principal**: admite dependencia negativa entre marcadores bajos (0-0, 1-0, 0-1, 1-1), más fiel a los datos reales de fútbol que Poisson simple.
- **Shrinkage Elo↔GLM**: imprescindible con ~20 partidos por selección para no sobreajustar.
- **RPS como métrica rectora del 1X2**: respeta el orden de resultados y penaliza menos los errores en resultados adyacentes.
- **Amistosos ponderados a 0.45** vs. partidos competitivos (1.00 para el Mundial).
- **Valor del XI sobre valor de plantilla**: cuando el lineup está confirmado, la suma de los titulares es más precisa que el total del plantel.
- **IDs tipo slug en la API**: ASCII estables, URL-safe, legibles. El texto libre con fuzzy matching queda exclusivamente en la CLI.
- **Narrativa generada en el backend**: el frontend recibe texto listo para mostrar sin necesidad de interpretar probabilidades.
