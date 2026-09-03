#!/usr/bin/env python3
"""Recorre una carpeta de facturas y actualiza el Excel.

Reparte el trabajo:
  - XML -> automatico de punta a punta, sin intervencion del modelo.
  - PDF o imagen sin XML -> extrae el texto (OCR si hace falta) y lo deja
    listo para que el agente saque los campos. El script NO los adivina.

El XML siempre gana sobre su PDF: es el documento fiscal, el PDF es su
representacion impresa.

Uso:
    python procesar.py carpeta/ --excel salida.xlsx
    python procesar.py carpeta/ --excel salida.xlsx --pendientes pend.json
"""
import argparse
import json
import os
import sys

import cfdi_xml
import excel_merge
import pdf_texto


def emparejar(carpeta, recursivo=True):
    """Devuelve (xmls, huerfanos) agrupando por nombre base.

    Huerfano = documento sin su XML al lado: un PDF, o una imagen suelta
    (factura fotografiada o escaneada). Si el XML existe, gana siempre.

    Recorre subcarpetas por defecto: la gente organiza las facturas por ano
    (entrantes/2025/, entrantes/2026/) y apuntar a la carpeta padre tiene que
    funcionar. Con recursivo=False se queda en un solo nivel.

    El emparejamiento es POR CARPETA, no global: dos archivos que se llamen
    igual en anos distintos (2025/A100.xml y 2026/A100.pdf) son facturas
    distintas y no deben emparejarse entre si.
    """
    bases = {}
    if recursivo:
        recorrido = os.walk(carpeta)
    else:
        recorrido = [(carpeta, [], os.listdir(carpeta))]

    for raiz_dir, _, archivos in recorrido:
        for nombre in sorted(archivos):
            raiz, ext = os.path.splitext(nombre)
            ext = ext.lower()
            if ext == ".xml" or ext == ".pdf" or ext in pdf_texto.EXT_IMAGEN:
                clave = (raiz_dir, raiz)
                bases.setdefault(clave, {})[ext] = os.path.join(raiz_dir, nombre)

    xmls, huerfanos = [], []
    for v in bases.values():
        if ".xml" in v:
            xmls.append(v[".xml"])
            continue
        # Sin XML: el PDF tiene prioridad sobre la imagen del mismo nombre,
        # porque puede traer capa de texto y evitar el OCR.
        otros = ([v[e] for e in (".pdf",) if e in v]
                 or [v[e] for e in pdf_texto.EXT_IMAGEN if e in v])
        if otros:
            huerfanos.append(otros[0])
    return sorted(xmls), sorted(huerfanos)


def main():
    p = argparse.ArgumentParser(description="Facturas (XML/PDF) -> Excel acumulativo")
    p.add_argument("carpeta")
    p.add_argument("--excel", required=True)
    p.add_argument("--pendientes", default=None,
                   help="donde escribir el texto de los documentos sin XML "
                        "(default: <excel>.pendientes.json)")
    p.add_argument("--actualizar", action="store_true")
    p.add_argument("--forzar-ocr", action="store_true")
    p.add_argument("--sin-recursion", action="store_true",
                   help="no entrar a subcarpetas (por defecto si entra)")
    args = p.parse_args()

    if not os.path.isdir(args.carpeta):
        print("ERROR: no es una carpeta: %s" % args.carpeta, file=sys.stderr)
        sys.exit(2)

    xmls, huerfanos = emparejar(args.carpeta, recursivo=not args.sin_recursion)

    # --- Ruta XML: determinista, sin el modelo ---
    filas, errores = [], []
    for ruta in xmls:
        try:
            filas.append(cfdi_xml.extraer(ruta))
        except cfdi_xml.CFDIError as e:
            errores.append({"archivo": os.path.basename(ruta), "error": str(e)})

    # Sin filas XML igual se fusiona la lista vacia: asi el resumen reporta
    # el total real que ya vive en el Excel, no un cero enganoso.
    resumen = excel_merge.fusionar(args.excel, filas, args.actualizar)

    # --- Ruta PDF/imagen: extraer texto y parar. El agente completa campos. ---
    pendientes = []
    for ruta in huerfanos:
        try:
            texto, meta = pdf_texto.extraer_texto(ruta, args.forzar_ocr)
            pendientes.append({
                "archivo": os.path.basename(ruta),
                # Con barras normales aunque estemos en Windows: el agente
                # copia este valor a un JSON que escribe a mano, y una ruta
                # con "\" produce escapes invalidos que rompen el parseo.
                "_ruta": os.path.abspath(ruta).replace(os.sep, "/"),
                "metodo": meta["metodo"], "texto": texto,
            })
        except pdf_texto.SinTextoError as e:
            errores.append({"archivo": os.path.basename(ruta), "error": str(e)})

    destino_pend = args.pendientes or (os.path.splitext(args.excel)[0] + ".pendientes.json")
    if pendientes:
        with open(destino_pend, "w", encoding="utf-8") as f:
            json.dump(pendientes, f, ensure_ascii=False, indent=2)

    resumen.update({
        "xml_encontrados": len(xmls),
        "pdf_sin_xml": len(huerfanos),
        "pendientes_archivo": destino_pend if pendientes else None,
        "errores": errores,
    })
    json.dump(resumen, sys.stdout, ensure_ascii=False, indent=2)
    print()

    if pendientes:
        print("\n%d PDF sin XML. El texto quedo en:\n  %s\n"
              "Lee ese archivo, extrae los campos de cada factura y pasalos a:\n"
              "  python excel_merge.py %s --json -"
              % (len(pendientes), destino_pend, args.excel), file=sys.stderr)


if __name__ == "__main__":
    main()
