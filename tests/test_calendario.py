from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

import habilmente as h
from habilmente import CALENDARIO_ESTANDAR, Calendario

D = date
PRIMER_Y_ULTIMO = Calendario(sabados=[1, -1])


# --- Calendario estándar (lunes a viernes) ------------------------------------------------


@pytest.mark.parametrize(
    ("fecha", "esperado"),
    [
        (D(2026, 10, 27), True),  # Martes normal.
        (D(2026, 10, 31), False),  # Sábado.
        (D(2026, 11, 1), False),  # Domingo.
        (D(2026, 11, 2), False),  # Lunes festivo (Todos los Santos trasladado).
        (D(2026, 4, 2), False),  # Jueves Santo.
        (D(2026, 7, 13), False),  # Nuevo festivo, Ley 2578 de 2026.
    ],
)
def test_es_dia_habil_estandar(fecha: date, esperado: bool) -> None:
    assert h.es_dia_habil(fecha) is esperado


def test_siguiente_salta_fin_de_semana_y_festivo() -> None:
    # Viernes 9 de enero de 2026 -> lunes 12 es Reyes -> martes 13.
    assert h.siguiente_dia_habil(D(2026, 1, 9)) == D(2026, 1, 13)


def test_siguiente_es_estricto_aunque_la_fecha_sea_habil() -> None:
    assert h.siguiente_dia_habil(D(2026, 10, 27)) == D(2026, 10, 28)
    assert h.anterior_dia_habil(D(2026, 10, 27)) == D(2026, 10, 26)


def test_cambio_de_año_en_ambas_direcciones() -> None:
    # 31 dic 2026 (jueves) -> 1 ene 2027 festivo (viernes) -> lunes 4.
    assert h.siguiente_dia_habil(D(2026, 12, 31)) == D(2027, 1, 4)
    assert h.anterior_dia_habil(D(2027, 1, 4)) == D(2026, 12, 31)
    assert h.dias_habiles_entre(D(2026, 12, 31), D(2027, 1, 4)) == 1


def test_semana_santa_completa() -> None:
    # Miércoles 1 abr 2026 + 1 hábil -> jueves y viernes santos -> lunes 6.
    assert h.sumar_dias_habiles(D(2026, 4, 1), 1) == D(2026, 4, 6)


@pytest.mark.parametrize(
    ("fecha", "esperado"),
    [
        (D(2026, 10, 27), D(2026, 10, 27)),  # Hábil: se queda.
        (D(2026, 10, 31), D(2026, 11, 3)),  # Sábado -> lunes festivo -> martes.
    ],
)
def test_sumar_cero(fecha: date, esperado: date) -> None:
    assert h.sumar_dias_habiles(fecha, 0) == esperado


def test_sumar_negativo() -> None:
    assert h.sumar_dias_habiles(D(2026, 1, 13), -1) == D(2026, 1, 9)
    assert h.sumar_dias_habiles(D(2026, 1, 13), -2) == D(2026, 1, 8)


def test_sumar_muchos_años() -> None:
    inicio = D(1984, 1, 2)
    fin = h.sumar_dias_habiles(inicio, 20_000)
    assert h.dias_habiles_entre(inicio, fin) == 20_000
    assert h.sumar_dias_habiles(fin, -20_000) == inicio


def test_dias_habiles_entre() -> None:
    assert h.dias_habiles_entre(D(2026, 10, 9), D(2026, 10, 16)) == 4
    assert h.dias_habiles_entre(D(2026, 10, 16), D(2026, 10, 9)) == -4
    assert h.dias_habiles_entre(D(2026, 10, 9), D(2026, 10, 9)) == 0
    # Rango de varios años: suma exacta de los días hábiles de cada año.
    total = sum(len(h.listar_dias_habiles(D(a, 1, 1), D(a, 12, 31))) for a in (2025, 2026))
    assert h.dias_habiles_entre(D(2024, 12, 31), D(2026, 12, 31)) == total


def test_listar_incluye_ambos_extremos() -> None:
    assert h.listar_dias_habiles(D(2026, 10, 26), D(2026, 10, 28)) == (
        D(2026, 10, 26),
        D(2026, 10, 27),
        D(2026, 10, 28),
    )
    assert h.listar_dias_habiles(D(2026, 10, 27), D(2026, 10, 27)) == (D(2026, 10, 27),)
    assert h.listar_dias_habiles(D(2026, 10, 31), D(2026, 11, 2)) == ()


