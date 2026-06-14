# Handoff Frontend — Cambios de API (2026-06-14)

Resumen de los cambios de hoy en la API del predictor WC2026. **Todo es aditivo y retrocompatible**: no se modificó ni se quitó ningún campo existente.

---

## 1. `POST /api/predict` ahora devuelve el 11 inicial, la formación y la posición de cada jugador

Cuando hay **lineup confirmado** (ESPN lo publica ~1 h antes del partido y sigue disponible en vivo y al finalizar), la respuesta incluye:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `lineup_confirmed_a` / `_b` | `boolean` | `true` si se obtuvo el XI confirmado del equipo A / B |
| `lineup_a` / `lineup_b` | `string[] \| null` | Nombres del 11 inicial (orden de ESPN). `null` si no hay lineup |
| `formation_a` / `formation_b` | `string \| null` | Formación táctica, ej. `"4-4-2"`, `"4-3-3"`. `null` si no hay lineup |
| `lineup_detail_a` / `lineup_detail_b` | `PlayerSlot[] \| null` | 11 inicial con detalle por jugador (para dibujar la cancha). `null` si no hay lineup |

**`PlayerSlot`** (cada elemento de `lineup_detail_*`, **ordenado por `formation_place`**):

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | `string` | Nombre completo |
| `jersey` | `number \| null` | Número de camiseta |
| `position` | `string \| null` | Rol/posición (abreviatura ESPN): `G`, `RB`, `LB`, `CB`, `CD-L`, `CD-R`, `CM-R`, `CM-L`, `LM`, `RM`, `CF-L`, `CF-R`, … |
| `formation_place` | `number \| null` | Ubicación en la formación: **1 = arquero … 11**. Junto con la formación permite posicionar al jugador en la cancha |

### Garantía de consistencia
```
lineup_confirmed_a === true  ⟺  lineup_a !== null  &&  lineup_detail_a !== null  &&  formation_a !== null
```
Los dos equipos son **independientes**: puede venir uno confirmado y el otro `null`. Manejar ambos casos.

### Ejemplo (recortado)
```json
{
  "team_a": "Haiti", "team_b": "Scotland",
  "p_a": 0.129, "p_draw": 0.249, "p_b": 0.623,

  "lineup_confirmed_a": true,
  "lineup_confirmed_b": true,
  "lineup_a": ["Johny Placide", "Hannes Delcroix", "Ricardo Adé", "..."],
  "formation_a": "4-4-2",
  "lineup_detail_a": [
    { "name": "Johny Placide",     "jersey": 1,  "position": "G",    "formation_place": 1 },
    { "name": "Carlens Arcus",     "jersey": 2,  "position": "RB",   "formation_place": 2 },
    { "name": "Martin Expérience", "jersey": 8,  "position": "LB",   "formation_place": 3 },
    { "name": "Danley Jean Jacques","jersey": 17,"position": "CM-R", "formation_place": 4 },
    "...11 jugadores ordenados por formation_place..."
  ],
  "formation_b": "4-4-2",
  "lineup_detail_b": [ "...11 jugadores..." ]
}
```

### TypeScript
```typescript
interface PlayerSlot {
  name: string;
  jersey: number | null;
  position: string | null;        // "G" | "RB" | "CB" | "CM-R" | "CF-L" | ...
  formation_place: number | null; // 1 (arquero) .. 11
}

interface PredictResponse {
  // ... campos existentes (team_*, p_*, xg_*, top_scorelines, narrative, etc.)
  lineup_confirmed_a: boolean;
  lineup_confirmed_b: boolean;
  lineup_a: string[] | null;
  lineup_b: string[] | null;
  formation_a: string | null;            // "4-4-2"
  formation_b: string | null;
  lineup_detail_a: PlayerSlot[] | null;  // ordenado por formation_place
  lineup_detail_b: PlayerSlot[] | null;
}
```

### Para dibujar la cancha
- Usar `formation_a` (la "shape", ej. `4-4-2`) + `lineup_detail_a` (cada jugador con su `formation_place` y `position`).
- `lineup_detail_*` **ya viene ordenado por `formation_place`** (1 = arquero). Podés mapear `formation_place` → coordenada de cancha, o agrupar por líneas usando la formación.
- `position` (abreviatura ESPN, con sufijos `-L`/`-R`) da el rol exacto si querés afinar la ubicación lateral/central.
- `lineup_a` (solo nombres) se mantiene por si querés una lista simple; tiene los mismos jugadores que `lineup_detail_a`.

### Cuándo viene poblado vs `null`
| Situación | lineup / formation |
|-----------|--------------------|
| Partido a > 1 día | `null` (no se consulta ESPN todavía) |
| Mismo día, lineup aún no publicado | `null` |
| Lineup confirmado (~1 h antes), **en juego** o **finalizado** | poblado |

> **Fix de hoy:** antes el lineup quedaba en `null` para partidos **en curso/finalizados** por un bug de matching de fecha (timezone) contra ESPN. Ya está corregido: los partidos en vivo y finalizados ahora traen el XI/formación.

---

## 2. `GET /api/fixture` — traer desde el primer día del Mundial

- El parámetro `include_past` ahora acepta **hasta 40** (antes 7).
- Para traer el fixture **desde el primer día del Mundial (2026-06-11)**: `GET /api/fixture?include_past=40&days_ahead=10`.
- El backend **nunca consulta días previos al 2026-06-11**, así que pasar un número alto es seguro (no dispara llamadas de más). Los días ya finalizados se cachean 24 h.

---

## 3. Integración robusta ante arranques en frío

Tras un deploy o reinicio, el contenedor arranca en frío y la carga inicial del modelo tarda. Para evitar timeouts:

1. **Pollear `GET /health`** hasta `{"predictor": "ready"}` antes de llamar a `/api/predict`.
2. Si `/api/predict` devuelve **`503`**, el predictor aún está cargando → reintentar con backoff (no es error definitivo).
3. Usar un **timeout de cliente holgado** en el primer request tras un arranque en frío (el de 190 s se quedó corto en un caso).

> El backtest de accuracy ya **no** corre al arrancar (se sirve un baseline versionado), así que la carga en frío es bastante más rápida y no compite con las predicciones.

---

## Notas
- Ningún cambio en el **request** de `/api/predict` (sigue siendo `team_a_id`, `team_b_id`, `date`, `knockout`, `model`).
- Swagger actualizado en `/docs` (incluye `PlayerSlot` y los campos nuevos con ejemplos).
- Pendiente conocido (no bloquea esto): cuando el XI está confirmado, `squad_desc_*` puede decir *"XI estimado"* porque los nombres de ESPN no siempre cruzan con la base de ratings para valuar el XI. Los **nombres/posiciones del XI sí son correctos**; es solo la valuación económica la que cae al estimado.
