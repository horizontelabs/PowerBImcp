"""
Dashboard Ejecutivo para Gerencia de Finanzas — SIMONE SPA
Enfocado en la estructura del Plan de Cuentas (Business Central)
Diseño minimalista, jerarquía visual limpia, métricas estructurales reales y tabla maestra de 3 columnas.
"""
import os
import sys
import json
import base64
import time
import requests
import msal

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
WORKSPACE_ID = "f97935fd-6dda-4c37-8ee6-4c88ced5c434"
REPORT_ID = "86bfa92e-97f1-4ee5-b045-f04cad6ebfe8"
DATASET_ID = "83af4580-d8a1-4519-ae25-98bff396291a"

CLIENT_ID = "ea0616ba-638b-4df5-95b9-636659ae5121"
AUTHORITY = "https://login.microsoftonline.com/organizations"
SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]

PAGE_1_ID = "7ade8cc3151e6e014024"
PAGE_2_ID = "accountDetailPage"

SCHEMA_VISUAL_CONTAINER = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json"
SCHEMA_PAGES_META = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

def get_valid_token():
    with open(TOKEN_FILE, "r") as f:
        token_data = json.load(f)

    # Verificar si el token actual está activo
    token = token_data.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    check = requests.get(f"https://api.powerbi.com/v1.0/myorg/reports/{REPORT_ID}", headers=headers)
    if check.status_code == 200:
        return token

    # Si expiró, renovar mediante refresh_token
    print("🔄 Renovando token de acceso expirado...")
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    if "refresh_token" in token_data:
        res = app.acquire_token_by_refresh_token(token_data["refresh_token"], scopes=SCOPES)
        if "access_token" in res:
            token_data.update(res)
            with open(TOKEN_FILE, "w") as f:
                json.dump(token_data, f)
            print("✅ Token renovado exitosamente.")
            return res["access_token"]

    raise Exception("No fue posible renovar el token. Ejecuta connect.py.")

def col_ref(col_name):
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": "accounts"}},
            "Property": col_name
        }
    }

def aggr_ref(col_name, function_id):
    """0=Sum, 1=CountNonNull, 2=Min, 3=Max"""
    return {
        "Aggregation": {
            "Expression": {
                "Column": {
                    "Expression": {"SourceRef": {"Entity": "accounts"}},
                    "Property": col_name
                }
            },
            "Function": function_id
        }
    }

def make_title(title_text):
    return {
        "title": [
            {
                "properties": {
                    "text": {"expr": {"Literal": {"Value": f"'{title_text}'"}}},
                    "show": {"expr": {"Literal": {"Value": "true"}}}
                }
            }
        ]
    }

def build_card_kpi(name, x, y, width, height, tab_order, col_name, aggr_func, display_name, title_text, filter_spec=None):
    field = aggr_ref(col_name, aggr_func) if aggr_func is not None else col_ref(col_name)
    visual_json = {
        "$schema": SCHEMA_VISUAL_CONTAINER,
        "name": name,
        "position": {
            "x": float(x),
            "y": float(y),
            "z": float(tab_order),
            "width": float(width),
            "height": float(height),
            "tabOrder": tab_order
        },
        "visual": {
            "visualType": "card",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            {
                                "field": field,
                                "queryRef": f"accounts.{col_name}",
                                "displayName": display_name
                            }
                        ]
                    }
                }
            },
            "visualContainerObjects": make_title(title_text)
        }
    }

    if filter_spec:
        filter_col, filter_val, filter_name = filter_spec
        val_literal = f"'{filter_val}'" if isinstance(filter_val, str) else str(filter_val).lower()
        visual_json["filterConfig"] = {
            "filters": [
                {
                    "name": filter_name,
                    "type": "Categorical",
                    "field": {
                        "Column": {
                            "Expression": {"SourceRef": {"Entity": "accounts"}},
                            "Property": filter_col
                        }
                    },
                    "filter": {
                        "Version": 2,
                        "From": [{"Name": "a", "Entity": "accounts", "Type": 0}],
                        "Where": [
                            {
                                "Condition": {
                                    "In": {
                                        "Expressions": [
                                            {
                                                "Column": {
                                                    "Expression": {"SourceRef": {"Source": "a"}},
                                                    "Property": filter_col
                                                }
                                            }
                                        ],
                                        "Values": [[{"Literal": {"Value": val_literal}}]]
                                    }
                                }
                            }
                        ]
                    },
                    "howCreated": "User"
                }
            ]
        }

    return visual_json

