import csv
import io
import json
import runpy
from datetime import date

import pytest

import habilmente as h
from habilmente.cli import ERROR, EXITO, NO_HABIL, main


def ejecutar(*argumentos: str) -> tuple[int, str]:
    salida = io.StringIO()
    codigo = main(list(argumentos), salida)
    return codigo, salida.getvalue()


# --- festivos -----------------------------------------------------------------------------


def test_festivos_en_texto() -> None:
    codigo, texto = ejecutar("festivos", "2027")
    assert codigo == EXITO
    assert texto.startswith("Festivos de Colombia en 2027 (19)")
    assert "2027-07-12  lunes      Nuestra Señora del Rosario de Chiquinquirá" in texto
    assert "(se traslada del 2027-07-09)" in texto
    assert "2027-05-01  sábado     Día del Trabajo\n" in texto


def test_atajo_con_solo_el_año() -> None:
    assert ejecutar("2027") == ejecutar("festivos", "2027")


def test_sin_argumentos_muestra_el_año_en_curso() -> None:
    codigo, texto = ejecutar()
    assert codigo == EXITO
    assert texto.startswith(f"Festivos de Colombia en {date.today().year}")


def test_festivos_en_json() -> None:
    codigo, texto = ejecutar("2025", "--formato", "json")
    datos = json.loads(texto)
    assert codigo == EXITO
    assert datos["año"] == 2025
    assert len(datos["festivos"]) == 18
    san_pedro = next(f for f in datos["festivos"] if f["nombre"] == "San Pedro y San Pablo")
    assert san_pedro == {
        "fecha": "2025-06-30",
        "dia_semana": "lunes",
        "nombre": "San Pedro y San Pablo",
        "tipo": "trasladable",
        "fecha_original": "2025-06-29",
        "trasladado": True,
    }
    assert "Año Nuevo" in texto  # Sin escapar tildes ni eñes.


def test_festivos_en_csv() -> None:
    _, texto = ejecutar("2026", "--formato", "csv")
    filas = list(csv.DictReader(io.StringIO(texto)))
    assert len(filas) == 19
    assert filas[0]["fecha"] == "2026-01-01"
    assert {fila["fecha"] for fila in filas} == {d.isoformat() for d in h.fechas_festivas(2026)}


# --- es-habil -----------------------------------------------------------------------------


def test_es_habil_codigos_de_salida() -> None:
    codigo, texto = ejecutar("es-habil", "2026-11-02")
    assert codigo == NO_HABIL
    assert texto == "2026-11-02 (lunes): No hábil: festivo (Día de Todos los Santos)\n"

    codigo, texto = ejecutar("es-habil", "2026-11-03")
    assert codigo == EXITO
    assert texto == "2026-11-03 (martes): Hábil: día entre semana\n"


@pytest.mark.parametrize("sabados", ["1,-1", "-1", " 1 , -1 ", "todos", "TODOS"])
def test_es_habil_con_sabados(sabados: str) -> None:
    codigo, _ = ejecutar("es-habil", "2026-01-31", "--sabados", sabados)
    assert codigo == EXITO


def test_sabados_ninguno() -> None:
    codigo, texto = ejecutar("es-habil", "2026-01-31", "--sabados", "ninguno")
    assert codigo == NO_HABIL
    assert texto.endswith("No hábil: sábado\n")


def test_es_habil_json() -> None:
    codigo, texto = ejecutar(
        "es-habil", "2026-12-08", "--habiles", "2026-12-08", "--formato", "json"
    )
    assert codigo == EXITO
    assert json.loads(texto) == {
        "fecha": "2026-12-08",
        "dia_semana": "martes",
        "es_habil": True,
        "motivo": "día hábil extra del calendario",
    }


def test_dias_no_habiles_extra() -> None:
    codigo, texto = ejecutar("es-habil", "2026-12-24", "--no-habiles", "2026-12-24,2026-12-31")
    assert codigo == NO_HABIL
    assert "día no hábil extra" in texto


# --- sumar, siguiente, anterior, entre ----------------------------------------------------


@pytest.mark.parametrize(
    ("argumentos", "esperado"),
    [
        (("sumar", "2026-10-30", "10"), "2026-11-17"),
        (("sumar", "2026-10-30", "-3"), "2026-10-27"),
        (("sumar", "2026-10-31", "0"), "2026-11-03"),
        (("siguiente", "2026-12-31"), "2027-01-04"),
        (("anterior", "2027-01-04"), "2026-12-31"),
        (("siguiente", "2026-01-30", "--sabados", "1,-1"), "2026-01-31"),
        (("entre", "2026-10-01", "2026-10-31"), "20"),
        (("entre", "2026-10-31", "2026-10-01"), "-20"),
    ],
)
def test_comandos_de_calculo(argumentos: tuple[str, ...], esperado: str) -> None:
    assert ejecutar(*argumentos) == (EXITO, f"{esperado}\n")


def test_sumar_json() -> None:
    _, texto = ejecutar("sumar", "2026-10-30", "1", "--formato", "json")
    assert json.loads(texto) == {
        "fecha": "2026-10-30",
        "n": 1,
        "resultado": {"fecha": "2026-11-03", "dia_semana": "martes"},
    }


