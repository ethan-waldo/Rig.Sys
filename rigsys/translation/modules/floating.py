"""Translator for Floating motion modules."""

from rigsys.translation.modules.generic import GenericTranslator


class FloatingTranslator(GenericTranslator):
    """Translator for rigsys floating modules."""

    module_type = "Floating"