def build_slicer(name, x, y, width, height, tab_order, col_name, title_text):
    return {
        "$schema": SCHEMA_VISUAL_CONTAINER,
        "name": name,
        "position": {
            "x": float(x),
            "y": float(y),
            "z": float(tab_order),
            "width": float(width),
            "height": float(height),
            "tabOrder": tab_order
        },
        "visual": {
            "visualType": "slicer",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            {
                                "field": col_ref(col_name),
                                "queryRef": f"accounts.{col_name}"
                            }
                        ]
                    }
                }
            },
            "visualContainerObjects": make_title(title_text)
        }
    }

def build_bar_chart(name, x, y, width, height, tab_order, cat_col, val_col, aggr_func, title_text):
    return {
        "$schema": SCHEMA_VISUAL_CONTAINER,
        "name": name,
        "position": {
            "x": float(x),
            "y": float(y),
            "z": float(tab_order),
            "width": float(width),
            "height": float(height),
            "tabOrder": tab_order
        },
        "visual": {
            "visualType": "barChart",
            "query": {
                "queryState": {
                    "Category": {
                        "projections": [
                            {
                                "field": col_ref(cat_col),
                                "queryRef": f"accounts.{cat_col}",
                                "active": True
                            }
                        ]
                    },
                    "Y": {
                        "projections": [
                            {
                                "field": aggr_ref(val_col, aggr_func),
                                "queryRef": f"Aggr(accounts.{val_col})"
                            }
                        ]
                    }
                }
            },
            "drillFilterOtherVisuals": True,
            "visualContainerObjects": make_title(title_text)
        }
    }

def build_table(name, x, y, width, height, tab_order, columns, title_text):
    projections = []
    for col, disp in columns:
        p = {
            "field": col_ref(col),
            "queryRef": f"accounts.{col}"
        }
        if disp:
            p["displayName"] = disp
        projections.append(p)

    return {
        "$schema": SCHEMA_VISUAL_CONTAINER,
        "name": name,
        "position": {
            "x": float(x),
            "y": float(y),
            "z": float(tab_order),
            "width": float(width),
            "height": float(height),
            "tabOrder": tab_order
        },
        "visual": {
            "visualType": "tableEx",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": projections
                    }
                }
            },
            "drillFilterOtherVisuals": True,
            "visualContainerObjects": make_title(title_text)
        }
    }

