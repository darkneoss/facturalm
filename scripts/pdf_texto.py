#!/usr/bin/env python3
"""PDF o imagen -> texto plano, para que un modelo SIN VISION pueda leerlo.

Usa pdf-inspector (Rust via PyO3) para dos cosas distintas:

  1. Clasificar: pdf_type, confidence, pages_needing_ocr y ocr_reasons_by_page
     dicen con precision si la capa de texto basta o hace falta OCR.
  2. Extraer con posiciones: extract_text_with_positions() da TextItems con
     x/y/ancho/fuente, y de ahi se reconstruyen los renglones.

Por que reconstruir en vez de usar r.markdown: el markdown colapsa la factura
en ~9 lineas (pierde el salto de renglon) y extract_text() pierde uno de los
dos RFC. La reconstruccion por posiciones conserva la estructura de renglon,
que es lo que un modelo necesita para leer etiqueta:valor.

Pero las posiciones no siempre ganan. En facturas reales rompen los acentos
(la 'e' acentuada sale como U+00D8, la 'o'/'i' desaparecen) sin que el
clasificador lo reporte, y ahi pdfplumber lee bien. Por eso no hay un orden
fijo: se comparan y gana el que conserve mas acentos. Ver acentos_rotos().

Tesseract es el ultimo recurso, para PDFs escaneados e imagenes sueltas.

Nunca devuelve imagenes. El contrato es documento -> str.
"""
import argparse
import json
import os
import re
import shutil
import sys

try:
    import pdf_inspector as _pi
except ImportError:
    _pi = None


# Formatos de imagen que Tesseract lee directo. Una factura fotografiada o
# escaneada a JPG no tiene capa de texto: va derecho a OCR.
EXT_IMAGEN = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp")


class SinTextoError(Exception):
    """El documento necesita OCR y no hay motor disponible."""


def clasificar(ruta):
    """Veredicto de pdf-inspector, o None si no esta instalado."""
    if _pi is None:
        return None
    try:
        r = _pi.process_pdf(ruta)
    except Exception:
        return None
    return {
        "pdf_type": r.pdf_type,
        "confidence": r.confidence,
        "pages_needing_ocr": list(r.pages_needing_ocr or []),
        "ocr_reasons_by_page": [str(x) for x in (r.ocr_reasons_by_page or [])],
        "has_encoding_issues": bool(r.has_encoding_issues),
        "is_complex_layout": bool(r.is_complex_layout),
        "pages_with_tables": list(r.pages_with_tables or []),
        "page_count": r.page_count,
    }


def texto_por_posiciones(ruta, tol_y=2.0, factor_espacio=0.25):
    """Reconstruye renglones a partir de los TextItem posicionados.

    Agrupa por coordenada Y (con tolerancia: los glifos de un mismo renglon no
    comparten Y exacto), ordena por X, e inserta un espacio cuando el hueco
    entre dos items supera una fraccion del tamano de fuente. Sin esa regla los
    tokens quedan pegados y un RFC deja de ser reconocible.
    """
    if _pi is None:
        return None
    try:
        items = _pi.extract_text_with_positions(ruta)
    except Exception:
        return None
    if not items:
        return None

    renglones = []
    for it in sorted(items, key=lambda i: (i.page, round(i.y, 1), i.x)):
        if renglones and renglones[-1][0] == it.page and abs(renglones[-1][1] - it.y) <= tol_y:
            renglones[-1][2].append(it)
        else:
            renglones.append([it.page, it.y, [it]])

    salida = []
    for _, _, its in renglones:
        its.sort(key=lambda i: i.x)
        linea, previo = "", None
        for i in its:
            if previo is not None:
                hueco = i.x - (previo.x + previo.width)
                if hueco > factor_espacio * max(previo.font_size, 1):
                    linea += " "
            linea += i.text
            previo = i
        salida.append(linea)
    texto = "\n".join(salida).strip()
    return texto or None


