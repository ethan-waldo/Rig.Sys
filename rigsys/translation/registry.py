"""Module translator registry."""

from __future__ import annotations

from typing import Any

from rigsys.translation.models import RigModuleDefinition
from rigsys.translation.modules.base import ModuleTranslator
from rigsys.translation.modules.fk import FKTranslator
from rigsys.translation.modules.fkrail import FKSegmentTranslator
from rigsys.translation.modules.floating import FloatingTranslator
from rigsys.translation.modules.follicle_eye import FollicleEyeTranslator
from rigsys.translation.modules.generic import GenericTranslator
from rigsys.translation.modules.hand import HandTranslator
from rigsys.translation.modules.ik import IKTranslator
from rigsys.translation.modules.limb import LimbTranslator
from rigsys.translation.modules.lips import LipsTranslator
from rigsys.translation.modules.point_target import PointTargetTranslator
from rigsys.translation.modules.quad_limb import QuadLimbTranslator
from rigsys.translation.modules.ribbon_bind_ik import RibbonBindIKTranslator
from rigsys.translation.modules.root import RootTranslator
from rigsys.translation.modules.test_motion_module import TestMotionModuleTranslator


MODULE_TRANSLATORS = {
    "Root": RootTranslator(),
    "FK": FKTranslator(),
    "FKSegment": FKSegmentTranslator(),
    "IK": IKTranslator(),
    "Limb": LimbTranslator(),
    "QuadLimb": QuadLimbTranslator(),
    "Hand": HandTranslator(),
    "Floating": FloatingTranslator(),
    "PointTarget": PointTargetTranslator(),
    "Lips": LipsTranslator(),
    "FollicleEye": FollicleEyeTranslator(),
    "RibbonBindIK": RibbonBindIKTranslator(),
    "TestMotionModule": TestMotionModuleTranslator(),
}

GENERIC_TRANSLATOR = GenericTranslator()


def get_translator(module: Any) -> ModuleTranslator:
    """Return a module-specific translator, or generic fallback."""
    return MODULE_TRANSLATORS.get(type(module).__name__, GENERIC_TRANSLATOR)


def translate_motion_module(module: Any) -> RigModuleDefinition:
    """Translate one motion module to a serializable module definition."""
    return get_translator(module).translate(module)
