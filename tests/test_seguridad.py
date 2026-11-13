"""Pruebas de ataque: entradas maliciosas, fuzzing, denegación de servicio y concurrencia.

Modelo de amenaza: habilmente es una librería de cálculo puro, sin red, sin archivos y
sin ejecución de código externo. Los riesgos realistas son (1) entradas hostiles que
provoquen errores inesperados, resultados falsos o consumo desmedido de CPU o memoria,
(2) salidas que inyecten códigos de control en la terminal y (3) cambios en el estado
compartido entre llamadas. Cada sección cubre uno de esos riesgos.
"""

import ast
import contextlib
import io
import itertools
import re
import threading
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

import habilmente as h
from habilmente import AÑO_MAXIMO, AÑO_MINIMO, Calendario
from habilmente.cli import main
from habilmente.festivos import _festivos_del_año

CODIGO_FUENTE = Path(h.__file__).parent
ERRORES_ESPERADOS = (TypeError, ValueError)

# Cualquier cosa que alguien pueda pasar por error o con mala intención.
BASURA = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.integers(min_value=-(10**50), max_value=10**50),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(),
    st.binary(),
    st.dates(),
    st.datetimes(),
    st.timedeltas(),
    st.lists(st.integers(), max_size=5),
    st.dictionaries(st.text(max_size=3), st.integers(), max_size=3),
    st.just(object()),
    st.just(float("nan")),
)


# --- 1. Objetos que mienten ---------------------------------------------------------------


