"""
SAP GR/IR KPI Builder
Comprehensive KPI calculations for executive dashboard based on ledger postings.
"""

import numpy as np
import pandas as pd
from datetime import datetime


def build_executive_kpis(reconciled_df):
    """
    Build executive KPIs from reconciled data.
    
    Args:
        reconciled_df: Reconciled DataFrame from reconciliation engine
    
    Returns:
        Dictionary of KPI values
    """
    kpis = {}
    tolerance = 0.01
    
    # 1. Total PO Lines
    kpis['total_po_lines'] = len(reconciled_df)
    
    # 2. Reconciled PO Lines (No open exposure)
    reconciled_mask = reconciled_df['Open_Exposure_INR'].abs() <= tolerance
    kpis['reconciled_po_lines'] = reconciled_mask.sum()
    
    # 3. Unreconciled PO Lines
    kpis['unreconciled_po_lines'] = len(reconciled_df) - kpis['reconciled_po_lines']
    
    # 4. Reconciliation Rate %
    if len(reconciled_df) > 0:
        kpis['reconciliation_rate_pct'] = (kpis['reconciled_po_lines'] / len(reconciled_df)) * 100
    else:
        kpis['reconciliation_rate_pct'] = 0.0
        
    # 5. Total GR Value INR
    kpis['total_gr_value_inr'] = reconciled_df['Net_GR_Val_INR'].sum()
    
    # 6. Total IR Value INR
    kpis['total_ir_value_inr'] = reconciled_df['Net_IR_Val_INR'].sum()
    
    # 7. Signed Open Balance INR
    kpis['signed_open_balance_inr'] = reconciled_df['Open_Val_INR'].sum()
    
    # 8. Total Open Exposure INR
    kpis['total_open_exposure_inr'] = reconciled_df['Open_Exposure_INR'].sum()
    
    # 9. IR Pending Count and Value
    kpis['pending_invoice_count'] = (reconciled_df['Status'].isin(['GR Done / IR Pending', 'GR Greater Than Invoice'])).sum()
    kpis['pending_invoice_value_inr'] = reconciled_df[reconciled_df['Status'].isin(['GR Done / IR Pending', 'GR Greater Than Invoice'])]['Open_Exposure_INR'].sum()
    
    # 10. GR Pending Count and Value
    kpis['pending_gr_count'] = (reconciled_df['Status'].isin(['IR Done / GR Pending', 'Invoice Greater Than GR'])).sum()
    kpis['pending_gr_value_inr'] = reconciled_df[reconciled_df['Status'].isin(['IR Done / GR Pending', 'Invoice Greater Than GR'])]['Open_Exposure_INR'].sum()
    
    # 11. Open PO Count
    kpis['open_po_count'] = reconciled_df[reconciled_df['Open_Exposure_INR'] > tolerance]['PO Number'].nunique()
    
    # 12. Active Vendors
    kpis['active_vendors'] = reconciled_df[reconciled_df['Open_Exposure_INR'] > tolerance]['Vendor'].nunique()
    
    # 13. Reversal Count and Value
    kpis['reversal_count'] = int(reconciled_df['Reversal_Count_PO'].sum()) if 'Reversal_Count_PO' in reconciled_df.columns else 0
    kpis['reversal_value_inr'] = reconciled_df['Reversal_Value_INR_PO'].sum() if 'Reversal_Value_INR_PO' in reconciled_df.columns else 0.0
    
    # 14. Currency Conversion Issues
    kpis['currency_conversion_issues'] = int(reconciled_df['Currency_Conversion_Missing_Count'].sum()) if 'Currency_Conversion_Missing_Count' in reconciled_df.columns else 0

    # 15. Average Invoice Delay (days to invoice first GR item)
    ir_pending = reconciled_df[reconciled_df['Status'].isin(['GR Done / IR Pending', 'GR Greater Than Invoice'])]
    if len(ir_pending) > 0 and 'Days_Open' in ir_pending.columns:
        kpis['average_invoice_delay_days'] = ir_pending['Days_Open'].mean()
    else:
        kpis['average_invoice_delay_days'] = 0.0
    
    # 16. Average Reconciliation Time (days to reconcile)
    if kpis['reconciled_po_lines'] > 0 and 'Days_Open' in reconciled_df.columns:
        reconciled_items = reconciled_df[reconciled_mask]
        kpis['average_reconciliation_time_days'] = reconciled_items['Days_Open'].mean()
    else:
        kpis['average_reconciliation_time_days'] = 0.0

    # Compatibility keys for older/different consumer logic
    kpis['reconciliation_rate'] = kpis['reconciliation_rate_pct']
    kpis['reconciled_count'] = kpis['reconciled_po_lines']
    kpis['total_po_items'] = kpis['total_po_lines']
    kpis['total_open_value'] = kpis['total_open_exposure_inr']
    kpis['total_gr_value'] = kpis['total_gr_value_inr']
    kpis['total_ir_value'] = kpis['total_ir_value_inr']
    kpis['critical_items'] = int((reconciled_df['risk_level'] == 'CRITICAL').sum()) if 'risk_level' in reconciled_df.columns else 0
    kpis['unique_pos'] = kpis['open_po_count']
    kpis['unique_vendors'] = kpis['active_vendors']
    kpis['total_reversals_val'] = kpis['reversal_value_inr']
    kpis['unique_plants'] = reconciled_df['Plant'].nunique() if 'Plant' in reconciled_df.columns else 0
    kpis['total_materials'] = reconciled_df['Material'].nunique() if 'Material' in reconciled_df.columns else 0
    
    # Status distribution
    status_counts = reconciled_df['Status'].value_counts().to_dict()
    kpis['status_distribution'] = {k: int(v) for k, v in status_counts.items()}
    
    # Aging distribution
    aging_counts = reconciled_df['Aging_Bucket'].value_counts().to_dict()
    kpis['aging_distribution'] = {k: int(v) for k, v in aging_counts.items()}
    
    # Round all float values
    for key, val in kpis.items():
        if isinstance(val, float):
            kpis[key] = round(val, 2)
        elif isinstance(val, np.floating):
            kpis[key] = round(float(val), 2)
        elif isinstance(val, (np.integer, int)):
            kpis[key] = int(val)
    
    return kpis


