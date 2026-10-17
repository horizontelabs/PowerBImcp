# PowerBImcp — guía para agentes

Este archivo es el contexto que un agente (Gemini, Claude, Codex) debe leer antes de
tocar el repo. Resume qué es el proyecto, cómo se desarrolla, qué reglas del formato
PBIR aprendimos a golpes y qué estaba roto antes de la intervención de octubre de 2026.

## Qué es

Un generador de reportes de Power BI. No usamos Power BI Desktop: el reporte se
describe en Python, se compila al formato **PBIR** (Power BI Enhanced Report Format,
carpetas de JSON) y se publica con la **Fabric REST API** (`getDefinition` /
`updateDefinition`). El modelo semántico ya existe en el servicio y proviene de
Dynamics 365 Business Central; el reporte sólo lo consume.

| Recurso | Valor |
|---|---|
| Reporte Multiempresa | `HOLDING INSIGNE V1`, id `67d5b2fd-4139-4c10-8948-ec838415f5f3` |
| Modelo Multiempresa | `HOLDING INSIGNE V1`, id `c71af0b4-2794-415e-a304-ce9a9fcb3619` (37 filiales, 14.356 cuentas) |
| Reporte Individual | `SIMONE SPA V3`, id `86bfa92e-97f1-4ee5-b045-f04cad6ebfe8` |
| Modelo Individual | `SIMONE SPA V3`, id `83af4580-d8a1-4519-ae25-98bff396291a` |
| Workspace | "Mi área de trabajo" del dueño (`f97935fd-…`). |
| Autenticación | MSAL, flujo de código de dispositivo, app pública `ea0616ba-…`. El token queda en `token.json` (ignorado por git). |

## Estructura

```
holding_dashboard.py             # Generador PBIR para HOLDING INSIGNE (multiempresa, 37 filiales)
management_dashboard.py          # Generador PBIR para SIMONE SPA V3 (individual)
tests/test_holding_dashboard.py  # Tests unitarios y validación de esquemas para Holding Insigne
tests/test_management_dashboard.py # Tests unitarios para Simone SpA
tests/schemas/                   # esquemas JSON oficiales de PBIR (microsoft/json-schemas), vendorizados
HOLDING_INSIGNE_V1.pbip/         # copia local sincronizada de la definición de HOLDING INSIGNE
SIMONE_SPA_V3.pbip/              # copia local sincronizada de la definición de SIMONE SPA
connect.py                       # prueba de conexión y login inicial (genera token.json)
```

## Flujo de trabajo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install requests msal jsonschema pytest
python connect.py                          # primera vez: login y token.json
python -m pytest                           # siempre antes de publicar
python management_dashboard.py --dry-run   # genera y escribe SIMONE_SPA_V3.pbip sin publicar
python management_dashboard.py             # publica a Power BI Service
```

Reglas de git: nunca se hace commit en `main`; rama de feature y pull request.
Después de publicar, la carpeta `SIMONE_SPA_V3.pbip` debe quedar idéntica a lo que
está en el servicio (el script la reescribe en cada corrida). Se commitea junto con
el cambio al script.

## Cómo se construye un reporte aquí

1. **Las cifras viven en medidas a nivel de reporte**, no en agregaciones de columnas.
   Se declaran en `definition/reportExtensions.json` (entidad `accounts`) y los
   visuales las referencian con `{"Measure": {"Expression": {"SourceRef": {"Schema":
   "extension", "Entity": "accounts"}}, "Property": "<nombre>"}}`. Ventaja: el nombre
   de la medida es la etiqueta del eje, así que no dependemos de los valores (a veces
   feos) que trae el modelo. El modelo semántico **no se modifica** desde este repo.
2. **Cada visual es un `visual.json`** generado por una función pura. `build_parts()`
   toma las partes que devuelve Fabric, conserva metadatos y tema, descarta todas las
   páginas y arma las nuevas.
3. **Todo JSON generado se valida contra el esquema que declara en `$schema`**
   (`tests/schemas`). Si un visual no valida, no se publica.
4. Formato: montos en millones de pesos con `formatString` `#,0,, "MM$"` y
   `labelDisplayUnits = 1` (sin unidades automáticas encima del formato).

## Reglas del formato PBIR que cuestan caro ignorar

- **Enum de agregación** (`Aggregation.Function`): `0` Sum, `1` Average, `2` Distinct
  count, `3` Min, `4` Max, `5` CountNonNull, `6` Median, `7` StdDev, `8` Variance.
  Fuente: `tests/schemas/semanticQuery_1.2.0.json`, definición `QueryAggregateFunction`.
  No adivinar; abrir el esquema.