def generate_minimalist_executive_report(base_parts):
    # Metadata de páginas
    pages_json = {
        "$schema": SCHEMA_PAGES_META,
        "pageOrder": [
            PAGE_1_ID,
            PAGE_2_ID
        ],
        "activePageName": PAGE_1_ID
    }

    # Página 1: Maestro de Cuentas (Dashboard Gerencial)
    p1_json = {
        "$schema": SCHEMA_PAGE,
        "name": PAGE_1_ID,
        "displayName": "Maestro de Cuentas",
        "displayOption": "FitToPage",
        "height": 1080,
        "width": 1920
    }

    # Página 2: Ficha Técnica Individual (Detalle de Cuenta)
    p2_json = {
        "$schema": SCHEMA_PAGE,
        "name": PAGE_2_ID,
        "displayName": "Ficha Técnica de Cuenta",
        "displayOption": "FitToPage",
        "height": 1080,
        "width": 1920
    }

    # Limpiar partes previas de páginas y visuales
    new_parts = [
        p for p in base_parts
        if not p["path"].startswith("definition/pages/") and "visuals" not in p["path"]
    ]

    new_parts.append({
        "path": "definition/pages/pages.json",
        "payload": base64.b64encode(json.dumps(pages_json).encode("utf-8")).decode("utf-8"),
        "payloadType": "InlineBase64"
    })
    new_parts.append({
        "path": f"definition/pages/{PAGE_1_ID}/page.json",
        "payload": base64.b64encode(json.dumps(p1_json).encode("utf-8")).decode("utf-8"),
        "payloadType": "InlineBase64"
    })
    new_parts.append({
        "path": f"definition/pages/{PAGE_2_ID}/page.json",
        "payload": base64.b64encode(json.dumps(p2_json).encode("utf-8")).decode("utf-8"),
        "payloadType": "InlineBase64"
    })

    # =========================================================================
    # PÁGINA 1: MAESTRO DE CUENTAS (MINIMALISTA, PROFESIONAL, ALTO ESPACIO)
    # =========================================================================
    p1_visuals = []

    # 1. Cabecera y Filtros Superiores (y: 25, h: 80)
    p1_visuals.append(build_card_kpi(
        "p1_header_title", 40, 25, 720, 80, 1,
        "number", 1, "Total Cuentas Catálogo",
        "SIMONE SPA — Estructura del Plan de Cuentas Contables (Business Central)"
    ))
    p1_visuals.append(build_slicer(
        "p1_slicer_category", 780, 25, 340, 80, 2,
        "category", "Filtrar por Categoría"
    ))
    p1_visuals.append(build_slicer(
        "p1_slicer_type", 1140, 25, 340, 80, 3,
        "accountType", "Filtrar por Tipo (Posting / Total)"
    ))
    p1_visuals.append(build_slicer(
        "p1_slicer_blocked", 1500, 25, 380, 80, 4,
        "blocked", "Filtrar Estado Bloqueo (True/False)"
    ))

    # 2. Indicadores Clave Ejecutivos (KPIs Estructurales Reales) (y: 120, h: 95)
    # KPI 1: Total Cuentas
    p1_visuals.append(build_card_kpi(
        "p1_kpi_total", 40, 120, 445, 95, 5,
        "number", 1, "386 Cuentas", "Total Cuentas Registradas"
    ))
    # KPI 2: Cuentas Imputables (Posting)
    p1_visuals.append(build_card_kpi(
        "p1_kpi_posting", 505, 120, 445, 95, 6,
        "number", 1, "231 Cuentas", "Cuentas Imputables (Posting)",
        filter_spec=("accountType", "Posting", "FiltroPosting")
    ))
    # KPI 3: Cuentas de Agrupación (Total)
    p1_visuals.append(build_card_kpi(
        "p1_kpi_total_type", 970, 120, 445, 95, 7,
        "number", 1, "155 Cuentas", "Cuentas de Agrupación (Total)",
        filter_spec=("accountType", "Total", "FiltroTotal")
    ))
    # KPI 4: Cuentas Bloqueadas (Inactivas)
    p1_visuals.append(build_card_kpi(
        "p1_kpi_blocked", 1435, 120, 445, 95, 8,
        "number", 1, "14 Cuentas", "Cuentas Bloqueadas en BC",
        filter_spec=("blocked", True, "FiltroBlocked")
    ))

    # 3. Vista Principal — Maestro de Cuentas (Izquierda: x: 40, y: 235, w: 980, h: 810)
    # "una tabla compacta con solo 2–3 columnas relevantes, idealmente number, displayName y category"
    master_cols = [
        ("number", "Nº Cuenta (ID)"),
        ("displayName", "Nombre de la Cuenta"),
        ("category", "Categoría Contable")
    ]
    p1_visuals.append(build_table(
        "p1_table_master", 40, 235, 980, 810, 9,
        master_cols, "Maestro de Cuentas — Haz clic en una fila para desplegar su ficha"
    ))

    # 4. Resumen Visual de Estructura (Derecha Superior: x: 1040, y: 235, w: 840, h: 360)
    # Gráfico de barras horizontal que muestra la distribución limpia del catálogo
    p1_visuals.append(build_bar_chart(
        "p1_chart_distribution", 1040, 235, 840, 360, 10,
        "category", "number", 1, "Distribución del Catálogo por Categoría Contable"
    ))

    # 5. Detalle Interactivo por Cuenta (Derecha Inferior: x: 1040, y: 615, w: 840, h: 430)
    # Panel de detalle con atributos clave al seleccionar una cuenta en la tabla
    detail_cols = [
        ("number", "Nº Cuenta"),
        ("displayName", "Nombre"),
        ("category", "Categoría"),
        ("subCategory", "Subcategoría"),
        ("accountType", "Tipo Cuenta"),
        ("directPosting", "Contabilización Directa"),
        ("blocked", "Bloqueada en BC"),
        ("lastModifiedDateTime", "Última Modificación"),
        ("id", "GUID Business Central")
    ]
    p1_visuals.append(build_table(
        "p1_table_detail", 1040, 615, 840, 430, 11,
        detail_cols, "Ficha Técnica de Cuenta (Detalle al seleccionar en el maestro)"
    ))

    for v in p1_visuals:
        new_parts.append({
            "path": f"definition/pages/{PAGE_1_ID}/visuals/{v['name']}/visual.json",
            "payload": base64.b64encode(json.dumps(v).encode("utf-8")).decode("utf-8"),
            "payloadType": "InlineBase64"
        })

    # =========================================================================
    # PÁGINA 2: FICHA TÉCNICA Y AUDITORÍA INDIVIDUAL DE CUENTA
    # =========================================================================
    p2_visuals = []

    # Buscador superior por ID y Nombre (y: 25, h: 80)
    p2_visuals.append(build_card_kpi(
        "p2_header_name", 40, 25, 720, 80, 1,
        "displayName", 3, "Nombre Cuenta",
        "Auditoría Individual de Cuenta Contable — SIMONE SPA"
    ))
    p2_visuals.append(build_slicer(
        "p2_slicer_number", 780, 25, 540, 80, 2,
        "number", "Buscador por Nº de Cuenta (ID)"
    ))
    p2_visuals.append(build_slicer(
        "p2_slicer_name", 1340, 25, 540, 80, 3,
        "displayName", "Buscador por Nombre de Cuenta"
    ))

    # KPIs de la cuenta seleccionada (y: 120, h: 95)
    p2_visuals.append(build_card_kpi(
        "p2_kpi_id", 40, 120, 445, 95, 4,
        "number", 3, "Código", "Nº de Cuenta (ID)"
    ))
    p2_visuals.append(build_card_kpi(
        "p2_kpi_cat", 505, 120, 445, 95, 5,
        "category", 3, "Categoría", "Categoría Contable"
    ))
    p2_visuals.append(build_card_kpi(
        "p2_kpi_type", 970, 120, 445, 95, 6,
        "accountType", 3, "Tipo", "Tipo (Posting / Total)"
    ))
    p2_visuals.append(build_card_kpi(
        "p2_kpi_blocked", 1435, 120, 445, 95, 7,
        "blocked", 3, "Estado", "¿Bloqueada en BC?"
    ))

    # Tabla técnica exhaustiva con parámetros de Business Central (y: 235, h: 810)
    audit_cols = [
        ("number", "Nº Cuenta (ID)"),
        ("displayName", "Nombre de Cuenta"),
        ("category", "Categoría"),
        ("subCategory", "Subcategoría"),
        ("accountType", "Tipo de Cuenta"),
        ("directPosting", "Permite Contabilización Directa"),
        ("blocked", "¿Bloqueada para Asientos?"),
        ("consolidationTranslationMethod", "Método Conversión Consolidación"),
        ("consolidationDebitAccount", "Cuenta Débito Consolidación"),
        ("consolidationCreditAccount", "Cuenta Crédito Consolidación"),
        ("excludeFromConsolidation", "Excluida de Consolidación"),
        ("lastModifiedDateTime", "Fecha Última Modificación"),
        ("id", "GUID Business Central (ID Sistema)")
    ]
    p2_visuals.append(build_table(
        "p2_table_audit", 40, 235, 1840, 810, 8,
        audit_cols, "Ficha Técnica y Configuración del Sistema en Business Central"
    ))

    for v in p2_visuals:
        new_parts.append({
            "path": f"definition/pages/{PAGE_2_ID}/visuals/{v['name']}/visual.json",
            "payload": base64.b64encode(json.dumps(v).encode("utf-8")).decode("utf-8"),
            "payloadType": "InlineBase64"
        })

    return new_parts

