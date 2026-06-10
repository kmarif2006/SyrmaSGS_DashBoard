"""
Syrma SGS Enterprise Procurement Analytics Platform
Flask Backend — AUDITED & CORRECTED VERSION
Fixes: Spend Inflation (Price Unit), Open Value mapping, and Currency Logic.
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
import io
import json
import math
import traceback
import urllib.request
import urllib.error
import os
from datetime import datetime
from services.grir_analytics_service import GRIRAnalyticsService
from services.grir_reconciliation_engine import aggregate_by_po_item
from services.grir_kpi_builder import (
    build_executive_kpis, build_aging_analysis, build_top_management_insights, build_chart_data
)

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"])

# ─── GR/IR Analytics Service ─────────────────────────────────────────────────
grir_service = GRIRAnalyticsService()

# ─── Global In-Memory Store ──────────────────────────────────────────────────
store = {
    "transaction_df": None,
    "master_df": None,
    "merged_df": None,
    "transaction_filename": None,
    "master_filename": None,
}

# ─── GRIR Analytics State ────────────────────────────────────────────────────
grir_state = {
    "grir_df": None,
    "me2n_df": None,
    "ekko_df": None,
    "reconciled_df": None,
    "kpis": None,
    "aging_analysis": None,
    "top_insights": None,
    "chart_data": None,
    "analysis_timestamp": None,
}


# ─── Utility Helpers ─────────────────────────────────────────────────────────

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
        # Material column in Sheet1 is usually 'Short Text' for display
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

    # Numeric coercions
    df["Exchange Rate"] = pd.to_numeric(df.get("Exchange Rate", 1), errors="coerce").fillna(1.0)
    df["Exchange Rate"] = df["Exchange Rate"].apply(lambda x: 1.0 if x <= 0 else x)
    
    # We trust 'Net Order Value' as the line total in source currency
    # It already handles (Price / Price Unit) * Qty
    df["Net Order Value"] = pd.to_numeric(df["Net Order Value"], errors="coerce").fillna(0.0)
    
    # 'Still to be delivered (value)' is the true "Open Value" in this dataset
    df["Still to be delivered (value)"] = pd.to_numeric(df["Still to be delivered (value)"], errors="coerce").fillna(0.0)

    # Determine which currency column to use
    cur_col = "Currency_x" if "Currency_x" in df.columns else "Currency"
    df[cur_col] = df[cur_col].astype(str).str.strip()

    # Calculations
    # Amount_INR = Amount_Source * Exchange_Rate
    df["Total_Spend_INR"] = df["Net Order Value"] * df["Exchange Rate"]
    df["Open_Value_INR"] = df["Still to be delivered (value)"] * df["Exchange Rate"]

    # Parse dates
    df["Document Date"] = pd.to_datetime(df["Document Date"], errors="coerce")
    df["Delivery date"] = pd.to_datetime(df["Delivery date"], errors="coerce")

    # Log metrics for Audit Verification
    total_cr = df["Total_Spend_INR"].sum() / 1e7
    print(f"--- AUDIT LOG ---")
    print(f"Total Rows: {len(df)}")
    print(f"Unique Currencies: {df[cur_col].unique()}")
    print(f"Total Spend: {total_cr:.2f} Cr (INR)")
    print(f"-----------------")

    return df


# ─── Upload Endpoints ─────────────────────────────────────────────────────────

@app.route("/api/upload-transactions", methods=["POST"])
def upload_transactions():
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted"}), 400
    try:
        # Save to disk as me2n.csv, gracefully handle permission errors if file is locked
        file_path = os.path.join(os.path.dirname(__file__), "me2n.csv")
        try:
            file_bytes = file.read()
            with open(file_path, "wb") as f:
                f.write(file_bytes)
        except PermissionError:
            print(f"Permission denied writing to {file_path}. It might be open in another program.")
        except Exception as e:
            print(f"Failed to write to {file_path}: {e}")
        finally:
            file.seek(0)

        # Using low_memory=False for large data
        df = pd.read_csv(file, encoding="utf-8", low_memory=False)
        if df.empty:
            return jsonify({"error": "Uploaded file is empty"}), 400
        
        # Mandatory columns for audited logic
        required = ["Purchasing Document", "Net Price", "Order Quantity", "Currency", "Net Order Value", "Still to be delivered (value)"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return jsonify({
                "error": f"Missing required columns in Transaction CSV: {missing}", 
                "available": list(df.columns)
            }), 400
        
        store["transaction_df"] = df
        store["transaction_filename"] = file.filename
        store["merged_df"] = None  # Invalidate merge
        
        # Sync with GRIR Service
        try:
            grir_service.upload_df(df, "me2n.csv")
        except Exception as e:
            print(f"Warning: Failed to sync with GRIR service: {e}")

        return jsonify({
            "message": "Transaction data uploaded successfully",
            "filename": file.filename,
            "rows": len(df),
            "columns": list(df.columns),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload-master", methods=["POST"])
def upload_master():
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted"}), 400
    try:
        # Save to disk as EKKO.csv, gracefully handle permission errors
        file_path = os.path.join(os.path.dirname(__file__), "EKKO.csv")
        try:
            file_bytes = file.read()
            with open(file_path, "wb") as f:
                f.write(file_bytes)
        except PermissionError:
            print(f"Permission denied writing to {file_path}. It might be open in another program.")
        except Exception as e:
            print(f"Failed to write to {file_path}: {e}")
        finally:
            file.seek(0)

        df = pd.read_csv(file, encoding="utf-8", low_memory=False)
        if df.empty:
            return jsonify({"error": "Uploaded file is empty"}), 400
        required = ["Purchasing Document", "Currency", "Exchange Rate"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return jsonify({"error": f"Missing required columns in Master CSV: {missing}", "available": list(df.columns)}), 400
        
        store["master_df"] = df
        store["master_filename"] = file.filename
        store["merged_df"] = None  # Invalidate merge
        
        # Sync with GRIR Service
        try:
            grir_service.upload_df(df, "EKKO.csv")
        except Exception as e:
            print(f"Warning: Failed to sync with GRIR service: {e}")

        return jsonify({
            "message": "Master data uploaded successfully",
            "filename": file.filename,
            "rows": len(df),
            "columns": list(df.columns),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/merge", methods=["POST"])
def merge_data():
    if store["transaction_df"] is None:
        return jsonify({"error": "Transaction data not uploaded"}), 400
    if store["master_df"] is None:
        return jsonify({"error": "Master purchasing data not uploaded"}), 400
    try:
        txn = store["transaction_df"]
        master = store["master_df"]

        # Drop duplicates in master to prevent many-to-many merge explosions
        master_clean = master.drop_duplicates(subset=["Purchasing Document"])

        # Selective master columns
        master_cols = ["Purchasing Document", "Company Code", "Exchange Rate"]
        for col in ["Deletion indicator", "Currency", "Purchasing Doc. Type"]:
            if col in master_clean.columns:
                master_cols.append(col)

        merged = pd.merge(
            txn,
            master_clean[master_cols],
            on="Purchasing Document",
            how="left",
        )
        merged = perform_currency_conversion(merged)
        store["merged_df"] = merged

        total_spend = safe_float(merged["Total_Spend_INR"].sum())
        return jsonify({
            "message": "Data merged and processed successfully",
            "merged_rows": len(merged),
            "total_spend_inr": total_spend,
            "unique_pos": int(merged["Purchasing Document"].nunique()),
            "unique_suppliers": int(merged["Name of Supplier"].nunique()) if "Name of Supplier" in merged.columns else 0,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Merge failed: {str(e)}"}), 500


# ─── Status ───────────────────────────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({
        "transaction_uploaded": store["transaction_df"] is not None,
        "master_uploaded": store["master_df"] is not None,
        "merged": store["merged_df"] is not None,
        "transaction_rows": len(store["transaction_df"]) if store["transaction_df"] is not None else 0,
        "master_rows": len(store["master_df"]) if store["master_df"] is not None else 0,
        "merged_rows": len(store["merged_df"]) if store["merged_df"] is not None else 0,
        "transaction_filename": store.get("transaction_filename"),
        "master_filename": store.get("master_filename"),
    })


# ─── KPI Summary ─────────────────────────────────────────────────────────────

@app.route("/api/summary", methods=["GET"])
def summary():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)

    total_spend = safe_float(df["Total_Spend_INR"].sum())
    total_open = safe_float(df["Open_Value_INR"].sum())
    efficiency = round((1 - (total_open / total_spend) if total_spend > 0 else 1) * 100, 2)

    del_col = next((c for c in ["Deletion indicator_y", "Deletion indicator_x", "Deletion indicator"] if c in df.columns), None)
    deleted_pos = 0
    if del_col:
        deleted_pos = int(df[df[del_col].notna() & (df[del_col].astype(str).str.strip() != "")]["Purchasing Document"].nunique())

    return jsonify({
        "total_pos": int(df["Purchasing Document"].nunique()),
        "total_spend_inr": total_spend,
        "total_open_value_inr": total_open,
        "total_suppliers": int(df["Name of Supplier"].nunique()) if "Name of Supplier" in df.columns else 0,
        "total_materials": int(df["Short Text"].nunique()) if "Short Text" in df.columns else 0,
        "total_quantity": safe_float(df["Order Quantity"].sum()),
        "deleted_pos": deleted_pos,
        "procurement_efficiency": efficiency,
    })


# ─── Analysis Endpoints ───────────────────────────────────────────────────────

@app.route("/api/supplier-analysis", methods=["GET"])
def supplier_analysis():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)
    top_n = int(request.args.get("top", 15))

    sup_col = "Name of Supplier" if "Name of Supplier" in df.columns else "Supplier/Supplying Plant"
    agg = df.groupby(sup_col).agg(
        Total_Spend_INR=("Total_Spend_INR", "sum"),
        PO_Count=("Purchasing Document", "nunique"),
        Open_Value_INR=("Open_Value_INR", "sum")
    ).reset_index().rename(columns={sup_col: "Supplier"}).sort_values("Total_Spend_INR", ascending=False).head(top_n)
    
    return jsonify(records_to_json(agg))


@app.route("/api/company-analysis", methods=["GET"])
def company_analysis():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)

    agg = df.groupby("Company Code").agg(
        Total_Spend_INR=("Total_Spend_INR", "sum"),
        PO_Count=("Purchasing Document", "nunique"),
        Open_Value_INR=("Open_Value_INR", "sum")
    ).reset_index().sort_values("Total_Spend_INR", ascending=False)
    return jsonify(records_to_json(agg))


@app.route("/api/material-analysis", methods=["GET"])
def material_analysis():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)
    top_n = int(request.args.get("top", 20))

    search_col = "Short Text" if "Short Text" in df.columns else "Material"
    agg = df.groupby(search_col).agg(
        Total_Spend_INR=("Total_Spend_INR", "sum"),
        Total_Quantity=("Order Quantity", "sum"),
        PO_Count=("Purchasing Document", "nunique")
    ).reset_index().rename(columns={search_col: "Material"}).sort_values("Total_Spend_INR", ascending=False).head(top_n)
    return jsonify(records_to_json(agg))


@app.route("/api/open-value-analysis", methods=["GET"])
def open_value_analysis():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)
    top_n = int(request.args.get("top", 15))

    sup_col = "Name of Supplier" if "Name of Supplier" in df.columns else "Supplier/Supplying Plant"
    agg = df.groupby(sup_col).agg(
        Open_Value_INR=("Open_Value_INR", "sum"),
        Total_Spend_INR=("Total_Spend_INR", "sum")
    ).reset_index().rename(columns={sup_col: "Supplier"})
    
    agg = agg[agg["Open_Value_INR"] > 0].sort_values("Open_Value_INR", ascending=False).head(top_n)
    return jsonify(records_to_json(agg))


@app.route("/api/monthly-trend", methods=["GET"])
def monthly_trend():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)

    df2 = df.dropna(subset=["Document Date"]).copy()
    df2["Month"] = df2["Document Date"].dt.to_period("M").astype(str)
    agg = df2.groupby("Month").agg(
        Total_Spend_INR=("Total_Spend_INR", "sum"),
        PO_Count=("Purchasing Document", "nunique")
    ).reset_index().sort_values("Month")
    return jsonify(records_to_json(agg))


@app.route("/api/plant-analysis", methods=["GET"])
def plant_analysis():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)

    agg = df.groupby("Plant").agg(
        Total_Spend_INR=("Total_Spend_INR", "sum"),
        PO_Count=("Purchasing Document", "nunique")
    ).reset_index().sort_values("Total_Spend_INR", ascending=False)
    return jsonify(records_to_json(agg))


@app.route("/api/purchasing-group-analysis", methods=["GET"])
def purchasing_group_analysis():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)

    agg = df.groupby("Purchasing Group").agg(
        Total_Spend_INR=("Total_Spend_INR", "sum"),
        PO_Count=("Purchasing Document", "nunique")
    ).reset_index().sort_values("Total_Spend_INR", ascending=False)
    return jsonify(records_to_json(agg))


@app.route("/api/item-category-analysis", methods=["GET"])
def item_category_analysis():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)

    cat_col = "Material Group" if "Material Group" in df.columns else "Item Category"
    df2 = df[df[cat_col].notna()].copy()
    agg = df2.groupby(cat_col).agg(
        Total_Spend_INR=("Total_Spend_INR", "sum"),
        Count=("Purchasing Document", "count")
    ).reset_index().rename(columns={cat_col: "name", "Total_Spend_INR": "value", "Count": "count"})
    return jsonify(records_to_json(agg.sort_values("value", ascending=False)))


@app.route("/api/aging", methods=["GET"])
def aging():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)
    today = pd.Timestamp.today().normalize()

    df2 = df.dropna(subset=["Document Date"]).copy()
    df2["Age_Days"] = (today - df2["Document Date"]).dt.days.clip(lower=0)

    def bucket(d):
        if d <= 30: return "0-30 days"
        if d <= 60: return "31-60 days"
        if d <= 90: return "61-90 days"
        return "90+ days"

    df2["Bucket"] = df2["Age_Days"].apply(bucket)
    agg = df2.groupby("Bucket").agg(
        PO_Count=("Purchasing Document", "nunique"),
        Total_Spend_INR=("Total_Spend_INR", "sum")
    ).reset_index()
    
    order = {"0-30 days": 0, "31-60 days": 1, "61-90 days": 2, "90+ days": 3}
    agg["_sort"] = agg["Bucket"].map(order)
    return jsonify(records_to_json(agg.sort_values("_sort").drop(columns=["_sort"])))


@app.route("/api/delivery-analysis", methods=["GET"])
def delivery_analysis():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)
    today = pd.Timestamp.today().normalize()

    df2 = df.dropna(subset=["Delivery date"]).copy()
    if df2.empty: return jsonify({"delayed": 0, "on_time": 0, "total": 0, "delay_pct": 0, "on_time_pct": 0, "chart": []})

    df2["Is_Delayed"] = df2["Delivery date"] < today
    delayed = int(df2["Is_Delayed"].sum())
    on_time = int((~df2["Is_Delayed"]).sum())
    total = delayed + on_time
    return jsonify({
        "delayed": delayed,
        "on_time": on_time,
        "total": total,
        "delay_pct": round(delayed/total*100, 1) if total > 0 else 0,
        "on_time_pct": round(on_time/total*100, 1) if total > 0 else 0,
        "chart": [{"name": "On Time", "value": on_time}, {"name": "Delayed", "value": delayed}]
    })


@app.route("/api/currency-exposure", methods=["GET"])
def currency_exposure():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)

    cur_col = "Currency_x" if "Currency_x" in df.columns else "Currency"
    agg = df.groupby(cur_col).agg(
        Original_Spend=("Net Order Value", "sum"),
        Converted_INR=("Total_Spend_INR", "sum"),
        PO_Count=("Purchasing Document", "nunique")
    ).reset_index().rename(columns={cur_col: "Currency"})
    return jsonify(records_to_json(agg))


@app.route("/api/pareto", methods=["GET"])
def pareto():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)
    top_n = int(request.args.get("top", 10))

    sup_col = "Name of Supplier" if "Name of Supplier" in df.columns else "Supplier/Supplying Plant"
    total_spend = safe_float(df["Total_Spend_INR"].sum())

    agg = df.groupby(sup_col)["Total_Spend_INR"].sum().reset_index().rename(columns={sup_col: "Supplier", "Total_Spend_INR": "Spend_INR"}).sort_values("Spend_INR", ascending=False).head(top_n)
    agg["Spend_Pct"] = (agg["Spend_INR"] / total_spend * 100).round(2) if total_spend > 0 else 0
    agg["Cumulative_Pct"] = agg["Spend_Pct"].cumsum().round(2)
    return jsonify(records_to_json(agg))


@app.route("/api/monthly-company-trend", methods=["GET"])
def monthly_company_trend():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)

    df2 = df.dropna(subset=["Document Date"]).copy()
    df2["Month"] = df2["Document Date"].dt.to_period("M").astype(str)
    agg = df2.groupby(["Month", "Company Code"])["Total_Spend_INR"].sum().reset_index()
    companies = sorted(agg["Company Code"].astype(str).unique().tolist())
    pivot = agg.pivot(index="Month", columns="Company Code", values="Total_Spend_INR").fillna(0).reset_index()
    pivot.columns = [str(c) for c in pivot.columns]
    return jsonify({"data": records_to_json(pivot.sort_values("Month")), "companies": companies})


@app.route("/api/ai-insights", methods=["GET"])
def ai_insights():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)

    insights = []
    total_spend = safe_float(df["Total_Spend_INR"].sum())
    total_open = safe_float(df["Open_Value_INR"].sum())
    sup_col = "Name of Supplier" if "Name of Supplier" in df.columns else "Supplier/Supplying Plant"

    # --- Insight Logic ---
    sup_agg = df.groupby(sup_col)["Total_Spend_INR"].sum().sort_values(ascending=False)
    if len(sup_agg) > 0 and total_spend > 0:
        top_pct = round(safe_float(sup_agg.iloc[0]) / total_spend * 100, 1)
        insights.append({
            "id": "top_supplier", "type": "supplier", "severity": "warning" if top_pct > 30 else "info",
            "icon": "TrendingUp", "title": "Top Supplier Concentration",
            "message": f"{str(sup_agg.index[0])[:40]} contributes {top_pct}% of total spend.", "metric": f"{top_pct}%"
        })

    open_pct = round(total_open / total_spend * 100, 1) if total_spend > 0 else 0
    insights.append({
        "id": "open_value", "type": "open_value", "severity": "warning" if open_pct > 20 else "success",
        "icon": "Clock", "title": "Open PO Exposure",
        "message": f"₹{total_open/1e7:.1f} Cr remains to be delivered ({open_pct}% of spend).", "metric": f"₹{total_open/1e7:.1f} Cr"
    })

    return jsonify(insights)


@app.route("/api/filters", methods=["GET"])
def filters():
    df, err, code = get_merged()
    if err: return err, code
    cur_col = "Currency_x" if "Currency_x" in df.columns else "Currency"
    sup_col = "Name of Supplier" if "Name of Supplier" in df.columns else "Supplier/Supplying Plant"
    
    return jsonify({
        "company_codes": sorted(df["Company Code"].dropna().astype(str).unique().tolist()),
        "suppliers": sorted(df[sup_col].dropna().unique().tolist())[:300],
        "plants": sorted(df["Plant"].dropna().astype(str).unique().tolist()),
        "purchasing_groups": sorted(df["Purchasing Group"].dropna().astype(str).unique().tolist()),
        "currencies": sorted(df[cur_col].dropna().astype(str).str.strip().unique().tolist()),
        "materials": sorted(df["Short Text"].dropna().unique().tolist())[:500],
        "date_range": {"min": str(df["Document Date"].min()), "max": str(df["Document Date"].max())}
    })


@app.route("/api/search", methods=["GET"])
def search():
    df, err, code = get_merged()
    if err: return err, code
    query = request.args.get("q", "").strip().lower()
    if not query: return jsonify([])
    mask = df["Purchasing Document"].astype(str).str.lower().str.contains(query) | df["Name of Supplier"].astype(str).str.lower().str.contains(query)
    return jsonify(records_to_json(df[mask].head(50)))


@app.route("/api/export", methods=["GET"])
def export_csv():
    df, err, code = get_merged()
    if err: return err, code
    df = apply_filters(df, request.args)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode("utf-8")), mimetype="text/csv", as_attachment=True, download_name="procurement_audit_export.csv")



@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user_message = data.get("message", "")
    history = data.get("history", [])
    filters = data.get("filters", {})

    system_prompt = (
        "You are the Syrma SGS Procurement Analytics Assistant, an AI chatbot built to help "
        "users analyze and understand their procurement, purchase orders, and supplier data.\n\n"
        "Here is the current state of the procurement data in the system:\n"
    )

    df = store.get("merged_df")
    if df is not None:
        try:
            # Apply active filters if any
            if filters:
                df = apply_filters(df, filters)
            
            total_spend = safe_float(df["Total_Spend_INR"].sum())
            total_open = safe_float(df["Open_Value_INR"].sum())
            efficiency = round((1 - (total_open / total_spend) if total_spend > 0 else 1) * 100, 2)
            pos = int(df["Purchasing Document"].nunique())
            
            sup_col = "Name of Supplier" if "Name of Supplier" in df.columns else "Supplier/Supplying Plant"
            suppliers = int(df[sup_col].nunique()) if sup_col in df.columns else 0
            
            search_col = "Short Text" if "Short Text" in df.columns else "Material"
            materials = int(df[search_col].nunique()) if search_col in df.columns else 0
            
            # Top 5 Suppliers by Spend
            top_sups = df.groupby(sup_col)["Total_Spend_INR"].sum().sort_values(ascending=False).head(5)
            top_sups_str = "\n".join([f"- {sup}: ₹{val/1e7:.2f} Cr" for sup, val in top_sups.items()])
            
            # Top 5 Plants by Spend
            top_plants = df.groupby("Plant")["Total_Spend_INR"].sum().sort_values(ascending=False).head(5)
            top_plants_str = "\n".join([f"- Plant {plant}: ₹{val/1e7:.2f} Cr" for plant, val in top_plants.items()])

            # Top 5 Materials by Spend
            top_mats = df.groupby(search_col)["Total_Spend_INR"].sum().sort_values(ascending=False).head(5)
            top_mats_str = "\n".join([f"- {mat}: ₹{val/1e7:.2f} Cr" for mat, val in top_mats.items()])

            system_prompt += f"""
