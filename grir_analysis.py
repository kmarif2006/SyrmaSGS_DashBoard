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
import warnings
warnings.filterwarnings('ignore')

ANALYSIS_DATE = datetime(2026, 6, 5)
BASE_DIR = r'c:\SyrmaSGS_DashBoard'


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING & CLEANING
# ─────────────────────────────────────────────────────────────────────────────

def load_data():
    print("  Loading GRIR.csv ...")
    grir = pd.read_csv(f'{BASE_DIR}/grir.csv', low_memory=False)
    print(f"    -> {len(grir):,} rows")

    print("  Loading EKKO.csv ...")
    ekko = pd.read_csv(f'{BASE_DIR}/EKKO.csv', low_memory=False)
    print(f"    -> {len(ekko):,} rows")

    print("  Loading ME2N.csv ...")
    me2n = pd.read_csv(f'{BASE_DIR}/me2n.csv', low_memory=False)
    print(f"    -> {len(me2n):,} rows")

    return grir, ekko, me2n


def clean_grir(grir):
    grir.columns = grir.columns.str.strip()
    grir['PO Number']    = grir['PO Number'].astype(str).str.strip()
    grir['PO Item']      = pd.to_numeric(grir['PO Item'], errors='coerce').fillna(0).astype(int).astype(str)
    grir['Trans Type']   = grir['Trans Type'].astype(str).str.strip()
    grir['Dr/Cr Ind']    = grir['Dr/Cr Ind'].astype(str).str.strip()
    grir['Quantity']     = pd.to_numeric(grir['Quantity'], errors='coerce').fillna(0)
    grir['Amt (LC)']     = pd.to_numeric(grir['Amt (LC)'], errors='coerce').fillna(0)
    grir['Posting Date'] = pd.to_datetime(grir['Posting Date'], errors='coerce')
    grir['Document Date']= pd.to_datetime(grir['Document Date'], errors='coerce')
    grir['Plant']        = grir['Plant'].astype(str).str.strip()

    # Signed values: S=Debit(+), H=Credit(-)
    grir['Signed Amt'] = np.where(grir['Dr/Cr Ind'] == 'S',  grir['Amt (LC)'], -grir['Amt (LC)'])
    grir['Signed Qty'] = np.where(grir['Dr/Cr Ind'] == 'S',  grir['Quantity'], -grir['Quantity'])
    return grir


def clean_me2n(me2n):
    me2n.columns = me2n.columns.str.strip()
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

    # Clean supplier name
    for col in ['Name of Supplier', 'Supplier/Supplying Plant']:
        if col in me2n.columns:
            me2n[col] = me2n[col].astype(str).str.strip()

    if 'Name of Supplier' in me2n.columns:
        me2n['Vendor'] = me2n['Name of Supplier']
    elif 'Supplier/Supplying Plant' in me2n.columns:
        me2n['Vendor'] = me2n['Supplier/Supplying Plant']
    else:
        me2n['Vendor'] = ''

    # Clean vendor: remove leading numeric ID
    import re
    me2n['Vendor'] = me2n['Vendor'].apply(lambda v: re.sub(r'^\d+\s+', '', str(v)).strip())

    me2n['Short Text'] = me2n.get('Short Text', pd.Series('', index=me2n.index)).astype(str).str.strip()
    me2n['Material']   = me2n.get('Material', pd.Series('', index=me2n.index)).astype(str).str.strip()
    me2n['Plant']      = me2n['Plant'].astype(str).str.strip()
    me2n['Material Group'] = me2n.get('Material Group', pd.Series('', index=me2n.index)).astype(str).str.strip()
    me2n['Deletion indicator'] = me2n.get('Deletion indicator', pd.Series('', index=me2n.index)).astype(str).str.strip()
    me2n['Document Date']= pd.to_datetime(me2n.get('Document Date', pd.Series()), errors='coerce')
    me2n['Delivery date']= pd.to_datetime(me2n.get('Delivery date', pd.Series()), errors='coerce')
    return me2n


