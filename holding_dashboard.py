"""Holding Insigne multi-company management dashboard — builds PBIR definition and deploys it.

Consolidates all 37 companies of Holding Insigne into an executive Power BI dashboard:
- Page 1: Consolidado financiero (Holding P&L, Balance Sheet, Multi-company Ranking & Comparison)
- Page 2: Gobernanza del catálogo (Cross-company COA audit, posting vs summary, blocked accounts)
- Page 3: Períodos y cierres contables (Fiscal periods, closed months, date locks)

Usage:
    python holding_dashboard.py --dry-run  # Pull, build, write local PBIP folder only
    python holding_dashboard.py            # Pull, build, write local PBIP, and push live
"""
import argparse
import base64
import json
import os
import shutil
import sys
import time

import msal
import requests

WORKSPACE_ID = "f97935fd-6dda-4c37-8ee6-4c88ced5c434"
REPORT_ID = "67d5b2fd-4139-4c10-8948-ec838415f5f3"
DATASET_ID = "c71af0b4-2794-415e-a304-ce9a9fcb3619"
CLIENT_ID = "ea0616ba-638b-4df5-95b9-636659ae5121"
AUTHORITY = "https://login.microsoftonline.com/organizations"
SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(HERE, "token.json")
LOCAL_REPORT_DIR = os.path.join(HERE, "HOLDING_INSIGNE_V1.pbip", "HOLDING_INSIGNE_V1.Report")

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
SCHEMA_VISUAL = SCHEMA + "visualContainer/2.0.0/schema.json"
SCHEMA_PAGE = SCHEMA + "page/2.1.0/schema.json"
SCHEMA_PAGES = SCHEMA + "pagesMetadata/1.1.0/schema.json"
SCHEMA_EXTENSION = SCHEMA + "reportExtension/1.0.0/schema.json"

PAGE_1_NAME = "consolidadoFinanciero"
PAGE_2_NAME = "gobernanzaCatalogo"
PAGE_3_NAME = "periodosContables"

ENTITY_ACCOUNTS = "cuentasHolding"
ENTITY_PERIODS = "periodosHolding"

POSTING = 'cuentasHolding[accountType] = "Posting"'
CATEGORY = {
    "assets": "Assets",
    "liabilities": "Liabilities",
    "equity": "Equity",
    "income": "Income",
    "cogs": "Cost_x0020_of_x0020_Goods_x0020_Sold",
    "expense": "Expense",
}
DEBIT_NATURE = (CATEGORY["assets"], CATEGORY["expense"], CATEGORY["cogs"])
MILLIONS = '#,0,, "MM$"'

BLUE, ORANGE, AQUA, NAVY = "#2a78d6", "#eb6834", "#1baf7a", "#0d366b"
INK, INK_MUTED = "#0b0b0b", "#52514e"


def _balance(category, sign=""):
    return f"{sign}CALCULATE(SUM(cuentasHolding[netChange]), {POSTING}, cuentasHolding[category] = \"{category}\")"


MEASURES_ACCOUNTS = [
    ("Activos", _balance(CATEGORY["assets"]), [], MILLIONS),
    ("Pasivos", _balance(CATEGORY["liabilities"], "-"), [], MILLIONS),
    ("Patrimonio", _balance(CATEGORY["equity"], "-"), [], MILLIONS),
    ("Ingresos", _balance(CATEGORY["income"], "-"), [], MILLIONS),
    ("Costo de ventas", _balance(CATEGORY["cogs"], "-"), [], MILLIONS),
    ("Gastos", _balance(CATEGORY["expense"], "-"), [], MILLIONS),
    ("Resultado", "[Ingresos] + [Costo de ventas] + [Gastos]", ["Ingresos", "Costo de ventas", "Gastos"], MILLIONS),
    (
        "Saldo natural",
        "CALCULATE(SUMX(cuentasHolding, IF(cuentasHolding[category] IN {"
        + ", ".join(f'"{c}"' for c in DEBIT_NATURE)
        + f"}}, cuentasHolding[netChange], -cuentasHolding[netChange])), {POSTING})",
        [],
        MILLIONS,
    ),
    ("Empresas activas", "DISTINCTCOUNT(cuentasHolding[Empresa])", [], "#,0"),
    ("Total cuentas", "COUNTROWS(cuentasHolding)", [], "#,0"),
    ("Cuentas imputables", 'CALCULATE(COUNTROWS(cuentasHolding), cuentasHolding[accountType] = "Posting")', [], "#,0"),
    ("Cuentas agrupacion", 'CALCULATE(COUNTROWS(cuentasHolding), cuentasHolding[accountType] = "Total")', [], "#,0"),
    ("Cuentas bloqueadas", "CALCULATE(COUNTROWS(cuentasHolding), cuentasHolding[blocked] = TRUE)", [], "#,0"),
    ("Cuentas registro directo", "CALCULATE(COUNTROWS(cuentasHolding), cuentasHolding[directPosting] = TRUE)", [], "#,0"),
]