def test_listar_cruza_años() -> None:
    dias = h.listar_dias_habiles(D(2026, 12, 30), D(2027, 1, 5))
    assert dias == (D(2026, 12, 30), D(2026, 12, 31), D(2027, 1, 4), D(2027, 1, 5))


def test_dias_habiles_del_mes() -> None:
    octubre = h.dias_habiles_del_mes(2026, 10)
    assert len(octubre) == 21  # 22 días entre semana menos el festivo del lunes 12.
    assert D(2026, 10, 12) not in octubre
    assert len(h.dias_habiles_del_mes(2026, 12)) == 21  # 23 entre semana menos el 8 y el 25.


@pytest.mark.parametrize(
    ("año", "mes", "n", "esperado"),
    [
        (2026, 1, 1, D(2026, 1, 2)),  # El 1 de enero es festivo.
        (2026, 1, 5, D(2026, 1, 8)),
        (2026, 1, -1, D(2026, 1, 30)),
        (2026, 12, -1, D(2026, 12, 31)),
        (2026, 3, -1, D(2026, 3, 31)),
        (2026, 5, 1, D(2026, 5, 4)),  # 1 de mayo festivo (viernes), luego fin de semana.
    ],
)
def test_dia_habil_del_mes(año: int, mes: int, n: int, esperado: date) -> None:
    assert h.dia_habil_del_mes(año, mes, n) == esperado


# --- Sábados configurables ----------------------------------------------------------------


def test_primer_y_ultimo_sabado_en_mes_de_cinco_sabados() -> None:
    # Enero 2026: sábados 3, 10, 17, 24 y 31.
    habiles = {d for d in (3, 10, 17, 24, 31) if PRIMER_Y_ULTIMO.es_dia_habil(D(2026, 1, d))}
    assert habiles == {3, 31}


def test_primer_y_ultimo_sabado_en_mes_de_cuatro_sabados() -> None:
    # Febrero 2026: sábados 7, 14, 21 y 28.
    habiles = {d for d in (7, 14, 21, 28) if PRIMER_Y_ULTIMO.es_dia_habil(D(2026, 2, d))}
    assert habiles == {7, 28}


@pytest.mark.parametrize(
    "festivo_en_sabado",
    [
        D(2027, 5, 1),  # Primer sábado de mayo 2027: Día del Trabajo.
        D(2027, 8, 7),  # Primer sábado de agosto 2027: Batalla de Boyacá.
        D(2027, 12, 25),  # Último sábado de diciembre 2027: Navidad.
    ],
)
def test_festivo_gana_sobre_sabado_habil(festivo_en_sabado: date) -> None:
    assert festivo_en_sabado.weekday() == 5
    assert h.es_festivo(festivo_en_sabado)
    assert not PRIMER_Y_ULTIMO.es_dia_habil(festivo_en_sabado)
    # La regla no se corre al sábado siguiente.
    assert not PRIMER_Y_ULTIMO.es_dia_habil(D(2027, 5, 8))


def test_quinto_sabado_solo_existe_en_algunos_meses() -> None:
    cal = Calendario(sabados=[5])
    assert cal.es_dia_habil(D(2026, 1, 31))
    assert cal.dias_habiles_del_mes(2026, 2) == h.dias_habiles_del_mes(2026, 2)


def test_quinto_desde_el_final_es_el_primero_en_meses_de_cinco() -> None:
    cal = Calendario(sabados=[-5])
    assert cal.es_dia_habil(D(2026, 1, 3))
    assert not cal.es_dia_habil(D(2026, 2, 7))


def test_todos_los_sabados() -> None:
    cal = Calendario(sabados="todos")
    assert all(cal.es_dia_habil(D(2026, 1, d)) for d in (3, 10, 17, 24, 31))
    assert not cal.es_dia_habil(D(2026, 1, 4))  # El domingo sigue sin ser hábil.


