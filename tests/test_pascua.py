from datetime import date

import pytest
from dateutil.easter import easter

from habilmente import AÑO_MAXIMO, AÑO_MINIMO, domingo_de_pascua


@pytest.mark.parametrize(
    ("año", "esperada"),
    [
        (1984, date(1984, 4, 22)),
        (2000, date(2000, 4, 23)),
        (2008, date(2008, 3, 23)),  # La más temprana del rango soportado.
        (2011, date(2011, 4, 24)),
        (2019, date(2019, 4, 21)),
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
        (2038, date(2038, 4, 25)),  # La más tardía posible en el calendario gregoriano.
    ],
)
def test_fechas_conocidas(año: int, esperada: date) -> None:
    assert domingo_de_pascua(año) == esperada


def test_coincide_con_dateutil_en_todo_el_rango() -> None:
    for año in range(AÑO_MINIMO, AÑO_MAXIMO + 1):
        assert domingo_de_pascua(año) == easter(año), año


def test_siempre_es_domingo_entre_22_de_marzo_y_25_de_abril() -> None:
    for año in range(AÑO_MINIMO, AÑO_MAXIMO + 1):
        pascua = domingo_de_pascua(año)
        assert pascua.weekday() == 6
        assert date(año, 3, 22) <= pascua <= date(año, 4, 25)
