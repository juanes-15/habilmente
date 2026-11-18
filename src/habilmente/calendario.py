"""Calendarios laborales configurables y aritmética de días hábiles.

Un día es hábil según estas reglas, en orden de prioridad:

1. Si está en ``dias_habiles_extra``, es hábil (aunque sea festivo o domingo).
2. Si está en ``dias_no_habiles_extra``, no es hábil.
3. Si es festivo nacional, no es hábil.
4. Si es sábado, es hábil solo si la configuración de ``sabados`` lo incluye.
5. De lunes a viernes es hábil; el domingo no.

Para contar se usa la convención de los plazos: "n días hábiles después de una
fecha" empieza a contar desde el día siguiente.

Con ``hora_corte``, algo recibido a esa hora o después (o en un día no hábil) se
entiende recibido el siguiente día hábil: ver :meth:`Calendario.fecha_efectiva` y
:meth:`Calendario.vencimiento`.
"""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from calendar import monthrange
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, tzinfo
from typing import Literal, TypeAlias
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from habilmente._validacion import (
    AÑO_MAXIMO,
    AÑO_MINIMO,
    validar_año,
    validar_entero,
    validar_fecha,
)
from habilmente.festivos import _fechas_del_año, nombre_festivo

ConfigSabados: TypeAlias = Literal["todos"] | Iterable[int] | None
"""Valores aceptados por ``Calendario(sabados=...)``."""

ConfigZona: TypeAlias = tzinfo | str | None
"""Valores aceptados por ``Calendario(zona_horaria=...)``."""

_POSICIONES_SABADO = frozenset({1, 2, 3, 4, 5, -1, -2, -3, -4, -5})
_MAXIMO_FECHAS_EXTRA = 1_000_000
_SABADO = 5
_DOMINGO = 6
_REFERENCIA_UTC = datetime(2000, 1, 1, tzinfo=UTC)
# Nombres IANA como "America/Bogota" o "Etc/GMT+5". Se filtran antes de consultar la base
# de zonas horarias del sistema, aunque zoneinfo también rechaza rutas peligrosas.
_PATRON_ZONA = re.compile(r"[A-Za-z0-9_+\-]{1,30}(?:/[A-Za-z0-9_+\-]{1,30}){0,2}", re.ASCII)


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
    # Se valida elemento por elemento y se corta en el primer problema: así un iterable
    # enorme o infinito no puede bloquear el programa (hay a lo sumo 10 posiciones).
    posiciones: list[int] = []
    for elemento in valor:
        if isinstance(elemento, bool) or not isinstance(elemento, int):
            raise TypeError(
                f"Las posiciones de 'sabados' deben ser enteros; se recibió {elemento!r:.40}."
            )
        posicion = validar_entero(elemento, "sabados")
        if posicion not in _POSICIONES_SABADO:
            raise ValueError(
                f"Posición de sábado inválida: {posicion}. Use 1 a 5 (primero a quinto) "
                "o -1 a -5 (último a quinto contando desde el final)."
                if abs(posicion) < 10**12
                else "Posición de sábado inválida. Use 1 a 5 o -1 a -5."
            )
        if posicion in posiciones:
            raise ValueError(f"Hay posiciones de sábado repetidas: {posicion}.")
        posiciones.append(posicion)
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
    fechas: set[date] = set()
    for cantidad, fecha in enumerate(valor, start=1):
        # Un iterable infinito o desmedido no debe colgar el programa: el rango completo
        # tiene unas 79.000 fechas, así que un millón de elementos ya es un error claro.
        if cantidad > _MAXIMO_FECHAS_EXTRA:
            raise ValueError(
                f"'{nombre}' tiene más de {_MAXIMO_FECHAS_EXTRA:,} elementos; "
                "revise que no sea un iterable infinito."
            )
        fechas.add(validar_fecha(fecha))
    return frozenset(fechas)


def _normalizar_hora_corte(valor: object) -> time | None:
    if valor is None:
        return None
    if not isinstance(valor, time):
        raise TypeError(
            f"'hora_corte' debe ser datetime.time, por ejemplo time(15, 0); "
            f"se recibió {type(valor).__name__}."
        )
    if valor.tzinfo is not None:
        raise ValueError("'hora_corte' no debe tener zona horaria; indíquela con 'zona_horaria'.")
    hora = time(valor.hour, valor.minute, valor.second, valor.microsecond)
    if hora == time(0, 0):
        raise ValueError(
            "'hora_corte' a medianoche haría que todo cuente al día siguiente; "
            "use None si no hay hora de corte."
        )
    return hora


