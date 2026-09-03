# Pruebas

Datos **100% ficticios**. Ninguna factura real vive en este repositorio.

Las fixtures usan los RFC genéricos del SAT: `EKU9003173C9` (emisor de pruebas)
y `XAXX010101000` (público en general). Los UUID son literales tipo
`AAAAAAAA-1111-…`, imposibles de confundir con un folio fiscal real.

## Correr

```bash
python pruebas/correr.py
```

Once comprobaciones de punta a punta. Sale con código 1 si alguna falla.

## Regenerar las fixtures

```bash
python pruebas/generar.py    # requiere reportlab para el PDF
```

## Qué cubre cada fixture

| Archivo | Caso |
|---|---|
| `normal.xml` | CFDI 4.0 simple, timbrado, sin descuento |
| `descuento.xml` | Con `Comprobante@Descuento` — el caso que descuadra el Excel |
| `sin-timbre.xml` | Sin Timbre Fiscal Digital: debe capturarse marcado, no descartarse |
| `solo-pdf.pdf` | PDF **sin** su XML, para ejercitar la ruta de extracción de texto |

`solo-pdf.pdf` no tiene XML al lado a propósito: si lo tuviera, el XML ganaría
y la ruta PDF nunca se probaría.

## Si agregas una factura real aquí

No lo hagas. El `.gitignore` exceptúa `pruebas/facturas/*.xml` y `*.pdf` para
que las fixtures se commiteen, así que **cualquier archivo que dejes en esta
carpeta sí entra al repositorio**. Las facturas reales van en `/facturas/` o
`/ejemplos/`, que están ignoradas.
