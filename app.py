"""
app.py
======
Frontend Streamlit del predictor de partidos — Copa del Mundo 2026.

Correr localmente:
    streamlit run app.py

Publicar en Streamlit Cloud:
    1. Subir el repositorio a GitHub.
    2. Ir a share.streamlit.io y conectar el repo.
    3. Configurar el archivo principal como app.py.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Mundial 2026 — Predictor",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS personalizado — look limpio y moderno
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    /* Fondo general */
    .stApp { background-color: #0a1628; color: #f0f4f8; }

    /* Header principal */
    .main-header {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
        color: #f0f4f8;
    }
    .main-header h1 { font-size: 2.4rem; font-weight: 800; margin: 0; }
    .main-header p  { color: #8899aa; margin: 0.3rem 0 0 0; font-size: 1rem; }

    /* Tarjeta de partido */
    .match-card {
        background: #132340;
        border: 1px solid #1e3354;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .match-teams {
        flex: 1;
        font-size: 1.05rem;
        font-weight: 600;
        color: #e8f0ff;
    }
    .match-time  { color: #667799; font-size: 0.85rem; min-width: 70px; text-align:right; }
    .match-live  { color: #ff4444; font-weight: 700; }
    .match-done  { color: #556677; font-size: 0.85rem; }

    /* Barra de probabilidad */
    .prob-row {
        display: flex;
        align-items: stretch;
        border-radius: 10px;
        overflow: hidden;
        height: 54px;
        margin: 1rem 0;
        font-weight: 700;
        font-size: 1.1rem;
    }
    .prob-a    { background:#1a5276; display:flex; align-items:center; justify-content:center; color:#fff; }
    .prob-draw { background:#2c3e50; display:flex; align-items:center; justify-content:center; color:#aaa; }
    .prob-b    { background:#1a3a5c; display:flex; align-items:center; justify-content:center; color:#fff; }

    /* Narrative box */
    .narrative {
        background: #0d1f35;
        border-left: 4px solid #2980b9;
        border-radius: 0 8px 8px 0;
        padding: 1rem 1.2rem;
        margin: 1rem 0;
        font-size: 1.05rem;
        line-height: 1.7;
        color: #d0dff0;
    }

    /* Scoreline grid */
    .score-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    .score-item {
        background: #132340;
        border: 1px solid #1e3354;
        border-radius: 8px;
        padding: 0.5rem;
        text-align: center;
        font-size: 1rem;
    }
    .score-item .score { font-size: 1.2rem; font-weight: 700; color: #7eb3e0; }
    .score-item .pct   { font-size: 0.85rem; color: #667799; }

    /* Separadores */
    hr { border-color: #1e3354 !important; }

    /* Ajustes Streamlit nativos */
    .stButton > button {
        width: 100%;
        background: #1a4a7a;
        color: #e8f4ff;
        border: 1px solid #2860aa;
        border-radius: 8px;
        padding: 0.45rem 0.5rem;
        font-size: 0.9rem;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.2s;
    }
    .stButton > button:hover { background: #1f5a90; }
    .stTabs [data-baseweb="tab"] { color: #8899aa; }
    .stTabs [aria-selected="true"] { color: #7eb3e0; border-bottom-color: #7eb3e0; }
    [data-testid="stMetricLabel"] { color: #8899aa !important; }
    [data-testid="stMetricValue"] { color: #e8f0ff !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Datos de display
# ---------------------------------------------------------------------------

FLAGS: dict[str, str] = {
    "Argentina": "🇦🇷", "Brazil": "🇧🇷", "Colombia": "🇨🇴",
    "Ecuador": "🇪🇨", "Paraguay": "🇵🇾", "Uruguay": "🇺🇾",
    "France": "🇫🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Germany": "🇩🇪",
    "Spain": "🇪🇸", "Portugal": "🇵🇹", "Netherlands": "🇳🇱",
    "Belgium": "🇧🇪", "Croatia": "🇭🇷", "Switzerland": "🇨🇭",
    "Denmark": "🇩🇰", "Austria": "🇦🇹", "Norway": "🇳🇴",
    "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Sweden": "🇸🇪", "Czechia": "🇨🇿",
    "Bosnia and Herzegovina": "🇧🇦", "Turkey": "🇹🇷", "Poland": "🇵🇱",
    "Morocco": "🇲🇦", "Senegal": "🇸🇳", "Algeria": "🇩🇿",
    "Cabo Verde": "🇨🇻", "Congo DR": "🇨🇩", "Côte d'Ivoire": "🇨🇮",
    "Egypt": "🇪🇬", "Ghana": "🇬🇭", "South Africa": "🇿🇦", "Tunisia": "🇹🇳",
    "Japan": "🇯🇵", "Korea Republic": "🇰🇷", "Australia": "🇦🇺",
    "Iran": "🇮🇷", "Iraq": "🇮🇶", "Jordan": "🇯🇴",
    "Qatar": "🇶🇦", "Saudi Arabia": "🇸🇦", "Uzbekistan": "🇺🇿",
    "Mexico": "🇲🇽", "USA": "🇺🇸", "Canada": "🇨🇦",
    "Panama": "🇵🇦", "Haiti": "🇭🇹", "Curaçao": "🇨🇼",
    "New Zealand": "🇳🇿",
}

from predict import TEAM_EN_TO_ES  # nombres en español


def _es(team: str) -> str:
    return TEAM_EN_TO_ES.get(team, team)


def _flag(team: str) -> str:
    return FLAGS.get(team, "🏳️")


# ---------------------------------------------------------------------------
# Carga de datos (cacheada)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def load_fixture(days: int = 10) -> list[dict]:
    from data.fixture import get_fixture
    return get_fixture(days_ahead=days, include_past_days=1)


@st.cache_resource(show_spinner=False)
def load_predictor():
    from data.ingest import build_dataset
    from data.synthetic import generate_team_metadata
    from prediction.predictor import MatchPredictor
    from config import DEFAULT_CONFIG
    matches = build_dataset(since_year=2018)
    metadata = generate_team_metadata()
    return MatchPredictor(matches, metadata=metadata, config=DEFAULT_CONFIG)


# ---------------------------------------------------------------------------
# Narrativa en lenguaje simple
# ---------------------------------------------------------------------------

def build_narrative(
    team_a: str, team_b: str,
    p_a: float, p_draw: float, p_b: float,
    xg_a: float, xg_b: float,
    top_scorelines: list,
    trend_a: float, trend_b: float,
    venue_label: str,
) -> str:
    nombre_a = _es(team_a)
    nombre_b = _es(team_b)
    partes = []

    # Favorito
    if p_a >= 0.62:
        partes.append(f"**{nombre_a}** llega como gran favorito ante **{nombre_b}**.")
    elif p_b >= 0.62:
        partes.append(f"**{nombre_b}** llega como gran favorito ante **{nombre_a}**.")
    elif p_a >= 0.50:
        partes.append(f"**{nombre_a}** tiene una leve ventaja, pero el partido está abierto.")
    elif p_b >= 0.50:
        partes.append(f"**{nombre_b}** tiene una leve ventaja, pero el partido está abierto.")
    else:
        partes.append(f"Partido muy parejo entre **{nombre_a}** y **{nombre_b}**.")

    # Sede
    if "sede" in venue_label.lower():
        partes.append(f"Además, juega con el apoyo de su hinchada.")

    # Goles esperados
    total = xg_a + xg_b
    if total < 1.9:
        partes.append("Se espera un partido cerrado, con pocos goles.")
    elif total < 2.7:
        partes.append("Se anticipan entre 2 y 3 goles en total.")
    else:
        partes.append("Hay chances de que sea un partido con varios goles.")

    # Resultado más probable
    ga, gb, p_top = top_scorelines[0]
    if ga == gb:
        partes.append(
            f"El resultado más probable es un **empate {ga}-{gb}** "
            f"({p_top*100:.0f}% de chances)."
        )
    elif ga > gb:
        partes.append(
            f"El marcador más probable es **{ga}-{gb}** a favor de {nombre_a} "
            f"({p_top*100:.0f}% de chances)."
        )
    else:
        partes.append(
            f"El marcador más probable es **{gb}-{ga}** a favor de {nombre_b} "
            f"({p_top*100:.0f}% de chances)."
        )

    # Forma reciente
    if trend_a > 50 and trend_b <= 10:
        partes.append(f"{nombre_a} viene en un gran momento de forma.")
    elif trend_b > 50 and trend_a <= 10:
        partes.append(f"{nombre_b} viene en un gran momento de forma.")
    elif trend_a > 50 and trend_b > 50:
        partes.append("Ambos equipos vienen en buen momento de forma.")
    elif trend_a < -50 and trend_b > 10:
        partes.append(f"{nombre_a} llega con cierta irregularidad reciente.")
    elif trend_b < -50 and trend_a > 10:
        partes.append(f"{nombre_b} llega con cierta irregularidad reciente.")

    return " ".join(partes)


# ---------------------------------------------------------------------------
# Sección de predicción
# ---------------------------------------------------------------------------

def show_prediction(match: dict) -> None:
    team_a = match["team_a"]
    team_b = match["team_b"]
    ref_date = match["date"]

    nombre_a = _es(team_a)
    nombre_b = _es(team_b)

    st.markdown("---")
    st.markdown(
        f"## {_flag(team_a)} {nombre_a}  vs  {nombre_b} {_flag(team_b)}",
    )

    # Valores de plantilla y lineup
    from predict import detect_venue, _fetch_squad_values, _fetch_lineup, _resolve_xi_value

    neutral, home_team = detect_venue(team_a, team_b)
    venue_label = (
        f"Local: {_es(home_team)} (sede del Mundial)"
        if not neutral and home_team
        else "Cancha neutral"
    )

    with st.spinner("Obteniendo valores de plantilla..."):
        squad_a = _fetch_squad_values(team_a)
        squad_b = _fetch_squad_values(team_b)

    with st.spinner("Consultando lineup confirmado..."):
        lineup = _fetch_lineup(team_a, team_b, ref_date)

    lineup_a = lineup["team_a"] if lineup else None
    lineup_b = lineup["team_b"] if lineup else None
    xi_val_a, xi_desc_a = _resolve_xi_value(team_a, lineup_a, squad_a)
    xi_val_b, xi_desc_b = _resolve_xi_value(team_b, lineup_b, squad_b)

    # Predicción
    predictor = load_predictor()
    with st.spinner("Calculando predicción..."):
        pred = predictor.predict(
            team_a, team_b, ref_date,
            neutral=neutral, home_team=home_team,
            squad_value_a=xi_val_a, squad_value_b=xi_val_b,
        )

    p_a = pred.p_a
    p_draw = pred.p_draw
    p_b = pred.p_b
    xg_a = pred.expected_goals_a
    xg_b = pred.expected_goals_b
    explanation = pred.explanation
    trend_a = explanation.get("trend_a", 0)
    trend_b = explanation.get("trend_b", 0)

    # --- Barra de probabilidades ---
    w_a    = int(p_a * 100)
    w_draw = int(p_draw * 100)
    w_b    = max(1, 100 - w_a - w_draw)

    st.markdown(
        f"""
        <div class="prob-row">
            <div class="prob-a"    style="width:{w_a}%">
                {_flag(team_a)} {w_a}%<br><small>{nombre_a}</small>
            </div>
            <div class="prob-draw" style="width:{w_draw}%">
                {w_draw}%<br><small>Empate</small>
            </div>
            <div class="prob-b"    style="width:{w_b}%">
                {w_b}%<br><small>{nombre_b} {_flag(team_b)}</small>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Métricas rápidas ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Goles esperados " + nombre_a, f"{xg_a:.1f}")
    col2.metric("Goles esperados " + nombre_b, f"{xg_b:.1f}")
    col3.metric("Cancha", venue_label.split(":")[0])
    lineup_status = "✅ Confirmado" if lineup else "⏳ Pendiente"
    col4.metric("Lineup", lineup_status)

    # --- Narrativa ---
    narrativa = build_narrative(
        team_a, team_b, p_a, p_draw, p_b,
        xg_a, xg_b, pred.top_scorelines,
        trend_a, trend_b, venue_label,
    )
    st.markdown(f'<div class="narrative">{narrativa}</div>', unsafe_allow_html=True)

    # --- Marcadores más probables ---
    st.markdown("#### Marcadores más probables")
    st.caption("Los 8 resultados con mayor probabilidad de ocurrir.")

    score_html = '<div class="score-grid">'
    for ga, gb, p in pred.top_scorelines[:8]:
        if ga > gb:
            winner = f"↑ {nombre_a}"
        elif gb > ga:
            winner = f"↑ {nombre_b}"
        else:
            winner = "Empate"
        score_html += (
            f'<div class="score-item">'
            f'<div class="score">{ga} — {gb}</div>'
            f'<div class="pct">{p*100:.1f}%</div>'
            f'<div class="pct" style="font-size:0.75rem;color:#445566">{winner}</div>'
            f'</div>'
        )
    score_html += "</div>"
    st.markdown(score_html, unsafe_allow_html=True)

    # --- Info de plantilla ---
    with st.expander("ℹ️ Fuente de datos de plantilla"):
        st.caption(f"**{nombre_a}:** {xi_desc_a}")
        st.caption(f"**{nombre_b}:** {xi_desc_b}")


