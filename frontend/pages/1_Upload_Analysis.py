"""Upload and Analysis page.

Milestone 4: upload a WAV file, validate it, show its details and waveform.
Milestone 6: choose a machine and send the recording to the backend for analysis.
"""
import sys
from pathlib import Path

# Let this page import from the project root (so "backend" can be found).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import plotly.graph_objects as go
import streamlit as st

from backend.services.audio_utils import (
    MAX_DURATION_SECONDS,
    MAX_FILE_SIZE_MB,
    MIN_DURATION_SECONDS,
    AudioValidationError,
    downsample_for_plot,
    format_file_size,
    make_playback_wav,
    validate_audio,
)
from components.data_source import (
    BackendError,
    analyse_recording,
    get_model_status,
    list_machines,
)
from components.ui import (
    COLOR_ABNORMAL,
    COLOR_NEUTRAL,
    COLOR_NORMAL,
    apply_style,
    metric_card,
    page_header,
    sidebar_brand,
)

st.set_page_config(page_title="Upload and Analysis - MachineMind", layout="wide")
apply_style()
sidebar_brand()

page_header(
    "Upload and Analysis",
    "Upload a machine-sound recording, inspect it, and send it for analysis",
)


def show_result(result):
    """Display the answer the backend gave for one analysis."""
    analysis = result["analysis"]
    alert = result["alert"]
    is_mock = analysis["is_mock"]
    abnormal = analysis["prediction_label"] == "Potentially Abnormal"

    st.markdown("### Result")
    if result.get("mock_warning"):
        st.warning(result["mock_warning"])
    for message in result.get("warnings", []):
        st.warning(message)

    col1, col2, col3 = st.columns([1.6, 1, 1])
    with col1:
        label = "Prediction (MOCK)" if is_mock else "Prediction"
        metric_card(
            label,
            analysis["prediction_label"],
            f"Machine {analysis['machine_code']}",
            COLOR_ABNORMAL if abnormal else COLOR_NORMAL,
        )
    with col2:
        threshold = analysis["threshold"]
        note = f"Flag threshold: {threshold:g}" if threshold is not None else "No threshold defined"
        metric_card("Anomaly score", f"{analysis['anomaly_score']:.4f}", note, COLOR_NEUTRAL, 0.1)
    with col3:
        metric_card(
            "Alert",
            "Generated" if alert else "None",
            "Saved in the alert list" if alert else "No alert for this result",
            COLOR_ABNORMAL if alert else COLOR_NORMAL,
            0.2,
        )

    st.info(f"What the score means: {result['score_note']}")
    if alert:
        st.warning(alert["message"])
    st.caption(
        f"Model: {analysis['model_name']} (version {analysis['model_version']}). "
        f"Saved in the history as analysis #{analysis['id']}."
    )


st.info(
    "Upload a WAV file to check it and see its waveform. To analyse it, choose a machine and "
    "press the Analyse button. While the placeholder model is active, every result is a MOCK "
    "and is labelled as one."
)

uploaded = st.file_uploader(
    "Upload a WAV recording",
    type=["wav"],
    help=(
        f"WAV only. Length {MIN_DURATION_SECONDS:.0f} to {MAX_DURATION_SECONDS:.0f} seconds, "
        f"up to {MAX_FILE_SIZE_MB} MB."
    ),
)

if uploaded is None:
    st.caption(
        f"Accepted: WAV files, {MIN_DURATION_SECONDS:.0f} to {MAX_DURATION_SECONDS:.0f} seconds, "
        f"up to {MAX_FILE_SIZE_MB} MB, mono or multi-channel."
    )
    st.stop()

file_bytes = uploaded.getvalue()

try:
    info, samples = validate_audio(file_bytes, uploaded.name)
except AudioValidationError as error:
    st.error(f"This recording cannot be used. {error}")
    st.stop()
except Exception as error:
    st.error(f"Unexpected problem while checking the file: {error}")
    st.stop()

