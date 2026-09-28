"""Model registry; adding an antenna does not change the core."""

from antenna_lab.core.config import ConfigurationError
from .quados8.model import build as build_quados8

MODELS = {"quados8": build_quados8}


def build_model(config):
    name = config["antenna"]["model"]
    if name not in MODELS:
        raise ConfigurationError(f"Nieobsługiwany model: {name}. Dostępne: {', '.join(MODELS)}")
    return MODELS[name](config["antenna"]["parameters"], reflector=config["simulation"]["reflector_model"] != "none")
