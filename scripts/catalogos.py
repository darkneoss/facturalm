"""Catálogos del SAT y clasificación de deducciones.

Portado de ExtFact, la app web de la que nace esta skill (no incluida en el
repositorio), para que el Excel que se produce aqui sea comparable columna por
columna con el que ella genera en el navegador.
"""
import unicodedata

# Encabezados del Excel, en el orden exacto de buildExportRows() de ExtFact
COLUMNAS = [
    "Archivo", "UUID", "Fecha", "Emisor", "RFC", "Nombre Receptor",
    "RFC Receptor", "Tipo de Comprobante", "Concepto", "Subtotal", "Descuento", "Importe",
    "Impuestos Trasladados", "Impuestos Retenidos", "Moneda", "Método de Pago",
    "Forma de Pago", "Uso CFDI", "Categoría", "Estado",
]

# Claves del contrato JSON, alineadas 1:1 con COLUMNAS
CLAVES = [
    "archivo", "uuid", "fecha", "emisor", "rfc", "receptor", "rfc_receptor",
    "tipo_comprobante", "concepto", "subtotal", "descuento", "importe",
    "impuestos_trasladados", "impuestos_retenidos", "moneda", "metodo_pago",
    "forma_pago", "uso_cfdi", "categoria", "estado",
]

# Columnas de montos que llevan formato #,##0.00.
# "Descuento" no existe en ExtFact: se agrego porque sin el, el Excel no cuadra
# (Subtotal - Descuento + Trasladados - Retenidos = Total).
COLUMNAS_NUMERICAS = ("Subtotal", "Descuento", "Importe",
                      "Impuestos Trasladados", "Impuestos Retenidos")

# Columnas de control, en una sección aparte a la derecha del esquema ExtFact
COLUMNAS_CONTROL = ["_origen", "_confianza", "_ruta"]

FORMAS_PAGO = {
    "01": "Efectivo", "02": "Cheque nominativo",
    "03": "Transferencia electrónica de fondos", "04": "Tarjeta de crédito",
    "05": "Monedero electrónico", "06": "Dinero electrónico",
    "08": "Vale de despensa", "12": "Dación en pago",
    "13": "Pago por subrogación", "14": "Pago por consignación",
    "15": "Condonación", "17": "Compensación", "23": "Novación",
    "24": "Confusión", "25": "Remisión de deuda",
    "26": "Prescripción o caducidad", "27": "A satisfacción del acreedor",
    "28": "Tarjeta de débito", "29": "Tarjeta de servicios",
    "30": "Aplicación de anticipos", "31": "Intermediario de pagos",
    "99": "Por definir",
}

USOS_CFDI = {
    "G01": "Adquisición de mercancías",
    "G02": "Devoluciones, descuentos o bonificaciones",
    "G03": "Gastos en general",
    "I01": "Construcciones",
    "I02": "Mobilario y equipo de oficina por inversiones",
    "I03": "Equipo de transporte",
    "I04": "Equipo de computo y accesorios",
    "I05": "Dados, troqueles, moldes, matrices y herramental",
    "I06": "Comunicaciones telefónicas",
    "I07": "Comunicaciones satelitales",
    "I08": "Otra maquinaria y equipo",
    "D01": "Honorarios médicos, dentales y gastos hospitalarios",
    "D02": "Gastos médicos por incapacidad o discapacidad",
    "D03": "Gastos funerales",
    "D04": "Donativos",
    "D05": "Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación)",
    "D06": "Aportaciones voluntarias al SAR",
    "D07": "Primas por seguros de gastos médicos",
    "D08": "Gastos de transportación escolar obligatoria",
    "D09": "Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones",
    "D10": "Pagos por servicios educativos (colegiaturas)",
    "P01": "Por definir",
    "CP01": "Pagos",
    "CN01": "Nómina",
    "S01": "Sin efectos fiscales",
}

TIPOS_COMPROBANTE = {
    "I": "Ingreso", "E": "Egreso", "P": "Pago", "N": "Nómina", "T": "Traslado",
}

USO_CATEGORY = {
    "D01": "salud", "D02": "salud", "D03": "funerarios", "D04": "donativos",
    "D05": "hipotecario", "D06": "retiro", "D07": "seguros_medicos",
    "D08": "transporte_escolar", "D09": "ahorro", "D10": "educacion",
    "I01": "inversiones", "I02": "inversiones", "I03": "inversiones",
    "I04": "inversiones", "I05": "inversiones", "I06": "inversiones",
    "I07": "inversiones", "I08": "inversiones",
    "G02": "devoluciones", "CN01": "nomina",
}