def build_aging_analysis(reconciled_df):
    """
    Build aging bucket analysis showing exposure and status breakdown.
    
    Args:
        reconciled_df: Reconciled DataFrame
    
    Returns:
        List of aging bucket summaries
    """
    buckets = ['0-30 Days', '31-60 Days', '61-90 Days', '91-180 Days', '180+ Days', 'Unknown']
    result = []
    
    for bucket in buckets:
        bucket_data = reconciled_df[reconciled_df['Aging_Bucket'] == bucket]
        if len(bucket_data) == 0:
            # Try legacy bucket mapping without ' Days' suffix
            legacy_bucket = bucket.replace(' Days', '')
            bucket_data = reconciled_df[reconciled_df['Aging_Bucket'] == legacy_bucket]
            
        if len(bucket_data) == 0:
            continue
        
        reconciled_mask = bucket_data['Open_Exposure_INR'].abs() <= 0.01
        
        result.append({
            'aging_bucket': bucket,
            'total_items': len(bucket_data),
            'reconciled_items': reconciled_mask.sum(),
            'unreconciled_items': (~reconciled_mask).sum(),
            'total_exposure_inr': round(bucket_data['Open_Exposure_INR'].sum(), 2),
            'ir_pending_count': (bucket_data['Status'].isin(['GR Done / IR Pending', 'GR Greater Than Invoice'])).sum(),
            'ir_pending_value_inr': round(bucket_data[bucket_data['Status'].isin(['GR Done / IR Pending', 'GR Greater Than Invoice'])]['Open_Exposure_INR'].sum(), 2),
            'gr_pending_count': (bucket_data['Status'].isin(['IR Done / GR Pending', 'Invoice Greater Than GR'])).sum(),
            'gr_pending_value_inr': round(bucket_data[bucket_data['Status'].isin(['IR Done / GR Pending', 'Invoice Greater Than GR'])]['Open_Exposure_INR'].sum(), 2),
            'gr_done_ir_pending_val': round(bucket_data[bucket_data['Status'] == 'GR Done / IR Pending']['Open_Exposure_INR'].sum(), 2),
            'gr_greater_inv_val': round(bucket_data[bucket_data['Status'] == 'GR Greater Than Invoice']['Open_Exposure_INR'].sum(), 2),
            'ir_done_gr_pending_val': round(bucket_data[bucket_data['Status'] == 'IR Done / GR Pending']['Open_Exposure_INR'].sum(), 2),
            'inv_greater_gr_val': round(bucket_data[bucket_data['Status'] == 'Invoice Greater Than GR']['Open_Exposure_INR'].sum(), 2),
            'review_required_val': round(bucket_data[bucket_data['Status'] == 'Review Required']['Open_Exposure_INR'].sum(), 2),
        })
    
    return result