MEASURES_PERIODS = [
    ("Total periodos", "COUNTROWS(periodosHolding)", [], "#,0"),
    ("Periodos cerrados", "CALCULATE(COUNTROWS(periodosHolding), periodosHolding[closed] = TRUE)", [], "#,0"),
    ("Periodos abiertos", "CALCULATE(COUNTROWS(periodosHolding), periodosHolding[closed] = FALSE)", [], "#,0"),
    ("Fechas bloqueadas", "CALCULATE(COUNTROWS(periodosHolding), periodosHolding[dateLocked] = TRUE)", [], "#,0"),
]


def report_extensions():
    def _build_entity(entity_name, measure_list):
        measures = []
        for name, expression, refs, fmt in measure_list:
            m = {"name": name, "dataType": "Double", "expression": expression, "formatString": fmt}
            if refs:
                m["references"] = {"measures": [{"schema": "extension", "entity": entity_name, "name": r} for r in refs]}
            measures.append(m)
        return {"name": entity_name, "measures": measures}

    return {
        "$schema": SCHEMA_EXTENSION,
        "name": "extension",
        "entities": [
            _build_entity(ENTITY_ACCOUNTS, MEASURES_ACCOUNTS),
            _build_entity(ENTITY_PERIODS, MEASURES_PERIODS),
        ],
    }


def measure_ref(name, entity=ENTITY_ACCOUNTS):
    return {"Measure": {"Expression": {"SourceRef": {"Schema": "extension", "Entity": entity}}, "Property": name}}


def column_ref(column, entity=ENTITY_ACCOUNTS):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": column}}


def measure_projection(name, entity=ENTITY_ACCOUNTS):
    return {"field": measure_ref(name, entity), "queryRef": f"{entity}.{name}", "nativeQueryRef": name}


def column_projection(column, entity=ENTITY_ACCOUNTS, active=False):
    p = {"field": column_ref(column, entity), "queryRef": f"{entity}.{column}", "nativeQueryRef": column}
    if active:
        p["active"] = True
    return p


def literal(value):
    return {"expr": {"Literal": {"Value": value}}}


def solid(hex_color):
    return {"solid": {"color": literal(f"'{hex_color}'")}}


def props(**kw):
    return [{"properties": kw}]


def container(name, x, y, w, h, z, visual, filters=None):
    doc = {
        "$schema": SCHEMA_VISUAL,
        "name": name,
        "position": {"x": float(x), "y": float(y), "z": float(z), "width": float(w), "height": float(h), "tabOrder": z},
        "visual": visual,
    }
    if filters:
        doc["filterConfig"] = {"filters": filters}
    return doc


def header(title, subtitle):
    return {
        "title": props(show=literal("true"), text=literal(f"'{title}'"), fontSize=literal("13D"), bold=literal("true"), fontColor=solid(INK)),
        "subTitle": props(show=literal("true"), text=literal(f"'{subtitle}'"), fontSize=literal("9.5D"), fontColor=solid(INK_MUTED)),
    }


def textbox(title, subtitle):
    run = lambda text, size, weight, color: {"value": text, "textStyle": {"fontSize": size, "fontWeight": weight, "color": color}}
    return {
        "visualType": "textbox",
        "objects": {
            "general": props(
                paragraphs=[
                    {"textRuns": [run(title, "18pt", "bold", INK)]},
                    {"textRuns": [run(subtitle, "10pt", "normal", INK_MUTED)]},
                ]
            )
        },
    }


