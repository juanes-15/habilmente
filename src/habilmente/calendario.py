"""Calendarios laborales configurables y aritmética de días hábiles.

Un día es hábil según estas reglas, en orden de prioridad:

1. Si está en ``dias_habiles_extra``, es hábil (aunque sea festivo o domingo).
2. Si está en ``dias_no_habiles_extra``, no es hábil.
3. Si es festivo nacional, no es hábil.
4. Si es sábado, es hábil solo si la configuración de ``sabados`` lo incluye.
5. De lunes a viernes es hábil; el domingo no.

Para contar se usa la convención de los plazos: "n días hábiles después de una
fecha" empieza a contar desde el día siguiente.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from calendar import monthrange
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, TypeAlias

from habilmente._validacion import (
    AÑO_MAXIMO,
    AÑO_MINIMO,
    validar_año,
    validar_entero,
    validar_fecha,
)
from habilmente.festivos import _fechas_del_año

ConfigSabados: TypeAlias = Literal["todos"] | Iterable[int] | None
"""Valores aceptados por ``Calendario(sabados=...)``."""

_POSICIONES_SABADO = frozenset({1, 2, 3, 4, 5, -1, -2, -3, -4, -5})
_SABADO = 5
_DOMINGO = 6


def _normalizar_sabados(valor: object) -> Literal["todos"] | tuple[int, ...] | None:
    if valor is None:
        return None
    if isinstance(valor, str):
        if valor == "todos":
            return "todos"
        raise ValueError(
            f"'sabados' solo acepta el texto \"todos\"; se recibió {valor!r}. "
            "Para sábados específicos use posiciones, por ejemplo [1, -1]."
        )
    if not isinstance(valor, Iterable):
        raise TypeError(
            "'sabados' debe ser None, \"todos\" o una lista de posiciones como [1, -1]; "
            f"se recibió {type(valor).__name__}."
        )
    posiciones = list(valor)
    for posicion in posiciones:
        if isinstance(posicion, bool) or not isinstance(posicion, int):
            raise TypeError(
                f"Las posiciones de 'sabados' deben ser enteros; se recibió {posicion!r}."
            )
        if posicion not in _POSICIONES_SABADO:
            raise ValueError(
                f"Posición de sábado inválida: {posicion}. Use 1 a 5 (primero a quinto) "
                "o -1 a -5 (último a quinto contando desde el final)."
            )
    if len(set(posiciones)) != len(posiciones):
        raise ValueError(f"Hay posiciones de sábado repetidas: {posiciones}.")
    if not posiciones:
        return None
    # Primero las positivas en orden y luego las negativas (-1, -2, ...), como se leen.
    return tuple(sorted(posiciones, key=lambda p: (p < 0, abs(p))))


def _normalizar_fechas(valor: object, nombre: str) -> frozenset[date]:
    if valor is None:
        return frozenset()
    if isinstance(valor, (str, bytes, date)) or not isinstance(valor, Iterable):
        raise TypeError(
            f"'{nombre}' debe ser una colección de fechas (lista, tupla o conjunto); "
            f"se recibió {type(valor).__name__}."
        )
    return frozenset(validar_fecha(fecha) for fecha in valor)


@dataclass(frozen=True, slots=True, init=False)
class Calendario:
    """Calendario laboral colombiano configurable e inmutable.

    Args:
        sabados: Qué sábados son hábiles. ``None`` (por defecto): ninguno.
            ``"todos"``: todos. Una colección de posiciones dentro del mes:
            ``1`` a ``5`` cuentan desde el inicio y ``-1`` a ``-5`` desde el final;
            ``[1, -1]`` significa el primer y el último sábado de cada mes. Si ese
            sábado es festivo no se trabaja y la regla no se corre a otro sábado.
        dias_no_habiles_extra: Fechas que no se trabajan además de los festivos,
            por ejemplo cierres de la empresa.
        dias_habiles_extra: Fechas que sí se trabajan aunque sean festivo o fin de
            semana. Tienen la máxima prioridad.

    Raises:
        TypeError: Si algún parámetro tiene un tipo inválido.
        ValueError: Si una posición de sábado no existe, está repetida, alguna fecha
            está fuera del rango soportado o una fecha aparece en ambas listas extra.

    Example:
        >>> from datetime import date
        >>> cal = Calendario(sabados=[1, -1])
        >>> cal.es_dia_habil(date(2026, 1, 3))  # Primer sábado de enero.
        True
        >>> cal.es_dia_habil(date(2026, 1, 10))  # Segundo sábado.
        False
    """

    sabados: Literal["todos"] | tuple[int, ...] | None
    dias_no_habiles_extra: frozenset[date]
    dias_habiles_extra: frozenset[date]
    _cache: dict[int, tuple[int, ...]] = field(repr=False, compare=False, hash=False)

    def __init__(
        self,
        *,
        sabados: ConfigSabados = None,
        dias_no_habiles_extra: Iterable[date] | None = None,
        dias_habiles_extra: Iterable[date] | None = None,
    ) -> None:
        """Valida y normaliza la configuración (ver la documentación de la clase)."""
        no_habiles = _normalizar_fechas(dias_no_habiles_extra, "dias_no_habiles_extra")
        habiles = _normalizar_fechas(dias_habiles_extra, "dias_habiles_extra")
        en_ambas = sorted(no_habiles & habiles)
        if en_ambas:
            muestra = ", ".join(f.isoformat() for f in en_ambas[:5])
            raise ValueError(
                f"Estas fechas están a la vez en dias_habiles_extra y dias_no_habiles_extra: "
                f"{muestra}."
            )
        object.__setattr__(self, "sabados", _normalizar_sabados(sabados))
        object.__setattr__(self, "dias_no_habiles_extra", no_habiles)
        object.__setattr__(self, "dias_habiles_extra", habiles)
        object.__setattr__(self, "_cache", {})

    # --- Reglas -----------------------------------------------------------------------

    def _es_sabado_habil(self, dia: date) -> bool:
        if self.sabados is None:
            return False
        if self.sabados == "todos":
            return True
        ultimo_dia = monthrange(dia.year, dia.month)[1]
        desde_inicio = (dia.day - 1) // 7 + 1
        desde_final = -((ultimo_dia - dia.day) // 7 + 1)
        return desde_inicio in self.sabados or desde_final in self.sabados

    def _es_habil(self, dia: date) -> bool:
        if dia in self.dias_habiles_extra:
            return True
        if dia in self.dias_no_habiles_extra or dia in _fechas_del_año(dia.year):
            return False
        dia_semana = dia.weekday()
        if dia_semana == _SABADO:
            return self._es_sabado_habil(dia)
        return dia_semana != _DOMINGO

    def _habiles_del_año(self, año: int) -> tuple[int, ...]:
        """Ordinales de los días hábiles del año, ordenados (se calculan una sola vez)."""
        habiles = self._cache.get(año)
        if habiles is None:
            inicio = date(año, 1, 1).toordinal()
            fin = date(año, 12, 31).toordinal()
            habiles = tuple(
                o for o in range(inicio, fin + 1) if self._es_habil(date.fromordinal(o))
            )
            self._cache[año] = habiles
        return habiles

    def _habiles_hasta(self, dia: date) -> int:
        """Cantidad de días hábiles del año de ``dia`` que son menores o iguales a él."""
        return bisect_right(self._habiles_del_año(dia.year), dia.toordinal())

    # --- Consultas ----------------------------------------------------------------------

    def es_dia_habil(self, fecha: date, /) -> bool:
        """Indica si la fecha es hábil en este calendario.

        Args:
            fecha: ``date`` o ``datetime`` (de este último se usa solo la fecha).

        Returns:
            ``True`` si es día hábil.

        Raises:
            TypeError: Si ``fecha`` no es ``date`` ni ``datetime``.
            ValueError: Si el año está fuera del rango soportado.
        """
        return self._es_habil(validar_fecha(fecha))

    def sumar_dias_habiles(self, fecha: date, /, n: int) -> date:
        """Avanza (o retrocede, si ``n`` es negativo) ``n`` días hábiles.

        La fecha de partida no cuenta: con ``n=1`` se obtiene el primer día hábil
        posterior, aunque la fecha de partida sea hábil. Con ``n=0`` se devuelve la
        misma fecha si es hábil o, si no, el siguiente día hábil.

        Args:
            fecha: Fecha de partida.
            n: Cantidad de días hábiles; puede ser negativa.

        Returns:
            La fecha hábil resultante.

        Raises:
            TypeError: Si ``fecha`` o ``n`` tienen un tipo inválido.
            ValueError: Si la fecha o el resultado salen del rango soportado.

        Example:
            >>> from datetime import date
            >>> sumar_dias_habiles(date(2026, 1, 9), 1)  # Viernes; el lunes 12 es Reyes.
            datetime.date(2026, 1, 13)
        """
        dia = validar_fecha(fecha)
        pasos = validar_entero(n, "n")
        if pasos == 0:
            return dia if self._es_habil(dia) else self.sumar_dias_habiles(dia, 1)

        año = dia.year
        habiles = self._habiles_del_año(año)
        if pasos > 0:
            indice = bisect_right(habiles, dia.toordinal())  # Primer hábil posterior.
            while pasos > len(habiles) - indice:
                pasos -= len(habiles) - indice
                año = self._año_siguiente(año, +1)
                habiles, indice = self._habiles_del_año(año), 0
            return date.fromordinal(habiles[indice + pasos - 1])

        pasos = -pasos
        indice = bisect_left(habiles, dia.toordinal())  # Hábiles anteriores en el año.
        while pasos > indice:
            pasos -= indice
            año = self._año_siguiente(año, -1)
            habiles = self._habiles_del_año(año)
            indice = len(habiles)
        return date.fromordinal(habiles[indice - pasos])

    @staticmethod
    def _año_siguiente(año: int, direccion: int) -> int:
        nuevo = año + direccion
        if not AÑO_MINIMO <= nuevo <= AÑO_MAXIMO:
            raise ValueError(
                f"El resultado queda fuera del rango soportado ({AÑO_MINIMO}-{AÑO_MAXIMO})."
            )
        return nuevo

    def siguiente_dia_habil(self, fecha: date, /) -> date:
        """Devuelve el primer día hábil estrictamente posterior a la fecha.

        Args:
            fecha: Fecha de referencia.

        Returns:
            El siguiente día hábil.

        Raises:
            TypeError: Si ``fecha`` no es ``date`` ni ``datetime``.
            ValueError: Si la fecha o el resultado salen del rango soportado.
        """
        return self.sumar_dias_habiles(fecha, 1)

    def anterior_dia_habil(self, fecha: date, /) -> date:
        """Devuelve el último día hábil estrictamente anterior a la fecha.

        Args:
            fecha: Fecha de referencia.

        Returns:
            El día hábil anterior.

        Raises:
            TypeError: Si ``fecha`` no es ``date`` ni ``datetime``.
            ValueError: Si la fecha o el resultado salen del rango soportado.
        """
        return self.sumar_dias_habiles(fecha, -1)

    def dias_habiles_entre(self, inicio: date, fin: date, /) -> int:
        """Cuenta los días hábiles después de ``inicio`` y hasta ``fin`` (incluido).

        Es la operación inversa de :meth:`sumar_dias_habiles`: si
        ``sumar_dias_habiles(a, n) == b`` con ``n > 0``, entonces
        ``dias_habiles_entre(a, b) == n``. Si ``inicio`` es posterior a ``fin`` el
        resultado es negativo, y se cumple ``entre(a, b) + entre(b, c) == entre(a, c)``.
        Para listar los días de un rango con ambos extremos incluidos use
        :meth:`listar_dias_habiles`.

        Args:
            inicio: Fecha de inicio (no se cuenta).
            fin: Fecha final (se cuenta si es hábil).

        Returns:
            Cantidad de días hábiles, con signo.

        Raises:
            TypeError: Si alguna fecha tiene un tipo inválido.
            ValueError: Si alguna fecha está fuera del rango soportado.

        Example:
            >>> from datetime import date
            >>> dias_habiles_entre(date(2026, 10, 9), date(2026, 10, 16))  # El 12 es festivo.
            4
        """
        a, b = validar_fecha(inicio), validar_fecha(fin)
        if a > b:
            return -self._contar(b, a)
        return self._contar(a, b)

    def _contar(self, a: date, b: date) -> int:
        """Días hábiles en el intervalo (a, b], con a <= b."""
        total = self._habiles_hasta(b) - self._habiles_hasta(a)
        for año in range(a.year, b.year):
            total += len(self._habiles_del_año(año))
        return total

    def listar_dias_habiles(self, inicio: date, fin: date, /) -> tuple[date, ...]:
        """Lista los días hábiles entre ``inicio`` y ``fin``, ambos incluidos.

        Args:
            inicio: Primera fecha del rango.
            fin: Última fecha del rango.

        Returns:
            Tupla ordenada de fechas hábiles (vacía si no hay ninguna).

        Raises:
            TypeError: Si alguna fecha tiene un tipo inválido.
            ValueError: Si ``inicio`` es posterior a ``fin`` o están fuera de rango.
        """
        a, b = validar_fecha(inicio), validar_fecha(fin)
        if a > b:
            raise ValueError(f"'inicio' ({a}) no puede ser posterior a 'fin' ({b}).")
        resultado: list[date] = []
        for año in range(a.year, b.year + 1):
            habiles = self._habiles_del_año(año)
            desde = bisect_left(habiles, a.toordinal())
            hasta = bisect_right(habiles, b.toordinal())
            resultado.extend(date.fromordinal(o) for o in habiles[desde:hasta])
        return tuple(resultado)

    def dias_habiles_del_mes(self, año: int, mes: int, /) -> tuple[date, ...]:
        """Lista los días hábiles de un mes.

        Args:
            año: Año entre 1984 y 2100.
            mes: Mes de 1 a 12.

        Returns:
            Tupla ordenada de fechas hábiles.

        Raises:
            TypeError: Si ``año`` o ``mes`` no son enteros.
            ValueError: Si están fuera de rango.

        Example:
            >>> len(dias_habiles_del_mes(2026, 10))
            21
        """
        validar_año(año)
        if not 1 <= validar_entero(mes, "mes") <= 12:
            raise ValueError(f"El mes debe estar entre 1 y 12; se recibió {mes}.")
        return self.listar_dias_habiles(date(año, mes, 1), date(año, mes, monthrange(año, mes)[1]))

    def dia_habil_del_mes(self, año: int, mes: int, n: int, /) -> date:
        """Devuelve el n-ésimo día hábil del mes (``-1`` es el último).

        Útil para fechas de corte como "el quinto día hábil" o "el último día hábil".

        Args:
            año: Año entre 1984 y 2100.
            mes: Mes de 1 a 12.
            n: Posición: ``1`` es el primero, ``-1`` el último, ``-2`` el penúltimo.

        Returns:
            La fecha hábil en esa posición.

        Raises:
            TypeError: Si algún parámetro no es entero.
            ValueError: Si ``n`` es 0 o el mes no tiene tantos días hábiles.

        Example:
            >>> dia_habil_del_mes(2026, 1, 1)  # El 1 de enero es festivo.
            datetime.date(2026, 1, 2)
        """
        posicion = validar_entero(n, "n")
        dias = self.dias_habiles_del_mes(año, mes)
        if posicion == 0 or abs(posicion) > len(dias):
            raise ValueError(
                f"El mes {mes:02d}/{año} tiene {len(dias)} días hábiles; "
                f"'n' debe estar entre 1 y {len(dias)} o entre -{len(dias)} y -1, "
                f"se recibió {posicion}."
            )
        return dias[posicion - 1] if posicion > 0 else dias[posicion]


CALENDARIO_ESTANDAR = Calendario()
"""Calendario de lunes a viernes sin sábados hábiles; lo usan las funciones del módulo."""


def es_dia_habil(fecha: date, /) -> bool:
    """Indica si la fecha es hábil de lunes a viernes (ver :meth:`Calendario.es_dia_habil`).

    Example:
        >>> from datetime import date
        >>> es_dia_habil(date(2026, 12, 25))
        False
    """
    return CALENDARIO_ESTANDAR.es_dia_habil(fecha)


def sumar_dias_habiles(fecha: date, /, n: int) -> date:
    """Suma ``n`` días hábiles (ver :meth:`Calendario.sumar_dias_habiles`)."""
    return CALENDARIO_ESTANDAR.sumar_dias_habiles(fecha, n)


def siguiente_dia_habil(fecha: date, /) -> date:
    """Primer día hábil posterior (ver :meth:`Calendario.siguiente_dia_habil`)."""
    return CALENDARIO_ESTANDAR.siguiente_dia_habil(fecha)


def anterior_dia_habil(fecha: date, /) -> date:
    """Último día hábil anterior (ver :meth:`Calendario.anterior_dia_habil`)."""
    return CALENDARIO_ESTANDAR.anterior_dia_habil(fecha)


def dias_habiles_entre(inicio: date, fin: date, /) -> int:
    """Días hábiles en ``(inicio, fin]`` (ver :meth:`Calendario.dias_habiles_entre`)."""
    return CALENDARIO_ESTANDAR.dias_habiles_entre(inicio, fin)


def listar_dias_habiles(inicio: date, fin: date, /) -> tuple[date, ...]:
    """Días hábiles en ``[inicio, fin]`` (ver :meth:`Calendario.listar_dias_habiles`)."""
    return CALENDARIO_ESTANDAR.listar_dias_habiles(inicio, fin)


def dias_habiles_del_mes(año: int, mes: int, /) -> tuple[date, ...]:
    """Días hábiles del mes (ver :meth:`Calendario.dias_habiles_del_mes`)."""
    return CALENDARIO_ESTANDAR.dias_habiles_del_mes(año, mes)


def dia_habil_del_mes(año: int, mes: int, n: int, /) -> date:
    """N-ésimo día hábil del mes (ver :meth:`Calendario.dia_habil_del_mes`)."""
    return CALENDARIO_ESTANDAR.dia_habil_del_mes(año, mes, n)


__all__ = [
    "CALENDARIO_ESTANDAR",
    "Calendario",
    "ConfigSabados",
    "anterior_dia_habil",
    "dia_habil_del_mes",
    "dias_habiles_del_mes",
    "dias_habiles_entre",
    "es_dia_habil",
    "listar_dias_habiles",
    "siguiente_dia_habil",
    "sumar_dias_habiles",
]
