"""Implementación ingenua (día por día) usada como referencia en las pruebas.

Es deliberadamente lenta y distinta a la de la librería: la posición del sábado se
obtiene listando los sábados del mes en vez de con aritmética, y las sumas recorren
el calendario un día a la vez sin cachés ni búsquedas binarias.
"""

from __future__ import annotations

from datetime import date, timedelta

from habilmente import AÑO_MAXIMO, AÑO_MINIMO, Calendario, fechas_festivas

UN_DIA = timedelta(days=1)
PRIMER_DIA = date(AÑO_MINIMO, 1, 1)
ULTIMO_DIA = date(AÑO_MAXIMO, 12, 31)


def _posiciones_del_sabado(dia: date) -> tuple[int, int]:
    sabados = []
    actual = dia.replace(day=1)
    while actual.month == dia.month:
        if actual.weekday() == 5:
            sabados.append(actual)
        actual += UN_DIA
    indice = sabados.index(dia)
    return indice + 1, indice - len(sabados)


def es_habil(cal: Calendario, dia: date) -> bool:
    if dia in cal.dias_habiles_extra:
        return True
    if dia in cal.dias_no_habiles_extra or dia in fechas_festivas(dia.year):
        return False
    if dia.weekday() == 6:
        return False
    if dia.weekday() == 5:
        if cal.sabados is None:
            return False
        if cal.sabados == "todos":
            return True
        return any(p in cal.sabados for p in _posiciones_del_sabado(dia))
    return True


def sumar(cal: Calendario, dia: date, n: int) -> date:
    """Lanza ValueError si se sale del rango, igual que la librería."""
    if n == 0:
        return dia if es_habil(cal, dia) else sumar(cal, dia, 1)
    paso = UN_DIA if n > 0 else -UN_DIA
    restantes = abs(n)
    actual = dia
    while restantes:
        actual += paso
        if not PRIMER_DIA <= actual <= ULTIMO_DIA:
            raise ValueError("fuera de rango")
        if es_habil(cal, actual):
            restantes -= 1
    return actual


def entre(cal: Calendario, a: date, b: date) -> int:
    if a > b:
        return -entre(cal, b, a)
    total = 0
    actual = a + UN_DIA
    while actual <= b:
        total += es_habil(cal, actual)
        actual += UN_DIA
    return total
