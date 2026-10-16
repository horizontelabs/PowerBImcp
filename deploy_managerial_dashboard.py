"""
Script para generar y desplegar el Dashboard Gerencial de Cuentas Contables en Power BI Service.
Conecta al reporte oficial de SIMONE SPA V3 mediante Microsoft Fabric REST API (PBIR format).
"""
import os
import sys
import json
import base64
import time
import requests

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
WORKSPACE_ID = "f97935fd-6dda-4c37-8ee6-4c88ced5c434"
REPORT_ID = "86bfa92e-97f1-4ee5-b045-f04cad6ebfe8"
DATASET_ID = "83af4580-d8a1-4519-ae25-98bff396291a"

PAGE_1_ID = "7ade8cc3151e6e014024"
PAGE_2_ID = "accountDetailPage"

SCHEMA_VISUAL_CONTAINER = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json"
SCHEMA_PAGES_META = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

def get_token():
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)["access_token"]

def col_ref(col_name):
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": "accounts"}},
            "Property": col_name
        }
    }

def aggr_ref(col_name, function_id):
    """function_id: 0 = Sum, 1 = CountNonNull, 2 = Min, 3 = Max"""
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

def build_card(name, x, y, width, height, tab_order, col_name, aggr_func, display_name, title_text):
    if aggr_func is not None:
        field = aggr_ref(col_name, aggr_func)
        query_ref = f"Aggr({col_name})"
    else:
        field = col_ref(col_name)
        query_ref = f"accounts.{col_name}"

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
                                "queryRef": query_ref,
                                "displayName": display_name
                            }
                        ]
                    }
                }
            },
            "visualContainerObjects": make_title(title_text)
        }
    }
    return visual_json

def build_slicer(name, x, y, width, height, tab_order, col_name, title_text):
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
    return visual_json

def build_donut(name, x, y, width, height, tab_order, cat_col, val_col, title_text):
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
            "visualType": "donutChart",
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
                                "field": aggr_ref(val_col, 1),
                                "queryRef": f"CountNonNull(accounts.{val_col})"
                            }
                        ]
                    }
                }
            },
            "drillFilterOtherVisuals": True,
            "visualContainerObjects": make_title(title_text)
        }
    }
    return visual_json

def build_column_chart(name, x, y, width, height, tab_order, cat_col, val_col, aggr_func, title_text):
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
            "visualType": "columnChart",
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
    return visual_json

def build_bar_chart(name, x, y, width, height, tab_order, cat_col, val_col, aggr_func, title_text):
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
    return visual_json

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
    return visual_json