# ---------------------------------------------------------------------------
# Sección de fixture
# ---------------------------------------------------------------------------

def show_fixture(fixture: list[dict]) -> None:
    if not fixture:
        st.warning(
            "No se pudo cargar el fixture del Mundial. "
            "Revisá tu conexión o usá el selector manual abajo."
        )
        return

    # Agrupar por fecha
    dates = sorted(set(m["date"] for m in fixture))
    today_str = date.today().isoformat()

    # Elegir tab inicial
    default_idx = next(
        (i for i, d in enumerate(dates) if d >= today_str), 0
    )
    tab_labels = []
    for d in dates:
        dt = date.fromisoformat(d)
        if d == today_str:
            tab_labels.append(f"HOY {dt.strftime('%d %b')}")
        elif d == (date.today() + timedelta(days=1)).isoformat():
            tab_labels.append(f"MAÑANA {dt.strftime('%d %b')}")
        else:
            tab_labels.append(dt.strftime("%a %d %b").capitalize())

    tabs = st.tabs(tab_labels)

    for tab, d in zip(tabs, dates):
        day_matches = [m for m in fixture if m["date"] == d]
        with tab:
            if not day_matches:
                st.caption("No hay partidos este día.")
                continue
            for match in day_matches:
                _render_match_row(match)


