---
name: facturalm
description: Use when the user hands over a Mexican invoice (CFDI) — XML, PDF, or a photo/scan — to capture into a spreadsheet: capturar facturas, procesar CFDI, actualizar el Excel de facturas, contabilizar comprobantes fiscales, deducciones. Read this BEFORE opening or looking at any invoice file: the skill extracts text with local OCR and must never use vision on the document.
---

# facturalm — Facturas (CFDI) a Excel

Extrae los datos de facturas mexicanas y los **acumula** en un `.xlsx` que
sobrevive entre corridas. El XML se procesa solo; el PDF necesita que tú leas
el texto y llenes los campos.

## Regla que rompe todo lo demás si la ignoras

**Cuando te den una factura —foto, captura, PDF o lo que sea— NO la mires.**
No uses la herramienta de visión, no la abras con `Read`, no la describas.
Copia el archivo a la carpeta y corre `procesar.py`. El texto sale de
`pdf_texto.py`, que hace OCR local con Tesseract.

Esto pasó en la primera instalación real: el agente vio la imagen antes de
correr la skill, y el usuario tuvo que corregirlo. Es fácil de hacer sin
darse cuenta, porque mirar la foto parece el camino corto.

| Lo que piensas | Por qué no |
|---|---|
| "Es más rápido si solo la veo" | El punto de la skill es no depender de visión. Un modelo sin ella queda fuera. |
| "Solo miro para confirmar el OCR" | Entonces el resultado depende de tus ojos y deja de ser reproducible. |
| "Es una foto, no un PDF; el OCR no aplica" | Sí aplica: `.jpg`/`.png` van por `ocr-imagen`. |
| "El OCR salió sucio, mejor la leo" | Reporta lo ilegible y pregunta. Inventar un dato fiscal es peor que dejarlo vacío. |
| "El usuario me la pegó en el chat" | Pide que la guarde como archivo y procésala. |

La única excepción es una imagen que solo existe pegada en la conversación,
sin archivo en disco: ahí dilo y pide el archivo.

**Datos privados.** Son facturas reales. Todo corre localmente, sin red. No
copies RFC, montos ni UUID al chat salvo que el usuario lo pida.

## Cómo te lo van a pedir

**"Las voy a ir dejando en esta carpeta, saca la info."** Es el caso central y
para el que está diseñada la skill. Corre `procesar.py` sobre la carpeta cada
vez; el append idempotente hace que solo entren las facturas nuevas. No hace
falta mover ni limpiar nada entre corridas, ni llevar registro de lo ya
procesado: el Excel es el registro.

**"Aquí te paso esta factura."** Si te dan la ruta de un archivo (así llegan
los adjuntos en la mayoría de agentes), trátalo igual: corre `procesar.py`
sobre la carpeta que lo contiene, o el script individual si es solo uno.

Si te pegan el **XML como texto** en el chat, guárdalo a un archivo temporal y
pásalo por `cfdi_xml.py`. No lo interpretes tú: el parser ya maneja los
namespaces, el descuento y el matiz de los impuestos.

Si lo que hay es una **factura escaneada o fotografiada** —un PDF sin capa de
texto, o un `.jpg`/`.png` suelto— también se procesa: va por OCR con Tesseract,
que corre local. Requiere tener Tesseract instalado; si falta, el script lo dice
en vez de fallar a medias.

Lo único que la skill no puede hacer es leer una imagen que solo existe pegada
en la conversación, sin archivo en disco. Pide que te la guarden como archivo.

## Uso normal

```bash
cd <skill>/scripts
python procesar.py <carpeta-de-facturas> --excel <salida.xlsx>
```

**Entra a las subcarpetas por defecto.** Si el usuario organiza por año
(`entrantes/2025/`, `entrantes/2026/`), apunta a la carpeta padre y las toma
todas. Con `--sin-recursion` se queda en un solo nivel.

Esto ya deja hecho todo lo que tiene XML. Devuelve un JSON con los conteos.
Re-ejecutarlo sobre la misma carpeta agrega **0 filas**: la clave es el UUID
del Timbre Fiscal.

Si un archivo `.xml` y un `.pdf` comparten nombre, **gana el XML** — es el
documento fiscal; el PDF es su representación impresa.

## Cuando hay PDF sin XML

