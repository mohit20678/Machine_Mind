"""Machines page: register machines and see the registered ones.

Milestone 6: the page talks to the backend, which saves machines in the SQLite database.
"""
import streamlit as st

from components.data_source import (
    MACHINE_TYPES,
    BackendError,
    load_machines_df,
    register_machine,
)
from components.ui import apply_style, page_header, sidebar_brand

st.set_page_config(page_title="Machines - MachineMind", layout="wide")
apply_style()
sidebar_brand()

page_header("Machines", "Register machines and link recordings to them")

st.caption(
    "MachineMind analyses uploaded recordings. It is not connected to live sensors, "
    "so a registered machine is only a label that recordings are linked to."
)

st.markdown("### Register a machine")
with st.form("register_machine_form"):
    left, right = st.columns(2)
    with left:
        machine_id = st.text_input(
            "Machine ID",
            placeholder="for example PUMP-01",
            help="Letters, numbers, hyphen or underscore. Must be unique. Cannot be changed later.",
        )
        machine_type = st.selectbox("Machine type", MACHINE_TYPES)
    with right:
        name = st.text_input("Machine name", placeholder="for example Cooling water pump")
        location = st.text_input("Location (optional)", placeholder="for example Plant 1, Line 2")
    submitted = st.form_submit_button("Register machine")

if submitted:
    try:
        saved = register_machine(machine_id, name, machine_type, location)
        st.success(f"Registered machine {saved['machine_id']} ({saved['name']}).")
    except BackendError as error:
        st.error(str(error))

st.markdown("### Registered machines")
try:
    machines = load_machines_df()
except BackendError as error:
    st.error(str(error))
    st.stop()

if machines.empty:
    st.info("No machines registered yet. Use the form above to add the first one.")
else:
    table = machines.rename(
        columns={
            "machine_id": "Machine ID",
            "name": "Name",
            "machine_type": "Type",
            "location": "Location",
            "analysis_count": "Analyses",
            "created_at": "Registered",
        }
    )
    st.dataframe(table, width="stretch", hide_index=True)
    st.caption(
        f"{len(machines)} machine(s). Saved in the database file data/machinemind.db, "
        "so they are still here after you restart the app."
    )
