"""
SAP GR/IR Reconciliation Engine
Production-grade reconciliation logic with INR normalization based on actual ledger postings.
"""

import numpy as np
import pandas as pd
from datetime import datetime


def aggregate_by_po_item(grir_df, me2n_df, ekko_df, analysis_date=None):
    """
    Aggregate GRIR data by PO Number + PO Item (reconciliation key).
    Join with ME2N and EKKO for master data enrichment and currency conversion fallbacks.
    
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
    else:
        analysis_date = pd.Timestamp(analysis_date)
        
    grir_df = grir_df.copy()
    me2n_df = me2n_df.copy()
    ekko_df = ekko_df.copy()

    # Strip column names
    grir_df.columns = grir_df.columns.str.strip()
    me2n_df.columns = me2n_df.columns.str.strip()
    ekko_df.columns = ekko_df.columns.str.strip()

    # Ensure Vendor, Plant and other columns exist or are mapped in me2n_df
    if 'Purchasing Document' in me2n_df.columns:
        me2n_df = me2n_df.rename(columns={'Purchasing Document': 'PO Number'})
    if 'Item' in me2n_df.columns:
        me2n_df = me2n_df.rename(columns={'Item': 'PO Item'})

    if 'Vendor' not in me2n_df.columns:
        if 'Name of Supplier' in me2n_df.columns and me2n_df['Name of Supplier'].dropna().any():
            me2n_df['Vendor'] = me2n_df['Name of Supplier']
        elif 'Supplier/Supplying Plant' in me2n_df.columns:
            me2n_df['Vendor'] = me2n_df['Supplier/Supplying Plant']
        else:
            me2n_df['Vendor'] = 'Unknown'

    import re
    me2n_df['Vendor'] = me2n_df['Vendor'].apply(lambda v: re.sub(r'^\d+\s+', '', str(v)).strip() if pd.notna(v) and str(v) != 'nan' else 'Unknown')

    cols_to_ensure = {
        'Plant': 'Unknown', 'Material': 'Unknown', 'Material Group': 'Unknown',
        'Short Text': 'Unknown', 'Purchasing Group': 'Unknown', 'Order Quantity': 0.0,
        'Net Order Value': 0.0, 'Open value': 0.0, 'Still to be delivered (qty)': 0.0,
        'Still to be invoiced (qty)' : 0.0, 'Still to be invoiced (val.)': 0.0,
        'Document Date': pd.NaT, 'Delivery date': pd.NaT
    }
    for col, default in cols_to_ensure.items():
        if col not in me2n_df.columns:
            me2n_df[col] = default
            
    # Standardize keys: convert to string and strip spaces
    grir_df['PO Number'] = grir_df['PO Number'].astype(str).str.strip()
    grir_df['PO Item'] = pd.to_numeric(grir_df['PO Item'], errors='coerce').fillna(0).astype(int).astype(str)
    
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
        (op_val.abs() <= 0.01),
        (net_gr > 0) & (net_ir == 0),
        (net_ir > 0) & (net_gr == 0),
        (net_ir > net_gr) & (net_gr > 0),
        (net_gr > net_ir) & (net_ir > 0),
    ]
    status_choices = [
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
            
    cond_ir_pending = agg_df['Status'].isin(['GR Done / IR Pending', 'GR Greater Than Invoice'])
    cond_gr_pending = agg_df['Status'].isin(['IR Done / GR Pending', 'Invoice Greater Than GR'])
    cond_recon = agg_df['Status'] == 'Reconciled'
    cond_else = ~(cond_ir_pending | cond_gr_pending | cond_recon)
    
    agg_df['Aging_Start_Date'] = pd.NaT
    agg_df.loc[cond_ir_pending, 'Aging_Start_Date'] = first_gr
    agg_df.loc[cond_gr_pending, 'Aging_Start_Date'] = first_ir
    agg_df.loc[cond_recon, 'Aging_Start_Date'] = max_last
    agg_df.loc[cond_else, 'Aging_Start_Date'] = doc_date
    
    agg_df['Aging_Start_Date'] = pd.to_datetime(agg_df['Aging_Start_Date'])
    
    # Calculate Days Open
    analysis_date_dt = pd.to_datetime(analysis_date)
    agg_df['Days_Open'] = (analysis_date_dt - agg_df['Aging_Start_Date']).dt.days
    agg_df['Days_Open'] = agg_df['Days_Open'].fillna(0).astype(int)
    
    # Classify into aging bucket
    agg_df['Aging_Bucket'] = agg_df['Days_Open'].apply(_aging_bucket)
    
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
    agg_df['Posting_Date'] = agg_df['Aging_Start_Date']
    agg_df['posting_date'] = agg_df['Aging_Start_Date']
    agg_df['net_gr_qty_grir'] = agg_df['Net_GR_Qty']
    
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
    if 'Net_Order_Value_INR' not in agg_df.columns:
        if 'Net Order Value' in agg_df.columns:
            ex_rate = agg_df.get('EKKO_Exchange_Rate', pd.Series(1.0, index=agg_df.index)).fillna(1.0)
            agg_df['Net_Order_Value_INR'] = agg_df['Net Order Value'] * ex_rate
        else:
            agg_df['Net_Order_Value_INR'] = 0.0
        
    return agg_df


def _aging_bucket(days):
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