[FILTERED STATE] (Reflecting dashboard filters: {filters if filters else 'None'})
- Total Spend: ₹{total_spend/1e7:.2f} Cr (INR)
- Total Open PO Value: ₹{total_open/1e7:.2f} Cr (INR)
- Procurement Efficiency: {efficiency:.2f}%
- Total Unique Purchase Orders (POs): {pos}
- Total Active Suppliers: {suppliers}
- Total Unique Materials (SKUs): {materials}

Top 5 Suppliers by Spend:
{top_sups_str}

Top 5 Plants by Spend:
{top_plants_str}

Top 5 Materials by Spend:
{top_mats_str}
"""
        except Exception as e:
            traceback.print_exc()
            system_prompt += f"\n(Error compiling data context: {str(e)})\n"
    else:
        system_prompt += (
            "\n[NO DATA DATASET LOADED]\n"
            "No CSV files have been uploaded and merged yet. Please inform the user that they "
            "need to upload the Transaction CSV (Sheet 1) and Master CSV (Sheet 2) and click 'Merge Data' "
            "before you can analyze specific data for them.\n"
        )

    system_prompt += """
Guidelines:
1. Answer the user's questions about the procurement data based on the provided stats.
2. If the user asks about a specific detail or chart, guide them to locate it on the dashboard (e.g. 'You can see the Monthly Spend Evolution chart for the trend over time' or 'The Pareto chart shows supplier concentration').
3. Keep answers concise, actionable, and formatted in clean markdown. Use ₹ for Rupees and state values in Crores (Cr) or Lakhs (L) where appropriate.
4. If you don't know the answer or the data isn't in the context, tell the user that but offer to help with general procurement interpretation or advice.
"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({
            "role": msg.get("role"),
            "content": msg.get("content")
        })
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": "qwen3:8b",
        "messages": messages,
        "stream": False
    }

    try:
        import json
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            reply = res_data.get("message", {}).get("content", "")
            return jsonify({"reply": reply})
    except urllib.error.URLError as e:
        print(f"Ollama connection error: {e}")
        return jsonify({
            "reply": "I couldn't connect to your local Ollama server. Please verify that Ollama is running and has the `qwen3:8b` model pulled (`ollama run qwen3:8b`)."
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": f"An error occurred while calling the local model: {str(e)}"}), 500

# ─── GR/IR Reconciliation Endpoints (Service Layer) ──────────────────────────


@app.route("/api/grir/summary", methods=["GET"])
@app.route("/grir/summary", methods=["GET"])
def grir_summary():
    """Return full GR/IR dashboard payload (excluding all_items for performance)."""
    if not grir_service.has_data():
        return jsonify({"success": False, "error": "GR/IR Analysis data not found. Please upload GRIR, EKKO, and ME2N files."}), 404
    dashboard = grir_service.get_dashboard()
    if not dashboard:
        return jsonify({"success": False, "error": "GR/IR Analysis data not found. Please upload SAP files and run the reconciliation engine."}), 404
    return jsonify(dashboard)


@app.route("/api/grir/dashboard", methods=["GET"])
@app.route("/grir/dashboard", methods=["GET"])
def grir_dashboard():
    """Return the full GR/IR dashboard analytics payload."""
    if not grir_service.has_data():
        return jsonify({"success": False, "error": "GR/IR Analysis data not found. Please upload GRIR, EKKO, and ME2N files."}), 404
    dashboard = grir_service.get_dashboard()
    if not dashboard:
        return jsonify({"success": False, "error": "GR/IR Analysis data not found."}), 404
    return jsonify(dashboard)


@app.route("/api/grir/items", methods=["GET"])
@app.route("/grir/items", methods=["GET"])
def grir_items():
    """Return paginated, filtered, sorted GR/IR items."""
    if not grir_service.has_data():
        return jsonify({"success": False, "error": "GR/IR Analysis data not found.", "items": [], "total": 0, "page": 1, "pages": 1, "limit": 50}), 200
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    risk_level = request.args.get("risk_level", "").strip()
    plant = request.args.get("plant", "").strip()
    sort_by = request.args.get("sortBy", "risk_score").strip()
    sort_order = request.args.get("sortOrder", "desc").strip()
    result = grir_service.get_items(page, limit, search, status, risk_level, plant, sort_by, sort_order)
    return jsonify(result)



# ─── GR/IR Upload, Metadata, AI Insights, and Export Endpoints ───────────────


@app.route("/grir/upload", methods=["POST"])
@app.route("/api/grir/upload", methods=["POST"])
def grir_upload():
    """Upload a GRIR, EKKO, or ME2N CSV/XLSX file for analysis."""
    print("[Flask] Received upload request for GR/IR!")
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in request"}), 400
    file = request.files["file"]
    print(f"[Flask] File received: {file.filename}")
    if not file or not (file.filename.lower().endswith(".csv") or file.filename.lower().endswith(".xlsx") or file.filename.lower().endswith(".xls")):
        return jsonify({"success": False, "error": "Only CSV, XLS, and XLSX formats are supported."}), 400
    try:
        # Save to disk as grir.csv or grir.xlsx to prevent stream hangs
        file_path = os.path.join(os.path.dirname(__file__), file.filename)
        try:
            file_bytes = file.read()
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            print(f"[Flask] Saved {file.filename} to disk successfully.")
        except PermissionError:
            print(f"[Flask] Permission denied writing to {file_path}. It might be open in another program.")
        except Exception as e:
            print(f"[Flask] Failed to write to {file_path}: {e}")
        finally:
            file.seek(0)
            
        print("[Flask] Reading file with pandas...")
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file_path, encoding="utf-8", low_memory=False)
        else:
            df = pd.read_excel(file_path)
            
        print(f"[Flask] Parsed dataframe with {len(df)} rows. Passing to grir_service.upload_df()...")
        result = grir_service.upload_df(df, file.filename)
        print("[Flask] grir_service.upload_df() completed successfully.")
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"File parsing and reconciliation failed: {str(e)}"}), 500


