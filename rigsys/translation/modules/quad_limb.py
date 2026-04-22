"""Translator for QuadLimb motion modules."""

from rigsys.translation.modules.limb import LimbTranslator


class QuadLimbTranslator(LimbTranslator):
    """QuadLimb shares limb translation behavior."""

    module_type = "QuadLimb"

