import importlib
import sys
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

pd = pytest.importorskip("pandas")

import habilmente as h  # noqa: E402
from habilmente import Calendario  # noqa: E402
from habilmente import pandas as hp  # noqa: E402

PRIMER_Y_ULTIMO = Calendario(sabados=[1, -1])


def serie(*valores: str | None, **kwargs: Any) -> Any:
    return pd.Series(pd.to_datetime(list(valores), format="ISO8601"), **kwargs)


# --- Funciones por columna ----------------------------------------------------------------


def test_es_dia_habil_conserva_indice_nombre_y_vacios() -> None:
    fechas = serie("2026-11-02", "2026-11-03 15:30", None, index=[10, 20, 30], name="radicado")
    resultado = hp.es_dia_habil(fechas)
    assert resultado.dtype == "boolean"
    assert resultado.name == "radicado"
    assert resultado.index.tolist() == [10, 20, 30]
    assert resultado.tolist() == [False, True, pd.NA]


def test_es_dia_habil_con_calendario() -> None:
    fechas = serie("2026-01-31", "2026-01-24")
    assert hp.es_dia_habil(fechas, PRIMER_Y_ULTIMO).tolist() == [True, False]


def test_zona_horaria_usa_la_fecha_local() -> None:
    # 2026-11-03 01:00 en Bogotá es 2026-11-03 06:00 UTC; en UTC-12 sería otro día.
    bogota = serie("2026-11-03 01:00").dt.tz_localize("America/Bogota")
    assert hp.es_dia_habil(bogota).tolist() == [True]
    noche_festivo = serie("2026-11-02 23:59").dt.tz_localize("America/Bogota")
    assert hp.es_dia_habil(noche_festivo).tolist() == [False]
    assert hp.es_dia_habil(noche_festivo.dt.tz_convert("UTC")).tolist() == [True]


def test_columna_object_con_date_datetime_y_vacios() -> None:
    fechas = pd.Series([date(2026, 11, 2), None, datetime(2026, 11, 3, 8), pd.NaT], dtype=object)
    assert hp.es_dia_habil(fechas).tolist() == [False, pd.NA, True, pd.NA]


def test_es_festivo_y_nombre() -> None:
    fechas = serie("2025-06-30", "2026-07-13", "2026-07-14", None)
    assert hp.es_festivo(fechas).tolist() == [True, True, False, pd.NA]
    nombres = hp.nombre_festivo(fechas)
    assert nombres.dtype == "string"
    assert nombres.tolist() == [
        "Sagrado Corazón de Jesús / San Pedro y San Pablo",
        "Nuestra Señora del Rosario de Chiquinquirá",
        pd.NA,
        pd.NA,
    ]


def test_sumar_dias_habiles() -> None:
    fechas = serie("2026-10-30", None, "2026-12-31")
    resultado = hp.sumar_dias_habiles(fechas, 1)
    assert pd.api.types.is_datetime64_dtype(resultado)
    assert resultado.tolist()[0] == pd.Timestamp("2026-11-03")
    assert resultado.isna().tolist() == [False, True, False]
    assert resultado.tolist()[2] == pd.Timestamp("2027-01-04")
    assert hp.sumar_dias_habiles(fechas, -1, PRIMER_Y_ULTIMO).tolist()[0] == pd.Timestamp(
        "2026-10-29"
    )


def test_dias_habiles_entre() -> None:
    radicado = serie("2026-11-02", "2026-11-03", None, "2026-01-31", "2020-01-01")
    respuesta = serie("2026-11-30", "2026-11-03", "2026-12-01", "2026-01-01", "2030-06-15")
    resultado = hp.dias_habiles_entre(radicado, respuesta)
    assert resultado.dtype == "Int64"
    esperado = [
        h.dias_habiles_entre(date(2026, 11, 2), date(2026, 11, 30)),
        0,
        pd.NA,
        h.dias_habiles_entre(date(2026, 1, 31), date(2026, 1, 1)),
        h.dias_habiles_entre(date(2020, 1, 1), date(2030, 6, 15)),
    ]
    assert resultado.tolist() == esperado


def test_dias_habiles_entre_todo_vacio() -> None:
    vacia = serie(None, None)
    assert hp.dias_habiles_entre(vacia, vacia).tolist() == [pd.NA, pd.NA]


