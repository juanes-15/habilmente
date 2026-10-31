import os

from hypothesis import HealthCheck, settings

# El perfil "ci" es más exhaustivo; se activa con HYPOTHESIS_PROFILE=ci.
for nombre, ejemplos in (("default", 300), ("ci", 2000)):
    settings.register_profile(
        nombre,
        max_examples=ejemplos,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))
