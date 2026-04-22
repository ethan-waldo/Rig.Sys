"""Translator for IK modules."""

from rigsys.translation.modules.generic import GenericTranslator


class IKTranslator(GenericTranslator):
    """Translator for rigsys IK modules."""

    module_type = "IK"
