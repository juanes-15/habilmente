"""Integración con pandas: columnas de días hábiles y tabla calendario para Power BI.

Requiere el extra opcional: ``pip install "habilmente[pandas]"``.

Todas las funciones aceptan columnas ``datetime64`` (con o sin zona horaria; se usa la
fecha local de cada valor) o columnas ``object`` con ``date``/``datetime``. Los valores
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
from datetime import date
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
    normalizar_fecha,
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
    "marcar_dias_habiles",
    "nombre_festivo",
    "sumar_dias_habiles",
    "tabla_calendario",
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


def _a_fecha(valor: object) -> date:
    if isinstance(valor, str):
        raise TypeError(
            f"La columna contiene texto ({valor!r}); conviértala primero con pd.to_datetime(...)."
        )
    if isinstance(valor, np.datetime64):
        return pd.Timestamp(valor).date()
    return normalizar_fecha(valor)


def _factorizar(serie: object) -> tuple[np.ndarray[Any, Any], list[date]]:
    """Códigos por fila (-1 = vacío) y la lista de fechas distintas."""
    if not isinstance(serie, pd.Series):
        raise TypeError(f"Se esperaba una pandas.Series; se recibió {type(serie).__name__}.")
    if pd.api.types.is_datetime64_any_dtype(serie.dtype):
        locales = serie.dt.tz_localize(None) if serie.dt.tz is not None else serie
        codigos, unicos = pd.factorize(locales.dt.normalize())
        return codigos, [ts.date() for ts in pd.DatetimeIndex(unicos)]
    if serie.dtype == object:
        codigos, unicos = pd.factorize(serie)
        return codigos, [_a_fecha(valor) for valor in unicos]
    raise TypeError(
        f"La columna {serie.name!r} tiene tipo {serie.dtype}; se esperaban fechas "
        "(datetime64 o date). Conviértala primero con pd.to_datetime(...)."
    )


def _evaluar(
    fechas: Sequence[date], funcion: Callable[[date], _T], errores: Errores
) -> list[_T | None]:
    resultados: list[_T | None] = []
    for fecha in fechas:
        try:
            resultados.append(funcion(fecha))
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
    funcion: Callable[[date], object],
    dtype: str,
    errores: Errores,
) -> pd.Series[Any]:
    codigos, fechas = _factorizar(serie)
    valores = _evaluar(fechas, lambda f: funcion(validar_fecha(f)), _validar_errores(errores))
    return _expandir(valores, codigos, dtype, serie)


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
    return _aplicar(serie, cal.es_dia_habil, "boolean", errores)


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
    return _aplicar(serie, lambda f: f in _fechas_del_año(f.year), "boolean", errores)


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
    return _aplicar(serie, _nombre_festivo, "string", errores)


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
    return _aplicar(serie, lambda f: cal.sumar_dias_habiles(f, n), "datetime64", errores)


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
    codigos_inicio, fechas_inicio = _factorizar(inicio)
    codigos_fin, fechas_fin = _factorizar(fin)
    if not inicio.index.equals(fin.index):
        raise ValueError("'inicio' y 'fin' deben tener el mismo índice (las mismas filas).")

    # Con un acumulado de días hábiles hasta cada fecha (incluida), cada fila se resuelve
    # con una resta: entre(a, b) = acumulado(b) - acumulado(a). Los años previos se suman
    # una sola vez desde el primer año presente en los datos.
    años = sorted({f.year for f in (*fechas_inicio, *fechas_fin)} & _AÑOS_SOPORTADOS)
    previos: dict[int, int] = {}
    total = 0
    for año in range(años[0], años[-1] + 1) if años else ():
        previos[año] = total
        total += len(cal._habiles_del_año(año))

    def acumulado(fecha: date) -> int:
        dia = validar_fecha(fecha)
        return previos[dia.year] + cal._habiles_hasta(dia)

    valores_inicio = _evaluar(fechas_inicio, acumulado, modo)
    valores_fin = _evaluar(fechas_fin, acumulado, modo)
    a = _expandir(valores_inicio, codigos_inicio, "Int64", inicio)
    b = _expandir(valores_fin, codigos_fin, "Int64", inicio)
    resultado = b - a
    resultado.name = None
    return resultado


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