@pytest.mark.parametrize("comando", ["siguiente", "anterior"])
def test_siguiente_y_anterior_json(comando: str) -> None:
    _, texto = ejecutar(comando, "2026-11-02", "--formato", "json")
    datos = json.loads(texto)
    assert datos["fecha"] == "2026-11-02"
    assert datos["resultado"]["fecha"] in {"2026-11-03", "2026-10-30"}


def test_entre_json() -> None:
    _, texto = ejecutar("entre", "2026-10-01", "2026-10-31", "--formato", "json")
    assert json.loads(texto) == {"inicio": "2026-10-01", "fin": "2026-10-31", "dias_habiles": 20}


# --- mes ----------------------------------------------------------------------------------


def test_mes_en_texto() -> None:
    codigo, texto = ejecutar("mes", "2026", "11")
    lineas = texto.splitlines()
    assert codigo == EXITO
    assert len(lineas) == 19
    assert lineas[0] == "2026-11-03  martes"


def test_mes_posicion() -> None:
    assert ejecutar("mes", "2026", "11", "--n", "5") == (EXITO, "2026-11-09  lunes\n")
    assert ejecutar("mes", "2026", "11", "--n", "-1") == (EXITO, "2026-11-30  lunes\n")


def test_mes_json_y_csv() -> None:
    _, texto = ejecutar("mes", "2026", "1", "--sabados", "1,-1", "--formato", "json")
    datos = json.loads(texto)
    assert datos["dias_habiles"][1] == {
        "fecha": "2026-01-03",
        "dia_semana": "sábado",
        "posicion": 2,
    }

    _, texto = ejecutar("mes", "2026", "1", "--formato", "csv")
    filas = list(csv.DictReader(io.StringIO(texto)))
    assert filas[0] == {"fecha": "2026-01-02", "dia_semana": "viernes", "posicion": "1"}


def test_csv_vacio_no_escribe_nada() -> None:
    # Un mes sin días hábiles (todos declarados no hábiles) da un CSV vacío.
    no_habiles = ",".join(d.isoformat() for d in h.dias_habiles_del_mes(2026, 2))
    assert ejecutar("mes", "2026", "2", "--no-habiles", no_habiles, "--formato", "csv") == (
        EXITO,
        "",
    )


# --- Errores ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argumentos", "mensaje"),
    [
        (("es-habil", "02/11/2026"), "use el formato AAAA-MM-DD"),
        (("es-habil", "20261102"), "use el formato AAAA-MM-DD"),
        (("es-habil", "2026-02-30"), "no existe"),
        (("sumar", "2026-01-01", "x"), "número entero"),
        (("sumar", "2026-01-01", "1.5"), "número entero"),
        (("festivos", "2027", "--formato", "xml"), "--formato"),
        (("es-habil", "2026-01-01", "--sabados", "1,primero"), "número entero"),
        (("es-habil", "2026-01-01", "--no-habiles", "2026/12/24"), "AAAA-MM-DD"),
        (("comando-raro",), "invalid choice"),
        (("es-habil",), "fecha"),
    ],
)
def test_errores_de_argumentos(
    argumentos: tuple[str, ...], mensaje: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as salida:
        ejecutar(*argumentos)
    assert salida.value.code == ERROR
    error = capsys.readouterr().err
    assert mensaje in error
    assert "Traceback" not in error


@pytest.mark.parametrize(
    ("argumentos", "mensaje"),
    [
        (("1950",), "Año fuera de rango"),
        (("es-habil", "2026-01-03", "--sabados", "6"), "Posición de sábado inválida"),
        (("siguiente", "2199-12-31"), "queda fuera del rango"),
        (("mes", "2026", "13"), "mes debe estar entre 1 y 12"),
        (("mes", "2026", "11", "--n", "0"), "tiene 19 días hábiles"),
        (
            ("es-habil", "2026-01-02", "--habiles", "2026-01-02", "--no-habiles", "2026-01-02"),
            "a la vez",
        ),
    ],
)
def test_errores_de_la_libreria(
    argumentos: tuple[str, ...], mensaje: str, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo, salida = ejecutar(*argumentos)
    assert codigo == ERROR
    assert salida == ""
    error = capsys.readouterr().err
    assert error.startswith("habilmente: error: ")
    assert mensaje in error


def test_version_y_ayuda(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        ejecutar("--version")
    assert salida.value.code == 0
    assert capsys.readouterr().out.startswith("habilmente ")

    with pytest.raises(SystemExit):
        ejecutar("--help")
    ayuda = capsys.readouterr().out
    assert "es-habil" in ayuda
    assert "Atajo" in ayuda


def test_solo_opciones_sin_comando(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        ejecutar("--formato", "json")
    assert salida.value.code == ERROR
    assert "invalid choice: 'json'" in capsys.readouterr().err


def test_python_m_habilmente(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["habilmente", "siguiente", "2026-12-31"])
    with pytest.raises(SystemExit) as salida:
        runpy.run_module("habilmente", run_name="__main__")
    assert salida.value.code == EXITO
    assert capsys.readouterr().out == "2027-01-04\n"
