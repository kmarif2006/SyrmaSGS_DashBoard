#!/usr/bin/env python3
"""
Test the complete upload and reconciliation workflow via Flask API
"""
import sys
import json
from io import BytesIO
from pathlib import Path
from app import app

def test_upload_workflow():
    """Test uploading files and verify reconciliation"""
    
    client = app.test_client()
    
    print("Testing GRIR Upload Workflow...\n")
    
    # Test 1: Check initial state (no data)
    print("1. Testing initial state (no files uploaded)...")
    response = client.get('/api/grir/kpis')
    print(f"   GET /api/grir/kpis: {response.status_code}")
    assert response.status_code == 400, "Should return 400 when no data"
    print("   ✓ Correctly returns 400 when no files uploaded\n")
    
    # Test 2: Upload files
    print("2. Testing file upload...")
    files_dir = Path('./')
    grir_file = files_dir / 'grir.csv'
    me2n_file = files_dir / 'me2n.csv'
    ekko_file = files_dir / 'EKKO.csv'
    
    if not all([grir_file.exists(), me2n_file.exists(), ekko_file.exists()]):
        print("   ✗ Some files not found!")
        print(f"   GRIR: {grir_file.exists()}")
        print(f"   ME2N: {me2n_file.exists()}")
        print(f"   EKKO: {ekko_file.exists()}")
        return False
    
    # Read file contents
    grir_content = grir_file.read_bytes()
    me2n_content = me2n_file.read_bytes()
    ekko_content = ekko_file.read_bytes()
    
    # Create file objects for upload
    data = {
        'grir_file': (BytesIO(grir_content), 'grir.csv'),
        'me2n_file': (BytesIO(me2n_content), 'me2n.csv'),
        'ekko_file': (BytesIO(ekko_content), 'EKKO.csv'),
    }
    response = client.post('/api/grir/upload-files', data=data, content_type='multipart/form-data')
    
    print(f"   POST /api/grir/upload-files: {response.status_code}")
    resp_json = response.get_json()
    
    if response.status_code != 200:
        print(f"   ✗ Upload failed: {resp_json}")
        return False
    
    print(f"   Rows processed: GRIR={resp_json.get('grir_rows')}, ME2N={resp_json.get('me2n_rows')}, EKKO={resp_json.get('ekko_rows')}")
    print("   ✓ Files uploaded successfully\n")
    
    # Test 3: Fetch KPIs
    print("3. Testing KPI retrieval...")
    response = client.get('/api/grir/kpis')
    print(f"   GET /api/grir/kpis: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ✗ KPI retrieval failed")
        return False
    
    response_data = response.get_json()
    kpis = response_data.get('kpis', {})
    print(f"   Total PO Lines: {kpis.get('total_po_lines')}")
    print(f"   Reconciliation Rate: {kpis.get('reconciliation_rate_pct')}%")
    print(f"   Open Exposure (INR): ₹{kpis.get('total_open_exposure_inr')}L")
    print("   ✓ KPIs retrieved successfully\n")
    
    # Test 4: Fetch full dashboard
    print("4. Testing dashboard data retrieval...")
    response = client.get('/api/grir/dashboard')
    print(f"   GET /api/grir/dashboard: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ✗ Dashboard retrieval failed")
        return False
    
    dashboard = response.get_json()
    print(f"   Dashboard has {len(dashboard.get('kpis', {}))} KPI metrics")
    print(f"   Aging buckets: {len(dashboard.get('aging_analysis', []))}")
    print(f"   Charts: {len(dashboard.get('charts', {}))}")
    print("   ✓ Dashboard data retrieved successfully\n")
    
    # Test 5: Export as JSON
    print("5. Testing JSON export...")
    response = client.get('/api/grir/export/json')
    print(f"   GET /api/grir/export/json: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ✗ JSON export failed")
        return False
    
    print("   ✓ JSON export successful\n")
    
    # Test 6: Export as Excel
    print("6. Testing Excel export...")
    response = client.get('/api/grir/export/excel')
    print(f"   GET /api/grir/export/excel: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   ✗ Excel export failed")
        return False
    
    print("   ✓ Excel export successful\n")
    
    print("✅ All workflow tests passed!")
    return True

if __name__ == '__main__':
    success = test_upload_workflow()
    sys.exit(0 if success else 1)