def clean_ekko(ekko):
    ekko.columns = ekko.columns.str.strip()
    ekko['Purchasing Document'] = ekko['Purchasing Document'].astype(str).str.strip()
    ekko['Company Code']        = ekko.get('Company Code', pd.Series()).astype(str).str.strip()
    ekko['Currency']            = ekko.get('Currency', pd.Series('INR')).astype(str).str.strip()
    ekko['Exchange Rate']       = pd.to_numeric(ekko.get('Exchange Rate', 1), errors='coerce').fillna(1)
    return ekko


# ─────────────────────────────────────────────────────────────────────────────
# AGING
# ─────────────────────────────────────────────────────────────────────────────

def aging_bucket(posting_date):
    if pd.isna(posting_date):
        return '365+'
    days = (ANALYSIS_DATE - posting_date).days
    if days <= 30:   return '0-30'
    if days <= 60:   return '31-60'
    if days <= 90:   return '61-90'
    if days <= 180:  return '91-180'
    if days <= 365:  return '181-365'
    return '365+'


# ─────────────────────────────────────────────────────────────────────────────
# STATUS CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def classify_status(row):
    gr_qty   = row['net_gr_qty']
    ir_qty   = row['net_ir_qty']
    open_qty = row['open_qty']
    open_val = row['open_val']
    rev_pct  = row['reversal_pct']
    tol = 0.01

    if rev_pct >= 99:
        return 'FULLY REVERSED'

    if abs(gr_qty) < tol and abs(ir_qty) < tol:
        return 'FULLY REVERSED'

    if abs(gr_qty) < tol and ir_qty > tol:
        return 'IR ONLY'

    if gr_qty > tol and abs(ir_qty) < tol:
        if rev_pct > 0:
            return 'PARTIALLY REVERSED'
        return 'GR ONLY'

    if abs(open_qty) < tol and abs(open_val) < 1:
        return 'FULLY RECONCILED'

    if abs(open_qty) < tol and abs(open_val) >= 1:
        return 'PRICE VARIANCE'

    if open_qty < -tol:
        return 'OVER INVOICED'

    if open_qty > tol:
        if ir_qty > tol:
            return 'PARTIALLY INVOICED'
        return 'GR ONLY'

    return 'PARTIALLY INVOICED'


# ─────────────────────────────────────────────────────────────────────────────
# RISK SCORING
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


