"""Cálculo del Domingo de Pascua en el calendario gregoriano."""

from __future__ import annotations

from datetime import date
from functools import cache

from habilmente._validacion import validar_año


@cache
def _calcular_pascua(año: int) -> date:
    # Algoritmo anónimo gregoriano (Meeus/Jones/Butcher), exacto para cualquier
    # año gregoriano. Los nombres de una letra siguen la notación original.
    a = año % 19
    b, c = divmod(año, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ajuste_semana = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ajuste_semana) // 451
    mes, dia = divmod(h + ajuste_semana - 7 * m + 114, 31)
    return date(año, mes, dia + 1)


def domingo_de_pascua(año: int, /) -> date:
    """Devuelve el Domingo de Pascua (Resurrección) del año indicado.

    Args:
        año: Año entre 1984 y 2100.

    Returns:
        La fecha del Domingo de Pascua.

    Raises:
        TypeError: Si ``año`` no es un entero.
        ValueError: Si ``año`` está fuera del rango soportado.

    Example:
        >>> domingo_de_pascua(2025)
        datetime.date(2025, 4, 20)
    """
    return _calcular_pascua(validar_año(año))