def capa_de_texto_es_basura(texto):
    """Detecta capas de texto que existen pero son ilegibles.

    Portado de textLayerLooksUnreliable() de OCRExtracTesseract, la otra app
    web de origen (no incluida en el repositorio).
    El sintoma es OCR previo malo ("T e m p e r a t u r a s") o texto rotado:
    rachas largas de tokens de una sola letra. Umbral 0.08 sobre tokens
    alfabeticos, minimo 50 tokens para no juzgar documentos muy cortos.
    """
    tokens = [t for t in re.split(r"\s+", texto or "") if t]
    alfabeticos = [t for t in tokens if re.search(r"[^\W\d_]", t, re.UNICODE)]
    if len(alfabeticos) < 50:
        return False
    en_rachas = racha = 0
    for t in alfabeticos:
        if len(t) == 1:
            racha += 1
        else:
            if racha >= 4:
                en_rachas += racha
            racha = 0
    if racha >= 4:
        en_rachas += racha
    return (en_rachas / len(alfabeticos)) > 0.08


def texto_pdfplumber(ruta):
    """Lectura con pdfplumber. Respaldo, y arbitro cuando hay acentos rotos."""
    try:
        import pdfplumber
    except ImportError:
        return None
    try:
        with pdfplumber.open(ruta) as pdf:
            texto = "\n".join((p.extract_text() or "") for p in pdf.pages).strip()
    except Exception:
        return None
    return texto or None


def _acentos(texto):
    return len(re.findall(r"[áéíóúüñÁÉÍÓÚÜÑ]", texto or ""))


def acentos_rotos(texto):
    """Sintoma de mapeo de fuente roto en un texto en espanol.

    Visto en facturas reales: la 'e' acentuada sale como 'O' con barra
    (U+00D8) y la 'o'/'i' acentuadas desaparecen ("exhibicion" pierde la
    letra). El clasificador de pdf-inspector reporta has_encoding_issues
    False en estos casos, asi que hay que detectarlo aparte.
    """
    if not texto:
        return False
    # U+00D8 no aparece en espanol; en medio de una palabra es una 'e' rota.
    if re.search(r"[a-zA-Z]Ø[a-zA-Z]", texto):
        return True
    # Texto largo en espanol sin un solo acento es sospechoso de por si.
    letras = len(re.findall(r"[^\W\d_]", texto, re.UNICODE))
    return letras > 400 and _acentos(texto) == 0


# El instalador de Windows no suele agregar Tesseract al PATH, asi que
# buscarlo solo con which() lo daria por ausente estando instalado.
_CANDIDATOS_TESSERACT = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""),
                 "Programs", "Tesseract-OCR", "tesseract.exe"),
)


def ruta_tesseract():
    """Devuelve la ruta al binario, o None. Respeta $TESSERACT_CMD."""
    explicita = os.environ.get("TESSERACT_CMD")
    if explicita and os.path.isfile(explicita):
        return explicita
    encontrada = shutil.which("tesseract")
    if encontrada:
        return encontrada
    for c in _CANDIDATOS_TESSERACT:
        if c and os.path.isfile(c):
            return c
    return None


def _exigir_tesseract():
    """Tesseract es un binario del sistema, no un paquete de Python."""
    ruta = ruta_tesseract()
    if not ruta:
        raise SinTextoError(
            """Este documento necesita OCR y Tesseract no esta instalado.
  Windows: winget install UB-Mannheim.TesseractOCR
  Luego:   pip install pytesseract pillow
  Marca el idioma espanol (spa) durante la instalacion.
  Si ya lo instalaste, apunta TESSERACT_CMD al .exe."""
        )
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = ruta
    return ruta


def idiomas_ocr():
    """'spa+eng' si el paquete de espanol esta instalado; si no, 'eng'.

    Sin este chequeo, pedir 'spa' en una instalacion que solo trae 'eng'
    aborta el OCR con un error de Tesseract en vez de degradar.
    """
    try:
        import pytesseract
        # Fijar el binario ANTES de preguntar: si Tesseract no esta en el PATH
        # (lo normal en Windows), pytesseract falla y degradariamos a 'eng'
        # aunque el paquete de espanol si este instalado.
        ruta = ruta_tesseract()
        if not ruta:
            return "eng"
        pytesseract.pytesseract.tesseract_cmd = ruta
        disponibles = set(pytesseract.get_languages(config=""))
    except Exception:
        return "eng"
    if "spa" in disponibles:
        return "spa+eng"
    return "eng"


