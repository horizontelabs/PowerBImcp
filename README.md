# PowerBImcp — Resumen financiero de SIMONE SPA en Power BI

Generador programático de un reporte de Power BI en formato **PBIR**, publicado con la
**Fabric REST API** sobre el modelo semántico de Dynamics 365 Business Central. No se
usa Power BI Desktop: todo el reporte sale de `management_dashboard.py`.

## Reportes Disponibles

1. **HOLDING INSIGNE V1 (Multiempresa — 37 Sociedades)**:
   - Report ID: `67d5b2fd-4139-4c10-8948-ec838415f5f3` | Dataset ID: `c71af0b4-2794-415e-a304-ce9a9fcb3619`
   - Páginas:
     - `consolidadoFinanciero`: KPIs consolidados de Activos ($1.58B), Pasivos, Patrimonio, Resultado, selector interactivo de filial, rankings de sociedades y matriz financiera ejecutiva.
     - `gobernanzaCatalogo`: Auditoría y homologación de 14.356 cuentas contables, desglose por clase y maestro consolidado.
     - `proveedores`: Gestión de proveedores y cuentas por pagar consolidadas (deuda total de $3.47B, ratio vencido, concentración por filial y proveedor, maestro con tramos de vencimiento, catálogo maestro de 17.610 proveedores y 3.598 facturas de compra trazables en 37 filiales).
     - `periodosContables`: Control de 1.116 períodos contables, meses cerrados y fechas bloqueadas en las 37 filiales.
   - Enlace directo: <https://app.powerbi.com/groups/me/reports/67d5b2fd-4139-4c10-8948-ec838415f5f3/consolidadoFinanciero?experience=power-bi>

2. **SIMONE SPA V3 (Individual — INVERSIONES SIMONE SPA)**:
   - Report ID: `86bfa92e-97f1-4ee5-b045-f04cad6ebfe8` | Dataset ID: `83af4580-d8a1-4519-ae25-98bff396291a`
   - Páginas: `resumenFinanciero`, `gobernanzaCatalogo`, `proveedores`.
   - Enlace directo: <https://app.powerbi.com/groups/me/reports/86bfa92e-97f1-4ee5-b045-f04cad6ebfe8/resumenFinanciero?experience=power-bi>

## Uso

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install requests msal jsonschema pytest
python connect.py                          # primera vez: login con código de dispositivo, crea token.json
python -m pytest                           # valida la definición contra los esquemas oficiales de PBIR
python management_dashboard.py --dry-run   # genera y escribe SIMONE_SPA_V3.pbip sin publicar
python management_dashboard.py             # publica a Power BI Service
```

## Estructura

```
management_dashboard.py        # reporte SIMONE SPA: medidas, páginas, visuales y despliegue
holding_dashboard.py           # reporte HOLDING INSIGNE: consolidación de 37 filiales, ranking y gobernanza
tests/                         # tests de ambos generadores y esquemas PBIR vendorizados
SIMONE_SPA_V3.pbip/            # copia local de la definición de SIMONE SPA
HOLDING_INSIGNE_V1.pbip/       # copia local de la definición multiempresa HOLDING INSIGNE
connect.py                     # prueba de conexión y login inicial
AGENTS.md                      # guía para agentes: reglas PBIR, diagnóstico de la versión anterior, checklist
```

`Catalogo_SIMONE.pbix`, `deploy_powerbi_report.py`, `auto_generate_report.py` y
`build_dashboard.py` son de una generación anterior y apuntan a otro dataset; se
conservan como referencia pero no forman parte del flujo.

## Seguridad

`token.json` y `.token_cache.bin` contienen credenciales y están en `.gitignore`.