# Orden = prioridad. Términos ya normalizados (minúsculas, sin acentos).
CONCEPT_RULES = [
    ("combustible", ["gasolina", "diesel", "combustible", "magna", "premium"]),
    ("alimentos", ["restaurant", "aliment", "comida", "cafeteria", "consumo de"]),
    ("hospedaje", ["hospedaje", "hotel"]),
    ("transporte", ["taxi", "uber", "didi", "caseta", "peaje", "estacionamiento",
                    "boleto", "vuelo", "autobus", "transporte"]),
    ("papeleria", ["papeleria", "material de oficina", "articulos de oficina",
                   "toner", "tinta", "libreta", "didactico"]),
    ("tecnologia", ["computad", "laptop", "software", "licencia", "monitor",
                    "impresora", "hosting", "dominio"]),
    ("salud", ["consulta", "medic", "dental", "hospital", "laboratorio",
               "medicament", "farmacia", "clinic", "analisis", "radiografia"]),
    ("educacion", ["colegiatura", "inscripcion", "escuela", "curso",
                   "capacitacion", "universidad", "ensenanza", "diplomado"]),
    ("servicios", ["honorari", "asesoria", "consultoria", "mantenimiento",
                   "reparacion", "servicio"]),
]

CATEGORIAS = {
    "salud": "Salud", "funerarios": "Funerarios", "donativos": "Donativos",
    "hipotecario": "Intereses hipotecarios", "retiro": "Retiro / SAR",
    "seguros_medicos": "Seguros médicos", "transporte_escolar": "Transporte escolar",
    "ahorro": "Ahorro / Pensiones", "educacion": "Educación",
    "combustible": "Combustible", "alimentos": "Alimentos",
    "hospedaje": "Hospedaje", "transporte": "Transporte", "papeleria": "Papelería",
    "tecnologia": "Tecnología", "servicios": "Servicios", "mercancias": "Mercancías",
    "devoluciones": "Devoluciones", "inversiones": "Inversiones", "nomina": "Nómina",
    "otros": "Otros",
}


def normalizar(s):
    """Minúsculas sin acentos, para comparar conceptos."""
    s = (s or "").lower()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def categorizar(uso_cfdi_code, concepto):
    """Clasifica la deducción. Uso CFDI manda; el concepto es el desempate."""
    # 1) Uso CFDI autoritativo (D01-D10 son justo las deducciones personales)
    if uso_cfdi_code and uso_cfdi_code in USO_CATEGORY:
        return USO_CATEGORY[uso_cfdi_code]
    # 2) Palabras clave del concepto
    c = normalizar(concepto)
    if c:
        for cat, terms in CONCEPT_RULES:
            if any(term in c for term in terms):
                return cat
    # 3) Fallback por Uso CFDI genérico
    if uso_cfdi_code == "G01":
        return "mercancias"
    if uso_cfdi_code == "G03":
        return "servicios"
    return "otros"


def etiqueta_forma_pago(code):
    if not code:
        return "No especificada"
    return FORMAS_PAGO.get(code, "Código: %s" % code)


def etiqueta_uso_cfdi(code):
    if not code:
        return "No especificado"
    return USOS_CFDI.get(code, "Código: %s" % code)


def etiqueta_tipo(code):
    if not code:
        return "No especificado"
    return TIPOS_COMPROBANTE.get(code, code)


def etiqueta_categoria(cat):
    return CATEGORIAS.get(cat, "Sin clasificar")


# ==========================================================================
# Validacion de RFC
# ==========================================================================

_RFC_VALORES = {}
for _i, _c in enumerate("0123456789"):
    _RFC_VALORES[_c] = _i
for _i, _c in enumerate("ABCDEFGHIJKLMN"):
    _RFC_VALORES[_c] = 10 + _i
_RFC_VALORES["&"] = 24
for _i, _c in enumerate("OPQRSTUVWXYZ"):
    _RFC_VALORES[_c] = 25 + _i
_RFC_VALORES[" "] = 37
_RFC_VALORES["\u00d1"] = 38

# El SAT exceptua sus RFC genericos del digito verificador.
RFC_GENERICOS = {"XAXX010101000", "XEXX010101000"}


def rfc_valido(rfc):
    """Comprueba el digito verificador del RFC.

    Existe por un error real de OCR: la 'Z' de la homoclave se leyo como '2'
    y el dato se reporto como legible. Un RFC mal leido no solo ensucia el
    Excel: como las filas sin UUID se deduplican por rfc|fecha|importe,
    tambien rompe la clave y permite que la misma factura entre dos veces.

    Ejemplo con el RFC de pruebas del SAT: EKU9003173C9 es valido y
    EKU9003173C8 no.

    Devuelve True/False, o None si el valor no tiene forma de RFC (vacio,
    marcadores como 'Sin RFC') y por tanto no hay nada que validar.
    """
    if not rfc:
        return None
    r = str(rfc).upper().strip()
    if r in RFC_GENERICOS:
        return True
    if len(r) not in (12, 13):
        return None
    relleno = (" " + r) if len(r) == 12 else r
    suma = 0
    for i, c in enumerate(relleno[:12]):
        if c not in _RFC_VALORES:
            return None
        suma += _RFC_VALORES[c] * (13 - i)
    resto = suma % 11
    if resto == 0:
        esperado = "0"
    elif resto == 1:
        esperado = "A"
    else:
        esperado = str(11 - resto)
    return relleno[12] == esperado
