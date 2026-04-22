"""Translator for FK modules."""

from rigsys.translation.modules.generic import GenericTranslator


class FKTranslator(GenericTranslator):
    """Translator for rigsys FK motion modules."""

    module_type = "FK"
