// Tipos espejo de los schemas de FastAPI (backend/api/schemas.py).
// No modificar manualmente — deben mantenerse sincronizados con el backend.

export interface Team {
  id: string;        // slug estable: "argentina", "korea-republic", "usa"
  canonical: string; // nombre interno en inglés: "Argentina", "Korea Republic"
  name_es: string;   // nombre en español para mostrar al usuario
  flag: string;      // emoji bandera
}

export interface FixtureMatch {
  id: string;
  date: string;        // "2026-06-15"
  time_utc: string;    // "20:00"
  team_a_id: string;   // slug — usar para llamar a /api/predict
  team_b_id: string;
  team_a: string;      // canónico inglés (para debugging)
  team_b: string;
  team_a_es: string;   // nombre en español para mostrar
  team_b_es: string;
  flag_a: string;
  flag_b: string;
  status: MatchStatus;
  score_a: string;
  score_b: string;
  neutral: boolean;
  round: string;
  venue: string;
}

export interface PredictRequest {
  team_a_id: string;   // slug de /api/teams
  team_b_id: string;
  date?: string;       // "YYYY-MM-DD"; default = hoy
  knockout?: boolean;  // true = modo eliminatoria con penales
  model?: "dixon_coles" | "bivariate_poisson" | "poisson_simple";
}

export interface ScoreProbability {
  score_a: number;
  score_b: number;
  probability: number; // 0–1
}

export interface PredictResponse {
  // Equipos
  team_a_id: string;   // slug — clave estable
  team_b_id: string;
  team_a: string;      // canónico inglés
  team_b: string;
  team_a_es: string;   // español para mostrar
  team_b_es: string;
  flag_a: string;
  flag_b: string;

  // Probabilidades 90 min
  p_a: number;         // probabilidad de victoria equipo A (0–1)
  p_draw: number;      // probabilidad de empate (0–1)
  p_b: number;         // probabilidad de victoria equipo B (0–1)

  // Goles esperados
  xg_a: number;
  xg_b: number;

  // Marcadores más probables (top 8, ordenados desc por probabilidad)
  top_scorelines: ScoreProbability[];

  // Sede
  neutral: boolean;
  home_team_id: string | null;  // slug del equipo local; null = cancha neutral
  venue_label: string;          // texto listo para mostrar

  // Fuente de datos de plantilla
  squad_desc_a: string;
  squad_desc_b: string;
  lineup_confirmed_a: boolean;
  lineup_confirmed_b: boolean;

  // Narrativa en español lista para mostrar al usuario
  narrative: string;

  // Modo eliminatoria (null si no aplica)
  is_knockout: boolean;
  p_penalties: number | null;
  p_advance_a: number | null;
  p_advance_b: number | null;
}

export type MatchStatus =
  | "programado"
  | "en juego"
  | "descanso"
  | "finalizado"
  | "postergado"
  | "cancelado"
  | "suspendido";
