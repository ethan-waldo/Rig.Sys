"""Generic fallback translator for motion modules."""

from rigsys.translation.modules.base import ModuleTranslator


class GenericTranslator(ModuleTranslator):
    """Fallback translator when no module-specific translator is registered."""

    module_type = "MotionModuleBase"
