# habilmente

[![CI](https://github.com/juanes-15/habilmente/actions/workflows/ci.yml/badge.svg)](https://github.com/juanes-15/habilmente/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/habilmente)](https://pypi.org/project/habilmente/)
[![Python](https://img.shields.io/pypi/pyversions/habilmente)](https://pypi.org/project/habilmente/)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](LICENSE)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/juanes-15/habilmente/badge)](https://scorecard.dev/viewer/?uri=github.com/juanes-15/habilmente)

**Festivos de Colombia y días hábiles con calendarios laborales configurables.**
Sin dependencias, verificada contra fuentes externas y lista para pandas y Power BI.

```bash
pip install habilmente
```

## ¿Qué problema resuelve?

Saber qué días son festivos es la parte fácil. Lo que se necesita a diario es otra cosa:
¿cuándo vence un plazo de 15 días hábiles?, ¿cuántos días hábiles tiene el mes para
repartir la meta?, ¿cuál es el quinto día hábil para el cierre contable?, ¿cuántos días
hábiles tardó cada respuesta? Y la respuesta cambia según la empresa: hay quienes
trabajan el primer y el último sábado del mes, cierran el 24 de diciembre o abren un
festivo.

habilmente calcula todo eso para cualquier año entre 1984 y 2199 aplicando las leyes,
sin tablas de fechas copiadas a mano:

- **Ley 51 de 1983 (Ley Emiliani):** festivos que se trasladan al lunes siguiente.
- **Festivos que dependen de la Pascua**, calculada con el algoritmo de Meeus/Jones/Butcher.
- **Ley 2578 de 2026:** el 9 de julio (Virgen de Chiquinquirá), festivo desde 2026.

## Uso en 5 líneas

```python
>>> from datetime import date
>>> from habilmente import Calendario
>>> cal = Calendario(sabados=[1, -1])  # Se trabaja el primer y el último sábado del mes.
>>> cal.sumar_dias_habiles(date(2026, 1, 9), 15)  # Plazo de 15 días hábiles.
datetime.date(2026, 1, 31)
>>> cal.explicar_dia(date(2026, 1, 12))
'No hábil: festivo (Día de los Reyes Magos)'

```

## Funciones principales

Todas existen como funciones del módulo (calendario estándar de lunes a viernes) y como
métodos de un `Calendario` configurado.

| Función | Para qué sirve |
|---|---|
| `festivos(año)` | Los festivos del año, con nombre, regla legal y fecha original antes del traslado |
| `es_festivo(fecha)` / `nombre_festivo(fecha)` | Saber si una fecha es festivo y cuál |
| `es_dia_habil(fecha)` / `explicar_dia(fecha)` | Saber si se trabaja y por qué regla |
| `sumar_dias_habiles(fecha, n)` | Vencimiento de plazos (acepta `n` negativo) |
| `siguiente_dia_habil(fecha)` / `anterior_dia_habil(fecha)` | El día hábil más cercano |
| `dias_habiles_entre(inicio, fin)` | Tiempos de respuesta y SLA |
| `listar_dias_habiles(inicio, fin)` | Los días hábiles de un rango |
| `dias_habiles_del_mes(año, mes)` | Para repartir metas mensuales |
| `dia_habil_del_mes(año, mes, n)` | Fechas de corte: el quinto día hábil, el último (`-1`) |

```python
>>> import habilmente as h
>>> h.nombre_festivo(date(2025, 6, 30))  # Dos celebraciones el mismo día.
'Sagrado Corazón de Jesús / San Pedro y San Pablo'
>>> h.dia_habil_del_mes(2026, 12, -1)  # Último día hábil del año.
datetime.date(2026, 12, 31)
>>> len(h.dias_habiles_del_mes(2026, 11))
19

```

### Calendario configurable

```python
>>> cal = Calendario(
...     sabados=[1, -1],  # None (ninguno), "todos" o posiciones: 1..5 y -1..-5
...     dias_no_habiles_extra=[date(2026, 12, 24)],  # Cierres propios de la empresa.
...     dias_habiles_extra=[date(2026, 12, 8)],  # Festivos que sí se trabajan.
... )
>>> cal.es_dia_habil(date(2026, 12, 8))
True

```

Cuando las reglas chocan, gana la de mayor prioridad: `dias_habiles_extra` →
`dias_no_habiles_extra` → festivo → sábados configurados → lunes a viernes. Si un sábado
configurado cae en festivo, no se trabaja y la regla no se corre al sábado siguiente.

## Comando de terminal

```bash
habilmente 2027                                   # festivos del año (sin nada: el año actual)
habilmente 2027 --formato csv > festivos.csv      # también json
habilmente es-habil 2026-11-02 --sabados 1,-1     # código de salida 0 si es hábil, 1 si no
habilmente sumar 2026-10-30 10
habilmente entre 2026-10-01 2026-10-31
habilmente mes 2026 11 --n 5                      # quinto día hábil de noviembre
```

## pandas y Power BI

```bash
pip install "habilmente[pandas]"
```

```python
from habilmente.pandas import dias_habiles_entre, marcar_dias_habiles, tabla_calendario

df = marcar_dias_habiles(df, "fecha", cal)  # copia con columna es_habil
df["sla"] = dias_habiles_entre(df["radicado"], df["respuesta"])  # días hábiles por fila
dim_fecha = tabla_calendario(date(2026, 1, 1), date(2026, 12, 31), cal)
dim_fecha.to_csv("dim_fecha.csv", index=False)  # para importar en Power BI
```

- **Tabla calendario:** trae año, trimestre, mes, día de la semana en español, semana
  ISO, si es festivo y cuál, si es hábil, número de día hábil del mes y si es el último
  día hábil del mes.
- **Fechas vacías y zonas horarias:** las fechas vacías (`NaT`) dan un resultado vacío,
  sin error. Con zona horaria se usa la fecha local.
- **Fechas fuera de rango:** con `errores="coerce"` quedan vacías en vez de detener el
  proceso.
- **Velocidad:** un millón de filas se procesa en centésimas de segundo, porque cada
  fecha distinta se calcula una sola vez.

## ¿Por qué habilmente?

| | habilmente | holidays | colombian-holidays / holidays-co |
|---|:---:|:---:|:---:|
| Festivos de Colombia | ✅ | ✅ | ✅ |
| Contar y sumar días hábiles | ✅ | ✅ básico | — |
| Sábados hábiles por posición en el mes | ✅ | — | — |
| Días extra hábiles o no hábiles de la empresa | ✅ | — | — |
| Explicación de por qué un día es o no hábil | ✅ | — | — |
| N-ésimo y último día hábil del mes | ✅ | — | — |
| Integración con pandas y tabla para Power BI | ✅ | — | — |
| Comando de terminal en español | ✅ | — | — |
| Sin dependencias | ✅ | — | — |

Comparación hecha con `holidays` 0.107 y con la descripción publicada en PyPI de
`colombian-holidays` 1.0.1 y `holidays-co` 1.1.3, en noviembre de 2026.

## Cómo se verificó

- **Calendarios publicados:** 2019 a 2027 coinciden día por día. El festivo nuevo de 2026
  se confirmó con el Ministerio del Interior.
- **Dos implementaciones independientes:** todos los años de 1984 a 2199 se comparan con
  unas reglas escritas aparte en los tests y con la Pascua de `dateutil`; hasta 2100,
  también con la librería `holidays`.
- **Casos aleatorios (hypothesis):** miles de casos por ejecución comparan la librería
  contra un cálculo ingenuo día por día. También se comprueban propiedades matemáticas:
  sumar y contar son inversos, contar es antisimétrico y aditivo, y "siguiente" nunca
  salta un día hábil.
- **Calidad:** 100 % de cobertura de líneas y ramas, mypy en modo estricto, y CI en
  Linux, Windows y macOS con Python 3.11 a 3.13 y pandas 2 y 3.

## Seguridad

habilmente no usa red, no lee ni escribe archivos y no ejecuta código externo. Aun así se
prueba como si alguien quisiera romperla:

- **Fuzzing de toda la API y del comando de terminal:** solo puede fallar con errores
  controlados (`TypeError`, `ValueError`).
- **Objetos que intentan engañar la validación:** enteros que mienten en las
  comparaciones o fechas con métodos falsos no logran saltarse los rangos ni inflar la
  memoria.
- **Denegación de servicio:** números de miles de dígitos, rangos máximos e iterables
  infinitos terminan rápido con un error claro.
- **Terminal:** los códigos de control en los argumentos se neutralizan antes de mostrar
  cualquier mensaje.
- **Código fuente:** un test prohíbe `eval`, `exec`, `pickle`, `subprocess`, red y acceso
  a archivos.
- **Cadena de suministro:**
  - GitHub Actions fijadas a un commit exacto y con permisos mínimos;
  - auditoría de los workflows con zizmor, y análisis con CodeQL, bandit y pip-audit;
  - OpenSSF Scorecard y Dependabot con 7 días de espera antes de adoptar versiones nuevas;
  - publicación en PyPI con Trusted Publishing (sin tokens) y atestaciones de procedencia.

Para reportar una vulnerabilidad, revisa [SECURITY.md](SECURITY.md).

## Decisiones técnicas

- **Convención de plazos:** `sumar_dias_habiles(f, n)` y `dias_habiles_entre(a, b)` no
  cuentan el día de inicio y sí el final, como un plazo legal. Para listar un rango con
  los dos extremos incluidos está `listar_dias_habiles`.
- **No se aceptan textos como fecha**, porque `01/02` puede ser enero o febrero. En la
  terminal solo se acepta `AAAA-MM-DD`.
- **Todo es inmutable:** `Calendario`, `Festivo` y los resultados se pueden compartir
  entre hilos sin riesgo.
- **Rendimiento:** cada año se calcula una sola vez por calendario y las búsquedas son
  binarias. Sumar 20 días hábiles toma menos de un microsegundo.
- **Rango 1984–2199:** antes de 1984 regían otras reglas. Los años futuros son una
  proyección con las leyes vigentes; si el Congreso crea o mueve un festivo, se publica
  una versión nueva.

## Roadmap

- [ ] Festivos regionales o de entidades específicas (por ejemplo, la Rama Judicial).
- [ ] Jornadas parciales (medio día hábil).
- [ ] Integración con polars.
- [ ] Documentación en un sitio web con ejemplos para analistas.

## Desarrollo

```bash
git clone https://github.com/juanes-15/habilmente.git
cd habilmente
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov          # tests, doctests de este README y cobertura
ruff check . && mypy  # lint y tipos
```

## Licencia

[MIT](LICENSE) © Juan Roncancio

---

## English summary

**habilmente** is a dependency-free Python library for Colombian public holidays and
business-day arithmetic.

- **Holiday rules:** it computes holidays for 1984–2199 from the law: the Emiliani Law
  (Monday shifts), Easter-based holidays and Law 2578 of 2026. There are no hard-coded
  date tables.
- **Configurable work calendars:** specific Saturdays by position in the month (e.g.
  first and last), company closures and worked holidays.
- **Business-day functions:** add business days, count them between dates, and get the
  n-th or last business day of a month. It also explains why each day is or isn't a
  business day.
- **Extras:** a Spanish CLI, and pandas helpers including a date dimension table for
  Power BI.
- **Verification:** results are checked against published calendars and two independent
  implementations, with property-based tests and fuzzing for security.
