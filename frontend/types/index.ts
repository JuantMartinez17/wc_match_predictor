// Tipos espejo de los schemas de FastAPI (backend/api/schemas.py)

export interface Team {
  canonical: string;
  name_es: string;
  flag: string;
}

export interface FixtureMatch {
  id: string;
  date: string;       // "2026-06-15"
  time_utc: string;   // "20:00"
  team_a: string;     // canónico inglés
  team_b: string;
  team_a_es: string;
  team_b_es: string;
  flag_a: string;
  flag_b: string;
  status: string;     // "programado" | "en juego" | "finalizado" | ...
  score_a: string;
  score_b: string;
  neutral: boolean;
  round: string;
  venue: string;
}

export interface ScoreProbability {
  score_a: number;
  score_b: number;
  probability: number; // 0–1
}

export interface PredictRequest {
  team_a: string;
  team_b: string;
  date?: string;
  knockout?: boolean;
  model?: "dixon_coles" | "bivariate_poisson" | "poisson_simple";
}

export interface PredictResponse {
  // Equipos
  team_a: string;
  team_b: string;
  team_a_es: string;
  team_b_es: string;
  flag_a: string;
  flag_b: string;

  // Probabilidades 90 min
  p_a: number;
  p_draw: number;
  p_b: number;

  // Goles esperados
  xg_a: number;
  xg_b: number;

  // Marcadores más probables (top 8)
  top_scorelines: ScoreProbability[];

  // Sede
  neutral: boolean;
  home_team: string | null;
  venue_label: string;

  // Plantilla
  squad_desc_a: string;
  squad_desc_b: string;
  lineup_confirmed_a: boolean;
  lineup_confirmed_b: boolean;

  // Narrativa
  narrative: string;

  // Knockout (opcionales)
  is_knockout: boolean;
  p_penalties?: number | null;
  p_advance_a?: number | null;
  p_advance_b?: number | null;
}

export type MatchStatus =
  | "programado"
  | "en juego"
  | "descanso"
  | "finalizado"
  | "postergado"
  | "cancelado"
  | "suspendido";
