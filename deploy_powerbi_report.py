import os
import json
import zipfile
import io
import requests
import time

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
OUTPUT_PBIX = os.path.join(os.path.dirname(__file__), "Catalogo_SIMONE.pbix")

DATASET_ID = "d7c2a2e6-17f4-405d-a54a-20a718528dcd"
WORKSPACE_ID = "f97935fd-6dda-4c37-8ee6-4c88ced5c434"

def get_token():
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)["access_token"]

def build_donut_visual():
    config = {
        "name": "DonutCategoryVisual",
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": 20.0,
                    "y": 70.0,
                    "z": 1.0,
                    "width": 460.0,
                    "height": 500.0,
                    "tabOrder": 1
                }
            }
        ],
        "singleVisual": {
            "visualType": "donutChart",
            "projections": {
                "Category": [
                    {
                        "queryRef": "accounts.category",
                        "active": True
                    }
                ],
                "Y": [
                    {
                        "queryRef": "CountNonNull(accounts.number)"
                    }
                ]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "a", "Entity": "accounts", "Type": 0}],
                "Select": [
                    {
                        "Column": {
                            "Expression": {"SourceRef": {"Source": "a"}},
                            "Property": "category"
                        },
                        "Name": "accounts.category"
                    },
                    {
                        "Aggregation": {
                            "Expression": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Source": "a"}},
                                    "Property": "number"
                                }
                            },
                            "Function": 1
                        },
                        "Name": "CountNonNull(accounts.number)"
                    }
                ]
            },
            "drillFilterOtherVisuals": True,
            "hasDefaultSort": True
        }
    }

    query = {
        "Commands": [
            {
                "SemanticQueryDataShapeCommand": {
                    "Query": {
                        "Version": 2,
                        "From": [{"Name": "a", "Entity": "accounts", "Type": 0}],
                        "Select": [
                            {
                                "Column": {
                                    "Expression": {"SourceRef": {"Source": "a"}},
                                    "Property": "category"
                                },
                                "Name": "accounts.category"
                            },
                            {
                                "Aggregation": {
                                    "Expression": {
                                        "Column": {
                                            "Expression": {"SourceRef": {"Source": "a"}},
                                            "Property": "number"
                                        }
                                    },
                                    "Function": 1
                                },
                                "Name": "CountNonNull(accounts.number)"
                            }
                        ]
                    },
                    "Binding": {
                        "Primary": {"Groupings": [{"Projections": [0]}]},
                        "DataReduction": {"DataVolume": 4, "Primary": {"Top": {"Count": 100}}},
                        "Version": 1
                    },
                    "ExecutionMetricsKind": 1
                }
            }
        ]
    }

    return {
        "x": 20.0,
        "y": 70.0,
        "z": 1.0,
        "width": 460.0,
        "height": 500.0,
        "config": json.dumps(config),
        "filters": "[]",
        "query": json.dumps(query)
    }

def build_table_visual():
    config = {
        "name": "AccountsTableVisual",
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": 500.0,
                    "y": 70.0,
                    "z": 2.0,
                    "width": 750.0,
                    "height": 580.0,
                    "tabOrder": 2
                }
            }
        ],
        "singleVisual": {
            "visualType": "tableEx",
            "projections": {
                "Values": [
                    {"queryRef": "accounts.number"},
                    {"queryRef": "accounts.displayName"},
                    {"queryRef": "accounts.category"},
                    {"queryRef": "accounts.accountType"},
                    {"queryRef": "accounts.netChange"}
                ]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "a", "Entity": "accounts", "Type": 0}],
                "Select": [
                    {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "number"}, "Name": "accounts.number"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "displayName"}, "Name": "accounts.displayName"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "category"}, "Name": "accounts.category"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "accountType"}, "Name": "accounts.accountType"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "netChange"}, "Name": "accounts.netChange"}
                ]
            },
            "drillFilterOtherVisuals": True,
            "hasDefaultSort": True
        }
    }

    query = {
        "Commands": [
            {
                "SemanticQueryDataShapeCommand": {
                    "Query": {
                        "Version": 2,
                        "From": [{"Name": "a", "Entity": "accounts", "Type": 0}],
                        "Select": [
                            {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "number"}, "Name": "accounts.number"},
                            {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "displayName"}, "Name": "accounts.displayName"},
                            {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "category"}, "Name": "accounts.category"},
                            {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "accountType"}, "Name": "accounts.accountType"},
                            {"Column": {"Expression": {"SourceRef": {"Source": "a"}}, "Property": "netChange"}, "Name": "accounts.netChange"}
                        ]
                    },
                    "Binding": {
                        "Primary": {"Groupings": [{"Projections": [0, 1, 2, 3, 4]}]},
                        "DataReduction": {"DataVolume": 4, "Primary": {"Window": {"Count": 500}}},
                        "Version": 1
                    },
                    "ExecutionMetricsKind": 1
                }
            }
        ]
    }

    return {
        "x": 500.0,
        "y": 70.0,
        "z": 2.0,
        "width": 750.0,
        "height": 580.0,
        "config": json.dumps(config),
        "filters": "[]",
        "query": json.dumps(query)
    }

