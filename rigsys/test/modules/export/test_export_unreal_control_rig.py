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
        self.nodeTypes = {
            "|Rig|modules|M_Root_IKFK_blend": "blendColors",
            "|Rig|modules|M_Root_IKFK_rev": "reverse",
        }

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
        self.userAttrs = {
            "|Rig|modules|M_Root_CTRL": ["IK_FK_Switch"],
            "|Rig|modules|M_RootOffset_CTRL": [],
        }
        self.attrData = {
            "|Rig|modules|M_Root_CTRL.IK_FK_Switch": {
                "type": "float",
                "value": 0.25,
                "keyable": True,
                "channelBox": True,
                "lock": False,
                "min": 0.0,
                "max": 1.0,
                "default": 0.0,
            },
        }
        self.connectionsByNode = {
            "|Rig|modules|M_Root_CTRL": [
                "|Rig|modules|M_Root_CTRL.visibility",
                "|Rig|modules|M_RootOffset_CTRL.visibility",
            ],
        }
        self.connectionsByPlug = {
            "|Rig|modules|M_Root_IKFK_blend.blender": ["|Rig|modules|M_Root_CTRL.IK_FK_Switch"],
            "|Rig|modules|M_Root_IKFK_blend.color1": ["|Rig|skeleton|M_Root_Base.rotate"],
            "|Rig|modules|M_Root_IKFK_blend.color2": ["|Rig|skeleton|M_Root_Offset.rotate"],
            "|Rig|modules|M_Root_IKFK_blend.output": ["|Rig|skeleton|M_Result.rotate"],
            "|Rig|modules|M_Root_CTRL.IK_FK_Switch": [
                "|Rig|modules|M_Root_IKFK_blend.blender",
                "|Rig|modules|M_FK_Grp.visibility",
                "|Rig|modules|M_Root_IKFK_rev.input.inputX",
            ],
            "|Rig|modules|M_Root_IKFK_rev.outputX": ["|Rig|modules|M_IK_Grp.visibility"],
            "|Rig|modules|M_Root_IKFK_rev.output.outputX": ["|Rig|modules|M_PV_Grp.visibility"],
        }
        self.constraintData = {
            "|Rig|constraints|M_RootOffset_parentConstraint1": {
                "type": "parentConstraint",
                "driven_parent": "|Rig|modules|M_RootOffset_CTRL",
                "targets": ["|Rig|modules|M_Root_CTRL"],
                "weight_aliases": ["M_Root_CTRLW0"],
                "weights": {"M_Root_CTRLW0": 1.0},
                "interp_type": 2,
            }
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
        if nodeType == "blendColors":
            return ["|Rig|modules|M_Root_IKFK_blend"]
        if nodeType == "reverse":
            return ["|Rig|modules|M_Root_IKFK_rev"]
        if nodeType in {
            "condition",
            "multiplyDivide",
            "plusMinusAverage",
            "multDoubleLinear",
            "clamp",
            "setRange",
            "remapValue",
        }:
            return []
        if nodeType == "parentConstraint":
            return [path for path, info in self.constraintData.items() if info["type"] == "parentConstraint"]
        if nodeType == "pointConstraint":
            return [path for path, info in self.constraintData.items() if info["type"] == "pointConstraint"]
        if nodeType == "orientConstraint":
            return [path for path, info in self.constraintData.items() if info["type"] == "orientConstraint"]
        if nodeType == "scaleConstraint":
            return [path for path, info in self.constraintData.items() if info["type"] == "scaleConstraint"]
        if nodeType == "aimConstraint":
            return [path for path, info in self.constraintData.items() if info["type"] == "aimConstraint"]
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

    def listAttr(self, node, userDefined=False):
        if userDefined:
            return list(self.userAttrs.get(node, []))
        return []

    def getAttr(self, plug, type=False, keyable=False, channelBox=False, lock=False):
        if type:
            return self.attrData[plug]["type"]
        if keyable:
            return self.attrData[plug]["keyable"]
        if channelBox:
            return self.attrData[plug]["channelBox"]
        if lock:
            return self.attrData[plug]["lock"]
        return self.attrData[plug]["value"]

    def attributeQuery(
        self,
        attr,
        node=None,
        minExists=False,
        maxExists=False,
        minimum=False,
        maximum=False,
        listDefault=False,
        listEnum=False,
    ):
        plug = f"{node}.{attr}"
        attrInfo = self.attrData.get(plug, {})
        if minExists:
            return "min" in attrInfo
        if maxExists:
            return "max" in attrInfo
        if minimum:
            return [attrInfo["min"]]
        if maximum:
            return [attrInfo["max"]]
        if listDefault:
            return [attrInfo["default"]]
        if listEnum:
            return []
        return False

    def listConnections(self, node, c=False, p=False, s=False, d=False):
        if c and p and s and not d:
            return list(self.connectionsByNode.get(node, []))
        if p and not c:
            return list(self.connectionsByPlug.get(node, []))
        return list(self.connectionsByNode.get(node, []))

    def nodeType(self, node):
        return self.nodeTypes.get(node, "transform")

    def _queryConstraint(self, constraint, queryTargets=False, queryWeightAliases=False):
        info = self.constraintData.get(constraint)
        if not info:
            return []
        if queryTargets:
            return list(info["targets"])
        if queryWeightAliases:
            return list(info["weight_aliases"])
        return []

    def parentConstraint(self, constraint, q=False, tl=False, wal=False):
        if q and tl:
            return self._queryConstraint(constraint, queryTargets=True)
        if q and wal:
            return self._queryConstraint(constraint, queryWeightAliases=True)
        return []

    def pointConstraint(self, constraint, q=False, tl=False, wal=False):
        if q and tl:
            return self._queryConstraint(constraint, queryTargets=True)
        if q and wal:
            return self._queryConstraint(constraint, queryWeightAliases=True)
        return []

    def orientConstraint(self, constraint, q=False, tl=False, wal=False):
        if q and tl:
            return self._queryConstraint(constraint, queryTargets=True)
        if q and wal:
            return self._queryConstraint(constraint, queryWeightAliases=True)
        return []

    def scaleConstraint(self, constraint, q=False, tl=False, wal=False):
        if q and tl:
            return self._queryConstraint(constraint, queryTargets=True)
        if q and wal:
            return self._queryConstraint(constraint, queryWeightAliases=True)
        return []

    def aimConstraint(self, constraint, q=False, tl=False, wal=False):
        if q and tl:
            return self._queryConstraint(constraint, queryTargets=True)
        if q and wal:
            return self._queryConstraint(constraint, queryWeightAliases=True)
        return []


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
    assert manifest["schema_version"] == 3
    assert len(manifest["custom_control_attributes"]) == 1
    assert manifest["custom_control_attributes"][0]["attribute"] == "IK_FK_Switch"
    assert len(manifest["constraints"]) == 1
    assert manifest["constraints"][0]["type"] == "parentConstraint"
    assert len(manifest["connections"]) == 1
    assert manifest["connections"][0]["destination"].endswith(".visibility")
    assert manifest["connections"][0]["source"].endswith(".visibility")

    scriptText = scriptPath.read_text(encoding="utf-8")
    assert "ControlRigBlueprintFactory" in scriptText
    assert "_apply_custom_attributes" in scriptText
    assert "_apply_constraints" in scriptText
    assert str(manifestPath) in scriptText