# ─────────────────────────────────────────────────────────────────────────────
# NARRATIVE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def explain(row):
    s   = row['status']
    gq  = row['net_gr_qty']
    iq  = row['net_ir_qty']
    oq  = row['open_qty']
    ov  = row['open_val']
    # Handle both 'Vendor' (DataFrame col) and 'vendor' (dict key) safely
    raw_vendor = row.get('Vendor', row.get('vendor', 'Vendor')) if hasattr(row, 'get') else getattr(row, 'Vendor', 'Vendor')
    v   = str(raw_vendor)[:40] if raw_vendor and str(raw_vendor) not in ('nan','None','') else 'Vendor'
    pct = row['inv_completion_pct']

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
# MAIN RECONCILIATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def reconcile(grir, me2n, ekko):
    print("  Building GRIR aggregates by PO+Item ...")
    # Aggregate GRIR
    gr_agg = grir[grir['Trans Type'] == '1'].groupby(['PO Number','PO Item']).agg(
        gr_qty_s   = ('Signed Qty', lambda x: x[grir.loc[x.index,'Dr/Cr Ind']=='S'].sum()),
        gr_qty_h   = ('Quantity',   lambda x: x[grir.loc[x.index,'Dr/Cr Ind']=='H'].sum()),
        gr_val_s   = ('Signed Amt', lambda x: x[grir.loc[x.index,'Dr/Cr Ind']=='S'].sum()),
        gr_val_h   = ('Amt (LC)',   lambda x: x[grir.loc[x.index,'Dr/Cr Ind']=='H'].sum()),
        gr_txn_count = ('Quantity', 'count'),
        earliest_gr  = ('Posting Date', 'min'),
        latest_gr    = ('Posting Date', 'max'),
    ).reset_index()

    ir_agg = grir[grir['Trans Type'] == '2'].groupby(['PO Number','PO Item']).agg(
        ir_qty_s   = ('Quantity',  lambda x: x[grir.loc[x.index,'Dr/Cr Ind']=='S'].sum()),
        ir_qty_h   = ('Quantity',  lambda x: x[grir.loc[x.index,'Dr/Cr Ind']=='H'].sum()),
        ir_val_s   = ('Amt (LC)',  lambda x: x[grir.loc[x.index,'Dr/Cr Ind']=='S'].sum()),
        ir_val_h   = ('Amt (LC)',  lambda x: x[grir.loc[x.index,'Dr/Cr Ind']=='H'].sum()),
        ir_txn_count = ('Quantity','count'),
        ir_doc_count = ('Document No','nunique') if 'Document No' in grir.columns else ('Quantity','count'),
        earliest_ir  = ('Posting Date','min'),
        latest_ir    = ('Posting Date','max'),
        earliest_doc_date = ('Document Date','min'),
    ).reset_index()

    print("  Merging with ME2N ...")
    me2n_key = me2n[['Purchasing Document','Item',
                      'Vendor','Short Text','Material','Material Group','Plant',
                      'Order Quantity','Still to be delivered (qty)',
                      'Net Price','Net Order Value',
                      'Still to be invoiced (qty)','Still to be invoiced (val.)',
                      'Open value','Total open value',
                      'Still to be delivered (value)',
                      'Deletion indicator','Document Date','Delivery date',
                      'Purchasing Group']].copy()
    me2n_key.rename(columns={
        'Purchasing Document': 'PO Number',
        'Item': 'PO Item',
    }, inplace=True)

    # Start from ME2N (authoritative PO line positions)
    df = me2n_key.copy()

    # Merge IR aggregates
    df = df.merge(ir_agg, on=['PO Number','PO Item'], how='left')
    # Merge GR aggregates
    df = df.merge(gr_agg, on=['PO Number','PO Item'], how='left')

    # Fill NaN
    num_cols = ['gr_qty_s','gr_qty_h','gr_val_s','gr_val_h',
                'ir_qty_s','ir_qty_h','ir_val_s','ir_val_h',
                'ir_txn_count','ir_doc_count','gr_txn_count']
    for c in num_cols:
        if c in df.columns:
            df[c] = df[c].fillna(0)

    # ── Net GR and IR from GRIR postings
    df['net_gr_qty_grir'] = df.get('gr_qty_s', 0) - df.get('gr_qty_h', 0)
    df['net_gr_val_grir'] = df.get('gr_val_s', 0) - df.get('gr_val_h', 0)
    df['net_ir_qty']      = df.get('ir_qty_s', 0) - df.get('ir_qty_h', 0)
    df['net_ir_val']      = df.get('ir_val_s', 0) - df.get('ir_val_h', 0)

    # ── Derive GR from ME2N: GR = Order Qty - Still to deliver
    df['net_gr_qty'] = df['Order Quantity'] - df['Still to be delivered (qty)']
    # GR value = Net Order Value - still to deliver value
    df['net_gr_val'] = df['Net Order Value'] - df['Still to be delivered (value)']

    # ── Use IR from GRIR; if GR-side GRIR data exists, use it (override)
    mask_gr = df['net_gr_qty_grir'].abs() > 0
    df.loc[mask_gr, 'net_gr_qty'] = df.loc[mask_gr, 'net_gr_qty_grir']
    df.loc[mask_gr, 'net_gr_val'] = df.loc[mask_gr, 'net_gr_val_grir']

    # ── For rows with no GRIR IR postings, use ME2N "still to invoice" as open position
    mask_no_ir = df['net_ir_qty'] == 0
    # net_ir = gr - still_to_invoice
    df.loc[mask_no_ir, 'net_ir_qty'] = df.loc[mask_no_ir, 'net_gr_qty'] - df.loc[mask_no_ir, 'Still to be invoiced (qty)']
    df.loc[mask_no_ir, 'net_ir_val'] = df.loc[mask_no_ir, 'net_gr_val'] - df.loc[mask_no_ir, 'Still to be invoiced (val.)']

    # ── Open quantities
    df['open_qty'] = df['net_gr_qty'] - df['net_ir_qty']
    df['open_val'] = df['net_gr_val'] - df['net_ir_val']

    # Cross-check with ME2N still to invoice
    # Where ME2N says still_to_invoice > 0 and we computed open_qty ≈ 0, trust ME2N
    mask_me2n_open = (df['Still to be invoiced (qty)'].abs() > 0.01) & (df['open_qty'].abs() < 0.01)
    df.loc[mask_me2n_open, 'open_qty'] = df.loc[mask_me2n_open, 'Still to be invoiced (qty)']
    df.loc[mask_me2n_open, 'open_val'] = df.loc[mask_me2n_open, 'Still to be invoiced (val.)']

    # ── Invoice completion %
    df['inv_completion_pct'] = np.where(
        df['net_gr_qty'] > 0,
        (df['net_ir_qty'] / df['net_gr_qty'] * 100).clip(-200, 200),
        0
    )

    # ── Reversal analysis
    df['ir_reversal_qty'] = df.get('ir_qty_h', 0)
    df['ir_reversal_val'] = df.get('ir_val_h', 0)
    df['gr_reversal_qty'] = df.get('gr_qty_h', 0)
    df['gr_reversal_val'] = df.get('gr_val_h', 0)
    df['reversal_pct']    = np.where(
        df.get('ir_qty_s', 0) > 0,
        (df.get('ir_qty_h', 0) / df.get('ir_qty_s', 1) * 100).clip(0, 100),
        0
    )

    # ── Price variance
    df['price_var_abs'] = np.where(
        (df['Net Price'] > 0) & (df['net_ir_qty'] > 0),
        df['net_ir_val'] - (df['net_ir_qty'] * df['Net Price']),
        0
    )
    df['price_var_pct'] = np.where(
        (df['Net Price'] > 0) & (df['net_ir_qty'] > 0),
        (df['price_var_abs'] / (df['net_ir_qty'] * df['Net Price']) * 100).clip(-200, 200),
        0
    )

    # ── Posting date (earliest meaningful)
    df['posting_date'] = df.get('earliest_ir', pd.NaT)
    mask_no_posting = df['posting_date'].isna()
    if 'earliest_gr' in df.columns:
        df.loc[mask_no_posting, 'posting_date'] = df.loc[mask_no_posting, 'earliest_gr']
    mask_still_no = df['posting_date'].isna()
    df.loc[mask_still_no, 'posting_date'] = df.loc[mask_still_no, 'Document Date']

    # ── Aging
    df['aging_bucket'] = df['posting_date'].apply(aging_bucket)

    # ── Classify status
    df['status'] = df.apply(classify_status, axis=1)

    # ── Risk scoring
    risk = df.apply(lambda r: compute_risk(
        r['status'], r['open_val'], r['aging_bucket'],
        r['reversal_pct'], r['price_var_pct']), axis=1)
    df['risk_score'] = risk.apply(lambda x: x[0])
    df['risk_level'] = risk.apply(lambda x: x[1])

    # ── Merge EKKO for currency / company code
    ekko_mini = ekko[['Purchasing Document','Company Code','Currency']].copy()
    ekko_mini.rename(columns={'Purchasing Document': 'PO Number'}, inplace=True)
    df = df.merge(ekko_mini, on='PO Number', how='left')
    df['Currency'] = df['Currency'].fillna('INR')

    # ── Days since posting
    df['days_open'] = df['posting_date'].apply(
        lambda d: (ANALYSIS_DATE - d).days if pd.notna(d) else None)

    print(f"  Reconciliation complete: {len(df):,} PO line items")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_kpis(df):
    total_items  = len(df)
    total_gr_val = df['net_gr_val'].sum()
    total_ir_val = df['net_ir_val'].sum()
    total_open   = df['open_val'].sum()
    total_open_q = df['open_qty'].sum()

    recon_count = (df['status'] == 'FULLY RECONCILED').sum()
    recon_rate  = recon_count / total_items * 100 if total_items else 0

    status_dist = df['status'].value_counts().to_dict()
    risk_dist   = df['risk_level'].value_counts().to_dict()

    pending_invoice_val = df[df['status'].isin(['GR ONLY','PARTIALLY INVOICED'])]['open_val'].sum()
    over_inv_val        = df[df['status'] == 'OVER INVOICED']['open_val'].abs().sum()
    ir_only_val         = df[df['status'] == 'IR ONLY']['net_ir_val'].sum()
    total_reversals_val = df['ir_reversal_val'].sum()

    return {
        'total_po_items':        int(total_items),
        'total_gr_value':        round(float(total_gr_val), 2),
        'total_ir_value':        round(float(total_ir_val), 2),
        'total_open_value':      round(float(total_open), 2),
        'total_open_qty':        round(float(total_open_q), 2),
        'reconciliation_rate':   round(float(recon_rate), 1),
        'reconciled_count':      int(recon_count),
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
    }


