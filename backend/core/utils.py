import math

import numpy as np
import pandas as pd
from flask import jsonify

from .state import store


def safe_float(v, default=0.0):
    """Safely convert value to float, returning default for NaN/Inf."""
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def clean_value(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return safe_float(v)
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d") if not pd.isna(v) else None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def records_to_json(df):
    """Convert a DataFrame to a JSON-safe list of dicts."""
    result = []
    for rec in df.to_dict(orient="records"):
        result.append({k: clean_value(v) for k, v in rec.items()})
    return result


def apply_filters(df, args):
    """Apply global query-param filters to a DataFrame."""
    d = df.copy()

    if args.get("company_code"):
        vals = [v.strip() for v in args["company_code"].split(",")]
        d = d[d["Company Code"].astype(str).isin(vals)]

    if args.get("supplier"):
        vals = [v.strip() for v in args["supplier"].split(",")]
        sup_col = "Name of Supplier" if "Name of Supplier" in d.columns else "Supplier/Supplying Plant"
        d = d[d[sup_col].isin(vals)]

    if args.get("plant"):
        vals = [v.strip() for v in args["plant"].split(",")]
        d = d[d["Plant"].astype(str).isin(vals)]

    if args.get("purchasing_group"):
        vals = [v.strip() for v in args["purchasing_group"].split(",")]
        d = d[d["Purchasing Group"].astype(str).isin(vals)]

    if args.get("material"):
        vals = [v.strip() for v in args["material"].split(",")]
        search_col = "Short Text" if "Short Text" in d.columns else "Material"
        d = d[d[search_col].isin(vals)]

    if args.get("currency"):
        vals = [v.strip() for v in args["currency"].split(",")]
        cur_col = "Currency_x" if "Currency_x" in d.columns else "Currency"
        d = d[d[cur_col].astype(str).str.strip().isin(vals)]

    if args.get("date_from"):
        try:
            date_from = pd.to_datetime(args["date_from"])
            d = d[d["Document Date"] >= date_from]
        except Exception:
            pass

    if args.get("date_to"):
        try:
            date_to = pd.to_datetime(args["date_to"])
            d = d[d["Document Date"] <= date_to]
        except Exception:
            pass

    return d


def get_merged():
    """Return merged_df or an error response tuple."""
    df = store.get("merged_df")
    if df is None:
        return None, jsonify({"error": "Data not merged yet. Please upload and merge files first."}), 400
    return df, None, None


def perform_currency_conversion(df):
    """
    Apply AUDITED currency conversion rules.
    CRITICAL FIX: Use 'Net Order Value' instead of manual (Price * Qty).
    SAP 'Net Price' is often per 'Price unit', causing 10,000x inflation if ignored.
    """
    df = df.copy()

    df["Exchange Rate"] = pd.to_numeric(df.get("Exchange Rate", 1), errors="coerce").fillna(1.0)
    df["Exchange Rate"] = df["Exchange Rate"].apply(lambda x: 1.0 if x <= 0 else x)

    df["Net Order Value"] = pd.to_numeric(df["Net Order Value"], errors="coerce").fillna(0.0)
    df["Still to be delivered (value)"] = pd.to_numeric(df["Still to be delivered (value)"], errors="coerce").fillna(0.0)

    cur_col = "Currency_x" if "Currency_x" in df.columns else "Currency"
    df[cur_col] = df[cur_col].astype(str).str.strip()

    df["Total_Spend_INR"] = df["Net Order Value"] * df["Exchange Rate"]
    df["Open_Value_INR"] = df["Still to be delivered (value)"] * df["Exchange Rate"]

    df["Document Date"] = pd.to_datetime(df["Document Date"], errors="coerce")
    df["Delivery date"] = pd.to_datetime(df["Delivery date"], errors="coerce")

    total_cr = df["Total_Spend_INR"].sum() / 1e7
    print(f"--- AUDIT LOG ---")
    print(f"Total Rows: {len(df)}")
    print(f"Unique Currencies: {df[cur_col].unique()}")
    print(f"Total Spend: {total_cr:.2f} Cr (INR)")
    print(f"-----------------")

    return df