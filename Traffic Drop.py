#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
from io import BytesIO
import numpy as np

# =========================
# Streamlit Page Setup
# =========================
st.set_page_config(page_title="Daily Traffic Drop Detector", layout="wide")
st.title("📉 Cell Traffic Drop Detection (2G / 3G / 4G)")
st.write("Compare same hour vs yesterday and detect ≥80% traffic drops with 100% availability.")

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
        "traffic_cols": ["CS traffic - Erl", "All_Data_Traffic"],
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
    df["Period start time"] = pd.to_datetime(df["Period start time"])
    df["yesterday_time"] = df["Period start time"] - pd.Timedelta(days=1)

    # Merge with yesterday's data
    merged = df.merge(
        df,
        left_on=[join_key, "yesterday_time"],
        right_on=[join_key, "Period start time"],
        suffixes=("_today", "_yesterday")
    )

    # Filter only cells with 100% availability today
    merged = merged[merged[f"{availability_col}_today"] == 100]

    # Initialize boolean Series for traffic drops
    drop_flag = pd.Series(False, index=merged.index)

    # Compute drop ratios safely for each traffic column
    for col in traffic_cols:
        merged[f"{col}_drop_ratio"] = np.divide(
            merged[f"{col}_today"],
            merged[f"{col}_yesterday"],
            out=np.full_like(merged[f"{col}_today"], np.nan, dtype=float),
            where=merged[f"{col}_yesterday"] != 0
        )

        # Update drop_flag where ratio is below threshold
        drop_flag |= (merged[f"{col}_drop_ratio"] <= drop_threshold)

    # Keep only violating rows
    violations = merged[drop_flag]

    # Columns to keep in output
    keep_cols = ["Period start time_today", join_key, f"{availability_col}_today"]
    for col in traffic_cols:
        keep_cols += [f"{col}_today", f"{col}_yesterday", f"{col}_drop_ratio"]

    return violations[keep_cols]

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

    with st.spinner("Processing data..."):
        for sheet, cfg in sheet_config.items():
            try:
                df = pd.read_excel(uploaded_file, sheet_name=sheet)

                if df.empty:
                    st.warning(f"Sheet '{sheet}' is empty, skipping.")
                    continue

                violations = process_sheet(
                    df,
                    cfg["join_key"],
                    cfg["traffic_cols"],
                    cfg["availability_col"],
                    drop_threshold
                )
                results[sheet] = violations
            except Exception as e:
                st.error(f"Error in sheet '{sheet}': {e}")

    st.success("Processing completed")

    # Display results per sheet
    for sheet, df in results.items():
        st.subheader(f"🚨 {sheet} Violations ({len(df)})")
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info(f"No violations detected in '{sheet}'.")

    # Prepare Excel download
    if results:
        excel_data = to_excel(results)
        st.download_button(
            label="⬇ Download Violations Excel",
            data=excel_data,
            file_name="Traffic_Drop_Violations.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
