"""Unreal Control Rig export module.

Exports a rig manifest from Maya and generates a companion Unreal Python script that can
create a Control Rig asset using Unreal's scripting APIs.
"""

import json
import logging
import os
from typing import Dict, List, Optional

import maya.cmds as cmds

import rigsys.modules.export.exportBase as exportBase


logger = logging.getLogger(__name__)


class UnrealControlRigExport(exportBase.ExportModuleBase):
    """Export module for Maya-to-Unreal Control Rig workflows."""

    def __init__(
        self,
        rig,
        exportPath: str,
        label: str = "",
        buildOrder: int = 5000,
        isMuted: bool = False,
        exportAll: bool = True,
        exportSelected: bool = False,
        nodesToExport: Optional[List[str]] = None,
        exportFBX: bool = True,
        fbxExportPath: str = "",
        createUnrealScript: bool = True,
        unrealScriptPath: str = "",
        controlRigPackagePath: str = "/Game/Rigs",
        controlRigName: str = "",
        skeletalMeshImportPath: str = "",
        mirror: bool = False,
    ) -> None:
        """Initialize the module.

        Args:
            exportPath: Path to manifest file or destination folder.
            exportAll: Export whole scene to FBX when exportFBX is enabled.
            exportSelected: Export only nodesToExport to FBX when enabled.
            nodesToExport: Maya nodes for selected export mode.
            exportFBX: Export a companion FBX file for Unreal import.
            fbxExportPath: Optional explicit FBX output path (file or folder).
            createUnrealScript: Generate Unreal Python script.
            unrealScriptPath: Optional explicit script output path (file or folder).
            controlRigPackagePath: Unreal content browser package path.
            controlRigName: Name of Control Rig asset in Unreal.
            skeletalMeshImportPath: Optional destination package path for FBX import.
        """
        super().__init__(
            rig=rig,
            exportPath=exportPath,
            label=label,
            buildOrder=buildOrder,
            isMuted=isMuted,
            mirror=mirror,
            extension=".json",
            fileNameSuffix="_unreal_control_rig",
        )

        self.exportAll = exportAll
        self.exportSelected = exportSelected
        self.nodesToExport = nodesToExport or []
        self.exportFBX = exportFBX
        self.fbxExportPath = fbxExportPath
        self.createUnrealScript = createUnrealScript
        self.unrealScriptPath = unrealScriptPath
        self.controlRigPackagePath = controlRigPackagePath
        self.controlRigName = controlRigName or f"{self._rig.name}_ControlRig"
        self.skeletalMeshImportPath = skeletalMeshImportPath

    def run(self) -> None:
        """Run export pipeline."""
        self._ensureDirectory(self.fullExportPath)

        fbxOutputPath = self._getResolvedFBXPath()
        scriptOutputPath = self._getResolvedScriptPath()

        manifestData = self._buildManifest(
            manifestPath=self.fullExportPath,
            fbxPath=fbxOutputPath if self.exportFBX else "",
            unrealScriptPath=scriptOutputPath if self.createUnrealScript else "",
        )

        with open(self.fullExportPath, "w", encoding="utf-8") as handle:
            json.dump(manifestData, handle, indent=4, sort_keys=True)

        if self.exportFBX:
            self._exportFBX(fbxOutputPath)

        if self.createUnrealScript:
            self._ensureDirectory(scriptOutputPath)
            script = self._buildUnrealScript(manifestPath=self.fullExportPath)
            with open(scriptOutputPath, "w", encoding="utf-8") as handle:
                handle.write(script)

    def _buildManifest(self, manifestPath: str, fbxPath: str, unrealScriptPath: str) -> Dict:
        """Build serializable manifest consumed by Unreal script."""
        packagePath = self.controlRigPackagePath.rstrip("/")
        if packagePath == "":
            packagePath = "/Game"

        return {
            "schema_version": 1,
            "rig_name": self._rig.name,
            "maya_version": cmds.about(version=True),
            "maya_api_version": str(cmds.about(apiVersion=True)),
            "export_files": {
                "manifest": manifestPath,
                "fbx": fbxPath,
                "unreal_script": unrealScriptPath,
            },
            "unreal": {
                "control_rig_package_path": packagePath,
                "control_rig_name": self.controlRigName,
                "skeletal_mesh_import_path": self.skeletalMeshImportPath or packagePath,
            },
            "joints": self._collectJoints(),
            "controls": self._collectControls(),
        }

    def _collectJoints(self) -> List[Dict]:
        """Collect skeletal hierarchy from Maya scene."""
        joints = cmds.ls(type="joint", long=True) or []
        data = []
        for joint in sorted(set(joints)):
            parentJoints = cmds.listRelatives(joint, p=True, type="joint", fullPath=True) or []
            parent = self._shortName(parentJoints[0]) if parentJoints else None
            transform = self._queryTransform(joint)
            data.append(
                {
                    "name": self._shortName(joint),
                    "path": joint,
                    "parent": parent,
                    "translation": transform["translation"],
                    "rotation": transform["rotation"],
                    "scale": transform["scale"],
                }
            )
        return data

    def _collectControls(self) -> List[Dict]:
        """Collect likely animator controls by naming convention."""
        controls = cmds.ls("*_CTRL", type="transform", long=True) or []
        data = []
        for control in sorted(set(controls)):
            parents = cmds.listRelatives(control, p=True, fullPath=True) or []
            shapes = cmds.listRelatives(control, s=True, fullPath=True) or []
            transform = self._queryTransform(control)
            data.append(
                {
                    "name": self._shortName(control),
                    "path": control,
                    "parent": self._shortName(parents[0]) if parents else None,
                    "shape_nodes": [self._shortName(shape) for shape in shapes],
                    "translation": transform["translation"],
                    "rotation": transform["rotation"],
                    "scale": transform["scale"],
                }
            )
        return data

    def _queryTransform(self, node: str) -> Dict[str, List[float]]:
        """Query world transform values from Maya."""
        return {
            "translation": cmds.xform(node, q=True, ws=True, t=True),
            "rotation": cmds.xform(node, q=True, ws=True, ro=True),
            "scale": cmds.xform(node, q=True, r=True, s=True),
        }

    def _shortName(self, fullName: str) -> str:
        """Convert Maya path name to short node name."""
        return fullName.split("|")[-1]

    def _getResolvedFBXPath(self) -> str:
        """Resolve final FBX output file path."""
        if self.fbxExportPath:
            if self.checkIfExportPathIsFile(self.fbxExportPath):
                return self.fbxExportPath
            return os.path.join(self.fbxExportPath, f"{self._rig.name}_unreal.fbx")

        baseDirectory = os.path.dirname(self.fullExportPath)
        return os.path.join(baseDirectory, f"{self._rig.name}_unreal.fbx")

    def _getResolvedScriptPath(self) -> str:
        """Resolve final generated Unreal script path."""
        if self.unrealScriptPath:
            if self.checkIfExportPathIsFile(self.unrealScriptPath):
                return self.unrealScriptPath
            return os.path.join(self.unrealScriptPath, f"{self._rig.name}_build_control_rig.py")

        baseDirectory = os.path.dirname(self.fullExportPath)
        return os.path.join(baseDirectory, f"{self._rig.name}_build_control_rig.py")

    def _ensureDirectory(self, filePath: str) -> None:
        """Ensure output directory exists."""
        outputDir = os.path.dirname(filePath)
        if outputDir and not os.path.exists(outputDir):
            os.makedirs(outputDir)

    def _exportFBX(self, fbxPath: str) -> None:
        """Export companion FBX from Maya scene."""
        self._ensureDirectory(fbxPath)
        self._ensureFBXPluginLoaded()

        if self.exportSelected:
            if not self.nodesToExport:
                raise ValueError("nodesToExport must be provided when exportSelected=True")
            cmds.select(self.nodesToExport, r=True)

        exportAll = self.exportAll and not self.exportSelected

        cmds.file(
            fbxPath,
            force=True,
            options="v=0;",
            typ="FBX export",
            preserveReferences=True,
            exportAll=exportAll,
            exportSelected=self.exportSelected,
        )

    def _ensureFBXPluginLoaded(self) -> None:
        """Ensure FBX plugin is loaded for modern Maya sessions."""
        try:
            if not cmds.pluginInfo("fbxmaya", q=True, loaded=True):
                cmds.loadPlugin("fbxmaya", quiet=True)
        except Exception:
            logger.warning("Could not verify/load fbxmaya plugin. Continuing with Maya file export.")

    def _buildUnrealScript(self, manifestPath: str) -> str:
        """Generate Unreal Python script for Control Rig creation."""
        manifestLiteral = json.dumps(manifestPath)
        return f'''"""Generated by Rig.Sys UnrealControlRigExport."""

import json
import os

import unreal


MANIFEST_PATH = {manifestLiteral}


def _log_warning(message):
    unreal.log_warning(f"[Rig.Sys] {{message}}")


def _load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        raise RuntimeError(f"Manifest not found: {{MANIFEST_PATH}}")

    with open(MANIFEST_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _ensure_content_path(path):
    editor_asset_library = unreal.EditorAssetLibrary()
    if not editor_asset_library.does_directory_exist(path):
        editor_asset_library.make_directory(path)


def _try_call(method, candidates):
    for args, kwargs in candidates:
        try:
            method(*args, **kwargs)
            return True
        except TypeError:
            continue
        except Exception as exc:
            _log_warning(f"Call failed for {{method}}: {{exc}}")
            return False
    return False


def _to_transform(translation, rotation, scale):
    return unreal.Transform(
        rotation=unreal.Rotator(rotation[0], rotation[1], rotation[2]),
        translation=unreal.Vector(translation[0], translation[1], translation[2]),
        scale3d=unreal.Vector(scale[0], scale[1], scale[2]),
    )


def _import_fbx_if_present(manifest):
    fbx_path = manifest.get("export_files", {{}}).get("fbx", "")
    if not fbx_path:
        return
    if not os.path.exists(fbx_path):
        _log_warning(f"FBX path does not exist: {{fbx_path}}")
        return

    unreal_data = manifest.get("unreal", {{}})
    destination = unreal_data.get("skeletal_mesh_import_path", "/Game")
    _ensure_content_path(destination)

    task = unreal.AssetImportTask()
    task.filename = fbx_path
    task.destination_path = destination
    task.automated = True
    task.replace_existing = True
    task.save = True

    fbx_options = unreal.FbxImportUI()
    fbx_options.import_as_skeletal = True
    task.options = fbx_options

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])


def _create_control_rig(manifest):
    unreal_data = manifest.get("unreal", {{}})
    package_path = unreal_data.get("control_rig_package_path", "/Game")
    asset_name = unreal_data.get("control_rig_name", "Generated_ControlRig")
    _ensure_content_path(package_path)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.ControlRigBlueprintFactory()
    control_rig_bp = asset_tools.create_asset(
        asset_name,
        package_path,
        unreal.ControlRigBlueprint,
        factory,
    )
    if control_rig_bp is None:
        raise RuntimeError("Failed to create Control Rig asset.")
    return control_rig_bp


def _populate_hierarchy(control_rig_bp, manifest):
    if not hasattr(control_rig_bp, "get_hierarchy_controller"):
        _log_warning("Control Rig blueprint has no get_hierarchy_controller() API.")
        return

    hierarchy = control_rig_bp.get_hierarchy_controller()
    if hierarchy is None:
        _log_warning("Hierarchy controller not available on Control Rig blueprint.")
        return

    for joint in manifest.get("joints", []):
        transform = _to_transform(joint["translation"], joint["rotation"], joint["scale"])
        parent = joint.get("parent") or ""
        if hasattr(hierarchy, "add_bone"):
            _try_call(
                hierarchy.add_bone,
                [
                    ((joint["name"], parent, transform), {{"setup_undo": False}}),
                    ((joint["name"], parent, transform, False), {{}}),
                    ((joint["name"], parent, transform), {{}}),
                ],
            )

    for control in manifest.get("controls", []):
        transform = _to_transform(control["translation"], control["rotation"], control["scale"])
        parent = control.get("parent") or ""

        control_added = False
        if hasattr(hierarchy, "add_control") and hasattr(unreal, "RigControlSettings"):
            control_settings = unreal.RigControlSettings()
            if hasattr(unreal, "RigControlType"):
                control_settings.control_type = unreal.RigControlType.EULER_TRANSFORM

            control_added = _try_call(
                hierarchy.add_control,
                [
                    ((control["name"], parent, control_settings, transform), {{"setup_undo": False}}),
                    ((control["name"], parent, control_settings, transform, transform), {{"setup_undo": False}}),
                    ((control["name"], parent, control_settings, transform, transform, False), {{}}),
                    ((control["name"], parent, control_settings, transform, transform, False, False), {{}}),
                ],
            )

        if not control_added and hasattr(hierarchy, "add_null"):
            _try_call(
                hierarchy.add_null,
                [
                    ((control["name"], parent, transform), {{"setup_undo": False}}),
                    ((control["name"], parent, transform, False), {{}}),
                    ((control["name"], parent, transform), {{}}),
                ],
            )


def main():
    manifest = _load_manifest()
    _import_fbx_if_present(manifest)
    control_rig_bp = _create_control_rig(manifest)
    _populate_hierarchy(control_rig_bp, manifest)
    unreal.EditorAssetLibrary.save_loaded_asset(control_rig_bp)
    unreal.log("[Rig.Sys] Unreal Control Rig generation complete.")


if __name__ == "__main__":
    main()
'''