def generate_report_parts(base_parts):
    # Definir pages.json con 2 páginas
    pages_json = {
        "$schema": SCHEMA_PAGES_META,
        "pageOrder": [
            PAGE_1_ID,
            PAGE_2_ID
        ],
        "activePageName": PAGE_1_ID
    }

    # Página 1: Dashboard Gerencial
    p1_json = {
        "$schema": SCHEMA_PAGE,
        "name": PAGE_1_ID,
        "displayName": "Dashboard Gerencial",
        "displayOption": "FitToPage",
        "height": 1080,
        "width": 1920
    }

    # Página 2: Detalle de Cuenta
    p2_json = {
        "$schema": SCHEMA_PAGE,
        "name": PAGE_2_ID,
        "displayName": "Detalle de Cuenta",
        "displayOption": "FitToPage",
        "height": 1080,
        "width": 1920
    }

    # Limpiar cualquier página o visual previo para evitar duplicados
    new_parts = [
        p for p in base_parts
        if not p["path"].startswith("definition/pages/") and "visuals" not in p["path"]
    ]

    # Agregar pages.json
    new_parts.append({
        "path": "definition/pages/pages.json",
        "payload": base64.b64encode(json.dumps(pages_json).encode("utf-8")).decode("utf-8"),
        "payloadType": "InlineBase64"
    })

    # Agregar Página 1: Dashboard Gerencial
    new_parts.append({
        "path": f"definition/pages/{PAGE_1_ID}/page.json",
        "payload": base64.b64encode(json.dumps(p1_json).encode("utf-8")).decode("utf-8"),
        "payloadType": "InlineBase64"
    })

    # Agregar Página 2: Detalle de Cuenta
    new_parts.append({
        "path": f"definition/pages/{PAGE_2_ID}/page.json",
        "payload": base64.b64encode(json.dumps(p2_json).encode("utf-8")).decode("utf-8"),
        "payloadType": "InlineBase64"
    })

    # ==========================================
    # VISUALES PÁGINA 1: DASHBOARD GERENCIAL
    # ==========================================
    p1_visuals = []

    # Fila 1: Cabecera y Filtros Macro (y: 20, h: 90)
    p1_visuals.append(build_card(
        "v1_header_title", 20, 20, 740, 90, 1,
        "number", 1, "Total Cuentas Catálogo",
        "SIMONE SPA — Panel Gerencial de Cuentas Contables (Business Central)"
    ))
    p1_visuals.append(build_slicer(
        "v1_slicer_category", 780, 20, 360, 90, 2,
        "category", "Filtrar por Categoría Contable"
    ))
    p1_visuals.append(build_slicer(
        "v1_slicer_account_type", 1160, 20, 360, 90, 3,
        "accountType", "Filtrar por Tipo (Posting / Total)"
    ))
    p1_visuals.append(build_slicer(
        "v1_slicer_blocked", 1540, 20, 360, 90, 4,
        "blocked", "Filtrar Estado de Bloqueo"
    ))

    # Fila 2: Indicadores Clave Macro (KPI Cards) (y: 125, h: 100)
    p1_visuals.append(build_card(
        "v1_kpi_total", 20, 125, 360, 100, 5,
        "number", 1, "Total Cuentas", "Universo de Cuentas Registradas"
    ))
    p1_visuals.append(build_card(
        "v1_kpi_net_change", 400, 125, 420, 100, 6,
        "netChange", 0, "Saldo Neto Consolidado", "Saldo Neto Total (CLP)"
    ))
    p1_visuals.append(build_card(
        "v1_kpi_direct_posting", 840, 125, 340, 100, 7,
        "displayName", 1, "Cuentas con Nombre", "Cuentas Imputables Activas"
    ))
    p1_visuals.append(build_card(
        "v1_kpi_min_account", 1200, 125, 340, 100, 8,
        "number", 2, "Cuenta Inicial", "Rango Inicial (Mínimo Código)"
    ))
    p1_visuals.append(build_card(
        "v1_kpi_max_account", 1560, 125, 340, 100, 9,
        "number", 3, "Cuenta Final", "Rango Final (Máximo Código)"
    ))

    # Fila 3: Gráficos Macro de Distribución (y: 240, h: 320)
    p1_visuals.append(build_donut(
        "v1_donut_category", 20, 240, 580, 320, 10,
        "category", "number", "Distribución de Cuentas por Categoría (Activo, Pasivo, etc.)"
    ))
    p1_visuals.append(build_column_chart(
        "v1_col_net_category", 620, 240, 680, 320, 11,
        "category", "netChange", 0, "Saldo Neto Total por Categoría Contable (CLP)"
    ))
    p1_visuals.append(build_bar_chart(
        "v1_bar_account_type", 1320, 240, 580, 320, 12,
        "accountType", "number", 1, "Cuentas por Tipo de Registro (Posting vs Total)"
    ))

    # Fila 4: Master-Detail Explorer (y: 575, h: 485)
    # Tabla Master: Directorio de Cuentas con IDs para presionar
    master_cols = [
        ("number", "Nº Cuenta (ID)"),
        ("displayName", "Nombre de Cuenta"),
        ("category", "Categoría"),
        ("subCategory", "Subcategoría"),
        ("accountType", "Tipo"),
        ("netChange", "Saldo Neto (CLP)"),
        ("directPosting", "Registro Directo"),
        ("blocked", "Bloqueada")
    ]
    p1_visuals.append(build_table(
        "v1_table_master", 20, 575, 1060, 485, 13,
        master_cols, "Directorio de Cuentas — Presiona un ID o fila para detallar en la ficha"
    ))

    # Ficha Detalle: Información Completa de la Cuenta Seleccionada
    detail_cols = [
        ("number", "Nº Cuenta (ID)"),
        ("displayName", "Nombre Cuenta"),
        ("id", "GUID Business Central"),
        ("category", "Categoría"),
        ("subCategory", "Subcategoría"),
        ("accountType", "Tipo de Cuenta"),
        ("netChange", "Saldo Neto"),
        ("directPosting", "Permite Registro Directo"),
        ("blocked", "Bloqueada en BC"),
        ("consolidationTranslationMethod", "Método Consolidación"),
        ("lastModifiedDateTime", "Última Modificación")
    ]
    p1_visuals.append(build_table(
        "v1_table_detail", 1100, 575, 800, 485, 14,
        detail_cols, "Ficha Técnica Detallada (Cuenta Seleccionada en la Tabla)"
    ))

    for v in p1_visuals:
        new_parts.append({
            "path": f"definition/pages/{PAGE_1_ID}/visuals/{v['name']}/visual.json",
            "payload": base64.b64encode(json.dumps(v).encode("utf-8")).decode("utf-8"),
            "payloadType": "InlineBase64"
        })

    # ==========================================
    # VISUALES PÁGINA 2: DETALLE DE CUENTA INDIVIDUAL
    # ==========================================
    p2_visuals = []

    # Fila 1: Header y Buscadores por ID / Nombre (y: 20, h: 100)
    p2_visuals.append(build_card(
        "v2_header_card", 20, 20, 700, 100, 1,
        "displayName", 3, "Nombre de la Cuenta",
        "SIMONE SPA — Ficha de Auditoría y Detalle Individual de Cuenta"
    ))
    p2_visuals.append(build_slicer(
        "v2_slicer_id", 740, 20, 560, 100, 2,
        "number", "Buscar / Seleccionar por Nº de Cuenta (ID)"
    ))
    p2_visuals.append(build_slicer(
        "v2_slicer_name", 1320, 20, 580, 100, 3,
        "displayName", "Buscar / Seleccionar por Nombre de Cuenta"
    ))

    # Fila 2: KPIs de la Cuenta Seleccionada (y: 135, h: 115)
    p2_visuals.append(build_card(
        "v2_kpi_id", 20, 135, 360, 115, 4,
        "number", 3, "Código Contable (ID)", "Nº de Cuenta (ID)"
    ))
    p2_visuals.append(build_card(
        "v2_kpi_net", 400, 135, 360, 115, 5,
        "netChange", 0, "Monto Saldo Neto", "Saldo / Movimiento Neto (CLP)"
    ))
    p2_visuals.append(build_card(
        "v2_kpi_cat", 780, 135, 360, 115, 6,
        "category", 3, "Categoría", "Categoría Contable"
    ))
    p2_visuals.append(build_card(
        "v2_kpi_type", 1160, 135, 360, 115, 7,
        "accountType", 3, "Tipo (Posting / Total)", "Tipo de Cuenta"
    ))
    p2_visuals.append(build_card(
        "v2_kpi_blocked", 1540, 135, 360, 115, 8,
        "blocked", 3, "¿Bloqueada en BC?", "Estado de Bloqueo"
    ))

    # Fila 3: Ficha Técnica Completa con TODOS los Atributos de Business Central (y: 265, h: 795)
    p2_full_cols = [
        ("number", "Nº de Cuenta (ID)"),
        ("displayName", "Nombre de la Cuenta"),
        ("id", "GUID Business Central (ID Sistema)"),
        ("category", "Categoría Contable"),
        ("subCategory", "Subcategoría"),
        ("accountType", "Tipo de Cuenta (Posting/Total)"),
        ("netChange", "Saldo Neto Acumulado (CLP)"),
        ("directPosting", "Permite Registro Directo"),
        ("blocked", "¿Bloqueada para Imputaciones?"),
        ("consolidationTranslationMethod", "Método Conversión Consolidación"),
        ("consolidationDebitAccount", "Cuenta Débito Consolidación"),
        ("consolidationCreditAccount", "Cuenta Crédito Consolidación"),
        ("excludeFromConsolidation", "Excluir de Consolidación"),
        ("lastModifiedDateTime", "Fecha y Hora Última Modificación")
    ]
    p2_visuals.append(build_table(
        "v2_full_table", 20, 265, 1880, 795, 9,
        p2_full_cols, "Ficha Técnica Exhaustiva — Todos los Parámetros y Configuración en Business Central"
    ))

    for v in p2_visuals:
        new_parts.append({
            "path": f"definition/pages/{PAGE_2_ID}/visuals/{v['name']}/visual.json",
            "payload": base64.b64encode(json.dumps(v).encode("utf-8")).decode("utf-8"),
            "payloadType": "InlineBase64"
        })

    return new_parts

