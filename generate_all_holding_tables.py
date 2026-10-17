import json, requests, msal, time, base64, re, uuid

TOKEN_FILE = 'token.json'
with open(TOKEN_FILE) as f:
    token_data = json.load(f)

app = msal.PublicClientApplication('ea0616ba-638b-4df5-95b9-636659ae5121', authority='https://login.microsoftonline.com/organizations')
res = app.acquire_token_by_refresh_token(token_data['refresh_token'], scopes=['https://analysis.windows.net/powerbi/api/.default'])
token = res['access_token']

headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
workspace_id = 'f97935fd-6dda-4c37-8ee6-4c88ced5c434'
dataset_id = 'c71af0b4-2794-415e-a304-ce9a9fcb3619'

base = f'https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/semanticModels/{dataset_id}/getDefinition'
print("Fetching current semantic model definition...")
r = requests.post(base, headers=headers)
loc = r.headers['Location']
while True:
    time.sleep(2)
    s = requests.get(loc, headers=headers).json()
    if s.get('status') == 'Succeeded':
        definition = requests.get(loc + '/result', headers=headers).json()
        break

# Extract companies from accounts tables in exact order
companies_mapping = []
for p in definition['definition']['parts']:
    path = p['path']
    if 'tables/accounts' in path and not 'LocalDate' in path and not 'cuentasHolding' in path:
        content = base64.b64decode(p['payload']).decode('utf-8', errors='ignore')
        m = re.search(r'#\"Navegación 1\"\s*=\s*Origen\{\[Name\s*=\s*\"([^\"]+)\"\]\}', content)
        comp = m.group(1) if m else 'UNKNOWN'
        t_match = re.search(r'^table\s+([^\n\r]+)', content)
        t_name = t_match.group(1).strip("'") if t_match else path
        idx_match = re.search(r'accounts\s*\((\d+)\)', t_name)
        idx = int(idx_match.group(1)) if idx_match else 1
        companies_mapping.append((idx, comp))

companies_mapping.sort(key=lambda x: x[0])
print(f"Found {len(companies_mapping)} companies:")
for idx, comp in companies_mapping:
    print(f"  {idx:2d}: {comp}")

# Read vendors template columns body
with open('vendors.tmdl', 'r', encoding='utf-8') as f:
    v_raw = f.read()
v_part_idx = v_raw.find('\tpartition')
v_columns_body = v_raw[v_raw.find('\n\tcolumn'):v_part_idx]

# Read purchaseInvoices template columns body
with open('purchaseInvoices.tmdl', 'r', encoding='utf-8') as f:
    pi_raw = f.read()
pi_part_idx = pi_raw.find('\tpartition')
pi_columns_body = pi_raw[pi_raw.find('\n\tcolumn'):pi_part_idx]

def replace_lineage_tags(body):
    return re.sub(r'lineageTag:\s*[a-f0-9\-]+', lambda m: f'lineageTag: {uuid.uuid4()}', body)

vendors_tables = []
vendors_selects = []
invoices_tables = []
invoices_selects = []