def slicer_visual(title, column, entity=ENTITY_ACCOUNTS):
    return {
        "visualType": "slicer",
        "query": {
            "queryState": {
                "Values": {"projections": [column_projection(column, entity=entity, active=True)]}
            }
        },
        "visualContainerObjects": {
            "title": props(show=literal("true"), text=literal(f"'{title}'"), fontSize=literal("10D"), bold=literal("true"), fontColor=solid(INK)),
        },
    }


def kpi_card(title, subtitle, measure_name, entity=ENTITY_ACCOUNTS):
    return {
        "visualType": "card",
        "query": {
            "queryState": {
                "Values": {"projections": [measure_projection(measure_name, entity=entity)]}
            }
        },
        "objects": {
            "labels": props(fontSize=literal("20D"), color=solid(INK)),
        },
        "visualContainerObjects": header(title, subtitle),
    }


def company_ranking_bar(title, subtitle, measure_name, color=BLUE):
    return {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [column_projection("Empresa", entity=ENTITY_ACCOUNTS, active=True)]},
                "Y": {"projections": [measure_projection(measure_name, entity=ENTITY_ACCOUNTS)]},
            },
            "sortDefinition": {
                "sort": [{"field": measure_ref(measure_name, entity=ENTITY_ACCOUNTS), "direction": "Descending"}],
                "isDefaultSort": True,
            },
        },
        "objects": {
            "legend": props(show=literal("false")),
            "labels": props(show=literal("true"), labelDisplayUnits=literal("1D"), labelPrecision=literal("0D"), color=solid(INK)),
            "valueAxis": props(show=literal("false"), gridlineShow=literal("false")),
            "categoryAxis": props(show=literal("true"), fontSize=literal("9D"), labelColor=solid(INK), maxMarginFactor=literal("40D")),
            "dataPoint": props(fill=solid(color)),
        },
        "visualContainerObjects": header(title, subtitle),
    }


def measures_column_chart(title, subtitle, series):
    return {
        "visualType": "clusteredColumnChart",
        "query": {
            "queryState": {
                "Y": {"projections": [measure_projection(n, entity=ENTITY_ACCOUNTS) for n, _ in series]}
            }
        },
        "objects": {
            "legend": props(show=literal("false")),
            "labels": props(show=literal("true"), labelDisplayUnits=literal("1D"), labelPrecision=literal("0D"), color=solid(INK)),
            "valueAxis": props(show=literal("false"), gridlineShow=literal("false")),
            "categoryAxis": props(show=literal("true"), fontSize=literal("10D"), labelColor=solid(INK)),
            "dataPoint": [{"properties": {"fill": solid(color)}, "selector": {"metadata": f"{ENTITY_ACCOUNTS}.{n}"}} for n, color in series],
        },
        "visualContainerObjects": header(title, subtitle),
    }


def multi_company_matrix_table(title, subtitle):
    return {
        "visualType": "tableEx",
        "query": {
            "queryState": {
                "Values": {
                    "projections": [
                        column_projection("Empresa", entity=ENTITY_ACCOUNTS),
                        measure_projection("Activos", entity=ENTITY_ACCOUNTS),
                        measure_projection("Pasivos", entity=ENTITY_ACCOUNTS),
                        measure_projection("Patrimonio", entity=ENTITY_ACCOUNTS),
                        measure_projection("Ingresos", entity=ENTITY_ACCOUNTS),
                        measure_projection("Resultado", entity=ENTITY_ACCOUNTS),
                    ]
                }
            }
        },
        "visualContainerObjects": header(title, subtitle),
    }


def table_visual(title, subtitle, columns, entity=ENTITY_ACCOUNTS):
    return {
        "visualType": "tableEx",
        "query": {
            "queryState": {
                "Values": {"projections": [column_projection(col, entity=entity) for col in columns]}
            }
        },
        "visualContainerObjects": header(title, subtitle),
    }


