"""Pytest bootstrap configuration for non-Maya environments."""

import sys
import types


def _ensure_maya_stubs() -> None:
    """Register lightweight Maya module stubs for import-time compatibility."""
    if "maya" in sys.modules:
        return

    mayaModule = types.ModuleType("maya")
    mayaCmdsModule = types.ModuleType("maya.cmds")
    mayaMelModule = types.ModuleType("maya.mel")
    mayaOpenMayaModule = types.ModuleType("maya.OpenMaya")
    mayaOpenMayaAnimModule = types.ModuleType("maya.OpenMayaAnim")
    mayaApiModule = types.ModuleType("maya.api")
    mayaApiOpenMayaModule = types.ModuleType("maya.api.OpenMaya")

    mayaModule.cmds = mayaCmdsModule
    mayaModule.mel = mayaMelModule
    mayaModule.OpenMaya = mayaOpenMayaModule
    mayaModule.OpenMayaAnim = mayaOpenMayaAnimModule
    mayaModule.api = mayaApiModule
    mayaApiModule.OpenMaya = mayaApiOpenMayaModule

    sys.modules["maya"] = mayaModule
    sys.modules["maya.cmds"] = mayaCmdsModule
    sys.modules["maya.mel"] = mayaMelModule
    sys.modules["maya.OpenMaya"] = mayaOpenMayaModule
    sys.modules["maya.OpenMayaAnim"] = mayaOpenMayaAnimModule
    sys.modules["maya.api"] = mayaApiModule
    sys.modules["maya.api.OpenMaya"] = mayaApiOpenMayaModule


_ensure_maya_stubs()