def test_sabados_hábiles_cambian_las_sumas() -> None:
    # Viernes 30 ene 2026 + 1: el sábado 31 es el último del mes y es hábil.
    assert PRIMER_Y_ULTIMO.siguiente_dia_habil(D(2026, 1, 30)) == D(2026, 1, 31)
    assert h.siguiente_dia_habil(D(2026, 1, 30)) == D(2026, 2, 2)
    assert len(PRIMER_Y_ULTIMO.dias_habiles_del_mes(2026, 1)) == (
        len(h.dias_habiles_del_mes(2026, 1)) + 2
    )


# --- Días extra y prioridades -------------------------------------------------------------


def test_dia_habil_extra_gana_sobre_festivo_y_domingo() -> None:
    cal = Calendario(dias_habiles_extra=[D(2026, 12, 8), D(2026, 12, 13)])
    assert cal.es_dia_habil(D(2026, 12, 8))  # Festivo.
    assert cal.es_dia_habil(D(2026, 12, 13))  # Domingo.


def test_dia_no_habil_extra() -> None:
    cal = Calendario(dias_no_habiles_extra=[D(2026, 12, 24), D(2026, 12, 31)])
    assert not cal.es_dia_habil(D(2026, 12, 24))
    assert cal.siguiente_dia_habil(D(2026, 12, 30)) == D(2027, 1, 4)


def test_no_habil_extra_gana_sobre_sabado_configurado() -> None:
    cal = Calendario(sabados="todos", dias_no_habiles_extra=[D(2026, 1, 3)])
    assert not cal.es_dia_habil(D(2026, 1, 3))


def test_fecha_en_ambas_listas_es_error() -> None:
    with pytest.raises(ValueError, match="a la vez"):
        Calendario(dias_habiles_extra=[D(2026, 1, 2)], dias_no_habiles_extra=[D(2026, 1, 2)])


# --- Configuración: normalización, igualdad e inmutabilidad -------------------------------


def test_normaliza_y_compara_configuraciones() -> None:
    a = Calendario(sabados=[-1, 1], dias_no_habiles_extra=[D(2026, 1, 2), D(2026, 1, 2)])
    b = Calendario(sabados=(1, -1), dias_no_habiles_extra={datetime(2026, 1, 2, 8)})
    assert a == b
    assert hash(a) == hash(b)
    assert a.sabados == (1, -1)
    assert Calendario(sabados=[]).sabados is None
    assert Calendario() == CALENDARIO_ESTANDAR


def test_es_inmutable_y_no_depende_de_la_lista_original() -> None:
    extra = [D(2026, 1, 2)]
    cal = Calendario(dias_no_habiles_extra=extra)
    extra.append(D(2026, 1, 5))
    assert cal.es_dia_habil(D(2026, 1, 5))
    with pytest.raises(FrozenInstanceError):
        cal.sabados = "todos"  # type: ignore[misc]


def test_repr_no_expone_la_cache() -> None:
    cal = Calendario(sabados=[1])
    cal.es_dia_habil(D(2026, 1, 3))
    assert "_cache" not in repr(cal)
    assert "sabados=(1,)" in repr(cal)


def test_acepta_generadores_y_datetime() -> None:
    cal = Calendario(sabados=(p for p in [1]), dias_habiles_extra=(D(2026, 1, d) for d in [4]))
    assert cal.es_dia_habil(datetime(2026, 1, 4, 10, 30))
    assert cal.sumar_dias_habiles(datetime(2026, 1, 3, 23, 0), 0) == D(2026, 1, 3)


# --- Validación de entradas ---------------------------------------------------------------


@pytest.mark.parametrize("sabados", [[6], [0], [-6], [1, 2, 3, 4, 5, 6]])
def test_posicion_de_sabado_inexistente(sabados: list[int]) -> None:
    with pytest.raises(ValueError, match="Posición de sábado inválida"):
        Calendario(sabados=sabados)


def test_posiciones_repetidas() -> None:
    with pytest.raises(ValueError, match="repetidas"):
        Calendario(sabados=[1, 1])


@pytest.mark.parametrize("sabados", ["Todos", "primero", "", "1,-1"])
def test_texto_de_sabados_desconocido(sabados: str) -> None:
    with pytest.raises(ValueError, match='"todos"'):
        Calendario(sabados=sabados)  # type: ignore[arg-type]