for idx, comp in companies_mapping:
    escaped_comp = comp.replace('"', '""')
    
    # 1. Vendors table
    v_tname = 'vendors' if idx == 1 else f'vendors ({idx})'
    v_cols = replace_lineage_tags(v_columns_body)
    v_tmdl = f'''table '{v_tname}'
\tlineageTag: {uuid.uuid4()}
{v_cols}
\tpartition '{v_tname}' = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t  Origen = Dynamics365BusinessCentral.ApiContentsWithOptions("PRODUCCION", "{escaped_comp}", "v2.0", [UseReadOnlyReplica = null, AcceptLanguage = null, Timeout = null, ODataMaxPageSize = null]),
\t\t\t\t  #"Navegacion 1" = Origen{{[Name = "vendors", Signature = "table"]}}[Data]
\t\t\t\tin
\t\t\t\t  #"Navegacion 1"
'''
    vendors_tables.append((v_tname, v_tmdl))
    vendors_selects.append(f'''\t\t\t\tSELECTCOLUMNS(
\t\t\t\t\t'{v_tname}',
\t\t\t\t\t"Empresa", "{escaped_comp}",
\t\t\t\t\t"id", '{v_tname}'[id],
\t\t\t\t\t"number", '{v_tname}'[number],
\t\t\t\t\t"displayName", '{v_tname}'[displayName],
\t\t\t\t\t"addressLine1", '{v_tname}'[addressLine1],
\t\t\t\t\t"city", '{v_tname}'[city],
\t\t\t\t\t"state", '{v_tname}'[state],
\t\t\t\t\t"country", '{v_tname}'[country],
\t\t\t\t\t"postalCode", '{v_tname}'[postalCode],
\t\t\t\t\t"phoneNumber", '{v_tname}'[phoneNumber],
\t\t\t\t\t"email", '{v_tname}'[email],
\t\t\t\t\t"website", '{v_tname}'[website],
\t\t\t\t\t"taxRegistrationNumber", '{v_tname}'[taxRegistrationNumber],
\t\t\t\t\t"currencyCode", '{v_tname}'[currencyCode],
\t\t\t\t\t"paymentTermsId", '{v_tname}'[paymentTermsId],
\t\t\t\t\t"paymentMethodId", '{v_tname}'[paymentMethodId],
\t\t\t\t\t"taxLiable", '{v_tname}'[taxLiable],
\t\t\t\t\t"blocked", '{v_tname}'[blocked],
\t\t\t\t\t"balance", '{v_tname}'[balance],
\t\t\t\t\t"lastModifiedDateTime", '{v_tname}'[lastModifiedDateTime]
\t\t\t\t)''')

    # 2. PurchaseInvoices table
    pi_tname = 'purchaseInvoices' if idx == 1 else f'purchaseInvoices ({idx})'
    pi_cols = replace_lineage_tags(pi_columns_body)
    pi_tmdl = f'''table '{pi_tname}'
\tlineageTag: {uuid.uuid4()}
{pi_cols}
\tpartition '{pi_tname}' = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t  Origen = Dynamics365BusinessCentral.ApiContentsWithOptions("PRODUCCION", "{escaped_comp}", "v2.0", [UseReadOnlyReplica = null, AcceptLanguage = null, Timeout = null, ODataMaxPageSize = null]),
\t\t\t\t  #"Navegacion 1" = Origen{{[Name = "purchaseInvoices", Signature = "table"]}}[Data]
\t\t\t\tin
\t\t\t\t  #"Navegacion 1"

\tannotation PBI_ResultType = Table
'''
    invoices_tables.append((pi_tname, pi_tmdl))
    invoices_selects.append(f'''\t\t\t\tSELECTCOLUMNS(
\t\t\t\t\t'{pi_tname}',
\t\t\t\t\t"Empresa", "{escaped_comp}",
\t\t\t\t\t"id", '{pi_tname}'[id],
\t\t\t\t\t"number", '{pi_tname}'[number],
\t\t\t\t\t"postingDate", '{pi_tname}'[postingDate],
\t\t\t\t\t"invoiceDate", '{pi_tname}'[invoiceDate],
\t\t\t\t\t"dueDate", '{pi_tname}'[dueDate],
\t\t\t\t\t"vendorInvoiceNumber", '{pi_tname}'[vendorInvoiceNumber],
\t\t\t\t\t"vendorId", '{pi_tname}'[vendorId],
\t\t\t\t\t"vendorNumber", '{pi_tname}'[vendorNumber],
\t\t\t\t\t"vendorName", '{pi_tname}'[vendorName],
\t\t\t\t\t"payToName", '{pi_tname}'[payToName],
\t\t\t\t\t"shortcutDimension1Code", '{pi_tname}'[shortcutDimension1Code],
\t\t\t\t\t"shortcutDimension2Code", '{pi_tname}'[shortcutDimension2Code],
\t\t\t\t\t"currencyCode", '{pi_tname}'[currencyCode],
\t\t\t\t\t"pricesIncludeTax", '{pi_tname}'[pricesIncludeTax],
\t\t\t\t\t"discountAmount", '{pi_tname}'[discountAmount],
\t\t\t\t\t"totalAmountExcludingTax", '{pi_tname}'[totalAmountExcludingTax],
\t\t\t\t\t"totalTaxAmount", '{pi_tname}'[totalTaxAmount],
\t\t\t\t\t"totalAmountIncludingTax", '{pi_tname}'[totalAmountIncludingTax],
\t\t\t\t\t"status", '{pi_tname}'[status],
\t\t\t\t\t"lastModifiedDateTime", '{pi_tname}'[lastModifiedDateTime]
\t\t\t\t)''')