def main():
    token = get_valid_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("="*75)
    print("🏛️ DESPLIEGUE DASHBOARD EJECUTIVO DE FINANZAS — SIMONE SPA")
    print("="*75)

    # 1. Obtener definición base actual del reporte
    print(f"📥 1. Descargando definición base del reporte {REPORT_ID}...")
    r_fab = requests.post(
        f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/reports/{REPORT_ID}/getDefinition",
        headers={"Authorization": f"Bearer {token}"}
    )
    if r_fab.status_code != 202:
        print(f"❌ Error al solicitar definición: {r_fab.status_code} - {r_fab.text}")
        sys.exit(1)

    op_loc = r_fab.headers.get("Location")
    for _ in range(15):
        time.sleep(1.5)
        p = requests.get(op_loc, headers={"Authorization": f"Bearer {token}"}).json()
        if p.get("status") == "Succeeded":
            break

    res = requests.get(f"{op_loc}/result", headers={"Authorization": f"Bearer {token}"}).json()
    base_parts = res.get("definition", {}).get("parts", [])
    print(f"✅ Definición base obtenida ({len(base_parts)} partes).")

    # 2. Generar definición minimalista ejecutiva
    print("🎨 2. Diseñando interfaz minimalista ejecutiva...")
    new_parts = generate_minimalist_executive_report(base_parts)
    print(f"✅ Se compilaron {len(new_parts)} partes PBIR (Maestro 3 columnas, KPIs reales, Ficha y Gráfico).")

    # 3. Aplicar actualización vía Fabric REST API
    print("🚀 3. Desplegando a Power BI Service...")
    r_upd = requests.post(
        f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/reports/{REPORT_ID}/updateDefinition",
        headers=headers,
        json={"definition": {"parts": new_parts}}
    )

    if r_upd.status_code != 202:
        print(f"❌ Error al enviar actualización: {r_upd.status_code} - {r_upd.text}")
        sys.exit(1)

    op_upd = r_upd.headers.get("Location")
    print("⏳ Procesando actualización en la nube...")

    for attempt in range(25):
        time.sleep(2)
        chk = requests.get(op_upd, headers={"Authorization": f"Bearer {token}"}).json()
        status = chk.get("status")
        print(f"   Estado de procesamiento: {status} ({attempt+1}/25)...")
        if status == "Succeeded":
            print("\n" + "="*75)
            print("🎉 ¡DASHBOARD EJECUTIVO DE FINANZAS DESPLEGADO CON ÉXITO!")
            print("="*75)
            print(f"🔗 URL directa al Maestro de Cuentas:")
            print(f"   https://app.powerbi.com/groups/me/reports/{REPORT_ID}/{PAGE_1_ID}?experience=power-bi")
            print("="*75)
            return
        elif status == "Failed":
            print("❌ Error en updateDefinition:", json.dumps(chk.get("error"), indent=2))
            sys.exit(1)

    print("⚠️ La operación tardó más de lo esperado.")

if __name__ == "__main__":
    main()
