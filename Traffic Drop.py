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

    return violations[keep_cols]
