# Las columnas y su origen en el CFDI 4.0

Replican `buildExportRows()` de ExtFact para que el
Excel sea comparable con el que genera ExtFact, **más `Descuento`**, que ExtFact
no exporta y sin el cual las cifras no cuadran.

| # | Columna | Origen en el XML |
|---|---|---|
| 1 | Archivo | nombre del archivo procesado |
| 2 | UUID | `TimbreFiscalDigital@UUID`; si falta → `Sin Timbre` |
| 3 | Fecha | `Comprobante@Fecha`, truncada a `YYYY-MM-DD` |
| 4 | Emisor | `Emisor@Nombre` |
| 5 | RFC | `Emisor@Rfc` |
| 6 | Nombre Receptor | `Receptor@Nombre` |
| 7 | RFC Receptor | `Receptor@Rfc` |
| 8 | Tipo de Comprobante | `Comprobante@TipoDeComprobante` (I/E/P/N/T) → etiqueta |
| 9 | Concepto | todos los `Concepto@Descripcion` unidos con `, ` |
| 10 | Subtotal | `Comprobante@SubTotal` (numérico, `#,##0.00`) |
| 11 | Descuento | `Comprobante@Descuento`, opcional → 0 si no viene |
| 12 | Importe | `Comprobante@Total` (numérico) |
| 13 | Impuestos Trasladados | `Impuestos@TotalImpuestosTrasladados` (numérico) |
| 14 | Impuestos Retenidos | `Impuestos@TotalImpuestosRetenidos` (numérico) |
| 15 | Moneda | `Comprobante@Moneda`, default `MXN` |
| 16 | Método de Pago | `Comprobante@MetodoPago`, código crudo (PUE/PPD) |
| 17 | Forma de Pago | `Comprobante@FormaPago` resuelto contra `FORMAS_PAGO` |
| 18 | Uso CFDI | `Receptor@UsoCFDI` resuelto contra `USOS_CFDI` |
| 19 | Categoría | clasificación de deducción (ver abajo) |
| 20 | Estado | `OK`, o el detalle del error |

Más tres columnas de control propias de esta skill: `_origen` (XML/PDF),
`_confianza` (alta/revisar) y `_ruta`.

## El matiz de los impuestos

Los totales se leen del `<cfdi:Impuestos>` que es **hijo directo** del
Comprobante. Una búsqueda recursiva devolvería los `<Impuestos>` de un
Concepto y daría cifras equivocadas — es el motivo de `_hijo_directo()` en
`cfdi_xml.py`, y por el que ExtFact usa su propio `directChild()`.

Si los atributos globales faltan, se suman los `Importe` a nivel concepto.

## Categoría

Prioridad: (1) el Uso CFDI, que es autoritativo — D01–D10 son justo las
deducciones personales e I01–I08 las inversiones; (2) palabras clave sobre el
Concepto normalizado sin acentos; (3) fallback `G01 → mercancías`,
`G03 → servicios`, y si no, `otros`.

## Diferencia con ExtFact

ExtFact no exporta `Descuento`, así que su Excel no cuadra en facturas que lo
traen (una de las de prueba descuenta 22,049.28 sobre un subtotal de 28,800).
Aquí sí se captura, y la identidad que debe cumplirse es:

    Subtotal − Descuento + Trasladados − Retenidos = Total

`verificar.py` la comprueba en cada fila.
