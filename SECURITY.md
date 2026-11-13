# Política de seguridad

## Versiones con soporte

| Versión | Soporte |
|---|---|
| 0.1.x | ✅ |

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Reporta de forma privada desde
[GitHub Security Advisories](https://github.com/juanes-15/habilmente/security/advisories/new)
e incluye:

- la versión de habilmente y de Python;
- los pasos o el código para reproducir el problema;
- el impacto que observaste.

Plazos de respuesta:

- **Confirmación de recibido:** en un máximo de 5 días hábiles (calculados con habilmente).
- **Corrección o plan de acción:** en un máximo de 30 días.

Se te dará crédito en el aviso publicado, salvo que prefieras quedar en el anonimato.

## Modelo de amenaza

habilmente es una librería de cálculo puro: no usa red, no lee ni escribe archivos, no
ejecuta código externo y no tiene dependencias en tiempo de ejecución. Se consideran
vulnerabilidades:

- **Errores inesperados:** entradas que provoquen excepciones distintas de `TypeError`,
  `ValueError` o `KeyError`.
- **Resultados falsos:** entradas que evadan la validación y produzcan resultados
  incorrectos sin avisar.
- **Consumo desmedido:** uso de CPU o memoria fuera de proporción con la entrada, o que
  nunca termine.
- **Inyección en la terminal:** salidas del comando `habilmente` que lleven códigos de
  control a la terminal.
- **Cadena de suministro:** problemas en el proceso de construcción o publicación del
  paquete.

No se consideran vulnerabilidades:

- **Código que ya se ejecuta en el mismo proceso de Python**, porque ese código puede
  modificar cualquier objeto.
- **Errores en el calendario legal**, por ejemplo una ley nueva que todavía no se haya
  incorporado. Estos se reportan como un issue normal.

## Medidas aplicadas

**Validación de entradas**
- Validación estricta de tipos y rangos, usando la implementación base de `int` para que
  subclases que mienten en las comparaciones no la evadan.
- Las fechas se reconstruyen en lugar de confiar en métodos que una subclase podría
  redefinir.

**Límites de consumo**
- Límites en los iterables de configuración, en los argumentos de la terminal y en el
  largo de los mensajes de error.
- Cachés acotadas por el rango de años soportado.

**Terminal**
- Los caracteres de control se escapan antes de mostrar cualquier mensaje.

**Pruebas**
- Fuzzing de la API, del constructor `Calendario`, del comando de terminal y de las
  funciones de pandas.
- Guardas estáticas que prohíben `eval`, `exec`, `pickle`, `subprocess`, red y acceso a
  archivos.

**CI y cadena de suministro**
- GitHub Actions fijadas por SHA, con `permissions: {}` por defecto y
  `persist-credentials: false`.
- Auditoría de los workflows con zizmor, y análisis con CodeQL (`security-extended`),
  bandit, pip-audit y OpenSSF Scorecard.
- Dependabot con 7 días de espera antes de proponer versiones nuevas.
- Publicación en PyPI con Trusted Publishing (OIDC, sin tokens guardados), environments
  con aprobación manual y atestaciones de procedencia (PEP 740).
