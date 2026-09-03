#!/usr/bin/env python3
"""Revisa que este todo lo que la skill necesita, y dice como arreglarlo.

Nada de esto se instala solo: Tesseract es un binario del sistema y los
paquetes de idioma son archivos de datos, ninguno entra por pip. Este script
existe para que quien instale la skill se entere de lo que falta ANTES de
procesar facturas, y no a media carpeta.

Uso:
    python diagnostico.py
    python diagnostico.py --instalar-spa    # descarga spa.traineddata
"""
import argparse
import os
import shutil
import sys

# Unico punto del proyecto que toca la red, y solo si se pide explicitamente.
URL_SPA = "https://github.com/tesseract-ocr/tessdata/raw/main/spa.traineddata"

OK, AVISO, FALTA = "OK", "AVISO", "FALTA"
_resultados = []


def reportar(nombre, estado, detalle=""):
    _resultados.append((nombre, estado, detalle))
    print("  %-34s %-6s %s" % (nombre, estado, detalle))


def revisar_python():
    print("\nDependencias de Python")
    obligatorias = [("lxml", "parseo de CFDI"), ("openpyxl", "escritura del Excel")]
    opcionales = [
        ("pdf_inspector", "clasificacion y texto posicionado de PDF"),
        ("pdfplumber", "respaldo de lectura de PDF"),
        ("pypdfium2", "render de paginas para OCR"),
        ("pytesseract", "puente a Tesseract"),
        ("PIL", "lectura de imagenes sueltas"),
    ]
    for mod, para in obligatorias:
        try:
            __import__(mod)
            reportar(mod, OK, para)
        except ImportError:
            reportar(mod, FALTA, "pip install -r requirements.txt")
    for mod, para in opcionales:
        try:
            __import__(mod)
            reportar(mod, OK, para)
        except ImportError:
            reportar(mod, AVISO, "sin esto: %s no disponible" % para)


def carpeta_tessdata(binario):
    """tessdata vive junto al ejecutable en la instalacion de Windows."""
    entorno = os.environ.get("TESSDATA_PREFIX")
    if entorno and os.path.isdir(entorno):
        return entorno
    candidata = os.path.join(os.path.dirname(binario), "tessdata")
    return candidata if os.path.isdir(candidata) else None


def revisar_ocr():
    print("\nOCR (solo para PDFs escaneados e imagenes)")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pdf_texto

    binario = pdf_texto.ruta_tesseract()
    if not binario:
        reportar("tesseract", FALTA,
                 "winget install UB-Mannheim.TesseractOCR")
        print("\n  Sin Tesseract, un PDF escaneado o una imagen no tienen ruta.")
        print("  Las facturas con XML o con capa de texto funcionan igual.")
        return None
    reportar("tesseract", OK, binario)
    if not shutil.which("tesseract"):
        reportar("tesseract en PATH", AVISO,
                 "no esta, pero se localiza igual; no hace falta arreglarlo")

    idiomas = pdf_texto.idiomas_ocr()
    if idiomas == "spa+eng":
        reportar("idioma espanol (spa)", OK, idiomas)
    else:
        reportar("idioma espanol (spa)", AVISO,
                 "solo 'eng'; corre --instalar-spa")
    return binario


def _se_puede_escribir(carpeta):
    """Prueba real de escritura. os.access miente en Windows."""
    prueba = os.path.join(carpeta, ".facturalm-escritura")
    try:
        with open(prueba, "w"):
            pass
        os.remove(prueba)
        return True
    except OSError:
        return False


