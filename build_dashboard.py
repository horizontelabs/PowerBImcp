import os
import json
import requests
import webbrowser

WORKSPACE_ID = "f97935fd-6dda-4c37-8ee6-4c88ced5c434"
DATASET_ID = "d7c2a2e6-17f4-405d-a54a-20a718528dcd"
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
OUTPUT_HTML = os.path.join(os.path.dirname(__file__), "dashboard.html")

def fetch_accounts():
    with open(TOKEN_FILE, "r") as f:
        token = json.load(f)["access_token"]
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    query = {"queries": [{"query": "EVALUATE accounts ORDER BY accounts[number]"}]}
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{DATASET_ID}/executeQueries"
    
    r = requests.post(url, headers=headers, json=query)
    if r.status_code != 200:
        raise Exception(f"Error querying Power BI: {r.status_code} - {r.text}")
    
    raw_rows = r.json()["results"][0]["tables"][0]["rows"]
    
    accounts = []
    for r in raw_rows:
        cat = r.get("accounts[category]", "").replace("_x0020_", " ").strip()
        if not cat:
            cat = "Sin Categoría"
        accounts.append({
            "id": r.get("accounts[id]", ""),
            "number": r.get("accounts[number]", ""),
            "displayName": r.get("accounts[displayName]", ""),
            "category": cat,
            "subCategory": r.get("accounts[subCategory]", "") or "-",
            "blocked": r.get("accounts[blocked]", False),
            "accountType": r.get("accounts[accountType]", "Posting"),
            "directPosting": r.get("accounts[directPosting]", False),
            "netChange": r.get("accounts[netChange]", 0.0) or 0.0,
            "lastModified": r.get("accounts[lastModifiedDateTime]", "")
        })
    return accounts

def generate_html(accounts):
    accounts_json = json.dumps(accounts, ensure_ascii=False)
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard Catálogo de Cuentas - SIMONE SPA</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #94a3b8; }}
  </style>
