"""Unit tests for ControlRigExport module."""

import json
import os
import sys
import tempfile
import types
import unittest

# Allow importing rigsys export modules in environments without Maya installed.
maya_module = types.ModuleType("maya")
maya_module.__path__ = []
maya_cmds_module = types.ModuleType("maya.cmds")
maya_api_module = types.ModuleType("maya.api")
maya_api_module.__path__ = []
maya_open_maya_module = types.ModuleType("maya.api.OpenMaya")
maya_module.cmds = maya_cmds_module
maya_module.api = maya_api_module
maya_api_module.OpenMaya = maya_open_maya_module
sys.modules.setdefault("maya", maya_module)
sys.modules.setdefault("maya.cmds", maya_cmds_module)
sys.modules.setdefault("maya.api", maya_api_module)
sys.modules.setdefault("maya.api.OpenMaya", maya_open_maya_module)

import rigsys.modules.export.controlRigExport as controlrig_export


class _FakeProxy:
    def __init__(self, name):
        self.name = name
        self.parent = None
        self.position = [0.0, 0.0, 0.0]
        self.rotation = [0.0, 0.0, 0.0]
        self.side = "M"
        self.label = "Root"
        self.upVector = False
        self.plug = False


class _FakeRootModule:
    side = "M"
    label = "Root"
    buildOrder = 0
    parent = None
    selectedPlug = "Local"
    selectedSocket = "Base"
    sockets = {"Base": None}
    plugs = {"Local": None, "World": None}
    ctrlShapes = "circle"
    ctrlScale = [1.0, 1.0, 1.0]
    addOffset = False
    aimAxis = "+x"
    upAxis = "-z"
    mirror = False
    mirrored = False
    proxies = {"Root": _FakeProxy("Base")}

    @staticmethod
    def getFullName():
        return "M_Root"


class _FakeRig:
    def __init__(self):
        self.name = "ExportRig"
        self.motionModules = {"M_Root": _FakeRootModule()}
        self.deformerModules = {}
        self.utilityModules = {}
        self.exportModules = {}

    def preBuild(self):
        return []


class TestControlRigExportModule(unittest.TestCase):
    def test_export_creates_json_payload(self):
        rig = _FakeRig()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = os.path.join(tmpdir, "exports")
            module = controlrig_export.ControlRigExport(rig=rig, exportPath=export_path)
            module.run()

            expected_path = os.path.join(export_path, "ExportRig_ControlRig.json")
            self.assertTrue(os.path.exists(expected_path))
            with open(expected_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertEqual(payload["rig_name"], "ExportRig")
            self.assertEqual(len(payload["modules"]), 1)
            self.assertEqual(payload["modules"][0]["module_name"], "M_Root")
