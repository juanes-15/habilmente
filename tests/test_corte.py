"""Horario de corte, zona horaria, fecha_efectiva y vencimiento."""

from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

import habilmente as h
from habilmente import Calendario
from tests import oraculo

D, DT = date, datetime
UTC = UTC
BOGOTA = ZoneInfo("America/Bogota")
CORTE_15 = Calendario(hora_corte=time(15, 0))
CORTE_BOGOTA = Calendario(hora_corte=time(15, 0), zona_horaria="America/Bogota")


# --- fecha_efectiva -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("momento", "esperado"),
    [
        (DT(2026, 11, 13, 14, 59, 59, 999_999), D(2026, 11, 13)),  # Viernes, justo antes.
        (DT(2026, 11, 13, 15, 0), D(2026, 11, 17)),  # En punto: lunes 16 es festivo.
        (DT(2026, 11, 13, 23, 59), D(2026, 11, 17)),
        (DT(2026, 11, 14, 9, 0), D(2026, 11, 17)),  # Sábado.
        (DT(2026, 11, 16, 9, 0), D(2026, 11, 17)),  # Lunes festivo, antes del corte.
        (D(2026, 11, 13), D(2026, 11, 13)),  # Fecha sin hora: cuenta antes del corte.
        (D(2026, 11, 14), D(2026, 11, 17)),
        (DT(2026, 12, 31, 16, 0), D(2027, 1, 4)),  # Cambio de año.
    ],
)
def test_fecha_efectiva_con_corte(momento: date, esperado: date) -> None:
    assert CORTE_15.fecha_efectiva(momento) == esperado


def test_sin_hora_de_corte_cuenta_el_mismo_dia_habil() -> None:
    assert h.fecha_efectiva(DT(2026, 11, 13, 23, 59)) == D(2026, 11, 13)
    assert h.fecha_efectiva(D(2026, 11, 14)) == D(2026, 11, 17)


def test_sabado_habil_con_corte() -> None:
    cal = Calendario(sabados=[1, -1], hora_corte=time(12, 0))
    assert cal.fecha_efectiva(DT(2026, 11, 7, 11, 0)) == D(2026, 11, 7)
    assert cal.fecha_efectiva(DT(2026, 11, 7, 12, 0)) == D(2026, 11, 9)


def test_dia_habil_extra_y_no_habil_extra_con_corte() -> None:
    cal = Calendario(
        hora_corte=time(15, 0),
        dias_habiles_extra=[D(2026, 11, 16)],
        dias_no_habiles_extra=[D(2026, 11, 17)],
    )
    assert cal.fecha_efectiva(DT(2026, 11, 13, 16, 0)) == D(2026, 11, 16)
    assert cal.fecha_efectiva(DT(2026, 11, 16, 16, 0)) == D(2026, 11, 18)


# --- Zona horaria -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("momento", "esperado"),
    [
        (DT(2026, 11, 13, 19, 59, tzinfo=UTC), D(2026, 11, 13)),  # 14:59 en Bogotá.
        (DT(2026, 11, 13, 20, 0, tzinfo=UTC), D(2026, 11, 17)),  # 15:00 en Bogotá.
        (DT(2026, 11, 14, 4, 59, tzinfo=UTC), D(2026, 11, 17)),  # Viernes 23:59 en Bogotá.
        (DT(2026, 11, 13, 10, 0), D(2026, 11, 13)),  # Sin zona: hora local de Bogotá.
        (DT(2026, 11, 13, 16, 0, tzinfo=timezone(timedelta(hours=1))), D(2026, 11, 13)),
    ],
)
def test_zona_horaria_convierte_antes_del_corte(momento: datetime, esperado: date) -> None:
    assert CORTE_BOGOTA.fecha_efectiva(momento) == esperado


def test_sin_zona_cada_datetime_usa_su_hora_local() -> None:
    # 21:30 UTC son las 16:30 en Bogotá, pero sin zona el calendario lee "21:30".
    assert CORTE_15.fecha_efectiva(DT(2026, 11, 13, 14, 0, tzinfo=UTC)) == D(2026, 11, 13)
    assert CORTE_15.fecha_efectiva(DT(2026, 11, 13, 21, 30, tzinfo=UTC)) == D(2026, 11, 17)


