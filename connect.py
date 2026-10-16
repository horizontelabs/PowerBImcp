import os
import sys
import json
import msal
import requests

WORKSPACE_ID = "f97935fd-6dda-4c37-8ee6-4c88ced5c434"
DATASET_ID = "d7c2a2e6-17f4-405d-a54a-20a718528dcd"

CLIENT_ID = "ea0616ba-638b-4df5-95b9-636659ae5121"
AUTHORITY = "https://login.microsoftonline.com/organizations"
SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")

def get_token():
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                token_data = json.load(f)
                if "access_token" in token_data:
                    # Validar si el token sigue vivo con el endpoint correcto
                    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
                    check = requests.get(f"https://api.powerbi.com/v1.0/myorg/datasets/{DATASET_ID}", headers=headers)
                    if check.status_code == 200:
                        return token_data["access_token"]
        except Exception:
            pass

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print("Error iniciando flujo:", json.dumps(flow, indent=2))
        sys.exit(1)

    print("\n" + "="*60)
    print("👉 AUTENTICACIÓN CON TU CUENTA MICROSOFT:")
    print(flow["message"])
    print("="*60 + "\n")
    sys.stdout.flush()

    res = app.acquire_token_by_device_flow(flow)
    if "access_token" in res:
        with open(TOKEN_FILE, "w") as f:
            json.dump(res, f)
        print("✅ Autenticación exitosa y guardada.")
        return res["access_token"]
    else:
        print("❌ Error de autenticación:", res.get("error_description"))
        sys.exit(1)

def test_connection():
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Probar endpoint de grupo, si es espacio personal usar endpoint raíz
    dataset_url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{DATASET_ID}"
    r = requests.get(dataset_url, headers=headers)
    is_personal = False

    if r.status_code == 401 and "personal workspace" in r.text:
        is_personal = True
        dataset_url = f"https://api.powerbi.com/v1.0/myorg/datasets/{DATASET_ID}"
        r = requests.get(dataset_url, headers=headers)

    if r.status_code == 200:
        info = r.json()
        print(f"\n📊 Dataset conectado con éxito: {info.get('name')}")
        print(f"   ID: {info.get('id')}")
        print(f"   Configurado por: {info.get('configuredBy')}")
    else:
        print(f"⚠️ Error al consultar dataset: {r.status_code} - {r.text}")
        return

    # Consulta DAX
    if is_personal:
        query_url = f"https://api.powerbi.com/v1.0/myorg/datasets/{DATASET_ID}/executeQueries"
    else:
        query_url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{DATASET_ID}/executeQueries"

    dax_body = {
        "queries": [
            {
                "query": "EVALUATE INFO.VIEW.TABLES()"
            }
        ]
    }
    r = requests.post(query_url, headers=headers, json=dax_body)
    if r.status_code == 200:
        data = r.json()
        rows = data["results"][0]["tables"][0]["rows"]
        print(f"\n📁 Se encontraron {len(rows)} tablas en el modelo:")
        for row in rows[:20]:
            table_name = row.get("Name") or row.get("[Name]")
            print(f"   - {table_name}")
        if len(rows) > 20:
            print(f"   ... y {len(rows) - 20} tablas más.")
    else:
        # Intentar con DMV estándar si INFO.VIEW.TABLES falla
        dax_body_dmv = {
            "queries": [
                {
                    "query": "SELECT [Name] FROM $SYSTEM.TMSCHEMA_TABLES"
                }
            ]
        }
        r2 = requests.post(query_url, headers=headers, json=dax_body_dmv)
        if r2.status_code == 200:
            data = r2.json()
            rows = data["results"][0]["tables"][0]["rows"]
            print(f"\n📁 Se encontraron {len(rows)} tablas en el modelo:")
            for row in rows[:20]:
                table_name = row.get("[Name]") or row.get("Name")
                print(f"   - {table_name}")
        else:
            print(f"\nℹ️ Conectado al dataset (executeQueries status: {r.status_code}).")

if __name__ == "__main__":
    test_connection()
