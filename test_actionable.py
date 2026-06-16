import sys
sys.path.append('C:\\project\\SyrmaSGS_DashBoard')
from services.grir_analytics_service import GRIRAnalyticsService
import pandas as pd

svc = GRIRAnalyticsService()
svc.upload_df(pd.read_csv('grir.csv', low_memory=False), 'grir.csv')
svc.upload_df(pd.read_csv('EKKO.csv', low_memory=False), 'EKKO.csv')
svc.upload_df(pd.read_csv('me2n.csv', low_memory=False), 'me2n.csv')
df = svc._df

mask1 = ((df['days_open'] > 90) & (~df['Status'].isin(['Reconciled', 'No Activity'])))
mask2 = (df['Status'] == 'Invoice Greater Than GR')
mask_all = (mask1 | mask2)

print(f"Mask 1 exposure: {df.loc[mask1, 'exposure_val'].sum():.2f}")
print(f"Mask 2 exposure: {df.loc[mask2, 'exposure_val'].sum():.2f}")
print(f"Mask All exposure: {df.loc[mask_all, 'exposure_val'].sum():.2f}")

# What is the sum of ALL unreconciled?
mask_unrec = ~df['Status'].isin(['Reconciled', 'No Activity'])
print(f"All Unreconciled exposure: {df.loc[mask_unrec, 'exposure_val'].sum():.2f}")
print(f"All Unreconciled count: {mask_unrec.sum()}")

print(df.groupby('Status')['exposure_val'].agg(['count', 'sum']))
