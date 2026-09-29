"""Model registry; adding an antenna does not change the core."""

from antenna_lab.core.config import ConfigurationError
from .quados8.model import build as build_quados8
from .biquad.model import build as build_biquad

MODELS = {"quados8": build_quados8, "biquad": build_biquad}
MODEL_NAMES = {"quados8": "Quados 8", "biquad": "Biquad"}


def build_model(config):
    name = config["antenna"]["model"]
    if name not in MODELS:
        raise ConfigurationError(f"Nieobsługiwany model: {name}. Dostępne: {', '.join(MODELS)}")
    return MODELS[name](config["antenna"]["parameters"], reflector=config["simulation"]["reflector_model"] != "none")
