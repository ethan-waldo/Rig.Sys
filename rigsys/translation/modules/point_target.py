"""Translator for PointTarget motion modules."""

from rigsys.translation.modules.generic import GenericTranslator


class PointTargetTranslator(GenericTranslator):
    """Translator for rigsys PointTarget modules."""

    module_type = "PointTarget"