- **`queryRef` es canónico**: `tabla.columna` para columnas, `tabla.medida` para
  medidas, `CountNonNull(tabla.columna)` (nombre de la función) para agregaciones.
  No inventar etiquetas como `Aggr(...)`.
- **Cuentas `Total` son subtotales.** Cualquier suma sobre `netChange` debe filtrar
  `accounts[accountType] = "Posting"` o duplica todo. Hay un test que lo exige.
- **Signo contable.** Business Central guarda los saldos acreedores en negativo
  (pasivos, patrimonio, ingresos). Para gerencia se invierte el signo por categoría;
  la medida `Saldo natural` lo hace por fila.
- **Las categorías vienen escapadas en OData**: `Cost_x0020_of_x0020_Goods_x0020_Sold`
  y una cuenta con categoría `_x0020_` (en blanco). Un visual con `category` en un eje
  muestra eso tal cual. Por eso las categorías se nombran vía medidas.
- **Filtro Top N por medida de extensión**: en la subconsulta, `From` lleva la
  entidad dos veces, una normal (`a`) y otra con `"Schema": "extension"` (`e`), y el
  `OrderBy` usa `SourceRef.Source = "e"`. Ver `top_n_filter()`.
- Para un ejemplo real de cualquier construcción, buscar `visual.json` en GitHub
  (`microsoft/BCApps` trae los reportes oficiales de Business Central en PBIR).

## Qué estaba roto antes (octubre de 2026) y cómo se encontró

Síntoma: al abrir el reporte, cada tarjeta y el gráfico de barras mostraban "Hubo un
problema con uno o más campos", error subyacente `Missing_References`. Tablas y
segmentadores funcionaban.

Diagnóstico, en orden, con cada hipótesis descartada por evidencia:

1. *¿Faltan columnas en el modelo?* Se consultó `INFO.VIEW.COLUMNS()` con
   `executeQueries`: las 13 columnas referenciadas existían. Descartado.
2. *¿`queryRef` inventado?* Se corrigió en una sola tarjeta y se publicó. Seguía
   fallando. Descartado como causa (seguía siendo un defecto).
3. *¿Agregación mal codificada?* Comparando contra un visual oficial de Microsoft,
   `CountNonNull` era `Function: 5`; el script usaba `1` creyendo que era "count".
   `1` es **Average**, y promediar la columna de texto `number` es exactamente un
   error de campo. Confirmado con el esquema y con el reporte renderizando al
   corregirlo en los 6 visuales afectados.

Otros defectos del código anterior, para no repetirlos:

- El reporte se había re-vinculado a un modelo (`83af…`) distinto del que todos los
  scripts inspeccionaban (`d7c2…`), sin revisar su esquema.
- Los KPI tenían los números escritos a mano en el título ("386 Cuentas").
- Cuatro copias de la configuración y tres rutinas de token distintas entre scripts.
- Cards con `Max` sobre columnas de texto, sin significado.
- Un detalle "al seleccionar" prometido en el README que ninguna definición implementaba.

Lección: antes de proponer un arreglo, obtener evidencia en cada capa (modelo →
definición → servicio) y cambiar **una** variable por publicación.

## Datos del modelo (para diseñar visuales nuevos)

Tabla `accounts`, 386 filas: `id`, `number`, `displayName`, `category`,
`subCategory` (vacía en todas las filas), `blocked`, `accountType` (`Posting` 231 /
`Total` 155), `directPosting`, `netChange` (único numérico; saldo acumulado en CLP),
consolidación, `lastModifiedDateTime`. No hay medidas en el modelo. Suma de
`netChange` en cuentas `Posting` = 0 (balance cuadra).

Perfil útil: activos ≈ 594 mil MM$, pasivos ≈ 581 mil MM$, patrimonio ≈ 27 mil MM$,
ingresos ≈ 20 mil MM$, costo de ventas ≈ 14 mil MM$, gastos ≈ 19 mil MM$.

## Checklist antes de publicar

- [ ] `python -m pytest` en verde.
- [ ] `--dry-run` y revisar el `visual.json` de cualquier construcción nueva.
- [ ] Publicar, abrir el reporte en el navegador y mirar cada visual; un JSON válido
      no garantiza que el servicio lo renderice.
- [ ] Commitear `SIMONE_SPA_V3.pbip` tal como quedó publicado.
