"""Coherencia entre lo que promete la documentación y lo que declara el paquete instalado."""

import re
from importlib.metadata import metadata
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DATOS = metadata("habilmente")


def test_extra_pandas_declarado() -> None:
    assert "pandas" in (DATOS.get_all("Provides-Extra") or [])
    requisitos = DATOS.get_all("Requires-Dist") or []
    patron = re.compile(r"""pandas>=2\.0\s*;\s*extra\s*==\s*["']pandas["']""")
    assert any(patron.fullmatch(r) for r in requisitos), requisitos


def test_sin_dependencias_obligatorias() -> None:
    requisitos = DATOS.get_all("Requires-Dist") or []
    assert all("extra ==" in r for r in requisitos), requisitos


@pytest.mark.parametrize(
    "archivo",
    [RAIZ / "README.md", *sorted((RAIZ / "src" / "habilmente").glob("*.py"))],
    ids=lambda p: p.name,
)
def test_todo_extra_mencionado_existe(archivo: Path) -> None:
    # Si la documentación o un mensaje de error dice pip install "habilmente[x]",
    # el extra x tiene que existir; si no, pip lo ignora sin instalar nada.
    mencionados = set(re.findall(r"habilmente\[(\w+)\]", archivo.read_text(encoding="utf-8")))
    declarados = set(DATOS.get_all("Provides-Extra") or [])
    assert mencionados <= declarados, f"{archivo.name}: {mencionados - declarados}"
