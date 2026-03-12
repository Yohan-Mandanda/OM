from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from om_eticket_downloader import load_accounts_from_file, run_eticket_downloads


st.set_page_config(page_title="OM E-Ticket Downloader", page_icon="🎫", layout="centered")

st.title("OM E-Ticket Downloader")
st.caption("Automate login + e-ticket download for multiple OM billetterie accounts.")

with st.form("run_form"):
    spreadsheet = st.file_uploader("Accounts file (CSV or XLSX)", type=["csv", "xlsx", "xlsm"])
    match_name = st.text_input(
        "Match(es) to download",
        placeholder="Ex: Lille   or   Auxerre,Lille",
    )
    output_dir = st.text_input("Output folder", value="downloads")
    headless = st.checkbox("Headless mode", value=False)
    login_wait_seconds = st.number_input(
        "Max wait for login / captcha solve (seconds)",
        min_value=30,
        max_value=600,
        value=120,
        step=15,
    )
    step_wait_seconds = st.number_input(
        "Wait between key actions (seconds)",
        min_value=0,
        max_value=30,
        value=10,
        step=1,
    )
    debug = st.checkbox("Debug mode (verbose logs + screenshots/html)", value=True)
    debug_dir = st.text_input("Debug output folder", value="debug")
    slow_mo_ms = st.number_input(
        "Slow motion per browser action (ms)",
        min_value=0,
        max_value=2000,
        value=0,
        step=50,
    )
    submitted = st.form_submit_button("Start download")

if submitted:
    if spreadsheet is None:
        st.error("Please upload a CSV or XLSX file first.")
        st.stop()

    if not match_name.strip():
        st.error("Please enter the match name.")
        st.stop()

    logs_placeholder = st.empty()
    live_logs = []

    def log(msg: str) -> None:
        live_logs.append(msg)
        logs_placeholder.code("\n".join(live_logs[-25:]), language="text")

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(spreadsheet.name).suffix) as tmp:
        tmp.write(spreadsheet.getbuffer())
        tmp_path = Path(tmp.name)

    try:
        accounts = load_accounts_from_file(tmp_path)
    except Exception as exc:
        st.error(f"Could not read account file: {exc}")
        st.stop()
    finally:
        tmp_path.unlink(missing_ok=True)

    if not accounts:
        st.warning("No valid accounts found (need email + password for each row).")
        st.stop()

    st.info(f"Loaded {len(accounts)} account(s). Running automation...")

    try:
        results = run_eticket_downloads(
            accounts=accounts,
            match_name=match_name.strip(),
            output_dir=Path(output_dir).expanduser(),
            headless=headless,
            login_wait_seconds=int(login_wait_seconds),
            step_wait_seconds=int(step_wait_seconds),
            slow_mo_ms=int(slow_mo_ms),
            debug=debug,
            debug_dir=Path(debug_dir).expanduser(),
            progress_cb=log,
        )
    except Exception as exc:
        st.error(f"Automation crashed: {exc}")
        st.stop()

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    if success_count:
        st.success(f"{success_count} account(s) completed successfully.")
    if fail_count:
        st.error(f"{fail_count} account(s) failed.")

    for result in results:
        if result.success:
            st.write(f"✅ **{result.email}** — {len(result.saved_files)} file(s) downloaded")
            if result.saved_files:
                st.code("\n".join(str(p) for p in result.saved_files), language="text")
        else:
            st.write(f"❌ **{result.email}** — {result.error}")
