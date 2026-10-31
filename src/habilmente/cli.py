"""Comando de terminal ``habilmente``.

Ejemplos::

    habilmente                      # festivos del año en curso
    habilmente 2027 --formato json
    habilmente es-habil 2026-11-02 --sabados 1,-1
    habilmente sumar 2026-10-30 10
    habilmente entre 2026-10-01 2026-10-31
    habilmente mes 2026 11 --n 5

Códigos de salida: 0 éxito (en ``es-habil``, el día es hábil), 1 el día no es hábil
(solo ``es-habil``), 2 error en los argumentos.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections.abc import Sequence
from datetime import date
from typing import Any, NoReturn, TextIO

from habilmente import __version__
from habilmente._textos import DIAS_SEMANA
from habilmente.calendario import Calendario, ConfigSabados
from habilmente.festivos import festivos

_PATRON_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")
_PATRON_ENTERO = re.compile(r"[+-]?\d+")
_COMANDOS = frozenset({"festivos", "es-habil", "sumar", "siguiente", "anterior", "entre", "mes"})

EXITO = 0
NO_HABIL = 1
ERROR = 2


# --- Conversión de argumentos -------------------------------------------------------------


def _fecha(texto: str) -> date:
    if not _PATRON_FECHA.fullmatch(texto):
        raise argparse.ArgumentTypeError(
            f"fecha inválida {texto!r}: use el formato AAAA-MM-DD, por ejemplo 2026-11-02"
        )
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"la fecha {texto!r} no existe") from None


def _entero(texto: str) -> int:
    if not _PATRON_ENTERO.fullmatch(texto):
        raise argparse.ArgumentTypeError(f"se esperaba un número entero, se recibió {texto!r}")
    return int(texto)


def _lista_fechas(texto: str) -> list[date]:
    return [_fecha(parte.strip()) for parte in texto.split(",") if parte.strip()]


def _sabados(texto: str) -> ConfigSabados:
    valor = texto.strip().lower()
    if valor == "todos":
        return "todos"
    if valor == "ninguno":
        return None
    return [_entero(parte.strip()) for parte in valor.split(",") if parte.strip()]


# --- Construcción del parser --------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(ERROR, f"{self.prog}: error: {message}\n")


def _crear_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="habilmente",
        description="Festivos de Colombia y días hábiles con calendarios configurables.",
        epilog="Sin comando muestra los festivos del año en curso. "
        "Atajo: 'habilmente 2027' equivale a 'habilmente festivos 2027'.",
    )
    parser.add_argument("--version", action="version", version=f"habilmente {__version__}")

    calendario = _Parser(add_help=False)
    grupo = calendario.add_argument_group("calendario laboral")
    grupo.add_argument(
        "--sabados",
        type=_sabados,
        default=None,
        metavar="CONFIG",
        help='sábados hábiles: "todos", "ninguno" o posiciones como "1,-1" '
        "(primero y último del mes)",
    )
    grupo.add_argument(
        "--no-habiles",
        type=_lista_fechas,
        default=[],
        metavar="FECHAS",
        help="fechas extra no hábiles separadas por coma",
    )
    grupo.add_argument(
        "--habiles",
        type=_lista_fechas,
        default=[],
        metavar="FECHAS",
        help="fechas que sí se trabajan aunque sean festivo o fin de semana",
    )

    def formato(*opciones: str) -> _Parser:
        padre = _Parser(add_help=False)
        padre.add_argument("--formato", choices=opciones, default="texto", help="formato de salida")
        return padre

    texto_json = formato("texto", "json")
    tabular = formato("texto", "json", "csv")

    sub = parser.add_subparsers(
        dest="comando", metavar="COMANDO", parser_class=_Parser, required=True
    )

    p = sub.add_parser("festivos", parents=[tabular], help="lista los festivos de un año")
    p.add_argument("año", type=_entero, help="año, por ejemplo 2027")

    p = sub.add_parser(
        "es-habil",
        parents=[calendario, texto_json],
        help="indica si una fecha es hábil (código de salida 0 si lo es, 1 si no)",
    )
    p.add_argument("fecha", type=_fecha, help="fecha AAAA-MM-DD")

    p = sub.add_parser(
        "sumar", parents=[calendario, texto_json], help="suma (o resta) días hábiles"
    )
    p.add_argument("fecha", type=_fecha, help="fecha de partida AAAA-MM-DD (no se cuenta)")
    p.add_argument("n", type=_entero, help="días hábiles; negativo para retroceder")

    for nombre, ayuda in (
        ("siguiente", "primer día hábil después de la fecha"),
        ("anterior", "último día hábil antes de la fecha"),
    ):
        p = sub.add_parser(nombre, parents=[calendario, texto_json], help=ayuda)
        p.add_argument("fecha", type=_fecha, help="fecha AAAA-MM-DD")

    p = sub.add_parser(
        "entre",
        parents=[calendario, texto_json],
        help="cuenta días hábiles después de INICIO y hasta FIN",
    )
    p.add_argument("inicio", type=_fecha, help="fecha inicial AAAA-MM-DD (no se cuenta)")
    p.add_argument("fin", type=_fecha, help="fecha final AAAA-MM-DD (se cuenta)")

    p = sub.add_parser(
        "mes", parents=[calendario, tabular], help="lista los días hábiles de un mes"
    )
    p.add_argument("año", type=_entero, help="año")
    p.add_argument("mes", type=_entero, help="mes de 1 a 12")
    p.add_argument(
        "--n",
        type=_entero,
        default=None,
        help="devuelve solo el n-ésimo día hábil (1 el primero, -1 el último)",
    )
    return parser


# --- Ejecución ----------------------------------------------------------------------------


def _con_dia(fecha: date) -> dict[str, Any]:
    return {"fecha": fecha.isoformat(), "dia_semana": DIAS_SEMANA[fecha.weekday()]}


def _escribir_json(datos: object, salida: TextIO) -> None:
    json.dump(datos, salida, ensure_ascii=False, indent=2)
    salida.write("\n")


def _escribir_csv(filas: list[dict[str, Any]], salida: TextIO) -> None:
    if not filas:
        return
    escritor = csv.DictWriter(salida, fieldnames=list(filas[0]), lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(filas)


def _cmd_festivos(args: argparse.Namespace, salida: TextIO) -> int:
    lista = festivos(args.año)
    filas = [
        {
            **_con_dia(f.fecha),
            "nombre": f.nombre,
            "tipo": f.tipo.value,
            "fecha_original": f.fecha_original.isoformat(),
            "trasladado": f.trasladado,
        }
        for f in lista
    ]
    if args.formato == "json":
        _escribir_json({"año": args.año, "festivos": filas}, salida)
    elif args.formato == "csv":
        _escribir_csv(filas, salida)
    else:
        salida.write(f"Festivos de Colombia en {args.año} ({len(lista)})\n\n")
        for f in lista:
            nota = f" (se traslada del {f.fecha_original.isoformat()})" if f.trasladado else ""
            dia = DIAS_SEMANA[f.fecha.weekday()]
            salida.write(f"{f.fecha.isoformat()}  {dia:<9}  {f.nombre}{nota}\n")
    return EXITO


def _calendario(args: argparse.Namespace) -> Calendario:
    return Calendario(
        sabados=args.sabados,
        dias_no_habiles_extra=args.no_habiles,
        dias_habiles_extra=args.habiles,
    )


def _cmd_es_habil(args: argparse.Namespace, salida: TextIO) -> int:
    cal = _calendario(args)
    habil = cal.es_dia_habil(args.fecha)
    explicacion = cal.explicar_dia(args.fecha)
    if args.formato == "json":
        motivo = explicacion.split(": ", 1)[1]
        _escribir_json({**_con_dia(args.fecha), "es_habil": habil, "motivo": motivo}, salida)
    else:
        dia = DIAS_SEMANA[args.fecha.weekday()]
        salida.write(f"{args.fecha.isoformat()} ({dia}): {explicacion}\n")
    return EXITO if habil else NO_HABIL


def _escribir_fecha(
    resultado: date, extra: dict[str, Any], args: argparse.Namespace, salida: TextIO
) -> None:
    if args.formato == "json":
        _escribir_json({**extra, "resultado": _con_dia(resultado)}, salida)
    else:
        salida.write(f"{resultado.isoformat()}\n")


def _cmd_sumar(args: argparse.Namespace, salida: TextIO) -> int:
    resultado = _calendario(args).sumar_dias_habiles(args.fecha, args.n)
    _escribir_fecha(resultado, {"fecha": args.fecha.isoformat(), "n": args.n}, args, salida)
    return EXITO


def _cmd_siguiente(args: argparse.Namespace, salida: TextIO) -> int:
    resultado = _calendario(args).siguiente_dia_habil(args.fecha)
    _escribir_fecha(resultado, {"fecha": args.fecha.isoformat()}, args, salida)
    return EXITO


def _cmd_anterior(args: argparse.Namespace, salida: TextIO) -> int:
    resultado = _calendario(args).anterior_dia_habil(args.fecha)
    _escribir_fecha(resultado, {"fecha": args.fecha.isoformat()}, args, salida)
    return EXITO


def _cmd_entre(args: argparse.Namespace, salida: TextIO) -> int:
    total = _calendario(args).dias_habiles_entre(args.inicio, args.fin)
    if args.formato == "json":
        datos = {"inicio": args.inicio.isoformat(), "fin": args.fin.isoformat()}
        _escribir_json({**datos, "dias_habiles": total}, salida)
    else:
        salida.write(f"{total}\n")
    return EXITO


def _cmd_mes(args: argparse.Namespace, salida: TextIO) -> int:
    cal = _calendario(args)
    if args.n is not None:
        dias = [(args.n, cal.dia_habil_del_mes(args.año, args.mes, args.n))]
    else:
        dias = list(enumerate(cal.dias_habiles_del_mes(args.año, args.mes), start=1))
    filas = [{**_con_dia(dia), "posicion": posicion} for posicion, dia in dias]
    if args.formato == "json":
        _escribir_json({"año": args.año, "mes": args.mes, "dias_habiles": filas}, salida)
    elif args.formato == "csv":
        _escribir_csv(filas, salida)
    else:
        for fila in filas:
            salida.write(f"{fila['fecha']}  {fila['dia_semana']}\n")
    return EXITO


_EJECUTORES = {
    "festivos": _cmd_festivos,
    "es-habil": _cmd_es_habil,
    "sumar": _cmd_sumar,
    "siguiente": _cmd_siguiente,
    "anterior": _cmd_anterior,
    "entre": _cmd_entre,
    "mes": _cmd_mes,
}


def main(argv: Sequence[str] | None = None, salida: TextIO | None = None) -> int:
    """Punto de entrada del comando ``habilmente``.

    Args:
        argv: Argumentos sin el nombre del programa; por defecto ``sys.argv[1:]``.
        salida: Dónde escribir el resultado; por defecto la salida estándar.

    Returns:
        Código de salida: 0 éxito, 1 día no hábil (solo ``es-habil``), 2 error.
    """
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if not argumentos:
        argumentos = ["festivos", str(date.today().year)]
    elif argumentos[0] not in _COMANDOS and _PATRON_ENTERO.fullmatch(argumentos[0]):
        argumentos.insert(0, "festivos")

    args = _crear_parser().parse_args(argumentos)

    try:
        return _EJECUTORES[args.comando](args, salida or sys.stdout)
    except (TypeError, ValueError) as error:
        sys.stderr.write(f"habilmente: error: {error}\n")
        return ERROR