class EnteroMentiroso(int):
    """Entero que dice estar siempre dentro de cualquier rango."""

    def __ge__(self, otro: object) -> bool:
        return True

    def __le__(self, otro: object) -> bool:
        return True

    def __lt__(self, otro: object) -> bool:
        return False

    def __gt__(self, otro: object) -> bool:
        return False

    def __eq__(self, otro: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 1


def test_entero_mentiroso_no_evade_el_rango_de_años() -> None:
    tamaño_antes = _festivos_del_año.cache_info().currsize
    for año in (3000, 1500, 10**9):
        with pytest.raises(ValueError, match="fuera de rango"):
            h.festivos(EnteroMentiroso(año))
    # La caché no creció: nadie puede llenar la memoria con años inventados.
    assert _festivos_del_año.cache_info().currsize == tamaño_antes


def test_entero_mentiroso_en_parametros() -> None:
    with pytest.raises(ValueError, match="Posición de sábado inválida"):
        Calendario(sabados=[EnteroMentiroso(9)])
    with pytest.raises(ValueError, match="mes debe estar entre 1 y 12"):
        h.dias_habiles_del_mes(2026, EnteroMentiroso(13))
    cal = Calendario(sabados=[EnteroMentiroso(1)])
    assert cal.sabados == (1,)
    assert type(cal.sabados[0]) is int  # Se guarda un int puro, no la subclase.


def test_la_cache_de_festivos_tiene_tamaño_acotado() -> None:
    for año in range(AÑO_MINIMO, AÑO_MAXIMO + 1):
        h.festivos(año)
    assert _festivos_del_año.cache_info().currsize <= AÑO_MAXIMO - AÑO_MINIMO + 1


class FechaConDateFalso(datetime):
    def date(self) -> Any:
        return "no soy una fecha"


class FechaConAñoFalso(date):
    @property
    def year(self) -> Any:
        return "2026"


def test_subclases_de_fecha_que_mienten() -> None:
    # No se confía en .date(): se reconstruye la fecha desde año, mes y día.
    assert h.es_festivo(FechaConDateFalso(2026, 12, 25))
    with pytest.raises(TypeError):
        h.es_dia_habil(FechaConAñoFalso(2026, 1, 1))


def test_zona_horaria_que_falla_no_se_invoca() -> None:
    from datetime import tzinfo

    class ZonaRota(tzinfo):
        def utcoffset(self, _: datetime | None) -> timedelta:
            raise RuntimeError("no debería llamarse")

        def dst(self, _: datetime | None) -> timedelta:
            raise RuntimeError("no debería llamarse")

        def tzname(self, _: datetime | None) -> str:
            raise RuntimeError("no debería llamarse")

    assert h.es_festivo(datetime(2026, 12, 25, 12, tzinfo=ZonaRota()))


# --- 2. Fuzzing: solo errores controlados -------------------------------------------------

FUNCIONES_DE_FECHA: list[Callable[[Any], object]] = [
    h.es_festivo,
    h.nombre_festivo,
    h.es_dia_habil,
    h.explicar_dia,
    h.siguiente_dia_habil,
    h.anterior_dia_habil,
]
FUNCIONES_DE_AÑO: list[Callable[[Any], object]] = [
    h.festivos,
    h.fechas_festivas,
    h.domingo_de_pascua,
]


@given(BASURA)
def test_fuzzing_funciones_de_un_argumento(valor: object) -> None:
    for funcion in (*FUNCIONES_DE_FECHA, *FUNCIONES_DE_AÑO):
        with contextlib.suppress(*ERRORES_ESPERADOS):
            funcion(valor)


@given(BASURA, BASURA, BASURA)
def test_fuzzing_funciones_de_varios_argumentos(a: object, b: object, c: object) -> None:
    llamadas: list[Callable[[], object]] = [
        lambda: h.sumar_dias_habiles(a, b),  # type: ignore[arg-type]
        lambda: h.dias_habiles_entre(a, b),  # type: ignore[arg-type]
        lambda: h.listar_dias_habiles(a, b),  # type: ignore[arg-type]
        lambda: h.dias_habiles_del_mes(a, b),  # type: ignore[arg-type]
        lambda: h.dia_habil_del_mes(a, b, c),  # type: ignore[arg-type]
    ]
    for llamada in llamadas:
        with contextlib.suppress(*ERRORES_ESPERADOS):
            llamada()


@given(BASURA, BASURA, BASURA)
def test_fuzzing_constructor_de_calendario(sabados: object, no: object, si: object) -> None:
    with contextlib.suppress(*ERRORES_ESPERADOS):
        Calendario(
            sabados=sabados,  # type: ignore[arg-type]
            dias_no_habiles_extra=no,  # type: ignore[arg-type]
            dias_habiles_extra=si,  # type: ignore[arg-type]
        )


@given(st.dates(date(AÑO_MINIMO, 1, 1), date(AÑO_MAXIMO, 12, 31)), st.integers())
def test_fuzzing_sumar_con_cualquier_entero(dia: date, n: int) -> None:
    try:
        resultado = h.sumar_dias_habiles(dia, n)
    except ValueError:
        return
    assert AÑO_MINIMO <= resultado.year <= AÑO_MAXIMO
    assert h.es_dia_habil(resultado)


# --- 3. Fuzzing del comando de terminal ---------------------------------------------------

PALABRAS = st.one_of(
    st.sampled_from(
        [
            "festivos",
            "es-habil",
            "sumar",
            "siguiente",
            "anterior",
            "entre",
            "mes",
            "--formato",
            "json",
            "csv",
            "texto",
            "--sabados",
            "1,-1",
            "todos",
            "--n",
            "--habiles",
            "--no-habiles",
            "2026-11-02",
            "2199-12-31",
            "1984-01-01",
            "2027",
            "-1",
            "0",
            "13",
            "--help",
            "--version",
        ]
    ),
    st.text(max_size=30),
    st.text(alphabet="\x1b[]0123456789;m\x00\n\r\t-", max_size=20),
)


@given(st.lists(PALABRAS, max_size=6))
def test_fuzzing_cli(argumentos: list[str]) -> None:
    salida, errores = io.StringIO(), io.StringIO()
    with pytest.MonkeyPatch.context() as parche:
        parche.setattr("sys.stderr", errores)
        parche.setattr("sys.stdout", salida)
        try:
            codigo: object = main(argumentos, salida)
        except SystemExit as fin:
            codigo = fin.code
    assert codigo in (0, 1, 2, None)
    texto_error = errores.getvalue()
    assert "Traceback" not in texto_error
    # Ningún código de control del usuario llega crudo a la terminal.
    assert "\x1b" not in texto_error
    assert "\x1b" not in salida.getvalue()


def test_cli_neutraliza_secuencias_de_escape(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["es-habil", "\x1b[2J\x1b[31mHACK"], io.StringIO())
    error = capsys.readouterr().err
    assert "\x1b" not in error
    assert r"\x1b[2J" in error


def test_cli_recorta_argumentos_gigantes(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["sumar", "2026-01-01", "9" * 100_000], io.StringIO())
    error = capsys.readouterr().err
    assert len(error) < 1_000
    assert "100000 caracteres" in error


def test_cli_recorta_argumentos_sobrantes(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["2027", *(["\x1b[31mx"] * 500)], io.StringIO())
    error = capsys.readouterr().err
    assert "mensaje recortado" in error
    assert "\x1b" not in error


@pytest.mark.parametrize("texto", ["٢٠٢٦-١١-٠٢", "２０２６-11-02", "2026-11-0２"])
def test_cli_rechaza_digitos_de_otros_alfabetos(texto: str) -> None:
    with pytest.raises(SystemExit) as fin:
        main(["es-habil", texto], io.StringIO())
    assert fin.value.code == 2


def test_cli_rechaza_enteros_unicode() -> None:
    with pytest.raises(SystemExit) as fin:
        main(["sumar", "2026-01-01", "٣"], io.StringIO())
    assert fin.value.code == 2


# --- 4. Denegación de servicio (CPU y memoria) --------------------------------------------


def _cronometrar(funcion: Callable[[], object]) -> float:
    inicio = time.perf_counter()
    with contextlib.suppress(*ERRORES_ESPERADOS):
        funcion()
    return time.perf_counter() - inicio


@pytest.mark.parametrize("n", [10**18, -(10**18), 10**4000, -(10**4000)])
def test_n_gigantesco_termina_rapido(n: int) -> None:
    # Se recorre a lo sumo un año por iteración: termina en milisegundos.
    assert _cronometrar(lambda: h.sumar_dias_habiles(date(2026, 1, 1), n)) < 1.0


def test_rangos_maximos_terminan_rapido() -> None:
    inicio, fin = date(AÑO_MINIMO, 1, 1), date(AÑO_MAXIMO, 12, 31)
    assert _cronometrar(lambda: h.listar_dias_habiles(inicio, fin)) < 2.0
    assert _cronometrar(lambda: h.dias_habiles_entre(inicio, fin)) < 2.0
    assert _cronometrar(lambda: h.dia_habil_del_mes(2026, 1, 10**100)) < 0.1


def test_iterable_infinito_de_sabados_no_bloquea() -> None:
    with pytest.raises(ValueError, match="repetidas"):
        Calendario(sabados=itertools.repeat(1))
    with pytest.raises(ValueError, match="Posición de sábado inválida"):
        Calendario(sabados=itertools.count(1))


def test_iterable_infinito_de_fechas_no_bloquea() -> None:
    with pytest.raises(ValueError, match="iterable infinito"):
        Calendario(dias_no_habiles_extra=itertools.repeat(date(2026, 1, 1)))
    with pytest.raises(TypeError):
        Calendario(dias_habiles_extra=itertools.count())  # type: ignore[arg-type]


def test_muchas_fechas_extra_se_deduplican() -> None:
    fechas = [date(2026, 1, 2)] * 500_000
    cal = Calendario(dias_no_habiles_extra=fechas)
    assert cal.dias_no_habiles_extra == frozenset({date(2026, 1, 2)})


# --- 5. Estado compartido y concurrencia --------------------------------------------------


def test_el_estado_compartido_no_se_puede_alterar() -> None:
    lista = h.festivos(2026)
    with pytest.raises((TypeError, AttributeError)):
        lista[0] = None  # type: ignore[index]
    with pytest.raises(AttributeError):
        h.fechas_festivas(2026).add(date(2026, 1, 2))  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        h.CALENDARIO_ESTANDAR.sabados = "todos"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        h.CALENDARIO_ESTANDAR.dias_habiles_extra.add(date(2026, 1, 1))  # type: ignore[attr-defined]
    assert h.festivos(2026) == lista
    assert h.es_dia_habil(date(2026, 1, 3)) is False


def test_concurrencia_da_los_mismos_resultados() -> None:
    cal = Calendario(sabados=[1, -1])
    esperado = {año: len(cal.dias_habiles_del_mes(año, 6)) for año in range(1984, 2200)}
    resultados: list[dict[int, int]] = []
    fallos: list[BaseException] = []

    def trabajo() -> None:
        try:
            nuevo = Calendario(sabados=[1, -1])
            resultados.append({a: len(nuevo.dias_habiles_del_mes(a, 6)) for a in esperado})
        except BaseException as error:  # pragma: no cover - solo si algo falla
            fallos.append(error)

    hilos = [threading.Thread(target=trabajo) for _ in range(16)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert not fallos
    assert all(r == esperado for r in resultados)


# --- 6. Guardas estáticas sobre el código fuente ------------------------------------------

MODULOS_PROHIBIDOS = {
    "os", "subprocess", "socket", "urllib", "http", "requests", "pickle", "marshal",
    "shelve", "ctypes", "importlib", "shutil", "tempfile", "multiprocessing",
}  # fmt: skip
LLAMADAS_PROHIBIDAS = {"eval", "exec", "compile", "__import__", "open", "input"}


def _archivos_fuente() -> list[Path]:
    return sorted(CODIGO_FUENTE.rglob("*.py"))


@pytest.mark.parametrize("archivo", _archivos_fuente(), ids=lambda p: p.name)
def test_sin_imports_ni_llamadas_peligrosas(archivo: Path) -> None:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres = {alias.name.split(".")[0] for alias in nodo.names}
        elif isinstance(nodo, ast.ImportFrom):
            nombres = {(nodo.module or "").split(".")[0]}
        else:
            nombres = set()
        # importlib.metadata solo se usa para leer la versión instalada del paquete.
        if archivo.name == "__init__.py" and isinstance(nodo, ast.ImportFrom):
            nombres -= {"importlib"}
        assert not nombres & MODULOS_PROHIBIDOS, f"{archivo.name}: {nombres}"
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id not in LLAMADAS_PROHIBIDAS, f"{archivo.name}: {nodo.func.id}"


def test_expresiones_regulares_sin_riesgo_de_redos() -> None:
    # Los patrones son lineales (sin cuantificadores anidados) y están anclados.
    from habilmente import cli

    for patron in (cli._PATRON_FECHA, cli._PATRON_ENTERO):
        assert not re.search(r"\)[*+]|\*\)|\+\)", patron.pattern)
        inicio = time.perf_counter()
        patron.fullmatch("9" * 100_000 + "x")
        assert time.perf_counter() - inicio < 0.1


@given(st.lists(BASURA, max_size=8))
def test_fuzzing_pandas_con_columnas_basura(valores: list[object]) -> None:
    pd = pytest.importorskip("pandas")
    from habilmente import pandas as hp

    columna = pd.Series(valores, dtype=object)
    for funcion in (hp.es_dia_habil, hp.es_festivo, hp.nombre_festivo):
        with contextlib.suppress(*ERRORES_ESPERADOS):
            funcion(columna)
    with contextlib.suppress(*ERRORES_ESPERADOS):
        hp.dias_habiles_entre(columna, columna)
