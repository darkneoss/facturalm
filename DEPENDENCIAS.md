# Dependencias de terceros

**Este repositorio no distribuye código de terceros.** Todo lo que contiene es
propio y está bajo [MIT](LICENSE). Lo de abajo se instala en tu máquina, con
sus propias licencias, y no viaja dentro de este repo.

Se documenta por transparencia, no porque MIT lo exija: como no redistribuimos
estos componentes, no arrastramos sus obligaciones de aviso.

## Se instalan con pip

| Paquete | Licencia | Para qué |
|---|---|---|
| [pdf-inspector](https://github.com/firecrawl/pdf-inspector) | MIT © Firecrawl | Clasificar el PDF y extraer texto posicionado |
| lxml | BSD | Parsear el CFDI |
| openpyxl | MIT | Leer y escribir el Excel |
| pdfplumber | MIT | Segundo lector de PDF |
| pypdfium2 | Apache-2.0 / BSD-3 | Renderizar páginas para OCR |
| pytesseract | Apache-2.0 | Puente a Tesseract |
| Pillow | MIT-CMU | Leer imágenes sueltas |

## Se instalan aparte (opcionales, solo para OCR)

**[Tesseract OCR](https://github.com/tesseract-ocr/tesseract)** — Apache-2.0.
Binario del sistema; no entra por pip. Solo hace falta para PDFs escaneados e
imágenes.

**Paquetes de idioma (`tessdata`)** — Apache-2.0. `diagnostico.py
--instalar-spa` descarga `spa.traineddata` desde el repositorio oficial de
Tesseract al `tessdata` de tu instalación. Es la única descarga que hace este
proyecto, y solo cuando se la pides explícitamente.

## Nada más sale a la red

El procesamiento de facturas no hace una sola petición. Las facturas nunca
salen de tu máquina.
