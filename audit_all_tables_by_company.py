import json, requests, msal

TOKEN_FILE = 'token.json'
with open(TOKEN_FILE) as f:
    token_data = json.load(f)

app = msal.PublicClientApplication('ea0616ba-638b-4df5-95b9-636659ae5121', authority='https://login.microsoftonline.com/organizations')
res = app.acquire_token_by_refresh_token(token_data['refresh_token'], scopes=['https://analysis.windows.net/powerbi/api/.default'])
token = res['access_token']

headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
dataset_id = 'c71af0b4-2794-415e-a304-ce9a9fcb3619'
query_url = f'https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries'

# 1. Holding summary query
dax_summary = '''
EVALUATE
ROW(
  "TotalCuentas", COUNTROWS(cuentasHolding),
  "EmpresasCuentas", DISTINCTCOUNT(cuentasHolding[Empresa]),
  "TotalPeriodos", COUNTROWS(periodosHolding),
  "EmpresasPeriodos", DISTINCTCOUNT(periodosHolding[Empresa]),
  "TotalProveedoresDeuda", COUNTROWS(proveedoresHolding),
  "EmpresasProveedoresDeuda", DISTINCTCOUNT(proveedoresHolding[Empresa]),
  "TotalMaestroVendors", COUNTROWS(maestroVendorsHolding),
  "EmpresasVendors", DISTINCTCOUNT(maestroVendorsHolding[Empresa]),
  "TotalFacturas", COUNTROWS(facturasHolding),
  "EmpresasFacturas", DISTINCTCOUNT(facturasHolding[Empresa])
)
'''

r = requests.post(query_url, headers=headers, json={'queries': [{'query': dax_summary}]})
print("Holding Summary:")
for k, v in r.json()['results'][0]['tables'][0]['rows'][0].items():
    print(f"  {k}: {v}")

# 2. Detailed audit per company for vendors and invoices
dax_details = '''
EVALUATE
SUMMARIZECOLUMNS(
  maestroVendorsHolding[Empresa],
  "VendorsCount", COUNTROWS(maestroVendorsHolding),
  "VendorsWithBalance", CALCULATE(COUNTROWS(maestroVendorsHolding), maestroVendorsHolding[balance] <> 0),
  "TotalBalanceVendors", SUM(maestroVendorsHolding[balance])
)
ORDER BY [VendorsCount] DESC
'''
r2 = requests.post(query_url, headers=headers, json={'queries': [{'query': dax_details}]})
print("\nMaestro Vendors per Company (Top 15):")
for row in r2.json()['results'][0]['tables'][0]['rows'][:15]:
    print(f"  {row['maestroVendorsHolding[Empresa]']:32} | Vendors: {row['[VendorsCount]']:5d} | Con Saldo: {row['[VendorsWithBalance]']:4d} | Saldo: {row['[TotalBalanceVendors]']:14,f}")

# 3. Invoices per company
dax_invoices = '''
EVALUATE
SUMMARIZECOLUMNS(
  facturasHolding[Empresa],
  "TotalFacturas", COUNTROWS(facturasHolding),
  "MontoTotalFacturas", SUM(facturasHolding[totalAmountIncludingTax])
)
ORDER BY [TotalFacturas] DESC
'''
r3 = requests.post(query_url, headers=headers, json={'queries': [{'query': dax_invoices}]})
print("\nFacturas de Compra per Company:")
for row in r3.json()['results'][0]['tables'][0]['rows']:
    print(f"  {row['facturasHolding[Empresa]']:32} | Facturas: {row['[TotalFacturas]']:5d} | Monto: {row['[MontoTotalFacturas]']:16,f}")