`procesar.py` no adivina campos. Extrae el texto, lo deja en
`<salida>.pendientes.json` y se detiene. Entonces te toca a ti:

1. Lee `<salida>.pendientes.json`. Cada entrada trae `archivo`, `metodo` y `texto`.
2. Por cada factura, arma un objeto con las claves de abajo. Deja
   `"uuid": "Sin Timbre"` si no encuentras un folio fiscal legible.
3. Marca siempre `"_origen": "PDF"` y `"_confianza": "revisar"`.
4. Insértalo:

```bash
python excel_merge.py <salida.xlsx> --json - <<'EOF'
[{ ...objetos... }]
EOF
```

**No inventes campos.** Si un dato no está en el texto, usa `null`. Una fila
incompleta y marcada es útil; una fila inventada corrompe la contabilidad.

**Y no des por bueno un RFC solo porque se lee entero.** Corre `verificar.py`
después de insertar: comprueba el dígito verificador y delata los que el OCR
leyó mal aunque parezcan correctos.

## Esquema de la fila

```json
{
  "archivo": "factura.pdf", "uuid": "...", "fecha": "2026-01-15",
  "emisor": "...", "rfc": "...", "receptor": "...", "rfc_receptor": "...",
  "tipo_comprobante": "Ingreso", "concepto": "...",
  "subtotal": 100.0, "descuento": 0.0, "importe": 116.0,
  "impuestos_trasladados": 16.0, "impuestos_retenidos": 0.0,
  "moneda": "MXN", "metodo_pago": "PUE", "forma_pago": "Efectivo",
  "uso_cfdi": "G03 - Gastos en general", "categoria": "Servicios",
  "estado": "OK", "_origen": "PDF", "_confianza": "revisar"
}
```