def build_textbox_header():
    config = {
        "name": "HeaderTitle",
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": 20.0,
                    "y": 15.0,
                    "z": 0.0,
                    "width": 1230.0,
                    "height": 45.0,
                    "tabOrder": 0
                }
            }
        ],
        "singleVisual": {
            "visualType": "textbox",
            "objects": {
                "general": [
                    {
                        "properties": {
                            "paragraphs": [
                                {
                                    "textRuns": [
                                        {
                                            "value": "SIMONE SPA — Catálogo de Cuentas Contables (Business Central)",
                                            "textStyle": {
                                                "fontWeight": "bold",
                                                "fontSize": "16pt",
                                                "color": "#1e293b"
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }
    return {
        "x": 20.0,
        "y": 15.0,
        "z": 0.0,
        "width": 1230.0,
        "height": 45.0,
        "config": json.dumps(config),
        "filters": "[]"
    }

def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    print("📥 Descargando plantilla base...")
    r = requests.get("https://api.powerbi.com/v1.0/myorg/reports/a502360e-c959-4bb9-bac5-08e73e6ad468/Export", headers=headers)
    if r.status_code != 200:
        print("Error descargando:", r.status_code, r.text)
        return

    src_zip = zipfile.ZipFile(io.BytesIO(r.content))
    
    # Construir nuevo Layout
    layout_raw = src_zip.read("Report/Layout").decode("utf-16-le", errors="ignore")
    layout = json.loads(layout_raw)

    # 1. Limpiar completamente referencias obsoletas
    layout["pods"] = []
    layout["filters"] = "[]"
    layout["resourcePackages"] = []
    
    # Limpiar bookmarks antiguos que apuntaban a Product y Country
    if "config" in layout:
        try:
            cfg = json.loads(layout["config"])
            cfg["bookmarks"] = []
            layout["config"] = json.dumps(cfg)
        except Exception:
            pass

    new_section = {
        "id": 0,
        "name": "CatalogoSIMONEPage",
        "displayName": "Catálogo de Cuentas",
        "filters": "[]",
        "ordinal": 0,
        "visualContainers": [
            build_textbox_header(),
            build_donut_visual(),
            build_table_visual()
        ],
        "config": "{}",
        "width": 1280.0,
        "height": 720.0
    }

    # Reemplazar secciones: dejar solo nuestra página principal
    layout["sections"] = [new_section]

    # Conexión al dataset de SIMONE SPA
    new_connections = {
        "Version": 6,
        "RemoteArtifacts": [
            {
                "DatasetId": DATASET_ID,
                "ReportId": ""
            }
        ],
        "OriginalWorkspaceObjectId": WORKSPACE_ID
    }

    # Generar archivo PBIX completo limpio
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as out_zip:
        for item in src_zip.infolist():
            if item.filename == "Report/Layout":
                encoded = json.dumps(layout).encode("utf-16-le")
                out_zip.writestr(item.filename, encoded)
            elif item.filename == "Connections":
                out_zip.writestr(item.filename, json.dumps(new_connections).encode("utf-8"))
            elif item.filename.startswith("Report/StaticResources/RegisteredResources/"):
                continue
            else:
                out_zip.writestr(item.filename, src_zip.read(item.filename))

    with open(OUTPUT_PBIX, "wb") as f:
        f.write(out_buf.getvalue())
    print(f"✅ Archivo PBIX limpio generado en: {OUTPUT_PBIX}")

    # Borrar reporte anterior si existe
    reports_res = requests.get("https://api.powerbi.com/v1.0/myorg/reports", headers=headers)
    for rep in reports_res.json().get("value", []):
        if rep.get("name") in ["Catalogo_SIMONE", "Catálogo de Cuentas - SIMONE SPA"]:
            requests.delete(f"https://api.powerbi.com/v1.0/myorg/reports/{rep.get('id')}", headers=headers)
            print(f"🗑️ Reporte anterior {rep.get('id')} eliminado.")

    # Subir nuevo
    print("🚀 Subiendo reporte limpio a Power BI Service...")
    import_url = f"https://api.powerbi.com/v1.0/myorg/imports?datasetDisplayName=Catalogo_SIMONE.pbix&nameConflict=CreateOrOverwrite"
    upload_headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("Catalogo_SIMONE.pbix", out_buf.getvalue(), "application/octet-stream")}
    
    resp = requests.post(import_url, headers=upload_headers, files=files)
    if resp.status_code in [200, 202]:
        import_id = resp.json().get("id")
        print(f"Import iniciado: {import_id}. Esperando procesamiento...")
        for _ in range(10):
            time.sleep(2)
            chk = requests.get(f"https://api.powerbi.com/v1.0/myorg/imports/{import_id}", headers=headers).json()
            if chk.get("importState") == "Succeeded":
                created_rep = chk.get("reports", [{}])[0]
                created_ds = chk.get("datasets", [{}])[0]
                rep_id = created_rep.get("id")
                ds_id = created_ds.get("id")
                print(f"Import terminado con éxito! Report ID: {rep_id}")
                
                # Rebind directo a SIMONE SPA V1
                print("Enlazando a SIMONE SPA V1...")
                rebind_res = requests.post(f"https://api.powerbi.com/v1.0/myorg/reports/{rep_id}/Rebind", headers=headers, json={"datasetId": DATASET_ID})
                print("Rebind status:", rebind_res.status_code)
                
                # Borrar dataset temporal de subida
                if ds_id:
                    requests.delete(f"https://api.powerbi.com/v1.0/myorg/datasets/{ds_id}", headers=headers)
                
                print(f"\n🎉 ¡REPORTE ACTUALIZADO Y CORREGIDO!")
                print(f"   URL: https://app.powerbi.com/groups/me/reports/{rep_id}")
                return rep_id
    else:
        print("Error en import:", resp.status_code, resp.text)

if __name__ == "__main__":
    main()