def _normalizar_zona(valor: object) -> tzinfo | None:
    if valor is None:
        return None
    if isinstance(valor, str):
        if not _PATRON_ZONA.fullmatch(valor):
            raise ValueError(
                f'Zona horaria inválida: {valor!r:.50}. Use un nombre IANA como "America/Bogota".'
            )
        try:
            return ZoneInfo(valor)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise ValueError(
                f"Zona horaria desconocida: {valor!r}. Use un nombre IANA como "
                '"America/Bogota" (en Windows puede requerir: pip install tzdata).'
            ) from None
    if not isinstance(valor, tzinfo):
        raise TypeError(
            "'zona_horaria' debe ser un nombre IANA como \"America/Bogota\" o un tzinfo; "
            f"se recibió {type(valor).__name__}."
        )
    # Se prueba una conversión al crear el calendario: un tzinfo defectuoso debe fallar
    # aquí con un mensaje claro, no después en cada cálculo.
    try:
        _REFERENCIA_UTC.astimezone(valor)
    except Exception as error:  # Un tzinfo propio puede lanzar cualquier excepción.
        raise ValueError(
            f"'zona_horaria' no permite convertir horas ({type(error).__name__}); "
            'use un nombre IANA como "America/Bogota" o datetime.timezone.'
        ) from None
    return valor


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
        hora_corte: Hora a partir de la cual algo recibido cuenta como recibido el
            siguiente día hábil, por ejemplo ``time(15, 0)``. Solo la usan
            :meth:`fecha_efectiva` y :meth:`vencimiento`; el resto de funciones solo
            miran la fecha.
        zona_horaria: Zona en la que se interpretan los ``datetime`` con zona
            horaria, como ``"America/Bogota"``. Los ``datetime`` sin zona y las
            fechas se toman tal cual. Sin ella, cada ``datetime`` usa su propia hora
            local.

    Raises:
        TypeError: Si algún parámetro tiene un tipo inválido.
        ValueError: Si una posición de sábado no existe, está repetida, alguna fecha
            está fuera del rango soportado, una fecha aparece en ambas listas extra,
            la hora de corte es medianoche o la zona horaria no existe.

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
    hora_corte: time | None
    zona_horaria: tzinfo | None
    _cache: dict[int, tuple[int, ...]] = field(repr=False, compare=False, hash=False)

    def __init__(
        self,
        *,
        sabados: ConfigSabados = None,
        dias_no_habiles_extra: Iterable[date] | None = None,
        dias_habiles_extra: Iterable[date] | None = None,
        hora_corte: time | None = None,
        zona_horaria: ConfigZona = None,
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
        object.__setattr__(self, "hora_corte", _normalizar_hora_corte(hora_corte))
        object.__setattr__(self, "zona_horaria", _normalizar_zona(zona_horaria))
        object.__setattr__(self, "_cache", {})

    # --- Entradas -----------------------------------------------------------------------

    def _momento(self, valor: object) -> tuple[date, time | None]:
        """Convierte la entrada en (fecha local, hora local o None si es solo fecha)."""
        if not isinstance(valor, datetime):
            return validar_fecha(valor), None
        if self.zona_horaria is not None and valor.utcoffset() is not None:
            # Cerca de los límites de datetime la conversión desborda: se valida antes.
            if not AÑO_MINIMO - 1 <= valor.year <= AÑO_MAXIMO + 1:
                validar_año(valor.year)
            valor = valor.astimezone(self.zona_horaria)
        dia = validar_fecha(valor)
        return dia, time(valor.hour, valor.minute, valor.second, valor.microsecond)

    def _fecha(self, valor: object) -> date:
        if self.zona_horaria is None:
            return validar_fecha(valor)
        return self._momento(valor)[0]

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

    def _clasificar(self, dia: date) -> tuple[bool, str]:
        """Aplica las reglas en orden de prioridad y devuelve (es hábil, motivo)."""
        if dia in self.dias_habiles_extra:
            return True, "día hábil extra del calendario"
        if dia in self.dias_no_habiles_extra:
            return False, "día no hábil extra del calendario"
        if dia in _fechas_del_año(dia.year):
            return False, f"festivo ({nombre_festivo(dia)})"
        dia_semana = dia.weekday()
        if dia_semana == _SABADO:
            if self._es_sabado_habil(dia):
                return True, "sábado hábil según el calendario"
            return False, "sábado"
        if dia_semana == _DOMINGO:
            return False, "domingo"
        return True, "día entre semana"

    def _es_habil(self, dia: date) -> bool:
        return self._clasificar(dia)[0]

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
        return self._es_habil(self._fecha(fecha))

    def explicar_dia(self, fecha: date, /) -> str:
        """Explica en una frase si la fecha es hábil y por qué regla.

        Args:
            fecha: ``date`` o ``datetime`` (de este último se usa solo la fecha).

        Returns:
            Texto como ``"No hábil: festivo (Día de Todos los Santos)"``.

        Raises:
            TypeError: Si ``fecha`` no es ``date`` ni ``datetime``.
            ValueError: Si el año está fuera del rango soportado.

        Example:
            >>> from datetime import date
            >>> Calendario(sabados=[1, -1]).explicar_dia(date(2026, 1, 3))
            'Hábil: sábado hábil según el calendario'
        """
        habil, motivo = self._clasificar(self._fecha(fecha))
        return f"{'Hábil' if habil else 'No hábil'}: {motivo}"

    def sumar_dias_habiles(self, fecha: date, /, n: int) -> date:
        """Avanza (o retrocede, si ``n`` es negativo) ``n`` días hábiles.

        La fecha de partida no cuenta: con ``n=1`` se obtiene el primer día hábil
        posterior, aunque la fecha de partida sea hábil. Con ``n=0`` se devuelve la
        misma fecha si es hábil o, si no, el siguiente día hábil.

        No aplica ``hora_corte``: para plazos que dependen de la hora de recepción use
        :meth:`vencimiento`.

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
        dia = self._fecha(fecha)
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
        :meth:`listar_dias_habiles`. No aplica ``hora_corte``; si las fechas tienen
        hora, cuente entre sus :meth:`fecha_efectiva`.

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
        a, b = self._fecha(inicio), self._fecha(fin)
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
        a, b = self._fecha(inicio), self._fecha(fin)
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
            año: Año entre 1984 y 2199.
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
            año: Año entre 1984 y 2199.
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

    # --- Horario de corte ---------------------------------------------------------------

    def fecha_efectiva(self, momento: date, /) -> date:
        """Devuelve el día hábil en que se entiende recibido algo.

        Es el mismo día si este es hábil y llegó antes de ``hora_corte``; si llegó
        a la hora de corte o después, o en un día no hábil, es el siguiente día
        hábil. Una ``date`` sin hora cuenta como recibida antes del corte.

        Args:
            momento: ``datetime`` (con o sin zona horaria) o ``date``.

        Returns:
            La fecha efectiva de recepción.

        Raises:
            TypeError: Si ``momento`` no es ``date`` ni ``datetime``.
            ValueError: Si la fecha o el resultado salen del rango soportado.

        Example:
            >>> from datetime import datetime, time
            >>> cal = Calendario(hora_corte=time(15, 0))
            >>> cal.fecha_efectiva(datetime(2026, 11, 13, 14, 59))  # Viernes, antes del corte.
            datetime.date(2026, 11, 13)
            >>> cal.fecha_efectiva(datetime(2026, 11, 13, 15, 0))  # El lunes 16 es festivo.
            datetime.date(2026, 11, 17)
        """
        dia, hora = self._momento(momento)
        a_tiempo = self.hora_corte is None or hora is None or hora < self.hora_corte
        if a_tiempo and self._es_habil(dia):
            return dia
        return self.sumar_dias_habiles(dia, 1)

    def vencimiento(self, momento: date, /, n: int) -> date:
        """Fecha en que vence un plazo de ``n`` días hábiles para algo recibido en ``momento``.

        Primero se obtiene la :meth:`fecha_efectiva` (aplica la hora de corte y corre
        al siguiente día hábil lo recibido en días no hábiles) y desde ahí se cuentan
        ``n`` días hábiles sin incluirla.

        Args:
            momento: ``datetime`` (con o sin zona horaria) o ``date`` de recepción.
            n: Días hábiles del plazo; ``0`` devuelve la fecha efectiva.

        Returns:
            La fecha de vencimiento.

        Raises:
            TypeError: Si ``momento`` o ``n`` tienen un tipo inválido.
            ValueError: Si ``n`` es negativo o el resultado sale del rango soportado.

        Example:
            >>> from datetime import datetime, time
            >>> cal = Calendario(hora_corte=time(15, 0))
            >>> cal.vencimiento(datetime(2026, 11, 13, 16, 30), 5)  # Cuenta desde el martes 17.
            datetime.date(2026, 11, 24)
        """
        pasos = validar_entero(n, "n")
        if pasos < 0:
            raise ValueError(f"'n' no puede ser negativo en un plazo; se recibió {pasos}.")
        return self.sumar_dias_habiles(self.fecha_efectiva(momento), pasos)


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


def explicar_dia(fecha: date, /) -> str:
    """Explica si la fecha es hábil y por qué (ver :meth:`Calendario.explicar_dia`)."""
    return CALENDARIO_ESTANDAR.explicar_dia(fecha)


def fecha_efectiva(momento: date, /) -> date:
    """Día hábil en que se entiende recibido algo (ver :meth:`Calendario.fecha_efectiva`).

    El calendario estándar no tiene hora de corte: lo recibido en un día no hábil
    cuenta desde el siguiente día hábil.
    """
    return CALENDARIO_ESTANDAR.fecha_efectiva(momento)


def vencimiento(momento: date, /, n: int) -> date:
    """Vencimiento de un plazo de ``n`` días hábiles (ver :meth:`Calendario.vencimiento`)."""
    return CALENDARIO_ESTANDAR.vencimiento(momento, n)


__all__ = [
    "CALENDARIO_ESTANDAR",
    "Calendario",
    "ConfigSabados",
    "ConfigZona",
    "anterior_dia_habil",
    "dia_habil_del_mes",
    "dias_habiles_del_mes",
    "dias_habiles_entre",
    "es_dia_habil",
    "explicar_dia",
    "fecha_efectiva",
    "listar_dias_habiles",
    "siguiente_dia_habil",
    "sumar_dias_habiles",
    "vencimiento",
]
