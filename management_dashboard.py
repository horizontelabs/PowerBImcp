"""Management dashboard for SIMONE SPA — builds the PBIR definition and deploys it.

The report has one page with a title and four charts, driven by report-level
measures so that no table, slicer or card is needed and no label leaks the
OData-escaped category names stored in the semantic model.

    python management_dashboard.py            # pull, build, write local PBIP, push
    python management_dashboard.py --dry-run  # pull, build, write local PBIP only
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
REPORT_ID = "86bfa92e-97f1-4ee5-b045-f04cad6ebfe8"
CLIENT_ID = "ea0616ba-638b-4df5-95b9-636659ae5121"
AUTHORITY = "https://login.microsoftonline.com/organizations"
SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]
HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(HERE, "token.json")
LOCAL_REPORT_DIR = os.path.join(HERE, "SIMONE_SPA_V3.pbip", "SIMONE_SPA_V3.Report")

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
SCHEMA_VISUAL = SCHEMA + "visualContainer/2.0.0/schema.json"
SCHEMA_PAGE = SCHEMA + "page/2.1.0/schema.json"
SCHEMA_PAGES = SCHEMA + "pagesMetadata/1.1.0/schema.json"
SCHEMA_EXTENSION = SCHEMA + "reportExtension/1.0.0/schema.json"

PAGE_NAME = "resumenFinanciero"
ENTITY = "accounts"
POSTING = 'accounts[accountType] = "Posting"'
# Category values exactly as Business Central exported them into the model.
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

# ---------------------------------------------------------------- measures ---


def _balance(category, sign=""):
    return f"{sign}CALCULATE(SUM(accounts[netChange]), {POSTING}, accounts[category] = \"{category}\")"


MEASURES = [
    # name, DAX, measures it references within the extension, formatString
    ("Activos", _balance(CATEGORY["assets"]), [], MILLIONS),
    ("Pasivos", _balance(CATEGORY["liabilities"], "-"), [], MILLIONS),
    ("Patrimonio", _balance(CATEGORY["equity"], "-"), [], MILLIONS),
    ("Ingresos", _balance(CATEGORY["income"], "-"), [], MILLIONS),
    ("Costo de ventas", _balance(CATEGORY["cogs"], "-"), [], MILLIONS),
    ("Gastos", _balance(CATEGORY["expense"], "-"), [], MILLIONS),
    ("Resultado", "[Ingresos] + [Costo de ventas] + [Gastos]", ["Ingresos", "Costo de ventas", "Gastos"], MILLIONS),
    (
        "Saldo natural",
        "CALCULATE(SUMX(accounts, IF(accounts[category] IN {"
        + ", ".join(f'"{c}"' for c in DEBIT_NATURE)
        + f"}}, accounts[netChange], -accounts[netChange])), {POSTING})",
        [],
        MILLIONS,
    ),
    # Medidas de Gobernanza y Auditoría del Catálogo
    ("Total cuentas", "COUNTROWS(accounts)", [], "#,0"),
    ("Cuentas imputables", 'CALCULATE(COUNTROWS(accounts), accounts[accountType] = "Posting")', [], "#,0"),
    ("Cuentas agrupación", 'CALCULATE(COUNTROWS(accounts), accounts[accountType] = "Total")', [], "#,0"),
    ("Cuentas bloqueadas", "CALCULATE(COUNTROWS(accounts), accounts[blocked] = TRUE)", [], "#,0"),
    ("Cuentas registro directo", "CALCULATE(COUNTROWS(accounts), accounts[directPosting] = TRUE)", [], "#,0"),
]


def report_extensions():
    measures = []
    for name, expression, refs, fmt in MEASURES:
        m = {"name": name, "dataType": "Double", "expression": expression, "formatString": fmt}
        if refs:
            m["references"] = {"measures": [{"schema": "extension", "entity": ENTITY, "name": r} for r in refs]}
        measures.append(m)
    return {"$schema": SCHEMA_EXTENSION, "name": "extension", "entities": [{"name": ENTITY, "measures": measures}]}


# ------------------------------------------------------ expression helpers ---


def measure_ref(name):
    return {"Measure": {"Expression": {"SourceRef": {"Schema": "extension", "Entity": ENTITY}}, "Property": name}}


def column_ref(column):
    return {"Column": {"Expression": {"SourceRef": {"Entity": ENTITY}}, "Property": column}}


def measure_projection(name):
    return {"field": measure_ref(name), "queryRef": f"{ENTITY}.{name}", "nativeQueryRef": name}


def column_projection(column, active=False):
    p = {"field": column_ref(column), "queryRef": f"{ENTITY}.{column}", "nativeQueryRef": column}
    if active:
        p["active"] = True
    return p


def literal(value):
    return {"expr": {"Literal": {"Value": value}}}


def solid(hex_color):
    return {"solid": {"color": literal(f"'{hex_color}'")}}


def props(**kw):
    return [{"properties": kw}]


# ----------------------------------------------------------------- filters ---


def categorical_filter(name, column, value):
    lit = f"'{value}'" if isinstance(value, str) else str(value).lower()
    return {
        "name": name,
        "type": "Categorical",
        "field": column_ref(column),
        "filter": {
            "Version": 2,
            "From": [{"Name": "a", "Entity": ENTITY, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": column}}],
                            "Values": [[{"Literal": {"Value": lit}}]],
                        }
                    }
                }
            ],
        },
        "howCreated": "User",
    }


def top_n_filter(name, column, measure, n):
    key = {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": column}}
    return {
        "name": name,
        "type": "TopN",
        "field": column_ref(column),
        "filter": {
            "Version": 2,
            "From": [
                {
                    "Name": "subquery",
                    "Expression": {
                        "Subquery": {
                            "Query": {
                                "Version": 2,
                                "From": [
                                    {"Name": "a", "Entity": ENTITY, "Type": 0},
                                    {"Name": "e", "Entity": ENTITY, "Schema": "extension", "Type": 0},
                                ],
                                "Select": [{**key, "Name": "field"}],
                                "OrderBy": [
                                    {
                                        "Direction": 2,
                                        "Expression": {"Measure": {"Expression": {"SourceRef": {"Source": "e"}}, "Property": measure}},
                                    }
                                ],
                                "Top": n,
                            }
                        }
                    },
                    "Type": 2,
                },
                {"Name": "a", "Entity": ENTITY, "Type": 0},
            ],
            "Where": [{"Condition": {"In": {"Expressions": [key], "Table": {"SourceRef": {"Source": "subquery"}}}}}],
        },
        "howCreated": "User",
    }


# ----------------------------------------------------------------- visuals ---


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
        "title": props(show=literal("true"), text=literal(f"'{title}'"), fontSize=literal("14D"), bold=literal("true"), fontColor=solid(INK)),
        "subTitle": props(show=literal("true"), text=literal(f"'{subtitle}'"), fontSize=literal("10D"), fontColor=solid(INK_MUTED)),
    }


def textbox(title, subtitle):
    run = lambda text, size, weight, color: {"value": text, "textStyle": {"fontSize": size, "fontWeight": weight, "color": color}}
    return {
        "visualType": "textbox",
        "objects": {
            "general": props(
                paragraphs=[
                    {"textRuns": [run(title, "20pt", "bold", INK)]},
                    {"textRuns": [run(subtitle, "11pt", "normal", INK_MUTED)]},
                ]
            )
        },
    }


def measures_column_chart(title, subtitle, series):
    """One column per measure; the measure name is the axis label, so no legend."""
    return {
        "visualType": "clusteredColumnChart",
        "query": {"queryState": {"Y": {"projections": [measure_projection(n) for n, _ in series]}}},
        "objects": {
            "legend": props(show=literal("false")),
            "labels": props(show=literal("true"), labelDisplayUnits=literal("1D"), labelPrecision=literal("0D"), color=solid(INK)),
            "valueAxis": props(show=literal("false"), gridlineShow=literal("false")),
            "categoryAxis": props(show=literal("true"), fontSize=literal("11D"), labelColor=solid(INK)),
            "dataPoint": [{"properties": {"fill": solid(color)}, "selector": {"metadata": f"{ENTITY}.{n}"}} for n, color in series],
        },
        "visualContainerObjects": header(title, subtitle),
    }


def top_accounts_bar(title, subtitle):
    return {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [column_projection("displayName", active=True)]},
                "Y": {"projections": [measure_projection("Saldo natural")]},
            },
            "sortDefinition": {"sort": [{"field": measure_ref("Saldo natural"), "direction": "Descending"}], "isDefaultSort": True},
        },
        "objects": {
            "legend": props(show=literal("false")),
            "labels": props(show=literal("true"), labelDisplayUnits=literal("1D"), labelPrecision=literal("0D"), color=solid(INK)),
            "valueAxis": props(show=literal("false"), gridlineShow=literal("false")),
            "categoryAxis": props(show=literal("true"), fontSize=literal("10D"), labelColor=solid(INK), maxMarginFactor=literal("40D")),
            "dataPoint": props(fill=solid(BLUE)),
        },
        "visualContainerObjects": header(title, subtitle),
    }


def assets_treemap(title, subtitle):
    return {
        "visualType": "treemap",
        "query": {
            "queryState": {
                "Details": {"projections": [column_projection("displayName")]},
                "Values": {"projections": [measure_projection("Saldo natural")]},
            },
            "sortDefinition": {"sort": [{"field": measure_ref("Saldo natural"), "direction": "Descending"}], "isDefaultSort": True},
        },
        "objects": {
            "legend": props(show=literal("false")),
            "labels": props(show=literal("true"), labelDisplayUnits=literal("1D"), labelPrecision=literal("0D")),
            "categoryLabels": props(show=literal("true")),
            "dataPoint": props(fill=solid(BLUE)),
        },
        "visualContainerObjects": header(title, subtitle),
    }


PAGE_2_NAME = "gobernanzaCatalogo"


def kpi_card(title, subtitle, measure_name):
    return {
        "visualType": "card",
        "query": {
            "queryState": {
                "Values": {"projections": [measure_projection(measure_name)]}
            }
        },
        "objects": {
            "labels": props(fontSize=literal("22D"), color=solid(INK)),
        },
        "visualContainerObjects": header(title, subtitle),
    }


def category_distribution_bar(title, subtitle):
    return {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [column_projection("category", active=True)]},
                "Y": {"projections": [measure_projection("Total cuentas")]},
            },
            "sortDefinition": {"sort": [{"field": measure_ref("Total cuentas"), "direction": "Descending"}], "isDefaultSort": True},
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


def table_visual(title, subtitle, columns):
    return {
        "visualType": "tableEx",
        "query": {
            "queryState": {
                "Values": {"projections": [column_projection(col) for col in columns]}
            }
        },
        "visualContainerObjects": header(title, subtitle),
    }


# -------------------------------------------------------------- the pages ---

# 1920 x 1080 canvas, 40px gutter, two rows of two.
COL = [(40, 900), (980, 900)]
ROW = [(110, 460), (600, 450)]


def page_1_visuals():
    (x1, w), (x2, _) = COL
    (y1, h1), (y2, h2) = ROW
    return [
        container("titulo", 40, 30, 1840, 60, 1, textbox(
            "SIMONE SPA — Resumen financiero",
            "Saldos acumulados de las cuentas imputables en Business Central, en millones de pesos (MM$)",
        )),
        container("estructura_financiera", x1, y1, w, h1, 2, measures_column_chart(
            "Estructura financiera", "Activos frente a pasivos y patrimonio",
            [("Activos", BLUE), ("Pasivos", ORANGE), ("Patrimonio", AQUA)],
        )),
        container("estado_resultados", x2, y1, w, h1, 3, measures_column_chart(
            "Estado de resultados", "Ingresos menos costo de ventas y gastos",
            [("Ingresos", BLUE), ("Costo de ventas", ORANGE), ("Gastos", ORANGE), ("Resultado", NAVY)],
        )),
        container("top_cuentas", x1, y2, w, h2, 4, top_accounts_bar(
            "Diez cuentas con mayor saldo", "Cuentas imputables, saldo según su naturaleza",
        ), filters=[
            categorical_filter("soloImputables", "accountType", "Posting"),
            top_n_filter("topDiez", "displayName", "Saldo natural", 10),
        ]),
        container("composicion_activos", x2, y2, w, h2, 5, assets_treemap(
            "Composición de activos", "Cuentas imputables de activo, por saldo",
        ), filters=[
            categorical_filter("soloActivos", "category", CATEGORY["assets"]),
            categorical_filter("soloImputables", "accountType", "Posting"),
        ]),
    ]


def page_2_visuals():
    return [
        container("titulo_gobernanza", 40, 25, 1840, 55, 1, textbox(
            "SIMONE SPA — Gobernanza y Auditoría del Catálogo Contable",
            "Supervisión del Plan de Cuentas (Business Central) — Cuentas operativas, bloqueos y políticas de imputación",
        )),
        container("kpi_total_cuentas", 40, 90, 440, 95, 2, kpi_card(
            "Total Cuentas Catálogo", "Universo completo registrado en BC", "Total cuentas",
        )),
        container("kpi_cuentas_imputables", 505, 90, 440, 95, 3, kpi_card(
            "Cuentas Imputables (Posting)", "Cuentas operativas que reciben asientos", "Cuentas imputables",
        )),
        container("kpi_cuentas_bloqueadas", 970, 90, 440, 95, 4, kpi_card(
            "Cuentas Bloqueadas", "Restringidas para nuevos registros", "Cuentas bloqueadas",
        )),
        container("kpi_registro_directo", 1435, 90, 445, 95, 5, kpi_card(
            "Contabilización Directa", "Permiten imputación manual por diario", "Cuentas registro directo",
        )),
        container("maestro_cuentas", 40, 195, 980, 855, 6, table_visual(
            "Maestro de Cuentas Contables", "Haz clic en cualquier fila para cargar su ficha técnica",
            ["number", "displayName", "category"],
        )),
        container("distribucion_categoria", 1045, 195, 835, 365, 7, category_distribution_bar(
            "Distribución del Catálogo por Categoría", "Cantidad de cuentas por clase contable",
        )),
        container("ficha_cuenta", 1045, 575, 835, 475, 8, table_visual(
            "Ficha Técnica de Cuenta (Detalle al seleccionar)",
            "Parámetros de sistema y políticas de registro en Business Central",
            ["number", "displayName", "category", "subCategory", "accountType", "directPosting", "blocked", "lastModifiedDateTime", "id"],
        )),
    ]


def page_json(name, display_name):
    return {"$schema": SCHEMA_PAGE, "name": name, "displayName": display_name,
            "displayOption": "FitToPage", "height": 1080, "width": 1920}


def pages_json():
    return {"$schema": SCHEMA_PAGES, "pageOrder": [PAGE_NAME, PAGE_2_NAME], "activePageName": PAGE_NAME}


# ------------------------------------------------------------- definition ---


def _part(path, obj):
    return {"path": path, "payload": base64.b64encode(json.dumps(obj, ensure_ascii=False).encode()).decode(), "payloadType": "InlineBase64"}


def build_parts(base_parts):
    """Keep the report's metadata and theme; replace every page and the extension."""
    parts = [p for p in base_parts
             if not p["path"].startswith("definition/pages/") and p["path"] != "definition/reportExtensions.json"]
    parts.append(_part("definition/reportExtensions.json", report_extensions()))
    parts.append(_part("definition/pages/pages.json", pages_json()))

    # Página 1: Resumen Financiero
    parts.append(_part(f"definition/pages/{PAGE_NAME}/page.json", page_json(PAGE_NAME, "Resumen financiero")))
    for v in page_1_visuals():
        parts.append(_part(f"definition/pages/{PAGE_NAME}/visuals/{v['name']}/visual.json", v))

    # Página 2: Gobernanza del Catálogo
    parts.append(_part(f"definition/pages/{PAGE_2_NAME}/page.json", page_json(PAGE_2_NAME, "Gobernanza del Catálogo")))
    for v in page_2_visuals():
        parts.append(_part(f"definition/pages/{PAGE_2_NAME}/visuals/{v['name']}/visual.json", v))

    return parts


def write_local(parts, root):
    """Mirror the definition into the PBIP folder so the repo matches what is live."""
    shutil.rmtree(os.path.join(root, "definition", "pages"), ignore_errors=True)
    for p in parts:
        path = os.path.join(root, p["path"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        raw = base64.b64decode(p["payload"])
        if path.endswith(".json"):  # pretty-print like the service does, so the repo diffs cleanly
            raw = json.dumps(json.loads(raw), indent=2, ensure_ascii=False).encode()
        with open(path, "wb") as f:
            f.write(raw)


# ----------------------------------------------------------------- fabric ---


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
    print(f"Publicado: https://app.powerbi.com/groups/me/reports/{REPORT_ID}/{PAGE_NAME}?experience=power-bi")


if __name__ == "__main__":
    main()