**No escribas `_ruta` a mano.** En Windows la ruta lleva `\` y produce escapes
inválidos que rompen el JSON. Si la quieres, cópiala tal cual de
`pendientes.json`, que ya viene con barras normales.

Ver `referencia/columnas.md` para el origen de cada columna en el CFDI.

## Scripts

| Script | Qué hace |
|---|---|
| `procesar.py` | Orquesta una carpeta completa. Punto de entrada normal. |
| `cfdi_xml.py` | CFDI 4.0 → JSON. Solo v4.0; v3.3 da error explícito. |
| `pdf_texto.py` | PDF o imagen → texto. Clasifica y extrae con pdf-inspector; pdfplumber de respaldo; OCR si hace falta. |
| `excel_merge.py` | Upsert idempotente en el `.xlsx`. `--actualizar` sobreescribe. |
| `catalogos.py` | Catálogos del SAT y clasificación de deducciones. |
| `diagnostico.py` | Revisa que el entorno esté completo y dice qué falta. |
| `verificar.py` | Comprueba `Subtotal − Descuento + Trasladados − Retenidos = Total`. |

## Comportamiento del Excel

- Se crea si no existe; si existe, **solo agrega**.
- Si el Excel viene de una versión anterior y le falta una columna, se agrega
  al final en la siguiente corrida — pero **vacía** en las filas que ya existen,
  porque el upsert las omite por duplicadas. Para rellenarlas:
  `python procesar.py <carpeta> --excel <xlsx> --actualizar`.
- Preserva las celdas editadas a mano y las columnas propias que el usuario
  haya agregado a la derecha.
- Sin UUID se usa la clave sustituta `rfc|fecha|importe`.
- `--actualizar` reescribe la fila cuando el UUID ya existe.

## Verificar el resultado

```bash
python verificar.py <salida.xlsx>
```

Reporta las filas que no cuadran (solo número de fila y diferencia, nunca los
datos). Un descuadre en una fila `_origen: PDF` casi siempre es un monto mal
leído. Sale con código 1 si encuentra alguno.

También **valida el dígito verificador de los RFC**. Corre esto siempre después
de capturar una factura por OCR: un RFC mal leído (`Z` como `2` es lo típico)
no solo ensucia el dato, rompe la clave `rfc|fecha|importe` con la que se
deduplican las filas sin UUID, y esa factura podría entrar dos veces.

Para comprobar que la skill entera sigue funcionando tras un cambio:
`python pruebas/correr.py` (usa facturas sintéticas, no datos reales).

## Limitaciones conocidas

- **No verifica el sello digital** del SAT. Se captura lo que la factura dice;
  no se comprueba que la firma sea válida.
- Una fila por factura: los conceptos se concatenan, no se desglosan.
- CFDI 4.0 únicamente.

## Cómo se lee un PDF

Tres niveles, en orden. El `metodo` que reporta `pdf_texto.py` dice cuál se usó:

1. `posiciones` — pdf-inspector da los TextItem con coordenadas y se reconstruyen
   los renglones agrupando por Y y ordenando por X. Es el mejor: conserva la
   estructura etiqueta:valor que necesitas para leer la factura.
2. `pdfplumber` — se usa cuando pdf-inspector no está instalado **y también
   cuando el texto posicionado trae los acentos rotos**. Pasa en facturas
   reales: la `é` sale como `Ø` y la `ó`/`í` desaparecen, sin que el
   clasificador lo reporte. Se compara el número de acentos de cada método y
   gana el que conserve más.
3. `ocr` — Tesseract, cuando el clasificador dice que el PDF está escaneado.
4. `ocr-imagen` — Tesseract directo, para un `.jpg`/`.png`/`.tif` suelto. Una
   imagen no tiene capa de texto que rescatar: es OCR o nada.

Una factura leída por OCR **casi nunca conserva el UUID**: es letra chica y una
cadena hexadecimal larga, y el OCR la pierde a cualquier escala. Eso no impide
capturarla — `excel_merge` usa la clave sustituta `rfc|fecha|importe`— pero sí
significa que esa fila no se puede cruzar por folio fiscal contra el XML si
llega después. Marca siempre `_confianza: revisar`.

No uses `r.markdown` de pdf-inspector para facturas: colapsa el documento en ~9
líneas y pierde los saltos de renglón. `extract_text()` tampoco: pierde uno de
los dos RFC. Ambas cosas están medidas contra las facturas de prueba.

## Requisitos

```bash
pip install -r scripts/requirements.txt
python scripts/diagnostico.py          # revisa qué falta
```

Si el diagnóstico marca `FALTA` en algo obligatorio, no proceses facturas
todavía: arregla eso primero. Los `AVISO` solo limitan la ruta OCR.

### Cuándo revisar el entorno

Nada se instala solo. Corre `diagnostico.py` en dos momentos:

- **La primera vez** que uses la skill en una máquina.
- **Cuando un documento falle con `SinTextoError`**, que es lo que lanza la
  ruta OCR cuando falta Tesseract. No supongas que el archivo está corrupto.

### Instalar Tesseract: pregunta antes

`diagnostico.py --instalar-tesseract` lo instala con winget, y encadena solo
el paquete de español —porque winget instala en silencio y eso se salta la
pantalla de idiomas, dejando únicamente inglés.

**Instalar software del sistema modifica la máquina del usuario: pídele
autorización antes de correr ese comando.** Nunca lo lances por tu cuenta
porque una factura falló. Si dice que no, sigue procesando: todo lo que tenga
XML o capa de texto funciona igual, y solo las escaneadas quedan pendientes.

Solo para **PDFs escaneados o imágenes**, además:
`winget install UB-Mannheim.TesseractOCR` y `pip install pytesseract pillow`.
Sin Tesseract, un documento escaneado no tiene ruta y el script lo dice en vez
de fallar a medias.

**No hace falta que Tesseract esté en el PATH.** El instalador de Windows no
suele agregarlo, así que la skill lo busca también en las rutas habituales
(`Program Files`, `LOCALAPPDATA/Programs`) y respeta `$TESSERACT_CMD` si lo
tienes en otro lado.

**Marca el idioma español al instalar.** Si `tessdata` solo trae `eng`, el OCR
igual corre —degrada a inglés en vez de abortar— pero las etiquetas acentuadas
("Descripción", "Régimen", "Método de Pago") salen peor. Los datos que más
importan (RFC, UUID, montos) son ASCII y se leen bien en ambos casos. Para
agregarlo después, basta copiar `spa.traineddata` a la carpeta `tessdata`.

pdf-inspector trae su propio OCR (`process_pdf_with_ocr`), **no se usa**:
requiere apuntar `PDFIUM_LIB_PATH` a una librería PDFium y **descarga modelos
ONNX de internet**, lo que choca con la garantía de que todo corre local.