def _render_match_row(match: dict) -> None:
    team_a = match["team_a"]
    team_b = match["team_b"]
    nombre_a = _es(team_a)
    nombre_b = _es(team_b)
    status = match["status"]

    col_teams, col_time, col_btn = st.columns([5, 1.5, 1.5])

    with col_teams:
        if status == "finalizado":
            st.markdown(
                f"{_flag(team_a)} **{nombre_a}** "
                f"`{match['score_a']} - {match['score_b']}` "
                f"**{nombre_b}** {_flag(team_b)}  "
                f"<span style='color:#445566;font-size:0.8rem'>Finalizado</span>",
                unsafe_allow_html=True,
            )
        elif status == "en juego":
            st.markdown(
                f"{_flag(team_a)} **{nombre_a}** "
                f"<span style='color:#ff4444;font-weight:700'>"
                f"{match['score_a']} - {match['score_b']} 🔴 EN JUEGO"
                f"</span> "
                f"**{nombre_b}** {_flag(team_b)}",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"{_flag(team_a)} **{nombre_a}**  vs  **{nombre_b}** {_flag(team_b)}"
            )

    with col_time:
        if status not in ("finalizado", "en juego"):
            st.caption(f"🕐 {match['time_utc']} UTC")
        else:
            st.caption("")

    with col_btn:
        btn_label = "📊 Predecir" if status != "finalizado" else "📊 Ver análisis"
        if st.button(btn_label, key=f"btn_{match['id']}_{match['team_a']}"):
            st.session_state["selected_match"] = match
            st.rerun()