def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("="*70)
    print("🚀 DESPLIEGUE DASHBOARD GERENCIAL POWER BI — SIMONE SPA V3")
    print("="*70)

    # 1. Obtener definición base actual del reporte
    print(f"📥 1. Descargando definición PBIR del reporte {REPORT_ID}...")
    r_fab = requests.post(
        f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/reports/{REPORT_ID}/getDefinition",
        headers={"Authorization": f"Bearer {token}"}
    )
    if r_fab.status_code != 202:
        print(f"❌ Error al solicitar definición: {r_fab.status_code} - {r_fab.text}")
        sys.exit(1)

    op_loc = r_fab.headers.get("Location") or r_fab.headers.get("Operation-Location")
    for attempt in range(20):
        time.sleep(1.5)
        p = requests.get(op_loc, headers={"Authorization": f"Bearer {token}"}).json()
        if p.get("status") == "Succeeded":
            break
        elif p.get("status") == "Failed":
            print("❌ Error en getDefinition:", p.get("error"))
            sys.exit(1)

    res = requests.get(f"{op_loc}/result", headers={"Authorization": f"Bearer {token}"}).json()
    base_parts = res.get("definition", {}).get("parts", [])
    print(f"✅ Definición obtenida. {len(base_parts)} partes base.")

    # 2. Generar nuevas partes del dashboard gerencial
    print("🎨 2. Construyendo visuales del Dashboard Gerencial y Ficha de Cuenta...")
    new_parts = generate_report_parts(base_parts)
    print(f"✅ Se configuraron {len(new_parts)} partes (Páginas y Visuales PBIR).")

    # 3. Aplicar actualización vía updateDefinition
    print("🚀 3. Enviando actualización a Power BI Service...")
    r_upd = requests.post(
        f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/reports/{REPORT_ID}/updateDefinition",
        headers=headers,
        json={"definition": {"parts": new_parts}}
    )

    if r_upd.status_code != 202:
        print(f"❌ Error al enviar updateDefinition: {r_upd.status_code} - {r_upd.text}")
        sys.exit(1)

    op_upd = r_upd.headers.get("Location") or r_upd.headers.get("Operation-Location")
    print(f"⏳ Procesando actualización en el servicio (Operación: {op_upd.split('/')[-1]})...")

    for attempt in range(25):
        time.sleep(2)
        chk = requests.get(op_upd, headers={"Authorization": f"Bearer {token}"}).json()
        status = chk.get("status")
        print(f"   Estado: {status} ({attempt+1}/25)...")
        if status == "Succeeded":
            print("\n" + "="*70)
            print("🎉 ¡DASHBOARD GERENCIAL CREADO Y DESPLEGADO CON ÉXITO TOTAL!")
            print("="*70)
            print(f"🔗 URL del reporte actualizado:")
            print(f"   https://app.powerbi.com/groups/me/reports/{REPORT_ID}/{PAGE_1_ID}?experience=power-bi")
            print(f"\n📄 Páginas disponibles:")
            print(f"   1. Dashboard Gerencial (Visión Macro, KPIs, Gráficos y Selector de Cuentas por ID)")
            print(f"   2. Detalle de Cuenta (Ficha Técnica exhaustiva con todos los campos de Business Central)")
            print("="*70)
            return
        elif status == "Failed":
            print("❌ Error en updateDefinition:", json.dumps(chk.get("error"), indent=2))
            sys.exit(1)

    print("⚠️ La operación tardó más de lo esperado. Por favor verifica en el portal de Power BI.")

if __name__ == "__main__":
    main()
