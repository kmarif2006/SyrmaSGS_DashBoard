#!/usr/bin/env python
"""Direct test of GRIR reconciliation engine."""

import sys
sys.path.insert(0, r'c:\project\SyrmaSGS_DashBoard')

from services.grir_reconciliation_engine import aggregate_by_po_item
from services.grir_kpi_builder import build_executive_kpis, build_aging_analysis, build_top_management_insights
import pandas as pd
from datetime import datetime

# Load the CSV files
print("Loading files...")
grir_df = pd.read_csv('grir.csv', low_memory=False)
me2n_df = pd.read_csv('me2n.csv', low_memory=False)
ekko_df = pd.read_csv('EKKO.csv', low_memory=False)

print(f"Loaded:")
print(f"  GRIR: {len(grir_df)} rows")
print(f"  ME2N: {len(me2n_df)} rows")
print(f"  EKKO: {len(ekko_df)} rows")

# Run reconciliation
print("\nRunning reconciliation...")
reconciled_df = aggregate_by_po_item(grir_df, me2n_df, ekko_df, pd.Timestamp(datetime.now()))

print(f"Reconciled: {len(reconciled_df)} PO line items")

# Build KPIs
print("\nBuilding KPIs...")
kpis = build_executive_kpis(reconciled_df)

print(f"\n=== EXECUTIVE KPIs ===")
print(f"Total PO Lines: {kpis['total_po_lines']}")
print(f"Reconciled Lines: {kpis['reconciled_po_lines']}")
print(f"Reconciliation Rate: {kpis['reconciliation_rate_pct']:.1f}%")
print(f"Total Open Exposure (INR): INR {kpis['total_open_exposure_inr']/1e5:.2f}L")
print(f"Total GR Value (INR): INR {kpis['total_gr_value_inr']/1e5:.2f}L")
print(f"Total IR Value (INR): INR {kpis['total_ir_value_inr']/1e5:.2f}L")
print(f"Pending Invoices: {kpis['pending_invoice_count']}")
print(f"Pending GRs: {kpis['pending_gr_count']}")
print(f"Avg Invoice Delay (days): {kpis['average_invoice_delay_days']:.1f}")
print(f"Avg Reconciliation Time (days): {kpis['average_reconciliation_time_days']:.1f}")

# Aging analysis
print("\nAging Analysis...")
aging = build_aging_analysis(reconciled_df)
for age_row in aging:
    print(f"  {age_row['aging_bucket']}: {age_row['total_items']} items, "
          f"INR {age_row['total_exposure_inr']/1e5:.2f}L exposure")

# Top insights
print("\nTop Insights...")
insights = build_top_management_insights(reconciled_df)
print(f"Top Vendors: {len(insights.get('top_vendors_by_exposure', []))} vendors identified")
if insights.get('top_vendors_by_exposure'):
    for v in insights['top_vendors_by_exposure'][:3]:
        print(f"  {v['vendor']}: INR {v['exposure_inr']/1e5:.2f}L")

print(f"\nStatus Summary:")
for status, data in insights.get('status_summary', {}).items():
    print(f"  {status}: {data['count']} items, INR {data['exposure_inr']/1e5:.2f}L exposure")

print("\n[PASS] Reconciliation and KPI calculation successful!")
