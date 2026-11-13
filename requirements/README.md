# Dependencias fijadas

El CI instala solo estas versiones exactas, verificadas por hash (`pip install --require-hashes`).
Así, una versión maliciosa publicada en PyPI no entra al CI sin pasar por un cambio revisado.
Los archivos sirven para Linux, Windows y macOS y para Python 3.11 a 3.13.

| Archivo | Uso |
|---|---|
| `desarrollo.txt` | Tests, lint, tipos y auditoría con pandas 3 |
| `desarrollo-pandas2.txt` | Lo mismo con pandas 2 (`restriccion-pandas2.txt`) |
| `construccion.txt` | Construir y publicar el paquete (`construccion.in`) |

Para regenerarlos después de cambiar `pyproject.toml`:

```bash
pip install uv
uv pip compile --universal --python-version 3.11 --generate-hashes pyproject.toml --extra dev -o requirements/desarrollo.txt
uv pip compile --universal --python-version 3.11 --generate-hashes pyproject.toml --extra dev -c requirements/restriccion-pandas2.txt -o requirements/desarrollo-pandas2.txt
uv pip compile --universal --python-version 3.11 --generate-hashes requirements/construccion.in -o requirements/construccion.txt
```

Dependabot propone las actualizaciones cada semana, después de 7 días de espera.