def instalar_spa(binario):
    """Descarga spa.traineddata al tessdata de esta instalacion."""
    if not binario:
        print("No hay Tesseract instalado; instala eso primero.")
        return 1
    destino_dir = carpeta_tessdata(binario)
    if not destino_dir:
        print("No encontre la carpeta tessdata junto a %s" % binario)
        print("Define TESSDATA_PREFIX y vuelve a intentar.")
        return 1

    # Si Tesseract se instalo en Program Files, su tessdata no se puede
    # escribir sin elevacion. En vez de fallar (o de pedir que corras esto
    # como administrador) se usa un tessdata propio dentro de la skill.
    if not _se_puede_escribir(destino_dir):
        propio = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "tessdata")
        propio = os.path.normpath(propio)
        print("Sin permiso de escritura en %s" % destino_dir)
        print("Uso un tessdata propio: %s" % propio)
        os.makedirs(propio, exist_ok=True)
        # TESSDATA_PREFIX reemplaza la carpeta entera, no la suma: si el
        # tessdata propio solo tuviera spa, se perderia eng y "spa+eng"
        # fallaria. Se copian los idiomas que ya estaban.
        import glob
        for origen in glob.glob(os.path.join(destino_dir, "*.traineddata")):
            copia = os.path.join(propio, os.path.basename(origen))
            if not os.path.exists(copia):
                shutil.copy2(origen, copia)
                print("  copiado %s" % os.path.basename(origen))
        destino_dir = propio

    destino = os.path.join(destino_dir, "spa.traineddata")
    if os.path.exists(destino):
        print("Ya existe: %s" % destino)
        return 0

    import urllib.request
    print("Descargando spa.traineddata (~18 MB)...")
    tmp = destino + ".tmp"
    try:
        urllib.request.urlretrieve(URL_SPA, tmp)
        # Descarga a .tmp y renombra: si se corta a medias, no queda un
        # traineddata truncado que Tesseract intente cargar.
        if os.path.getsize(tmp) < 1_000_000:
            os.remove(tmp)
            print("La descarga salio incompleta. Reintenta.")
            return 1
        os.replace(tmp, destino)
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        print("Fallo la descarga: %s" % e)
        print("Alternativa: bajalo a mano de %s" % URL_SPA)
        print("y dejalo en %s" % destino_dir)
        return 1
    print("Listo: %s" % destino)
    return 0


def instalar_tesseract():
    """Instala Tesseract con winget. Cambia el sistema del usuario."""
    if not shutil.which("winget"):
        print("winget no esta disponible. Instala Tesseract a mano:")
        print("  https://github.com/UB-Mannheim/tesseract/wiki")
        return 1
    import subprocess
    print("Instalando Tesseract con winget...")
    r = subprocess.run(
        ["winget", "install", "--id", "UB-Mannheim.TesseractOCR",
         "--accept-package-agreements", "--accept-source-agreements"])
    if r.returncode != 0:
        print("winget devolvio %d. Instala a mano si el problema persiste."
              % r.returncode)
        return 1
    return 0


def main():
    p = argparse.ArgumentParser(description="Revisa el entorno de la skill")
    p.add_argument("--instalar-spa", action="store_true",
                   help="descarga el paquete de idioma espanol para Tesseract")
    p.add_argument("--instalar-tesseract", action="store_true",
                   help="instala Tesseract con winget (Windows). Modifica el "
                        "sistema: pide autorizacion al usuario antes de usarlo")
    args = p.parse_args()

    print("Diagnostico de facturalm")
    revisar_python()
    binario = revisar_ocr()

    if args.instalar_tesseract:
        print()
        codigo = instalar_tesseract()
        if codigo == 0:
            # winget instala en silencio y eso se salta la pantalla de
            # idiomas: siempre queda solo 'eng'. Encadenar el espanol es
            # parte de la instalacion, no un extra.
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import pdf_texto
            print()
            return instalar_spa(pdf_texto.ruta_tesseract())
        return codigo

    if args.instalar_spa:
        print()
        return instalar_spa(binario)

    faltantes = [n for n, e, _ in _resultados if e == FALTA]
    avisos = [n for n, e, _ in _resultados if e == AVISO]
    print()
    if faltantes:
        print("Falta lo obligatorio: %s" % ", ".join(faltantes))
        return 1
    if avisos:
        print("Todo lo obligatorio esta. Con avisos en: %s" % ", ".join(avisos))
        return 0
    print("Todo listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
