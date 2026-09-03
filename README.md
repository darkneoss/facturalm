# facturalm

Skill de agente que extrae datos de facturas mexicanas (CFDI) —XML o PDF— y los
acumula en un Excel que sobrevive entre corridas.

Pensada para usarse desde Claude Code, Hermes u otro agente con acceso a shell.
Toda la lógica determinista vive en scripts de Python; el modelo solo interviene
cuando hay un PDF sin XML.

## Qué resuelve

Capturar facturas es un trabajo que nunca termina: llegan de a poco, unas con
XML y otras solo en PDF, y el Excel de siempre hay que volver a llenarlo. Las
herramientas que convierten CFDI a Excel suelen regenerar el archivo desde
cero, así que no puedes ir agregando: cada corrida empieza de nuevo y pierdes
lo que anotaste a mano.

Aquí el Excel es acumulativo. Dejas las facturas en una carpeta, corres el
script, y solo entran las nuevas. El Excel es el registro: no hace falta mover
lo ya procesado ni llevar una lista aparte.

- Re-procesar la misma carpeta agrega 0 filas (clave: UUID del Timbre Fiscal).
- Un PDF cuya factura ya entró por XML se detecta como duplicado.
- Preserva las celdas y columnas que agregues a mano al Excel.
- Captura `Descuento`, así el Excel cuadra:
  `Subtotal − Descuento + Trasladados − Retenidos = Total`.
- Acepta XML, PDF (con o sin capa de texto) e imágenes sueltas (`.jpg`, `.png`, …).
- **No requiere visión**: los documentos se convierten a texto localmente con
  [pdf-inspector](https://github.com/firecrawl/pdf-inspector) (clasificación +
  texto posicionado), así que funciona con modelos sin capacidad multimodal.
- Sin llamadas de red. Las facturas nunca salen de la máquina.

## Instalación

**1. Coloca la carpeta donde tu agente busca skills.**

| Agente | Ubicación |
|---|---|
| Claude Code | `~/.claude/skills/facturalm/` (o el repo en el proyecto) |
| Hermes | Bajo `~/.hermes/plugins/…/skills/facturalm/`; se invoca con `skill_view("facturalm")` |
| Otros | Cualquier ruta; basta con que el agente pueda leer `SKILL.md` |

Un agente sin descubrimiento de skills funciona igual: dile que lea `SKILL.md`
y siga las instrucciones de ahí.

**2. Instala las dependencias.**

```bash
pip install -r scripts/requirements.txt
python scripts/diagnostico.py
```

El diagnóstico dice qué falta y cómo arreglarlo. Nada del OCR se instala solo:
Tesseract es un binario del sistema y los paquetes de idioma son archivos de
datos, ninguno entra por pip. Para el español:
`python scripts/diagnostico.py --instalar-spa`.

Opcional, para PDFs escaneados e imágenes: Tesseract OCR con el paquete de idioma
`spa` (`winget install UB-Mannheim.TesseractOCR` + `pip install pytesseract`).

## Pruebas

```bash
python pruebas/correr.py
```

Veinte comprobaciones de punta a punta contra facturas sintéticas
(`pruebas/facturas/`, datos ficticios con los RFC genéricos del SAT). El
repositorio no contiene ninguna factura real.

## Uso

No está pensada para correrla a mano. Le hablas al agente:

> Voy a ir dejando las facturas en `~/facturas/2026`. Sácame la info a un Excel.

El agente corre `procesar.py`, y ahí se bifurca:

- **Las facturas con XML entran solas.** Es determinista, el modelo no
  interviene: parsear un CFDI no es un trabajo para un LLM.
- **Un PDF o imagen sin XML se detiene y te lo pasa.** El script extrae el
  texto (OCR si hace falta) y el agente saca los campos de ahí. Esas filas
  quedan marcadas `_confianza: revisar`.

Después basta con:

> Ya dejé más facturas, actualiza el Excel.

Solo entran las nuevas. Las que ya estaban se omiten por UUID, así que puedes
repetirlo sin pensar en cuáles procesaste antes.

Otras cosas que puedes pedirle:

- *"¿Cuadran los totales del Excel?"* — corre `verificar.py`, que comprueba
  `Subtotal − Descuento + Trasladados − Retenidos = Total` en cada fila. Útil
  sobre todo para las filas que salieron de un PDF.
- *"Esta factura solo la tengo en PDF, aquí está la ruta."*
- *"Corrige el concepto de la fila 4, el OCR lo leyó mal."*

### A mano

Si prefieres el CLI directo:

```bash
python scripts/procesar.py <carpeta-de-facturas> --excel salida.xlsx
python scripts/verificar.py salida.xlsx
```

Ver [SKILL.md](SKILL.md) para el flujo completo, incluido el handoff de los PDFs
sin XML, y [referencia/columnas.md](referencia/columnas.md) para el mapeo de
cada columna al CFDI.

## Licencias

Ver [LICENSES.md](LICENSES.md).
