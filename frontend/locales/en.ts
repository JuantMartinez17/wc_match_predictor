import type { Translations } from "./types";

export const en: Translations = {
  meta: {
    title: "World Cup 2026 Predictor",
    description:
      "Choose two national teams and see the result probabilities, calculated with statistical models on real match data.",
    dateLocale: "en-US",
  },
  nav: {
    title: "World Cup 2026",
    predict: "Predict",
    fixture: "Fixture",
  },
  hero: {
    badge: "FIFA World Cup 2026",
    heading1: "Predict who wins",
    heading2: "every match",
    description:
      "Choose two national teams and see the result probabilities, calculated with statistical models on real match data.",
    ctaPredict: "Try the predictor",
    ctaFixture: "View fixture",
  },
  countdown: {
    started: "The World Cup has started",
    label: "The World Cup starts in",
    days: "days",
    hours: "hours",
    min: "min",
    sec: "sec",
  },
  fixture: {
    sectionLabel: "Fixture",
    heading: "Upcoming matches",
    rounds: {
      "group-stage": "Group Stage",
      "round-of-32": "Round of 32",
      "round-of-16": "Round of 16",
      "quarter-finals": "Quarter-finals",
      "semi-finals": "Semi-finals",
      final: "Final",
      "third-place": "Third Place",
    },
    description:
      'Tap "View prediction" on any match to see the full analysis.',
    emptyState: "No matches scheduled in this period.",
    loadMore: "Load more matches",
    today: "Today",
    tomorrow: "Tomorrow",
    viewAnalysis: "View analysis",
    viewPrediction: "View prediction",
    retry: "Retry",
    errorLoad: "Could not load the fixture. Please try again.",
    errorPredict: "Could not calculate the prediction. Please try again.",
    vs: "vs",
    utcSuffix: "UTC",
    status: {
      "en juego": "In play",
      descanso: "Half-time",
      finalizado: "Full time",
      postergado: "Postponed",
      cancelado: "Cancelled",
      suspendido: "Suspended",
      programado: "Scheduled",
      STATUS_FULL_TIME: "Full time",
    },
  },
  predictor: {
    sectionLabel: "Predictor",
    heading: "Predict a match",
    description:
      "Choose two national teams and the model calculates result probabilities using real match data.",
    errorLoad:
      "Could not load national teams. Check your connection and try again in a few seconds.",
    errorPredict: "Could not calculate the prediction. Please try again.",
    teamALabel: "Team A",
    teamBLabel: "Team B",
    placeholderA: "Team A",
    placeholderB: "Team B",
    dateAriaLabel: "Match date",
    knockout: "Knockout",
    calculating: "Calculating...",
    predict: "Predict",
    clear: "Clear",
  },
  teamPicker: {
    placeholder: "Select team",
    search: "Search...",
    noResults: "No results",
  },
  modelPicker: {
    label: "Model",
    recommended: "Recommended",
    dixon_coles: {
      label: "Dixon-Coles",
      description:
        "Most accurate. Adjusts for low-scoring matches and gives more weight to recent results.",
    },
    bivariate_poisson: {
      label: "Bivariate Poisson",
      description:
        "Estimates both teams' goals taking into account the correlation between them.",
    },
    poisson_simple: {
      label: "Simple Poisson",
      description:
        "Baseline model. Estimates each team's goals independently.",
    },
  },
  modal: { close: "Close" },
  theme: {
    toLight: "Switch to light mode",
    toDark: "Switch to dark mode",
  },
  result: {
    draw: "Draw",
    winsTeamHeadline: (name) => `${name} wins`,
    advancesTeamLabel: (name) => `${name} advances`,
    mostLikelyScores: "Most likely scores",
    lineupConfirmed: "Confirmed lineup",
    lineupPending: "Lineup pending",
    probabilitiesAt90: "Probabilities at 90'",
    penaltiesProbability: "Probability of penalty shootout:",
    analysis: "Analysis",
    squadFormation: "Squad & formation",
    mostLikelyResult: "Most likely result",
    confidenceHigh: "High",
    confidenceMedium: "Medium",
    confidenceLow: "Low",
    confidencePhrase: (level) => `${level.toLowerCase()} confidence`,
    score: "Score",
    vs: "vs",
  },
};