</head>
<body class="bg-slate-50 text-slate-800 font-sans antialiased min-h-screen flex flex-col">

  <!-- Header -->
  <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-400 flex items-center justify-center text-white font-bold shadow-md shadow-orange-500/20">
          BI
        </div>
        <div>
          <h1 class="text-lg font-bold text-slate-900 leading-tight">SIMONE SPA — Catálogo Contable</h1>
          <p class="text-xs text-slate-500">Conectado en vivo al Dataset de Power BI (Business Central)</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          386 Cuentas Activas
        </span>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full flex flex-col gap-6">

    <!-- Top Grid: KPI & Donut Chart -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Chart Card -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-col lg:col-span-1">
        <div class="flex items-center justify-between mb-2">
          <h2 class="text-sm font-bold text-slate-700 uppercase tracking-wider">Cuentas por Categoría</h2>
          <span class="text-xs text-slate-400">Haz clic en el anillo para filtrar</span>
        </div>
        <div class="relative flex-1 flex items-center justify-center min-h-[220px]">
          <canvas id="categoryChart"></canvas>
        </div>
        <div class="mt-3 pt-3 border-t border-slate-100 flex justify-between text-xs text-slate-500">
          <span id="activeFilterLabel">Filtro: Todas</span>
          <button id="resetFilterBtn" class="text-amber-600 hover:text-amber-700 font-semibold hidden">Quitar filtro</button>
        </div>
      </div>

      <!-- Quick Stats Card -->
      <div class="lg:col-span-2 grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <span class="text-xs font-semibold uppercase text-slate-400">Activos (Assets)</span>
          <p class="text-2xl font-bold text-slate-900 mt-2" id="statAssets">0</p>
          <span class="text-xs text-slate-400 mt-1">Cuentas contables</span>
        </div>
        <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <span class="text-xs font-semibold uppercase text-slate-400">Pasivos (Liabilities)</span>
          <p class="text-2xl font-bold text-slate-900 mt-2" id="statLiabilities">0</p>
          <span class="text-xs text-slate-400 mt-1">Cuentas contables</span>
        </div>
        <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <span class="text-xs font-semibold uppercase text-slate-400">Gastos (Expense)</span>
          <p class="text-2xl font-bold text-slate-900 mt-2" id="statExpenses">0</p>
          <span class="text-xs text-slate-400 mt-1">Cuentas contables</span>
        </div>
        <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <span class="text-xs font-semibold uppercase text-slate-400">Ingresos (Income)</span>
          <p class="text-2xl font-bold text-slate-900 mt-2" id="statIncome">0</p>
          <span class="text-xs text-slate-400 mt-1">Cuentas contables</span>
        </div>

        <!-- Search Bar Banner -->
        <div class="col-span-2 sm:col-span-4 bg-white p-3 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-3">
          <div class="relative flex-1 min-w-[240px]">
            <input type="text" id="searchInput" placeholder="Buscar por Nº de cuenta (ej. 110101) o nombre..." 
                   class="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500">
            <svg class="w-4 h-4 text-slate-400 absolute left-3 top-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
          </div>
          <select id="categorySelect" class="py-2 px-3 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/20">
            <option value="">Todas las categorías</option>
          </select>
          <span id="counterBadge" class="text-xs font-medium text-slate-500 ml-auto">386 cuentas</span>
        </div>
      </div>

    </div>

    <!-- Master-Detail Layout -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 items-start">

      <!-- Master List / Table -->
      <div class="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[560px]">
        <div class="px-5 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h3 class="text-xs font-bold text-slate-600 uppercase tracking-wider">Listado de Cuentas (Haz clic para ver detalle)</h3>
          <span class="text-xs text-slate-400">Ordenado por Nº</span>
        </div>
        <div class="overflow-y-auto flex-1">
          <table class="w-full text-left text-sm text-slate-600">
            <thead class="text-xs text-slate-400 uppercase bg-slate-50 sticky top-0 z-10 border-b border-slate-200">
              <tr>
                <th class="py-2.5 px-4 font-semibold">Nº Cuenta (ID)</th>
                <th class="py-2.5 px-4 font-semibold">Nombre de Cuenta</th>
                <th class="py-2.5 px-4 font-semibold">Categoría</th>
                <th class="py-2.5 px-4 font-semibold text-right">Saldo Neto</th>
              </tr>
            </thead>
            <tbody id="accountsTableBody" class="divide-y divide-slate-100">
              <!-- Dynamically populated -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- Detail Card (Ficha de la Cuenta) -->
      <div id="detailPanel" class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sticky top-20 flex flex-col">
        <div class="flex items-start justify-between border-b border-slate-100 pb-4 mb-4">
          <div>
            <span id="detailBadge" class="px-2.5 py-1 text-xs font-bold rounded-lg bg-amber-50 text-amber-700 border border-amber-200">Selecciona una cuenta</span>
            <h3 id="detailName" class="text-lg font-bold text-slate-900 mt-2 leading-snug">Detalle de Cuenta</h3>
            <p id="detailNumber" class="text-xs text-slate-500">Haz clic en cualquier fila o ID de la tabla para cargar su ficha</p>
          </div>
        </div>

        <div id="detailContent" class="space-y-3.5 text-xs">
          <div class="flex justify-between py-1 border-b border-slate-50">
            <span class="text-slate-400 font-medium">Categoría:</span>
            <span id="detailCategory" class="font-semibold text-slate-700">-</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-50">
            <span class="text-slate-400 font-medium">Subcategoría:</span>
            <span id="detailSubcategory" class="font-semibold text-slate-700">-</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-50">
            <span class="text-slate-400 font-medium">Tipo de Cuenta:</span>
            <span id="detailType" class="font-semibold text-slate-700">-</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-50">
            <span class="text-slate-400 font-medium">Registro Directo:</span>
            <span id="detailDirectPosting" class="font-semibold text-slate-700">-</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-50">
            <span class="text-slate-400 font-medium">Bloqueada en BC:</span>
            <span id="detailBlocked" class="font-semibold text-slate-700">-</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-50">
            <span class="text-slate-400 font-medium">Saldo / Movimiento Neto:</span>
            <span id="detailNetChange" class="font-bold text-slate-900 text-sm">-</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-50">
            <span class="text-slate-400 font-medium">Última Modificación:</span>
            <span id="detailLastModified" class="font-mono text-slate-500">-</span>
          </div>
          <div class="pt-2">
            <span class="text-slate-400 font-medium block mb-1">GUID Business Central (ID):</span>
            <input type="text" id="detailGuid" readonly 
                   class="w-full font-mono text-[11px] bg-slate-50 border border-slate-200 rounded px-2 py-1 text-slate-600 select-all cursor-pointer">
          </div>
        </div>

        <div class="mt-6 pt-4 border-t border-slate-100 flex flex-col gap-2">
          <a id="bcLink" href="https://businesscentral.dynamics.com" target="_blank"
             class="w-full text-center py-2 px-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs transition shadow-sm">
            Abrir en Business Central ↗
          </a>
        </div>
      </div>

    </div>

  </main>

  <script>
    const accounts = {accounts_json};
    let selectedCategory = null;
    let selectedAccountId = null;

    // Format CLP Currency
    const formatCurrency = (val) => {{
      return new Intl.NumberFormat('es-CL', {{ style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }}).format(val);
    }};

    // Populate Category stats
    const counts = {{}};
    accounts.forEach(a => {{
      counts[a.category] = (counts[a.category] || 0) + 1;
    }});

    document.getElementById('statAssets').textContent = counts['Assets'] || 0;
    document.getElementById('statLiabilities').textContent = counts['Liabilities'] || 0;
    document.getElementById('statExpenses').textContent = counts['Expense'] || 0;
    document.getElementById('statIncome').textContent = counts['Income'] || 0;

    // Category Select Options
    const categorySelect = document.getElementById('categorySelect');
    Object.keys(counts).sort().forEach(cat => {{
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = `${{cat}} (${{counts[cat]}})`;
      categorySelect.appendChild(opt);
    }});

    // Render Table Rows
    const tbody = document.getElementById('accountsTableBody');
    const searchInput = document.getElementById('searchInput');
    const counterBadge = document.getElementById('counterBadge');

    function renderTable() {{
      const query = searchInput.value.toLowerCase().trim();
      const catFilter = categorySelect.value || selectedCategory;

      const filtered = accounts.filter(a => {{
        const matchesQuery = a.number.toLowerCase().includes(query) || a.displayName.toLowerCase().includes(query);
        const matchesCat = !catFilter || a.category === catFilter;
        return matchesQuery && matchesCat;
      }});

      counterBadge.textContent = `${{filtered.length}} de ${{accounts.length}} cuentas`;
      tbody.innerHTML = '';

      if (filtered.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="4" class="py-8 text-center text-slate-400">No se encontraron cuentas con esos filtros.</td></tr>';
        return;
      }}

      filtered.forEach(acc => {{
        const tr = document.createElement('tr');
        tr.className = `cursor-pointer transition hover:bg-amber-50/50 ${{acc.id === selectedAccountId ? 'bg-amber-100/70 font-medium' : ''}}`;
        tr.onclick = () => selectAccount(acc);

        tr.innerHTML = `
          <td class="py-2.5 px-4">
            <span class="inline-flex items-center px-2 py-0.5 rounded font-mono text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-amber-200">
              ${{acc.number}}
            </span>
          </td>
          <td class="py-2.5 px-4 font-medium text-slate-800">${{acc.displayName}}</td>
          <td class="py-2.5 px-4">
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600">
              ${{acc.category}}
            </span>
          </td>
          <td class="py-2.5 px-4 text-right font-mono text-xs ${{acc.netChange < 0 ? 'text-rose-600' : 'text-slate-700'}}">
            ${{formatCurrency(acc.netChange)}}
          </td>
        `;
        tbody.appendChild(tr);
      }});

      // Auto select first if none selected
      if (!selectedAccountId && filtered.length > 0) {{
        selectAccount(filtered[0]);
      }}
    }}

    // Select Account Function
    function selectAccount(acc) {{
      selectedAccountId = acc.id;
      document.getElementById('detailBadge').textContent = `Cuenta Nº ${{acc.number}}`;
      document.getElementById('detailName').textContent = acc.displayName;
      document.getElementById('detailNumber').textContent = `ID interno: ${{acc.id.substring(0, 13)}}...`;
      document.getElementById('detailCategory').textContent = acc.category;
      document.getElementById('detailSubcategory').textContent = acc.subCategory;
      document.getElementById('detailType').textContent = acc.accountType;
      document.getElementById('detailDirectPosting').textContent = acc.directPosting ? 'Sí (Permitido)' : 'No (Solo acumulador)';
      document.getElementById('detailBlocked').textContent = acc.blocked ? '⚠️ Bloqueada' : '✅ Habilitada';
      document.getElementById('detailNetChange').textContent = formatCurrency(acc.netChange);
      document.getElementById('detailLastModified').textContent = acc.lastModified.replace('T', ' ').substring(0, 19);
      document.getElementById('detailGuid').value = acc.id;

      // Update row active state
      Array.from(tbody.children).forEach(row => {{
        row.classList.remove('bg-amber-100/70', 'font-medium');
      }});
      // Re-render highlight
      const activeRow = Array.from(tbody.querySelectorAll('tr')).find(r => r.textContent.includes(acc.number));
      if (activeRow) activeRow.classList.add('bg-amber-100/70', 'font-medium');
    }}

    // Donut Chart Initialization
    const ctx = document.getElementById('categoryChart').getContext('2d');
    const categories = Object.keys(counts);
    const chartData = categories.map(c => counts[c]);

    const chart = new Chart(ctx, {{
      type: 'doughnut',
      data: {{
        labels: categories,
        datasets: [{{
          data: chartData,
          backgroundColor: [
            '#f59e0b', // Amber (Assets)
            '#3b82f6', // Blue (Liabilities)
            '#10b981', // Emerald (Equity)
            '#8b5cf6', // Violet (Income)
            '#ef4444', // Red (Expense)
            '#64748b', // Slate
            '#06b6d4'
          ],
          borderWidth: 2,
          borderColor: '#ffffff',
          hoverOffset: 6
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }}
        }},
        cutout: '68%',
        onClick: (evt, elements) => {{
          if (elements.length > 0) {{
            const index = elements[0].index;
            const cat = categories[index];
            selectedCategory = (selectedCategory === cat) ? null : cat;
            categorySelect.value = selectedCategory || '';
            updateFilterLabel();
            renderTable();
          }}
        }}
      }}
    }});

    function updateFilterLabel() {{
      const label = document.getElementById('activeFilterLabel');
      const resetBtn = document.getElementById('resetFilterBtn');
      if (selectedCategory) {{
        label.innerHTML = `Filtro: <b class="text-amber-600">${{selectedCategory}}</b> (${{counts[selectedCategory]}})`;
        resetBtn.classList.remove('hidden');
      }} else {{
        label.textContent = 'Filtro: Todas las categorías';
        resetBtn.classList.add('hidden');
      }}
    }}

    document.getElementById('resetFilterBtn').onclick = () => {{
      selectedCategory = null;
      categorySelect.value = '';
      updateFilterLabel();
      renderTable();
    }};

    categorySelect.onchange = (e) => {{
      selectedCategory = e.target.value || null;
      updateFilterLabel();
      renderTable();
    }};

    searchInput.oninput = renderTable;

    // Initial render
    renderTable();
  </script>
</body>
</html>
"""
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Dashboard generado exitosamente en: {OUTPUT_HTML}")
    webbrowser.open("file://" + OUTPUT_HTML)

if __name__ == "__main__":
    print("⏳ Obteniendo las 386 cuentas desde Power BI...")
    accs = fetch_accounts()
    print(f"📊 {len(accs)} cuentas recibidas. Generando dashboard interactivo...")
    generate_html(accs)
