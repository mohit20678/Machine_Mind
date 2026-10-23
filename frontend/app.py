"""MachineMind dashboard (home page).

Run from the project root:
    streamlit run frontend/app.py
"""
import plotly.express as px
import streamlit as st

from components.demo_data import empty_data, get_demo_data
from components.ui import (
    COLOR_ABNORMAL,
    COLOR_NEUTRAL,
    COLOR_NORMAL,
    COLOR_WARNING,
    apply_style,
    hero,
    metric_card,
    sidebar_brand,
)

st.set_page_config(page_title="MachineMind", layout="wide")
apply_style()
sidebar_brand()

st.sidebar.markdown("---")
show_demo = st.sidebar.checkbox("Show demonstration data", value=False)

hero(
    "MachineMind",
    "Upload a machine-sound recording and let AI flag potentially abnormal "
    "behaviour before it becomes a breakdown.",
)

# Choose the data source
if show_demo:
    machines, analyses, alerts = get_demo_data()
    st.warning(
        "DEMONSTRATION DATA: every number, chart and table below is fake and is "
        "shown only to preview the design. Untick the box in the sidebar to hide it."
    )
else:
    machines, analyses, alerts = empty_data()
    st.info(
        "No analyses yet. The database is added in Milestone 5, so real values "
        "will appear here after that. Tick 'Show demonstration data' in the "
        "sidebar to preview the design."
    )

# Work out the numbers for the cards
total_machines = len(machines)
total_analyses = len(analyses)
normal_count = int((analyses["prediction"] == "Normal").sum())
abnormal_count = int((analyses["prediction"] == "Potentially Abnormal").sum())

if total_analyses == 0:
    status_text, status_note, status_color = "No data", "No recordings analysed yet", COLOR_NEUTRAL
elif abnormal_count > 0:
    status_text, status_note, status_color = (
        "Review needed",
        "Some recordings were flagged as potentially abnormal",
        COLOR_WARNING,
    )
else:
    status_text, status_note, status_color = "No flags", "No abnormal recordings found", COLOR_NORMAL

# Top row of cards
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    metric_card("Recording status", status_text, status_note, status_color, 0.0)
with col2:
    metric_card("Machines registered", total_machines, "Registered in MachineMind", COLOR_NEUTRAL, 0.12)
with col3:
    metric_card("Analyses performed", total_analyses, "Uploaded recordings analysed", "#7C4DFF", 0.24)
with col4:
    metric_card("Normal", normal_count, "Recordings", COLOR_NORMAL, 0.36)
with col5:
    metric_card("Potentially abnormal", abnormal_count, "Recordings", COLOR_ABNORMAL, 0.48)

st.markdown("### Analysis results over time")
if total_analyses == 0:
    st.info("Nothing to chart yet. A chart appears here once recordings are analysed.")
else:
    chart_data = analyses.copy()
    chart_data["date"] = chart_data["timestamp"].dt.date
    daily = chart_data.groupby(["date", "prediction"]).size().reset_index(name="recordings")
    figure = px.bar(
        daily,
        x="date",
        y="recordings",
        color="prediction",
        barmode="stack",
        color_discrete_map={
            "Normal": COLOR_NORMAL,
            "Potentially Abnormal": COLOR_ABNORMAL,
        },
        labels={"date": "Date", "recordings": "Recordings", "prediction": "Result"},
        template="plotly_dark",
    )
    figure.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12, x=0),
    )
    figure.update_xaxes(gridcolor="rgba(255,255,255,0.06)")
    figure.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
    st.plotly_chart(figure, width="stretch")

left, right = st.columns(2)

with left:
    st.markdown("### Recent analyses")
    if total_analyses == 0:
        st.info("No analyses yet.")
    else:
        recent = analyses.head(8).copy()
        recent["timestamp"] = recent["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(recent, width="stretch", hide_index=True)
        if show_demo:
            st.caption("demo_score is a made-up number, not a model output.")

with right:
    st.markdown("### Recent alerts")
    if len(alerts) == 0:
        st.info("No alerts yet.")
    else:
        recent_alerts = alerts.head(8).copy()
        recent_alerts["timestamp"] = recent_alerts["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(recent_alerts, width="stretch", hide_index=True)
