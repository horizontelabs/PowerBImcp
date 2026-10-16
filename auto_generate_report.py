import os
import json
import webbrowser

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
OUTPUT_HTML = os.path.join(os.path.dirname(__file__), "create_report.html")

DATASET_ID = "d7c2a2e6-17f4-405d-a54a-20a718528dcd"

def main():
    with open(TOKEN_FILE, "r") as f:
        token = json.load(f)["access_token"]

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Generador Automático de Visuales Power BI</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Power BI Client & Report Authoring SDK oficiales de Microsoft -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/powerbi-client/2.22.3/powerbi.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/powerbi-report-authoring@3.0.0/dist/powerbi-report-authoring.min.js"></script>
  <style>
    #reportContainer {{
      width: 100%;
      height: 780px;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      background: #f8fafc;
    }}
  </style>
</head>
<body class="bg-slate-100 p-6 font-sans text-slate-800">

  <div class="max-w-7xl mx-auto space-y-4">
    <!-- Header de control -->
    <div class="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex items-center justify-between">
      <div>
        <h1 class="text-lg font-bold text-slate-900">Generador Automático de Visuales — SIMONE SPA</h1>
        <p class="text-xs text-slate-500">Ejecuta el código oficial de Microsoft Report Authoring para insertar el anillo y guardar el reporte en tu cuenta</p>
      </div>
      <div class="flex items-center gap-3">
        <button id="btnAutoRun" onclick="runAutomatedFlow()" class="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold transition shadow-md shadow-amber-600/20 flex items-center gap-2">
          ⚡ Generar Visuales y Guardar Reporte
        </button>
      </div>
    </div>

    <!-- Status Log Banner -->
    <div id="statusBox" class="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 rounded-xl text-xs font-mono">
      Iniciando sesión del motor de Power BI...
    </div>

    <!-- Power BI Embed Container -->
    <div id="reportContainer"></div>
  </div>

  <script>
    const token = "{token}";
    const datasetId = "{DATASET_ID}";
    const models = window['powerbi-client'].models;
    let report = null;

    const embedConfig = {{
      type: 'report',
      datasetId: datasetId,
      accessToken: token,
      tokenType: models.TokenType.Aad,
      embedUrl: 'https://app.powerbi.com/reportEmbed?datasetId=' + datasetId,
      permissions: models.Permissions.All,
      settings: {{
        panes: {{
          filters: {{ visible: true, expanded: false }},
          pageNavigation: {{ visible: true }}
        }}
      }}
    }};

    const container = document.getElementById('reportContainer');
    const statusBox = document.getElementById('statusBox');

    function log(msg, isSuccess = false, isError = false) {{
      statusBox.textContent = msg;
      if (isSuccess) {{
        statusBox.className = "bg-emerald-50 border border-emerald-200 text-emerald-900 px-4 py-3 rounded-xl text-xs font-mono font-bold";
      }} else if (isError) {{
        statusBox.className = "bg-rose-50 border border-rose-200 text-rose-900 px-4 py-3 rounded-xl text-xs font-mono font-bold";
      }}
    }}

    // Iniciar creación del reporte
    log("Cargando el lienzo oficial de Power BI con el dataset SIMONE SPA V1...");
    report = powerbi.createReport(container, embedConfig);

    report.on('loaded', () => {{
      log("✅ Lienzo de Power BI cargado con éxito. Haz clic en 'Generar Visuales y Guardar' o espera la ejecución automática...");
      setTimeout(runAutomatedFlow, 1500);
    }});

    report.on('error', (err) => {{
      console.error(err);
      log("⚠️ Notificación del lienzo: " + (err.detail ? JSON.stringify(err.detail) : "Cargando..."));
    }});

    async function runAutomatedFlow() {{
      try {{
        log("1/4 Obteniendo la página del reporte...");
        const pages = await report.getPages();
        const page = pages[0];

        log("2/4 Creando el Gráfico de Anillo (Donut Chart) mediante código...");
        const donutLayout = {{
          x: 20,
          y: 30,
          z: 1,
          width: 480,
          height: 480
        }};

        // Crear gráfico de anillo o circular nativo
        let donut = null;
        try {{
          const res = await page.createVisual('donutChart', donutLayout);
          donut = res.visual;
        }} catch(e) {{
          console.warn("donutChart fallback a pieChart", e);
          const res = await page.createVisual('pieChart', donutLayout);
          donut = res.visual;
        }}

        // Agregar campos al anillo
        log("Asignando campos 'category' y 'number' al anillo...");
        await donut.addDataField('Category', {{
          $schema: "http://powerbi.com/product/schema#column",
          table: "accounts",
          column: "category"
        }});

        await donut.addDataField('Y', {{
          $schema: "http://powerbi.com/product/schema#columnAggr",
          table: "accounts",
          column: "number",
          aggregationFunction: "Count"
        }});

        log("3/4 Creando la Tabla de Cuentas Contables mediante código...");
        const tableLayout = {{
          x: 520,
          y: 30,
          z: 2,
          width: 720,
          height: 600
        }};

        const tableRes = await page.createVisual('tableEx', tableLayout);
        const tableVisual = tableRes.visual;

        await tableVisual.addDataField('Values', {{
          $schema: "http://powerbi.com/product/schema#column",
          table: "accounts",
          column: "number"
        }});
        await tableVisual.addDataField('Values', {{
          $schema: "http://powerbi.com/product/schema#column",
          table: "accounts",
          column: "displayName"
        }});
        await tableVisual.addDataField('Values', {{
          $schema: "http://powerbi.com/product/schema#column",
          table: "accounts",
          column: "category"
        }});
        await tableVisual.addDataField('Values', {{
          $schema: "http://powerbi.com/product/schema#column",
          table: "accounts",
          column: "netChange"
        }});

        log("4/4 Guardando el reporte en tu cuenta de Power BI...");
        await report.saveAs({{
          name: "Catálogo de Cuentas SIMONE SPA (Oficial)"
        }});

        log("🎉 ¡ÉXITO TOTAL! Reporte generado y guardado en tu cuenta oficial de Power BI (app.powerbi.com).", true);

      }} catch(err) {{
        console.error("Error en generación:", err);
        log("Resultado: " + (err.message || JSON.stringify(err)), false, true);
      }}
    }}
  </script>
</body>
</html>
"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Generador de authoring creado en: {OUTPUT_HTML}")
    webbrowser.open("file://" + OUTPUT_HTML)

if __name__ == "__main__":
    main()
