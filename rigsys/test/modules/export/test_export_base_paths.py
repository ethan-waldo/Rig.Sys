"""Tests for export path resolution behavior."""

import sys
import types


if "maya" not in sys.modules:
    mayaModule = types.ModuleType("maya")
    mayaCmdsModule = types.ModuleType("maya.cmds")
    mayaModule.cmds = mayaCmdsModule
    sys.modules["maya"] = mayaModule
    sys.modules["maya.cmds"] = mayaCmdsModule


from rigsys.modules.export.exportBase import ExportModuleBase


class _DummyRig:
    def __init__(self, name):
        self.name = name


def test_export_path_keeps_explicit_file_path(tmp_path):
    module = ExportModuleBase(
        rig=_DummyRig("TestRig"),
        exportPath=str(tmp_path / "custom_name.fbx"),
        extension=".fbx",
    )

    assert module.fullExportPath == str(tmp_path / "custom_name.fbx")


def test_export_path_builds_file_name_for_directory(tmp_path):
    module = ExportModuleBase(
        rig=_DummyRig("TestRig"),
        exportPath=str(tmp_path),
        extension=".json",
        fileNameSuffix="_unreal_control_rig",
    )

    assert module.fullExportPath == str(tmp_path / "TestRig_unreal_control_rig.json")