@app.route("/api/grir/upload/metadata", methods=["GET"])
def grir_upload_metadata():
    """Return metadata about the currently loaded dataset."""
    return jsonify(grir_service.get_metadata())


@app.route("/api/grir/ai-insights", methods=["GET"])
def grir_ai_insights():
    """Return deterministic rule-based insights for GR/IR analysis."""
    if not grir_service.has_data():
        return jsonify({"success": False, "error": "GR/IR Analysis output not found. Please run the analysis first."}), 404
    insights = grir_service.get_ai_insights()
    if not insights:
        return jsonify({"success": False, "error": "No insights available."}), 404
    return jsonify(insights)





@app.route("/api/grir/export/pdf", methods=["GET"])
def grir_export_pdf():
    """Generate and download a multi-page PDF audit report."""
    if not grir_service.has_data():
        return jsonify({"success": False, "error": "GR/IR Analysis data not found."}), 404
    try:
        pdf_buffer = grir_service.generate_pdf()
        if not pdf_buffer:
            return jsonify({"success": False, "error": "Failed to generate PDF."}), 500
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"grir_audit_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to generate PDF: {str(e)}"}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# ─── PRODUCTION-GRADE GRIR ANALYTICS ENDPOINTS ─────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════
# These endpoints implement the complete GRIR reconciliation workflow with INR
# normalization, reconciliation engine, and comprehensive KPI calculations.
# Isolated from existing functionality to prevent breaking changes.