@pytest.mark.parametrize("sabados", [1, True, 1.5])
def test_sabados_con_tipo_invalido(sabados: object) -> None:
    with pytest.raises(TypeError, match="sabados"):
        Calendario(sabados=sabados)  # type: ignore[arg-type]


@pytest.mark.parametrize("posiciones", [[True], [1.0], ["1"], [None]])
def test_posiciones_con_tipo_invalido(posiciones: list[object]) -> None:
    with pytest.raises(TypeError, match="enteros"):
        Calendario(sabados=posiciones)  # type: ignore[arg-type]


@pytest.mark.parametrize("valor", ["2026-01-01", D(2026, 1, 1), 20260101, b"x"])
def test_dias_extra_deben_ser_coleccion(valor: object) -> None:
    with pytest.raises(TypeError, match="colección de fechas"):
        Calendario(dias_no_habiles_extra=valor)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="colección de fechas"):
        Calendario(dias_habiles_extra=valor)  # type: ignore[arg-type]


def test_dias_extra_con_elementos_invalidos() -> None:
    with pytest.raises(TypeError, match=r"datetime\.date"):
        Calendario(dias_habiles_extra=["2026-01-01"])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="fuera de rango"):
        Calendario(dias_habiles_extra=[D(1983, 12, 31)])


@pytest.mark.parametrize("n", [True, 1.0, "1", None])
def test_n_debe_ser_entero(n: object) -> None:
    with pytest.raises(TypeError, match="'n' debe ser un entero"):
        h.sumar_dias_habiles(D(2026, 1, 1), n)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="'n' debe ser un entero"):
        h.dia_habil_del_mes(2026, 1, n)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "funcion",
    [h.es_dia_habil, h.siguiente_dia_habil, h.anterior_dia_habil],
)
def test_fechas_invalidas_en_funciones(funcion: object) -> None:
    with pytest.raises(TypeError, match=r"datetime\.date"):
        funcion("2026-01-01")  # type: ignore[operator]
    with pytest.raises(ValueError, match="fuera de rango"):
        funcion(D(1983, 6, 1))  # type: ignore[operator]


def test_resultado_fuera_de_rango() -> None:
    with pytest.raises(ValueError, match="queda fuera del rango"):
        h.siguiente_dia_habil(D(2100, 12, 31))
    with pytest.raises(ValueError, match="queda fuera del rango"):
        h.anterior_dia_habil(D(1984, 1, 2))  # El 1 de enero de 1984 es festivo.
    with pytest.raises(ValueError, match="queda fuera del rango"):
        h.sumar_dias_habiles(D(2100, 1, 1), 1_000)


def test_rangos_invalidos() -> None:
    with pytest.raises(ValueError, match="no puede ser posterior"):
        h.listar_dias_habiles(D(2026, 2, 1), D(2026, 1, 1))
    with pytest.raises(TypeError, match=r"datetime\.date"):
        h.dias_habiles_entre(D(2026, 1, 1), "2026-02-01")  # type: ignore[arg-type]


@pytest.mark.parametrize("mes", [0, 13, -1])
def test_mes_fuera_de_rango(mes: int) -> None:
    with pytest.raises(ValueError, match="mes debe estar entre 1 y 12"):
        h.dias_habiles_del_mes(2026, mes)


@pytest.mark.parametrize("mes", [True, 1.0, "1"])
def test_mes_con_tipo_invalido(mes: object) -> None:
    with pytest.raises(TypeError, match="'mes' debe ser un entero"):
        h.dias_habiles_del_mes(2026, mes)  # type: ignore[arg-type]


@pytest.mark.parametrize("n", [0, 22, -22])
def test_posicion_inexistente_en_el_mes(n: int) -> None:
    with pytest.raises(ValueError, match="tiene 21 días hábiles"):
        h.dia_habil_del_mes(2026, 10, n)


def test_año_invalido_en_funciones_de_mes() -> None:
    with pytest.raises(ValueError, match="fuera de rango"):
        h.dias_habiles_del_mes(2101, 1)
    with pytest.raises(TypeError, match="entero"):
        h.dia_habil_del_mes("2026", 1, 1)  # type: ignore[arg-type]