def category_distribution_bar(title, subtitle):
    return {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [column_projection("category", entity=ENTITY_ACCOUNTS, active=True)]},
                "Y": {"projections": [measure_projection("Total cuentas", entity=ENTITY_ACCOUNTS)]},
            },
            "sortDefinition": {"sort": [{"field": measure_ref("Total cuentas", entity=ENTITY_ACCOUNTS), "direction": "Descending"}], "isDefaultSort": True},
        },
        "objects": {
            "legend": props(show=literal("false")),
            "labels": props(show=literal("true"), labelDisplayUnits=literal("1D"), labelPrecision=literal("0D"), color=solid(INK)),
            "valueAxis": props(show=literal("false"), gridlineShow=literal("false")),
            "categoryAxis": props(show=literal("true"), fontSize=literal("10D"), labelColor=solid(INK)),
            "dataPoint": props(fill=solid(BLUE)),
        },
        "visualContainerObjects": header(title, subtitle),
    }


# ----------------------------------------------------------- page visuals ---


def page_1_visuals():
    return [
        container("titulo_consolidado", 40, 20, 1380, 55, 1, textbox(
            "HOLDING INSIGNE — Consolidado Financiero Multi-Empresa",
            "Visión patrimonial, balance general y estado de resultados consolidado de las 37 filiales (CLP MM$)",
        )),
        container("slicer_empresa", 1440, 20, 440, 60, 2, slicer_visual(
            "Filtrar por Filial / Empresa", "Empresa", entity=ENTITY_ACCOUNTS
        )),
        container("kpi_activos", 40, 85, 350, 95, 3, kpi_card(
            "Activos Totales", "Masa activa consolidada de las sociedades", "Activos"
        )),
        container("kpi_pasivos", 410, 85, 350, 95, 4, kpi_card(
            "Pasivos Totales", "Obligaciones totales con terceros y acreedores", "Pasivos"
        )),
        container("kpi_patrimonio", 780, 85, 350, 95, 5, kpi_card(
            "Patrimonio Neto", "Capital y reservas acumuladas del holding", "Patrimonio"
        )),
        container("kpi_resultado", 1150, 85, 350, 95, 6, kpi_card(
            "Resultado del Ejercicio", "Utilidad / Pérdida neta consolidada", "Resultado"
        )),
        container("kpi_empresas", 1520, 85, 360, 95, 7, kpi_card(
            "Sociedades Holding", "Total empresas operativas en Business Central", "Empresas activas"
        )),
        container("ranking_activos", 40, 190, 900, 420, 8, company_ranking_bar(
            "Ranking de Sociedades por Activos Totales (Top Holdings)",
            "Distribución y escala de volumen patrimonial por empresa (MM$)",
            "Activos",
            color=BLUE,
        )),
        container("ranking_patrimonio", 960, 190, 920, 420, 9, company_ranking_bar(
            "Ranking de Sociedades por Patrimonio Neto",
            "Respaldo patrimonial y solvencia neta por filial (MM$)",
            "Patrimonio",
            color=AQUA,
        )),
        container("estructura_financiera", 40, 625, 440, 425, 10, measures_column_chart(
            "Estructura Patrimonial Consolidada",
            "Activos frente a Pasivos y Patrimonio",
            [("Activos", BLUE), ("Pasivos", ORANGE), ("Patrimonio", AQUA)],
        )),
        container("estado_resultados", 500, 625, 440, 425, 11, measures_column_chart(
            "Desglose de Resultados (P&L)",
            "Ingresos menos costos operacionales y gastos",
            [("Ingresos", BLUE), ("Costo de ventas", ORANGE), ("Gastos", ORANGE), ("Resultado", NAVY)],
        )),
        container("matriz_resumen_empresas", 960, 625, 920, 425, 12, multi_company_matrix_table(
            "Matriz Financiera Ejecutiva por Sociedad (Inter-Empresa)",
            "Comparativa directa de Activos, Pasivos, Patrimonio e Ingresos por empresa",
        )),
    ]