@app.route("/api/grir/upload-files", methods=["POST"])
def grir_upload_files():
    """Upload GRIR, ME2N, and/or EKKO files for analysis."""
    print("[GRIR] Upload request received")
    
    try:
        files = request.files
        file_mapping = {}
        
        # Parse uploaded files and detect types
        for file_key in files:
            file = files[file_key]
            if not file or file.filename == '':
                continue
            
            try:
                print(f"[GRIR] Processing file: {file.filename}")
                
                if file.filename.lower().endswith('.csv'):
                    df = pd.read_csv(file, encoding='utf-8', low_memory=False)
                elif file.filename.lower().endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file)
                else:
                    return jsonify({"success": False, "error": f"Unsupported format for {file.filename}"}), 400
                
                # Detect file type by schema
                file_type = _detect_grir_file_type(df)
                if not file_type:
                    return jsonify({"success": False, "error": f"Could not detect file type for {file.filename}. Ensure it has proper GRIR/ME2N/EKKO columns."}), 400
                
                print(f"[GRIR] Detected file type: {file_type}")
                file_mapping[file_type] = df
                
            except Exception as e:
                return jsonify({"success": False, "error": f"Failed to parse {file.filename}: {str(e)}"}), 400
        
        if not file_mapping:
            return jsonify({"success": False, "error": "No files uploaded"}), 400
        
        # Store DataFrames
        grir_state['grir_df'] = file_mapping.get('GRIR')
        grir_state['me2n_df'] = file_mapping.get('ME2N')
        grir_state['ekko_df'] = file_mapping.get('EKKO')
        
        print(f"[GRIR] Stored files: GRIR={grir_state['grir_df'] is not None and not grir_state['grir_df'].empty}, ME2N={grir_state['me2n_df'] is not None and not grir_state['me2n_df'].empty}, EKKO={grir_state['ekko_df'] is not None and not grir_state['ekko_df'].empty}")
        
        # Validate minimum requirements
        if grir_state['grir_df'] is None or grir_state['me2n_df'] is None:
            return jsonify({
                "success": False,
                "error": "GRIR and ME2N files are required for analysis"
            }), 400
        
        # Run reconciliation
        print("[GRIR] Running reconciliation...")
        try:
            grir_state['reconciled_df'] = aggregate_by_po_item(
                grir_state['grir_df'],
                grir_state['me2n_df'],
                grir_state['ekko_df'],
                analysis_date=pd.Timestamp(datetime.now())
            )
            
            # Build analytics
            print("[GRIR] Building KPIs...")
            grir_state['kpis'] = build_executive_kpis(grir_state['reconciled_df'])
            grir_state['aging_analysis'] = build_aging_analysis(grir_state['reconciled_df'])
            grir_state['top_insights'] = build_top_management_insights(grir_state['reconciled_df'])
            grir_state['chart_data'] = build_chart_data(grir_state['reconciled_df'])
            grir_state['analysis_timestamp'] = datetime.now().isoformat()
            
            print("[GRIR] Analysis complete!")
            
            return jsonify({
                "success": True,
                "message": "Files uploaded and analysis completed successfully",
                "files_processed": list(file_mapping.keys()),
                "po_lines_analyzed": len(grir_state['reconciled_df']),
                "reconciliation_rate_pct": round(grir_state['kpis']['reconciliation_rate_pct'], 1),
                "total_open_exposure_inr": round(grir_state['kpis']['total_open_exposure_inr'], 2)
            })
            
        except Exception as e:
            traceback.print_exc()
            print(f"[GRIR] Reconciliation error: {e}")
            return jsonify({
                "success": False,
                "error": f"Reconciliation failed: {str(e)}"
            }), 500
            
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def _detect_grir_file_type(df):
    """Detect SAP file type by columns."""
    cols_lower = [str(c).strip().lower() for c in df.columns]
    
    # Check for GRIR-specific columns
    grir_indicators = ['trans type', 'trans_type', 'dr/cr ind', 'dr_cr_ind', 'amt (lc)', 'amt_lc']
    if any(indicator in cols_lower for indicator in grir_indicators):
        return 'GRIR'
    
    # Check for EKKO-specific columns
    ekko_indicators = ['exchange rate', 'exchange_rate', 'company code', 'company_code']
    if any(indicator in cols_lower for indicator in ekko_indicators):
        if 'purchasing document' in cols_lower or 'purchasing_document' in cols_lower:
            return 'EKKO'
    
    # Check for ME2N-specific columns
    me2n_indicators = ['net order value', 'net_order_value', 'still to be delivered', 'still_to_be_delivered']
    if any(indicator in cols_lower for indicator in me2n_indicators):
        return 'ME2N'
    
    # Fallback: check purchasing document presence
    if 'purchasing document' in cols_lower or 'purchasing_document' in cols_lower:
        if 'company code' in cols_lower or 'company_code' in cols_lower:
            return 'EKKO'
        return 'ME2N'
    
    return None


