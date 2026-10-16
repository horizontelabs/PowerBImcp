# PowerBImcp — Resumen financiero de SIMONE SPA en Power BI

Generador programático de un reporte de Power BI en formato **PBIR**, publicado con la
**Fabric REST API** sobre el modelo semántico de Dynamics 365 Business Central. No se
usa Power BI Desktop: todo el reporte sale de `management_dashboard.py`.

## El reporte

Una página, **Resumen financiero**, pensada para gerencia: sin tablas ni filtros,
cuatro gráficos y nada que haya que operar.

| Gráfico | Qué muestra |
|---|---|
| Estructura financiera | Activos, pasivos y patrimonio |
| Estado de resultados | Ingresos, costo de ventas, gastos y resultado acumulado |
| Diez cuentas con mayor saldo | Cuentas imputables, saldo según su naturaleza contable |
| Composición de activos | Treemap de las cuentas imputables de activo |

Las cifras provienen de medidas a nivel de reporte (`reportExtensions.json`) que
consideran sólo cuentas imputables (`Posting`), invierten el signo de los saldos
acreedores y se expresan en millones de pesos (MM$). El modelo semántico no se toca.

Enlace directo (requiere acceso al workspace del dueño):
<https://app.powerbi.com/groups/me/reports/86bfa92e-97f1-4ee5-b045-f04cad6ebfe8/resumenFinanciero?experience=power-bi>

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
management_dashboard.py        # medidas, página, visuales y despliegue
tests/                         # tests del generador y esquemas PBIR vendorizados
SIMONE_SPA_V3.pbip/            # copia local de la definición publicada (la escribe el script)
connect.py                     # prueba de conexión y login inicial
AGENTS.md                      # guía para agentes: reglas PBIR, diagnóstico de la versión anterior, checklist
```

`Catalogo_SIMONE.pbix`, `deploy_powerbi_report.py`, `auto_generate_report.py` y
`build_dashboard.py` son de una generación anterior y apuntan a otro dataset; se
conservan como referencia pero no forman parte del flujo.

## Seguridad

`token.json` y `.token_cache.bin` contienen credenciales y están en `.gitignore`.
