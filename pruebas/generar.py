#!/usr/bin/env python3
"""Genera las facturas sinteticas de prueba.

Datos 100% ficticios: usa los RFC genericos del SAT (EKU9003173C9 para el
emisor de pruebas, XAXX010101000 para publico en general). Ninguna factura
real vive en este repositorio.

Cubre los casos que importan:
  - normal:     CFDI simple, sin descuento
  - descuento:  con Comprobante@Descuento, el caso que descuadra el Excel
  - sin-timbre: sin TimbreFiscalDigital, debe capturarse marcado

Uso: python generar.py
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
DESTINO = os.path.join(AQUI, "facturas")

PLANTILLA = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
                  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
                  Version="4.0" Serie="DEMO" Folio="{folio}"
                  Fecha="{fecha}T10:00:00" SubTotal="{subtotal:.2f}"{descuento}
                  Total="{total:.2f}" Moneda="MXN" TipoDeComprobante="I"
                  MetodoPago="PUE" FormaPago="03" LugarExpedicion="64000"
                  Exportacion="01">
  <cfdi:Emisor Rfc="EKU9003173C9" Nombre="ESCUELA KEMPER URGATE SA DE CV"
               RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="XAXX010101000" Nombre="PUBLICO EN GENERAL"
                 DomicilioFiscalReceptor="64000" RegimenFiscalReceptor="616"
                 UsoCFDI="{uso}"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1" ClaveUnidad="E48"
                   Descripcion="{concepto}" ValorUnitario="{subtotal:.2f}"
                   Importe="{subtotal:.2f}" ObjetoImp="02">
      <cfdi:Impuestos>
        <cfdi:Traslados>
          <cfdi:Traslado Base="{base:.2f}" Impuesto="002" TipoFactor="Tasa"
                         TasaOCuota="0.160000" Importe="{iva:.2f}"/>
        </cfdi:Traslados>
      </cfdi:Impuestos>
    </cfdi:Concepto>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="{iva:.2f}">
    <cfdi:Traslados>
      <cfdi:Traslado Base="{base:.2f}" Impuesto="002" TipoFactor="Tasa"
                     TasaOCuota="0.160000" Importe="{iva:.2f}"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>{timbre}
</cfdi:Comprobante>
"""

TIMBRE = """
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital Version="1.1" UUID="{uuid}"
        FechaTimbrado="{fecha}T10:00:05" RfcProvCertif="SAT970701NN3"
        SelloCFD="DEMO" NoCertificadoSAT="00001000000504465028" SelloSAT="DEMO"/>
  </cfdi:Complemento>"""

CASOS = [
    {"nombre": "normal", "folio": "1001", "fecha": "2026-01-15",
     "subtotal": 1000.00, "desc": 0.0, "uso": "G03",
     "concepto": "Servicio de consultoria",
     "uuid": "AAAAAAAA-1111-2222-3333-BBBBBBBBBBBB"},
    {"nombre": "descuento", "folio": "1002", "fecha": "2026-01-20",
     "subtotal": 28800.00, "desc": 22049.28, "uso": "G01",
     "concepto": "Material didactico",
     "uuid": "CCCCCCCC-4444-5555-6666-DDDDDDDDDDDD"},
    {"nombre": "sin-timbre", "folio": "1003", "fecha": "2026-01-25",
     "subtotal": 500.00, "desc": 0.0, "uso": "D10",
     "concepto": "Colegiatura enero", "uuid": None},
]


def construir(c):
    base = c["subtotal"] - c["desc"]
    iva = round(base * 0.16, 2)
    return PLANTILLA.format(
        folio=c["folio"], fecha=c["fecha"], subtotal=c["subtotal"],
        descuento=(' Descuento="%.2f"' % c["desc"]) if c["desc"] else "",
        total=round(base + iva, 2), uso=c["uso"], concepto=c["concepto"],
        base=base, iva=iva,
        timbre=TIMBRE.format(uuid=c["uuid"], fecha=c["fecha"]) if c["uuid"] else "",
    )


def pdf(c, ruta):
    """Representacion impresa, para probar la ruta PDF sin XML."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        return False
    base = c["subtotal"] - c["desc"]
    iva = round(base * 0.16, 2)
    lineas = [
        ("Factura DEMO-%s" % c["folio"], 16),
        ("", 10),
        ("Emisor: ESCUELA KEMPER URGATE SA DE CV", 10),
        ("RFC Emisor: EKU9003173C9", 10),
        ("Receptor: PUBLICO EN GENERAL", 10),
        ("RFC Receptor: XAXX010101000", 10),
        ("Fecha: %s" % c["fecha"], 10),
        ("Uso CFDI: %s" % c["uso"], 10),
        ("Metodo de Pago: PUE", 10),
        ("Forma de Pago: 03 Transferencia electronica de fondos", 10),
        ("", 10),
        ("Concepto: %s" % c["concepto"], 10),
        ("", 10),
        ("Subtotal: %.2f" % c["subtotal"], 10),
    ]
    if c["desc"]:
        lineas.append(("Descuento: %.2f" % c["desc"], 10))
    lineas += [
        ("IVA Trasladado: %.2f" % iva, 10),
        ("Total: %.2f" % round(base + iva, 2), 10),
        ("Moneda: MXN", 10),
        ("", 10),
    ]
    if c["uuid"]:
        lineas.append(("Folio Fiscal (UUID): %s" % c["uuid"], 9))

    cv = canvas.Canvas(ruta, pagesize=letter)
    y = 720
    for texto, tam in lineas:
        cv.setFont("Helvetica", tam)
        cv.drawString(72, y, texto)
        y -= tam + 8
    cv.showPage()
    cv.save()
    return True


def main():
    os.makedirs(DESTINO, exist_ok=True)
    sin_pdf = False
    for c in CASOS:
        x = os.path.join(DESTINO, "%s.xml" % c["nombre"])
        with open(x, "w", encoding="utf-8") as f:
            f.write(construir(c))
        # solo 'normal' lleva PDF, y sin su XML al lado, para ejercitar la
        # ruta de PDF huerfano
        if c["nombre"] == "normal":
            if not pdf(c, os.path.join(DESTINO, "solo-pdf.pdf")):
                sin_pdf = True
        print("  %s.xml" % c["nombre"])
    if sin_pdf:
        print("\nAviso: falta reportlab, no se genero el PDF (pip install reportlab)")
    else:
        print("  solo-pdf.pdf")


if __name__ == "__main__":
    main()
