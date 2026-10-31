"""habilmente: festivos de Colombia y días hábiles con calendarios configurables."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from habilmente._validacion import AÑO_MAXIMO, AÑO_MINIMO
from habilmente.calendario import (
    CALENDARIO_ESTANDAR,
    Calendario,
    ConfigSabados,
    anterior_dia_habil,
    dia_habil_del_mes,
    dias_habiles_del_mes,
    dias_habiles_entre,
    es_dia_habil,
    listar_dias_habiles,
    siguiente_dia_habil,
    sumar_dias_habiles,
)
from habilmente.festivos import (
    Festivo,
    TipoFestivo,
    es_festivo,
    fechas_festivas,
    festivos,
    nombre_festivo,
)
from habilmente.pascua import domingo_de_pascua

try:
    __version__ = version("habilmente")
except PackageNotFoundError:  # pragma: no cover - solo ocurre sin instalar el paquete
    __version__ = "0.0.0"

__all__ = [
    "AÑO_MAXIMO",
    "AÑO_MINIMO",
    "CALENDARIO_ESTANDAR",
    "Calendario",
    "ConfigSabados",
    "Festivo",
    "TipoFestivo",
    "__version__",
    "anterior_dia_habil",
    "dia_habil_del_mes",
    "dias_habiles_del_mes",
    "dias_habiles_entre",
    "domingo_de_pascua",
    "es_dia_habil",
    "es_festivo",
    "fechas_festivas",
    "festivos",
    "listar_dias_habiles",
    "nombre_festivo",
    "siguiente_dia_habil",
    "sumar_dias_habiles",
]