def test_la_zona_aplica_a_todas_las_funciones() -> None:
    sabado_utc = DT(2026, 11, 14, 4, 30, tzinfo=UTC)  # Viernes 23:30 en Bogotá.
    con_zona = Calendario(zona_horaria=BOGOTA)
    assert con_zona.es_dia_habil(sabado_utc)
    assert con_zona.explicar_dia(sabado_utc) == "Hábil: día entre semana"
    assert con_zona.sumar_dias_habiles(sabado_utc, 1) == D(2026, 11, 17)
    assert con_zona.dias_habiles_entre(sabado_utc, D(2026, 11, 17)) == 1
    assert con_zona.listar_dias_habiles(sabado_utc, sabado_utc) == (D(2026, 11, 13),)
    # Sin zona se conserva el comportamiento anterior: se usa la fecha del propio datetime.
    assert not h.es_dia_habil(sabado_utc)


def test_zona_con_horario_de_verano() -> None:
    nueva_york = Calendario(hora_corte=time(15, 0), zona_horaria="America/New_York")
    # 19:30 UTC son las 14:30 en marzo después del cambio de hora (UTC-4) y las 15:30 antes.
    assert nueva_york.fecha_efectiva(DT(2026, 3, 10, 18, 30, tzinfo=UTC)) == D(2026, 3, 10)
    assert nueva_york.fecha_efectiva(DT(2026, 3, 6, 20, 30, tzinfo=UTC)) == D(2026, 3, 9)


def test_tzinfo_sin_desfase_se_trata_como_hora_local() -> None:
    class SinDesfase(timezone.__base__):  # type: ignore[misc,name-defined]
        def utcoffset(self, _: datetime | None) -> None:
            return None

        def dst(self, _: datetime | None) -> None:
            return None

        def tzname(self, _: datetime | None) -> str:
            return "local"

    momento = DT(2026, 11, 13, 16, 0, tzinfo=SinDesfase())
    assert CORTE_BOGOTA.fecha_efectiva(momento) == D(2026, 11, 17)


@pytest.mark.parametrize(
    "momento",
    [
        DT(1, 1, 1, tzinfo=UTC),
        DT(9999, 12, 31, 23, 59, tzinfo=UTC),
        DT(1984, 1, 1, 3, 0, tzinfo=UTC),  # En Bogotá todavía es 1983.
        DT(2200, 1, 1, 6, 0, tzinfo=UTC),  # En Bogotá ya es 2200.
    ],
)
def test_limites_del_rango_con_zona(momento: datetime) -> None:
    with pytest.raises(ValueError, match="fuera de rango"):
        CORTE_BOGOTA.fecha_efectiva(momento)


# --- vencimiento --------------------------------------------------------------------------


def test_vencimiento() -> None:
    assert CORTE_15.vencimiento(DT(2026, 11, 13, 14, 0), 5) == D(2026, 11, 23)
    assert CORTE_15.vencimiento(DT(2026, 11, 13, 16, 30), 5) == D(2026, 11, 24)
    assert CORTE_15.vencimiento(DT(2026, 11, 13, 16, 30), 0) == D(2026, 11, 17)
    assert h.vencimiento(D(2026, 11, 14), 1) == D(2026, 11, 18)


def test_vencimiento_valida_n() -> None:
    with pytest.raises(ValueError, match="no puede ser negativo"):
        CORTE_15.vencimiento(D(2026, 11, 13), -1)
    with pytest.raises(TypeError, match="'n' debe ser un entero"):
        CORTE_15.vencimiento(D(2026, 11, 13), True)
    with pytest.raises(ValueError, match="queda fuera del rango"):
        CORTE_15.vencimiento(DT(2199, 12, 31, 16, 0), 1)


# --- Configuración ------------------------------------------------------------------------


def test_configuracion_se_normaliza_y_compara() -> None:
    a = Calendario(hora_corte=time(15, 0), zona_horaria="America/Bogota")
    b = Calendario(hora_corte=time(15, 0), zona_horaria=ZoneInfo("America/Bogota"))
    assert a == b
    assert hash(a) == hash(b)
    assert a != Calendario(hora_corte=time(16, 0), zona_horaria="America/Bogota")
    assert a != Calendario(hora_corte=time(15, 0))
    assert "hora_corte=datetime.time(15, 0)" in repr(a)
    assert "America/Bogota" in repr(a)
    assert Calendario(zona_horaria=timezone(timedelta(hours=-5))).zona_horaria is not None