def test_dias_habiles_entre_requiere_mismo_indice() -> None:
    with pytest.raises(ValueError, match="mismo índice"):
        hp.dias_habiles_entre(serie("2026-01-01", index=[0]), serie("2026-01-02", index=[1]))


def test_series_vacias() -> None:
    vacia = pd.Series([], dtype="datetime64[ns]")
    assert hp.es_dia_habil(vacia).tolist() == []
    assert hp.dias_habiles_entre(vacia, vacia).tolist() == []


# --- errores="coerce" ---------------------------------------------------------------------


def test_coerce_deja_vacias_las_fechas_fuera_de_rango() -> None:
    fechas = serie("1980-01-01", "2026-11-03", "2199-12-31")
    with pytest.raises(ValueError, match="fuera de rango"):
        hp.es_dia_habil(fechas)
    habil_2199 = h.es_dia_habil(date(2199, 12, 31))
    assert hp.es_dia_habil(fechas, errores="coerce").tolist() == [pd.NA, True, habil_2199]
    sumadas = hp.sumar_dias_habiles(fechas, 1, errores="coerce")
    assert sumadas.isna().tolist() == [True, False, True]
    entre = hp.dias_habiles_entre(
        fechas, serie("2026-01-01", "2026-11-04", "2026-01-01"), errores="coerce"
    )
    assert entre.isna().tolist() == [True, False, False]


def test_errores_invalido() -> None:
    with pytest.raises(ValueError, match="'errores'"):
        hp.es_dia_habil(serie("2026-01-01"), errores="ignore")  # type: ignore[arg-type]


# --- Validación de entradas ---------------------------------------------------------------


def test_texto_en_la_columna() -> None:
    with pytest.raises(TypeError, match=r"pd\.to_datetime"):
        hp.es_dia_habil(pd.Series(["2026-01-01", "2026-01-02"]))
    with pytest.raises(TypeError, match=r"pd\.to_datetime"):
        hp.es_dia_habil(pd.Series(["2026-01-01", None], dtype=object))


def test_columna_numerica() -> None:
    with pytest.raises(TypeError, match="se esperaban fechas"):
        hp.es_dia_habil(pd.Series([20260101]))


def test_no_es_una_serie() -> None:
    with pytest.raises(TypeError, match=r"pandas\.Series"):
        hp.es_dia_habil([date(2026, 1, 1)])  # type: ignore[arg-type]


def test_calendario_invalido() -> None:
    with pytest.raises(TypeError, match=r"habilmente\.Calendario"):
        hp.es_dia_habil(serie("2026-01-01"), {"sabados": "todos"})  # type: ignore[arg-type]


def test_n_invalido() -> None:
    with pytest.raises(TypeError, match="'n' debe ser un entero"):
        hp.sumar_dias_habiles(serie("2026-01-01"), 1.5)  # type: ignore[arg-type]


def test_acepta_numpy_datetime64_en_object() -> None:
    import numpy as np

    fechas = pd.Series([np.datetime64("2026-11-02"), np.datetime64("2026-11-03")], dtype=object)
    assert hp.es_dia_habil(fechas).tolist() == [False, True]


# --- marcar_dias_habiles ------------------------------------------------------------------


def test_marcar_no_modifica_el_original() -> None:
    df = pd.DataFrame({"fecha": serie("2026-11-02", "2026-11-03"), "valor": [1, 2]})
    resultado = hp.marcar_dias_habiles(df, "fecha")
    assert list(df.columns) == ["fecha", "valor"]
    assert resultado["es_habil"].tolist() == [False, True]
    nombre_propio = hp.marcar_dias_habiles(df, "fecha", PRIMER_Y_ULTIMO, nueva="habil")
    assert "habil" in nombre_propio.columns


def test_marcar_validaciones() -> None:
    df = pd.DataFrame({"fecha": serie("2026-11-02"), "es_habil": [True]})
    with pytest.raises(KeyError, match="no existe"):
        hp.marcar_dias_habiles(df, "otra")
    with pytest.raises(ValueError, match="ya existe"):
        hp.marcar_dias_habiles(df, "fecha")
    with pytest.raises(TypeError, match="DataFrame"):
        hp.marcar_dias_habiles(df["fecha"], "fecha")


# --- tabla_calendario ---------------------------------------------------------------------