def build_aging(df):
    buckets = ['0-30','31-60','61-90','91-180','181-365','365+']
    result = []
    for b in buckets:
        sub = df[df['aging_bucket'] == b]
        open_sub = sub[sub['status'] != 'FULLY RECONCILED']
        result.append({
            'bucket':          b,
            'total_count':     int(len(sub)),
            'open_count':      int(len(open_sub)),
            'open_value':      round(float(open_sub['open_val'].sum()), 2),
            'gr_only_val':     round(float(sub[sub['status']=='GR ONLY']['open_val'].sum()), 2),
            'partial_inv_val': round(float(sub[sub['status']=='PARTIALLY INVOICED']['open_val'].sum()), 2),
            'over_inv_val':    round(float(sub[sub['status']=='OVER INVOICED']['open_val'].abs().sum()), 2),
            'ir_only_val':     round(float(sub[sub['status']=='IR ONLY']['net_ir_val'].sum()), 2),
        })
    return result


def build_vendor_insights(df):
    total_open = df['open_val'].sum()
    vendors = []
    for vendor, vdf in df.groupby('Vendor'):
        if not vendor or vendor in ('nan','','None','NaN'):
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
            'pending_invoice':  round(float(vdf[vdf['status'].isin(['GR ONLY','PARTIALLY INVOICED'])]['open_val'].sum()), 2),
            'over_invoiced':    round(float(vdf[vdf['status']=='OVER INVOICED']['open_val'].abs().sum()), 2),
        })

    return sorted(vendors, key=lambda x: abs(x['open_value']), reverse=True)[:30]