def texto_ocr_imagen(ruta):
    """OCR de una imagen suelta: factura fotografiada o escaneada a JPG/PNG.

    Una imagen no tiene capa de texto que rescatar, asi que aqui no hay
    clasificacion previa ni respaldo: es OCR o nada.
    """
    _exigir_tesseract()
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise SinTextoError(
            "Falta dependencia de OCR: %s (pip install pytesseract pillow)" % e)
    with Image.open(ruta) as img:
        return pytesseract.image_to_string(img, lang=idiomas_ocr()).strip()


def texto_ocr(ruta, escala=3.0):
    """OCR local de un PDF. No sale de la maquina, no usa vision.

    Medido sobre una factura real (1 pagina): a escala 2.0 recupera 1 de los
    2 RFC; a 3.0 recupera los dos, y tarda lo mismo (1.8s). Mas alla de 3.0
    no mejora y si cuesta tiempo. El UUID no se recupera a ninguna escala: es
    letra chica y una cadena hex larga. Por eso las filas que vienen de OCR
    suelen quedarse sin UUID y usan la clave sustituta de excel_merge.
    """
    _exigir_tesseract()
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError as e:
        raise SinTextoError(
            "Falta dependencia de OCR: %s (pip install pytesseract pypdfium2)" % e)

    salida = []
    pdf = pdfium.PdfDocument(ruta)
    try:
        for i in range(len(pdf)):
            salida.append(pytesseract.image_to_string(
                pdf[i].render(scale=escala).to_pil(), lang=idiomas_ocr()))
    finally:
        pdf.close()   # liberar: cientos de MB si se acumulan
    return "\n".join(salida).strip()



def extraer_texto(ruta, forzar_ocr=False):
    """Devuelve (texto, meta). Lanza SinTextoError si no hay ruta viable."""
    meta = {"archivo": os.path.basename(ruta), "metodo": None, "clasificacion": None}

    # Una imagen no tiene capa de texto ni se puede clasificar: OCR directo.
    if ruta.lower().endswith(EXT_IMAGEN):
        meta["metodo"] = "ocr-imagen"
        return texto_ocr_imagen(ruta), meta

    if forzar_ocr:
        meta["metodo"] = "ocr-forzado"
        return texto_ocr(ruta), meta

    veredicto = clasificar(ruta)
    meta["clasificacion"] = veredicto

    # El clasificador manda sobre si hace falta OCR. Mismas guardas que
    # las de tryNativePdfExtract() en OCRExtracTesseract.
    necesita_ocr = bool(veredicto) and (
        veredicto["pdf_type"] != "text_based"
        or veredicto["pages_needing_ocr"]
        or veredicto["has_encoding_issues"]
        or veredicto["confidence"] < 0.7
    )

    if not necesita_ocr:
        pos = texto_por_posiciones(ruta)
        if pos and capa_de_texto_es_basura(pos):
            pos = None

        # Las posiciones dan mejor estructura de renglon, pero en algunas
        # facturas reales rompen los acentos (la 'e' acentuada sale como Ø y
        # la 'o'/'i' acentuadas se pierden) sin que el clasificador lo note.
        # Cuando eso pasa, pdfplumber lee bien y gana: un "Metodo de pago"
        # legible vale mas que diez renglones extra.
        if pos is None or acentos_rotos(pos):
            plu = texto_pdfplumber(ruta)
            if plu and not capa_de_texto_es_basura(plu):
                if pos is None or _acentos(plu) > _acentos(pos):
                    meta["metodo"] = "pdfplumber"
                    return plu, meta

        if pos:
            meta["metodo"] = "posiciones"
            return pos, meta

    meta["metodo"] = "ocr"
    return texto_ocr(ruta), meta


def main():
    p = argparse.ArgumentParser(description="PDF -> texto plano (sin vision)")
    p.add_argument("pdf", help="archivo .pdf o imagen (.jpg, .png, ...)")
    p.add_argument("--forzar-ocr", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        texto, meta = extraer_texto(args.pdf, args.forzar_ocr)
    except SinTextoError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        sys.exit(2)

    if args.json:
        json.dump({**meta, "texto": texto}, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print("# %s (metodo: %s)" % (meta["archivo"], meta["metodo"]))
        print(texto)


if __name__ == "__main__":
    main()
