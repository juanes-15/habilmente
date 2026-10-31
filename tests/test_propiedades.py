"""Pruebas con miles de casos aleatorios contra el oráculo ingenuo y propiedades matemáticas."""

from datetime import date, timedelta
from typing import cast

from hypothesis import assume, given
from hypothesis import strategies as st

from habilmente import AÑO_MAXIMO, AÑO_MINIMO, Calendario, ConfigSabados
from tests import oraculo

# Fechas en todo el rango y, con más peso, en una ventana corta donde las listas extra
# coinciden a menudo con las fechas consultadas (así se ejercitan las prioridades).
TODO_EL_RANGO = st.dates(date(AÑO_MINIMO, 1, 1), date(AÑO_MAXIMO, 12, 31))
VENTANA = st.dates(date(2025, 12, 1), date(2027, 1, 31))
FECHAS = st.one_of(TODO_EL_RANGO, VENTANA, VENTANA)

SABADOS: st.SearchStrategy[ConfigSabados] = st.one_of(
    st.none(),
    st.just(cast("ConfigSabados", "todos")),
    st.lists(st.sampled_from([1, 2, 3, 4, 5, -1, -2, -3, -4, -5]), max_size=4, unique=True),
)


@st.composite
def calendarios(draw: st.DrawFn) -> Calendario:
    no_habiles = draw(st.sets(VENTANA, max_size=20))
    habiles = draw(st.sets(VENTANA, max_size=20)) - no_habiles
    return Calendario(
        sabados=draw(SABADOS), dias_no_habiles_extra=no_habiles, dias_habiles_extra=habiles
    )


CALENDARIOS = st.one_of(st.just(Calendario()), st.just(Calendario(sabados=[1, -1])), calendarios())


def _en_rango(dia: date) -> bool:
    return oraculo.PRIMER_DIA <= dia <= oraculo.ULTIMO_DIA


@given(CALENDARIOS, FECHAS)
def test_es_dia_habil_coincide_con_oraculo(cal: Calendario, dia: date) -> None:
    assert cal.es_dia_habil(dia) == oraculo.es_habil(cal, dia)


@given(CALENDARIOS, FECHAS, st.integers(-80, 80))
def test_sumar_coincide_con_oraculo(cal: Calendario, dia: date, n: int) -> None:
    try:
        esperado: date | None = oraculo.sumar(cal, dia, n)
    except ValueError:
        esperado = None
    if esperado is None:
        try:
            cal.sumar_dias_habiles(dia, n)
        except ValueError:
            return
        raise AssertionError("Debió fallar por salirse del rango")
    assert cal.sumar_dias_habiles(dia, n) == esperado


@given(CALENDARIOS, FECHAS, st.integers(-500, 500))
def test_entre_coincide_con_oraculo(cal: Calendario, a: date, desfase: int) -> None:
    b = a + timedelta(days=desfase) if _en_rango(a + timedelta(days=desfase)) else a
    assert cal.dias_habiles_entre(a, b) == oraculo.entre(cal, a, b)


@given(CALENDARIOS, FECHAS, st.integers(0, 120))
def test_listar_coincide_con_oraculo(cal: Calendario, a: date, largo: int) -> None:
    b = min(a + timedelta(days=largo), oraculo.ULTIMO_DIA)
    esperado = tuple(
        a + timedelta(days=i)
        for i in range((b - a).days + 1)
        if oraculo.es_habil(cal, a + timedelta(days=i))
    )
    assert cal.listar_dias_habiles(a, b) == esperado


@given(CALENDARIOS, FECHAS, st.integers(1, 3000))
def test_entre_es_inversa_de_sumar(cal: Calendario, a: date, n: int) -> None:
    try:
        b = cal.sumar_dias_habiles(a, n)
        # Al devolverse n días desde b se llega al último día hábil que no supera a.
        regreso = a if cal.es_dia_habil(a) else cal.anterior_dia_habil(a)
    except ValueError:
        assume(False)
    assert cal.es_dia_habil(b)
    assert cal.dias_habiles_entre(a, b) == n
    assert cal.sumar_dias_habiles(b, -n) == regreso


@given(CALENDARIOS, FECHAS, FECHAS, FECHAS)
def test_entre_es_antisimetrica_y_aditiva(cal: Calendario, a: date, b: date, c: date) -> None:
    assert cal.dias_habiles_entre(a, b) == -cal.dias_habiles_entre(b, a)
    assert cal.dias_habiles_entre(a, b) + cal.dias_habiles_entre(b, c) == (
        cal.dias_habiles_entre(a, c)
    )


@given(CALENDARIOS, FECHAS)
def test_siguiente_y_anterior_no_saltan_dias_habiles(cal: Calendario, dia: date) -> None:
    try:
        siguiente = cal.siguiente_dia_habil(dia)
        anterior = cal.anterior_dia_habil(dia)
    except ValueError:
        assume(False)
    assert anterior < dia < siguiente
    assert cal.dias_habiles_entre(dia, siguiente) == 1
    assert cal.dias_habiles_entre(anterior, dia) == (1 if cal.es_dia_habil(dia) else 0)
    assert cal.listar_dias_habiles(anterior, siguiente) == tuple(
        d for d in (anterior, dia, siguiente) if cal.es_dia_habil(d)
    )


@given(CALENDARIOS, st.integers(AÑO_MINIMO, AÑO_MAXIMO), st.integers(1, 12))
def test_dia_habil_del_mes_recorre_el_mes(cal: Calendario, año: int, mes: int) -> None:
    dias = cal.dias_habiles_del_mes(año, mes)
    assert all(d.year == año and d.month == mes and cal.es_dia_habil(d) for d in dias)
    for i, dia in enumerate(dias):
        assert cal.dia_habil_del_mes(año, mes, i + 1) == dia
        assert cal.dia_habil_del_mes(año, mes, i - len(dias)) == dia


@given(CALENDARIOS, FECHAS)
def test_explicar_dia_es_coherente(cal: Calendario, dia: date) -> None:
    habil = cal.es_dia_habil(dia)
    assert cal.explicar_dia(dia).startswith("Hábil: " if habil else "No hábil: ")