st.success(
    f"{info.filename} is a readable WAV recording and passed the upload checks. "
    "This is not an analysis result."
)
if info.is_silent:
    st.warning("This recording looks completely silent. Check that the right file was uploaded.")

# Recording details
st.markdown("### Recording details")
col1, col2, col3, col4 = st.columns(4)
with col1:
    metric_card("Duration", f"{info.duration_seconds:.2f} s", "Length of the recording", COLOR_NEUTRAL, 0.0)
with col2:
    metric_card("Sample rate", f"{info.sample_rate:,} Hz", "Samples per second", "#7C4DFF", 0.1)
with col3:
    metric_card("Channels", info.channels, "Microphones in the file", COLOR_NORMAL, 0.2)
with col4:
    metric_card("File size", format_file_size(info.size_bytes), "On disk", COLOR_NEUTRAL, 0.3)

with st.expander("More technical details"):
    st.markdown(
        f"- File name: `{info.filename}`\n"
        f"- Format: `{info.format_name}` / `{info.subtype}`\n"
        f"- Samples per channel: `{info.frames:,}`\n"
        f"- Peak amplitude: `{info.peak_amplitude:.4f}` (scale 0 to 1)\n"
        f"- RMS level: `{info.rms:.4f}` (scale 0 to 1)"
    )

# Waveform
st.markdown("### Waveform")
if info.channels > 1:
    options = [f"Channel {number}" for number in range(1, info.channels + 1)]
    options.append("Average of all channels")
    choice = st.selectbox("Channel to display", options, index=0)
    if choice == "Average of all channels":
        signal = samples.mean(axis=1)
    else:
        signal = samples[:, options.index(choice)]
else:
    choice = "Channel 1"
    signal = samples[:, 0]

positions, values = downsample_for_plot(signal)
seconds = positions / info.sample_rate

figure = go.Figure(
    go.Scatter(
        x=seconds,
        y=values,
        mode="lines",
        line=dict(color="#00E5FF", width=1),
        name=choice,
    )
)
figure.update_layout(
    template="plotly_dark",
    height=340,
    margin=dict(l=10, r=10, t=10, b=10),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    xaxis_title="Time (s)",
    yaxis_title="Amplitude",
    showlegend=False,
)
figure.update_xaxes(gridcolor="rgba(255,255,255,0.06)")
figure.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
st.plotly_chart(figure, width="stretch")
st.caption(f"Showing: {choice}. Amplitude is scaled from -1 to 1.")

# Listen
st.markdown("### Listen")
st.audio(make_playback_wav(samples, info.sample_rate), format="audio/wav")
st.caption("Mono mix of all channels, for listening only. It is not what the model will receive.")

# Analysis
st.markdown("### Analysis")
try:
    machine_list = list_machines()
    model_status = get_model_status()
except BackendError as error:
    st.error(str(error))
    st.stop()

if not model_status["is_real"]:
    st.warning(
        f"Real ML inference is not connected. {model_status['message']} "
        "Any result below is a MOCK placeholder, not a genuine prediction."
    )

if not machine_list:
    st.info("Register a machine on the Machines page first. Every analysis is linked to a machine.")
    st.stop()

machine_options = {f"{m['machine_id']} - {m['name']}": m["id"] for m in machine_list}
selected = st.selectbox("Machine this recording belongs to", list(machine_options))
file_key = f"{uploaded.name}:{uploaded.size}"

if st.button("Analyse recording", type="primary"):
    with st.spinner("Analysing the recording..."):
        try:
            result = analyse_recording(machine_options[selected], uploaded.name, file_bytes)
        except BackendError as error:
            st.session_state.pop("last_result", None)
            st.error(f"The analysis was not completed, and nothing was saved. {error}")
        else:
            st.session_state["last_result"] = {"file_key": file_key, "result": result}

saved = st.session_state.get("last_result")
if saved and saved["file_key"] == file_key:
    show_result(saved["result"])