def build_top_management_insights(reconciled_df):
    """
    Build top management insights and exception reports.
    
    Args:
        reconciled_df: Reconciled DataFrame
    
    Returns:
        Dictionary with top insights
    """
    insights = {}
    
    # Top Vendors by Open Exposure
    insights['top_vendors_by_exposure'] = []
    if 'Vendor' in reconciled_df.columns and 'Open_Exposure_INR' in reconciled_df.columns:
        try:
            top_vendors = (reconciled_df.groupby('Vendor')['Open_Exposure_INR'].sum()
                           .sort_values(ascending=False).head(10))
            insights['top_vendors_by_exposure'] = [
                {'vendor': vendor, 'exposure_inr': round(float(value), 2)}
                for vendor, value in top_vendors.items()
            ]
        except Exception:
            pass
    
    # Top Plants by Open Exposure
    insights['top_plants_by_exposure'] = []
    if 'Plant' in reconciled_df.columns and 'Open_Exposure_INR' in reconciled_df.columns:
        try:
            top_plants = (reconciled_df.groupby('Plant')['Open_Exposure_INR'].sum()
                           .sort_values(ascending=False).head(10))
            insights['top_plants_by_exposure'] = [
                {'plant': plant, 'exposure_inr': round(float(value), 2)}
                for plant, value in top_plants.items()
            ]
        except Exception:
            pass
    
    # Top Material Groups by Open Exposure
    insights['top_material_groups_by_exposure'] = []
    if 'Material Group' in reconciled_df.columns and 'Open_Exposure_INR' in reconciled_df.columns:
        try:
            top_matgrps = (reconciled_df.groupby('Material Group')['Open_Exposure_INR'].sum()
                           .sort_values(ascending=False).head(10))
            insights['top_material_groups_by_exposure'] = [
                {'material_group': matgrp, 'exposure_inr': round(float(value), 2)}
                for matgrp, value in top_matgrps.items()
            ]
        except Exception:
            pass
    
    # Largest Unreconciled PO Lines
    insights['largest_unreconciled_po_lines'] = []
    if 'Open_Exposure_INR' in reconciled_df.columns and 'PO Number' in reconciled_df.columns:
        try:
            unreconciled = reconciled_df[reconciled_df['Open_Exposure_INR'].abs() > 0.01].copy()
            select_cols = ['PO Number', 'PO Item', 'Status', 'Open_Exposure_INR', 'Days_Open']
            if 'Vendor' in reconciled_df.columns:
                select_cols.insert(2, 'Vendor')
            available_cols = [c for c in select_cols if c in unreconciled.columns]
            
            largest_unreconciled = unreconciled.nlargest(20, 'Open_Exposure_INR')[available_cols]
            insights['largest_unreconciled_po_lines'] = [
                {
                    'po_number': row['PO Number'],
                    'po_item': str(row['PO Item']),
                    'vendor': row.get('Vendor', 'N/A') if 'Vendor' in available_cols else 'N/A',
                    'status': row['Status'],
                    'exposure_inr': round(float(row['Open_Exposure_INR']), 2),
                    'days_open': int(row['Days_Open'])
                }
                for _, row in largest_unreconciled.iterrows()
            ]
        except Exception:
            pass
    
    # Vendor Invoice Delay Ranking
    insights['vendor_invoice_delay_ranking'] = []
    if 'Status' in reconciled_df.columns and 'Vendor' in reconciled_df.columns and 'Days_Open' in reconciled_df.columns:
        try:
            ir_pending = reconciled_df[reconciled_df['Status'] == 'IR Pending'].copy()
            if len(ir_pending) > 0:
                vendor_delays = ir_pending.groupby('Vendor').agg({
                    'Days_Open': ['mean', 'count', 'max'],
                    'Open_Exposure_INR': 'sum'
                }).round(2)
                vendor_delays.columns = ['avg_days', 'pending_count', 'max_days', 'exposure_inr']
                vendor_delays = vendor_delays.sort_values('avg_days', ascending=False).head(10)
                
                insights['vendor_invoice_delay_ranking'] = [
                    {
                        'vendor': vendor,
                        'avg_days_open': round(float(row['avg_days']), 1),
                        'pending_count': int(row['pending_count']),
                        'max_days_open': int(row['max_days']),
                        'exposure_inr': round(float(row['exposure_inr']), 2)
                    }
                    for vendor, row in vendor_delays.iterrows()
                ]
        except Exception:
            pass
    
    # Status summary
    status_summary = {}
    if 'Status' in reconciled_df.columns:
        for status in ['Reconciled', 'GR Done / IR Pending', 'IR Done / GR Pending', 'Invoice Greater Than GR', 'GR Greater Than Invoice', 'Review Required']:
            status_data = reconciled_df[reconciled_df['Status'] == status]
            status_summary[status] = {
                'count': len(status_data),
                'exposure_inr': round(float(status_data['Open_Exposure_INR'].sum()), 2) if 'Open_Exposure_INR' in reconciled_df.columns else 0
            }
    insights['status_summary'] = status_summary
    
    return insights


