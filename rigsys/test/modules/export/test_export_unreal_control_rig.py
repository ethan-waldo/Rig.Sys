"""Tests for UnrealControlRigExport."""

import json
import sys
import types


if "maya" not in sys.modules:
    mayaModule = types.ModuleType("maya")
    mayaCmdsModule = types.ModuleType("maya.cmds")
    mayaModule.cmds = mayaCmdsModule
    sys.modules["maya"] = mayaModule
    sys.modules["maya.cmds"] = mayaCmdsModule


import rigsys.modules.export.unrealControlRigExport as unrealExportModule


class _DummyRig:
    def __init__(self, name):
        self.name = name


class _FakeMayaCmds:
    def __init__(self):
        self.plugins = {"fbxmaya": False}
        self.selected = []
        self.fileCalls = []

        self.joints = [
            "|Rig|skeleton|M_Root_Base",
            "|Rig|skeleton|M_Root_Offset",
        ]
        self.controls = [
            "|Rig|modules|M_Root_CTRL",
            "|Rig|modules|M_RootOffset_CTRL",
        ]
        self.parents = {
            "|Rig|skeleton|M_Root_Base": [],
            "|Rig|skeleton|M_Root_Offset": ["|Rig|skeleton|M_Root_Base"],
            "|Rig|modules|M_Root_CTRL": ["|Rig|modules"],
            "|Rig|modules|M_RootOffset_CTRL": ["|Rig|modules|M_Root_CTRL"],
        }
        self.shapes = {
            "|Rig|modules|M_Root_CTRL": ["|Rig|modules|M_Root_CTRL|M_Root_CTRLShape"],
            "|Rig|modules|M_RootOffset_CTRL": ["|Rig|modules|M_RootOffset_CTRL|M_RootOffset_CTRLShape"],
        }
        self.transforms = {
            "|Rig|skeleton|M_Root_Base": {
                "translation": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
            "|Rig|skeleton|M_Root_Offset": {
                "translation": [0.0, 10.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
            "|Rig|modules|M_Root_CTRL": {
                "translation": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
            "|Rig|modules|M_RootOffset_CTRL": {
                "translation": [0.0, 5.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        }

    def about(self, version=False, apiVersion=False):
        if version:
            return "2025"
        if apiVersion:
            return 20250000
        return ""

    def ls(self, *args, **kwargs):
        nodeType = kwargs.get("type")
        if nodeType == "joint":
            return list(self.joints)
        if nodeType == "transform" and args and args[0] == "*_CTRL":
            return list(self.controls)
        return []

    def listRelatives(self, node, p=False, type=None, fullPath=False, s=False):
        if p:
            parents = self.parents.get(node, [])
            if type == "joint":
                return [parent for parent in parents if parent in self.joints]
            return list(parents)
        if s:
            return list(self.shapes.get(node, []))
        return []

    def xform(self, node, q=False, ws=False, t=False, ro=False, r=False, s=False):
        data = self.transforms[node]
        if t:
            return list(data["translation"])
        if ro:
            return list(data["rotation"])
        if s:
            return list(data["scale"])
        raise ValueError("Unsupported xform query.")

    def pluginInfo(self, pluginName, q=False, loaded=False):
        return self.plugins.get(pluginName, False)

    def loadPlugin(self, pluginName, quiet=False):
        self.plugins[pluginName] = True

    def select(self, nodes, r=False):
        self.selected = list(nodes)

    def file(self, filePath, **kwargs):
        self.fileCalls.append((filePath, kwargs))
        return filePath


def test_unreal_control_rig_export_writes_manifest_script_and_fbx(tmp_path, monkeypatch):
    fakeCmds = _FakeMayaCmds()
    monkeypatch.setattr(unrealExportModule, "cmds", fakeCmds)

    module = unrealExportModule.UnrealControlRigExport(
        rig=_DummyRig("DemoRig"),
        exportPath=str(tmp_path),
        exportAll=False,
        exportSelected=True,
        nodesToExport=["|Rig|modules|M_Root_CTRL"],
        exportFBX=True,
        createUnrealScript=True,
        controlRigPackagePath="/Game/Characters/Rigs",
        controlRigName="DemoRig_ControlRig",
    )
    module.run()

    manifestPath = tmp_path / "DemoRig_unreal_control_rig.json"
    scriptPath = tmp_path / "DemoRig_build_control_rig.py"
    fbxPath = tmp_path / "DemoRig_unreal.fbx"

    assert manifestPath.exists()
    assert scriptPath.exists()
    assert len(fakeCmds.fileCalls) == 1
    assert fakeCmds.fileCalls[0][0] == str(fbxPath)
    assert fakeCmds.fileCalls[0][1]["exportSelected"] is True
    assert fakeCmds.fileCalls[0][1]["exportAll"] is False
    assert fakeCmds.selected == ["|Rig|modules|M_Root_CTRL"]

    with open(manifestPath, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    assert manifest["rig_name"] == "DemoRig"
    assert manifest["maya_version"] == "2025"
    assert manifest["maya_api_version"] == "20250000"
    assert manifest["unreal"]["control_rig_package_path"] == "/Game/Characters/Rigs"
    assert manifest["unreal"]["control_rig_name"] == "DemoRig_ControlRig"
    assert len(manifest["joints"]) == 2
    assert len(manifest["controls"]) == 2

    scriptText = scriptPath.read_text(encoding="utf-8")
    assert "ControlRigBlueprintFactory" in scriptText
    assert str(manifestPath) in scriptText
