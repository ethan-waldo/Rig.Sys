"""Translator for TestMotionModule motion modules."""

from rigsys.translation.modules.generic import GenericTranslator


class TestMotionModuleTranslator(GenericTranslator):
    """Translator for rigsys TestMotionModule modules."""

    module_type = "TestMotionModule"
