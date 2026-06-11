import type { Translations } from "./types";

export const es: Translations = {
  meta: {
    title: "Predictor del Mundial 2026",
    description:
      "Elegí dos selecciones y conocé las probabilidades del resultado, calculadas con modelos estadísticos sobre partidos reales.",
    dateLocale: "es-AR",
  },
  nav: {
    title: "Mundial 2026",
    predict: "Predecir",
    fixture: "Fixture",
  },
  hero: {
    badge: "Mundial FIFA 2026",
    heading1: "Predecí quién gana",
    heading2: "cada partido",
    description:
      "Elegí dos selecciones y conocé las probabilidades del resultado, calculadas con modelos estadísticos sobre partidos reales.",
    ctaPredict: "Probar el predictor",
    ctaFixture: "Ver el fixture",
  },
  countdown: {
    started: "El Mundial ya está en marcha",
    label: "El Mundial arranca en",
    days: "días",
    hours: "horas",
    min: "min",
    sec: "seg",
  },
  fixture: {
    sectionLabel: "Fixture",
    heading: "Próximos partidos",
    rounds: {
      "group-stage": "Fase de grupos",
      "round-of-32": "Dieciseisavos de final",
      "round-of-16": "Octavos de final",
      "quarter-finals": "Cuartos de final",
      "semi-finals": "Semifinales",
      final: "Final",
      "third-place": "Tercer puesto",
    },
    description:
      'Tocá "Ver predicción" en cualquier partido y mirá el análisis completo.',
    emptyState: "No hay partidos programados en este período.",
    loadMore: "Ver más partidos",
    today: "Hoy",
    tomorrow: "Mañana",
    viewAnalysis: "Ver análisis",
    viewPrediction: "Ver predicción",
    retry: "Reintentar",
    errorLoad: "No pudimos cargar el fixture. Intentá de nuevo.",
    errorPredict: "No pudimos calcular la predicción. Intentá de nuevo.",
    vs: "vs",
    utcSuffix: "UTC",
    status: {
      "en juego": "En juego",
      descanso: "Descanso",
      finalizado: "Finalizado",
      postergado: "Postergado",
      cancelado: "Cancelado",
      suspendido: "Suspendido",
      programado: "Programado",
      STATUS_FULL_TIME: "Finalizado",
    },
  },
  predictor: {
    sectionLabel: "Predictor",
    heading: "Predecí un partido",
    description:
      "Elegí dos selecciones y el modelo calcula las probabilidades del resultado con datos de partidos reales.",
    errorLoad:
      "No pudimos cargar las selecciones. Revisá tu conexión e intentá de nuevo en unos segundos.",
    errorPredict: "No pudimos calcular la predicción. Intentá de nuevo.",
    teamALabel: "Equipo A",
    teamBLabel: "Equipo B",
    placeholderA: "Selección A",
    placeholderB: "Selección B",
    dateAriaLabel: "Fecha del partido",
    knockout: "Eliminatoria",
    calculating: "Calculando...",
    predict: "Predecir",
    clear: "Limpiar",
  },
  teamPicker: {
    placeholder: "Elegir selección",
    search: "Buscar...",
    noResults: "Sin resultados",
  },
  modelPicker: {
    label: "Modelo",
    recommended: "Recomendado",
    dixon_coles: {
      label: "Dixon-Coles",
      description:
        "El más preciso. Ajusta los partidos de pocos goles y da más peso a los resultados recientes.",
    },
    bivariate_poisson: {
      label: "Poisson bivariado",
      description:
        "Estima los goles de ambos equipos teniendo en cuenta la correlación entre sí.",
    },
    poisson_simple: {
      label: "Poisson simple",
      description:
        "Modelo base. Estima los goles de cada equipo de forma independiente.",
    },
  },
  modal: { close: "Cerrar" },
  theme: {
    toLight: "Cambiar a modo claro",
    toDark: "Cambiar a modo oscuro",
  },
  result: {
    draw: "Empate",
    winsTeamHeadline: (name) => `Gana ${name}`,
    advancesTeamLabel: (name) => `Avanza ${name}`,
    mostLikelyScores: "Marcadores más probables",
    lineupConfirmed: "Formación confirmada",
    lineupPending: "Formación por confirmar",
    probabilitiesAt90: "Probabilidades a 90'",
    penaltiesProbability: "Probabilidad de definición por penales:",
    analysis: "Análisis",
    squadFormation: "Plantilla y formación",
    mostLikelyResult: "Resultado más probable",
    confidenceHigh: "Alta",
    confidenceMedium: "Media",
    confidenceLow: "Baja",
    confidencePhrase: (level) => `confianza ${level.toLowerCase()}`,
    score: "Marcador",
    vs: "vs",
  },
};