# Consolidated maestroVendorsHolding
union_v_expr = ',\n'.join(vendors_selects)
tmdl_maestro_vendors = f'''table maestroVendorsHolding
\tlineageTag: {uuid.uuid4()}

\tcolumn Empresa
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [Empresa]

\tcolumn id
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [id]

\tcolumn number
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [number]

\tcolumn displayName
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [displayName]

\tcolumn addressLine1
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [addressLine1]

\tcolumn city
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [city]

\tcolumn state
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [state]

\tcolumn country
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [country]

\tcolumn postalCode
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [postalCode]

\tcolumn phoneNumber
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [phoneNumber]

\tcolumn email
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [email]

\tcolumn website
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [website]

\tcolumn taxRegistrationNumber
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [taxRegistrationNumber]

\tcolumn currencyCode
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [currencyCode]

\tcolumn paymentTermsId
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [paymentTermsId]

\tcolumn paymentMethodId
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [paymentMethodId]

\tcolumn taxLiable
\t\tdataType: boolean
\t\tformatString: """TRUE"";""TRUE"";""FALSE"""
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [taxLiable]

\tcolumn blocked
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [blocked]

\tcolumn balance
\t\tdataType: double
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: sum
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [balance]

\tcolumn lastModifiedDateTime
\t\tdataType: dateTime
\t\tformatString: General Date
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [lastModifiedDateTime]

\tpartition maestroVendorsHolding = calculated
\t\tmode: import
\t\tsource =
\t\t\tUNION(
{union_v_expr}
\t\t\t)
'''

# Consolidated facturasHolding
union_pi_expr = ',\n'.join(invoices_selects)
tmdl_facturas_holding = f'''table facturasHolding
\tlineageTag: {uuid.uuid4()}

\tcolumn Empresa
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [Empresa]

\tcolumn id
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [id]

\tcolumn number
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [number]

\tcolumn postingDate
\t\tdataType: dateTime
\t\tformatString: General Date
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [postingDate]

\tcolumn invoiceDate
\t\tdataType: dateTime
\t\tformatString: General Date
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [invoiceDate]

\tcolumn dueDate
\t\tdataType: dateTime
\t\tformatString: General Date
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [dueDate]

\tcolumn vendorInvoiceNumber
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [vendorInvoiceNumber]

\tcolumn vendorId
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [vendorId]

\tcolumn vendorNumber
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [vendorNumber]

\tcolumn vendorName
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [vendorName]

\tcolumn payToName
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [payToName]

\tcolumn shortcutDimension1Code
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [shortcutDimension1Code]

\tcolumn shortcutDimension2Code
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [shortcutDimension2Code]

\tcolumn currencyCode
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [currencyCode]

\tcolumn pricesIncludeTax
\t\tdataType: boolean
\t\tformatString: """TRUE"";""TRUE"";""FALSE"""
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [pricesIncludeTax]

\tcolumn discountAmount
\t\tdataType: double
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: sum
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [discountAmount]

\tcolumn totalAmountExcludingTax
\t\tdataType: double
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: sum
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [totalAmountExcludingTax]

\tcolumn totalTaxAmount
\t\tdataType: double
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: sum
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [totalTaxAmount]

\tcolumn totalAmountIncludingTax
\t\tdataType: double
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: sum
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [totalAmountIncludingTax]

\tcolumn status
\t\tdataType: string
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [status]

\tcolumn lastModifiedDateTime
\t\tdataType: dateTime
\t\tformatString: General Date
\t\tlineageTag: {uuid.uuid4()}
\t\tsummarizeBy: none
\t\tisNameInferred: false
\t\tisDataTypeInferred: false
\t\tsourceColumn: [lastModifiedDateTime]

\tpartition facturasHolding = calculated
\t\tmode: import
\t\tsource =
\t\t\tUNION(
{union_pi_expr}
\t\t\t)
'''