# ---------------------------------------------------------------------------
# Selector manual (fallback sin fixture)
# ---------------------------------------------------------------------------

def show_manual_selector() -> None:
    from data.ingest import WC2026_TEAMS

    teams_es = sorted(TEAM_EN_TO_ES.get(t, t) for t in WC2026_TEAMS)
    teams_map = {TEAM_EN_TO_ES.get(t, t): t for t in WC2026_TEAMS}

    st.markdown("### Selector de partido")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        sel_a = st.selectbox("Primer equipo", teams_es, key="manual_a")
    with col2:
        sel_b = st.selectbox("Segundo equipo", [t for t in teams_es if t != sel_a], key="manual_b")
    with col3:
        sel_date = st.date_input("Fecha", value=date.today(), key="manual_date")

    if st.button("⚽ Predecir este partido", use_container_width=True):
        st.session_state["selected_match"] = {
            "id": "manual",
            "date": sel_date.isoformat(),
            "time_utc": "",
            "team_a": teams_map[sel_a],
            "team_b": teams_map[sel_b],
            "status": "programado",
            "score_a": "", "score_b": "",
            "neutral": True,
            "round": "",
            "venue": "",
        }
        st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>⚽ Copa del Mundo 2026</h1>
        <p>Seleccioná un partido para ver la predicción</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")

    # Cargar predictor en background (para que esté listo)
    with st.spinner("Cargando modelo predictivo..."):
        load_predictor()

    # Fixture
    with st.spinner("Obteniendo fixture..."):
        fixture = load_fixture()

    show_fixture(fixture)

    # Selector manual como alternativa siempre disponible
    with st.expander("🔧 Elegir partido manualmente"):
        show_manual_selector()

    # Resultado de la predicción
    if selected := st.session_state.get("selected_match"):
        show_prediction(selected)


main()