def build_material_insights(df):
    mats = []
    for mat, mdf in df.groupby('Short Text'):
        if not mat or mat in ('nan','','None','NaN'):
            continue
        mats.append({
            'material':    str(mat)[:80],
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
        if not plant or plant in ('nan','','None','NaN'):
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
    exc_df = df[~df['status'].isin(['FULLY RECONCILED','FULLY REVERSED'])].copy()
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

    old_items = df[df['aging_bucket'].isin(['181-365','365+']) & (df['open_val'].abs() > 1000)]
    if len(old_items):
        actions.append({
            'priority':   'HIGH',
            'category':   'Aging GR/IR Clearance',
            'action':     f"Clear {len(old_items)} items aged >180 days. Total value: INR {old_items['open_val'].abs().sum():,.0f}. Write off irrecoverable balances with management approval.",
            'owner':      'Finance Controller',
            'impact':     'Cleanse BS; reduce audit risk; improve GR/IR account accuracy.',
            'timeline':   'Before month-end close',
        })

    partial = df[df['status'] == 'PARTIALLY INVOICED']
    if len(partial):
        actions.append({
            'priority':   'MEDIUM',
            'category':   'Partial Invoice Completion',
            'action':     f"Follow up with vendors on {len(partial)} partially invoiced PO items. Pending value: INR {partial['open_val'].sum():,.0f}.",
            'owner':      'AP Team',
            'impact':     'Accurate vendor liability booking; timely payment to vendors.',
            'timeline':   'Within 14 business days',
        })

    pv_items = df[abs(df['price_var_pct']) > 10]
    if len(pv_items):
        actions.append({
            'priority':   'MEDIUM',
            'category':   'Price Variance Resolution',
            'action':     f"Review {len(pv_items)} items with >10% price variance. Raise vendor debit/credit memos or renegotiate PO. Total variance: INR {pv_items['price_var_abs'].abs().sum():,.0f}.",
            'owner':      'Procurement / Finance',
            'impact':     'Accurate inventory and COGS; vendor contract compliance.',
            'timeline':   'Within 21 business days',
        })

    actions.append({
        'priority':   'LOW',
        'category':   'Month-End Accrual Posting',
        'action':     f"Post accrual journals for all GR-Only and Partially Invoiced items before period close. Total accrual required: INR {(kpis['pending_invoice_val']):,.0f}.",
        'owner':      'Finance Team',
        'impact':     'Accurate P&L; GRIR account reconciliation for auditors.',
        'timeline':   'Last 2 working days of each month',
    })

    return actions


def build_executive_summary(df, kpis):
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
    if (df['aging_bucket'].isin(['181-365','365+'])).sum() > 0:
        old_val = df[df['aging_bucket'].isin(['181-365','365+'])]['open_val'].abs().sum()
        risk_flags.append(f"INR {old_val/1e7:.2f} Cr in items aged >180 days — overdue for clearance")
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


# ─────────────────────────────────────────────────────────────────────────────
# JSON SERIALIZER
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*65)
    print("  SAP GR/IR RECONCILIATION ANALYSIS ENGINE - Syrma SGS")
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

    print("\n[5/5] Assembling output JSON...")

    # All items (safe subset for UI table)
    all_items_cols = [
        'PO Number','PO Item','Vendor','Short Text','Plant','Material Group',
        'net_gr_qty','net_gr_val','net_ir_qty','net_ir_val',
        'open_qty','open_val','status','risk_level','risk_score',
        'aging_bucket','inv_completion_pct','reversal_pct',
        'price_var_pct','price_var_abs','days_open','posting_date','Currency'
    ]
    existing = [c for c in all_items_cols if c in df.columns]
    all_items = df[existing].copy()
    all_items['posting_date'] = all_items['posting_date'].apply(
        lambda d: d.strftime('%Y-%m-%d') if pd.notna(d) else '')
    all_items = all_items.fillna('')
    all_items_list = all_items.to_dict('records')

    output = {
        'metadata': {
            'generated_at':     ANALYSIS_DATE.strftime('%Y-%m-%d %H:%M'),
            'company':          'Syrma SGS Technology Limited',
            'company_code':     '1100',
            'plant':            '1103',
            'currency':         'INR',
            'source_files':     ['GRIR.csv','EKKO.csv','ME2N.csv'],
            'grir_row_count':   len(grir),
            'me2n_row_count':   len(me2n),
        },
        'executive_summary':       exec_sum,
        'kpis':                    kpis,
        'vendor_insights':         vendors,
        'material_insights':       materials,
        'plant_insights':          plants,
        'aging_analysis':          aging,
        'reversal_analysis':       reversals,
        'price_variance_analysis': price_var,
        'financial_impact':        fin_imp,
        'top_exceptions':          exceptions,
        'recommended_actions':     actions,
        'management_summary': {
            'analysis_date':      ANALYSIS_DATE.strftime('%d %B %Y'),
            'total_po_items':     kpis['total_po_items'],
            'open_exposure_cr':   round(abs(kpis['total_open_value'])/1e7, 2),
            'reconciliation_rate':kpis['reconciliation_rate'],
            'critical_items':     kpis['critical_items'],
            'status_distribution':kpis['status_distribution'],
            'risk_distribution':  kpis['risk_distribution'],
        },
        'all_items': all_items_list,
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
    print(f"  ✓ Status Distribution  : {kpis['status_distribution']}")
    print(f"{'='*65}\n")


if __name__ == '__main__':
    main()
