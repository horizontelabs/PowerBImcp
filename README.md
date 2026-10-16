# PowerBImcp — Power BI & Business Central Automation Engine

Sistema de automatización y despliegue programático de reportes en **Power BI Service** utilizando el formato moderno **PBIR (Power BI Enhanced Report Format)** y la **API REST de Microsoft Fabric**, conectado al modelo de datos de **Dynamics 365 Business Central**.

---

## 🏛️ Dashboard Ejecutivo para Gerencia de Finanzas

El proyecto incluye la generación automatizada de un dashboard ejecutivo minimalista para explorar y auditar el **Plan de Cuentas (Chart of Accounts)** de la compañía.

### Componentes Clave:
1. **Vista Principal — Maestro de Cuentas:**
   - Tabla compacta con 3 columnas esenciales: `Nº Cuenta (ID)`, `Nombre de la Cuenta` y `Categoría Contable`.
   - Navegación ágil, ordenamiento y selección interactiva.
2. **Indicadores Ejecutivos Estructurales:**
   - **Total Cuentas:** Conteo total de cuentas del catálogo (`386`).
   - **Cuentas Imputables (Posting):** Cuentas operativas que reciben asientos contables (`231`).
   - **Cuentas de Agrupación (Total):** Cuentas de cabecera y estructura (`155`).
   - **Cuentas Bloqueadas:** Cuentas con restricción activa en Business Central (`14`).
3. **Resumen Visual de Estructura:**
   - Gráfico de barras horizontal que refleja la distribución del catálogo por categoría contable (Activos, Pasivos, Gastos, Ingresos, Patrimonio, Costo de Ventas).
4. **Ficha de Detalle Interactivo:**
   - Sincronización en tiempo real al seleccionar cualquier cuenta: visualización de tipo de cuenta, contabilización directa, estado de bloqueo, fecha de modificación y GUID de Business Central.
5. **Auditoría Técnica Individual (Segunda Página):**
   - Buscador predictivo por ID y Nombre, con todos los parámetros técnicos y de consolidación del ERP.

---

## 📂 Estructura del Repositorio

```text
├── SIMONE_SPA_V3.pbip               # Proyecto Power BI Enhanced Report Format (PBIR)
│   └── SIMONE_SPA_V3.Report/
│       ├── definition/
│       │   ├── pages/               # Definiciones JSON de páginas y visuales
│       │   ├── report.json          # Configuración global del reporte
│       │   └── version.json
│       ├── definition.pbir          # Puntero semántico a Power BI Service
│       └── StaticResources/        # Temas y paletas Fluent corporativas
├── deploy_executive_finance_dashboard.py # Script de compilación y despliegue PBIR a la nube
├── connect.py                       # Autenticación MSAL y verificación de dataset DAX
├── Catalogo_SIMONE.pbip             # Proyecto PBIP base
└── README.md
```

---

## 🚀 Requisitos e Instalación

### Requisitos:
* Python 3.10+
* Cuenta de Microsoft con acceso a Power BI / Microsoft Fabric

### Instalación:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests msal
```

### Autenticación y Despliegue:
```bash
# Probar conexión con el servicio
python connect.py

# Desplegar el dashboard ejecutivo directamente a Power BI Service
python deploy_executive_finance_dashboard.py
```

---

## 🔐 Seguridad
Los tokens de acceso y sesión (`token.json`, `.token_cache.bin`) están excluidos del repositorio a través de `.gitignore`.
