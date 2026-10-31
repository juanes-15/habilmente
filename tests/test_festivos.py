from datetime import date, datetime, timedelta

import holidays
import pytest

from habilmente import (
    AÑO_MAXIMO,
    AÑO_MINIMO,
    Festivo,
    TipoFestivo,
    domingo_de_pascua,
    es_festivo,
    fechas_festivas,
    festivos,
    nombre_festivo,
)
from tests import oraculo
from tests.calendarios_oficiales import CALENDARIOS_OFICIALES

TODOS_LOS_AÑOS = range(AÑO_MINIMO, AÑO_MAXIMO + 1)


# --- Contraste con fuentes externas -------------------------------------------------------


@pytest.mark.parametrize("año", sorted(CALENDARIOS_OFICIALES))
def test_coincide_con_calendario_oficial(año: int) -> None:
    assert fechas_festivas(año) == CALENDARIOS_OFICIALES[año]


def test_coincide_con_libreria_holidays_hasta_2100() -> None:
    # Implementación de terceros; solo cubre hasta 2100.
    for año in range(AÑO_MINIMO, 2101):
        referencia = frozenset(holidays.country_holidays("CO", years=año))
        assert fechas_festivas(año) == referencia, año


def test_coincide_con_oraculo_propio_en_todo_el_rango() -> None:
    # Reglas escritas aparte y Pascua de dateutil: cubre también 2101 a 2199.
    for año in TODOS_LOS_AÑOS:
        assert fechas_festivas(año) == oraculo.festivos(año), año


# --- Estructura de cada año ---------------------------------------------------------------


@pytest.mark.parametrize("año", TODOS_LOS_AÑOS)
def test_cantidad_y_reglas_de_cada_festivo(año: int) -> None:
    lista = festivos(año)
    pascua = domingo_de_pascua(año)

    assert len(lista) == (19 if año >= 2026 else 18)
    assert list(lista) == sorted(lista)

    for festivo in lista:
        assert festivo.fecha.year == año
        match festivo.tipo:
            case TipoFestivo.FIJO:
                assert not festivo.trasladado
            case TipoFestivo.SEMANA_SANTA:
                assert not festivo.trasladado
                assert festivo.fecha in {pascua - timedelta(days=3), pascua - timedelta(days=2)}
            case TipoFestivo.TRASLADABLE | TipoFestivo.PASCUA_TRASLADABLE:
                assert festivo.fecha.weekday() == 0
                assert 0 <= (festivo.fecha - festivo.fecha_original).days <= 6


def test_conteo_por_tipo() -> None:
    tipos = [f.tipo for f in festivos(2026)]
    assert tipos.count(TipoFestivo.FIJO) == 6
    assert tipos.count(TipoFestivo.TRASLADABLE) == 8
    assert tipos.count(TipoFestivo.SEMANA_SANTA) == 2
    assert tipos.count(TipoFestivo.PASCUA_TRASLADABLE) == 3


# --- Casos borde --------------------------------------------------------------------------


def test_festivo_fijo_en_domingo_no_se_traslada() -> None:
    # 20 de julio de 2025 cayó domingo: se pierde, no se mueve al lunes.
    assert es_festivo(date(2025, 7, 20))
    assert not es_festivo(date(2025, 7, 21))


def test_trasladable_en_domingo_pasa_al_lunes() -> None:
    assert not es_festivo(date(2025, 6, 29))
    assert es_festivo(date(2025, 6, 30))


def test_trasladable_que_ya_cae_en_lunes_se_queda() -> None:
    (raza,) = [f for f in festivos(2026) if f.fecha_original == date(2026, 10, 12)]
    assert raza.fecha == date(2026, 10, 12)
    assert not raza.trasladado


def test_traslado_que_cambia_de_mes() -> None:
    # San Pedro 2024 (sábado 29 de junio) se descansa el lunes 1 de julio.
    assert es_festivo(date(2024, 7, 1))
    assert not es_festivo(date(2024, 6, 29))


@pytest.mark.parametrize(
    ("fecha", "nombre"),
    [
        (date(2025, 6, 30), "Sagrado Corazón de Jesús / San Pedro y San Pablo"),
        (date(2019, 7, 1), "Sagrado Corazón de Jesús / San Pedro y San Pablo"),
    ],
)
def test_dos_celebraciones_el_mismo_dia(fecha: date, nombre: str) -> None:
    assert nombre_festivo(fecha) == nombre
    assert len(fechas_festivas(fecha.year)) == 17
    assert len(festivos(fecha.year)) == 18


def test_nuevo_festivo_ley_2578_solo_desde_2026() -> None:
    assert nombre_festivo(date(2026, 7, 13)) == "Nuestra Señora del Rosario de Chiquinquirá"
    assert not es_festivo(date(2025, 7, 14))
    nombres_2025 = {f.nombre for f in festivos(2025)}
    assert "Nuestra Señora del Rosario de Chiquinquirá" not in nombres_2025


def test_bordes_del_año() -> None:
    assert es_festivo(date(2027, 1, 1))
    assert es_festivo(date(2026, 12, 25))
    assert not es_festivo(date(2026, 12, 31))


def test_dia_normal_y_domingo_no_son_festivos() -> None:
    assert not es_festivo(date(2026, 10, 27))
    assert nombre_festivo(date(2026, 10, 27)) is None
    assert not es_festivo(date(2026, 10, 25))  # Domingo.


def test_acepta_datetime_y_usa_solo_la_fecha() -> None:
    assert es_festivo(datetime(2025, 12, 25, 23, 59))
    assert nombre_festivo(datetime(2025, 12, 25, 0, 0)) == "Navidad"


def test_acepta_subclases_de_date() -> None:
    class MiFecha(date):
        pass

    assert es_festivo(MiFecha(2025, 1, 1))


# --- Inmutabilidad ------------------------------------------------------------------------


def test_resultados_inmutables() -> None:
    lista = festivos(2025)
    assert isinstance(lista, tuple)
    assert isinstance(fechas_festivas(2025), frozenset)
    with pytest.raises(AttributeError):
        lista[0].nombre = "otro"  # type: ignore[misc]


def test_festivo_trasladado_expone_fecha_original() -> None:
    festivo = Festivo(date(2025, 6, 30), "X", TipoFestivo.TRASLADABLE, date(2025, 6, 29))
    assert festivo.trasladado


# --- Validación de entradas ---------------------------------------------------------------


@pytest.mark.parametrize("año", ["2025", 2025.0, None, True, [2025]])
def test_año_con_tipo_invalido(año: object) -> None:
    with pytest.raises(TypeError, match="entero"):
        festivos(año)  # type: ignore[arg-type]


@pytest.mark.parametrize("año", [AÑO_MINIMO - 1, AÑO_MAXIMO + 1, 0, -2025])
def test_año_fuera_de_rango(año: int) -> None:
    with pytest.raises(ValueError, match="fuera de rango"):
        fechas_festivas(año)


def test_limites_del_rango_funcionan() -> None:
    assert festivos(AÑO_MINIMO)
    assert festivos(AÑO_MAXIMO)


@pytest.mark.parametrize("fecha", ["2025-12-25", 20251225, None, (2025, 12, 25)])
def test_fecha_con_tipo_invalido(fecha: object) -> None:
    with pytest.raises(TypeError, match=r"datetime\.date"):
        es_festivo(fecha)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"datetime\.date"):
        nombre_festivo(fecha)  # type: ignore[arg-type]


def test_fecha_fuera_de_rango() -> None:
    with pytest.raises(ValueError, match="fuera de rango"):
        es_festivo(date(1983, 1, 1))
