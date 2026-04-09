from __future__ import annotations

from pathlib import Path
import os

import pandas as pd
import streamlit as st

from app.db import fetch_all, init_db
from app.appium_servers import list_servers, start_server_for_device, stop_server_for_device
from app.devices import list_devices, sync_devices, validate_batch_device_assignments
from app.importer import import_excel
from app.planner import plan_batch
from app.reports import generate_batch_report
from app.runner import run_batch

st.set_page_config(page_title="Automation Platform", layout="wide")
st.title("Automation Platform")
st.caption("Import jobs, plan AI steps, execute actions, and generate reports.")

init_db()

if "server_host" not in st.session_state:
    st.session_state.server_host = "127.0.0.1"
if "base_port" not in st.session_state:
    st.session_state.base_port = 4723

tab_automation, tab_servers, tab_monitor = st.tabs([
    "Automation",
    "Appium Server Manager",
    "Monitoring",
])

with tab_automation:
    left, right = st.columns([1, 1])

    with left:
        st.subheader("Import")
        upload = st.file_uploader("Upload jobs_template.xlsx", type=["xlsx"])
        if upload and st.button("Import File", type="primary"):
            tmp = Path("data/upload.xlsx")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(upload.getvalue())
            batch_id = import_excel(str(tmp))
            st.success(f"Imported successfully. Batch ID: {batch_id}")

    with right:
        st.subheader("Batch Actions")
        live_mode = st.checkbox("Live Appium mode", value=False)

        batches = fetch_all("SELECT id, source_file, created_at FROM import_batches ORDER BY id DESC")
        batch_options = [f"{row['id']} | {row['source_file']} | {row['created_at']}" for row in batches]
        selected = st.selectbox("Select Batch", options=batch_options if batch_options else ["No batches"], index=0)

        batch_id = None
        if batches:
            batch_id = int(selected.split("|")[0].strip())

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("Validate Device Assignment", disabled=batch_id is None):
                validation = validate_batch_device_assignments(batch_id)
                st.success(f"Validation: {validation}")
        with c2:
            if st.button("Plan Steps", disabled=batch_id is None):
                count = plan_batch(batch_id)
                st.success(f"Planned {count} jobs")
        with c3:
            if st.button("Run Batch", disabled=batch_id is None):
                summary = run_batch(batch_id, use_mock=(not live_mode))
                st.success(f"Run completed: {summary}")
        with c4:
            if st.button("Generate Report", disabled=batch_id is None):
                report = generate_batch_report(batch_id)
                st.success(f"Report ready: {report}")

with tab_servers:
    st.subheader("Appium Server Manager")
    st.caption("Auto-discover devices, map host/base port, and start one Appium server per device ID.")

    c_host, c_port, c_refresh = st.columns([2, 1, 1])
    with c_host:
        server_host = st.text_input("Server Host", key="server_host")
    with c_port:
        base_port = st.number_input("Base Port", min_value=1024, max_value=65535, step=1, key="base_port")
    with c_refresh:
        st.write("")
        if st.button("Refresh Devices"):
            stats = sync_devices(f"http://{server_host}:{int(base_port)}")
            st.success(f"Device discovery complete: {stats}")

    auto_stats = sync_devices(f"http://{server_host}:{int(base_port)}")
    st.caption(f"Auto-discovery status: {auto_stats}")

    devices = list_devices()
    if devices:
        online_device_ids = [d["device_id"] for d in devices if d.get("status") == "online"]
        rows: list[dict[str, object]] = []
        for idx, d in enumerate(devices):
            proposed_port = int(base_port) + idx
            rows.append(
                {
                    "device_id": d.get("device_id"),
                    "platform": d.get("platform"),
                    "model": d.get("model"),
                    "os_version": d.get("os_version"),
                    "status": d.get("status"),
                    "proposed_server_url": f"http://{server_host}:{proposed_port}",
                    "current_server_url": d.get("appium_server_url"),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        selected_device = st.selectbox(
            "Selected Device",
            options=online_device_ids if online_device_ids else ["No online devices"],
            key="server_selected_device",
        )

        s1, s2, s3, s4 = st.columns(4)
        with s1:
            if st.button("Start Server (Selected)", disabled=not online_device_ids):
                idx = online_device_ids.index(selected_device)
                result = start_server_for_device(selected_device, server_host, int(base_port) + idx)
                st.success(f"Start result: {result}")
        with s2:
            if st.button("Stop Server (Selected)", disabled=not online_device_ids):
                result = stop_server_for_device(selected_device)
                st.success(f"Stop result: {result}")
        with s3:
            if st.button("Start Servers (All Online)", disabled=not online_device_ids):
                count = 0
                for idx, device_id in enumerate(online_device_ids):
                    start_server_for_device(device_id, server_host, int(base_port) + idx)
                    count += 1
                st.success(f"Started/checked {count} server(s)")
        with s4:
            if st.button("Stop Servers (All Online)", disabled=not online_device_ids):
                count = 0
                for device_id in online_device_ids:
                    stop_server_for_device(device_id)
                    count += 1
                st.success(f"Stopped {count} server(s)")
    else:
        st.info("No devices discovered. Connect devices and click Refresh Devices.")

    st.subheader("Managed Appium Servers")
    servers = list_servers()
    if servers:
        st.dataframe(pd.DataFrame(servers), use_container_width=True)
    else:
        st.info("No managed Appium servers yet.")

with tab_monitor:
    st.subheader("Jobs")
    job_rows = fetch_all(
        """
        SELECT j.id, j.batch_id, j.account_id, j.device_id, j.intent, j.status, j.priority,
               j.error_message, j.evidence_path, j.created_at
        FROM jobs j
        ORDER BY j.id DESC
        LIMIT 500
        """
    )

    if job_rows:
        df = pd.DataFrame([dict(r) for r in job_rows])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No jobs imported yet.")

    st.subheader("Run Events")
    events = fetch_all(
        "SELECT e.id, e.job_id, e.level, e.message, e.created_at FROM run_events e ORDER BY e.id DESC LIMIT 200"
    )
    if events:
        event_df = pd.DataFrame([dict(r) for r in events])
        st.dataframe(event_df, use_container_width=True)
    else:
        st.info("No run events yet.")
