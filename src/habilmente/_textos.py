"""Textos fijos en español, independientes del idioma configurado en el sistema."""

from __future__ import annotations

DIAS_SEMANA: tuple[str, ...] = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
"""Nombres de los días indexados por ``date.weekday()`` (lunes = 0)."""
