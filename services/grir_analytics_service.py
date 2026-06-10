"""
SAP GR/IR Reconciliation Analytics Service
In-memory analytics engine — no subprocess, no JSON file I/O.
All computation from uploaded DataFrames.
"""

import io
import os
import re
import math
import json
import traceback
import numpy as np
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from flask import send_file

PROJECT_DIR = Path(__file__).resolve().parent.parent

def _load_rules():
    rules_path = PROJECT_DIR / "config" / "analytics_rules.json"
    if rules_path.exists():
        with open(rules_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ─── Column Alias Maps ───────────────────────────────────────────────────────

GRIR_MAP = {
    'PO Number': ['po number', 'po_number', 'po no', 'po_no', 'purchase order', 'ebeln'],
    'PO Item': ['po item', 'po_item', 'item', 'ebelp'],
    'Trans Type': ['trans type', 'trans_type', 'transaction type', 'transaction_type', 'vgabe'],
    'Dr/Cr Ind': ['dr/cr ind', 'dr_cr_ind', 'debit/credit indicator', 'debit_credit_indicator', 'shkzg'],
    'Quantity': ['quantity', 'qty', 'menge'],
    'Amt (FC)': ['amt (fc)', 'amt_fc', 'amount fc', 'amount_fc', 'wrbtr'],
    'Posting Date': ['posting date', 'posting_date', 'budat'],
    'Document Date': ['document date', 'document_date', 'bldat'],
    'Amt (LC)': ['amt (lc)', 'amt_lc', 'amount lc', 'amount_lc', 'dmbtr'],
    'Plant': ['plant', 'werks'],
    'Doc Type': ['doc type', 'doc_type', 'blart'],
    'Document No': ['document no', 'document_no', 'document number', 'document_number', 'belnr'],
    'Doc Item': ['doc item', 'doc_item', 'buzei'],
    'Reference Doc': ['reference doc', 'reference_doc', 'xblnr'],
}

EKKO_MAP = {
    'Purchasing Document': ['purchasing document', 'purchasing_document', 'purchase order', 'ebeln'],
    'Company Code': ['company code', 'company_code', 'bukrs'],
    'Purchasing Doc. Type': ['purchasing doc. type', 'purchasing_doc_type', 'bsart'],
    'Deletion indicator': ['deletion indicator', 'deletion_indicator', 'loekz'],
    'Currency': ['currency', 'waers'],
    'Exchange Rate': ['exchange rate', 'exchange_rate', 'kuras'],
}

ME2N_MAP = {
    'Purchasing Document': ['purchasing document', 'purchasing_document', 'ebeln'],
    'Purchasing Group': ['purchasing group', 'purchasing_group', 'ekgrp'],
    'Purch. organization': ['purch. organization', 'purchasing organization', 'purchasing_organization', 'ekorg'],
    'Deletion indicator': ['deletion indicator', 'deletion_indicator', 'loekz'],
    'Purchasing Doc. Type': ['purchasing doc. type', 'purchasing_doc_type', 'bsart'],
    'Material': ['material', 'matnr'],
    'Short Text': ['short text', 'short_text', 'material description', 'material_description', 'txz01'],
    'Order Quantity': ['order quantity', 'order_quantity', 'menge'],
    'Still to be delivered (qty)': ['still to be delivered (qty)', 'still_to_be_delivered_qty', 'open quantity', 'open_quantity'],
    'Document Date': ['document date', 'document_date', 'bldat'],
    'Supplier/Supplying Plant': ['supplier/supplying plant', 'supplier', 'name of supplier', 'supplier name', 'lifnr'],
    'Net Price': ['net price', 'net_price', 'netpr'],
    'Item': ['item', 'ebelp'],
    'Item category': ['item category', 'item_category', 'pstyp'],
    'Plant': ['plant', 'werks'],
    'Material Group': ['material group', 'material_group', 'matkl'],
    'Currency': ['currency', 'waers'],
    'Price unit': ['price unit', 'price_unit', 'peinh'],
    'Still to be delivered (value)': ['still to be delivered (value)', 'still_to_be_delivered_val', 'still_to_be_delivered_value'],
    'Still to be invoiced (qty)': ['still to be invoiced (qty)', 'still_to_be_invoiced_qty'],
    'Still to be invoiced (val.)': ['still to be invoiced (val.)', 'still_to_be_invoiced_val', 'still_to_be_invoiced_value'],
    'Open value': ['open value', 'open_value'],
    'Name of Supplier': ['name of supplier', 'name_of_supplier', 'supplier name', 'supplier_name'],
    'Net Order Value': ['net order value', 'net_order_value', 'netwr'],
    'Total open value': ['total open value', 'total_open_value'],
    'Delivery date': ['delivery date', 'delivery_date', 'eeind'],
}

GRIR_ALIASES = {
    'PO Number': ['po number', 'po_number', 'po no', 'po_no', 'purchase order', 'ebeln'],
    'PO Item': ['po item', 'po_item', 'item', 'ebelp'],
    'Trans Type': ['trans type', 'trans_type', 'transaction type', 'transaction_type', 'vgabe'],
    'Dr/Cr Ind': ['dr/cr ind', 'dr_cr_ind', 'debit/credit indicator', 'debit_credit_indicator', 'shkzg'],
    'Quantity': ['quantity', 'qty', 'menge'],
    'Amt (FC)': ['amt (fc)', 'amt_fc', 'amount fc', 'amount_fc', 'wrbtr'],
    'Posting Date': ['posting date', 'posting_date', 'budat'],
    'Document Date': ['document date', 'document_date', 'bldat'],
    'Amt (LC)': ['amt (lc)', 'amt_lc', 'amount lc', 'amount_lc', 'dmbtr'],
    'Plant': ['plant', 'werks'],
}

EKKO_ALIASES_UPLOAD = {
    'Purchasing Document': ['purchasing document', 'purchasing_document', 'purchase order', 'ebeln'],
    'Company Code': ['company code', 'company_code', 'bukrs'],
    'Purchasing Doc. Type': ['purchasing doc. type', 'purchasing_doc_type', 'bsart'],
    'Deletion indicator': ['deletion indicator', 'deletion_indicator', 'loekz'],
    'Currency': ['currency', 'waers'],
    'Exchange Rate': ['exchange rate', 'exchange_rate', 'kuras'],
}

ME2N_ALIASES_UPLOAD = {
    'Purchasing Document': ['purchasing document', 'purchasing_document', 'ebeln'],
    'Short Text': ['short text', 'short_text', 'material description', 'material_description', 'txz01'],
    'Order Quantity': ['order quantity', 'order_quantity', 'menge'],
    'Net Price': ['net price', 'net_price', 'netpr'],
    'Item': ['item', 'ebelp'],
    'Plant': ['plant', 'werks'],
    'Net Order Value': ['net order value', 'net_order_value', 'netwr'],
    'Open value': ['open value', 'open_value', 'still to be delivered (value)', 'still_to_be_delivered_value'],
}


# ─── Utility Functions ───────────────────────────────────────────────────────

def safe_json(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj) if not (math.isnan(obj) or math.isinf(obj)) else None
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat() if pd.notna(obj) else None
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    raise TypeError(f"Type {type(obj)} not serializable")


def safe_float(v, default=0.0):
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def map_columns(df, mapping_dict):
    col_map = {}
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    for std_name, aliases in mapping_dict.items():
        for alias in aliases:
            if alias in cols_lower:
                col_map[cols_lower[alias]] = std_name
                break
        if std_name.lower() in cols_lower and std_name not in col_map.values():
            col_map[cols_lower[std_name.lower()]] = std_name
    return df.rename(columns=col_map)


def material_key(row):
    mat = str(row.get("Material", "")).strip()
    if mat and mat not in ("nan", "None", ""):
        return mat
    return str(row.get("Short Text", "")).strip()


def material_label(row):
    mat = str(row.get("Material", "")).strip()
    text = str(row.get("Short Text", "")).strip()
    if mat and mat not in ("nan", "None", "") and text and text not in ("nan", "None"):
        return f"{mat} — {text[:60]}"
    return text or mat or "Unknown"


def detect_sap_file_type(df):
    cols = [str(c).strip().lower() for c in df.columns]
    if any(alias in cols for alias in ['exchange rate', 'exchange_rate', 'kuras']):
        return 'EKKO'
    if any(alias in cols for alias in ['trans type', 'trans_type', 'dr/cr ind', 'dr_cr_ind', 'amt (fc)', 'amt_fc']):
        return 'GRIR'
    if any(alias in cols for alias in ['net order value', 'net_order_value', 'still to be delivered (qty)', 'still to be delivered (value)']):
        return 'ME2N'
    if 'purchasing document' in cols or 'purchasing_document' in cols:
        if 'company code' in cols or 'company_code' in cols or 'bukrs' in cols:
            return 'EKKO'
        else:
            return 'ME2N'
    return None


def align_dataframe_columns(df, required_map, file_type):
    col_map = {}
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    missing_required = []

    required_keys = []
    if file_type == 'GRIR':
        required_keys = ['PO Number', 'PO Item', 'Trans Type', 'Dr/Cr Ind', 'Quantity', 'Amt (LC)', 'Posting Date']
    elif file_type == 'EKKO':
        required_keys = ['Purchasing Document', 'Currency', 'Exchange Rate', 'Company Code', 'Purchasing Doc. Type']
    elif file_type == 'ME2N':
        required_keys = ['Purchasing Document', 'Short Text', 'Order Quantity', 'Net Price', 'Item', 'Plant', 'Net Order Value', 'Open value']

    for std_name, aliases in required_map.items():
        found = False
        for alias in aliases:
            if alias in cols_lower:
                col_map[cols_lower[alias]] = std_name
                found = True
                break
        if not found:
            if std_name.lower() in cols_lower:
                col_map[cols_lower[std_name.lower()]] = std_name
            elif std_name in required_keys:
                missing_required.append(std_name)

    if missing_required:
        raise ValueError(f"Missing required columns for {file_type}: {missing_required}")

    return df.rename(columns=col_map)


# ─── Data Cleaning ───────────────────────────────────────────────────────────

def clean_grir(grir):
    grir.columns = grir.columns.str.strip()
    cols_to_ensure = {
        'PO Number': '', 'Doc Type': '', 'PO Item': '0', 'Plant': '',
        'Trans Type': '1', 'Document No': '', 'Doc Item': '', 'Quantity': 0.0,
        'Amt (FC)': 0.0, 'Posting Date': pd.NaT, 'Document Date': pd.NaT,
        'Amt (LC)': 0.0, 'Reference Doc': '', 'Dr/Cr Ind': 'S',
    }
    for col, default in cols_to_ensure.items():
        if col not in grir.columns:
            grir[col] = default

    grir['PO Number'] = grir['PO Number'].astype(str).str.strip()
    grir['PO Item'] = pd.to_numeric(grir['PO Item'], errors='coerce').fillna(0).astype(int).astype(str)
    grir['Trans Type'] = grir['Trans Type'].astype(str).str.strip()
    grir['Dr/Cr Ind'] = grir['Dr/Cr Ind'].astype(str).str.strip()
    grir['Quantity'] = pd.to_numeric(grir['Quantity'], errors='coerce').fillna(0)
    grir['Amt (LC)'] = pd.to_numeric(grir['Amt (LC)'], errors='coerce').fillna(0)
    grir['Amt (FC)'] = pd.to_numeric(grir['Amt (FC)'], errors='coerce').fillna(grir['Amt (LC)'])
    grir['Posting Date'] = pd.to_datetime(grir['Posting Date'], errors='coerce')
    grir['Document Date'] = pd.to_datetime(grir['Document Date'], errors='coerce')
    grir['Plant'] = grir['Plant'].astype(str).str.strip()

    grir['Signed Amt'] = np.where(grir['Dr/Cr Ind'] == 'S', grir['Amt (LC)'], -grir['Amt (LC)'])
    grir['Signed Qty'] = np.where(grir['Dr/Cr Ind'] == 'S', grir['Quantity'], -grir['Quantity'])
    return grir


def clean_me2n(me2n):
    me2n.columns = me2n.columns.str.strip()
    cols_to_ensure = {
        'Purchasing Document': '', 'Item': '10', 'Order Quantity': 0.0,
        'Still to be delivered (qty)': 0.0, 'Net Price': 0.0, 'Net Order Value': 0.0,
        'Still to be invoiced (qty)': 0.0, 'Still to be invoiced (val.)': 0.0,
        'Open value': 0.0, 'Total open value': 0.0, 'Still to be delivered (value)': 0.0,
        'Name of Supplier': '', 'Supplier/Supplying Plant': '', 'Short Text': '',
        'Material': '', 'Plant': '', 'Material Group': '', 'Deletion indicator': '',
        'Document Date': pd.NaT, 'Delivery date': pd.NaT, 'Purchasing Group': '', 'Purch. organization': '',
    }
    for col, default in cols_to_ensure.items():
        if col not in me2n.columns:
            me2n[col] = default

    me2n['Purchasing Document'] = me2n['Purchasing Document'].astype(str).str.strip()
    me2n['Item'] = pd.to_numeric(me2n['Item'], errors='coerce').fillna(0).astype(int).astype(str)
    me2n['Order Quantity'] = pd.to_numeric(me2n['Order Quantity'], errors='coerce').fillna(0)
    me2n['Still to be delivered (qty)'] = pd.to_numeric(me2n['Still to be delivered (qty)'], errors='coerce').fillna(0)
    me2n['Net Price'] = pd.to_numeric(me2n['Net Price'], errors='coerce').fillna(0)
    me2n['Net Order Value'] = pd.to_numeric(me2n['Net Order Value'], errors='coerce').fillna(0)
    me2n['Still to be invoiced (qty)'] = pd.to_numeric(me2n['Still to be invoiced (qty)'], errors='coerce').fillna(0)
    me2n['Still to be invoiced (val.)'] = pd.to_numeric(me2n['Still to be invoiced (val.)'], errors='coerce').fillna(0)
    me2n['Open value'] = pd.to_numeric(me2n['Open value'], errors='coerce').fillna(0)
    me2n['Total open value'] = pd.to_numeric(me2n['Total open value'], errors='coerce').fillna(0)
    me2n['Still to be delivered (value)'] = pd.to_numeric(me2n['Still to be delivered (value)'], errors='coerce').fillna(0)

    if 'Name of Supplier' in me2n.columns and me2n['Name of Supplier'].dropna().any():
        me2n['Vendor'] = me2n['Name of Supplier']
    elif 'Supplier/Supplying Plant' in me2n.columns:
        me2n['Vendor'] = me2n['Supplier/Supplying Plant']
    else:
        me2n['Vendor'] = ''

    me2n['Vendor'] = me2n['Vendor'].apply(lambda v: re.sub(r'^\d+\s+', '', str(v)).strip() if pd.notna(v) else '')
    me2n['Short Text'] = me2n['Short Text'].astype(str).str.strip()
    me2n['Material'] = me2n['Material'].astype(str).str.strip()
    me2n['Plant'] = me2n['Plant'].astype(str).str.strip()
    me2n['Material Group'] = me2n['Material Group'].astype(str).str.strip()
    me2n['Deletion indicator'] = me2n['Deletion indicator'].astype(str).str.strip()
    me2n['Document Date'] = pd.to_datetime(me2n['Document Date'], errors='coerce')
    me2n['Delivery date'] = pd.to_datetime(me2n['Delivery date'], errors='coerce')
    return me2n


def clean_ekko(ekko):
    ekko.columns = ekko.columns.str.strip()
    if 'Purchasing Document' not in ekko.columns:
        ekko['Purchasing Document'] = ''
    if 'Company Code' not in ekko.columns:
        ekko['Company Code'] = ''
    if 'Currency' not in ekko.columns:
        ekko['Currency'] = 'INR'
    if 'Exchange Rate' not in ekko.columns:
        ekko['Exchange Rate'] = 1.0
    if 'Purchasing Doc. Type' not in ekko.columns:
        ekko['Purchasing Doc. Type'] = ''

    ekko['Purchasing Document'] = ekko['Purchasing Document'].astype(str).str.strip()
    ekko['Company Code'] = ekko['Company Code'].astype(str).str.strip()
    ekko['Currency'] = ekko['Currency'].astype(str).str.strip().fillna('INR')
    ekko['Exchange Rate'] = pd.to_numeric(ekko['Exchange Rate'], errors='coerce').fillna(1.0)
    ekko['Exchange Rate'] = ekko['Exchange Rate'].apply(lambda x: 1.0 if x <= 0 else x)
    return ekko


# ─── Aging ───────────────────────────────────────────────────────────────────

def aging_bucket(days):
    if pd.isna(days) or days is None:
        return '180+'
    if days <= 30:
        return '0-30'
    if days <= 60:
        return '31-60'
    if days <= 90:
        return '61-90'
    if days <= 180:
        return '91-180'
    return '180+'


# ─── Status Classification ──────────────────────────────────────────────────

def classify_status(row):
    gr_qty = row['net_gr_qty']
    ir_qty = row['net_ir_qty']
    open_qty = row['open_qty']
    open_val = row['open_val']
    rev_pct = row['reversal_pct']
    tol = 0.01

    if rev_pct >= 99 or (abs(gr_qty) < tol and abs(ir_qty) < tol):
        return 'FULLY REVERSED'
    if abs(gr_qty) < tol and ir_qty > tol:
        return 'IR ONLY'
    if gr_qty > tol and abs(ir_qty) < tol:
        if rev_pct > 0:
            return 'PARTIALLY REVERSED'
        return 'GR ONLY'
    if abs(open_qty) < tol and abs(open_val) < 1.0:
        return 'FULLY RECONCILED'
    if abs(open_qty) < tol and abs(open_val) >= 1.0:
        return 'PRICE VARIANCE'
    if open_qty < -tol:
        return 'OVER INVOICED'
    if open_qty > tol:
        if ir_qty > tol:
            return 'PARTIALLY INVOICED'
        return 'GR ONLY'
    return 'PARTIALLY INVOICED'


# ─── Risk Scoring ────────────────────────────────────────────────────────────

def compute_row_risk(row, reconciled):
    if reconciled or row['status'] in ('FULLY RECONCILED', 'FULLY REVERSED'):
        return 0, 'LOW'

    score = 0
    status_map = {
        'GR ONLY': 35, 'IR ONLY': 50, 'PARTIALLY INVOICED': 20,
        'OVER INVOICED': 60, 'PRICE VARIANCE': 30, 'PARTIALLY REVERSED': 10,
    }
    score += status_map.get(row['status'], 15)

    days_open = row.get('days_open')
    if pd.notna(days_open):
        if days_open > 90:
            score += 30
        elif days_open > 60:
            score += 20
        elif days_open > 30:
            score += 10

    price_var_pct = abs(row.get('price_var_pct', 0.0))
    if price_var_pct > 10:
        score += 10
    elif price_var_pct > 5:
        score += 5

    av = abs(row.get('open_val', 0.0))
    if av > 1000000:
        score += 10
    elif av > 100000:
        score += 5

    score = min(max(int(score), 0), 100)

    if score >= 75:
        level = 'CRITICAL'
    elif score >= 50:
        level = 'HIGH'
    elif score >= 25:
        level = 'MEDIUM'
    else:
        level = 'LOW'

    return score, level


# ─── Narrative Generation ───────────────────────────────────────────────────

def explain(row):
    s = row['status']
    gq = row['net_gr_qty']
    iq = row['net_ir_qty']
    oq = row['open_qty']
    ov = row['open_val']
    raw_vendor = row.get('Vendor', 'Vendor')
    v = str(raw_vendor)[:40] if raw_vendor and str(raw_vendor) not in ('nan', 'None', '') else 'Vendor'
    pct = row.get('inv_completion_pct', 0.0)

    if s == 'GR ONLY':
        return (f"Goods quantity {gq:.1f} units worth INR {ov:,.0f} received from {v}, "
                f"but no invoice has been posted. Accrual liability is understated by this amount.")
    if s == 'IR ONLY':
        return (f"Invoice of INR {abs(ov):,.0f} was received from {v} without a corresponding "
                f"goods receipt. This represents a control violation — payment must not be released.")
    if s == 'PARTIALLY INVOICED':
        return (f"{gq:.1f} units received; only {iq:.1f} invoiced ({pct:.0f}% completion). "
                f"Pending invoice for {oq:.1f} units valued at INR {ov:,.0f}. Vendor follow-up required.")
    if s == 'OVER INVOICED':
        return (f"Invoice qty ({iq:.1f}) exceeds GR qty ({gq:.1f}) by {abs(oq):.1f} units. "
                f"Excess invoice value INR {abs(ov):,.0f}. Risk of duplicate invoice or fraud. Block payment immediately.")
    if s == 'PRICE VARIANCE':
        return (f"Quantity reconciled, but value mismatch of INR {abs(ov):,.0f} detected. "
                f"Price variance {row['price_var_pct']:.1f}% between GR and IR posting.")
    if s == 'PARTIALLY REVERSED':
        return (f"Partial reversal of {row['reversal_pct']:.0f}% detected. "
                f"Net open balance of INR {abs(ov):,.0f} remains.")
    if s == 'FULLY REVERSED':
        return "All transactions fully reversed. Net balance is zero."
    return f"Open balance INR {abs(ov):,.0f} with status {s}."


# ─── Reconciliation Engine ──────────────────────────────────────────────────

def reconcile(grir, me2n, ekko, analysis_date):
    print("  Building GRIR aggregates by PO+Item ...")

    grir['gr_qty_s'] = np.where((grir['Trans Type'] == '1') & (grir['Dr/Cr Ind'] == 'S'), grir['Signed Qty'], 0)
    grir['gr_qty_h'] = np.where((grir['Trans Type'] == '1') & (grir['Dr/Cr Ind'] == 'H'), grir['Quantity'], 0)
    grir['gr_val_s'] = np.where((grir['Trans Type'] == '1') & (grir['Dr/Cr Ind'] == 'S'), grir['Signed Amt'], 0)
    grir['gr_val_h'] = np.where((grir['Trans Type'] == '1') & (grir['Dr/Cr Ind'] == 'H'), grir['Amt (LC)'], 0)

    grir['ir_qty_s'] = np.where((grir['Trans Type'] == '2') & (grir['Dr/Cr Ind'] == 'S'), grir['Quantity'], 0)
    grir['ir_qty_h'] = np.where((grir['Trans Type'] == '2') & (grir['Dr/Cr Ind'] == 'H'), grir['Quantity'], 0)
    grir['ir_val_s'] = np.where((grir['Trans Type'] == '2') & (grir['Dr/Cr Ind'] == 'S'), grir['Amt (LC)'], 0)
    grir['ir_val_h'] = np.where((grir['Trans Type'] == '2') & (grir['Dr/Cr Ind'] == 'H'), grir['Amt (LC)'], 0)

    gr_agg = grir[grir['Trans Type'] == '1'].groupby(['PO Number', 'PO Item']).agg(
        gr_qty_s=('gr_qty_s', 'sum'),
        gr_qty_h=('gr_qty_h', 'sum'),
        gr_val_s=('gr_val_s', 'sum'),
        gr_val_h=('gr_val_h', 'sum'),
        gr_txn_count=('Quantity', 'count'),
        earliest_gr=('Posting Date', 'min'),
        latest_gr=('Posting Date', 'max'),
    ).reset_index()

    ir_agg = grir[grir['Trans Type'] == '2'].groupby(['PO Number', 'PO Item']).agg(
        ir_qty_s=('ir_qty_s', 'sum'),
        ir_qty_h=('ir_qty_h', 'sum'),
        ir_val_s=('ir_val_s', 'sum'),
        ir_val_h=('ir_val_h', 'sum'),
        ir_txn_count=('Quantity', 'count'),
        ir_doc_count=('Document No', 'nunique') if 'Document No' in grir.columns else ('Quantity', 'count'),
        earliest_ir=('Posting Date', 'min'),
        latest_ir=('Posting Date', 'max'),
        earliest_doc_date=('Document Date', 'min'),
    ).reset_index()

    print("  Merging ME2N with EKKO exchange rates ...")
    ekko_for_merge = ekko[['Purchasing Document', 'Exchange Rate', 'Currency']].rename(
        columns={'Currency': 'PO_Currency'}
    ).drop_duplicates(subset=['Purchasing Document'])

    me2n_mapped = me2n.merge(ekko_for_merge, on='Purchasing Document', how='left')
    me2n_mapped['Exchange Rate'] = me2n_mapped['Exchange Rate'].fillna(1.0)
    me2n_mapped['PO_Currency'] = me2n_mapped['PO_Currency'].fillna('INR')
    me2n_mapped['Currency'] = me2n_mapped['PO_Currency']

    me2n_mapped['Net_Order_Value_INR'] = me2n_mapped['Net Order Value'] * me2n_mapped['Exchange Rate']
    me2n_mapped['Open_Value_INR'] = me2n_mapped['Open value'] * me2n_mapped['Exchange Rate']

    print("  Merging with GR/IR postings ...")
    merge_cols = ['Purchasing Document', 'Item',
                  'Vendor', 'Short Text', 'Material', 'Material Group', 'Plant',
                  'Order Quantity', 'Still to be delivered (qty)',
                  'Net Price', 'Net Order Value', 'Net_Order_Value_INR', 'Open_Value_INR',
                  'Still to be invoiced (qty)', 'Still to be invoiced (val.)',
                  'Open value', 'Total open value',
                  'Still to be delivered (value)',
                  'Deletion indicator', 'Document Date', 'Delivery date',
                  'Purchasing Group', 'Exchange Rate', 'Currency']
    existing_merge_cols = [c for c in merge_cols if c in me2n_mapped.columns]
    me2n_key = me2n_mapped[existing_merge_cols].copy()
    me2n_key.rename(columns={
        'Purchasing Document': 'PO Number',
        'Item': 'PO Item',
    }, inplace=True)

    df = me2n_key.copy()
    df = df.merge(ir_agg, on=['PO Number', 'PO Item'], how='left')
    df = df.merge(gr_agg, on=['PO Number', 'PO Item'], how='left')

    num_cols = ['gr_qty_s', 'gr_qty_h', 'gr_val_s', 'gr_val_h',
                'ir_qty_s', 'ir_qty_h', 'ir_val_s', 'ir_val_h',
                'ir_txn_count', 'ir_doc_count', 'gr_txn_count']
    for c in num_cols:
        if c in df.columns:
            df[c] = df[c].fillna(0)

    df['net_gr_qty_grir'] = df.get('gr_qty_s', 0) - df.get('gr_qty_h', 0)
    df['net_gr_val_grir'] = df.get('gr_val_s', 0) - df.get('gr_val_h', 0)
    df['net_ir_qty'] = df.get('ir_qty_s', 0) - df.get('ir_qty_h', 0)
    df['net_ir_val'] = df.get('ir_val_s', 0) - df.get('ir_val_h', 0)

    df['net_gr_qty'] = df['Order Quantity'] - df['Still to be delivered (qty)']
    df['net_gr_val'] = (df['Net Order Value'] - df['Still to be delivered (value)']) * df['Exchange Rate']

    mask_gr = df['net_gr_qty_grir'].abs() > 0
    df.loc[mask_gr, 'net_gr_qty'] = df.loc[mask_gr, 'net_gr_qty_grir']
    df.loc[mask_gr, 'net_gr_val'] = df.loc[mask_gr, 'net_gr_val_grir']

    df['open_qty'] = df['net_gr_qty'] - df['net_ir_qty']
    df['open_val'] = df['net_gr_val'] - df['net_ir_val']
    df['exposure_val'] = (df['net_gr_val'] - df['net_ir_val']).abs()

    mask_me2n_open = (df['Still to be invoiced (qty)'].abs() > 0.01) & (df['open_qty'].abs() < 0.01)
    df.loc[mask_me2n_open, 'open_qty'] = df.loc[mask_me2n_open, 'Still to be invoiced (qty)']
    df.loc[mask_me2n_open, 'open_val'] = df.loc[mask_me2n_open, 'Still to be invoiced (val.)'] * df.loc[mask_me2n_open, 'Exchange Rate']

    df['inv_completion_pct'] = np.where(
        df['net_gr_qty'] > 0,
        (df['net_ir_qty'] / df['net_gr_qty'] * 100).clip(-200, 200),
        0
    )

    df['ir_reversal_qty'] = df.get('ir_qty_h', 0)
    df['ir_reversal_val'] = df.get('ir_val_h', 0)
    df['gr_reversal_qty'] = df.get('gr_qty_h', 0)
    df['gr_reversal_val'] = df.get('gr_val_h', 0)
    df['reversal_pct'] = np.where(
        df.get('ir_qty_s', 0) > 0,
        (df.get('ir_qty_h', 0) / df.get('ir_qty_s', 1) * 100).clip(0, 100),
        0
    )

    df['invoice_price'] = np.where(df['net_ir_qty'] > 0, df['net_ir_val'] / df['net_ir_qty'], df['Net Price'] * df['Exchange Rate'])
    df['po_price_inr'] = df['Net Price'] * df['Exchange Rate']
    df['price_var_abs'] = (df['invoice_price'] - df['po_price_inr']) * df['net_ir_qty']
    df['price_var_pct'] = np.where(
        df['po_price_inr'] > 0,
        ((df['invoice_price'] - df['po_price_inr']) / df['po_price_inr'] * 100).clip(-200, 200),
        0
    )

    df['posting_date'] = df.get('earliest_ir', pd.NaT)
    mask_no_posting = df['posting_date'].isna()
    if 'earliest_gr' in df.columns:
        df.loc[mask_no_posting, 'posting_date'] = df.loc[mask_no_posting, 'earliest_gr']
    mask_still_no = df['posting_date'].isna()
    df.loc[mask_still_no, 'posting_date'] = df.loc[mask_still_no, 'Document Date']

    df['days_open'] = (analysis_date - pd.to_datetime(df['posting_date'])).dt.days

    df['aging_bucket'] = np.where(df['days_open'] <= 30, '0-30',
                         np.where(df['days_open'] <= 60, '31-60',
                         np.where(df['days_open'] <= 90, '61-90',
                         np.where(df['days_open'] <= 180, '91-180',
                         np.where(pd.isna(df['days_open']), 'Unknown', '180+')))))

    tol = 0.01
    qty_diff = (df['net_gr_qty'] - df['net_ir_qty']).abs()
    df['amount_matched'] = (
        (df['exposure_val'] < tol) &
        (qty_diff < tol)
    )
    df['reconciled'] = df['amount_matched']

    status = np.full(len(df), 'Open Issue', dtype=object)
    status[df['open_val'] > 0] = 'Price Variance'
    status[df['open_qty'] > 0] = 'Partial Invoice'
    status[(df['net_ir_qty'] > 0) & (df['net_gr_qty'] <= 0)] = 'IR No GR'
    status[(df['net_gr_qty'] > 0) & (df['net_ir_qty'] <= 0)] = 'GR No IR'
    status[df['amount_matched']] = 'Reconciled'
    df['status'] = status

    df['material_key'] = df['Material'].fillna(df.get('Short Text', '')).fillna('Unknown').astype(str).str.strip()
    df['material_label'] = df['Material'].fillna('').astype(str) + " - " + df.get('Short Text', '').fillna('').astype(str)
    df['material_label'] = df['material_label'].str.strip(' -')

    # Vectorized Risk Score
    risk_score = np.zeros(len(df), dtype=int)
    val = df['exposure_val'].fillna(0)
    risk_score += np.where(val > 100000, 5, np.where(val > 50000, 3, np.where(val > 10000, 1, 0)))
    
    days = df['days_open']
    days_score = np.where(days > 90, 5, np.where(days > 60, 3, np.where(days > 30, 1, 0)))
    risk_score += np.where(pd.notna(days), days_score, 0)
    
    risk_score = np.where(df['reconciled'], 0, risk_score)
    risk_level = np.where(risk_score >= 8, 'High', np.where(risk_score >= 4, 'Medium', 'Low'))
    risk_level = np.where(df['reconciled'], 'Low', risk_level)
    
    df['risk_score'] = risk_score
    df['risk_level'] = risk_level

    print(f"  Reconciliation complete: {len(df):,} PO line items")
    return df


# ─── Analytics Builders ──────────────────────────────────────────────────────

def build_kpis(df, ekko=None):
    total_items = len(df)
    total_gr_val = df['net_gr_val'].sum()
    total_ir_val = df['net_ir_val'].sum()
    total_open_exposure = df['exposure_val'].sum()
    total_open_signed = df['open_val'].sum()
    total_open_q = df['open_qty'].sum()

    recon_count = int(df['amount_matched'].sum())
    recon_rate = recon_count / total_items * 100 if total_items else 0

    status_dist = df['status'].value_counts().to_dict()
    risk_dist = df['risk_level'].value_counts().to_dict()

    pending_invoice_val = df[df['status'].isin(['GR ONLY', 'PARTIALLY INVOICED'])]['open_val'].sum()
    over_inv_val = df[df['status'] == 'OVER INVOICED']['open_val'].abs().sum()
    ir_only_val = df[df['status'] == 'IR ONLY']['net_ir_val'].sum()
    total_reversals_val = df['ir_reversal_val'].sum()

    spend_by_vendor = df.groupby('Vendor')['Net_Order_Value_INR'].sum().sort_values(ascending=False)
    spend_by_matgrp = df.groupby('Material Group')['Net_Order_Value_INR'].sum().sort_values(ascending=False)
    spend_by_purchgrp = df.groupby('Purchasing Group')['Net_Order_Value_INR'].sum().sort_values(ascending=False)

    company_codes = []
    if ekko is not None and 'Company Code' in ekko.columns:
        company_codes = sorted(ekko['Company Code'].dropna().astype(str).unique().tolist())

    return {
        'total_po_items': int(total_items),
        'total_gr_value': round(float(total_gr_val), 2),
        'total_ir_value': round(float(total_ir_val), 2),
        'total_open_value': round(float(total_open_exposure), 2),
        'total_open_value_signed': round(float(total_open_signed), 2),
        'total_open_qty': round(float(total_open_q), 2),
        'reconciliation_rate': round(float(recon_rate), 1),
        'reconciled_count': recon_count,
        'matched_lines': recon_count,
        'unmatched_lines': int(total_items - recon_count),
        'open_item_count': int(total_items - recon_count),
        'critical_items': int((df['risk_level'] == 'CRITICAL').sum()),
        'high_risk_items': int((df['risk_level'] == 'HIGH').sum()),
        'medium_risk_items': int((df['risk_level'] == 'MEDIUM').sum()),
        'low_risk_items': int((df['risk_level'] == 'LOW').sum()),
        'pending_invoice_val': round(float(pending_invoice_val), 2),
        'over_invoice_val': round(float(over_inv_val), 2),
        'ir_only_val': round(float(ir_only_val), 2),
        'total_reversals_val': round(float(total_reversals_val), 2),
        'status_distribution': {k: int(v) for k, v in status_dist.items()},
        'risk_distribution': {k: int(v) for k, v in risk_dist.items()},
        'unique_vendors': int(df['Vendor'].nunique()),
        'unique_pos': int(df['PO Number'].nunique()),
        'unique_plants': int(df['Plant'].nunique()),
        'total_materials': int(df['material_key'].nunique()),
        'total_procurement_spend_inr': round(float(df['Net_Order_Value_INR'].sum()), 2),
        'top_supplier': str(spend_by_vendor.index[0]) if len(spend_by_vendor) else 'N/A',
        'top_material_group': str(spend_by_matgrp.index[0]) if len(spend_by_matgrp) else 'N/A',
        'top_purchasing_group': str(spend_by_purchgrp.index[0]) if len(spend_by_purchgrp) else 'N/A',
        'total_purchasing_groups': int(df['Purchasing Group'].nunique()),
        'total_plants': int(df['Plant'].nunique()),
        'total_suppliers': int(df['Vendor'].nunique()),
        'company_codes': company_codes,
    }


def build_aging(df):
    buckets = ['0-30', '31-60', '61-90', '91-180', '180+']
    result = []
    for b in buckets:
        sub = df[df['aging_bucket'] == b]
        open_sub = sub[~sub['reconciled']]
        result.append({
            'bucket': b,
            'total_count': int(len(sub)),
            'open_count': int(len(open_sub)),
            'open_value': round(float(open_sub['exposure_val'].sum()), 2),
            'exposure': round(float(open_sub['exposure_val'].sum()), 2),
            'gr_only_val': round(float(sub[sub['status'] == 'GR ONLY']['open_val'].sum()), 2),
            'partial_inv_val': round(float(sub[sub['status'] == 'PARTIALLY INVOICED']['open_val'].sum()), 2),
            'over_inv_val': round(float(sub[sub['status'] == 'OVER INVOICED']['open_val'].abs().sum()), 2),
            'ir_only_val': round(float(sub[sub['status'] == 'IR ONLY']['net_ir_val'].sum()), 2),
        })
    return result


def calculate_group_risk_scores(df, group_col, total_open_exposure):
    groups = []
    total_exposure = max(total_open_exposure, 1.0)

    for name, gdf in df.groupby(group_col):
        if not name or pd.isna(name) or str(name).strip() in ('', 'nan', 'None'):
            continue

        grp_exposure = gdf['exposure_val'].sum()
        exposure_pct = grp_exposure / total_exposure * 100
        if grp_exposure == 0:
            exp_score = 0
        elif exposure_pct < 5:
            exp_score = 25
        elif exposure_pct < 10:
            exp_score = 50
        elif exposure_pct < 20:
            exp_score = 75
        else:
            exp_score = 100

        avg_days = gdf['days_open'].dropna().mean()
        if pd.isna(avg_days) or avg_days == 0:
            age_score = 0
        elif avg_days <= 30:
            age_score = 25
        elif avg_days <= 60:
            age_score = 50
        elif avg_days <= 90:
            age_score = 75
        else:
            age_score = 100

        recon_rate = gdf['reconciled'].sum() / len(gdf) * 100
        recon_failure_rate = 100 - recon_rate
        if recon_failure_rate == 0:
            recon_score = 0
        elif recon_failure_rate < 5:
            recon_score = 25
        elif recon_failure_rate < 10:
            recon_score = 50
        elif recon_failure_rate < 20:
            recon_score = 75
        else:
            recon_score = 100

        avg_var = gdf['price_var_pct'].abs().mean()
        if pd.isna(avg_var) or avg_var == 0:
            var_score = 0
        elif avg_var < 2:
            var_score = 25
        elif avg_var < 5:
            var_score = 50
        elif avg_var < 10:
            var_score = 75
        else:
            var_score = 100

        if group_col == 'Plant':
            score = 0.40 * exp_score + 0.30 * age_score + 0.30 * recon_score
        else:
            score = 0.40 * exp_score + 0.30 * age_score + 0.20 * recon_score + 0.10 * var_score

        score = min(max(round(score), 0), 100)

        if score >= 76:
            risk_level = 'CRITICAL'
        elif score >= 51:
            risk_level = 'HIGH'
        elif score >= 26:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'

        key_name = 'material' if group_col in ('Short Text', 'material_key', 'material_label') else group_col.lower()
        groups.append({
            key_name: str(name),
            'exposure': round(float(grp_exposure), 2),
            'avg_days_open': round(float(avg_days), 1) if not pd.isna(avg_days) else 0.0,
            'recon_rate': round(float(recon_rate), 1),
            'avg_price_variance': round(float(avg_var), 1) if not pd.isna(avg_var) else 0.0,
            'score': score,
            'risk_level': risk_level,
        })

    return sorted(groups, key=lambda x: x['exposure'], reverse=True)


def generate_risk_flags(df, total_open_exposure):
    flags = []
    total_exposure = max(total_open_exposure, 1.0)
    high_crit_df = df[df['risk_level'].isin(['HIGH', 'CRITICAL'])]

    for _, row in high_crit_df.iterrows():
        line_exposure = abs(row['open_val'])
        exp_pct = line_exposure / total_exposure * 100

        vendor = row.get('Vendor', 'Unknown Vendor')
        material = row.get('Short Text', 'Unknown Material')
        plant = row.get('Plant', 'Unknown Plant')
        po = f"{row['PO Number']} / {row['PO Item']}"

        reasons = []
        rec_action = ""

        if row['status'] == 'OVER INVOICED':
            reasons.append(f"Excess invoicing: Invoice receipt exceeds Goods receipt by {abs(row['open_qty']):.1f} units")
            rec_action = "Block payment immediately, investigate duplicate invoicing or billing error."
        elif row['status'] == 'IR ONLY':
            reasons.append("Three-way match failure: Invoice receipt posted without goods receipt")
            rec_action = "Block payment until goods receipt is verified and posted."
        elif row['status'] == 'GR ONLY' and row['days_open'] and row['days_open'] > 90:
            reasons.append(f"Aged Goods Receipt: Goods received but no invoice posted for {row['days_open']} days")
            rec_action = "Contact supplier to request invoice or clear accrual balance."

        if abs(row['price_var_pct']) > 10:
            reasons.append(f"Price compliance variance: {row['price_var_pct']:.1f}% deviation from PO net price")
            rec_action = "Verify purchase agreement, issue supplier debit note for excess amount."

        if not reasons:
            reasons.append(f"Reconciliation discrepancy with status {row['status']} and exposure of INR {line_exposure:,.2f}")
            rec_action = "Review ledger entries and align with supplier statement."

        flags.append({
            'po': po,
            'vendor': str(vendor),
            'material': str(material),
            'plant': str(plant),
            'risk_level': row['risk_level'],
            'risk_score': int(row['risk_score']),
            'risk_category': row['status'],
            'business_rule_triggered': "; ".join(reasons),
            'threshold': "Various rule boundaries (>60d, >5% variance, >0 tolerance for IR-only/over-invoice)",
            'actual_value': f"Exposure: INR {line_exposure:,.2f}, Days open: {row['days_open']}, Price var: {row['price_var_pct']:.1f}%",
            'source_dataset': "GRIR, ME2N, EKKO",
            'recommended_action': rec_action,
        })

    return flags


def generate_deterministic_insights(df, kpis, total_open_exposure):
    insights = []

    vendors = df.groupby('Vendor')['open_val'].agg(lambda x: x.abs().sum()).reset_index()
    if not vendors.empty and total_open_exposure > 0:
        top_vendor = vendors.sort_values('open_val', ascending=False).iloc[0]
        top_vendor_name = top_vendor['Vendor']
        top_vendor_exp = top_vendor['open_val']
        pct = top_vendor_exp / total_open_exposure * 100

        if pct > 20:
            insights.append({
                'id': 'vendor_concentration',
                'title': 'High Vendor Exposure Concentration',
                'severity': 'warning' if pct < 30 else 'error',
                'icon': 'TrendingUp',
                'source_dataset': 'ME2N, EKKO, GRIR',
                'formula_used': 'Vendor Exposure / Total Exposure * 100',
                'threshold_used': '> 20% total exposure',
                'actual_value': f"{pct:.1f}% (INR {top_vendor_exp/1e7:.2f} Cr)",
                'message': f"Vendor '{top_vendor_name}' contributes {pct:.1f}% of total exposure.",
                'metric': f"{pct:.1f}%",
                'business_impact': "Concentration of outstanding balances on a single vendor increases supplier risk and could cause settlement disputes.",
            })

    recon_rate = kpis.get('reconciliation_rate', 0.0)
    if recon_rate < 90:
        insights.append({
            'id': 'reconciliation_rate',
            'title': 'Elevated Reconciliation Discrepancy Rate',
            'severity': 'error' if recon_rate < 80 else 'warning',
            'icon': 'PieChart',
            'source_dataset': 'GRIR, ME2N',
            'formula_used': 'Matched PO Lines / Total PO Lines * 100',
            'threshold_used': '< 90% match rate',
            'actual_value': f"{recon_rate:.1f}%",
            'message': f"Only {recon_rate:.1f}% of PO items are fully reconciled.",
            'metric': f"{recon_rate:.1f}%",
            'business_impact': "Low reconciliation rates signal systemic goods receipt delays or invoice receipt errors, extending month-end closing cycles.",
        })

    over_inv_val = kpis.get('over_invoice_val', 0.0)
    if over_inv_val > 10000:
        insights.append({
            'id': 'over_invoicing',
            'title': 'Over-Invoice Payment Leakage Risk',
            'severity': 'error' if over_inv_val > 1000000 else 'warning',
            'icon': 'Trash2',
            'source_dataset': 'GRIR, ME2N',
            'formula_used': 'SUM(ABS(Open Value)) for OVER INVOICED items',
            'threshold_used': '> INR 10,000 leakage limit',
            'actual_value': f"INR {over_inv_val:,.2f}",
            'message': f"Over-invoiced items carrying excess value of INR {over_inv_val:,.2f} detected.",
            'metric': f"INR {over_inv_val/1e5:.1f}L",
            'business_impact': "Invoices approved and paid for quantities exceeding goods receipts present direct cash leakage and internal control failures.",
        })

    old_items = df[df['aging_bucket'].isin(['91-180', '180+']) & (~df['reconciled'])]
    old_exp = old_items['open_val'].abs().sum()
    old_pct = old_exp / total_open_exposure * 100 if total_open_exposure > 0 else 0
    if old_pct > 10:
        insights.append({
            'id': 'aging_exposure',
            'title': 'Significant Aged Open Reconciliation Balances',
            'severity': 'warning' if old_pct < 20 else 'error',
            'icon': 'Clock',
            'source_dataset': 'GRIR',
            'formula_used': 'SUM(Open Value) for items aged > 90 days / Total Exposure * 100',
            'threshold_used': '> 10% of total exposure',
            'actual_value': f"{old_pct:.1f}% (INR {old_exp/1e7:.2f} Cr)",
            'message': f"Balances aged >90 days contribute {old_pct:.1f}% of total open exposure.",
            'metric': f"{old_pct:.1f}%",
            'business_impact': "Long-outstanding GR/IR balances can lead to auditor exceptions and require month-end balance sheet write-offs.",
        })

    return insights


def build_vendor_insights(df):
    total_open = df['open_val'].sum()
    top_vendors = df.groupby('Vendor')['open_val'].sum().abs().nlargest(30).index
    df_top = df[df['Vendor'].isin(top_vendors)]

    vendors = []
    for vendor, vdf in df_top.groupby('Vendor'):
        if not vendor or str(vendor) in ('nan', '', 'None', 'NaN'):
            continue
        v_open = vdf['open_val'].sum()
        v_gr = vdf['net_gr_val'].sum()
        v_ir = vdf['net_ir_val'].sum()
        exc = int((vdf['risk_level'].isin(['CRITICAL', 'HIGH'])).sum())
        top_status = vdf['status'].mode().iloc[0] if len(vdf) > 0 else ''
        avg_rev = float(vdf['reversal_pct'].mean())
        avg_days = float(vdf['days_open'].dropna().mean()) if vdf['days_open'].dropna().any() else 0

        vendors.append({
            'vendor': str(vendor)[:70],
            'po_count': int(vdf['PO Number'].nunique()),
            'item_count': int(len(vdf)),
            'gr_value': round(float(v_gr), 2),
            'ir_value': round(float(v_ir), 2),
            'open_value': round(float(v_open), 2),
            'open_pct_total': round(float(v_open / total_open * 100 if total_open else 0), 1),
            'avg_reversal_pct': round(avg_rev, 1),
            'avg_days_open': round(avg_days, 0),
            'exception_count': exc,
            'dominant_status': str(top_status),
            'risk_level': str(vdf['risk_level'].mode().iloc[0]) if len(vdf) else 'LOW',
            'pending_invoice': round(float(vdf[vdf['status'].isin(['GR ONLY', 'PARTIALLY INVOICED'])]['open_val'].sum()), 2),
            'over_invoiced': round(float(vdf[vdf['status'] == 'OVER INVOICED']['open_val'].abs().sum()), 2),
        })
    return sorted(vendors, key=lambda x: abs(x['open_value']), reverse=True)[:30]


def build_material_insights(df):
    top_mats = df.groupby('material_key')['open_val'].sum().abs().nlargest(25).index
    df_top = df[df['material_key'].isin(top_mats)]

    mats = []
    for mat, mdf in df_top.groupby('material_key'):
        if not mat or str(mat) in ('nan', '', 'None', 'NaN'):
            continue
        label = mdf['material_label'].iloc[0] if 'material_label' in mdf.columns else str(mat)
        mats.append({
            'material': str(label)[:80],
            'material_key': str(mat)[:40],
            'item_count': int(len(mdf)),
            'open_value': round(float(mdf['open_val'].sum()), 2),
            'gr_value': round(float(mdf['net_gr_val'].sum()), 2),
            'ir_value': round(float(mdf['net_ir_val'].sum()), 2),
            'status_dist': {k: int(v) for k, v in mdf['status'].value_counts().to_dict().items()},
        })
    return sorted(mats, key=lambda x: abs(x['open_value']), reverse=True)[:25]


def build_plant_insights(df):
    total_open = df['open_val'].sum()
    top_plants = df.groupby('Plant')['open_val'].sum().abs().nlargest(10).index
    df_top = df[df['Plant'].isin(top_plants)]

    plants = []
    for plant, pdf in df_top.groupby('Plant'):
        if not plant or str(plant) in ('nan', '', 'None', 'NaN'):
            continue
        p_open = pdf['open_val'].sum()
        p_gr = pdf['net_gr_val'].sum()
        p_ir = pdf['net_ir_val'].sum()
        recon_r = (pdf['status'] == 'FULLY RECONCILED').sum() / len(pdf) * 100 if len(pdf) else 0
        exc_rate = (pdf['risk_level'].isin(['CRITICAL', 'HIGH'])).sum() / len(pdf) * 100 if len(pdf) else 0
        plants.append({
            'plant': str(plant),
            'item_count': int(len(pdf)),
            'open_value': round(float(p_open), 2),
            'gr_value': round(float(p_gr), 2),
            'ir_value': round(float(p_ir), 2),
            'open_pct_total': round(float(p_open / total_open * 100 if total_open else 0), 1),
            'reconciliation_rate': round(float(recon_r), 1),
            'exception_rate': round(float(exc_rate), 1),
            'critical_count': int((pdf['risk_level'] == 'CRITICAL').sum()),
        })
    return sorted(plants, key=lambda x: abs(x['open_value']), reverse=True)


def build_price_variance(df):
    pv = df[abs(df['price_var_pct']) > 5].copy()
    pv = pv.sort_values('price_var_pct', key=abs, ascending=False)
    result = []
    for _, row in pv.head(25).iterrows():
        result.append({
            'po_number': str(row['PO Number']),
            'po_item': str(row['PO Item']),
            'vendor': str(row['Vendor'])[:60],
            'material': str(row['Short Text'])[:60],
            'po_price': round(float(row['Net Price']), 2),
            'ir_value': round(float(row['net_ir_val']), 2),
            'gr_value': round(float(row['net_gr_val']), 2),
            'variance_pct': round(float(row['price_var_pct']), 2),
            'variance_abs': round(float(row['price_var_abs']), 2),
            'risk_level': 'HIGH' if abs(row['price_var_pct']) > 15 else 'MEDIUM',
        })
    return result


def build_reversal_analysis(df):
    rev = df[df['reversal_pct'] > 0].sort_values('reversal_pct', ascending=False)
    result = []
    for _, row in rev.head(25).iterrows():
        result.append({
            'po_number': str(row['PO Number']),
            'po_item': str(row['PO Item']),
            'vendor': str(row['Vendor'])[:60],
            'material': str(row['Short Text'])[:60],
            'ir_qty': round(float(row['net_ir_qty']), 2),
            'reversal_qty': round(float(row['ir_reversal_qty']), 2),
            'reversal_val': round(float(row['ir_reversal_val']), 2),
            'reversal_pct': round(float(row['reversal_pct']), 1),
            'open_val': round(float(row['open_val']), 2),
            'status': str(row['status']),
        })
    return result


def build_exceptions(df):
    exc_df = df[~df['reconciled'] & (df['status'] != 'FULLY REVERSED')].copy()
    exc_df = exc_df.sort_values(['risk_score', 'open_val'], ascending=[False, True]).head(30)

    result = []
    for _, row in exc_df.iterrows():
        result.append({
            'po_number': str(row['PO Number']),
            'po_item': str(row['PO Item']),
            'vendor': str(row['Vendor'])[:60],
            'material': str(row['Short Text'])[:60],
            'plant': str(row['Plant']),
            'status': str(row['status']),
            'open_val': round(float(row['open_val']), 2),
            'open_qty': round(float(row['open_qty']), 2),
            'net_gr_val': round(float(row['net_gr_val']), 2),
            'net_ir_val': round(float(row['net_ir_val']), 2),
            'risk_score': int(row['risk_score']),
            'risk_level': str(row['risk_level']),
            'aging_bucket': str(row['aging_bucket']),
            'inv_completion_pct': round(float(row['inv_completion_pct']), 1),
            'reversal_pct': round(float(row['reversal_pct']), 1),
            'posting_date': row['posting_date'].strftime('%Y-%m-%d') if pd.notna(row['posting_date']) else '',
            'days_open': int(row['days_open']) if pd.notna(row['days_open']) else 0,
            'explanation': explain(row),
        })
    return result


def build_recommended_actions(df, kpis):
    actions = []

    gr_only = df[df['status'] == 'GR ONLY']
    if len(gr_only):
        actions.append({
            'priority': 'HIGH',
            'category': 'Pending Invoice Follow-up',
            'action': f"Contact vendors for {len(gr_only)} PO items where goods were received but no invoice posted. Total exposure: INR {gr_only['open_val'].sum():,.0f}.",
            'owner': 'Accounts Payable / Procurement',
            'impact': 'Reduce accrual liability understatement; improve AP closing accuracy.',
            'timeline': 'Within 7 business days',
        })

    ir_only = df[df['status'] == 'IR ONLY']
    if len(ir_only):
        actions.append({
            'priority': 'CRITICAL',
            'category': 'Invoice Without GR — Control Violation',
            'action': f"Investigate {len(ir_only)} items invoiced without goods receipt. Block payment on all. Total: INR {ir_only['net_ir_val'].sum():,.0f}.",
            'owner': 'Internal Audit / Warehouse / AP',
            'impact': 'Prevent fraudulent payments; restore 3-way match controls.',
            'timeline': 'Immediate — escalate to Finance Controller',
        })

    over_inv = df[df['status'] == 'OVER INVOICED']
    if len(over_inv):
        actions.append({
            'priority': 'CRITICAL',
            'category': 'Over-Invoice Investigation',
            'action': f"Review {len(over_inv)} over-invoiced items. Issue vendor debit notes or block duplicate invoices. Excess: INR {over_inv['open_val'].abs().sum():,.0f}.",
            'owner': 'Finance Controller / Internal Audit',
            'impact': 'Prevent overpayment; recover excess invoice amounts.',
            'timeline': 'Within 3 business days',
        })

    old_items = df[df['aging_bucket'].isin(['91-180', '180+']) & (~df['reconciled']) & (df['open_val'].abs() > 1000)]
    if len(old_items):
        actions.append({
            'priority': 'HIGH',
            'category': 'Aging GR/IR Clearance',
            'action': f"Clear {len(old_items)} items aged >90 days. Total value: INR {old_items['open_val'].abs().sum():,.0f}. Write off irrecoverable balances with management approval.",
            'owner': 'Finance Controller',
            'impact': 'Cleanse BS; reduce audit risk; improve GR/IR account accuracy.',
            'timeline': 'Before period close',
        })

    return actions


def build_executive_summary(df, kpis, analysis_date):
    open_val = kpis['total_open_value']
    open_cr = abs(open_val) / 1e7
    total_items = kpis['total_po_items']
    open_items = kpis['open_item_count']
    recon_rate = kpis['reconciliation_rate']
    crit = kpis['critical_items']

    gr_only_pct = (df[df['status'] == 'GR ONLY']['open_val'].sum() / open_val * 100) if open_val else 0
    partial_pct = (df[df['status'] == 'PARTIALLY INVOICED']['open_val'].sum() / open_val * 100) if open_val else 0
    over_inv_pct = (df[df['status'] == 'OVER INVOICED']['open_val'].abs().sum() / abs(open_val) * 100) if open_val else 0

    risk_flags = []
    if (df['status'] == 'OVER INVOICED').sum() > 0:
        risk_flags.append(f"{(df['status'] == 'OVER INVOICED').sum()} over-invoiced items detected — potential overpayment or fraud risk")
    if (df['status'] == 'IR ONLY').sum() > 0:
        risk_flags.append(f"{(df['status'] == 'IR ONLY').sum()} invoices received without goods receipt — 3-way match control failure")
    if (df['aging_bucket'].isin(['91-180', '180+']) & (~df['reconciled'])).sum() > 0:
        old_val = df[df['aging_bucket'].isin(['91-180', '180+']) & (~df['reconciled'])]['open_val'].abs().sum()
        risk_flags.append(f"INR {old_val/1e7:.2f} Cr in items aged >90 days — overdue for clearance")
    if crit > 0:
        risk_flags.append(f"{crit} PO items classified as CRITICAL risk requiring immediate action")

    return {
        'headline': f"INR {open_cr:.2f} Cr of GRIR exposure unreconciled across {open_items:,} PO items as of {analysis_date.strftime('%d %B %Y')}",
        'detail': (
            f"Out of {total_items:,} PO line items analyzed, {open_items:,} ({100-recon_rate:.0f}%) "
            f"carry unresolved GR/IR balances. {abs(gr_only_pct):.0f}% of open exposure relates to "
            f"goods received without invoices (accrual risk), {abs(partial_pct):.0f}% to partially invoiced "
            f"deliveries, and {abs(over_inv_pct):.0f}% to potential over-invoicing. "
            f"{crit} PO items are CRITICAL and require immediate escalation."
        ),
        'risk_flags': risk_flags,
        'key_metrics': {
            'open_value_cr': round(open_cr, 2),
            'reconciliation_pct': round(recon_rate, 1),
            'critical_items': crit,
            'unique_vendors': kpis['unique_vendors'],
            'total_pos': kpis['unique_pos'],
        },
    }


def build_financial_impact(df, kpis):
    open_val = kpis['total_open_value']
    pending = kpis['pending_invoice_val']
    over_inv = kpis['over_invoice_val']
    ir_only = kpis['ir_only_val']

    return [
        {
            'area': 'Accounts Payable Liability',
            'impact_val': round(float(abs(open_val)), 2),
            'impact_cr': round(float(abs(open_val)) / 1e7, 3),
            'description': f"INR {abs(open_val)/1e7:.2f} Cr in uncleared GRIR balance may misstate Accounts Payable. Accruals required before close.",
            'action': 'Book month-end accruals for all open GR-only items.',
            'severity': 'HIGH',
        },
        {
            'area': 'Accrued Liabilities',
            'impact_val': round(float(abs(pending)), 2),
            'impact_cr': round(float(abs(pending)) / 1e7, 3),
            'description': f"INR {abs(pending)/1e7:.2f} Cr of goods received but not invoiced requires accrual. Omitting this understates liabilities.",
            'action': 'Pass accrual journal: Dr. GR/IR Expense Cr. Accrued Liabilities.',
            'severity': 'HIGH',
        },
        {
            'area': 'Over-Payment Risk',
            'impact_val': round(float(over_inv), 2),
            'impact_cr': round(float(over_inv) / 1e7, 3),
            'description': f"INR {over_inv/1e7:.2f} Cr at risk of over-payment due to invoice quantities exceeding GR. Block all over-invoiced items.",
            'action': 'Block payment run for all OVER INVOICED items; investigate duplicates.',
            'severity': 'CRITICAL',
        },
        {
            'area': 'Control Violation Exposure',
            'impact_val': round(float(abs(ir_only)), 2),
            'impact_cr': round(float(abs(ir_only)) / 1e7, 3),
            'description': f"INR {abs(ir_only)/1e7:.2f} Cr of invoices without goods receipts indicates process breakdown. Audit trail required.",
            'action': 'Obtain GR confirmation or reject invoice. Escalate to Internal Audit.',
            'severity': 'CRITICAL',
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class GRIRAnalyticsService:
    def __init__(self):
        self._grir = None
        self._ekko = None
        self._me2n = None
        self._df = None
        self._metadata = None
        self._output = None
        self._rules = _load_rules()
        self._analysis_date = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

    def has_data(self):
        return self._df is not None and self._output is not None

    def load_from_disk(self, project_dir=None):
        """Load pre-existing CSVs from project root on startup."""
        project_dir = Path(project_dir or PROJECT_DIR)
        grir_path = project_dir / "grir.csv"
        ekko_path = project_dir / "EKKO.csv"
        me2n_path = project_dir / "me2n.csv"

        try:
            print("\n[GRIR Service] Checking for pre-existing CSV files from project root...")
            loaded_any = False

            if ekko_path.exists():
                ekko = pd.read_csv(ekko_path, low_memory=False)
                self._ekko = map_columns(ekko, EKKO_MAP)
                print("  [GRIR Service] Loaded EKKO.csv from disk.")
                loaded_any = True

            if me2n_path.exists():
                me2n = pd.read_csv(me2n_path, low_memory=False)
                self._me2n = map_columns(me2n, ME2N_MAP)
                print("  [GRIR Service] Loaded me2n.csv from disk.")
                loaded_any = True

            if grir_path.exists():
                grir = pd.read_csv(grir_path, low_memory=False)
                self._grir = map_columns(grir, GRIR_MAP)
                print("  [GRIR Service] Loaded grir.csv from disk.")
                loaded_any = True

            if not loaded_any:
                print("  [GRIR Service] Pre-loaded CSVs not found in project root. Waiting for upload.")
                return False

            all_ready = all(d is not None for d in [self._grir, self._ekko, self._me2n])
            if all_ready:
                self._run_full_pipeline(self._grir, self._ekko, self._me2n, "grir.csv (Pre-loaded)")
                print(f"  [GRIR Service] Pre-loaded data ready: {len(self._df):,} PO line items")
                return True
            else:
                missing = []
                if self._grir is None: missing.append('GRIR')
                if self._ekko is None: missing.append('EKKO')
                if self._me2n is None: missing.append('ME2N')
                print(f"  [GRIR Service] Loaded partial data. Waiting for remaining datasets: {', '.join(missing)}")
                return False

        except Exception as e:
            print(f"  [GRIR Service] Error loading pre-existing CSVs: {e}")
            traceback.print_exc()
            return False

    def upload_df(self, df, filename):
        """Process a dataframe directly from memory instead of a file stream."""
        if df.empty:
            raise ValueError("The uploaded dataframe is empty.")
            
        file_type = detect_sap_file_type(df)
        if not file_type:
            raise ValueError("Unable to auto-detect SAP file type from dataframe.")

        print(f"[GRIR Service] Detected SAP file type from df: {file_type}")

        if file_type == 'GRIR':
            df = align_dataframe_columns(df, GRIR_MAP, 'GRIR')
            self._grir = clean_grir(df)
        elif file_type == 'EKKO':
            df = align_dataframe_columns(df, EKKO_MAP, 'EKKO')
            self._ekko = df
        elif file_type == 'ME2N':
            df = align_dataframe_columns(df, ME2N_MAP, 'ME2N')
            self._me2n = df

        record_count = len(df)
        po_count = int(df['PO Number'].nunique()) if 'PO Number' in df.columns else int(df['Purchasing Document'].nunique()) if 'Purchasing Document' in df.columns else 0

        all_ready = all(d is not None for d in [self._grir, self._ekko, self._me2n])
        if all_ready:
            print("[GRIR Service] All 3 datasets available. Running full reconciliation pipeline...")
            self._run_full_pipeline(self._grir, self._ekko, self._me2n, filename)
        else:
            missing = []
            if self._grir is None: missing.append('GRIR')
            if self._ekko is None: missing.append('EKKO')
            if self._me2n is None: missing.append('ME2N')
            print(f"[GRIR Service] Waiting for remaining datasets: {', '.join(missing)}")

        self._metadata = {
            'file_name': filename,
            'record_count': record_count,
            'po_count': po_count,
            'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M')
        }

        return {
            'success': True,
            'file_name': filename,
            'record_count': record_count,
            'po_count': po_count,
            'upload_timestamp': self._analysis_date.strftime('%Y-%m-%d %H:%M:%S'),
            'metadata': self._metadata,
            'datasets_ready': all_ready,
            'missing_datasets': missing if not all_ready else [],
        }

    def upload(self, file_storage, filename=None):
        if filename is None:
            filename = getattr(file_storage, 'filename', 'unknown.csv')

        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'csv'

        if ext == 'csv':
            df = pd.read_csv(file_storage, low_memory=False)
        else:
            df = pd.read_excel(file_storage)

        if df.empty:
            raise ValueError("The uploaded file is empty.")
            raise ValueError("The uploaded dataframe is empty.")

        file_type = detect_sap_file_type(df)
        if not file_type:
            raise ValueError("Unable to auto-detect SAP file type. Check file headers.")

        print(f"[GRIR Service] Detected SAP file type from df: {file_type}")

        if file_type == 'GRIR':
            df = align_dataframe_columns(df, GRIR_ALIASES, 'GRIR')
            df = map_columns(df, GRIR_MAP)
            self._grir = df
        elif file_type == 'EKKO':
            df = align_dataframe_columns(df, EKKO_ALIASES_UPLOAD, 'EKKO')
            df = map_columns(df, EKKO_MAP)
            self._ekko = df
        elif file_type == 'ME2N':
            df = align_dataframe_columns(df, ME2N_ALIASES_UPLOAD, 'ME2N')
            df = map_columns(df, ME2N_MAP)
            self._me2n = df

        record_count = len(df)
        po_count = int(df['PO Number'].nunique()) if 'PO Number' in df.columns else int(df['Purchasing Document'].nunique()) if 'Purchasing Document' in df.columns else 0

        all_ready = all(d is not None for d in [self._grir, self._ekko, self._me2n])
        if all_ready:
            print("[GRIR Service] All 3 datasets available. Running full reconciliation pipeline...")
            self._run_full_pipeline(self._grir, self._ekko, self._me2n, filename)
        else:
            missing = []
            if self._grir is None:
                missing.append('GRIR')
            if self._ekko is None:
                missing.append('EKKO')
            if self._me2n is None:
                missing.append('ME2N')
            print(f"[GRIR Service] Waiting for remaining datasets: {', '.join(missing)}")

        self._metadata = {
            'file_name': filename,
            'upload_date': self._analysis_date.strftime('%Y-%m-%d %H:%M'),
            'record_count': record_count,
            'po_count': po_count,
            'vendor_count': int(self._df['Vendor'].nunique()) if self._df is not None else 0,
            'material_count': int(self._df['material_key'].nunique()) if self._df is not None else 0,
            'plant_count': int(self._df['Plant'].nunique()) if self._df is not None else 0,
        }

        return {
            'success': True,
            'file_name': filename,
            'record_count': record_count,
            'po_count': po_count,
            'upload_timestamp': self._analysis_date.strftime('%Y-%m-%d %H:%M:%S'),
            'metadata': self._metadata,
            'datasets_ready': all_ready,
            'missing_datasets': missing if not all_ready else [],
        }

    def _run_full_pipeline(self, grir, ekko, me2n, filename):
        """Run the complete reconciliation and analytics pipeline."""
        print("\n[GRIR Service] [1/3] Cleaning & standardising data...")
        grir = clean_grir(grir)
        me2n = clean_me2n(me2n)
        ekko = clean_ekko(ekko)

        print("[GRIR Service] [2/3] Running reconciliation engine...")
        df = reconcile(grir, me2n, ekko, self._analysis_date)

        print("[GRIR Service] [3/3] Computing analytics...")
        total_open_exposure = df['exposure_val'].sum()

        kpis = build_kpis(df, ekko)
        aging = build_aging(df)
        vendors = build_vendor_insights(df)
        materials = build_material_insights(df)
        plants = build_plant_insights(df)
        price_var = build_price_variance(df)
        reversals = build_reversal_analysis(df)
        exceptions = build_exceptions(df)
        actions = build_recommended_actions(df, kpis)
        exec_sum = build_executive_summary(df, kpis, self._analysis_date)
        fin_imp = build_financial_impact(df, kpis)

        vendor_risk = calculate_group_risk_scores(df, 'Vendor', total_open_exposure)
        material_risk = calculate_group_risk_scores(df, 'Short Text', total_open_exposure)
        plant_risk = calculate_group_risk_scores(df, 'Plant', total_open_exposure)
        rule_based_risks = generate_risk_flags(df, total_open_exposure)
        deterministic_insights = generate_deterministic_insights(df, kpis, total_open_exposure)

        spend_by_vendor = df.groupby('Vendor')['Net_Order_Value_INR'].sum().reset_index().rename(columns={'Vendor': 'vendor', 'Net_Order_Value_INR': 'spend'}).sort_values('spend', ascending=False)
        top_supplier = spend_by_vendor.iloc[0]['vendor'] if len(spend_by_vendor) else 'N/A'
        spend_by_matgrp = df.groupby('Material Group')['Net_Order_Value_INR'].sum().reset_index().rename(columns={'Material Group': 'material_group', 'Net_Order_Value_INR': 'spend'}).sort_values('spend', ascending=False)
        top_material_group = spend_by_matgrp.iloc[0]['material_group'] if len(spend_by_matgrp) else 'N/A'
        spend_by_purchgrp = df.groupby('Purchasing Group')['Net_Order_Value_INR'].sum().reset_index().rename(columns={'Purchasing Group': 'purchasing_group', 'Net_Order_Value_INR': 'spend'}).sort_values('spend', ascending=False)
        top_purchasing_group = spend_by_purchgrp.iloc[0]['purchasing_group'] if len(spend_by_purchgrp) else 'N/A'

        kpis.update({
            'total_procurement_spend_inr': round(float(df['Net_Order_Value_INR'].sum()), 2),
            'top_supplier': top_supplier,
            'top_material_group': top_material_group,
            'top_purchasing_group': top_purchasing_group,
            'total_purchasing_groups': int(df['Purchasing Group'].nunique()),
            'total_plants': int(df['Plant'].nunique()),
        })

        all_items_cols = [
            'PO Number', 'PO Item', 'Vendor', 'Short Text', 'Plant', 'Material Group',
            'net_gr_qty', 'net_gr_val', 'net_ir_qty', 'net_ir_val',
            'open_qty', 'open_val', 'status', 'risk_level', 'risk_score',
            'aging_bucket', 'inv_completion_pct', 'reversal_pct',
            'price_var_pct', 'price_var_abs', 'days_open', 'posting_date', 'Currency',
        ]
        existing = [c for c in all_items_cols if c in df.columns]
        all_items = df[existing].copy()
        all_items['posting_date'] = all_items['posting_date'].apply(
            lambda d: d.strftime('%Y-%m-%d') if pd.notna(d) else '')
        all_items = all_items.fillna('')
        all_items_list = all_items.to_dict('records')

        self._output = {
            'metadata': {
                'generated_at': self._analysis_date.strftime('%Y-%m-%d %H:%M'),
                'company': 'Syrma SGS Technology Limited',
                'plant': '1103',
                'currency': 'INR',
                'source_files': ['GRIR.csv', 'EKKO.csv', 'ME2N.csv'],
                'grir_row_count': len(grir),
                'me2n_row_count': len(me2n),
                'uploaded_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'record_count': len(grir),
                'po_count': kpis['unique_pos'],
            },
            'kpis': kpis,
            'reconciliation': {
                'matched_lines': int(df['reconciled'].sum()),
                'unmatched_lines': int((~df['reconciled']).sum()),
                'reconciliation_rate': kpis['reconciliation_rate'],
            },
            'exposure': {
                'total_open_exposure': round(float(total_open_exposure), 2),
                'exposure_by_vendor': df.groupby('Vendor')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Vendor': 'vendor', 'open_val': 'open_exposure'}).sort_values('open_exposure', ascending=False).to_dict('records'),
                'exposure_by_material': df.groupby('Short Text')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Short Text': 'material', 'open_val': 'open_exposure'}).sort_values('open_exposure', ascending=False).to_dict('records'),
                'exposure_by_plant': df.groupby('Plant')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Plant': 'plant', 'open_val': 'open_exposure'}).sort_values('open_exposure', ascending=False).to_dict('records'),
            },
            'vendor_analytics': {
                'top_vendors_by_spend': spend_by_vendor.head(15).to_dict('records'),
                'top_vendors_by_exposure': df.groupby('Vendor')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Vendor': 'vendor', 'open_val': 'exposure'}).sort_values('exposure', ascending=False).head(15).to_dict('records'),
                'top_vendors_by_aging': df.groupby('Vendor')['days_open'].mean().reset_index().rename(columns={'Vendor': 'vendor', 'days_open': 'avg_days_open'}).fillna(0).sort_values('avg_days_open', ascending=False).head(15).to_dict('records'),
                'vendor_risk_score': vendor_risk,
            },
            'material_analytics': {
                'material_spend': df.groupby('Short Text')['Net_Order_Value_INR'].sum().reset_index().rename(columns={'Short Text': 'material', 'Net_Order_Value_INR': 'spend'}).sort_values('spend', ascending=False).to_dict('records'),
                'material_risk_score': material_risk,
            },
            'aging': {
                'buckets': aging,
                'vendor_aging': df.groupby(['Vendor', 'aging_bucket'])['open_val'].sum().unstack().fillna(0).reset_index().rename(columns={'Vendor': 'vendor'}).to_dict('records') if not df.empty else [],
                'plant_aging': df.groupby(['Plant', 'aging_bucket'])['open_val'].sum().unstack().fillna(0).reset_index().rename(columns={'Plant': 'plant'}).to_dict('records') if not df.empty else [],
            },
            'variance': {
                'price_variance': price_var,
                'variance_pct': round(float(df['price_var_pct'].abs().mean()), 2) if len(df) else 0.0,
            },
            'risks': {
                'rule_based_risks': rule_based_risks,
            },
            'executive_summary': exec_sum,
            'charts': {
                'risk_level': kpis.get('risk_distribution', {}),
                'status': kpis.get('status_distribution', {}),
            },
            'vendor_insights': vendors,
            'material_insights': materials,
            'plant_insights': plants,
            'aging_analysis': aging,
            'reversal_analysis': reversals,
            'price_variance_analysis': price_var,
            'financial_impact': fin_imp,
            'top_exceptions': exceptions,
            'recommended_actions': actions,
            'deterministic_insights': deterministic_insights,
            'all_items': all_items_list,
        }

        self._df = df
        print(f"\n[GRIR Service] Pipeline complete:")
        print(f"  Total PO Line Items  : {kpis['total_po_items']:,}")
        print(f"  Reconciliation Rate  : {kpis['reconciliation_rate']}%")
        print(f"  Total Open Value     : {kpis['total_open_value']:,.2f}")
        print(f"  Critical Items       : {kpis['critical_items']}")
        print(f"  Unique Vendors       : {kpis['unique_vendors']}")

    def get_metadata(self):
        if self._metadata:
            return self._metadata
        if self._output:
            kpis = self._output.get('kpis', {})
            meta = self._output.get('metadata', {})
            return {
                'file_name': 'grir.csv (Pre-loaded)',
                'upload_date': 'N/A',
                'record_count': meta.get('grir_row_count', 0),
                'po_count': kpis.get('unique_pos', 0),
                'vendor_count': kpis.get('unique_vendors', 0),
                'material_count': kpis.get('total_materials', 0),
            }
        return {
            'file_name': 'None',
            'upload_date': 'N/A',
            'record_count': 0,
            'po_count': 0,
            'vendor_count': 0,
            'material_count': 0,
        }

    def get_dashboard(self):
        if not self._output:
            return None
        output = {k: v for k, v in self._output.items() if k != 'all_items'}
        return output

    def get_items(self, page=1, limit=50, search='', status='', risk_level='',
                  plant='', sortBy='risk_score', sortOrder='desc'):
        if not self._output:
            return {'items': [], 'total': 0, 'page': 1, 'pages': 1, 'limit': limit}

        all_items = self._output.get('all_items', [])

        filtered = all_items

        if search:
            sl = search.lower()
            filtered = [
                item for item in filtered
                if sl in str(item.get('PO Number', '')).lower()
                or sl in str(item.get('Vendor', '')).lower()
                or sl in str(item.get('Short Text', '')).lower()
            ]

        if status:
            filtered = [item for item in filtered if item.get('status') == status]

        if risk_level:
            filtered = [item for item in filtered if item.get('risk_level') == risk_level]

        if plant:
            filtered = [item for item in filtered if str(item.get('Plant', '')) == plant]

        if sortBy:
            reverse = (sortOrder == 'desc')
            numeric_fields = ['net_gr_qty', 'net_gr_val', 'net_ir_qty', 'net_ir_val',
                              'open_qty', 'open_val', 'risk_score', 'days_open',
                              'inv_completion_pct', 'reversal_pct', 'price_var_pct', 'price_var_abs']

            def get_sort_key(item):
                val = item.get(sortBy)
                if val is None:
                    return 0 if sortBy in numeric_fields else ""
                if sortBy in numeric_fields:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return 0.0
                return str(val).lower()

            try:
                filtered = sorted(filtered, key=get_sort_key, reverse=reverse)
            except Exception:
                pass

        total = len(filtered)
        start = (page - 1) * limit
        end = start + limit
        paginated = filtered[start:end]
        pages = math.ceil(total / limit) if limit > 0 else 1

        return {
            'items': paginated,
            'total': total,
            'page': page,
            'pages': pages,
            'limit': limit,
        }

    def get_ai_insights(self):
        if not self._output:
            return None

        exec_sum = self._output.get('executive_summary', {})
        vendor_insights = self._output.get('vendor_insights', [])
        material_insights = self._output.get('material_insights', [])
        plant_insights = self._output.get('plant_insights', [])
        financial_impact = self._output.get('financial_impact', [])
        recommended_actions = self._output.get('recommended_actions', [])
        deterministic_insights = self._output.get('deterministic_insights', [])

        return {
            'headline': exec_sum.get('headline', 'GR/IR Reconciliation Analysis'),
            'executive_summary': exec_sum.get('detail', ''),
            'critical_risks': exec_sum.get('risk_flags', []),
            'vendor_findings': [
                f"{v['vendor']}: Open exposure INR {v['open_value']:,.0f} ({v['open_pct_total']:.1f}% of total). "
                f"Dominant status: {v['dominant_status']}. Avg days open: {v['avg_days_open']:.0f}d."
                for v in vendor_insights[:5]
                if v.get('open_value', 0) != 0
            ],
            'material_findings': [
                f"{m['material']}: Open balance INR {m['open_value']:,.0f} across {m['item_count']} PO items."
                for m in material_insights[:5]
                if m.get('open_value', 0) != 0
            ],
            'plant_findings': [
                f"Plant {p['plant']}: {p['item_count']} items, "
                f"INR {p['open_value']:,.0f} open, reconciliation rate {p['reconciliation_rate']:.1f}%."
                for p in plant_insights[:3]
            ],
            'financial_impact': [
                f"[{fi['severity']}] {fi['area']}: INR {fi['impact_val']:,.0f} ({fi['impact_cr']:.3f} Cr). {fi['description']}"
                for fi in financial_impact
            ],
            'recommended_actions': [
                f"[{a['priority']}] {a['category']} — {a['action']} Owner: {a['owner']}. Timeline: {a['timeline']}."
                for a in recommended_actions
            ],
            'deterministic_insights': deterministic_insights,
            'key_metrics': exec_sum.get('key_metrics', {}),
        }

    def generate_pdf(self):
        """Generate multi-section PDF report from cached analytics data."""
        if not self._output:
            return None

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch

            data = self._output
            kpis = data.get('kpis', {})
            exec_sum = data.get('executive_summary', {})
            aging_data = data.get('aging_analysis', [])
            vendor_list = data.get('vendor_insights', [])[:15]
            material_list = data.get('material_insights', [])[:15]
            plant_list = data.get('plant_insights', [])
            exceptions = data.get('top_exceptions', [])[:20]
            actions = data.get('recommended_actions', [])
            fin_impact = data.get('financial_impact', [])
            price_var = data.get('price_variance_analysis', [])[:15]
            risk_flags = data.get('risks', {}).get('rule_based_risks', [])[:10]
            vendor_risk = data.get('vendor_analytics', {}).get('vendor_risk_score', [])[:10]
            recon_data = data.get('reconciliation', {})
            det_insights = data.get('deterministic_insights', [])

            generated_at = datetime.now().strftime("%d %B %Y at %H:%M IST")

            styles = getSampleStyleSheet()
            INDIGO = colors.HexColor('#4f46e5')
            DARK = colors.HexColor('#1e1b4b')
            SLATE = colors.HexColor('#334155')
            MUTED = colors.HexColor('#64748b')
            HDR_BG = colors.HexColor('#eef2ff')
            ROW_ALT = colors.HexColor('#f8fafc')

            title_style = ParagraphStyle('T', parent=styles['Heading1'], fontSize=20, leading=24,
                textColor=INDIGO, spaceAfter=4)
            sub_style = ParagraphStyle('S', parent=styles['Normal'], fontSize=9, leading=12,
                textColor=MUTED, spaceAfter=14)
            h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, leading=16,
                textColor=DARK, spaceBefore=14, spaceAfter=6)
            h3_style = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=11, leading=13,
                textColor=DARK, spaceBefore=10, spaceAfter=4)
            body_style = ParagraphStyle('B', parent=styles['Normal'], fontSize=9, leading=13,
                textColor=SLATE, spaceAfter=4)
            bold_style = ParagraphStyle('BB', parent=body_style, fontName='Helvetica-Bold')
            bullet_style = ParagraphStyle('BUL', parent=body_style, leftIndent=12)
            warn_style = ParagraphStyle('W', parent=body_style, textColor=colors.HexColor('#b91c1c'))

            def mk_tbl(rows, col_widths, hdr=True):
                t = Table(rows, colWidths=col_widths, repeatRows=1 if hdr else 0)
                style_cmds = [
                    ('BACKGROUND', (0, 0), (-1, 0), HDR_BG),
                    ('TEXTCOLOR', (0, 0), (-1, 0), DARK),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('LEADING', (0, 0), (-1, -1), 11),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ROW_ALT]),
                ]
                t.setStyle(TableStyle(style_cmds))
                return t

            def fmt_inr(val):
                try:
                    v = float(val)
                    if abs(v) >= 1e7:
                        return f"Rs.{v/1e7:.2f} Cr"
                    if abs(v) >= 1e5:
                        return f"Rs.{v/1e5:.2f} L"
                    return f"Rs.{v:,.0f}"
                except Exception:
                    return str(val)

            def p(text, style=None):
                return Paragraph(str(text), style or body_style)

            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                pdf_buffer, pagesize=letter,
                rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40,
            )
            story = []

            story.append(Paragraph("SAP GR/IR Reconciliation Audit Report", title_style))
            story.append(Paragraph(
                f"Generated: {generated_at} | Organisation: Syrma SGS Technology Limited",
                sub_style
            ))
            story.append(HRFlowable(width="100%", thickness=1, color=INDIGO, spaceAfter=12))

            headline = exec_sum.get('headline', 'GR/IR Analysis')
            story.append(Paragraph(headline, bold_style))
            story.append(Spacer(1, 6))
            story.append(Paragraph(exec_sum.get('detail', ''), body_style))
            story.append(Spacer(1, 10))

            for rf in exec_sum.get('risk_flags', []):
                story.append(Paragraph(f"WARNING: {rf}", warn_style))
            story.append(Spacer(1, 14))

            story.append(Paragraph("1. Key Performance Indicators", h2_style))
            status_dist = kpis.get('status_distribution', {})

            kpi_rows = [
                [p("Metric", bold_style), p("Value", bold_style), p("Metric", bold_style), p("Value", bold_style)],
                [p("Total PO Line Items"), p(f"{kpis.get('total_po_items',0):,}"),
                 p("Reconciliation Rate"), p(f"{kpis.get('reconciliation_rate',0):.1f}%")],
                [p("Open Exposure"), p(fmt_inr(kpis.get('total_open_value',0))),
                 p("Pending Invoice Value"), p(fmt_inr(kpis.get('pending_invoice_val',0)))],
                [p("Over-Invoice Risk"), p(fmt_inr(kpis.get('over_invoice_val',0))),
                 p("IR Control Violations"), p(fmt_inr(kpis.get('ir_only_val',0)))],
                [p("Critical Items"), p(str(kpis.get('critical_items',0))),
                 p("High Risk Items"), p(str(kpis.get('high_risk_items',0)))],
                [p("Unique Vendors"), p(str(kpis.get('unique_vendors',0))),
                 p("Unique POs"), p(str(kpis.get('unique_pos',0)))],
            ]
            story.append(mk_tbl(kpi_rows, [160, 110, 160, 110]))
            story.append(PageBreak())

            story.append(Paragraph("2. Reconciliation & GR/IR Exposure Summary", h2_style))
            story.append(Paragraph(
                f"Matched Lines: {recon_data.get('matched_lines',0):,} | "
                f"Unmatched Lines: {recon_data.get('unmatched_lines',0):,} | "
                f"Reconciliation Rate: {recon_data.get('reconciliation_rate',0):.1f}%",
                body_style
            ))
            story.append(Spacer(1, 8))

            story.append(Paragraph("3. Aging Breakdown", h2_style))
            if aging_data:
                ag_rows = [[p("Bucket", bold_style), p("Total Items", bold_style),
                            p("Open Items", bold_style), p("Open Value", bold_style),
                            p("GR Only Val", bold_style), p("IR Only Val", bold_style)]]
                for a in aging_data:
                    ag_rows.append([
                        p(a.get('bucket', '')), p(str(a.get('total_count', 0))),
                        p(str(a.get('open_count', 0))), p(fmt_inr(a.get('open_value', 0))),
                        p(fmt_inr(a.get('gr_only_val', 0))), p(fmt_inr(a.get('ir_only_val', 0))),
                    ])
                story.append(mk_tbl(ag_rows, [70, 65, 65, 90, 90, 90]))
            story.append(PageBreak())

            story.append(Paragraph("4. Top Vendor Exposure Analysis", h2_style))
            if vendor_list:
                v_rows = [[p("Vendor", bold_style), p("POs", bold_style), p("GR Value", bold_style),
                           p("IR Value", bold_style), p("Open Value", bold_style),
                           p("% Total", bold_style), p("Risk", bold_style)]]
                for v in vendor_list:
                    v_rows.append([
                        p(str(v.get('vendor', ''))[:40]), p(str(v.get('po_count', 0))),
                        p(fmt_inr(v.get('gr_value', 0))), p(fmt_inr(v.get('ir_value', 0))),
                        p(fmt_inr(v.get('open_value', 0))), p(f"{v.get('open_pct_total', 0):.1f}%"),
                        p(v.get('risk_level', '')),
                    ])
                story.append(mk_tbl(v_rows, [130, 30, 70, 70, 70, 45, 50]))
            story.append(PageBreak())

            story.append(Paragraph("5. Top Exceptions (Unreconciled Items)", h2_style))
            if exceptions:
                ex_rows = [[p("PO / Item", bold_style), p("Vendor", bold_style),
                            p("Status", bold_style), p("Open Value", bold_style),
                            p("Days Open", bold_style), p("Risk", bold_style)]]
                for ex in exceptions:
                    ex_rows.append([
                        p(f"{ex.get('po_number','')}/{ex.get('po_item','')}"),
                        p(str(ex.get('vendor', ''))[:35]), p(ex.get('status', '')),
                        p(fmt_inr(ex.get('open_val', 0))), p(str(ex.get('days_open', 0))),
                        p(ex.get('risk_level', '')),
                    ])
                story.append(mk_tbl(ex_rows, [80, 120, 100, 80, 60, 60]))
            story.append(Spacer(1, 12))

            if det_insights:
                story.append(Paragraph("6. Audit Findings & Deterministic Insights", h2_style))
                for ins in det_insights:
                    story.append(Paragraph(f"{ins.get('title','')}", bold_style))
                    story.append(Paragraph(
                        f"Source: {ins.get('source_dataset','')} | "
                        f"Formula: {ins.get('formula_used','')} | "
                        f"Threshold: {ins.get('threshold_used','')} | "
                        f"Actual: {ins.get('actual_value','')}",
                        bullet_style
                    ))
                    story.append(Paragraph(f"Impact: {ins.get('business_impact','')}", bullet_style))
                    story.append(Spacer(1, 4))

            story.append(Spacer(1, 10))
            story.append(Paragraph("7. Reconciliation Action Plan", h2_style))
            for act in actions:
                story.append(Paragraph(
                    f"[{act.get('priority','?')}] {act.get('category','')}", bold_style
                ))
                story.append(Paragraph(act.get('action', ''), bullet_style))
                story.append(Paragraph(
                    f"Owner: {act.get('owner','')} | Timeline: {act.get('timeline','')} | Impact: {act.get('impact','')}",
                    bullet_style
                ))
                story.append(Spacer(1, 6))

            story.append(Spacer(1, 20))
            story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED, spaceAfter=6))
            story.append(Paragraph(
                f"Report generated automatically by Syrma SGS Procurement Analytics Platform on {generated_at}. "
                "All figures are calculated deterministically from SAP source files (GRIR, EKKO, ME2N).",
                sub_style
            ))

            doc.build(story)
            pdf_buffer.seek(0)
            return pdf_buffer

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Failed to generate PDF: {str(e)}")