def build_chart_data(reconciled_df):
    """
    Build data for all dashboard charts.
    
    Args:
        reconciled_df: Reconciled DataFrame
    
    Returns:
        Dictionary with chart-ready data
    """
    charts = {}
    
    # 1. Reconciliation Status Donut
    try:
        status_dist = reconciled_df['Status'].value_counts()
        charts['reconciliation_status_donut'] = [
            {'name': status, 'value': int(count)}
            for status, count in status_dist.items()
        ]
    except Exception:
        charts['reconciliation_status_donut'] = []
    
    # 2. Aging Bucket Histogram
    try:
        aging_dist = reconciled_df['Aging_Bucket'].value_counts()
        buckets_order = ['0-30 Days', '31-60 Days', '61-90 Days', '91-180 Days', '180+ Days', 'Unknown']
        charts['aging_bucket_histogram'] = [
            {'name': bucket, 'value': int(aging_dist.get(bucket, 0))}
            for bucket in buckets_order if bucket in aging_dist.index or aging_dist.get(bucket, 0) > 0
        ]
    except Exception:
        charts['aging_bucket_histogram'] = []
    
    # 3. Vendor Exposure Bar Chart
    charts['vendor_exposure_bar'] = []
    if 'Vendor' in reconciled_df.columns and 'Open_Exposure_INR' in reconciled_df.columns:
        try:
            vendor_exposure = reconciled_df.groupby('Vendor')['Open_Exposure_INR'].sum().sort_values(ascending=False).head(15)
            charts['vendor_exposure_bar'] = [
                {'name': vendor, 'value': round(float(exposure), 2)}
                for vendor, exposure in vendor_exposure.items()
            ]
        except Exception:
            pass
    
    # 4. Plant Exposure Bar Chart
    charts['plant_exposure_bar'] = []
    if 'Plant' in reconciled_df.columns and 'Open_Exposure_INR' in reconciled_df.columns:
        try:
            plant_exposure = reconciled_df.groupby('Plant')['Open_Exposure_INR'].sum().sort_values(ascending=False).head(15)
            charts['plant_exposure_bar'] = [
                {'name': plant, 'value': round(float(exposure), 2)}
                for plant, exposure in plant_exposure.items()
            ]
        except Exception:
            pass
    
    # 5. Material Group Exposure Bar Chart
    charts['material_group_exposure_bar'] = []
    if 'Material Group' in reconciled_df.columns and 'Open_Exposure_INR' in reconciled_df.columns:
        try:
            matgrp_exposure = reconciled_df.groupby('Material Group')['Open_Exposure_INR'].sum().sort_values(ascending=False).head(15)
            charts['material_group_exposure_bar'] = [
                {'name': matgrp, 'value': round(float(exposure), 2)}
                for matgrp, exposure in matgrp_exposure.items()
            ]
        except Exception:
            pass
    
    # 6. Open Exposure Trend (by posting date)
    charts['monthly_exposure_trend'] = []
    if 'Posting_Date' in reconciled_df.columns and 'Open_Exposure_INR' in reconciled_df.columns:
        try:
            trend_data = reconciled_df.copy()
            trend_data['Year_Month'] = pd.to_datetime(trend_data['Posting_Date'], format='mixed', errors='coerce').dt.to_period('M')
            monthly_exposure = trend_data.groupby('Year_Month')['Open_Exposure_INR'].sum().sort_index()
            charts['monthly_exposure_trend'] = [
                {'month': str(month), 'value': round(float(exposure), 2)}
                for month, exposure in monthly_exposure.items()
            ]
        except Exception:
            pass
    
    # 7. Monthly GR vs IR Trend
    charts['monthly_gr_vs_ir'] = []
    if 'Posting_Date' in reconciled_df.columns and 'Net_GR_Val_INR' in reconciled_df.columns and 'Net_IR_Val_INR' in reconciled_df.columns:
        try:
            trend_data = reconciled_df.copy()
            trend_data['Year_Month'] = pd.to_datetime(trend_data['Posting_Date'], format='mixed', errors='coerce').dt.to_period('M')
            monthly_gr = trend_data.groupby('Year_Month')['Net_GR_Val_INR'].sum().sort_index()
            monthly_ir = trend_data.groupby('Year_Month')['Net_IR_Val_INR'].sum().sort_index()
            charts['monthly_gr_vs_ir'] = [
                {
                    'month': str(month),
                    'gr_value': round(float(monthly_gr.get(month, 0)), 2),
                    'ir_value': round(float(monthly_ir.get(month, 0)), 2)
                }
                for month in sorted(set(monthly_gr.index) | set(monthly_ir.index))
            ]
        except Exception:
            pass
    
    return charts
