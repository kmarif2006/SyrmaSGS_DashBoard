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
from datetime import datetime

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"])

# ─── Global In-Memory Store ──────────────────────────────────────────────────
store = {
    "transaction_df": None,
    "master_df": None,
    "merged_df": None,
    "transaction_filename": None,
    "master_filename": None,
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

# ─── GR/IR Reconciliation Endpoints ──────────────────────────────────────────

import os
import json

GRIR_DATA_CACHE = None

def get_grir_data():
    global GRIR_DATA_CACHE
    if GRIR_DATA_CACHE is None:
        file_path = r"c:\SyrmaSGS_DashBoard\grir_analysis_output.json"
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                GRIR_DATA_CACHE = json.load(f)
        except Exception as e:
            print(f"Error loading GRIR analysis file: {e}")
            return None
    return GRIR_DATA_CACHE


@app.route("/api/grir/summary", methods=["GET"])
def grir_summary():
    data = get_grir_data()
    if not data:
        return jsonify({"error": "GR/IR Analysis output not found. Please run the analysis first."}), 404
    
    # Exclude 'all_items' to avoid large payload sizes
    summary_data = {k: v for k, v in data.items() if k != "all_items"}
    return jsonify(summary_data)


@app.route("/api/grir/items", methods=["GET"])
def grir_items():
    data = get_grir_data()
    if not data:
        return jsonify({"error": "GR/IR Analysis output not found. Please run the analysis first."}), 404
    
    all_items = data.get("all_items", [])
    
    # Fetch parameters
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    search = request.args.get("search", "").strip().lower()
    status = request.args.get("status", "").strip()
    risk_level = request.args.get("risk_level", "").strip()
    plant = request.args.get("plant", "").strip()
    sort_by = request.args.get("sortBy", "risk_score").strip()
    sort_order = request.args.get("sortOrder", "desc").strip()
    
    # Apply filtering
    filtered_items = all_items
    
    if search:
        filtered_items = [
            item for item in filtered_items
            if search in str(item.get("PO Number", "")).lower() or
               search in str(item.get("Vendor", "")).lower() or
               search in str(item.get("Short Text", "")).lower()
        ]
        
    if status:
        filtered_items = [item for item in filtered_items if item.get("status") == status]
        
    if risk_level:
        filtered_items = [item for item in filtered_items if item.get("risk_level") == risk_level]
        
    if plant:
        filtered_items = [item for item in filtered_items if str(item.get("Plant", "")) == plant]
        
    # Apply sorting
    if sort_by:
        reverse = (sort_order == "desc")
        
        def get_sort_key(item):
            val = item.get(sort_by)
            if val is None:
                # Fallbacks for types
                return "" if isinstance(val, str) else 0
            # Numeric fields
            if sort_by in ["net_gr_qty", "net_gr_val", "net_ir_qty", "net_ir_val", "open_qty", "open_val", "risk_score", "days_open", "inv_completion_pct", "reversal_pct", "price_var_pct", "price_var_abs"]:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return 0.0
            return str(val).lower()
            
        try:
            filtered_items = sorted(filtered_items, key=get_sort_key, reverse=reverse)
        except Exception as e:
            print(f"Sorting error: {e}")
            
    # Apply pagination
    total = len(filtered_items)
    start = (page - 1) * limit
    end = start + limit
    paginated_items = filtered_items[start:end]
    
    pages = math.ceil(total / limit) if limit > 0 else 1
    
    return jsonify({
        "items": paginated_items,
        "total": total,
        "page": page,
        "pages": pages,
        "limit": limit
    })



# ─── SAP Column Detection & Mapping ──────────────────────────────────────────

SAP_COLUMN_MAP = {
    # PO Number
    'po number': 'PO Number',
    'po_number': 'PO Number',
    'po no': 'PO Number',
    'po_no': 'PO Number',
    'purchase order': 'PO Number',
    'purchase_order': 'PO Number',
    'ebeln': 'PO Number',
    
    # PO Item
    'po item': 'PO Item',
    'po_item': 'PO Item',
    'item': 'PO Item',
    'po_item_no': 'PO Item',
    'ebelp': 'PO Item',
    
    # Material Number
    'material number': 'Material Number',
    'material_number': 'Material Number',
    'material_no': 'Material Number',
    'material no': 'Material Number',
    'matnr': 'Material Number',
    
    # Material Description
    'material description': 'Material Description',
    'material_description': 'Material Description',
    'material text': 'Material Description',
    'short text': 'Material Description',
    'txz01': 'Material Description',
    
    # Vendor
    'vendor': 'Vendor',
    'supplier': 'Vendor',
    'supplier name': 'Vendor',
    'name of supplier': 'Vendor',
    'lifnr': 'Vendor',
    
    # Plant
    'plant': 'Plant',
    'werks': 'Plant',
    
    # Company Code
    'company code': 'Company Code',
    'company_code': 'Company Code',
    'bukrs': 'Company Code',
    
    # Currency
    'currency': 'Waers',
    'waers': 'Waers',
    
    # Posting Date
    'posting date': 'Posting Date',
    'posting_date': 'Posting Date',
    'budat': 'Posting Date',
    
    # Document Date
    'document date': 'Document Date',
    'document_date': 'Document Date',
    'bldat': 'Document Date',
    
    # Quantity
    'quantity': 'Quantity',
    'qty': 'Quantity',
    'menge': 'Quantity',
    
    # Amount
    'amount': 'Amt (LC)',
    'amt': 'Amt (LC)',
    'amount in lc': 'Amt (LC)',
    'amt (lc)': 'Amt (LC)',
    'amt_lc': 'Amt (LC)',
    'wrbtr': 'Amt (LC)',
    'dmbtr': 'Amt (LC)',
    
    # Unit Price
    'unit price': 'Unit Price',
    'unit_price': 'Unit Price',
    'price': 'Unit Price',
    'netpr': 'Unit Price',
    
    # Transaction Type
    'transaction type': 'Trans Type',
    'transaction_type': 'Trans Type',
    'trans type': 'Trans Type',
    'trans_type': 'Trans Type',
    'vgabe': 'Trans Type',
    
    # Debit/Credit Indicator
    'debit/credit indicator': 'Dr/Cr Ind',
    'debit_credit_indicator': 'Dr/Cr Ind',
    'dr/cr ind': 'Dr/Cr Ind',
    'dr_cr_ind': 'Dr/Cr Ind',
    'shkzg': 'Dr/Cr Ind',
    
    # Movement Type
    'movement type': 'Movement Type',
    'movement_type': 'Movement Type',
    'mvt type': 'Movement Type',
    'bwart': 'Movement Type',
    
    # Document Number
    'document number': 'Document No',
    'document_number': 'Document No',
    'doc no': 'Document No',
    'doc_no': 'Document No',
    'belnr': 'Document No',
    
    # Doc Type
    'doc type': 'Doc Type',
    'doc_type': 'Doc Type',
    'blart': 'Doc Type',
    
    # Doc Item
    'doc item': 'Doc Item',
    'doc_item': 'Doc Item',
    'buzei': 'Doc Item',
    
    # Reference Doc
    'reference doc': 'Reference Doc',
    'reference_doc': 'Reference Doc',
    'xblnr': 'Reference Doc',
}


# ─── GR/IR Upload and Dynamic Analysis APIs ──────────────────────────────────

@app.route("/api/grir/upload", methods=["POST"])
def grir_upload():
    global GRIR_DATA_CACHE
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400
    file = request.files["file"]
    if not file or not (file.filename.lower().endswith(".csv") or file.filename.lower().endswith(".xlsx") or file.filename.lower().endswith(".xls")):
        return jsonify({"error": "Only CSV, XLS, and XLSX formats are supported."}), 400
    
    try:
        filename = file.filename
        print(f"Parsing uploaded file: {filename}")
        
        # Read file into DataFrame
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(file, low_memory=False)
        else:
            df = pd.read_excel(file)
            
        if df.empty:
            return jsonify({"error": "The uploaded file is empty."}), 400
            
        # Map columns intelligently
        col_mapping = {}
        for col in df.columns:
            cleaned_col = str(col).strip().lower()
            if cleaned_col in SAP_COLUMN_MAP:
                col_mapping[col] = SAP_COLUMN_MAP[cleaned_col]
        
        df = df.rename(columns=col_mapping)
        
        # Verify required columns exist
        required_cols = [
            'PO Number', 'PO Item', 'Trans Type', 'Dr/Cr Ind', 
            'Quantity', 'Amt (LC)', 'Posting Date', 'Document Date', 'Plant'
        ]
        
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            return jsonify({
                "error": f"Unable to map required columns: {missing_cols}. Please verify your file contains these columns or their equivalents.",
                "available_columns": list(df.columns)
            }), 400
            
        # Clean data types
        df['PO Number'] = df['PO Number'].astype(str).str.strip()
        df['PO Item'] = pd.to_numeric(df['PO Item'], errors='coerce').fillna(0).astype(int).astype(str)
        df['Trans Type'] = df['Trans Type'].astype(str).str.strip()
        df['Dr/Cr Ind'] = df['Dr/Cr Ind'].astype(str).str.strip()
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
        df['Amt (LC)'] = pd.to_numeric(df['Amt (LC)'], errors='coerce').fillna(0)
        df['Posting Date'] = pd.to_datetime(df['Posting Date'], errors='coerce')
        df['Document Date'] = pd.to_datetime(df['Document Date'], errors='coerce')
        df['Plant'] = df['Plant'].astype(str).str.strip()
        
        # Add default optional columns if not present
        if 'Doc Type' not in df.columns: df['Doc Type'] = ''
        if 'Document No' not in df.columns: df['Document No'] = ''
        if 'Doc Item' not in df.columns: df['Doc Item'] = ''
        if 'Reference Doc' not in df.columns: df['Reference Doc'] = ''
        if 'Amt (FC)' not in df.columns: df['Amt (FC)'] = df['Amt (LC)']
        
        # Save as the primary data source replacing grir.csv
        target_path = r"c:\SyrmaSGS_DashBoard\grir.csv"
        df.to_csv(target_path, index=False, date_format='%Y-%m-%d %H:%M:%S')
        
        # Run standard reconciliation subprocess to update outputs
        print("Executing SAP GR/IR Reconciliation engine subprocess...")
        import subprocess
        result = subprocess.run(
            ["python", "grir_analysis.py"],
            cwd=r"c:\SyrmaSGS_DashBoard",
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Reconciliation engine failure: {result.stderr}")
            return jsonify({"error": f"SAP Reconciliation process failed: {result.stderr}"}), 500
            
        print("Analysis completed successfully. Clearing cache...")
        GRIR_DATA_CACHE = None
        
        # Clear AI insights cache to force regeneration
        ai_cache_path = r"c:\SyrmaSGS_DashBoard\grir_ai_insights.json"
        if os.path.exists(ai_cache_path):
            try:
                os.remove(ai_cache_path)
            except Exception:
                pass
                
        # Load the updated reconciled JSON outputs
        data = get_grir_data()
        if not data:
            return jsonify({"error": "Failed to load reconciled data after analysis."}), 500
            
        kpis = data.get("kpis", {})
        metadata = {
            "file_name": filename,
            "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "num_records": len(df),
            "num_pos": kpis.get("unique_pos", df['PO Number'].nunique()),
            "num_vendors": kpis.get("unique_vendors", 0),
            "num_materials": kpis.get("total_materials", 0)
        }
        
        # Cache metadata to disk
        meta_path = r"c:\SyrmaSGS_DashBoard\grir_upload_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
            
        return jsonify({
            "message": "File processed and SAP GR/IR reconciliation completed successfully.",
            "metadata": metadata
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"File parsing and reconciliation failed: {str(e)}"}), 500


@app.route("/api/grir/upload/metadata", methods=["GET"])
def grir_upload_metadata():
    meta_path = r"c:\SyrmaSGS_DashBoard\grir_upload_metadata.json"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception:
            pass
            
    # Default metadata fallback
    data = get_grir_data()
    if data:
        kpis = data.get("kpis", {})
        metadata = {
            "file_name": "grir.csv (Pre-loaded System Default)",
            "upload_date": "N/A",
            "num_records": data.get("metadata", {}).get("grir_row_count", 87964),
            "num_pos": kpis.get("unique_pos", 0),
            "num_vendors": kpis.get("unique_vendors", 0),
            "num_materials": kpis.get("total_materials", 0)
        }
        return jsonify(metadata)
        
    return jsonify({
        "file_name": "None",
        "upload_date": "N/A",
        "num_records": 0,
        "num_pos": 0,
        "num_vendors": 0,
        "num_materials": 0
    })


# ─── Gemini AI Reconciliation Analytics ──────────────────────────────────────

def generate_rule_based_insights(data):
    kpis = data.get("kpis", {})
    open_val = kpis.get("total_open_value", 0)
    open_cr = abs(open_val) / 1e7
    recon_rate = kpis.get("reconciliation_rate", 0)
    crit_count = kpis.get("critical_items", 0)
    vendor_count = kpis.get("unique_vendors", 0)
    
    vendors = data.get("vendor_insights", [])
    top_vendor_name = vendors[0]["vendor"] if vendors else "N/A"
    top_vendor_open = vendors[0]["open_value"] if vendors else 0
    top_vendor_pct = vendors[0]["open_pct_total"] if vendors else 0

    materials = data.get("material_insights", [])
    top_mat_name = materials[0]["material"] if materials else "N/A"
    top_mat_open = materials[0]["open_value"] if materials else 0

    return {
        "headline": f"INR {open_cr:.2f} Cr in Open GR/IR Reconciliation Balances Signals Accrual and Compliance Risks",
        "executive_summary": (
            f"The SAP reconciliation audit reveals that out of {kpis.get('total_po_items', 0):,} PO items, "
            f"only {recon_rate:.1f}% are fully reconciled. The net open exposure stands at INR {open_val:,.2f} "
            f"({open_cr:.2f} Cr). This exposure represents a combination of pending supplier invoices "
            f"(liability understatements) and invoices received without goods receipts (payment risk)."
        ),
        "critical_risks": [
            f"{crit_count} PO items are flagged as Critical severity due to extensive aging or over-invoicing.",
            "Invoices received without corresponding Goods Receipts (IR without GR) represent major internal control violations.",
            "Over-invoiced items carrying duplicates present a leakage risk for Accounts Payable payments."
        ],
        "vendor_findings": [
            f"Supplier '{top_vendor_name}' contributes the largest share of open exposure, accounting for "
            f"INR {top_vendor_open:,.2f} ({top_vendor_pct}% of total exposure).",
            f"Reconciliation balances are spread across {vendor_count} unique vendors, suggesting systemic procurement delays."
        ],
        "material_findings": [
            f"Material group or item '{top_mat_name}' shows an open balance of INR {top_mat_open:,.2f}, indicating "
            "delivery verification bottlenecks or vendor billing delays."
        ],
        "plant_findings": [
            "Certain plant locations demonstrate higher exception rates, necessitating localized process adjustments."
        ],
        "financial_impact": [
            f"Month-end accruals of INR {kpis.get('pending_invoice_val', 0):,.2f} are required to prevent understating Accounts Payable.",
            f"Over-invoiced amount of INR {kpis.get('over_invoice_val', 0):,.2f} could result in cash outflow leakages if paid."
        ],
        "recommended_actions": [
            "Audit all 'IR ONLY' exceptions and activate payment blocks until Goods Receipts are posted (Immediate).",
            f"Contact vendor '{top_vendor_name}' to resolve pending invoices and aging reconciliation items (Procurement; 5 Days).",
            "Clear all open balances outstanding for more than 180 days (Finance Team; Before Month-End)."
        ]
    }


@app.route("/api/grir/ai-insights", methods=["GET"])
def grir_ai_insights():
    data = get_grir_data()
    if not data:
        return jsonify({"error": "GR/IR Analysis output not found. Please run the analysis first."}), 404
        
    cache_path = r"c:\SyrmaSGS_DashBoard\grir_ai_insights.json"
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception:
            pass

    # Summarize metrics for AI payload (Never send raw 100k records)
    kpis = data.get("kpis", {})
    vendors = data.get("vendor_insights", [])[:5]
    materials = data.get("material_insights", [])[:5]
    exceptions = data.get("top_exceptions", [])[:5]
    aging = data.get("aging_analysis", [])
    reversals = data.get("reversal_analysis", [])[:5]

    prompt = f"""
You are an expert SAP MM Consultant, SAP FI Consultant, Auditor, and Procurement Controller.
Analyze the following summarized SAP GR/IR reconciliation results for Syrma SGS and generate management-grade insights.

KPI Summary:
- Total PO Items: {kpis.get('total_po_items')}
- Reconciled Items: {kpis.get('reconciled_count')}
- Reconciliation Rate: {kpis.get('reconciliation_rate')}%
- Total Open Exposure Value: INR {kpis.get('total_open_value'):,}
- Pending Supplier Invoice Value: INR {kpis.get('pending_invoice_val'):,}
- Over-Invoiced Value: INR {kpis.get('over_invoice_val'):,}
- Critical Risk Items: {kpis.get('critical_items')}
- Unique Vendors with Open Balances: {kpis.get('unique_vendors')}

Top 5 Exposed Vendors:
{json.dumps(vendors, indent=2)}

Top 5 Exposed Materials:
{json.dumps(materials, indent=2)}

Top 5 Critical Exceptions:
{json.dumps(exceptions, indent=2)}

Aging Analysis (Open Value per Bucket):
{json.dumps(aging, indent=2)}

Top 5 Reversals:
{json.dumps(reversals, indent=2)}

Generate a response in JSON format (do not wrap it in markdown code blocks) containing the following fields:
{{
  "headline": "A short bold executive summary headline",
  "executive_summary": "A high-level paragraph summarizing the reconciliation status, total exposure, and primary drivers.",
  "critical_risks": [
    "List of critical risk items (e.g. over-invoicing, control violations like IR without GR, aging exposure)"
  ],
  "vendor_findings": [
    "Specific findings regarding underperforming or highly exposed vendors"
  ],
  "material_findings": [
    "Specific material or category exposure findings"
  ],
  "plant_findings": [
    "Plant-level findings if any plant contributes disproportionately to the exposure"
  ],
  "financial_impact": [
    "Impact on Accounts Payable, working capital, P&L, accruals, and month-end closing risks"
  ],
  "recommended_actions": [
    "Specific actions with clear priority, owners (e.g. Accounts Payable, Procurement), and timelines"
  ]
}}
"""

    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    api_key = os.environ.get("GEMINI_API_KEY")
    insights = None

    if api_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                res_data = json.loads(r.read().decode("utf-8"))
                text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    if lines[0].startswith("```json"):
                        text = "\n".join(lines[1:-1])
                    else:
                        text = "\n".join(lines[1:-1])
                insights = json.loads(text)
        except Exception as e:
            print(f"Gemini API request failed: {e}")

    # Fallback to local Ollama
    if not insights:
        ollama_payload = {
            "model": "qwen3:8b",
            "messages": [
                {"role": "system", "content": "You are a senior SAP Auditor. Provide the requested JSON object."},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "format": "json"
        }
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=json.dumps(ollama_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                res_data = json.loads(r.read().decode("utf-8"))
                text = res_data.get("message", {}).get("content", "").strip()
                insights = json.loads(text)
        except Exception as e:
            print(f"Ollama call failed: {e}")

    # Fallback to rule-based insights if both models are unavailable
    if not insights:
        insights = generate_rule_based_insights(data)

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(insights, f, indent=2)
    except Exception as e:
        print(f"Error caching AI insights: {e}")

    return jsonify(insights)


# ─── Report Export endpoints ──────────────────────────────────────────────────

@app.route("/api/grir/export/json", methods=["GET"])
def grir_export_json():
    target_path = r"c:\SyrmaSGS_DashBoard\grir_analysis_output.json"
    if not os.path.exists(target_path):
        return jsonify({"error": "GR/IR Analysis data not found."}), 404
    return send_file(target_path, as_attachment=True, download_name="grir_reconciliation_report.json")


@app.route("/api/grir/export/excel", methods=["GET"])
def grir_export_excel():
    data = get_grir_data()
    if not data:
        return jsonify({"error": "GR/IR Analysis data not found."}), 404
        
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 1. KPIs
            kpis = data.get("kpis", {})
            kpis_df = pd.DataFrame(list(kpis.items()), columns=["Metric", "Value"])
            kpis_df.to_excel(writer, sheet_name="KPIs Summary", index=False)
            
            # 2. Exceptions
            exceptions = data.get("top_exceptions", [])
            if exceptions:
                exc_df = pd.DataFrame(exceptions)
                exc_df.to_excel(writer, sheet_name="Top Exceptions", index=False)
                
            # 3. Vendors
            vendors = data.get("vendor_insights", [])
            if vendors:
                vendors_df = pd.DataFrame(vendors)
                vendors_df.to_excel(writer, sheet_name="Vendor Performance", index=False)
                
            # 4. Materials
            materials = data.get("material_insights", [])
            if materials:
                materials_df = pd.DataFrame(materials)
                materials_df.to_excel(writer, sheet_name="Material Insights", index=False)
                
            # 5. Aging
            aging = data.get("aging_analysis", [])
            if aging:
                aging_df = pd.DataFrame(aging)
                aging_df.to_excel(writer, sheet_name="Aging Analysis", index=False)
                
            # 6. Price Variances
            price_var = data.get("price_variance_analysis", [])
            if price_var:
                pv_df = pd.DataFrame(price_var)
                pv_df.to_excel(writer, sheet_name="Price Variances", index=False)
                
            # 7. Reversals
            reversals = data.get("reversal_analysis", [])
            if reversals:
                rev_df = pd.DataFrame(reversals)
                rev_df.to_excel(writer, sheet_name="Reversals Log", index=False)
                
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue()),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="grir_reconciliation_report.xlsx"
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Failed to generate Excel sheet: {str(e)}"}), 500


@app.route("/api/grir/export/ai-report", methods=["GET"])
def grir_export_ai_report():
    data = get_grir_data()
    if not data:
        return jsonify({"error": "GR/IR Analysis data not found."}), 404
        
    try:
        ai_resp = grir_ai_insights()
        ai_data = ai_resp[0].get_json() if hasattr(ai_resp[0], 'get_json') else ai_resp.get_json()
        
        md_report = f"""# SAP GR/IR RECONCILIATION AI AUDIT REPORT
=====================================================
Generated on: {datetime.now().strftime('%d %B %Y at %H:%M')}
Organization: Syrma SGS Technology Limited
Reconciliation Rate: {data.get('kpis', {}).get('reconciliation_rate', 'N/A')}%
Total Open Exposure: INR {data.get('kpis', {}).get('total_open_value', 0):,}

Headline: {ai_data.get('headline', '')}

-----------------------------------------------------
1. EXECUTIVE SYNTHESIS
-----------------------------------------------------
{ai_data.get('executive_summary', '')}

-----------------------------------------------------
2. CRITICAL AUDIT RISKS
-----------------------------------------------------
"""
        for i, risk in enumerate(ai_data.get('critical_risks', []), 1):
            md_report += f"{i}. {risk}\n"
            
        md_report += "\n-----------------------------------------------------\n3. VENDOR FINDINGS\n-----------------------------------------------------\n"
        for i, find in enumerate(ai_data.get('vendor_findings', []), 1):
            md_report += f"{i}. {find}\n"
            
        md_report += "\n-----------------------------------------------------\n4. MATERIAL FINDINGS\n-----------------------------------------------------\n"
        for i, find in enumerate(ai_data.get('material_findings', []), 1):
            md_report += f"{i}. {find}\n"
            
        md_report += "\n-----------------------------------------------------\n5. PLANT FINDINGS\n-----------------------------------------------------\n"
        for i, find in enumerate(ai_data.get('plant_findings', []), 1):
            md_report += f"{i}. {find}\n"
            
        md_report += "\n-----------------------------------------------------\n6. FINANCIAL STATEMENT & WORKING CAPITAL IMPACT\n-----------------------------------------------------\n"
        for i, imp in enumerate(ai_data.get('financial_impact', []), 1):
            md_report += f"{i}. {imp}\n"
            
        md_report += "\n-----------------------------------------------------\n7. ACTION PRIORITIES CHECKLIST\n-----------------------------------------------------\n"
        for i, act in enumerate(ai_data.get('recommended_actions', []), 1):
            md_report += f"{i}. {act}\n"
            
        output = io.BytesIO(md_report.encode("utf-8"))
        return send_file(
            output,
            mimetype="text/markdown",
            as_attachment=True,
            download_name="grir_ai_audit_report.md"
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Failed to generate AI report: {str(e)}"}), 500


@app.route("/api/grir/export/pdf", methods=["GET"])
def grir_export_pdf():
    data = get_grir_data()
    if not data:
        return jsonify({"error": "GR/IR Analysis data not found."}), 404
        
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        ai_resp = grir_ai_insights()
        ai_data = ai_resp[0].get_json() if hasattr(ai_resp[0], 'get_json') else ai_resp.get_json()
        
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer, 
            pagesize=letter,
            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
        )
        story = []
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor('#4f46e5'),
            spaceAfter=15
        )
        
        h2_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#1e1b4b'),
            spaceBefore=12,
            spaceAfter=6
        )
        
        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#334155'),
            spaceAfter=8
        )
        
        bold_body_style = ParagraphStyle(
            'BoldBody',
            parent=body_style,
            fontName='Helvetica-Bold'
        )

        meta_style = ParagraphStyle(
            'Metadata',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=15
        )
        
        # 1. Document Title
        story.append(Paragraph("SAP GR/IR Reconciliation Audit Report", title_style))
        story.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y')} | Organization: Syrma SGS Technology Limited", meta_style))
        story.append(Spacer(1, 10))
        
        # 2. Executive Synthesis
        story.append(Paragraph("1. Executive Summary", h2_style))
        story.append(Paragraph(ai_data.get('headline', 'SAP GR/IR Accrual and Compliance Risks'), bold_body_style))
        story.append(Paragraph(ai_data.get('executive_summary', 'No executive summary available.'), body_style))
        story.append(Spacer(1, 10))
        
        # 3. KPIs Table
        story.append(Paragraph("2. Reconciliation Key Performance Indicators", h2_style))
        kpi_table_rows = [
            [Paragraph("<b>Metric</b>", body_style), Paragraph("<b>Value</b>", body_style)],
            [Paragraph("Total PO Line Items", body_style), Paragraph(f"{data.get('kpis', {}).get('total_po_items', 0):,}", body_style)],
            [Paragraph("Reconciliation Rate", body_style), Paragraph(f"{data.get('kpis', {}).get('reconciliation_rate', 0)}%", body_style)],
            [Paragraph("Total Open Exposure Value", body_style), Paragraph(f"INR {data.get('kpis', {}).get('total_open_value', 0):,}", body_style)],
            [Paragraph("Accruals Required (Pending Invoices)", body_style), Paragraph(f"INR {data.get('kpis', {}).get('pending_invoice_val', 0):,}", body_style)],
            [Paragraph("Over-Invoiced Risk Amount", body_style), Paragraph(f"INR {data.get('kpis', {}).get('over_invoice_val', 0):,}", body_style)],
            [Paragraph("Critical Risk Items Count", body_style), Paragraph(f"{data.get('kpis', {}).get('critical_items', 0)}", body_style)]
        ]
        t = Table(kpi_table_rows, colWidths=[250, 250])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8fafc')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9'))
        ]))
        story.append(t)
        story.append(Spacer(1, 15))
        
        story.append(PageBreak())
        
        # 4. Critical Audit Risks
        story.append(Paragraph("3. Critical Audit Risks", h2_style))
        for risk in ai_data.get('critical_risks', []):
            story.append(Paragraph(f"• {risk}", body_style))
        story.append(Spacer(1, 10))
            
        # 5. Vendor Findings
        story.append(Paragraph("4. Vendor Performance Findings", h2_style))
        for find in ai_data.get('vendor_findings', []):
            story.append(Paragraph(f"• {find}", body_style))
        story.append(Spacer(1, 10))
            
        # 6. Material Findings
        story.append(Paragraph("5. Material & Supply Chain Findings", h2_style))
        for find in ai_data.get('material_findings', []):
            story.append(Paragraph(f"• {find}", body_style))
        story.append(Spacer(1, 10))
            
        # 7. Recommended Actions
        story.append(Paragraph("6. Reconciliation Action Plan", h2_style))
        for act in ai_data.get('recommended_actions', []):
            story.append(Paragraph(f"• {act}", body_style))
            
        doc.build(story)
        pdf_buffer.seek(0)
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="grir_audit_report.pdf"
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500


# ─── Server Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Syrma Procurement Analytics -- Backend starting on http://localhost:5000")
    app.run(debug=True, port=5000, host="0.0.0.0")


