"""
SAP GR/IR Reconciliation Engine
Production-grade reconciliation logic with INR normalization.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta


def normalize_to_inr(df, amount_lc_col='Amt (LC)', amount_fc_col='Amt (FC)', 
                     exchange_rate_col='Exchange Rate'):
    """
    Normalize amounts to INR using Amt(LC) as primary, Amt(FC)*ExRate as fallback.
    
    Args:
        df: DataFrame with amount and exchange rate columns
        amount_lc_col: Column name for local currency amounts
        amount_fc_col: Column name for foreign currency amounts
        exchange_rate_col: Column name for exchange rates
    
    Returns:
        DataFrame with normalized INR amounts
    """
    df = df.copy()
    
    # Ensure columns exist
    if exchange_rate_col not in df.columns:
        df[exchange_rate_col] = 1.0
    if amount_lc_col not in df.columns:
        df[amount_lc_col] = 0.0
    if amount_fc_col not in df.columns:
        df[amount_fc_col] = 0.0
    
    # Ensure numeric types
    df[exchange_rate_col] = pd.to_numeric(df[exchange_rate_col], errors='coerce').fillna(1.0)
    df[exchange_rate_col] = df[exchange_rate_col].apply(lambda x: 1.0 if x <= 0 else x)
    
    df[amount_lc_col] = pd.to_numeric(df[amount_lc_col], errors='coerce').fillna(0.0)
    df[amount_fc_col] = pd.to_numeric(df[amount_fc_col], errors='coerce').fillna(0.0)
    
    # Primary: Use Amt(LC) directly (already in local currency)
    # Fallback: Use Amt(FC) * Exchange Rate
    df['Normalized_Amount_INR'] = np.where(
        df[amount_lc_col] != 0,
        df[amount_lc_col],
        df[amount_fc_col] * df[exchange_rate_col]
    )
    
    return df


def apply_dr_cr_logic(df, amount_col='Normalized_Amount_INR', dr_cr_col='Dr/Cr Ind'):
    """
    Apply debit/credit logic: S=positive, H=negative (reversal).
    
    Args:
        df: DataFrame with amount and Dr/Cr columns
        amount_col: Column name for amounts
        dr_cr_col: Column name for Dr/Cr indicator (S or H)
    
    Returns:
        DataFrame with signed amounts
    """
    df = df.copy()
    df[dr_cr_col] = df[dr_cr_col].astype(str).str.strip().fillna('S')
    
    df['Signed_Amount'] = np.where(
        df[dr_cr_col] == 'S',
        df[amount_col],
        -df[amount_col]
    )
    
    return df


def aggregate_by_po_item(grir_df, me2n_df, ekko_df, analysis_date=None):
    """
    Aggregate GRIR data by PO Number + PO Item (reconciliation key).
    Join with ME2N and EKKO for comprehensive reconciliation.
    
    Args:
        grir_df: GR/IR posting records
        me2n_df: Purchase order details
        ekko_df: Purchase order headers with exchange rates
        analysis_date: Date for aging calculation (default: today)
    
    Returns:
        Reconciled DataFrame with all metrics
    """
    if analysis_date is None:
        analysis_date = pd.Timestamp(datetime.now())
    
    print("  Aggregating GRIR by PO Number + PO Item...")
    
    # Ensure required columns exist
    required_grir = ['PO Number', 'PO Item', 'Trans Type', 'Dr/Cr Ind', 
                     'Quantity', 'Amt (LC)', 'Posting Date']
    for col in required_grir:
        if col not in grir_df.columns:
            grir_df[col] = 0 if col in ['Quantity', 'Amt (LC)'] else ''
    
    # Normalize amounts
    grir_df = normalize_to_inr(grir_df, 'Amt (LC)', 'Amt (FC)', 'Exchange Rate')
    grir_df = apply_dr_cr_logic(grir_df, 'Normalized_Amount_INR', 'Dr/Cr Ind')
    
    # Classify transactions by type and sign
    grir_df['gr_qty'] = np.where(grir_df['Trans Type'] == '1', grir_df['Quantity'], 0)
    grir_df['gr_qty_signed'] = np.where(grir_df['Trans Type'] == '1', 
                                        np.where(grir_df['Dr/Cr Ind'] == 'S', 
                                                grir_df['Quantity'], -grir_df['Quantity']), 0)
    grir_df['gr_val_signed'] = np.where(grir_df['Trans Type'] == '1', grir_df['Signed_Amount'], 0)
    
    grir_df['ir_qty'] = np.where(grir_df['Trans Type'] == '2', grir_df['Quantity'], 0)
    grir_df['ir_qty_signed'] = np.where(grir_df['Trans Type'] == '2',
                                        np.where(grir_df['Dr/Cr Ind'] == 'S',
                                                grir_df['Quantity'], -grir_df['Quantity']), 0)
    grir_df['ir_val_signed'] = np.where(grir_df['Trans Type'] == '2', grir_df['Signed_Amount'], 0)
    
    # Aggregate GR transactions
    gr_agg = grir_df[grir_df['Trans Type'] == '1'].groupby(['PO Number', 'PO Item']).agg(
        gr_qty_total=('gr_qty_signed', 'sum'),
        gr_val_total=('gr_val_signed', 'sum'),
        gr_txn_count=('Quantity', 'count'),
        posting_date_gr=('Posting Date', 'min'),
    ).reset_index()
    
    # Aggregate IR transactions
    ir_agg = grir_df[grir_df['Trans Type'] == '2'].groupby(['PO Number', 'PO Item']).agg(
        ir_qty_total=('ir_qty_signed', 'sum'),
        ir_val_total=('ir_val_signed', 'sum'),
        ir_txn_count=('Quantity', 'count'),
        posting_date_ir=('Posting Date', 'min'),
    ).reset_index()
    
    # Prepare ME2N with exchange rates
    if ekko_df is not None and not ekko_df.empty:
        ekko_rates = ekko_df[['Purchasing Document', 'Exchange Rate', 'Currency']].drop_duplicates(
            subset=['Purchasing Document']
        )
        me2n_merged = me2n_df.merge(
            ekko_rates.rename(columns={'Purchasing Document': 'Purchasing Document', 
                                       'Currency': 'PO_Currency'}),
            on='Purchasing Document',
            how='left'
        )
    else:
        me2n_merged = me2n_df.copy()
        me2n_merged['Exchange Rate'] = 1.0
        me2n_merged['PO_Currency'] = 'INR'
    
    me2n_merged['Exchange Rate'] = me2n_merged['Exchange Rate'].fillna(1.0)
    me2n_merged['Exchange Rate'] = me2n_merged['Exchange Rate'].apply(lambda x: 1.0 if x <= 0 else x)
    
    # Normalize ME2N amounts to INR
    me2n_merged['Net_Order_Value_INR'] = (me2n_merged.get('Net Order Value', 0) * 
                                          me2n_merged['Exchange Rate'])
    me2n_merged['Open_Value_INR'] = (me2n_merged.get('Open value', 0) * 
                                     me2n_merged['Exchange Rate'])
    
    # Prepare PO line details
    po_lines = me2n_merged.rename(columns={
        'Purchasing Document': 'PO Number',
        'Item': 'PO Item',
    }).copy()
    
    required_cols = ['PO Number', 'PO Item', 'Order Quantity', 'Still to be delivered (qty)',
                     'Net Order Value', 'Open value', 'Net Price', 'Net_Order_Value_INR',
                     'Open_Value_INR', 'Exchange Rate']
    for col in required_cols:
        if col not in po_lines.columns:
            po_lines[col] = 0.0 if col.endswith('value') or col.endswith('Quantity') or col == 'Net Price' else ''
    
    # Merge: PO Lines + GR + IR
    # Select columns carefully - only include those that exist
    base_cols = ['PO Number', 'PO Item', 'Order Quantity', 'Still to be delivered (qty)',
                 'Net Order Value', 'Open value', 'Net Price', 'Net_Order_Value_INR',
                 'Open_Value_INR', 'Exchange Rate']
    
    # Add optional columns if they exist
    optional_cols = ['Plant', 'Vendor', 'Short Text', 'Material', 'Material Group', 
                     'Purchasing Group', 'Document Date', 'Delivery date', 'Company Code', 
                     'PO_Currency']
    for col in optional_cols:
        if col in po_lines.columns and col not in base_cols:
            base_cols.append(col)
    
    # Add any remaining columns not in base set
    remaining_cols = [c for c in po_lines.columns if c not in base_cols]
    select_cols = base_cols + remaining_cols
    
    reconciled = po_lines[select_cols].copy()
    
    reconciled = reconciled.merge(gr_agg, on=['PO Number', 'PO Item'], how='left')
    reconciled = reconciled.merge(ir_agg, on=['PO Number', 'PO Item'], how='left')
    
    # Fill NaN with 0
    numeric_cols = ['gr_qty_total', 'gr_val_total', 'ir_qty_total', 'ir_val_total',
                   'gr_txn_count', 'ir_txn_count']
    for col in numeric_cols:
        if col in reconciled.columns:
            reconciled[col] = reconciled[col].fillna(0)
    
    # Calculate net quantities and values
    reconciled['Net_GR_Qty'] = reconciled['Order Quantity'] - reconciled['Still to be delivered (qty)']
    reconciled['Net_GR_Val_INR'] = reconciled['Net_Order_Value_INR'] - (
        reconciled.get('Still to be delivered (value)', 0) * reconciled['Exchange Rate']
    )
    reconciled['Net_IR_Qty'] = reconciled.get('ir_qty_total', 0)
    reconciled['Net_IR_Val_INR'] = reconciled.get('ir_val_total', 0)
    
    # Calculate open quantities and values
    reconciled['Open_Qty'] = reconciled['Net_GR_Qty'] - reconciled['Net_IR_Qty']
    reconciled['Open_Val_INR'] = reconciled['Net_GR_Val_INR'] - reconciled['Net_IR_Val_INR']
    reconciled['Open_Exposure_INR'] = reconciled['Open_Val_INR'].abs()
    
    # Posting date for aging
    reconciled['Posting_Date'] = reconciled.get('posting_date_ir')
    mask_no_ir = reconciled['Posting_Date'].isna()
    if 'posting_date_gr' in reconciled.columns:
        reconciled.loc[mask_no_ir, 'Posting_Date'] = reconciled.loc[mask_no_ir, 'posting_date_gr']
    mask_still_none = reconciled['Posting_Date'].isna()
    reconciled.loc[mask_still_none, 'Posting_Date'] = reconciled.loc[mask_still_none, 'Document Date']
    
    # Calculate days open
    reconciled['Days_Open'] = (analysis_date - pd.to_datetime(reconciled['Posting_Date'], format='mixed', errors='coerce')).dt.days
    reconciled['Days_Open'] = reconciled['Days_Open'].fillna(0).astype(int)
    
    # Classify reconciliation status
    tolerance = 0.01
    reconciled['Status'] = _classify_status(reconciled, tolerance)
    
    # Calculate aging bucket
    reconciled['Aging_Bucket'] = reconciled['Days_Open'].apply(_aging_bucket)
    
    print(f"  Aggregation complete: {len(reconciled):,} PO line items")
    return reconciled


def _classify_status(df, tolerance=0.01):
    """Classify reconciliation status for each row."""
    status = np.full(len(df), 'No Activity', dtype=object)
    
    # Determine status based on quantities and values
    has_gr = df['Net_GR_Qty'].abs() > tolerance
    has_ir = df['Net_IR_Qty'].abs() > tolerance
    open_qty = df['Open_Qty'].abs()
    open_val = df['Open_Val_INR'].abs()
    
    # GR Done: No open exposure
    status[open_val <= tolerance] = 'GR Done'
    
    # IR Pending: GR > IR (invoicing pending)
    status[(has_gr & ~has_ir) | ((df['Net_GR_Val_INR'] > df['Net_IR_Val_INR']) & (open_val > tolerance))] = 'IR Pending'
    
    # GR Pending: IR > GR (goods receipt pending)
    status[(has_ir & ~has_gr) | ((df['Net_IR_Val_INR'] > df['Net_GR_Val_INR']) & (open_val > tolerance))] = 'GR Pending'
    
    # No Activity: Both zero
    status[~has_gr & ~has_ir] = 'No Activity'
    
    return status


def _aging_bucket(days):
    """Classify days into aging bucket."""
    if pd.isna(days) or days is None:
        return 'Unknown'
    days = int(days)
    if days <= 30:
        return '0-30 Days'
    elif days <= 60:
        return '31-60 Days'
    elif days <= 90:
        return '61-90 Days'
    elif days <= 180:
        return '91-180 Days'
    else:
        return '180+ Days'