# Filter out old parts for vendors, maestroVendorsHolding, purchaseInvoices, facturasHolding
new_parts = []
for p in definition['definition']['parts']:
    path = p['path']
    if 'tables/vendors' in path or 'tables/maestroVendorsHolding' in path or 'tables/purchaseInvoices' in path or 'tables/facturasHolding' in path:
        continue
    new_parts.append(p)

# Update model.tmdl to reference all new tables
for p in new_parts:
    if p['path'] == 'definition/model.tmdl':
        content = base64.b64decode(p['payload']).decode('utf-8')
        lines = [line for line in content.splitlines() if not any(k in line for k in ['vendors', 'maestroVendorsHolding', 'purchaseInvoices', 'facturasHolding'])]
        for t_name, _ in vendors_tables:
            lines.append(f"ref table '{t_name}'")
        lines.append('ref table maestroVendorsHolding')
        for t_name, _ in invoices_tables:
            lines.append(f"ref table '{t_name}'")
        lines.append('ref table facturasHolding')
        p['payload'] = base64.b64encode('\n'.join(lines).encode('utf-8')).decode('utf-8')

# Add all 37 vendors tables
for t_name, tmdl in vendors_tables:
    new_parts.append({
        'path': f'definition/tables/{t_name}.tmdl',
        'payload': base64.b64encode(tmdl.encode('utf-8')).decode('utf-8'),
        'payloadType': 'InlineBase64'
    })

# Add maestroVendorsHolding.tmdl
new_parts.append({
    'path': 'definition/tables/maestroVendorsHolding.tmdl',
    'payload': base64.b64encode(tmdl_maestro_vendors.encode('utf-8')).decode('utf-8'),
    'payloadType': 'InlineBase64'
})

# Add all 37 purchaseInvoices tables
for t_name, tmdl in invoices_tables:
    new_parts.append({
        'path': f'definition/tables/{t_name}.tmdl',
        'payload': base64.b64encode(tmdl.encode('utf-8')).decode('utf-8'),
        'payloadType': 'InlineBase64'
    })

# Add facturasHolding.tmdl
new_parts.append({
    'path': 'definition/tables/facturasHolding.tmdl',
    'payload': base64.b64encode(tmdl_facturas_holding.encode('utf-8')).decode('utf-8'),
    'payloadType': 'InlineBase64'
})

print(f"Total parts prepared for updateDefinition: {len(new_parts)}")
print(f"  - Accounts tables: 37 + 1 holding")
print(f"  - AccountingPeriods tables: 37 + 1 holding")
print(f"  - AgedAccountsPayables tables: 37 + 1 holding")
print(f"  - Vendors tables: {len(vendors_tables)} + 1 holding")
print(f"  - PurchaseInvoices tables: {len(invoices_tables)} + 1 holding")

# Save payload to json file for review / sending
with open('update_definition_payload.json', 'w') as out:
    json.dump({'definition': {'parts': new_parts}}, out)
print("Payload written to update_definition_payload.json successfully.")
