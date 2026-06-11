#!/usr/bin/env python
"""Test GRIR upload and analysis."""

import sys
sys.path.insert(0, r'A:\Desktop\SyrmaSGS_DashBoard.worktrees\agents-grir-analytics-dashboard-implementation')

from app import app
import pandas as pd
import io

# Read the CSV files
grir_df = pd.read_csv('grir.csv')
me2n_df = pd.read_csv('me2n.csv')
ekko_df = pd.read_csv('EKKO.csv')

print(f"Loaded files:")
print(f"  GRIR: {len(grir_df)} rows, {len(grir_df.columns)} columns")
print(f"  ME2N: {len(me2n_df)} rows, {len(me2n_df.columns)} columns")
print(f"  EKKO: {len(ekko_df)} rows, {len(ekko_df.columns)} columns")

# Test with the Flask test client
with app.test_client() as client:
    # Prepare file data
    with open('grir.csv', 'rb') as grir_file, open('me2n.csv', 'rb') as me2n_file, open('EKKO.csv', 'rb') as ekko_file:
        files = {
            'grir': (grir_file, 'grir.csv'),
            'me2n': (me2n_file, 'me2n.csv'),
            'ekko': (ekko_file, 'EKKO.csv'),
        }
        
        # Upload files
        response = client.post(
            '/api/grir/upload-files',
            data=files,
            content_type='multipart/form-data'
        )
    
    print(f"\nUpload response: {response.status_code}")
    resp_data = response.get_json()
    print(f"Response: {resp_data}")
    
    # Get KPIs
    if resp_data.get('success'):
        response = client.get('/api/grir/kpis')
        print(f"\nKPIs response: {response.status_code}")
        kpis_data = response.get_json()
        if kpis_data.get('success'):
            kpis = kpis_data.get('kpis', {})
            print(f"KPIs:")
            print(f"  Total PO Lines: {kpis.get('total_po_lines')}")
            print(f"  Reconciliation Rate: {kpis.get('reconciliation_rate_pct')}%")
            print(f"  Open Exposure INR: ₹{kpis.get('total_open_exposure_inr', 0)/1e5:.2f}L")
            print(f"  Reconciled Lines: {kpis.get('reconciled_po_lines')}")
            print(f"  Unreconciled Lines: {kpis.get('unreconciled_po_lines')}")

