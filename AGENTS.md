# Instrucciones para agentes que trabajen en este repositorio

Este repo **es** una skill (`SKILL.md`). Si vienes a *usar* la skill para
capturar facturas, lee `SKILL.md`. Lo de abajo es para modificar su código.

## Datos fiscales: la regla que no se negocia

Las facturas son documentos fiscales reales de clientes.

- **Nunca** commitees un XML, PDF o XLSX que no sea una fixture sintética.
  `/facturas/` y `/ejemplos/` están en `.gitignore` por eso; no los quites.
- **`pruebas/facturas/` es la excepción del `.gitignore`**: lo que dejes ahí
  **sí entra al repositorio**. Solo datos ficticios generados por
  `pruebas/generar.py` (RFC genéricos del SAT).
- Los scripts imprimen **solo conteos** por stdout, nunca RFC, montos ni UUID.
  La única excepción deliberada es el texto del PDF en el archivo de
  pendientes, que el modelo necesita para extraer campos. Si "mejoras" un
  mensaje de error, no metas datos de la factura en él.
- No copies contenido de facturas al chat ni a un issue, aunque sea para
  ilustrar un bug. Usa las fixtures de `pruebas/`.

## Sin dependencia de visión

La skill debe funcionar con modelos sin capacidad multimodal (DeepSeek, Llama).

- `pdf_texto.py` es la única frontera con el PDF y su contrato es `PDF -> str`.
- No agregues instrucciones tipo "abre el PDF" o "revisa la imagen": rompen en
  silencio en agentes sin visión.
- El OCR es Tesseract corriendo local, no el modelo "viendo" la factura.

## Si algo del entorno falla

```bash
python scripts/diagnostico.py
```

Es el único punto del proyecto que toca la red o modifica el sistema, y solo
con `--instalar-spa` / `--instalar-tesseract`. El procesamiento de facturas
nunca hace peticiones ni instala nada.

Si agregas una instalación automática en cualquier otro lado, la estás
poniendo donde nadie la espera: mantenla aquí y detrás de un flag.

## Antes de dar un cambio por terminado

```bash
python pruebas/correr.py
```

Once comprobaciones, sin datos reales. Si tocas el esquema de columnas o la
lógica de deduplicación, agrega la comprobación correspondiente ahí.

## Decisiones que parecen bugs y no lo son

- **`_hijo_directo()` en `cfdi_xml.py`**: los totales de impuestos se leen del
  `<cfdi:Impuestos>` hijo *directo* del Comprobante. Una búsqueda recursiva
  devuelve los `<Impuestos>` de un Concepto y da cifras equivocadas.
- **`excel_merge` selecciona columnas por nombre, no por posición.** Tras una
  migración, las columnas nuevas quedan al final, después de las que agregó el
  usuario. Indexar por posición rompe el backfill en silencio.
- **No se usa `r.markdown` ni `extract_text()` de pdf-inspector** para leer
  facturas: el primero colapsa el documento en ~9 líneas, el segundo pierde uno
  de los dos RFC. Se reconstruye desde `extract_text_with_positions()`.
- **El OCR propio de pdf-inspector (`process_pdf_with_ocr`) no se usa**:
  descarga modelos ONNX de internet, y eso rompe la garantía de "todo local".
- **Tesseract no se busca solo con `shutil.which`.** El instalador de Windows
  no lo agrega al PATH; `ruta_tesseract()` revisa además las rutas habituales
  y `$TESSERACT_CMD`. Simplificarlo a `which()` lo daría por ausente estando
  instalado.
- **`idiomas_ocr()` degrada a `eng` si falta `spa`.** Pedir un idioma que no
  está en `tessdata` aborta el OCR con un error de Tesseract; es mejor un OCR
  peor que ninguno. Fija `tesseract_cmd` antes de preguntar: sin eso reporta
  `eng` aunque el español sí esté instalado.

## Convenciones

Sin CI, sin changelog automático, sin conventional commits. Es un proyecto
pequeño y sin servidor: no hay qué correr ni qué publicar más allá de las
pruebas de arriba.
