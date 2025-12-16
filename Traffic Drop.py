#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# =========================
# Streamlit Page Setup
# =========================
st.set_page_config(page_title="Daily Traffic Drop Detector", layout="wide")
st.title("📉 Cell Traffic Drop Detection (2G / 3G / 4G)")
st.write(
    "Compare LAST available hour with the SAME hour yesterday "
    "and detect ≥80% traffic drops with 100% availability."
)

# =========================
# Config for Each Sheet
# =========================
sheet_config = {
    "2G performance": {
        "join_key": "Segment Name",
        "traffic_cols": ["TCH traffic sum in time"],
        "availability_col": "Cell avail accuracy 1s cellL"
    },
    "3G performance": {
        "join_key": "WBTS name",
        "traffic_cols": ["CS traffic - Erl", "All_Data_Traffic_MB"],
        "availability_col": "Cell Availability, excluding blocked by user state (BLU)"
    },
    "4G performance": {
        "join_key": "LNBTS name",
        "traffic_cols": ["Total LTE data volume, DL + UL"],
        "availability_col": "Cell Avail excl BLU"
    }
}

# =========================
# Functions
# =========================
def process_sheet(df, join_key, traffic_cols, availability_col, drop_threshold):

    # Ensure datetime
    df["Period start time"] = pd.to_datetime(df["Period start time"])

    # -------------------------
    # 1️⃣ Identify LAST hour
    # -------------------------
    last_hour = df["Period start time"].max()

    df_today = df[df["Period start time"] == last_hour].copy()
    df_yesterday = df.copy()

    # -------------------------
    # 2️⃣ Create yesterday time
    # -------------------------
    df_today["yesterday_time"] = df_today["Period start time"] - pd.Timedelta(days=1)

    # -------------------------
    # 3️⃣ Merge today vs yesterday
    # -------------------------
    merged = df_today.merge(
        df_yesterday,
        left_on=[join_key, "yesterday_time"],
        right_on=[join_key, "Period start time"],
        suffixes=("_today", "_yesterday")
    )

    # -------------------------
    # 4️⃣ Availability condition
    # -------------------------
    merged = merged[merged[f"{availability_col}_today"] == 100]

    # -------------------------
    # 5️⃣ Traffic drop logic
    # Drop % = (Yesterday - Today) / Yesterday
    # -------------------------
    drop_flag = pd.Series(False, index=merged.index)

    for col in traffic_cols:
        today = merged[f"{col}_today"].astype(float)
        yesterday = merged[f"{col}_yesterday"].astype(float)

        merged[f"{col}_drop_ratio"] = np.where(
            yesterday > 0,
            (yesterday - today) / yesterday,
            np.nan
        )

        drop_flag |= merged[f"{col}_drop_ratio"] >= drop_threshold

    # -------------------------
    # 6️⃣ Output
    # -------------------------
    violations = merged[drop_flag]

    keep_cols = [
        "Period start time_today",
        join_key,
        f"{availability_col}_today"
    ]

    for col in traffic_cols:
        keep_cols += [
            f"{col}_today",
            f"{col}_yesterday",
            f"{col}_drop_ratio"
        ]

    return violations[keep_cols], last_hour


def to_excel(results_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet, df in results_dict.items():
            df.to_excel(writer, sheet_name=sheet, index=False)
    return output.getvalue()

# =========================
# UI Components
# =========================
uploaded_file = st.file_uploader("📂 Upload Performance Excel File", type=["xlsx"])

drop_threshold = st.slider(
    "Traffic drop threshold (%)",
    min_value=50,
    max_value=95,
    value=80
) / 100

if uploaded_file:
    results = {}
    analyzed_hours = {}

    with st.spinner("Processing data..."):
        for sheet, cfg in sheet_config.items():
            try:
                df = pd.read_excel(uploaded_file, sheet_name=sheet)

                if df.empty:
                    st.warning(f"Sheet '{sheet}' is empty, skipping.")
                    continue

                violations, last_hour = process_sheet(
                    df,
                    cfg["join_key"],
                    cfg["traffic_cols"],
                    cfg["availability_col"],
                    drop_threshold
                )

                results[sheet] = violations
                analyzed_hours[sheet] = last_hour

            except Exception as e:
                st.error(f"Error in sheet '{sheet}': {e}")

    st.success("Processing completed")

    # Display analyzed hour
    for sheet, hour in analyzed_hours.items():
        st.info(f"🕒 {sheet} → Analyzed hour: {hour}")

    # Display results
    for sheet, df in results.items():
        st.subheader(f"🚨 {sheet} Violations ({len(df)})")
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info(f"No violations detected in '{sheet}'.")

    # Excel download
    if results:
        excel_data = to_excel(results)
        st.download_button(
            label="⬇ Download Violations Excel",
            data=excel_data,
            file_name="Traffic_Drop_Violations.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