def page_2_visuals():
    return [
        container("titulo_gobernanza", 40, 20, 1380, 55, 1, textbox(
            "HOLDING INSIGNE — Gobernanza y Auditoría del Catálogo Contable",
            "Homologación, parametrización y control de 14.356 cuentas contables en las 37 filiales",
        )),
        container("slicer_empresa_p2", 1440, 20, 440, 60, 2, slicer_visual(
            "Filtrar Catálogo por Filial", "Empresa", entity=ENTITY_ACCOUNTS
        )),
        container("kpi_total_cuentas", 40, 85, 350, 95, 3, kpi_card(
            "Total Cuentas Catálogo", "Universo consolidado en Business Central", "Total cuentas"
        )),
        container("kpi_cuentas_imputables", 410, 85, 350, 95, 4, kpi_card(
            "Cuentas Imputables (Posting)", "Cuentas operativas que reciben asientos", "Cuentas imputables"
        )),
        container("kpi_cuentas_agrupacion", 780, 85, 350, 95, 5, kpi_card(
            "Cuentas Agrupación (Total)", "Títulos y subtotales del plan de cuentas", "Cuentas agrupacion"
        )),
        container("kpi_cuentas_bloqueadas", 1150, 85, 350, 95, 6, kpi_card(
            "Cuentas Bloqueadas", "Restringidas para nuevos registros", "Cuentas bloqueadas"
        )),
        container("kpi_registro_directo", 1520, 85, 360, 95, 7, kpi_card(
            "Contabilización Directa", "Permiten imputación manual directa por diario", "Cuentas registro directo"
        )),
        container("cuentas_por_empresa", 40, 190, 900, 390, 8, company_ranking_bar(
            "Profundidad del Catálogo por Filial",
            "Cantidad de cuentas registradas por empresa (control de homologación)",
            "Total cuentas",
            color=BLUE,
        )),
        container("distribucion_categoria", 960, 190, 920, 390, 9, category_distribution_bar(
            "Distribución del Catálogo por Clase Contable",
            "Número de cuentas por categoría contable en el holding",
        )),
        container("maestro_cuentas_holding", 40, 595, 1840, 455, 10, table_visual(
            "Maestro Consolidado de Cuentas Contables (Búsqueda y Auditoría)",
            "Detalle de cuentas, clasificación, políticas de registro y saldo contable acumulado por sociedad",
            ["Empresa", "number", "displayName", "category", "accountType", "blocked", "directPosting", "netChange"],
            entity=ENTITY_ACCOUNTS,
        )),
    ]


def page_3_visuals():
    return [
        container("titulo_periodos", 40, 20, 1380, 55, 1, textbox(
            "HOLDING INSIGNE — Control de Períodos y Cierres Contables",
            "Monitoreo de ejercicios fiscales, meses cerrados y control de fechas bloqueadas en las 37 filiales",
        )),
        container("slicer_empresa_p3", 1440, 20, 440, 60, 2, slicer_visual(
            "Filtrar Períodos por Filial", "Empresa", entity=ENTITY_PERIODS
        )),
        container("kpi_total_periodos", 40, 85, 440, 95, 3, kpi_card(
            "Total Períodos Registrados", "Histórico de meses y ejercicios en BC", "Total periodos", entity=ENTITY_PERIODS
        )),
        container("kpi_periodos_cerrados", 505, 85, 440, 95, 4, kpi_card(
            "Períodos Cerrados Definitivos", "Meses con cierre formal completado", "Periodos cerrados", entity=ENTITY_PERIODS
        )),
        container("kpi_periodos_abiertos", 970, 85, 440, 95, 5, kpi_card(
            "Períodos Abiertos Vigentes", "Meses disponibles para contabilización", "Periodos abiertos", entity=ENTITY_PERIODS
        )),
        container("kpi_fechas_bloqueadas", 1435, 85, 445, 95, 6, kpi_card(
            "Fechas Bloqueadas (Date Locked)", "Períodos protegidos contra modificaciones", "Fechas bloqueadas", entity=ENTITY_PERIODS
        )),
        container("maestro_periodos_holding", 40, 195, 1840, 855, 7, table_visual(
            "Auditoría Consolidada de Períodos Contables y Ejercicios Fiscales",
            "Listado detallado por empresa, fecha de inicio, estado de cierre y bloqueo de fecha en Business Central",
            ["Empresa", "startingDate", "name", "newFiscalYear", "closed", "dateLocked", "lastModifiedDateTime"],
            entity=ENTITY_PERIODS,
        )),
    ]


def page_json(name, display_name):
    return {
        "$schema": SCHEMA_PAGE,
        "name": name,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": 1080,
        "width": 1920,
    }


def pages_json():
    return {
        "$schema": SCHEMA_PAGES,
        "pageOrder": [PAGE_1_NAME, PAGE_2_NAME, PAGE_3_NAME],
        "activePageName": PAGE_1_NAME,
    }


