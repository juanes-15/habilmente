# Changelog

Todos los cambios importantes de este proyecto se documentan aquí. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.1.1] - 2026-11-13

### Corregido

- El extra `pandas` no estaba declarado: `pip install "habilmente[pandas]"` no instalaba
  pandas, aunque el README y los mensajes de error lo indicaban. Ahora se instala.
- Nuevo test y chequeo de CI que instalan el wheel con el extra `pandas` y usan
  `habilmente.pandas`, para que este error no se repita.

## [0.1.0] - 2026-11-12

Primera versión.

### Agregado

- **Festivos nacionales de Colombia de 1984 a 2199**, calculados desde las reglas legales:
  - fijos;
  - trasladables por la Ley 51 de 1983 (Ley Emiliani);
  - dependientes de la Pascua;
  - el 9 de julio desde 2026 (Ley 2578 de 2026).
- **Funciones de festivos:** `festivos`, `fechas_festivas`, `es_festivo`,
  `nombre_festivo` y `domingo_de_pascua`.
- **`Calendario` configurable e inmutable:** sábados hábiles por posición en el mes,
  días no hábiles extra y días hábiles extra.
- **Funciones de días hábiles:** `es_dia_habil`, `explicar_dia`, `sumar_dias_habiles`,
  `siguiente_dia_habil`, `anterior_dia_habil`, `dias_habiles_entre`,
  `listar_dias_habiles`, `dias_habiles_del_mes` y `dia_habil_del_mes`.
- **Comando `habilmente`:** subcomandos `festivos`, `es-habil`, `sumar`, `siguiente`,
  `anterior`, `entre` y `mes`, con salida en texto, JSON o CSV.
- **Módulo opcional `habilmente.pandas`:** columnas de días hábiles, festivos, sumas y
  conteos (con soporte de `NaT`, zonas horarias y `errores="coerce"`), más
  `tabla_calendario` para Power BI.
- **Pruebas:** verificación contra calendarios publicados y dos implementaciones
  independientes, pruebas con hypothesis y fuzzing de seguridad.
- **CI y seguridad:** GitHub Actions para lint, tipos, tests, seguridad y publicación con
  Trusted Publishing.

[Sin publicar]: https://github.com/juanes-15/habilmente/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/juanes-15/habilmente/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/juanes-15/habilmente/releases/tag/v0.1.0