@pytest.mark.parametrize("hora", ["15:00", 15, DT(2026, 1, 1, 15, 0), 15.0])
def test_hora_corte_con_tipo_invalido(hora: object) -> None:
    with pytest.raises(TypeError, match=r"datetime\.time"):
        Calendario(hora_corte=hora)  # type: ignore[arg-type]


def test_hora_corte_invalida() -> None:
    with pytest.raises(ValueError, match="no debe tener zona horaria"):
        Calendario(hora_corte=time(15, 0, tzinfo=UTC))
    with pytest.raises(ValueError, match="medianoche"):
        Calendario(hora_corte=time(0, 0))


@pytest.mark.parametrize(
    "zona",
    ["", "America", "No/Existe", "../etc/passwd", "/etc/localtime", "America/Bogota ", "a\x00b"],
)
def test_zona_invalida(zona: str) -> None:
    with pytest.raises(ValueError, match="Zona horaria"):
        Calendario(zona_horaria=zona)


@pytest.mark.parametrize("zona", ["x" * 100, "a/b/c/d", "America/Bogotá"])
def test_zona_con_formato_invalido_no_consulta_el_sistema(zona: str) -> None:
    with pytest.raises(ValueError, match="Zona horaria inválida"):
        Calendario(zona_horaria=zona)


@pytest.mark.parametrize("zona", [5, -5.0, b"America/Bogota", ["America/Bogota"]])
def test_zona_con_tipo_invalido(zona: object) -> None:
    with pytest.raises(TypeError, match="zona_horaria"):
        Calendario(zona_horaria=zona)  # type: ignore[arg-type]


# --- Comparación contra el oráculo y propiedades ------------------------------------------

DESFASES = st.integers(-12 * 60, 14 * 60).map(lambda m: timezone(timedelta(minutes=m)))
CORTES = st.one_of(st.none(), st.times().filter(lambda t: t != time(0, 0)))
MOMENTOS = st.one_of(
    st.dates(D(2025, 1, 1), D(2027, 12, 31)),
    st.datetimes(DT(2025, 1, 1), DT(2027, 12, 31)),
    st.datetimes(DT(2025, 1, 1), DT(2027, 12, 31), timezones=DESFASES),
)


@st.composite
def calendarios_con_corte(draw: st.DrawFn) -> Calendario:
    return Calendario(
        sabados=draw(st.sampled_from([None, "todos", [1, -1], [2]])),
        dias_no_habiles_extra=draw(st.sets(st.dates(D(2025, 1, 1), D(2027, 12, 31)), max_size=8)),
        hora_corte=draw(CORTES),
        zona_horaria=draw(st.one_of(st.none(), DESFASES)),
    )


@given(calendarios_con_corte(), MOMENTOS, st.integers(0, 40))
def test_coincide_con_oraculo(cal: Calendario, momento: date, n: int) -> None:
    efectiva = cal.fecha_efectiva(momento)
    assert efectiva == oraculo.fecha_efectiva(cal, momento)
    assert cal.es_dia_habil(efectiva)
    assert cal.vencimiento(momento, n) == oraculo.sumar(cal, efectiva, n)


@given(
    calendarios_con_corte(),
    st.datetimes(DT(2025, 1, 1), DT(2027, 12, 31)),
    st.timedeltas(timedelta(0), timedelta(days=400)),
)
def test_fecha_efectiva_nunca_retrocede(
    cal: Calendario, momento: datetime, paso: timedelta
) -> None:
    posterior = momento + paso
    assume(posterior.year <= 2027)
    assert cal.fecha_efectiva(momento) <= cal.fecha_efectiva(posterior)


def test_tzinfo_defectuoso_falla_al_crear_el_calendario() -> None:
    class SinDesfase(timezone.__base__):  # type: ignore[misc,name-defined]
        def utcoffset(self, _: datetime | None) -> None:
            return None

        def dst(self, _: datetime | None) -> None:
            return None

        def tzname(self, _: datetime | None) -> str:
            return "x"

    class DesfaseImposible(SinDesfase):
        def utcoffset(self, _: datetime | None) -> timedelta:  # type: ignore[override]
            return timedelta(hours=30)

    class QueExplota(SinDesfase):
        def utcoffset(self, _: datetime | None) -> timedelta:  # type: ignore[override]
            raise RuntimeError("tzinfo roto")

    for zona in (SinDesfase(), DesfaseImposible(), QueExplota()):
        with pytest.raises(ValueError, match="no permite convertir horas"):
            Calendario(zona_horaria=zona)
