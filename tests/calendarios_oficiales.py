"""Calendarios de festivos verificados contra fuentes externas (no generados por la librería).

Fuentes consultadas el 2026-10-26:

- 2019 a 2025: listados "solo feriados" de calendariodecolombia.com
  (https://www.calendariodecolombia.com/descarga-calendario/<año>/solo-feriados).
- 2026 y 2027: el mismo listado más el festivo de la Ley 2578 del 1 de junio de 2026
  (9 de julio, Virgen de Chiquinquirá), que esa fuente aún no incluía:
  * 2026-07-13: Ministerio del Interior, "Gobierno sanciona ley que convierte el 9 de
    julio en nuevo festivo nacional" (mininterior.gov.co) y Cámara de Representantes.
  * 2027-07-12: Publimetro (2026-10-02) y la librería ``holidays`` 0.107.
"""

from __future__ import annotations

from datetime import date

# Cada año se escribe como "MM-DD" separados por espacio para que sea fácil compararlo
# a ojo con la fuente.
_LISTADOS: dict[int, str] = {
    2019: "01-01 01-07 03-25 04-18 04-19 05-01 06-03 06-24 07-01 07-20 08-07 08-19 "
    "10-14 11-04 11-11 12-08 12-25",
    2020: "01-01 01-06 03-23 04-09 04-10 05-01 05-25 06-15 06-22 06-29 07-20 08-07 "
    "08-17 10-12 11-02 11-16 12-08 12-25",
    2021: "01-01 01-11 03-22 04-01 04-02 05-01 05-17 06-07 06-14 07-05 07-20 08-07 "
    "08-16 10-18 11-01 11-15 12-08 12-25",
    2022: "01-01 01-10 03-21 04-14 04-15 05-01 05-30 06-20 06-27 07-04 07-20 08-07 "
    "08-15 10-17 11-07 11-14 12-08 12-25",
    2023: "01-01 01-09 03-20 04-06 04-07 05-01 05-22 06-12 06-19 07-03 07-20 08-07 "
    "08-21 10-16 11-06 11-13 12-08 12-25",
    2024: "01-01 01-08 03-25 03-28 03-29 05-01 05-13 06-03 06-10 07-01 07-20 08-07 "
    "08-19 10-14 11-04 11-11 12-08 12-25",
    2025: "01-01 01-06 03-24 04-17 04-18 05-01 06-02 06-23 06-30 07-20 08-07 08-18 "
    "10-13 11-03 11-17 12-08 12-25",
    2026: "01-01 01-12 03-23 04-02 04-03 05-01 05-18 06-08 06-15 06-29 07-13 07-20 "
    "08-07 08-17 10-12 11-02 11-16 12-08 12-25",
    2027: "01-01 01-11 03-22 03-25 03-26 05-01 05-10 05-31 06-07 07-05 07-12 07-20 "
    "08-07 08-16 10-18 11-01 11-15 12-08 12-25",
}

CALENDARIOS_OFICIALES: dict[int, frozenset[date]] = {
    año: frozenset(date(año, int(d[:2]), int(d[3:])) for d in listado.split())
    for año, listado in _LISTADOS.items()
}
