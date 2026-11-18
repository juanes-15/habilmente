"""Integración con pandas: columnas de días hábiles y tabla calendario para Power BI.

Requiere el extra opcional: ``pip install "habilmente[pandas]"``.

Todas las funciones aceptan columnas ``datetime64`` (con o sin zona horaria) o columnas
``object`` con ``date``/``datetime``. Con zona horaria se usa la fecha local de cada valor,
o la de ``zona_horaria`` si el calendario la define. Los valores
vacíos (``NaT``, ``None``) dan un resultado vacío (``<NA>``) en vez de un error. Cada
fecha distinta se calcula una sola vez, así que millones de filas se procesan rápido.

Con ``errores="coerce"`` las fechas fuera del rango soportado (o cuyo resultado se sale
de él) quedan vacías en lugar de lanzar ``ValueError``.

Example:
    >>> import pandas as pd
    >>> from habilmente.pandas import marcar_dias_habiles
    >>> df = pd.DataFrame({"fecha": pd.to_datetime(["2026-11-02", "2026-11-03"])})
    >>> marcar_dias_habiles(df, "fecha")["es_habil"].tolist()
    [False, True]
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, time, tzinfo
from typing import Any, Literal, TypeVar

try:
    import numpy as np
    import pandas as pd
except ModuleNotFoundError as error:
    raise ModuleNotFoundError(
        'habilmente.pandas necesita pandas. Instálelo con: pip install "habilmente[pandas]"'
    ) from error

from habilmente._textos import DIAS_SEMANA
from habilmente._validacion import (
    AÑO_MAXIMO,
    AÑO_MINIMO,
    validar_entero,
    validar_fecha,
)
from habilmente.calendario import CALENDARIO_ESTANDAR, Calendario
from habilmente.festivos import _fechas_del_año
from habilmente.festivos import nombre_festivo as _nombre_festivo

Errores = Literal["raise", "coerce"]
_T = TypeVar("_T")
_AÑOS_SOPORTADOS = frozenset(range(AÑO_MINIMO, AÑO_MAXIMO + 1))

__all__ = [
    "dias_habiles_entre",
    "es_dia_habil",
    "es_festivo",
    "fecha_efectiva",
    "marcar_dias_habiles",
    "nombre_festivo",
    "sumar_dias_habiles",
    "tabla_calendario",
    "vencimiento",
]


# --- Utilidades internas ------------------------------------------------------------------


def _validar_errores(errores: object) -> Errores:
    if errores == "raise":
        return "raise"
    if errores == "coerce":
        return "coerce"
    raise ValueError(f'\'errores\' debe ser "raise" o "coerce"; se recibió {errores!r}.')


def _validar_calendario(calendario: object) -> Calendario:
    if calendario is None:
        return CALENDARIO_ESTANDAR
    if not isinstance(calendario, Calendario):
        raise TypeError(
            "'calendario' debe ser un habilmente.Calendario; "
            f"se recibió {type(calendario).__name__}."
        )
    return calendario


def _sin_texto(valor: object) -> object:
    if isinstance(valor, str):
        raise TypeError(
            f"La columna contiene texto ({valor!r:.40}); conviértala primero con "
            "pd.to_datetime(...)."
        )
    if isinstance(valor, np.datetime64):
        return pd.Timestamp(valor)
    return valor


def _factorizar(
    serie: object,
    zona: tzinfo | None = None,
    *,
    con_hora: bool = False,
    hora_corte: time | None = None,
) -> tuple[np.ndarray[Any, Any], list[object]]:
    """Códigos por fila (-1 = vacío) y los valores distintos, listos para el calendario.

    En columnas ``datetime64`` los valores salen en hora local (de ``zona`` si se indica)
    y reducidos para no repetir cálculos: a la fecha, o con ``con_hora`` a la fecha más
    "antes o después de ``hora_corte``" (solo eso cambia el resultado). Así hay a lo
    sumo dos valores distintos por día. En columnas ``object`` salen tal cual: el
    calendario los valida y convierte uno por uno.
    """
    if not isinstance(serie, pd.Series):
        raise TypeError(f"Se esperaba una pandas.Series; se recibió {type(serie).__name__}.")
    if pd.api.types.is_datetime64_any_dtype(serie.dtype):
        locales = serie
        if serie.dt.tz is not None:
            if zona is not None:
                locales = locales.dt.tz_convert(zona)
            locales = locales.dt.tz_localize(None)
        dias = locales.dt.normalize()
        if con_hora and hora_corte is not None:
            # Representante de cada grupo: medianoche (antes del corte) o la hora de corte.
            # Unidad explícita: numpy desaprueba la unidad genérica que usan otros caminos.
            segundos = hora_corte.hour * 3600 + hora_corte.minute * 60 + hora_corte.second
            corte = pd.Timedelta(segundos * 1_000_000 + hora_corte.microsecond, unit="us")
            tarde = (locales - dias) >= corte
            dias = dias.where(~tarde, dias + corte)
        codigos, unicos = pd.factorize(dias)
        indice = pd.DatetimeIndex(unicos)
        if con_hora:
            return codigos, [ts.to_pydatetime(warn=False) for ts in indice]
        return codigos, [ts.date() for ts in indice]
    if serie.dtype == object:
        codigos, unicos = pd.factorize(serie)
        return codigos, [_sin_texto(valor) for valor in unicos]
    raise TypeError(
        f"La columna {serie.name!r} tiene tipo {serie.dtype}; se esperaban fechas "
        "(datetime64 o date). Conviértala primero con pd.to_datetime(...)."
    )


def _evaluar(
    valores: Sequence[Any], funcion: Callable[[Any], _T], errores: Errores
) -> list[_T | None]:
    resultados: list[_T | None] = []
    for valor in valores:
        try:
            resultados.append(funcion(valor))
        except ValueError:
            if errores == "raise":
                raise
            resultados.append(None)
    return resultados


def _expandir(
    valores: Sequence[Any], codigos: np.ndarray[Any, Any], dtype: str, serie: pd.Series[Any]
) -> pd.Series[Any]:
    """Reparte los resultados por fecha distinta a cada fila (``<NA>`` donde había vacío)."""
    arreglo: Any
    if dtype == "datetime64":
        arreglo = pd.array(pd.to_datetime(list(valores)))
    else:
        arreglo = pd.array(list(valores), dtype=dtype)  # type: ignore[call-overload]
    filas = pd.api.extensions.take(arreglo, codigos, allow_fill=True)
    return pd.Series(filas, index=serie.index, name=serie.name)


def _aplicar(
    serie: pd.Series[Any],
    funcion: Callable[[Any], object],
    dtype: str,
    errores: Errores,
    zona: tzinfo | None = None,
    *,
    con_hora: bool = False,
    hora_corte: time | None = None,
) -> pd.Series[Any]:
    modo = _validar_errores(errores)
    codigos, unicos = _factorizar(serie, zona, con_hora=con_hora, hora_corte=hora_corte)
    return _expandir(_evaluar(unicos, funcion, modo), codigos, dtype, serie)


def _es_festivo(valor: object) -> bool:
    dia = validar_fecha(valor)
    return dia in _fechas_del_año(dia.year)


# --- Funciones públicas -------------------------------------------------------------------


def es_dia_habil(
    serie: pd.Series[Any],
    calendario: Calendario | None = None,
    *,
    errores: Errores = "raise",
) -> pd.Series[Any]:
    """Marca cada fecha como hábil o no (``boolean`` con ``<NA>`` para vacíos).

    Args:
        serie: Columna de fechas.
        calendario: Calendario laboral; por defecto lunes a viernes.
        errores: ``"raise"`` (por defecto) o ``"coerce"`` para dejar vacías las fechas
            fuera de rango.

    Returns:
        Serie booleana con el mismo índice y nombre.

    Raises:
        TypeError: Si la columna no contiene fechas o el calendario no es válido.
        ValueError: Si hay fechas fuera de rango y ``errores="raise"``.
    """
    cal = _validar_calendario(calendario)
    return _aplicar(serie, cal.es_dia_habil, "boolean", errores, cal.zona_horaria)


def es_festivo(serie: pd.Series[Any], *, errores: Errores = "raise") -> pd.Series[Any]:
    """Marca cada fecha como festivo nacional o no (``boolean`` con ``<NA>`` para vacíos).

    Args:
        serie: Columna de fechas.
        errores: ``"raise"`` o ``"coerce"`` (ver :func:`es_dia_habil`).

    Returns:
        Serie booleana con el mismo índice y nombre.

    Raises:
        TypeError: Si la columna no contiene fechas.
        ValueError: Si hay fechas fuera de rango y ``errores="raise"``.
    """
    return _aplicar(serie, _es_festivo, "boolean", errores)


def nombre_festivo(serie: pd.Series[Any], *, errores: Errores = "raise") -> pd.Series[Any]:
    """Nombre del festivo de cada fecha (``string``; ``<NA>`` si no es festivo o está vacía).

    Args:
        serie: Columna de fechas.
        errores: ``"raise"`` o ``"coerce"`` (ver :func:`es_dia_habil`).

    Returns:
        Serie de texto con el mismo índice y nombre.

    Raises:
        TypeError: Si la columna no contiene fechas.
        ValueError: Si hay fechas fuera de rango y ``errores="raise"``.
    """
    return _aplicar(serie, lambda v: _nombre_festivo(validar_fecha(v)), "string", errores)


def sumar_dias_habiles(
    serie: pd.Series[Any],
    n: int,
    calendario: Calendario | None = None,
    *,
    errores: Errores = "raise",
) -> pd.Series[Any]:
    """Suma ``n`` días hábiles a cada fecha (``datetime64``; ``NaT`` para vacíos).

    Sigue la misma convención que :func:`habilmente.sumar_dias_habiles`.

    Args:
        serie: Columna de fechas.
        n: Días hábiles a sumar; negativo para restar.
        calendario: Calendario laboral; por defecto lunes a viernes.
        errores: ``"raise"`` o ``"coerce"`` (ver :func:`es_dia_habil`).

    Returns:
        Serie de fechas con el mismo índice y nombre.

    Raises:
        TypeError: Si la columna no contiene fechas o ``n`` no es entero.
        ValueError: Si una fecha o su resultado salen del rango y ``errores="raise"``.
    """
    cal = _validar_calendario(calendario)
    validar_entero(n, "n")
    return _aplicar(
        serie, lambda v: cal.sumar_dias_habiles(v, n), "datetime64", errores, cal.zona_horaria
    )


def dias_habiles_entre(
    inicio: pd.Series[Any],
    fin: pd.Series[Any],
    calendario: Calendario | None = None,
    *,
    errores: Errores = "raise",
) -> pd.Series[Any]:
    """Cuenta los días hábiles en ``(inicio, fin]`` fila por fila (``Int64``).

    Ideal para medir tiempos de respuesta o SLA en días hábiles. Sigue la misma
    convención que :func:`habilmente.dias_habiles_entre`; es negativo si ``fin`` es
    anterior a ``inicio`` y vacío si alguna de las dos fechas está vacía.

    Args:
        inicio: Columna de fechas iniciales (no se cuentan).
        fin: Columna de fechas finales (se cuentan si son hábiles).
        calendario: Calendario laboral; por defecto lunes a viernes.
        errores: ``"raise"`` o ``"coerce"`` (ver :func:`es_dia_habil`).

    Returns:
        Serie de enteros con el índice de ``inicio``.

    Raises:
        TypeError: Si alguna columna no contiene fechas.
        ValueError: Si las columnas no tienen el mismo índice, o hay fechas fuera de
            rango y ``errores="raise"``.
    """
    cal = _validar_calendario(calendario)
    modo = _validar_errores(errores)
    codigos_inicio, unicos_inicio = _factorizar(inicio, cal.zona_horaria)
    codigos_fin, unicos_fin = _factorizar(fin, cal.zona_horaria)
    if not inicio.index.equals(fin.index):
        raise ValueError("'inicio' y 'fin' deben tener el mismo índice (las mismas filas).")
    fechas_inicio = _evaluar(unicos_inicio, cal._fecha, modo)
    fechas_fin = _evaluar(unicos_fin, cal._fecha, modo)

    # Con un acumulado de días hábiles hasta cada fecha (incluida), cada fila se resuelve
    # con una resta: entre(a, b) = acumulado(b) - acumulado(a). Los años previos se suman
    # una sola vez desde el primer año presente en los datos.
    años = sorted(
        {f.year for f in (*fechas_inicio, *fechas_fin) if f is not None} & _AÑOS_SOPORTADOS
    )
    previos: dict[int, int] = {}
    total = 0
    for año in range(años[0], años[-1] + 1) if años else ():
        previos[año] = total
        total += len(cal._habiles_del_año(año))

    def acumulado(dia: date | None) -> int | None:
        return None if dia is None else previos[dia.year] + cal._habiles_hasta(dia)

    valores_inicio = [acumulado(dia) for dia in fechas_inicio]
    valores_fin = [acumulado(dia) for dia in fechas_fin]
    a = _expandir(valores_inicio, codigos_inicio, "Int64", inicio)
    b = _expandir(valores_fin, codigos_fin, "Int64", inicio)
    resultado = b - a
    resultado.name = None
    return resultado


def fecha_efectiva(
    serie: pd.Series[Any],
    calendario: Calendario | None = None,
    *,
    errores: Errores = "raise",
) -> pd.Series[Any]:
    """Día hábil en que se entiende recibido cada valor, con la hora de corte del calendario.

    Usa la hora de cada valor: es la versión por columna de
    :meth:`habilmente.Calendario.fecha_efectiva`.

    Args:
        serie: Columna de momentos (``datetime64`` con o sin zona, o ``object``).
        calendario: Calendario laboral, normalmente con ``hora_corte``.
        errores: ``"raise"`` o ``"coerce"`` (ver :func:`es_dia_habil`).

    Returns:
        Serie de fechas (``datetime64``) con el mismo índice y nombre.

    Raises:
        TypeError: Si la columna no contiene fechas.
        ValueError: Si una fecha o su resultado salen del rango y ``errores="raise"``.
    """
    cal = _validar_calendario(calendario)
    return _aplicar(
        serie,
        cal.fecha_efectiva,
        "datetime64",
        errores,
        cal.zona_horaria,
        con_hora=True,
        hora_corte=cal.hora_corte,
    )


def vencimiento(
    serie: pd.Series[Any],
    n: int,
    calendario: Calendario | None = None,
    *,
    errores: Errores = "raise",
) -> pd.Series[Any]:
    """Vencimiento de un plazo de ``n`` días hábiles para cada momento de recepción.

    Es la versión por columna de :meth:`habilmente.Calendario.vencimiento`.

    Args:
        serie: Columna de momentos de recepción.
        n: Días hábiles del plazo (0 o más).
        calendario: Calendario laboral, normalmente con ``hora_corte``.
        errores: ``"raise"`` o ``"coerce"`` (ver :func:`es_dia_habil`).

    Returns:
        Serie de fechas (``datetime64``) con el mismo índice y nombre.

    Raises:
        TypeError: Si la columna no contiene fechas o ``n`` no es entero.
        ValueError: Si ``n`` es negativo, o una fecha o su resultado salen del rango y
            ``errores="raise"``.
    """
    cal = _validar_calendario(calendario)
    if validar_entero(n, "n") < 0:
        raise ValueError(f"'n' no puede ser negativo en un plazo; se recibió {n}.")
    return _aplicar(
        serie,
        lambda v: cal.vencimiento(v, n),
        "datetime64",
        errores,
        cal.zona_horaria,
        con_hora=True,
        hora_corte=cal.hora_corte,
    )


def marcar_dias_habiles(
    df: pd.DataFrame,
    columna: str,
    calendario: Calendario | None = None,
    *,
    nueva: str = "es_habil",
    errores: Errores = "raise",
) -> pd.DataFrame:
    """Devuelve una copia de ``df`` con una columna que indica si cada fecha es hábil.

    El DataFrame original no se modifica.

    Args:
        df: Tabla de datos.
        columna: Nombre de la columna de fechas.
        calendario: Calendario laboral; por defecto lunes a viernes.
        nueva: Nombre de la columna a crear.
        errores: ``"raise"`` o ``"coerce"`` (ver :func:`es_dia_habil`).

    Returns:
        Copia de ``df`` con la columna nueva.

    Raises:
        TypeError: Si ``df`` no es un DataFrame o la columna no contiene fechas.
        KeyError: Si la columna no existe.
        ValueError: Si la columna nueva ya existe, o hay fechas fuera de rango y
            ``errores="raise"``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Se esperaba un pandas.DataFrame; se recibió {type(df).__name__}.")
    if columna not in df.columns:
        raise KeyError(f"La columna {columna!r} no existe. Columnas: {list(df.columns)}.")
    if nueva in df.columns:
        raise ValueError(
            f"La columna {nueva!r} ya existe; elija otro nombre con el parámetro 'nueva'."
        )
    resultado = df.copy()
    resultado[nueva] = es_dia_habil(df[columna], calendario, errores=errores)
    return resultado


