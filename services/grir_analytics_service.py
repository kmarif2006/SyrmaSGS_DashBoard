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


# ─── Data Cleaning & Calculations ───────────────────────────────────────────
import sys
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from grir_analysis import (
    clean_grir, clean_me2n, clean_ekko,
    reconcile, build_kpis, build_aging,
    build_vendor_insights, build_material_insights, build_plant_insights,
    build_price_variance, build_reversal_analysis, build_exceptions,
    build_recommended_actions, build_executive_summary, build_financial_impact,
    classify_status, compute_risk, compute_row_risk, aging_bucket, explain,
    calculate_group_risk_scores, generate_risk_flags, generate_deterministic_insights
)
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

        def compute_expanded_columns(row):
            op_val = row.get('open_val', 0.0)
            net_gr = row.get('net_gr_val', 0.0)
            net_ir = row.get('net_ir_val', 0.0)
            days_op = row.get('days_open', 0)
            
            abs_op = abs(op_val)
            if abs_op <= 0.01:
                st = "Reconciled"
                oad = ""
            else:
                oad = int(days_op) if pd.notna(days_op) else ""
                if net_gr > 0 and net_ir == 0:
                    st = "GR Done / IR Pending"
                elif net_ir > 0 and net_gr == 0:
                    st = "IR Done / GR Pending"
                elif net_ir > net_gr and net_gr > 0:
                    st = "Invoice Greater Than GR"
                elif net_gr > net_ir and net_ir > 0:
                    st = "GR Greater Than Invoice"
                else:
                    st = "Review Required"
            return pd.Series({'status': st, 'open_aging_days': oad})

        new_cols = all_items.apply(compute_expanded_columns, axis=1)
        all_items['status'] = new_cols['status']
        all_items['open_aging_days'] = new_cols['open_aging_days']

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
            filtered = [
                item for item in filtered 
                if item.get('status') == status or 
                   (status == "IR Pending" and item.get('status') in ["GR Done / IR Pending", "GR Greater Than Invoice"]) or
                   (status == "GR Pending" and item.get('status') in ["IR Done / GR Pending", "Invoice Greater Than GR"]) or
                   (status == "Reconciled" and item.get('status') == "Reconciled")
            ]

        if risk_level:
            filtered = [item for item in filtered if item.get('risk_level') == risk_level]

        if plant:
            filtered = [item for item in filtered if str(item.get('Plant', '')) == plant]

        if sortBy:
            reverse = (sortOrder == 'desc')
            numeric_fields = ['net_gr_qty', 'net_gr_val', 'net_ir_qty', 'net_ir_val',
                              'open_qty', 'open_val', 'risk_score', 'days_open', 'open_aging_days',
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
