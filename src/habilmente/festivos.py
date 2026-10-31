"""Festivos nacionales de Colombia calculados a partir de sus reglas legales.

Las reglas provienen de la Ley 51 de 1983 (Ley Emiliani): seis festivos se
celebran siempre en su fecha, siete se trasladan al lunes siguiente cuando no
caen en lunes, y cinco dependen del Domingo de Pascua (dos de ellos fijos y tres
trasladables). La Ley 2578 de 2026 agrega desde 2026 el 9 de julio, también
trasladable. No hay tablas de fechas quemadas: todo se calcula para cada año.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from functools import cache

from habilmente._validacion import AÑO_MINIMO, normalizar_fecha, validar_año
from habilmente.pascua import _calcular_pascua


class TipoFestivo(StrEnum):
    """Regla legal que determina la fecha de un festivo."""

    FIJO = "fijo"
    """Se celebra siempre en su fecha, aunque caiga en domingo."""

    TRASLADABLE = "trasladable"
    """Fecha de calendario que se traslada al lunes siguiente (Ley Emiliani)."""

    SEMANA_SANTA = "semana_santa"
    """Depende de la Pascua y no se traslada (Jueves y Viernes Santo)."""

    PASCUA_TRASLADABLE = "pascua_trasladable"
    """Depende de la Pascua y se traslada al lunes siguiente."""


@dataclass(frozen=True, slots=True, order=True)
class Festivo:
    """Un festivo nacional ya ubicado en su fecha de descanso.

    Attributes:
        fecha: Día de descanso, ya trasladado si la ley lo exige.
        nombre: Nombre de la celebración.
        tipo: Regla legal que se aplicó.
        fecha_original: Fecha de la celebración antes de cualquier traslado.
    """

    fecha: date
    nombre: str
    tipo: TipoFestivo
    fecha_original: date

    @property
    def trasladado(self) -> bool:
        """Indica si el festivo se movió de su fecha original al lunes."""
        return self.fecha != self.fecha_original


_FIJOS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Año Nuevo"),
    (5, 1, "Día del Trabajo"),
    (7, 20, "Día de la Independencia"),
    (8, 7, "Batalla de Boyacá"),
    (12, 8, "Inmaculada Concepción"),
    (12, 25, "Navidad"),
)

# (mes, día, nombre, primer año en que rige).
_TRASLADABLES: tuple[tuple[int, int, str, int], ...] = (
    (1, 6, "Día de los Reyes Magos", AÑO_MINIMO),
    (3, 19, "Día de San José", AÑO_MINIMO),
    (6, 29, "San Pedro y San Pablo", AÑO_MINIMO),
    # Ley 2578 del 1 de junio de 2026.
    (7, 9, "Nuestra Señora del Rosario de Chiquinquirá", 2026),
    (8, 15, "Asunción de la Virgen", AÑO_MINIMO),
    # Conocido históricamente como "Día de la Raza" (Resolución 0138 de 2021, MinCultura).
    (10, 12, "Día de la Diversidad Étnica y Cultural", AÑO_MINIMO),
    (11, 1, "Día de Todos los Santos", AÑO_MINIMO),
    (11, 11, "Independencia de Cartagena", AÑO_MINIMO),
)

# Días de diferencia respecto al Domingo de Pascua.
_SEMANA_SANTA: tuple[tuple[int, str], ...] = (
    (-3, "Jueves Santo"),
    (-2, "Viernes Santo"),
)

_PASCUA_TRASLADABLES: tuple[tuple[int, str], ...] = (
    (39, "Ascensión del Señor"),
    (60, "Corpus Christi"),
    (68, "Sagrado Corazón de Jesús"),
)


def _al_lunes_siguiente(fecha: date) -> date:
    """Devuelve la misma fecha si es lunes; si no, el lunes siguiente."""
    return fecha + timedelta(days=-fecha.weekday() % 7)


@cache  # El rango de años es acotado, así que la caché también.
def _festivos_del_año(año: int) -> tuple[Festivo, ...]:
    pascua = _calcular_pascua(año)
    lista: list[Festivo] = []

    for mes, dia, nombre in _FIJOS:
        fecha = date(año, mes, dia)
        lista.append(Festivo(fecha, nombre, TipoFestivo.FIJO, fecha))

    for mes, dia, nombre, desde in _TRASLADABLES:
        if año < desde:
            continue
        original = date(año, mes, dia)
        lista.append(
            Festivo(_al_lunes_siguiente(original), nombre, TipoFestivo.TRASLADABLE, original)
        )

    for desfase, nombre in _SEMANA_SANTA:
        fecha = pascua + timedelta(days=desfase)
        lista.append(Festivo(fecha, nombre, TipoFestivo.SEMANA_SANTA, fecha))

    for desfase, nombre in _PASCUA_TRASLADABLES:
        original = pascua + timedelta(days=desfase)
        lista.append(
            Festivo(_al_lunes_siguiente(original), nombre, TipoFestivo.PASCUA_TRASLADABLE, original)
        )

    return tuple(sorted(lista))


@cache
def _fechas_del_año(año: int) -> frozenset[date]:
    return frozenset(festivo.fecha for festivo in _festivos_del_año(año))


def festivos(año: int, /) -> tuple[Festivo, ...]:
    """Lista los festivos nacionales del año, ordenados por fecha.

    Son 18 hasta 2025 y 19 desde 2026 (Ley 2578 de 2026).

    Si dos celebraciones caen el mismo día (como el 30 de junio de 2025, San Pedro
    y Sagrado Corazón), ambas aparecen; por eso puede haber menos días distintos
    que celebraciones. Para obtener solo los días use :func:`fechas_festivas`.

    Args:
        año: Año entre 1984 y 2199.

    Returns:
        Tupla inmutable de :class:`Festivo`.

    Raises:
        TypeError: Si ``año`` no es un entero.
        ValueError: Si ``año`` está fuera del rango soportado.

    Example:
        >>> festivos(2026)[0]
        Festivo(fecha=datetime.date(2026, 1, 1), nombre='Año Nuevo', ...)
    """
    return _festivos_del_año(validar_año(año))


def fechas_festivas(año: int, /) -> frozenset[date]:
    """Devuelve el conjunto de días festivos del año, sin repetidos.

    Args:
        año: Año entre 1984 y 2199.

    Returns:
        Conjunto inmutable de fechas.

    Raises:
        TypeError: Si ``año`` no es un entero.
        ValueError: Si ``año`` está fuera del rango soportado.
    """
    return _fechas_del_año(validar_año(año))


def es_festivo(fecha: date, /) -> bool:
    """Indica si la fecha es festivo nacional en Colombia.

    Los domingos no se consideran festivos aquí; para saber si un día se trabaja
    use :func:`habilmente.es_dia_habil`.

    Args:
        fecha: ``date`` o ``datetime`` (de este último se usa solo la fecha).

    Returns:
        ``True`` si es festivo.

    Raises:
        TypeError: Si ``fecha`` no es ``date`` ni ``datetime``.
        ValueError: Si el año está fuera del rango soportado.

    Example:
        >>> from datetime import date
        >>> es_festivo(date(2025, 6, 30))
        True
    """
    dia = normalizar_fecha(fecha)
    return dia in _fechas_del_año(validar_año(dia.year))


def nombre_festivo(fecha: date, /) -> str | None:
    """Devuelve el nombre del festivo de esa fecha, o ``None`` si no es festivo.

    Si coinciden dos celebraciones, se unen con " / ".

    Args:
        fecha: ``date`` o ``datetime`` (de este último se usa solo la fecha).

    Returns:
        El nombre del festivo o ``None``.

    Raises:
        TypeError: Si ``fecha`` no es ``date`` ni ``datetime``.
        ValueError: Si el año está fuera del rango soportado.

    Example:
        >>> from datetime import date
        >>> nombre_festivo(date(2025, 6, 30))
        'Sagrado Corazón de Jesús / San Pedro y San Pablo'
    """
    dia = normalizar_fecha(fecha)
    nombres = [f.nombre for f in _festivos_del_año(validar_año(dia.year)) if f.fecha == dia]
    return " / ".join(nombres) if nombres else None
