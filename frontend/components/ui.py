"""Shared look-and-feel helpers for every MachineMind page (black animated theme)."""
import streamlit as st

COLOR_NORMAL = "#00E676"
COLOR_ABNORMAL = "#FF5252"
COLOR_NEUTRAL = "#00E5FF"
COLOR_WARNING = "#FFB300"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&family=Space+Grotesk:wght@500;700&display=swap');

@keyframes mmBgShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
@keyframes mmFadeUp {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes mmWave {
    0%, 100% { height: 8%; }
    50%      { height: 100%; }
}
@keyframes mmPulse {
    0%   { box-shadow: 0 0 0 0 rgba(0, 229, 255, 0.7); }
    70%  { box-shadow: 0 0 0 10px rgba(0, 229, 255, 0); }
    100% { box-shadow: 0 0 0 0 rgba(0, 229, 255, 0); }
}
@keyframes mmGlow {
    0%, 100% { text-shadow: 0 0 18px rgba(0, 229, 255, 0.35); }
    50%      { text-shadow: 0 0 34px rgba(124, 77, 255, 0.6); }
}

.stApp {
    background: linear-gradient(135deg, #020305 0%, #080D18 35%, #020305 65%, #0A0714 100%);
    background-size: 300% 300%;
    animation: mmBgShift 24s ease infinite;
    font-family: 'Inter', sans-serif;
}
.stApp p, .stApp label, .stApp li, .stApp span.mm-text {
    font-family: 'Inter', sans-serif;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    font-family: 'Space Grotesk', sans-serif;
    letter-spacing: -0.01em;
}
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1300px; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #05070A 0%, #0A0F1A 100%);
    border-right: 1px solid rgba(0, 229, 255, 0.15);
}
/* Put the brand name into the empty strip at the top of the sidebar */
[data-testid="stSidebarHeader"] {
    padding: 1.6rem 1rem 0.8rem 1.2rem;
    align-items: center;
}
[data-testid="stSidebarHeader"]::before {
    content: "MachineMind";
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.7rem;
    font-weight: 700;
    background: linear-gradient(90deg, #00E5FF, #7C4DFF);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}
.mm-brand-sub { font-size: 0.80rem; opacity: 0.6; margin-bottom: 8px; }

/* Hero */
.mm-hero {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    flex-wrap: wrap;
    padding: 34px 38px;
    margin-bottom: 26px;
    border-radius: 22px;
    border: 1px solid rgba(0, 229, 255, 0.18);
    background: radial-gradient(circle at 15% 20%, rgba(0, 229, 255, 0.12), transparent 45%),
                radial-gradient(circle at 90% 80%, rgba(124, 77, 255, 0.16), transparent 45%),
                rgba(255, 255, 255, 0.02);
    overflow: hidden;
    animation: mmFadeUp 0.9s ease both;
}
.mm-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 5px 14px;
    border-radius: 999px;
    border: 1px solid rgba(0, 229, 255, 0.35);
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #9BE9F5;
    background: rgba(0, 229, 255, 0.06);
}
.mm-dot {
    width: 9px; height: 9px; border-radius: 50%;
    background: #00E5FF;
    animation: mmPulse 1.8s infinite;
}
.mm-pill-warn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-left: 10px;
    padding: 5px 14px;
    border-radius: 999px;
    border: 1px solid rgba(255, 179, 0, 0.45);
    font-size: 0.78rem;
    color: #FFD166;
    background: rgba(255, 179, 0, 0.07);
}
.mm-hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 3.6rem;
    font-weight: 700;
    line-height: 1.05;
    margin: 16px 0 8px 0;
    background: linear-gradient(90deg, #FFFFFF 0%, #00E5FF 55%, #7C4DFF 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: mmGlow 4s ease-in-out infinite;
}
.mm-hero-sub { font-size: 1.05rem; opacity: 0.75; max-width: 560px; }
.mm-wave {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 120px;
    min-width: 260px;
}
.mm-wave span {
    display: block;
    width: 5px;
    height: 20%;
    border-radius: 3px;
    background: linear-gradient(180deg, #00E5FF, #7C4DFF);
    animation: mmWave 1.4s ease-in-out infinite;
}

/* Cards */
.mm-card {
    position: relative;
    overflow: hidden;
    background: linear-gradient(145deg, rgba(255,255,255,0.07), rgba(255,255,255,0.02));
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 16px;
    padding: 20px 20px 16px 20px;
    margin-bottom: 14px;
    backdrop-filter: blur(10px);
    animation: mmFadeUp 0.8s ease both;
    transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}
.mm-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--accent);
    box-shadow: 0 0 18px var(--accent);
}
.mm-card:hover {
    transform: translateY(-6px);
    border-color: var(--accent);
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.65);
}
.mm-label { font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.65; }
.mm-value { font-family: 'Space Grotesk', sans-serif; font-size: 2.3rem; font-weight: 700; line-height: 1.25; color: #FFFFFF; }
.mm-note { font-size: 0.78rem; opacity: 0.6; }

/* Section titles */
.stApp h3 {
    margin-top: 1.2rem;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(0, 229, 255, 0.18);
}

/* Buttons and inputs */
.stButton > button {
    border: 1px solid rgba(0, 229, 255, 0.5);
    background: linear-gradient(90deg, rgba(0, 229, 255, 0.15), rgba(124, 77, 255, 0.15));
    color: #FFFFFF;
    border-radius: 10px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 22px rgba(0, 229, 255, 0.45);
    border-color: #00E5FF;
}
[data-testid="stDataFrame"] {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
}

@media (prefers-reduced-motion: reduce) {
    .stApp, .mm-hero, .mm-card, .mm-wave span, .mm-dot, .mm-hero-title { animation: none !important; }
}
</style>
"""


def apply_style():
    """Inject the black animated theme (CSS) into the page."""
    st.markdown(CSS, unsafe_allow_html=True)


def sidebar_brand():
    """Show the tagline and the 'model not connected' notice in the sidebar.

    The MachineMind name itself is drawn by the CSS at the top of the sidebar.
    """
    st.sidebar.markdown(
        '<div class="mm-brand-sub">Industrial acoustic anomaly detection</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.warning("ML model not connected. No real predictions are being made yet.")


def hero(title, subtitle, show_model_warning=True):
    """Big animated banner at the top of the home page."""
    bars = []
    for i in range(46):
        duration = 0.9 + (i % 7) * 0.13
        delay = -(i * 0.11)
        bars.append(
            f'<span style="animation-duration:{duration:.2f}s;animation-delay:{delay:.2f}s"></span>'
        )
    warn = (
        '<span class="mm-pill-warn">ML model not connected</span>' if show_model_warning else ""
    )
    html = (
        '<div class="mm-hero">'
        '<div class="mm-hero-text">'
        f'<span class="mm-badge"><span class="mm-dot"></span>Acoustic anomaly detection</span>{warn}'
        f'<div class="mm-hero-title">{title}</div>'
        f'<div class="mm-hero-sub">{subtitle}</div>'
        "</div>"
        f'<div class="mm-wave">{"".join(bars)}</div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def page_header(title, subtitle):
    st.title(title)
    st.caption(subtitle)


def metric_card(label, value, note="", accent=COLOR_NEUTRAL, delay=0.0):
    """Draw one summary card. 'delay' staggers the fade-in animation."""
    html = (
        f'<div class="mm-card" style="--accent:{accent};animation-delay:{delay}s">'
        f'<div class="mm-label">{label}</div>'
        f'<div class="mm-value">{value}</div>'
        f'<div class="mm-note">{note}</div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def placeholder_page(title, subtitle, milestone, planned_items):
    """A simple page that says what will be built here and when."""
    st.set_page_config(page_title=f"{title} - MachineMind", layout="wide")
    apply_style()
    sidebar_brand()
    page_header(title, subtitle)
    st.info(f"This page is not built yet. It is planned for {milestone}.")
    st.markdown("**Planned features:**")
    for item in planned_items:
        st.markdown(f"- {item}")