def tabla_calendario(inicio: date, fin: date, calendario: Calendario | None = None) -> pd.DataFrame:
    """Genera una tabla calendario (dimensión de fechas) lista para Power BI.

    Tiene una fila por día entre ``inicio`` y ``fin`` (ambos incluidos) con las
    columnas: ``fecha``, ``año``, ``trimestre``, ``mes``, ``dia``, ``dia_semana``,
    ``numero_dia_semana`` (1 = lunes), ``semana_iso``, ``es_fin_de_semana``,
    ``es_festivo``, ``nombre_festivo``, ``es_habil``, ``dia_habil_del_mes``
    (posición del día hábil dentro del mes; vacío si no es hábil),
    ``dias_habiles_del_mes`` y ``es_ultimo_dia_habil_del_mes``.

    Args:
        inicio: Primera fecha.
        fin: Última fecha.
        calendario: Calendario laboral; por defecto lunes a viernes.

    Returns:
        DataFrame con una fila por día.

    Raises:
        TypeError: Si las fechas o el calendario tienen un tipo inválido.
        ValueError: Si ``inicio`` es posterior a ``fin`` o están fuera de rango.

    Example:
        >>> from datetime import date
        >>> tabla = tabla_calendario(date(2026, 11, 1), date(2026, 11, 30))
        >>> int(tabla["es_habil"].sum())
        19
    """
    cal = _validar_calendario(calendario)
    a, b = validar_fecha(inicio), validar_fecha(fin)
    if a > b:
        raise ValueError(f"'inicio' ({a}) no puede ser posterior a 'fin' ({b}).")

    dias = [date.fromordinal(o) for o in range(a.toordinal(), b.toordinal() + 1)]
    habiles_por_mes: dict[tuple[int, int], tuple[date, ...]] = {}
    for dia in dias:
        clave = (dia.year, dia.month)
        if clave not in habiles_por_mes:
            habiles_por_mes[clave] = cal.dias_habiles_del_mes(*clave)
    posicion = {d: i for habiles in habiles_por_mes.values() for i, d in enumerate(habiles, 1)}

    filas = []
    for dia in dias:
        habiles = habiles_por_mes[(dia.year, dia.month)]
        filas.append(
            {
                "fecha": dia,
                "año": dia.year,
                "trimestre": (dia.month - 1) // 3 + 1,
                "mes": dia.month,
                "dia": dia.day,
                "dia_semana": DIAS_SEMANA[dia.weekday()],
                "numero_dia_semana": dia.isoweekday(),
                "semana_iso": dia.isocalendar().week,
                "es_fin_de_semana": dia.weekday() >= 5,  # Sábado (5) o domingo (6).
                "es_festivo": dia in _fechas_del_año(dia.year),
                "nombre_festivo": _nombre_festivo(dia),
                "es_habil": dia in posicion,
                "dia_habil_del_mes": posicion.get(dia),
                "dias_habiles_del_mes": len(habiles),
                "es_ultimo_dia_habil_del_mes": bool(habiles) and dia == habiles[-1],
            }
        )
    tabla = pd.DataFrame(filas)
    tabla["fecha"] = pd.to_datetime(tabla["fecha"])
    tabla["nombre_festivo"] = tabla["nombre_festivo"].astype("string")
    tabla["dia_habil_del_mes"] = tabla["dia_habil_del_mes"].astype("Int64")
    return tabla