@app.route("/api/grir/kpis", methods=["GET"])
def grir_get_kpis():
    """Get all executive KPIs."""
    if grir_state['reconciled_df'] is None:
        return jsonify({
            "success": False,
            "error": "No data analyzed. Please upload files first."
        }), 400
    
    return jsonify({
        "success": True,
        "kpis": grir_state['kpis'],
        "analysis_timestamp": grir_state['analysis_timestamp']
    })


@app.route("/api/grir/aging", methods=["GET"])
def grir_get_aging():
    """Get aging bucket analysis."""
    if grir_state['reconciled_df'] is None:
        return jsonify({
            "success": False,
            "error": "No data analyzed. Please upload files first."
        }), 400
    
    return jsonify({
        "success": True,
        "aging_analysis": grir_state['aging_analysis']
    })


@app.route("/api/grir/insights", methods=["GET"])
def grir_get_insights():
    """Get top management insights."""
    if grir_state['reconciled_df'] is None:
        return jsonify({
            "success": False,
            "error": "No data analyzed. Please upload files first."
        }), 400
    
    return jsonify({
        "success": True,
        "insights": grir_state['top_insights']
    })


@app.route("/api/grir/charts", methods=["GET"])
def grir_get_charts():
    """Get chart data for all visualizations."""
    if grir_state['reconciled_df'] is None:
        return jsonify({
            "success": False,
            "error": "No data analyzed. Please upload files first."
        }), 400
    
    return jsonify({
        "success": True,
        "charts": grir_state['chart_data']
    })


