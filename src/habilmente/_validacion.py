"""Validación y normalización de las entradas públicas de la librería."""

from __future__ import annotations

from datetime import date, datetime

AÑO_MINIMO = 1984
"""Primer año soportado: la Ley 51 de 1983 (Ley Emiliani) rige desde 1984."""

AÑO_MAXIMO = 2100
"""Último año soportado: hasta aquí cada año se contrasta con una implementación independiente."""


def validar_año(año: object) -> int:
    """Comprueba que ``año`` sea un entero dentro del rango soportado.

    Args:
        año: Valor recibido por la función pública.

    Returns:
        El mismo año, ya validado.

    Raises:
        TypeError: Si no es un ``int`` (``bool`` tampoco se acepta).
        ValueError: Si está fuera de ``AÑO_MINIMO``..``AÑO_MAXIMO``.
    """
    if isinstance(año, bool) or not isinstance(año, int):
        raise TypeError(f"El año debe ser un entero; se recibió {type(año).__name__}.")
    if not AÑO_MINIMO <= año <= AÑO_MAXIMO:
        raise ValueError(
            f"Año fuera de rango: {año}. Se soportan años entre {AÑO_MINIMO} y {AÑO_MAXIMO}."
        )
    return año


def normalizar_fecha(fecha: object) -> date:
    """Convierte la entrada en un ``datetime.date`` puro.

    Acepta ``date`` y ``datetime`` (incluye subclases como ``pandas.Timestamp``);
    de un ``datetime`` se toma solo la fecha, sin convertir zonas horarias.

    Args:
        fecha: Valor recibido por la función pública.

    Returns:
        La fecha como ``datetime.date``.

    Raises:
        TypeError: Si no es ``date`` ni ``datetime``. Los textos no se interpretan
            para evitar ambigüedades de formato (``01/02`` puede ser enero o febrero).
    """
    if isinstance(fecha, datetime):
        return fecha.date()
    if isinstance(fecha, date):
        return date(fecha.year, fecha.month, fecha.day)
    raise TypeError(
        f"Se esperaba datetime.date o datetime.datetime; se recibió {type(fecha).__name__}."
    )
