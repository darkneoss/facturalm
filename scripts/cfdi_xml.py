#!/usr/bin/env python3
"""CFDI 4.0 (XML) -> JSON con el esquema de la skill.

Puerto de extractCFDIData() de ExtFact, la app web de la que nace esta skill.
No verifica el sello digital: eso se quedo en ExtFact y no aporta a la captura.

Uso:
    python cfdi_xml.py factura.xml            # un archivo -> JSON
    python cfdi_xml.py carpeta/ --glob        # todos los .xml -> JSON array
"""
import argparse
import json
import os
import sys

from lxml import etree

import catalogos as cat

CFDI_NS = "http://www.sat.gob.mx/cfd/4"
CFDI33_NS = "http://www.sat.gob.mx/cfd/3"
TFD_NS = "http://www.sat.gob.mx/TimbreFiscalDigital"

# Las facturas llegan de terceros: se parsean como datos hostiles.
#
# Con estas opciones, un XML con un DOCTYPE que declare entidades externas
# (<!ENTITY x SYSTEM "file:///...">) no puede leer archivos del disco ni
# hacer peticiones de red, y tampoco se puede montar una bomba de expansion
# de entidades. Hoy el parser por defecto de lxml ya rechaza ese caso porque
# no carga el DTD interno, pero eso es un default, no una garantia: dejarlo
# explicito evita que un cambio de version o un "arreglo" al mensaje de
# error lo reabra sin que nadie lo note.
_PARSER = etree.XMLParser(
    resolve_entities=False,   # no expandir entidades
    load_dtd=False,           # no leer el DTD (ni el subconjunto interno)
    no_network=True,          # nada de red al resolver referencias
    huge_tree=False,          # limites contra documentos desmesurados
)


class CFDIError(Exception):
    pass


def _hijo_directo(padre, local_name, ns):
    """Primer hijo DIRECTO con ese nombre y namespace.

    Existe porque una búsqueda recursiva (findall con //) devolvería los
    <Impuestos> de un Concepto en lugar del <Impuestos> global del
    Comprobante. Mismo motivo por el que ExtFact usa un helper directChild()
    en vez de getElementsByTagNameNS.
    """
    for hijo in padre:
        if isinstance(hijo.tag, str) and hijo.tag == "{%s}%s" % (ns, local_name):
            return hijo
    return None


def _hijos_directos(padre, local_name, ns):
    tag = "{%s}%s" % (ns, local_name)
    return [h for h in padre if isinstance(h.tag, str) and h.tag == tag]


def _sumar_impuestos_concepto(conceptos, tag_name):
    """Fallback: suma los Importe a nivel concepto cuando faltan los globales."""
    total = 0.0
    for concepto in conceptos:
        imp = _hijo_directo(concepto, "Impuestos", CFDI_NS)
        if imp is None:
            continue
        # El contenedor (Traslados/Retenciones) es hijo directo de <Impuestos>
        for nodo in imp.iter("{%s}%s" % (CFDI_NS, tag_name)):
            try:
                total += float(nodo.get("Importe") or 0)
            except ValueError:
                pass
    return round(total, 2)


