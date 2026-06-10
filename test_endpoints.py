#!/usr/bin/env python
"""Test GRIR endpoints directly."""

import sys
sys.path.insert(0, r'A:\Desktop\SyrmaSGS_DashBoard.worktrees\agents-grir-analytics-dashboard-implementation')

from app import app

# Test the app directly
with app.test_client() as client:
    # Test GET /api/grir/kpis
    response = client.get('/api/grir/kpis')
    print(f'GET /api/grir/kpis: {response.status_code}')
    print(f'Response: {response.get_json()}')
    
    # Test GET /api/grir/aging
    response = client.get('/api/grir/aging')
    print(f'\nGET /api/grir/aging: {response.status_code}')
    print(f'Response: {response.get_json()}')
    
    # List all routes
    print(f'\nAll routes with grir:')
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: str(r)):
        if 'grir' in str(rule).lower() and 'api' in str(rule):
            print(f'  {rule}')