@app.route("/api/grir/reconciled-items", methods=["GET"])
def grir_get_reconciled_items():
    """Get paginated reconciled items with filters."""
    if grir_state['reconciled_df'] is None:
        return jsonify({
            "success": False,
            "error": "No data analyzed. Please upload files first.",
            "items": [],
            "total": 0
        }), 400
    
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 50))
        search = request.args.get("search", "").strip()
        status_filter = request.args.get("status", "").strip()
        
        df = grir_state['reconciled_df'].copy()
        
        # Apply filters
        if status_filter:
            df = df[df['Status'] == status_filter]
        
        if search:
            search_lower = search.lower()
            df = df[
                df['PO Number'].astype(str).str.lower().str.contains(search_lower, na=False) |
                df['Vendor'].astype(str).str.lower().str.contains(search_lower, na=False) |
                df['Material'].astype(str).str.lower().str.contains(search_lower, na=False)
            ]
        
        total = len(df)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        items = df.iloc[start_idx:end_idx][[
            'PO Number', 'PO Item', 'Vendor', 'Material', 'Status',
            'Net_GR_Qty', 'Net_IR_Qty', 'Open_Qty',
            'Net_GR_Val_INR', 'Net_IR_Val_INR', 'Open_Exposure_INR',
            'Days_Open', 'Aging_Bucket'
        ]].copy()
        
        items_json = records_to_json(items)
        
        return jsonify({
            "success": True,
            "items": items_json,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/grir/dashboard", methods=["GET"])
def grir_get_dashboard():
    """Get complete dashboard data (KPIs + Charts + Insights)."""
    if grir_state['reconciled_df'] is None:
        return jsonify({
            "success": False,
            "error": "No data analyzed. Please upload files first."
        }), 400
    
    return jsonify({
        "success": True,
        "kpis": grir_state['kpis'],
        "aging": grir_state['aging_analysis'],
        "insights": grir_state['top_insights'],
        "charts": grir_state['chart_data'],
        "analysis_timestamp": grir_state['analysis_timestamp']
    })


@app.route("/api/grir/export/json", methods=["GET"])
def grir_export_json():
    """Export complete analysis as JSON."""
    if grir_state['reconciled_df'] is None:
        return jsonify({
            "success": False,
            "error": "No data analyzed. Please upload files first."
        }), 400
    
    export_data = {
        "metadata": {
            "analysis_timestamp": grir_state['analysis_timestamp'],
            "po_lines_analyzed": len(grir_state['reconciled_df']),
        },
        "kpis": grir_state['kpis'],
        "aging_analysis": grir_state['aging_analysis'],
        "insights": grir_state['top_insights'],
        "chart_data": grir_state['chart_data'],
        "items": records_to_json(grir_state['reconciled_df'])
    }
    
    return jsonify({
        "success": True,
        "data": export_data
    })


@app.route("/api/grir/export/excel", methods=["GET"])
def grir_export_excel():
    """Export analysis as Excel report."""
    if grir_state['reconciled_df'] is None:
        return jsonify({
            "success": False,
            "error": "No data analyzed. Please upload files first."
        }), 400
    
    try:
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet 1: KPIs Summary
            kpis_flat = []
            for key, value in grir_state['kpis'].items():
                kpis_flat.append({'Metric': key, 'Value': value})
            pd.DataFrame(kpis_flat).to_excel(writer, sheet_name='KPIs', index=False)
            
            # Sheet 2: Aging Analysis
            pd.DataFrame(grir_state['aging_analysis']).to_excel(writer, sheet_name='Aging', index=False)
            
            # Sheet 3: Top Insights - Vendors
            if grir_state['top_insights'].get('top_vendors_by_exposure'):
                pd.DataFrame(grir_state['top_insights']['top_vendors_by_exposure']).to_excel(
                    writer, sheet_name='Top Vendors', index=False
                )
            
            # Sheet 4: Top Insights - Plants
            if grir_state['top_insights'].get('top_plants_by_exposure'):
                pd.DataFrame(grir_state['top_insights']['top_plants_by_exposure']).to_excel(
                    writer, sheet_name='Top Plants', index=False
                )
            
            # Sheet 5: Largest Unreconciled
            if grir_state['top_insights'].get('largest_unreconciled_po_lines'):
                pd.DataFrame(grir_state['top_insights']['largest_unreconciled_po_lines']).to_excel(
                    writer, sheet_name='Largest Unreconciled', index=False
                )
            
            # Sheet 6: All Items
            grir_state['reconciled_df'].to_excel(writer, sheet_name='All Items', index=False)
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue()),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"grir_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        )
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Failed to generate Excel: {str(e)}"
        }), 500


# ─── Server Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import threading
    import webbrowser

    # Remove automatic disk loading to ensure clean state
    # grir_service.load_from_disk()

    # Open browser automatically
    def open_browser():
        webbrowser.open_new('http://127.0.0.1:5000')

    print("Syrma Procurement Analytics -- Backend starting on http://localhost:5000")
    debug_mode = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug_mode, port=5000, host="0.0.0.0")


