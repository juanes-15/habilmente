"""habilmente: festivos de Colombia y días hábiles con calendarios configurables."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from habilmente._validacion import AÑO_MAXIMO, AÑO_MINIMO
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
    "Festivo",
    "TipoFestivo",
    "__version__",
    "domingo_de_pascua",
    "es_festivo",
    "fechas_festivas",
    "festivos",
    "nombre_festivo",
]
