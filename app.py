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


if __name__ == "__main__":
    print("Syrma Procurement Analytics -- Backend starting on http://localhost:5000")
    app.run(debug=True, port=5000, host="0.0.0.0")