def _part(path, obj):
    return {
        "path": path,
        "payload": base64.b64encode(json.dumps(obj, ensure_ascii=False).encode()).decode(),
        "payloadType": "InlineBase64",
    }


def build_parts(base_parts):
    """Keep the report's metadata and theme; replace every page and the extension."""
    parts = [
        p for p in base_parts
        if not p["path"].startswith("definition/pages/") and p["path"] != "definition/reportExtensions.json"
    ]
    parts.append(_part("definition/reportExtensions.json", report_extensions()))
    parts.append(_part("definition/pages/pages.json", pages_json()))

    # Page 1: Consolidado financiero
    parts.append(_part(f"definition/pages/{PAGE_1_NAME}/page.json", page_json(PAGE_1_NAME, "Consolidado financiero")))
    for v in page_1_visuals():
        parts.append(_part(f"definition/pages/{PAGE_1_NAME}/visuals/{v['name']}/visual.json", v))

    # Page 2: Gobernanza del catálogo
    parts.append(_part(f"definition/pages/{PAGE_2_NAME}/page.json", page_json(PAGE_2_NAME, "Gobernanza del catálogo")))
    for v in page_2_visuals():
        parts.append(_part(f"definition/pages/{PAGE_2_NAME}/visuals/{v['name']}/visual.json", v))

    # Page 3: Períodos contables
    parts.append(_part(f"definition/pages/{PAGE_3_NAME}/page.json", page_json(PAGE_3_NAME, "Períodos contables")))
    for v in page_3_visuals():
        parts.append(_part(f"definition/pages/{PAGE_3_NAME}/visuals/{v['name']}/visual.json", v))

    return parts


def write_local(parts, root):
    """Mirror the definition into the PBIP folder so the repo matches what is live."""
    shutil.rmtree(os.path.join(root, "definition", "pages"), ignore_errors=True)
    for p in parts:
        path = os.path.join(root, p["path"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        raw = base64.b64decode(p["payload"])
        if path.endswith(".json"):
            raw = json.dumps(json.loads(raw), indent=2, ensure_ascii=False).encode()
        with open(path, "wb") as f:
            f.write(raw)


def get_token():
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    cached = json.load(open(TOKEN_FILE)) if os.path.exists(TOKEN_FILE) else {}
    if "refresh_token" in cached:
        res = app.acquire_token_by_refresh_token(cached["refresh_token"], scopes=SCOPES)
        if "access_token" in res:
            cached.update(res)
            json.dump(cached, open(TOKEN_FILE, "w"))
            return res["access_token"]
    flow = app.initiate_device_flow(scopes=SCOPES)
    print(flow["message"], flush=True)
    res = app.acquire_token_by_device_flow(flow)
    if "access_token" not in res:
        sys.exit(f"Autenticación fallida: {res.get('error_description')}")
    json.dump(res, open(TOKEN_FILE, "w"))
    return res["access_token"]


def _wait(r, headers):
    if r.status_code == 200:
        return r.json()
    if r.status_code != 202:
        sys.exit(f"Fabric respondió {r.status_code}: {r.text[:500]}")
    location = r.headers["Location"]
    for _ in range(60):
        time.sleep(float(r.headers.get("Retry-After", 2)))
        status = requests.get(location, headers=headers).json()
        if status.get("status") == "Succeeded":
            return requests.get(location + "/result", headers=headers).json()
        if status.get("status") == "Failed":
            sys.exit("Operación fallida: " + json.dumps(status.get("error"), indent=1))
    sys.exit("La operación no terminó a tiempo.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="build and write the local PBIP folder without pushing")
    args = ap.parse_args(argv)

    headers = {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}
    base = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/reports/{REPORT_ID}"

    current = _wait(requests.post(base + "/getDefinition", headers=headers), headers)
    parts = build_parts(current["definition"]["parts"])
    write_local(parts, LOCAL_REPORT_DIR)
    print(f"Definición generada: {len(parts)} partes, copia local en {LOCAL_REPORT_DIR}")
    if args.dry_run:
        return
    _wait(requests.post(base + "/updateDefinition", headers=headers, json={"definition": {"parts": parts}}), headers)
    print(f"Publicado: https://app.powerbi.com/groups/me/reports/{REPORT_ID}/{PAGE_1_NAME}?experience=power-bi")


if __name__ == "__main__":
    main()
