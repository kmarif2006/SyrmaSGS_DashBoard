"""
SAP GR/IR Reconciliation Analysis Engine
Analyzes GRIR, EKKO, and ME2N SAP exports for Syrma SGS
Author: Antigravity AI
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import json
import numpy as np
from datetime import datetime, date
from pathlib import Path
import warnings
import re
import os
warnings.filterwarnings('ignore')

ANALYSIS_DATE = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
PROJECT_DIR = Path(__file__).resolve().parent
BASE_DIR = Path(os.environ.get("DATA_DIR", PROJECT_DIR / "data" / "uploads" / "current"))
ARTIFACTS_DIR = BASE_DIR / "artifacts"

def _load_rules():
    rules_path = PROJECT_DIR / "config" / "analytics_rules.json"
    if rules_path.exists():
        with open(rules_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

RULES = _load_rules()
RECON_TOLERANCE = RULES.get("reconciliation_tolerance", 0.01)

# Configurable Classification Rules
CLASSIFICATION_RULES = RULES.get("classification_rules", {
    "GR_TRANS_TYPES": ["1"],
    "IR_TRANS_TYPES": ["2"],
    "DEBIT_INDICATORS": ["S"],
    "CREDIT_INDICATORS": ["H"]
})


def material_key(row):
    """Group materials by SAP Material number; fall back to Short Text."""
    mat = str(row.get("Material", "")).strip()
    if mat and mat not in ("nan", "None", ""):
        return mat
    return str(row.get("Short Text", "")).strip()


def material_label(row):
    """Display label: Short Text with Material number when available."""
    mat = str(row.get("Material", "")).strip()
    text = str(row.get("Short Text", "")).strip()
    if mat and mat not in ("nan", "None", "") and text and text not in ("nan", "None"):
        return f"{mat} — {text[:60]}"
    return text or mat or "Unknown"

# Column Aliases Mapping
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
    'Reference Doc': ['reference doc', 'reference_doc', 'xblnr']
}

EKKO_MAP = {
    'Purchasing Document': ['purchasing document', 'purchasing_document', 'purchase order', 'ebeln'],
    'Company Code': ['company code', 'company_code', 'bukrs'],
    'Purchasing Doc. Type': ['purchasing doc. type', 'purchasing_doc_type', 'bsart'],
    'Deletion indicator': ['deletion indicator', 'deletion_indicator', 'loekz'],
    'Currency': ['currency', 'waers'],
    'Exchange Rate': ['exchange rate', 'exchange_rate', 'kuras']
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
    'Delivery date': ['delivery date', 'delivery_date', 'eeind']
}


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


def load_data(data_dir=None):
    data_dir = Path(data_dir or BASE_DIR)
    grir_path = data_dir / "grir.csv"
    ekko_path = data_dir / "EKKO.csv"
    me2n_path = data_dir / "me2n.csv"
    for p, name in [(grir_path, "GRIR"), (ekko_path, "EKKO"), (me2n_path, "ME2N")]:
        if not p.exists():
            raise FileNotFoundError(f"Required SAP file not found: {p} ({name})")

    print("  Loading GRIR.csv ...")
    grir = pd.read_csv(grir_path, low_memory=False)
    grir = map_columns(grir, GRIR_MAP)
    print(f"    -> {len(grir):,} rows")

    print("  Loading EKKO.csv ...")
    ekko = pd.read_csv(ekko_path, low_memory=False)
    ekko = map_columns(ekko, EKKO_MAP)
    print(f"    -> {len(ekko):,} rows")

    print("  Loading ME2N.csv ...")
    me2n = pd.read_csv(me2n_path, low_memory=False)
    me2n = map_columns(me2n, ME2N_MAP)
    print(f"    -> {len(me2n):,} rows")

    return grir, ekko, me2n


def clean_grir(grir):
    grir.columns = grir.columns.str.strip()
    
    # Ensure standard columns exist
    cols_to_ensure = {
        'PO Number': '', 'Doc Type': '', 'PO Item': '0', 'Plant': '',
        'Trans Type': '1', 'Document No': '', 'Doc Item': '', 'Quantity': 0.0,
        'Amt (FC)': 0.0, 'Posting Date': pd.NaT, 'Document Date': pd.NaT,
        'Amt (LC)': 0.0, 'Reference Doc': '', 'Dr/Cr Ind': 'S'
    }
    for col, default in cols_to_ensure.items():
        if col not in grir.columns:
            grir[col] = default

    grir['PO Number']    = grir['PO Number'].astype(str).str.strip()
    grir['PO Item']      = pd.to_numeric(grir['PO Item'], errors='coerce').fillna(0).astype(int).astype(str)
    grir['Trans Type']   = grir['Trans Type'].astype(str).str.strip()
    grir['Dr/Cr Ind']    = grir['Dr/Cr Ind'].astype(str).str.strip()
    grir['Quantity']     = pd.to_numeric(grir['Quantity'], errors='coerce').fillna(0)
    grir['Amt (LC)']     = pd.to_numeric(grir['Amt (LC)'], errors='coerce').fillna(0)
    grir['Amt (FC)']     = pd.to_numeric(grir['Amt (FC)'], errors='coerce').fillna(grir['Amt (LC)'])
    grir['Posting Date'] = pd.to_datetime(grir['Posting Date'], errors='coerce')
    grir['Document Date']= pd.to_datetime(grir['Document Date'], errors='coerce')
    grir['Plant']        = grir['Plant'].astype(str).str.strip()

    # Signed values: S=Debit(+), H=Credit(-)
    grir['Signed Amt'] = np.where(grir['Dr/Cr Ind'] == 'S',  grir['Amt (LC)'], -grir['Amt (LC)'])
    grir['Signed Qty'] = np.where(grir['Dr/Cr Ind'] == 'S',  grir['Quantity'], -grir['Quantity'])
    return grir


def clean_me2n(me2n):
    me2n.columns = me2n.columns.str.strip()
    
    # Ensure required/optional columns exist
    cols_to_ensure = {
        'Purchasing Document': '', 'Item': '10', 'Order Quantity': 0.0,
        'Still to be delivered (qty)': 0.0, 'Net Price': 0.0, 'Net Order Value': 0.0,
        'Still to be invoiced (qty)': 0.0, 'Still to be invoiced (val.)': 0.0,
        'Open value': 0.0, 'Total open value': 0.0, 'Still to be delivered (value)': 0.0,
        'Name of Supplier': '', 'Supplier/Supplying Plant': '', 'Short Text': '',
        'Material': '', 'Plant': '', 'Material Group': '', 'Deletion indicator': '',
        'Document Date': pd.NaT, 'Delivery date': pd.NaT, 'Purchasing Group': '', 'Purch. organization': ''
    }
    for col, default in cols_to_ensure.items():
        if col not in me2n.columns:
            me2n[col] = default

    me2n['Purchasing Document']         = me2n['Purchasing Document'].astype(str).str.strip()
    me2n['Item']                        = pd.to_numeric(me2n['Item'], errors='coerce').fillna(0).astype(int).astype(str)
    me2n['Order Quantity']              = pd.to_numeric(me2n['Order Quantity'], errors='coerce').fillna(0)
    me2n['Still to be delivered (qty)'] = pd.to_numeric(me2n['Still to be delivered (qty)'], errors='coerce').fillna(0)
    me2n['Net Price']                   = pd.to_numeric(me2n['Net Price'], errors='coerce').fillna(0)
    me2n['Net Order Value']             = pd.to_numeric(me2n['Net Order Value'], errors='coerce').fillna(0)
    me2n['Still to be invoiced (qty)']  = pd.to_numeric(me2n['Still to be invoiced (qty)'], errors='coerce').fillna(0)
    me2n['Still to be invoiced (val.)'] = pd.to_numeric(me2n['Still to be invoiced (val.)'], errors='coerce').fillna(0)
    me2n['Open value']                  = pd.to_numeric(me2n['Open value'], errors='coerce').fillna(0)
    me2n['Total open value']            = pd.to_numeric(me2n['Total open value'], errors='coerce').fillna(0)
    me2n['Still to be delivered (value)'] = pd.to_numeric(me2n['Still to be delivered (value)'], errors='coerce').fillna(0)

    if 'Name of Supplier' in me2n.columns and me2n['Name of Supplier'].dropna().any():
        me2n['Vendor'] = me2n['Name of Supplier']
    elif 'Supplier/Supplying Plant' in me2n.columns:
        me2n['Vendor'] = me2n['Supplier/Supplying Plant']
    else:
        me2n['Vendor'] = ''

    # Clean vendor name
    me2n['Vendor'] = me2n['Vendor'].apply(lambda v: re.sub(r'^\d+\s+', '', str(v)).strip() if pd.notna(v) else '')

    me2n['Short Text'] = me2n['Short Text'].astype(str).str.strip()
    me2n['Material']   = me2n['Material'].astype(str).str.strip()
    me2n['Plant']      = me2n['Plant'].astype(str).str.strip()
    me2n['Material Group'] = me2n['Material Group'].astype(str).str.strip()
    me2n['Deletion indicator'] = me2n['Deletion indicator'].astype(str).str.strip()
    me2n['Document Date'] = pd.to_datetime(me2n['Document Date'], errors='coerce')
    me2n['Delivery date'] = pd.to_datetime(me2n['Delivery date'], errors='coerce')
    return me2n


def clean_ekko(ekko, strict=True):
    ekko.columns = ekko.columns.str.strip()
    required = ['Purchasing Document', 'Currency', 'Exchange Rate', 'Company Code', 'Purchasing Doc. Type']
    missing = [c for c in required if c not in ekko.columns]
    if missing and strict:
        raise ValueError(f"EKKO missing required columns: {missing}")
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
    ekko['Company Code']        = ekko['Company Code'].astype(str).str.strip()
    ekko['Currency']            = ekko['Currency'].astype(str).str.strip().fillna('INR')
    ekko['Exchange Rate']       = pd.to_numeric(ekko['Exchange Rate'], errors='coerce').fillna(1.0)
    ekko['Exchange Rate']       = ekko['Exchange Rate'].apply(lambda x: 1.0 if x <= 0 else x)
    return ekko


# ─────────────────────────────────────────────────────────────────────────────
# AGING BUCKETS
# ─────────────────────────────────────────────────────────────────────────────

def aging_bucket(val):
    if pd.isna(val) or val is None:
        return '365+'
    if isinstance(val, (int, float, np.integer, np.floating)):
        days = int(val)
    else:
        # assume it is a Timestamp / datetime
        posting_date = pd.to_datetime(val)
        days = (ANALYSIS_DATE - posting_date).days
    
    if days <= 30:   return '0-30'
    if days <= 60:   return '31-60'
    if days <= 90:   return '61-90'
    if days <= 180:  return '91-180'
    if days <= 365:  return '181-365'
    return '365+'



# ─────────────────────────────────────────────────────────────────────────────
# RECONCILIATION & STATUS CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def classify_status(row):
    gr_qty   = row.get('net_gr_qty', 0)
    ir_qty   = row.get('net_ir_qty', 0)
    gr_val   = row.get('net_gr_val', 0)
    ir_val   = row.get('net_ir_val', 0)
    open_val = row.get('open_val', 0)
    open_qty = row.get('open_qty', 0)
    rev_pct  = row.get('reversal_pct', 0)
    tol = 0.01

    if (abs(gr_qty) < tol and abs(ir_qty) < tol) or (abs(gr_val) < tol and abs(ir_val) < tol) or rev_pct >= 99:
        return 'No Activity'

    if abs(open_val) <= tol:
        return 'Reconciled'

    if open_val > tol:
        return 'IR Pending'

    if open_val < -tol:
        return 'GR Pending'

    return 'No Activity'



# ─────────────────────────────────────────────────────────────────────────────
# RULE-BASED RISK SCORING (No opaque AI scoring)
# ─────────────────────────────────────────────────────────────────────────────

def compute_risk(status, open_val, bucket, rev_pct, pv_pct):
    score = 0
    status_map = {
        'FULLY RECONCILED': 0, 'FULLY REVERSED': 0, 'CLOSED': 0,
        'PARTIALLY REVERSED': 15, 'PARTIALLY INVOICED': 25,
        'GR ONLY': 40, 'IR ONLY': 55, 'PRICE VARIANCE': 35,
        'OVER INVOICED': 65, 'CRITICAL EXCEPTION': 85,
    }
    score += status_map.get(status, 20)

    av = abs(open_val)
    if av > 5000000:   score += 30
    elif av > 1000000: score += 20
    elif av > 500000:  score += 12
    elif av > 100000:  score += 6

    age_map = {'0-30': 0, '31-60': 5, '61-90': 12, '91-180': 20, '181-365': 30, '365+': 40}
    score += age_map.get(bucket, 0)

    if abs(pv_pct) > 20: score += 15
    elif abs(pv_pct) > 10: score += 8

    if rev_pct > 50: score += 10

    score = min(score, 100)
    if score >= 70: level = 'CRITICAL'
    elif score >= 50: level = 'HIGH'
    elif score >= 30: level = 'MEDIUM'
    else: level = 'LOW'
    return score, level


def compute_row_risk(row, reconciled):
    if reconciled or row['status'] in ('FULLY RECONCILED', 'FULLY REVERSED'):
        return 0, 'LOW'

    score = 0
    status_map = {
        'GR ONLY': 35, 'IR ONLY': 50, 'PARTIALLY INVOICED': 20,
        'OVER INVOICED': 60, 'PRICE VARIANCE': 30, 'PARTIALLY REVERSED': 10
    }
    score += status_map.get(row['status'], 15)

    days_open = row.get('days_open')
    if pd.notna(days_open):
        if days_open > 90:   score += 30
        elif days_open > 60: score += 20
        elif days_open > 30: score += 10

    price_var_pct = abs(row.get('price_var_pct', 0.0))
    if price_var_pct > 10:   score += 10
    elif price_var_pct > 5:  score += 5

    av = abs(row.get('open_val', 0.0))
    if av > 1000000:   score += 10
    elif av > 100000:  score += 5

    score = min(max(int(score), 0), 100)

    if score >= 75:   level = 'CRITICAL'
    elif score >= 50: level = 'HIGH'
    elif score >= 25: level = 'MEDIUM'
    else:             level = 'LOW'

    return score, level


# ─────────────────────────────────────────────────────────────────────────────
# NARRATIVE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def explain(row):
    s   = row['status']
    gq  = row['net_gr_qty']
    iq  = row['net_ir_qty']
    oq  = row['open_qty']
    ov  = row['open_val']
    raw_vendor = row.get('Vendor', 'Vendor')
    v   = str(raw_vendor)[:40] if raw_vendor and str(raw_vendor) not in ('nan','None','') else 'Vendor'
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


# ─────────────────────────────────────────────────────────────────────────────
# RECONCILIATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def reconcile(grir, me2n, ekko, analysis_date=None):
    print("  Building GRIR aggregates by PO+Item ...")
    if analysis_date is None:
        analysis_date = pd.Timestamp(ANALYSIS_DATE)
    else:
        analysis_date = pd.Timestamp(analysis_date)
    grir_df = grir.copy()
    me2n_df = me2n.copy()
    ekko_df = ekko.copy()
    
    # Standardize keys: convert to string and strip spaces
    grir_df['PO Number'] = grir_df['PO Number'].astype(str).str.strip()
    grir_df['PO Item'] = pd.to_numeric(grir_df['PO Item'], errors='coerce').fillna(0).astype(int).astype(str)
    
    if 'Purchasing Document' in me2n_df.columns:
        me2n_df = me2n_df.rename(columns={'Purchasing Document': 'PO Number'})
    if 'Item' in me2n_df.columns:
        me2n_df = me2n_df.rename(columns={'Item': 'PO Item'})
        
    me2n_df['PO Number'] = me2n_df['PO Number'].astype(str).str.strip()
    me2n_df['PO Item'] = pd.to_numeric(me2n_df['PO Item'], errors='coerce').fillna(0).astype(int).astype(str)
    
    if 'Purchasing Document' in ekko_df.columns:
        ekko_df = ekko_df.rename(columns={'Purchasing Document': 'PO Number'})
    ekko_df['PO Number'] = ekko_df['PO Number'].astype(str).str.strip()
    
    # Left join EKKO to GRIR
    ekko_cols = ['PO Number', 'Currency', 'Exchange Rate']
    if 'Company Code' in ekko_df.columns:
        ekko_cols.append('Company Code')
    ekko_sub = ekko_df[ekko_cols].rename(columns={
        'Currency': 'EKKO_Currency',
        'Exchange Rate': 'EKKO_Exchange_Rate',
        'Company Code': 'EKKO_Company_Code'
    }).drop_duplicates(subset=['PO Number'])
    
    grir_df = grir_df.merge(ekko_sub, on='PO Number', how='left')
    
    # Normalize amount to INR
    Amt_LC = pd.to_numeric(grir_df['Amt (LC)'], errors='coerce').fillna(0.0)
    Amt_FC = pd.to_numeric(grir_df['Amt (FC)'], errors='coerce').fillna(0.0)
    GRIR_Exchange_Rate = pd.to_numeric(grir_df['Exchange Rate'], errors='coerce').fillna(0.0) if 'Exchange Rate' in grir_df.columns else pd.Series(0.0, index=grir_df.index)
    EKKO_Exchange_Rate = pd.to_numeric(grir_df['EKKO_Exchange_Rate'], errors='coerce').fillna(0.0) if 'EKKO_Exchange_Rate' in grir_df.columns else pd.Series(0.0, index=grir_df.index)
    
    conds = [
        (Amt_LC != 0),
        (Amt_FC != 0) & (GRIR_Exchange_Rate > 0),
        (Amt_FC != 0) & (EKKO_Exchange_Rate > 0)
    ]
    choices = [
        Amt_LC,
        Amt_FC * GRIR_Exchange_Rate,
        Amt_FC * EKKO_Exchange_Rate
    ]
    grir_df['Normalized_Amount_INR'] = np.select(conds, choices, default=0.0)
    grir_df['Currency_Conversion_Missing'] = (~(conds[0] | conds[1] | conds[2])) & ((Amt_FC != 0) | (Amt_LC != 0))
    
    # Apply S/H sign
    qty = pd.to_numeric(grir_df['Quantity'], errors='coerce').fillna(0.0)
    grir_df['Signed_Qty'] = np.where(grir_df['Dr/Cr Ind'] == 'H', -qty, qty)
    grir_df['Signed_Amount_INR'] = np.where(grir_df['Dr/Cr Ind'] == 'H', -grir_df['Normalized_Amount_INR'], grir_df['Normalized_Amount_INR'])
    
    # Split GR and IR
    grir_df['GR_Value_INR'] = np.where(grir_df['Trans Type'] == '1', grir_df['Signed_Amount_INR'], 0.0)
    grir_df['IR_Value_INR'] = np.where(grir_df['Trans Type'] == '2', grir_df['Signed_Amount_INR'], 0.0)
    grir_df['GR_Qty'] = np.where(grir_df['Trans Type'] == '1', grir_df['Signed_Qty'], 0.0)
    grir_df['IR_Qty'] = np.where(grir_df['Trans Type'] == '2', grir_df['Signed_Qty'], 0.0)
    
    grir_df['Posting_Date_dt'] = pd.to_datetime(grir_df['Posting Date'], errors='coerce')
    grir_df['GR_Date'] = np.where(grir_df['Trans Type'] == '1', grir_df['Posting_Date_dt'], pd.NaT)
    grir_df['IR_Date'] = np.where(grir_df['Trans Type'] == '2', grir_df['Posting_Date_dt'], pd.NaT)
    
    grir_df['GR_Date'] = pd.to_datetime(grir_df['GR_Date'])
    grir_df['IR_Date'] = pd.to_datetime(grir_df['IR_Date'])
    
    grir_df['is_gr'] = (grir_df['Trans Type'] == '1')
    grir_df['is_ir'] = (grir_df['Trans Type'] == '2')
    grir_df['is_reversal'] = (grir_df['Dr/Cr Ind'] == 'H')
    grir_df['reversal_val'] = np.where(grir_df['Dr/Cr Ind'] == 'H', grir_df['Normalized_Amount_INR'], 0.0)
    
    # Aggregate by PO Number + PO Item
    agg_df = grir_df.groupby(['PO Number', 'PO Item']).agg(
        Net_GR_Val_INR=('GR_Value_INR', 'sum'),
        Net_IR_Val_INR=('IR_Value_INR', 'sum'),
        Net_GR_Qty=('GR_Qty', 'sum'),
        Net_IR_Qty=('IR_Qty', 'sum'),
        GR_Txn_Count=('is_gr', 'sum'),
        IR_Txn_Count=('is_ir', 'sum'),
        First_GR_Date=('GR_Date', 'min'),
        First_IR_Date=('IR_Date', 'min'),
        Last_GR_Date=('GR_Date', 'max'),
        Last_IR_Date=('IR_Date', 'max'),
        Reversal_Count_PO=('is_reversal', 'sum'),
        Reversal_Value_INR_PO=('reversal_val', 'sum'),
        Currency_Conversion_Missing_Count=('Currency_Conversion_Missing', 'sum')
    ).reset_index()
    
    # Calculate balance and exposure
    agg_df['Open_Val_INR'] = agg_df['Net_GR_Val_INR'] - agg_df['Net_IR_Val_INR']
    agg_df['Open_Exposure_INR'] = agg_df['Open_Val_INR'].abs()
    agg_df['Open_Qty'] = agg_df['Net_GR_Qty'] - agg_df['Net_IR_Qty']
    agg_df['Open_Qty_Exposure'] = agg_df['Open_Qty'].abs()
    
    # Classify status
    op_val = agg_df['Open_Val_INR']
    net_gr = agg_df['Net_GR_Val_INR']
    net_ir = agg_df['Net_IR_Val_INR']
    
    status_conds = [
        ((agg_df['Net_GR_Qty'].abs() < 0.01) & (agg_df['Net_IR_Qty'].abs() < 0.01)) | ((net_gr.abs() < 0.01) & (net_ir.abs() < 0.01)),
        (op_val.abs() <= 0.01),
        (net_gr > 0) & (net_ir == 0),
        (net_ir > 0) & (net_gr == 0),
        (net_ir > net_gr) & (net_gr > 0),
        (net_gr > net_ir) & (net_ir > 0),
    ]
    status_choices = [
        'No Activity',
        'Reconciled',
        'GR Done / IR Pending',
        'IR Done / GR Pending',
        'Invoice Greater Than GR',
        'GR Greater Than Invoice',
    ]
    agg_df['Status'] = np.select(status_conds, status_choices, default='Review Required')
    
    # Bring in Exchange Rate and Currency from ekko_df to me2n_df first
    ekko_cols_to_merge = ['PO Number', 'Exchange Rate', 'Currency']
    ekko_for_merge = ekko_df[[c for c in ekko_cols_to_merge if c in ekko_df.columns]].drop_duplicates(subset=['PO Number'])
    me2n_merged = me2n_df.merge(ekko_for_merge, on='PO Number', how='left')
    me2n_merged['Exchange Rate'] = me2n_merged.get('Exchange Rate', pd.Series(1.0, index=me2n_merged.index)).fillna(1.0)
    me2n_merged['Currency'] = me2n_merged.get('Currency', pd.Series('INR', index=me2n_merged.index)).fillna('INR')

    # Left join ME2N for metadata enrichment only
    me2n_cols = ['PO Number', 'PO Item', 'Vendor', 'Plant', 'Material', 'Material Group', 
                 'Short Text', 'Purchasing Group', 'Order Quantity', 'Net Order Value', 
                 'Open value', 'Still to be delivered qty', 'Still to be delivered (qty)', 'Still to be invoiced (qty)', 'Still to be invoiced (val.)', 'Delivery date', 'Document Date', 'Net Price', 'Exchange Rate']
    me2n_sub_cols = [c for c in me2n_cols if c in me2n_merged.columns]
    me2n_sub = me2n_merged[me2n_sub_cols].drop_duplicates(subset=['PO Number', 'PO Item'])
    
    agg_df = agg_df.merge(me2n_sub, on=['PO Number', 'PO Item'], how='left')
    
    # Fill missing Vendor, Plant etc. with defaults
    if 'Vendor' in agg_df.columns:
        agg_df['Vendor'] = agg_df['Vendor'].fillna('Unknown')
    if 'Plant' in agg_df.columns:
        agg_df['Plant'] = agg_df['Plant'].fillna('Unknown')
    if 'Material' in agg_df.columns:
        agg_df['Material'] = agg_df['Material'].fillna('Unknown')
    if 'Material Group' in agg_df.columns:
        agg_df['Material Group'] = agg_df['Material Group'].fillna('Unknown')
    if 'Short Text' in agg_df.columns:
        agg_df['Short Text'] = agg_df['Short Text'].fillna('Unknown')
        
    # Aging logic
    first_gr = pd.to_datetime(agg_df['First_GR_Date'])
    first_ir = pd.to_datetime(agg_df['First_IR_Date'])
    max_last = pd.to_datetime(agg_df[['Last_GR_Date', 'Last_IR_Date']].max(axis=1))
    
    # Extract Document Date from ME2N or fallback to EKKO Document Date (if available)
    doc_date = pd.NaT
    if 'Document Date' in agg_df.columns:
        doc_date = pd.to_datetime(agg_df['Document Date'])
    elif 'Document Date' in ekko_df.columns:
        ekko_dates = ekko_df[['PO Number', 'Document Date']].drop_duplicates(subset=['PO Number'])
        agg_df = agg_df.merge(ekko_dates, on='PO Number', how='left', suffixes=('', '_EKKO'))
        if 'Document Date_EKKO' in agg_df.columns:
            doc_date = pd.to_datetime(agg_df['Document Date_EKKO'])
            
    cond_ir_pending = agg_df['Status'] == 'IR Pending'
    cond_gr_pending = agg_df['Status'] == 'GR Pending'
    cond_recon = agg_df['Status'] == 'Reconciled'
    cond_else = ~(cond_ir_pending | cond_gr_pending | cond_recon)
    
    agg_df['Aging_Start_Date'] = pd.NaT
    agg_df.loc[cond_ir_pending, 'Aging_Start_Date'] = first_gr
    agg_df.loc[cond_gr_pending, 'Aging_Start_Date'] = first_ir
    agg_df.loc[cond_recon, 'Aging_Start_Date'] = max_last
    agg_df.loc[cond_else, 'Aging_Start_Date'] = doc_date
    
    agg_df['Aging_Start_Date'] = pd.to_datetime(agg_df['Aging_Start_Date'])
    
    # Calculate Days Open
    agg_df['Days_Open'] = (analysis_date - agg_df['Aging_Start_Date']).dt.days
    agg_df['Days_Open'] = agg_df['Days_Open'].fillna(0).astype(int)
    
    # Classify into aging bucket
    agg_df['Aging_Bucket'] = agg_df['Days_Open'].apply(aging_bucket)
    
    # Keep legacy/expected column names for compatibility
    agg_df['net_gr_qty'] = agg_df['Net_GR_Qty']
    agg_df['net_ir_qty'] = agg_df['Net_IR_Qty']
    agg_df['open_qty'] = agg_df['Open_Qty']
    agg_df['net_gr_val'] = agg_df['Net_GR_Val_INR']
    agg_df['net_ir_val'] = agg_df['Net_IR_Val_INR']
    agg_df['open_val'] = agg_df['Open_Val_INR']
    agg_df['exposure_val'] = agg_df['Open_Exposure_INR']
    agg_df['days_open'] = agg_df['Days_Open']
    agg_df['aging_bucket'] = agg_df['Aging_Bucket']
    agg_df['status'] = agg_df['Status']
    agg_df['reconciled'] = agg_df['Status'] == 'Reconciled'
    agg_df['posting_date'] = agg_df['Aging_Start_Date']
    agg_df['amount_matched'] = agg_df['reconciled']
    agg_df['net_gr_qty_grir'] = agg_df['Net_GR_Qty']
    agg_df['material_key'] = agg_df['Material'].fillna(agg_df.get('Short Text', '')).fillna('Unknown').astype(str).str.strip()
    agg_df['material_label'] = agg_df['Material'].fillna('').astype(str) + " - " + agg_df.get('Short Text', '').fillna('').astype(str)
    agg_df['material_label'] = agg_df['material_label'].str.strip(' -')
    
    # Reversal info (Legacy compatibility)
    agg_df['ir_reversal_qty'] = 0.0
    agg_df['ir_reversal_val'] = 0.0
    agg_df['gr_reversal_qty'] = 0.0
    agg_df['gr_reversal_val'] = 0.0
    agg_df['reversal_pct'] = 0.0
    agg_df['ir_reversal_val'] = agg_df['Reversal_Value_INR_PO']
    agg_df['reversal_pct'] = np.where(agg_df['Net_IR_Qty'] != 0, (agg_df['Reversal_Value_INR_PO'] / agg_df['Net_IR_Qty']).clip(0, 100), 0.0)

    # Invoice completion percentage
    agg_df['inv_completion_pct'] = np.where(
        agg_df['net_gr_qty'] > 0,
        (agg_df['net_ir_qty'] / agg_df['net_gr_qty'] * 100).clip(0, 100),
        0.0
    )

    # Price Variance calculations (Legacy compatibility)
    agg_df['invoice_price'] = np.where(agg_df['net_ir_qty'] > 0, agg_df['net_ir_val'] / agg_df['net_ir_qty'], agg_df['Net Price'] * agg_df['Exchange Rate'])
    agg_df['po_price_inr']   = agg_df['Net Price'] * agg_df['Exchange Rate']
    agg_df['price_var_abs'] = (agg_df['invoice_price'] - agg_df['po_price_inr']) * agg_df['net_ir_qty']
    agg_df['price_var_pct'] = np.where(
        agg_df['po_price_inr'] > 0,
        ((agg_df['invoice_price'] - agg_df['po_price_inr']) / agg_df['po_price_inr'] * 100).clip(-200, 200),
        0
    )
    # Zero out price variance if no IR quantity or Net Price is zero
    mask_zero_pv = (agg_df['net_ir_qty'] == 0) | (agg_df['Net Price'] == 0)
    agg_df.loc[mask_zero_pv, 'price_var_abs'] = 0.0
    agg_df.loc[mask_zero_pv, 'price_var_pct'] = 0.0
    
    # Add dummy/fallback columns for ME2N quantities to keep downstream KPI math happy
    if 'Net_Order_Value_INR' not in agg_df.columns:
        if 'Net Order Value' in agg_df.columns:
            ex_rate = agg_df.get('Exchange Rate', pd.Series(1.0, index=agg_df.index)).fillna(1.0)
            agg_df['Net_Order_Value_INR'] = agg_df['Net Order Value'] * ex_rate
        else:
            agg_df['Net_Order_Value_INR'] = 0.0

    # Add dummy/fallback columns for ME2N quantities to keep downstream KPI math happy
    if 'Still to be delivered (qty)' not in agg_df.columns:
        agg_df['Still to be delivered (qty)'] = 0.0
    if 'Still to be invoiced (qty)' not in agg_df.columns:
        agg_df['Still to be invoiced (qty)'] = 0.0
    if 'Still to be invoiced (val.)' not in agg_df.columns:
        agg_df['Still to be invoiced (val.)'] = 0.0
    if 'Net Price' not in agg_df.columns:
        agg_df['Net Price'] = 0.0
    if 'Exchange Rate' not in agg_df.columns:
        agg_df['Exchange Rate'] = 1.0

    # Risk scoring (Legacy compatibility using 0-100 scale)
    risk_results = agg_df.apply(
        lambda r: compute_risk(
            r['Status'],
            r['Open_Val_INR'],
            r['Aging_Bucket'],
            r['reversal_pct'],
            r['price_var_pct']
        ),
        axis=1
    )
    agg_df['risk_score'] = [x[0] for x in risk_results]
    agg_df['risk_level'] = [x[1] for x in risk_results]
        
    print(f"  Reconciliation complete: {len(agg_df):,} PO line items")
    return agg_df


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_kpis(df, ekko=None):
    total_items  = len(df)
    total_gr_val = df['net_gr_val'].sum()
    total_ir_val = df['net_ir_val'].sum()
    total_open_exposure = df['exposure_val'].sum()
    total_open_signed = df['open_val'].sum()
    total_open_q = df['open_qty'].sum()

    recon_count = (df['Status'] == 'Reconciled').sum()
    recon_rate  = recon_count / total_items * 100 if total_items else 0.0

    status_dist_init = {
        'Reconciled': 0,
        'GR Done / IR Pending': 0,
        'IR Done / GR Pending': 0,
        'Invoice Greater Than GR': 0,
        'GR Greater Than Invoice': 0,
        'Review Required': 0
    }
    status_counts = df['Status'].value_counts().to_dict()
    status_dist_init.update(status_counts)
    status_dist = status_dist_init

    risk_dist   = df['risk_level'].value_counts().to_dict()

    pending_invoice_val = df[df['Status'].isin(['GR Done / IR Pending', 'GR Greater Than Invoice'])]['Open_Exposure_INR'].sum()
    over_inv_val        = df[df['Status'].isin(['IR Done / GR Pending', 'Invoice Greater Than GR'])]['Open_Exposure_INR'].sum()
    ir_only_val         = df[df['Status'] == 'IR Done / GR Pending']['Open_Exposure_INR'].sum()
    total_reversals_val = df['Reversal_Value_INR_PO'].sum() if 'Reversal_Value_INR_PO' in df.columns else 0.0

    spend_by_vendor = df.groupby('Vendor')['Net_Order_Value_INR'].sum().sort_values(ascending=False) if 'Vendor' in df.columns and 'Net_Order_Value_INR' in df.columns else pd.Series()
    spend_by_matgrp = df.groupby('Material Group')['Net_Order_Value_INR'].sum().sort_values(ascending=False) if 'Material Group' in df.columns and 'Net_Order_Value_INR' in df.columns else pd.Series()
    spend_by_purchgrp = df.groupby('Purchasing Group')['Net_Order_Value_INR'].sum().sort_values(ascending=False) if 'Purchasing Group' in df.columns and 'Net_Order_Value_INR' in df.columns else pd.Series()

    company_codes = []
    if ekko is not None and 'Company Code' in ekko.columns:
        company_codes = sorted(ekko['Company Code'].dropna().astype(str).unique().tolist())
    elif 'EKKO_Company_Code' in df.columns:
        company_codes = sorted(df['EKKO_Company_Code'].dropna().astype(str).unique().tolist())

    return {
        'total_po_items':        int(total_items),
        'total_gr_value':        round(float(total_gr_val), 2),
        'total_ir_value':        round(float(total_ir_val), 2),
        'total_open_value':      round(float(total_open_signed), 2),
        'total_open_value_signed': round(float(total_open_signed), 2),
        'total_open_qty':        round(float(total_open_q), 2),
        'reconciliation_rate':   round(float(recon_rate), 1),
        'reconciled_count':      int(recon_count),
        'matched_lines':         int(recon_count),
        'unmatched_lines':       int(total_items - recon_count),
        'open_item_count':       int(total_items - recon_count),
        'critical_items':        int((df['risk_level'] == 'CRITICAL').sum()),
        'high_risk_items':       int((df['risk_level'] == 'HIGH').sum()),
        'medium_risk_items':     int((df['risk_level'] == 'MEDIUM').sum()),
        'low_risk_items':        int((df['risk_level'] == 'LOW').sum()),
        'pending_invoice_val':   round(float(pending_invoice_val), 2),
        'over_invoice_val':      round(float(over_inv_val), 2),
        'ir_only_val':           round(float(ir_only_val), 2),
        'total_reversals_val':   round(float(total_reversals_val), 2),
        'status_distribution':   {k: int(v) for k, v in status_dist.items()},
        'risk_distribution':     {k: int(v) for k, v in risk_dist.items()},
        'unique_vendors':        int(df['Vendor'].nunique()),
        'unique_pos':            int(df['PO Number'].nunique()),
        'unique_plants':         int(df['Plant'].nunique()),
        'total_materials':       int(df['material_key'].nunique()) if 'material_key' in df.columns else int(df['Material'].nunique()),
        'total_procurement_spend_inr': round(float(df['Net_Order_Value_INR'].sum()), 2),
        'top_supplier':          str(spend_by_vendor.index[0]) if len(spend_by_vendor) else 'N/A',
        'top_material_group':    str(spend_by_matgrp.index[0]) if len(spend_by_matgrp) else 'N/A',
        'top_purchasing_group':  str(spend_by_purchgrp.index[0]) if len(spend_by_purchgrp) else 'N/A',
        'total_purchasing_groups': int(df['Purchasing Group'].nunique()),
        'total_plants':          int(df['Plant'].nunique()),
        'total_suppliers':       int(df['Vendor'].nunique()),
        'company_codes':         company_codes,
    }


def build_aging(df):
    buckets = ['0-30', '31-60', '61-90', '91-180', '181-365', '365+']
    result = []
    for b in buckets:
        sub = df[df['aging_bucket'] == b]
        open_sub = sub[~sub['reconciled']]
        result.append({
            'bucket':          b,
            'total_count':     int(len(sub)),
            'open_count':      int(len(open_sub)),
            'open_value':      round(float(open_sub['exposure_val'].sum()), 2),
            'exposure':        round(float(open_sub['exposure_val'].sum()), 2),
            'gr_done_ir_pending_val': round(float(sub[sub['status']=='GR Done / IR Pending']['open_val'].abs().sum()), 2),
            'gr_greater_inv_val': round(float(sub[sub['status']=='GR Greater Than Invoice']['open_val'].abs().sum()), 2),
            'ir_done_gr_pending_val': round(float(sub[sub['status']=='IR Done / GR Pending']['open_val'].abs().sum()), 2),
            'inv_greater_gr_val': round(float(sub[sub['status']=='Invoice Greater Than GR']['open_val'].abs().sum()), 2),
            'review_required_val': round(float(sub[sub['status']=='Review Required']['open_val'].abs().sum()), 2),
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
        
        if score >= 76:     risk_level = 'CRITICAL'
        elif score >= 51:   risk_level = 'HIGH'
        elif score >= 26:   risk_level = 'MEDIUM'
        else:               risk_level = 'LOW'
            
        key_name = 'material' if group_col in ('Short Text', 'material_key', 'material_label') else group_col.lower()
        groups.append({
            key_name: str(name),
            'exposure': round(float(grp_exposure), 2),
            'avg_days_open': round(float(avg_days), 1) if not pd.isna(avg_days) else 0.0,
            'recon_rate': round(float(recon_rate), 1),
            'avg_price_variance': round(float(avg_var), 1) if not pd.isna(avg_var) else 0.0,
            'score': score,
            'risk_level': risk_level
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
        
        if row['status'] == 'Invoice Greater Than GR':
            reasons.append(f"Excess invoicing: Invoice receipt exceeds Goods receipt by {abs(row['open_qty']):.1f} units")
            rec_action = "Block payment immediately, investigate duplicate invoicing or billing error."
        elif row['status'] == 'IR Done / GR Pending':
            reasons.append("Three-way match failure: Invoice receipt posted without goods receipt")
            rec_action = "Block payment until goods receipt is verified and posted."
        elif row['status'] == 'GR Done / IR Pending' and row['days_open'] > 90:
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
            'recommended_action': rec_action
        })
        
    return flags


def generate_deterministic_insights(df, kpis, total_open_exposure):
    insights = []
    
    # 1. Vendor Concentration Insight
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
                'business_impact': "Concentration of outstanding balances on a single vendor increases supplier risk and could cause settlement disputes."
            })
            
    # 2. Overall Reconciliation Rate
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
            'business_impact': "Low reconciliation rates signal systemic goods receipt delays or invoice receipt errors, extending month-end closing cycles."
        })
        
    # 3. Over-invoicing Leakage
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
            'business_impact': "Invoices approved and paid for quantities exceeding goods receipts present direct cash leakage and internal control failures."
        })
        
    # 4. Aging Exposure
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
            'business_impact': "Long-outstanding GR/IR balances can lead to auditor exceptions and require month-end balance sheet write-offs."
        })
        
    return insights


def build_vendor_insights(df):
    total_open = df['open_val'].sum()
    vendors = []
    for vendor, vdf in df.groupby('Vendor'):
        if not vendor or str(vendor) in ('nan','','None','NaN'):
            continue
        v_open = vdf['open_val'].sum()
        v_gr   = vdf['net_gr_val'].sum()
        v_ir   = vdf['net_ir_val'].sum()
        exc    = int((vdf['risk_level'].isin(['CRITICAL','HIGH'])).sum())
        top_status = vdf['status'].mode().iloc[0] if len(vdf) > 0 else ''
        avg_rev    = float(vdf['reversal_pct'].mean())
        avg_days   = float(vdf['days_open'].dropna().mean()) if vdf['days_open'].dropna().any() else 0

        vendors.append({
            'vendor':           str(vendor)[:70],
            'po_count':         int(vdf['PO Number'].nunique()),
            'item_count':       int(len(vdf)),
            'gr_value':         round(float(v_gr), 2),
            'ir_value':         round(float(v_ir), 2),
            'open_value':       round(float(v_open), 2),
            'open_pct_total':   round(float(v_open / total_open * 100 if total_open else 0), 1),
            'avg_reversal_pct': round(avg_rev, 1),
            'avg_days_open':    round(avg_days, 0),
            'exception_count':  exc,
            'dominant_status':  str(top_status),
            'risk_level':       str(vdf['risk_level'].mode().iloc[0]) if len(vdf) else 'LOW',
            'pending_invoice':  round(float(vdf[vdf['status'].isin(['GR Done / IR Pending','GR Greater Than Invoice'])]['open_val'].sum()), 2),
            'over_invoiced':    round(float(vdf[vdf['status'].isin(['IR Done / GR Pending','Invoice Greater Than GR'])]['open_val'].abs().sum()), 2),
        })
    return sorted(vendors, key=lambda x: abs(x['open_value']), reverse=True)[:30]


def build_material_insights(df):
    mats = []
    for mat, mdf in df.groupby('material_key'):
        if not mat or str(mat) in ('nan','','None','NaN'):
            continue
        label = mdf['material_label'].iloc[0] if 'material_label' in mdf.columns else str(mat)
        mats.append({
            'material':    str(label)[:80],
            'material_key': str(mat)[:40],
            'item_count':  int(len(mdf)),
            'open_value':  round(float(mdf['open_val'].sum()), 2),
            'gr_value':    round(float(mdf['net_gr_val'].sum()), 2),
            'ir_value':    round(float(mdf['net_ir_val'].sum()), 2),
            'status_dist': {k: int(v) for k, v in mdf['status'].value_counts().to_dict().items()},
        })
    return sorted(mats, key=lambda x: abs(x['open_value']), reverse=True)[:25]


def build_plant_insights(df):
    total_open = df['open_val'].sum()
    plants = []
    for plant, pdf in df.groupby('Plant'):
        if not plant or str(plant) in ('nan','','None','NaN'):
            continue
        p_open   = pdf['open_val'].sum()
        p_gr     = pdf['net_gr_val'].sum()
        p_ir     = pdf['net_ir_val'].sum()
        recon_r  = (pdf['status'] == 'FULLY RECONCILED').sum() / len(pdf) * 100 if len(pdf) else 0
        exc_rate = (pdf['risk_level'].isin(['CRITICAL','HIGH'])).sum() / len(pdf) * 100 if len(pdf) else 0
        plants.append({
            'plant':              str(plant),
            'item_count':         int(len(pdf)),
            'open_value':         round(float(p_open), 2),
            'gr_value':           round(float(p_gr), 2),
            'ir_value':           round(float(p_ir), 2),
            'open_pct_total':     round(float(p_open / total_open * 100 if total_open else 0), 1),
            'reconciliation_rate':round(float(recon_r), 1),
            'exception_rate':     round(float(exc_rate), 1),
            'critical_count':     int((pdf['risk_level'] == 'CRITICAL').sum()),
        })
    return sorted(plants, key=lambda x: abs(x['open_value']), reverse=True)


def build_plant_analytics(df, plant_risk, total_open_exposure):
    """Dedicated plant analytics section per API contract."""
    spend = df.groupby('Plant')['Net_Order_Value_INR'].sum().reset_index().rename(
        columns={'Plant': 'plant', 'Net_Order_Value_INR': 'spend'}
    ).sort_values('spend', ascending=False)
    exposure = df.groupby('Plant')['exposure_val'].sum().reset_index().rename(
        columns={'Plant': 'plant', 'exposure_val': 'exposure'}
    ).sort_values('exposure', ascending=False)
    aging = df.groupby('Plant')['days_open'].mean().reset_index().rename(
        columns={'Plant': 'plant', 'days_open': 'avg_days_open'}
    ).fillna(0).sort_values('avg_days_open', ascending=False)
    variance = df.groupby('Plant')['price_var_pct'].mean().reset_index().rename(
        columns={'Plant': 'plant', 'price_var_pct': 'avg_price_variance'}
    ).fillna(0).sort_values('avg_price_variance', key=abs, ascending=False)
    return {
        'plant_spend': spend.to_dict('records'),
        'plant_exposure': exposure.to_dict('records'),
        'plant_aging': aging.to_dict('records'),
        'plant_variance': variance.to_dict('records'),
        'plant_risk_score': plant_risk,
        'top_plants': spend.head(15).to_dict('records'),
        'plant_concentration': round(
            float(spend['spend'].max() / spend['spend'].sum() * 100), 1
        ) if spend['spend'].sum() > 0 else 0.0,
    }


def build_price_variance(df):
    pv = df[abs(df['price_var_pct']) > 5].copy()
    pv = pv.sort_values('price_var_pct', key=abs, ascending=False)
    result = []
    for _, row in pv.head(25).iterrows():
        result.append({
            'po_number':  str(row['PO Number']),
            'po_item':    str(row['PO Item']),
            'vendor':     str(row['Vendor'])[:60],
            'material':   str(row['Short Text'])[:60],
            'po_price':   round(float(row['Net Price']), 2),
            'ir_value':   round(float(row['net_ir_val']), 2),
            'gr_value':   round(float(row['net_gr_val']), 2),
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
            'po_number':      str(row['PO Number']),
            'po_item':        str(row['PO Item']),
            'vendor':         str(row['Vendor'])[:60],
            'material':       str(row['Short Text'])[:60],
            'ir_qty':         round(float(row['net_ir_qty']), 2),
            'reversal_qty':   round(float(row['ir_reversal_qty']), 2),
            'reversal_val':   round(float(row['ir_reversal_val']), 2),
            'reversal_pct':   round(float(row['reversal_pct']), 1),
            'open_val':       round(float(row['open_val']), 2),
            'status':         str(row['status']),
        })
    return result


def build_exceptions(df):
    exc_df = df[~df['reconciled'] & (df['status'] != 'FULLY REVERSED')].copy()
    exc_df = exc_df.sort_values(['risk_score','open_val'], ascending=[False, True]).head(30)

    result = []
    for _, row in exc_df.iterrows():
        result.append({
            'po_number':    str(row['PO Number']),
            'po_item':      str(row['PO Item']),
            'vendor':       str(row['Vendor'])[:60],
            'material':     str(row['Short Text'])[:60],
            'plant':        str(row['Plant']),
            'status':       str(row['status']),
            'open_val':     round(float(row['open_val']), 2),
            'open_qty':     round(float(row['open_qty']), 2),
            'net_gr_val':   round(float(row['net_gr_val']), 2),
            'net_ir_val':   round(float(row['net_ir_val']), 2),
            'risk_score':   int(row['risk_score']),
            'risk_level':   str(row['risk_level']),
            'aging_bucket': str(row['aging_bucket']),
            'inv_completion_pct': round(float(row['inv_completion_pct']), 1),
            'reversal_pct': round(float(row['reversal_pct']), 1),
            'posting_date': row['posting_date'].strftime('%Y-%m-%d') if pd.notna(row['posting_date']) else '',
            'days_open':    int(row['days_open']) if pd.notna(row['days_open']) else 0,
            'explanation':  explain(row),
        })
    return result


def build_recommended_actions(df, kpis):
    actions = []

    gr_only = df[df['status'] == 'GR ONLY']
    if len(gr_only):
        actions.append({
            'priority':   'HIGH',
            'category':   'Pending Invoice Follow-up',
            'action':     f"Contact vendors for {len(gr_only)} PO items where goods were received but no invoice posted. Total exposure: INR {gr_only['open_val'].sum():,.0f}.",
            'owner':      'Accounts Payable / Procurement',
            'impact':     'Reduce accrual liability understatement; improve AP closing accuracy.',
            'timeline':   'Within 7 business days',
        })

    ir_only = df[df['status'] == 'IR ONLY']
    if len(ir_only):
        actions.append({
            'priority':   'CRITICAL',
            'category':   'Invoice Without GR — Control Violation',
            'action':     f"Investigate {len(ir_only)} items invoiced without goods receipt. Block payment on all. Total: INR {ir_only['net_ir_val'].sum():,.0f}.",
            'owner':      'Internal Audit / Warehouse / AP',
            'impact':     'Prevent fraudulent payments; restore 3-way match controls.',
            'timeline':   'Immediate — escalate to Finance Controller',
        })

    over_inv = df[df['status'] == 'OVER INVOICED']
    if len(over_inv):
        actions.append({
            'priority':   'CRITICAL',
            'category':   'Over-Invoice Investigation',
            'action':     f"Review {len(over_inv)} over-invoiced items. Issue vendor debit notes or block duplicate invoices. Excess: INR {over_inv['open_val'].abs().sum():,.0f}.",
            'owner':      'Finance Controller / Internal Audit',
            'impact':     'Prevent overpayment; recover excess invoice amounts.',
            'timeline':   'Within 3 business days',
        })

    old_items = df[df['aging_bucket'].isin(['91-180','180+']) & (~df['reconciled']) & (df['open_val'].abs() > 1000)]
    if len(old_items):
        actions.append({
            'priority':   'HIGH',
            'category':   'Aging GR/IR Clearance',
            'action':     f"Clear {len(old_items)} items aged >90 days. Total value: INR {old_items['open_val'].abs().sum():,.0f}. Write off irrecoverable balances with management approval.",
            'owner':      'Finance Controller',
            'impact':     'Cleanse BS; reduce audit risk; improve GR/IR account accuracy.',
            'timeline':   'Before period close',
        })

    return actions


def build_executive_summary(df, kpis, analysis_date=None):
    open_val   = kpis['total_open_value']
    open_cr    = abs(open_val) / 1e7
    total_items= kpis['total_po_items']
    open_items = kpis['open_item_count']
    recon_rate = kpis['reconciliation_rate']
    crit       = kpis['critical_items']

    gr_only_pct = (df[df['status']=='GR ONLY']['open_val'].sum() / open_val * 100) if open_val else 0
    partial_pct = (df[df['status']=='PARTIALLY INVOICED']['open_val'].sum() / open_val * 100) if open_val else 0
    over_inv_pct= (df[df['status']=='OVER INVOICED']['open_val'].abs().sum() / abs(open_val) * 100) if open_val else 0

    risk_flags = []
    if (df['status']=='OVER INVOICED').sum() > 0:
        risk_flags.append(f"{(df['status']=='OVER INVOICED').sum()} over-invoiced items detected — potential overpayment or fraud risk")
    if (df['status']=='IR ONLY').sum() > 0:
        risk_flags.append(f"{(df['status']=='IR ONLY').sum()} invoices received without goods receipt — 3-way match control failure")
    if (df['aging_bucket'].isin(['91-180','180+']) & (~df['reconciled'])).sum() > 0:
        old_val = df[df['aging_bucket'].isin(['91-180','180+']) & (~df['reconciled'])]['open_val'].abs().sum()
        risk_flags.append(f"INR {old_val/1e7:.2f} Cr in items aged >90 days — overdue for clearance")
    if crit > 0:
        risk_flags.append(f"{crit} PO items classified as CRITICAL risk requiring immediate action")

    return {
        'headline':    f"INR {open_cr:.2f} Cr of GRIR exposure unreconciled across {open_items:,} PO items as of {ANALYSIS_DATE.strftime('%d %B %Y')}",
        'detail':      (
            f"Out of {total_items:,} PO line items analyzed, {open_items:,} ({100-recon_rate:.0f}%) "
            f"carry unresolved GR/IR balances. {abs(gr_only_pct):.0f}% of open exposure relates to "
            f"goods received without invoices (accrual risk), {abs(partial_pct):.0f}% to partially invoiced "
            f"deliveries, and {abs(over_inv_pct):.0f}% to potential over-invoicing. "
            f"{crit} PO items are CRITICAL and require immediate escalation."
        ),
        'risk_flags':  risk_flags,
        'key_metrics': {
            'open_value_cr':     round(open_cr, 2),
            'reconciliation_pct':round(recon_rate, 1),
            'critical_items':    crit,
            'unique_vendors':    kpis['unique_vendors'],
            'total_pos':         kpis['unique_pos'],
        },
    }


def build_financial_impact(df, kpis):
    open_val = kpis['total_open_value']
    pending  = kpis['pending_invoice_val']
    over_inv = kpis['over_invoice_val']
    ir_only  = kpis['ir_only_val']

    return [
        {
            'area':        'Accounts Payable Liability',
            'impact_val':  round(float(abs(open_val)), 2),
            'impact_cr':   round(float(abs(open_val))/1e7, 3),
            'description': f"INR {abs(open_val)/1e7:.2f} Cr in uncleared GRIR balance may misstate Accounts Payable. Accruals required before close.",
            'action':      'Book month-end accruals for all open GR-only items.',
            'severity':    'HIGH',
        },
        {
            'area':        'Accrued Liabilities',
            'impact_val':  round(float(abs(pending)), 2),
            'impact_cr':   round(float(abs(pending))/1e7, 3),
            'description': f"INR {abs(pending)/1e7:.2f} Cr of goods received but not invoiced requires accrual. Omitting this understates liabilities.",
            'action':      'Pass accrual journal: Dr. GR/IR Expense Cr. Accrued Liabilities.',
            'severity':    'HIGH',
        },
        {
            'area':        'Over-Payment Risk',
            'impact_val':  round(float(over_inv), 2),
            'impact_cr':   round(float(over_inv)/1e7, 3),
            'description': f"INR {over_inv/1e7:.2f} Cr at risk of over-payment due to invoice quantities exceeding GR. Block all over-invoiced items.",
            'action':      'Block payment run for all OVER INVOICED items; investigate duplicates.',
            'severity':    'CRITICAL',
        },
        {
            'area':        'Control Violation Exposure',
            'impact_val':  round(float(abs(ir_only)), 2),
            'impact_cr':   round(float(abs(ir_only))/1e7, 3),
            'description': f"INR {abs(ir_only)/1e7:.2f} Cr of invoices without goods receipts indicates process breakdown. Audit trail required.",
            'action':      'Obtain GR confirmation or reject invoice. Escalate to Internal Audit.',
            'severity':    'CRITICAL',
        },
    ]


def safe_json(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
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


def main():
    print("\n" + "="*65)
    print("  SAP GR/IR RECONCILIATION ANALYSIS ENGINE")
    print("="*65)

    print("\n[1/5] Loading source files...")
    grir, ekko, me2n = load_data()

    print("\n[2/5] Cleaning & standardising data...")
    grir = clean_grir(grir)
    me2n = clean_me2n(me2n)
    ekko = clean_ekko(ekko)

    print("\n[3/5] Running reconciliation engine...")
    df = reconcile(grir, me2n, ekko)

    print("\n[4/5] Computing analytics...")
    kpis      = build_kpis(df)
    aging     = build_aging(df)
    vendors   = build_vendor_insights(df)
    materials = build_material_insights(df)
    plants    = build_plant_insights(df)
    price_var = build_price_variance(df)
    reversals = build_reversal_analysis(df)
    exceptions= build_exceptions(df)
    actions   = build_recommended_actions(df, kpis)
    exec_sum  = build_executive_summary(df, kpis)
    fin_imp   = build_financial_impact(df, kpis)

    total_open_exposure = kpis['total_open_value']

    # Generate Rule-based Risks & Insights
    vendor_risk = calculate_group_risk_scores(df, 'Vendor', total_open_exposure)
    material_risk = calculate_group_risk_scores(df, 'Short Text', total_open_exposure)
    plant_risk = calculate_group_risk_scores(df, 'Plant', total_open_exposure)
    rule_based_risks = generate_risk_flags(df, total_open_exposure)
    deterministic_insights = generate_deterministic_insights(df, kpis, total_open_exposure)

    # ── Net Order Value Spend Aggregations ──
    spend_by_vendor = df.groupby('Vendor')['Net_Order_Value_INR'].sum().reset_index().rename(columns={'Vendor':'vendor', 'Net_Order_Value_INR':'spend'}).sort_values('spend', ascending=False)
    top_supplier = spend_by_vendor.iloc[0]['vendor'] if len(spend_by_vendor) else 'N/A'
    
    spend_by_matgrp = df.groupby('Material Group')['Net_Order_Value_INR'].sum().reset_index().rename(columns={'Material Group':'material_group', 'Net_Order_Value_INR':'spend'}).sort_values('spend', ascending=False)
    top_material_group = spend_by_matgrp.iloc[0]['material_group'] if len(spend_by_matgrp) else 'N/A'
    
    spend_by_purchgrp = df.groupby('Purchasing Group')['Net_Order_Value_INR'].sum().reset_index().rename(columns={'Purchasing Group':'purchasing_group', 'Net_Order_Value_INR':'spend'}).sort_values('spend', ascending=False)
    top_purchasing_group = spend_by_purchgrp.iloc[0]['purchasing_group'] if len(spend_by_purchgrp) else 'N/A'

    # Update KPIs with Top aggregations
    kpis.update({
        'total_procurement_spend_inr': round(float(df['Net_Order_Value_INR'].sum()), 2),
        'top_supplier': top_supplier,
        'top_material_group': top_material_group,
        'top_purchasing_group': top_purchasing_group,
        'total_purchasing_groups': int(df['Purchasing Group'].nunique()),
        'total_plants': int(df['Plant'].nunique())
    })

    print("\n[5/5] Assembling output JSON...")

    all_items_cols = [
        'PO Number','PO Item','Vendor','Short Text','Plant','Material Group',
        'net_gr_qty','net_gr_val','net_ir_qty','net_ir_val',
        'open_qty','open_val','status','risk_level','risk_score',
        'aging_bucket','inv_completion_pct','reversal_pct',
        'price_var_pct','price_var_abs','days_open','posting_date','Currency'
    ]
    existing = [c for c in all_items_cols if c in df.columns]
    all_items = df[existing].copy()

    all_items['open_aging_days'] = all_items.apply(
        lambda r: int(r['days_open']) if pd.notna(r['days_open']) and r['status'] != 'Reconciled' else "",
        axis=1
    )

    all_items['posting_date'] = all_items['posting_date'].apply(
        lambda d: d.strftime('%Y-%m-%d') if pd.notna(d) else '')
    all_items = all_items.fillna('')
    all_items_list = all_items.to_dict('records')

    # Construct the final schema response payload
    output = {
        'metadata': {
            'generated_at':     ANALYSIS_DATE.strftime('%Y-%m-%d %H:%M'),
            'company':          'Syrma SGS Technology Limited',
            'plant':            '1103',
            'currency':         'INR',
            'source_files':     ['GRIR.csv','EKKO.csv','ME2N.csv'],
            'grir_row_count':   len(grir),
            'me2n_row_count':   len(me2n),
            'uploaded_at':      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'record_count':     len(grir),
            'po_count':         kpis['unique_pos']
        },
        'kpis': kpis,
        'reconciliation': {
            'matched_lines': int(df['reconciled'].sum()),
            'unmatched_lines': int((~df['reconciled']).sum()),
            'reconciliation_rate': kpis['reconciliation_rate']
        },
        'exposure': {
            'total_open_exposure': round(float(total_open_exposure), 2),
            'exposure_by_vendor': df.groupby('Vendor')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Vendor': 'vendor', 'open_val': 'open_exposure'}).sort_values('open_exposure', ascending=False).to_dict('records'),
            'exposure_by_material': df.groupby('Short Text')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Short Text': 'material', 'open_val': 'open_exposure'}).sort_values('open_exposure', ascending=False).to_dict('records'),
            'exposure_by_plant': df.groupby('Plant')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Plant': 'plant', 'open_val': 'open_exposure'}).sort_values('open_exposure', ascending=False).to_dict('records'),
            'exposure_by_purchasing_group': df.groupby('Purchasing Group')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Purchasing Group': 'purchasing_group', 'open_val': 'open_exposure'}).sort_values('open_exposure', ascending=False).to_dict('records')
        },
        'vendor_analytics': {
            'top_vendors_by_spend': spend_by_vendor.head(15).to_dict('records'),
            'top_vendors_by_exposure': df.groupby('Vendor')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Vendor': 'vendor', 'open_val': 'exposure'}).sort_values('exposure', ascending=False).head(15).to_dict('records'),
            'top_vendors_by_aging': df.groupby('Vendor')['days_open'].mean().reset_index().rename(columns={'Vendor':'vendor', 'days_open':'avg_days_open'}).fillna(0).sort_values('avg_days_open', ascending=False).head(15).to_dict('records'),
            'top_vendors_by_variance': df.groupby('Vendor')['price_var_pct'].mean().reset_index().rename(columns={'Vendor':'vendor', 'price_var_pct':'avg_price_variance'}).fillna(0).sort_values('avg_price_variance', key=abs, ascending=False).head(15).to_dict('records'),
            'vendor_concentration_pct': round(float(df.groupby('Vendor')['open_val'].sum().abs().max() / total_open_exposure * 100), 1) if total_open_exposure > 0 else 0.0,
            'vendor_dependency_pct': round(float(df.groupby('Vendor')['Net_Order_Value_INR'].sum().max() / df['Net_Order_Value_INR'].sum() * 100), 1) if df['Net_Order_Value_INR'].sum() > 0 else 0.0,
            'vendor_risk_score': vendor_risk
        },
        'material_analytics': {
            'material_spend': df.groupby('Short Text')['Net_Order_Value_INR'].sum().reset_index().rename(columns={'Short Text': 'material', 'Net_Order_Value_INR': 'spend'}).sort_values('spend', ascending=False).to_dict('records'),
            'material_exposure': df.groupby('Short Text')['open_val'].agg(lambda x: round(float(x.abs().sum()), 2)).reset_index().rename(columns={'Short Text': 'material', 'open_val': 'exposure'}).sort_values('exposure', ascending=False).to_dict('records'),
            'material_aging': df.groupby('Short Text')['days_open'].mean().reset_index().rename(columns={'Short Text': 'material', 'days_open': 'avg_days_open'}).fillna(0).sort_values('avg_days_open', ascending=False).to_dict('records'),
            'material_variance': df.groupby('Short Text')['price_var_pct'].mean().reset_index().rename(columns={'Short Text': 'material', 'price_var_pct': 'avg_price_variance'}).fillna(0).sort_values('avg_price_variance', key=abs, ascending=False).to_dict('records'),
            'material_risk_score': material_risk,
            'top_materials': df.groupby('Short Text')['Net_Order_Value_INR'].sum().reset_index().rename(columns={'Short Text': 'material', 'Net_Order_Value_INR': 'spend'}).sort_values('spend', ascending=False).head(15).to_dict('records'),
            'material_concentration': round(float(df.groupby('Short Text')['Net_Order_Value_INR'].sum().max() / df['Net_Order_Value_INR'].sum() * 100), 1) if df['Net_Order_Value_INR'].sum() > 0 else 0.0
        },
        'aging': {
            'buckets': aging,
            'vendor_aging': df.groupby(['Vendor', 'aging_bucket'])['open_val'].sum().unstack().fillna(0).reset_index().rename(columns={'Vendor': 'vendor'}).to_dict('records'),
            'material_aging': df.groupby(['Short Text', 'aging_bucket'])['open_val'].sum().unstack().fillna(0).reset_index().rename(columns={'Short Text': 'material'}).to_dict('records'),
            'plant_aging': df.groupby(['Plant', 'aging_bucket'])['open_val'].sum().unstack().fillna(0).reset_index().rename(columns={'Plant': 'plant'}).to_dict('records')
        },
        'variance': {
            'price_variance': price_var,
            'variance_pct': round(float(df['price_var_pct'].abs().mean()), 2) if len(df) else 0.0,
            'vendor_variance': df.groupby('Vendor')['price_var_pct'].mean().reset_index().rename(columns={'Vendor':'vendor', 'price_var_pct':'variance'}).fillna(0).to_dict('records'),
            'material_variance': df.groupby('Short Text')['price_var_pct'].mean().reset_index().rename(columns={'Short Text':'material', 'price_var_pct':'variance'}).fillna(0).to_dict('records'),
            'plant_variance': df.groupby('Plant')['price_var_pct'].mean().reset_index().rename(columns={'Plant':'plant', 'price_var_pct':'variance'}).fillna(0).to_dict('records')
        },
        'risks': {
            'rule_based_risks': rule_based_risks
        },
        'executive_summary': exec_sum,
        'charts': {
            'risk_level': kpis.get('risk_distribution', {}),
            'status': kpis.get('status_distribution', {})
        },
        'management_summary': {
            'analysis_date':      ANALYSIS_DATE.strftime('%d %B %Y'),
            'total_po_items':     kpis['total_po_items'],
            'open_exposure_cr':   round(abs(kpis['total_open_value'])/1e7, 2),
            'reconciliation_rate':kpis['reconciliation_rate'],
            'critical_items':     kpis['critical_items'],
            'status_distribution':kpis['status_distribution'],
            'risk_distribution':  kpis['risk_distribution'],
        },

        # ── Backward compatibility keys for dashboard UI ──
        'vendor_insights':         vendors,
        'material_insights':       materials,
        'plant_insights':          plants,
        'aging_analysis':          aging,
        'reversal_analysis':       reversals,
        'price_variance_analysis': price_var,
        'financial_impact':        fin_imp,
        'top_exceptions':          exceptions,
        'recommended_actions':     actions,
        'deterministic_insights':  deterministic_insights,
        'all_items':               all_items_list
    }

    out_path = f'{BASE_DIR}/grir_analysis_output.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, default=safe_json, indent=2)

    print(f"\n{'='*65}")
    print(f"  ✓ Output saved → {out_path}")
    print(f"  ✓ Total PO Line Items  : {kpis['total_po_items']:,}")
    print(f"  ✓ Reconciliation Rate  : {kpis['reconciliation_rate']}%")
    print(f"  ✓ Total Open Value     : ₹{kpis['total_open_value']:,.2f}")
    print(f"  ✓ Critical Items       : {kpis['critical_items']}")
    print(f"  ✓ Unique Vendors       : {kpis['unique_vendors']}")
    print(f"{'='*65}\n")


if __name__ == '__main__':
    main()