def test_tabla_calendario_columnas_y_valores() -> None:
    tabla = hp.tabla_calendario(date(2026, 10, 30), date(2026, 11, 4))
    assert list(tabla.columns) == [
        "fecha",
        "año",
        "trimestre",
        "mes",
        "dia",
        "dia_semana",
        "numero_dia_semana",
        "semana_iso",
        "es_fin_de_semana",
        "es_festivo",
        "nombre_festivo",
        "es_habil",
        "dia_habil_del_mes",
        "dias_habiles_del_mes",
        "es_ultimo_dia_habil_del_mes",
    ]
    assert len(tabla) == 6
    primera = tabla.iloc[0]
    assert primera["dia_semana"] == "viernes"
    assert primera["es_ultimo_dia_habil_del_mes"]
    assert primera["dia_habil_del_mes"] == 21
    festivo = tabla.iloc[3]
    assert festivo["nombre_festivo"] == "Día de Todos los Santos"
    assert not festivo["es_habil"]
    assert pd.isna(festivo["dia_habil_del_mes"])
    assert tabla.iloc[4]["dia_habil_del_mes"] == 1
    assert tabla["dias_habiles_del_mes"].tolist() == [21, 21, 19, 19, 19, 19]


def test_tabla_calendario_un_año_completo() -> None:
    tabla = hp.tabla_calendario(date(2026, 1, 1), date(2026, 12, 31), PRIMER_Y_ULTIMO)
    assert len(tabla) == 365
    assert int(tabla["es_festivo"].sum()) == 19
    assert int(tabla["es_ultimo_dia_habil_del_mes"].sum()) == 12
    habiles = tabla.loc[tabla["es_habil"], "fecha"].dt.date.tolist()
    assert habiles == list(
        PRIMER_Y_ULTIMO.listar_dias_habiles(date(2026, 1, 1), date(2026, 12, 31))
    )


def test_tabla_calendario_mes_sin_habiles() -> None:
    cerrado = Calendario(dias_no_habiles_extra=h.dias_habiles_del_mes(2026, 2))
    tabla = hp.tabla_calendario(date(2026, 2, 1), date(2026, 2, 28), cerrado)
    assert not tabla["es_habil"].any()
    assert not tabla["es_ultimo_dia_habil_del_mes"].any()


def test_tabla_calendario_validaciones() -> None:
    with pytest.raises(ValueError, match="no puede ser posterior"):
        hp.tabla_calendario(date(2026, 2, 1), date(2026, 1, 1))
    with pytest.raises(TypeError, match=r"datetime\.date"):
        hp.tabla_calendario("2026-01-01", date(2026, 1, 2))  # type: ignore[arg-type]


# --- Comparación contra el cálculo fila por fila ------------------------------------------

FECHAS = st.dates(date(2024, 1, 1), date(2028, 12, 31))


@given(st.lists(st.one_of(FECHAS, st.none()), max_size=40), st.integers(-30, 30))
def test_coincide_con_el_calculo_fila_por_fila(fechas: list[date | None], n: int) -> None:
    columna = pd.Series(pd.to_datetime(fechas), dtype="datetime64[ns]")
    habiles = hp.es_dia_habil(columna, PRIMER_Y_ULTIMO).tolist()
    sumadas = hp.sumar_dias_habiles(columna, n, PRIMER_Y_ULTIMO).tolist()
    fin = columna + timedelta(days=n * 3)
    entre = hp.dias_habiles_entre(columna, fin, PRIMER_Y_ULTIMO).tolist()
    for i, fecha in enumerate(fechas):
        if fecha is None:
            assert habiles[i] is pd.NA
            assert pd.isna(sumadas[i])
            assert entre[i] is pd.NA
        else:
            assert habiles[i] == PRIMER_Y_ULTIMO.es_dia_habil(fecha)
            assert sumadas[i].date() == PRIMER_Y_ULTIMO.sumar_dias_habiles(fecha, n)
            esperado = PRIMER_Y_ULTIMO.dias_habiles_entre(fecha, fecha + timedelta(days=n * 3))
            assert entre[i] == esperado


# --- pandas no instalado ------------------------------------------------------------------


def test_mensaje_claro_si_falta_pandas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", None)
    monkeypatch.delitem(sys.modules, "habilmente.pandas")
    with pytest.raises(ModuleNotFoundError, match=r'pip install "habilmente\[pandas\]"'):
        importlib.import_module("habilmente.pandas")