def _num(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def extraer(ruta):
    """Lee un CFDI 4.0 y devuelve el dict del contrato. Lanza CFDIError."""
    nombre = os.path.basename(ruta)
    try:
        arbol = etree.parse(ruta, _PARSER)
    except etree.XMLSyntaxError:
        raise CFDIError("El archivo XML está mal formado o corrupto.")

    comprobante = arbol.getroot()
    if comprobante.tag == "{%s}Comprobante" % CFDI33_NS:
        raise CFDIError("CFDI v3.3 no soportado (se requiere v4.0).")
    if comprobante.tag != "{%s}Comprobante" % CFDI_NS:
        raise CFDIError("No es un CFDI válido.")

    emisor = _hijo_directo(comprobante, "Emisor", CFDI_NS)
    receptor = _hijo_directo(comprobante, "Receptor", CFDI_NS)
    nodo_conceptos = _hijo_directo(comprobante, "Conceptos", CFDI_NS)
    conceptos = _hijos_directos(nodo_conceptos, "Concepto", CFDI_NS) if nodo_conceptos is not None else []

    timbres = list(comprobante.iter("{%s}TimbreFiscalDigital" % TFD_NS))
    uuid = timbres[0].get("UUID") if timbres else None

    # Impuestos: los totales globales mandan; si faltan, se suman los conceptos.
    globales = _hijo_directo(comprobante, "Impuestos", CFDI_NS)
    if globales is not None and globales.get("TotalImpuestosTrasladados"):
        trasladados = _num(globales.get("TotalImpuestosTrasladados"))
    else:
        trasladados = _sumar_impuestos_concepto(conceptos, "Traslado")
    if globales is not None and globales.get("TotalImpuestosRetenidos"):
        retenidos = _num(globales.get("TotalImpuestosRetenidos"))
    else:
        retenidos = _sumar_impuestos_concepto(conceptos, "Retencion")

    # Una fila por factura: las descripciones se aplanan en un solo string.
    descripciones = [c.get("Descripcion") for c in conceptos if c.get("Descripcion")]
    concepto = ", ".join(descripciones)

    uso_code = receptor.get("UsoCFDI") if receptor is not None else None

    return {
        "archivo": nombre,
        "uuid": uuid or "Sin Timbre",
        "fecha": (comprobante.get("Fecha") or "").split("T")[0] or "Sin fecha",
        "emisor": (emisor.get("Nombre") if emisor is not None else None) or "Sin nombre",
        "rfc": (emisor.get("Rfc") if emisor is not None else None) or "Sin RFC",
        "receptor": (receptor.get("Nombre") if receptor is not None else None) or "Sin nombre",
        "rfc_receptor": (receptor.get("Rfc") if receptor is not None else None) or "Sin RFC",
        "tipo_comprobante": cat.etiqueta_tipo(comprobante.get("TipoDeComprobante")),
        "concepto": concepto or "Sin conceptos",
        "subtotal": _num(comprobante.get("SubTotal")),
        # Opcional en el CFDI: si no viene, es 0. Sin este campo el Excel no
        # cuadra en facturas con descuento.
        "descuento": _num(comprobante.get("Descuento")),
        "importe": _num(comprobante.get("Total")),
        "impuestos_trasladados": trasladados,
        "impuestos_retenidos": retenidos,
        "moneda": comprobante.get("Moneda") or "MXN",
        "metodo_pago": comprobante.get("MetodoPago") or "No especificado",
        "forma_pago": cat.etiqueta_forma_pago(comprobante.get("FormaPago")),
        "uso_cfdi": cat.etiqueta_uso_cfdi(uso_code),
        "categoria": cat.etiqueta_categoria(cat.categorizar(uso_code, concepto)),
        # Sin timbre no hay CFDI válido ante el SAT: se conserva la fila, marcada.
        "estado": "OK" if uuid else "Sin Timbre",
        "_origen": "XML",
        "_confianza": "alta",
        "_ruta": os.path.abspath(ruta),
    }


def main():
    p = argparse.ArgumentParser(description="CFDI 4.0 XML -> JSON")
    p.add_argument("ruta", help="archivo .xml o carpeta")
    p.add_argument("--glob", action="store_true", help="procesar todos los .xml de la carpeta")
    args = p.parse_args()

    if args.glob or os.path.isdir(args.ruta):
        rutas = sorted(os.path.join(args.ruta, f) for f in os.listdir(args.ruta)
                       if f.lower().endswith(".xml"))
    else:
        rutas = [args.ruta]

    salida = []
    for r in rutas:
        try:
            salida.append(extraer(r))
        except CFDIError as e:
            salida.append({
                "archivo": os.path.basename(r), "uuid": None, "estado": str(e),
                "_origen": "XML", "_confianza": "error", "_ruta": os.path.abspath(r),
            })
    json.dump(salida if len(rutas) > 1 else salida[0], sys.stdout,
              ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
