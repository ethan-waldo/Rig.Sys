"""Translator for TestMotionModule motion modules."""

from __future__ import annotations

from typing import Any, Dict

from rigsys.translation.modules.generic import GenericTranslator


class TestMotionModuleTranslator(GenericTranslator):
    """Translator for rigsys TestMotionModule modules."""

    module_type = "TestMotionModule"

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        settings = super().build_module_settings(module)
        settings.update(
            {
                "expected_plugs": ["SomePlug", "AnotherPlug"],
                "expected_sockets": ["SomeSocket", "AnotherSocket"],
            }
        )
        return settings
