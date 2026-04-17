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

        joints = self._collectJoints()
        controls = self._collectControls()
        rigLogicNodes = self._collectRigLogicNodes()
        ikFkSystems = self._collectIkFkSystems()

        rigVmInstructions = self._buildRigVmInstructions(
            ikFkSystems=ikFkSystems,
            rigLogicNodes=rigLogicNodes,
        )

        return {
            "schema_version": 4,
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
            "joints": joints,
            "controls": controls,
            "rig_logic_nodes": rigLogicNodes,
            "ik_fk_systems": ikFkSystems,
            "rigvm_instructions": rigVmInstructions,
            "custom_control_attributes": self._collectCustomControlAttributes(controls),
            "constraints": self._collectConstraints(),
            "connections": self._collectConnections(joints=joints, controls=controls),
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

    def _collectCustomControlAttributes(self, controls: List[Dict]) -> List[Dict]:
        """Collect user-defined custom attributes on controls for parity reconstruction."""
        data = []
        for control in controls:
            controlPath = control["path"]
            controlName = control["name"]
            userAttrs = cmds.listAttr(controlPath, userDefined=True) or []
            for attr in sorted(set(userAttrs)):
                plug = f"{controlPath}.{attr}"

                try:
                    attrType = cmds.getAttr(plug, type=True)
                except Exception:
                    continue

                if attrType in ("message", "TdataCompound", "compound"):
                    continue

                attrData = {
                    "control": controlName,
                    "control_path": controlPath,
                    "attribute": attr,
                    "type": attrType,
                    "value": self._safeGetAttrValue(plug),
                    "keyable": self._safeGetAttrState(plug, "keyable"),
                    "channel_box": self._safeGetAttrState(plug, "channelBox"),
                    "locked": self._safeGetAttrState(plug, "lock"),
                    "min": None,
                    "max": None,
                    "default": None,
                    "enum": None,
                }

                try:
                    if cmds.attributeQuery(attr, node=controlPath, minExists=True):
                        minimum = cmds.attributeQuery(attr, node=controlPath, minimum=True) or []
                        if minimum:
                            attrData["min"] = minimum[0]
                except Exception:
                    pass

                try:
                    if cmds.attributeQuery(attr, node=controlPath, maxExists=True):
                        maximum = cmds.attributeQuery(attr, node=controlPath, maximum=True) or []
                        if maximum:
                            attrData["max"] = maximum[0]
                except Exception:
                    pass

                try:
                    defaultValue = cmds.attributeQuery(attr, node=controlPath, listDefault=True) or []
                    if defaultValue:
                        attrData["default"] = defaultValue[0]
                except Exception:
                    pass

                try:
                    enumNames = cmds.attributeQuery(attr, node=controlPath, listEnum=True) or []
                    if enumNames:
                        attrData["enum"] = enumNames[0]
                except Exception:
                    pass

                data.append(attrData)

        return data

    def _collectConstraints(self) -> List[Dict]:
        """Collect supported Maya constraints for Unreal reconstruction attempts."""
        constraintTypes = {
            "parentConstraint": cmds.parentConstraint,
            "pointConstraint": cmds.pointConstraint,
            "orientConstraint": cmds.orientConstraint,
            "scaleConstraint": cmds.scaleConstraint,
            "aimConstraint": cmds.aimConstraint,
        }

        data = []
        for constraintType, queryCommand in constraintTypes.items():
            constraints = cmds.ls(type=constraintType, long=True) or []
            for constraint in sorted(set(constraints)):
                drivenParents = cmds.listRelatives(constraint, p=True, fullPath=True) or []
                drivenNode = self._shortName(drivenParents[0]) if drivenParents else None

                targets = []
                try:
                    targets = queryCommand(constraint, q=True, tl=True) or []
                except Exception:
                    targets = []

                weightAliases = []
                try:
                    weightAliases = queryCommand(constraint, q=True, wal=True) or []
                except Exception:
                    weightAliases = []

                weights = {}
                for alias in weightAliases:
                    try:
                        weights[alias] = cmds.getAttr(f"{constraint}.{alias}")
                    except Exception:
                        continue

                interpolation = None
                try:
                    interpolation = cmds.getAttr(f"{constraint}.interpType")
                except Exception:
                    interpolation = None

                data.append(
                    {
                        "name": self._shortName(constraint),
                        "path": constraint,
                        "type": constraintType,
                        "driven": drivenNode,
                        "targets": [self._shortName(target) for target in targets],
                        "weights": weights,
                        "interp_type": interpolation,
                    }
                )

        return data

    def _collectConnections(self, joints: List[Dict], controls: List[Dict]) -> List[Dict]:
        """Collect incoming attribute connections on exported rig nodes."""
        nodePaths = set()
        for joint in joints:
            nodePaths.add(joint["path"])
        for control in controls:
            nodePaths.add(control["path"])

        data = []
        for nodePath in sorted(nodePaths):
            connectionPairs = cmds.listConnections(
                nodePath,
                c=True,
                p=True,
                s=True,
                d=False,
            ) or []
            if len(connectionPairs) % 2 != 0:
                continue

            for index in range(0, len(connectionPairs), 2):
                destinationPlug = connectionPairs[index]
                sourcePlug = connectionPairs[index + 1]
                data.append(
                    {
                        "destination": destinationPlug,
                        "source": sourcePlug,
                    }
                )

        return data

    def _collectRigLogicNodes(self) -> List[Dict]:
        """Collect utility graph nodes commonly used for rig logic."""
        supportedTypes = [
            "blendColors",
            "reverse",
            "condition",
            "multiplyDivide",
            "plusMinusAverage",
            "multDoubleLinear",
            "clamp",
            "setRange",
            "remapValue",
        ]

        data = []
        for nodeType in supportedTypes:
            nodes = cmds.ls(type=nodeType, long=True) or []
            for node in sorted(set(nodes)):
                attrs = self._listNodeAttrs(node)
                values = {}
                for attr in attrs:
                    plug = f"{node}.{attr}"
                    value = self._safeGetAttrValue(plug)
                    if isinstance(value, (int, float, str, bool)) or value is None:
                        values[attr] = value
                    elif isinstance(value, (list, tuple)):
                        values[attr] = list(value)

                data.append(
                    {
                        "name": self._shortName(node),
                        "path": node,
                        "type": nodeType,
                        "values": values,
                    }
                )
        return data

    def _collectIkFkSystems(self) -> List[Dict]:
        """Collect common Maya IK/FK blend patterns for Unreal reconstruction."""
        blendNodes = cmds.ls(type="blendColors", long=True) or []
        systemsBySwitch = {}

        for blendNode in sorted(set(blendNodes)):
            blenderSource = self._firstConnection(f"{blendNode}.blender", source=True, destination=False)
            if blenderSource is None or not blenderSource.endswith(".IK_FK_Switch"):
                continue

            switchKey = blenderSource
            switchControl = blenderSource.split(".", 1)[0]
            system = systemsBySwitch.setdefault(
                switchKey,
                {
                    "switch_attribute_path": blenderSource,
                    "switch_attribute": self._shortPlug(blenderSource),
                    "switch_control": self._shortName(switchControl),
                    "blend_nodes": [],
                    "visibility_targets": {
                        "switch": [],
                        "reverse": [],
                    },
                },
            )

            drivenDestination = self._firstConnection(f"{blendNode}.output", source=False, destination=True)
            fkSource = self._firstConnection(f"{blendNode}.color1", source=True, destination=False)
            ikSource = self._firstConnection(f"{blendNode}.color2", source=True, destination=False)

            system["blend_nodes"].append(
                {
                    "node": self._shortName(blendNode),
                    "driven": self._shortPlug(drivenDestination) if drivenDestination else None,
                    "fk_source": self._shortPlug(fkSource) if fkSource else None,
                    "ik_source": self._shortPlug(ikSource) if ikSource else None,
                }
            )

        for switchKey, system in systemsBySwitch.items():
            switchOutputs = self._listConnections(switchKey, source=False, destination=True, plugs=True)

            reverseNodes = set()
            for outPlug in switchOutputs:
                if outPlug.endswith(".visibility"):
                    system["visibility_targets"]["switch"].append(self._shortPlug(outPlug))

                nodeName = self._plugNode(outPlug)
                if nodeName and self._safeNodeType(nodeName) == "reverse":
                    reverseNodes.add(nodeName)

            for reverseNode in sorted(reverseNodes):
                reverseOutputs = []
                reverseOutputs.extend(
                    self._listConnections(f"{reverseNode}.outputX", source=False, destination=True, plugs=True)
                )
                reverseOutputs.extend(
                    self._listConnections(f"{reverseNode}.output.outputX", source=False, destination=True, plugs=True)
                )
                for reverseOutput in reverseOutputs:
                    if reverseOutput.endswith(".visibility"):
                        system["visibility_targets"]["reverse"].append(self._shortPlug(reverseOutput))

            system["visibility_targets"]["switch"] = sorted(set(system["visibility_targets"]["switch"]))
            system["visibility_targets"]["reverse"] = sorted(set(system["visibility_targets"]["reverse"]))

        return sorted(systemsBySwitch.values(), key=lambda item: item["switch_attribute"])

    def _buildRigVmInstructions(self, ikFkSystems: List[Dict], rigLogicNodes: List[Dict]) -> List[Dict]:
        """Build generic RigVM instruction payloads for Unreal graph reconstruction."""
        instructions = []

        for system in ikFkSystems:
            switchAttr = system.get("switch_attribute")
            switchControl = system.get("switch_control")
            for blendNode in system.get("blend_nodes", []):
                if not blendNode.get("driven"):
                    continue
                instructions.append(
                    {
                        "type": "ik_fk_blend",
                        "switch_attribute": switchAttr,
                        "switch_control": switchControl,
                        "driven": blendNode.get("driven"),
                        "fk_source": blendNode.get("fk_source"),
                        "ik_source": blendNode.get("ik_source"),
                    }
                )

            visibilityTargets = system.get("visibility_targets", {})
            switchVisibility = visibilityTargets.get("switch", [])
            reverseVisibility = visibilityTargets.get("reverse", [])
            if switchVisibility or reverseVisibility:
                instructions.append(
                    {
                        "type": "ik_fk_visibility_switch",
                        "switch_attribute": switchAttr,
                        "switch_control": switchControl,
                        "switch_visible_targets": switchVisibility,
                        "reverse_visible_targets": reverseVisibility,
                    }
                )

        for logicNode in rigLogicNodes:
            nodeName = logicNode.get("name")
            nodeType = logicNode.get("type")
            values = logicNode.get("values", {})
            for attrName, value in values.items():
                if not isinstance(value, (int, float, bool, str)):
                    continue
                instructions.append(
                    {
                        "type": "logic_constant",
                        "node": nodeName,
                        "node_type": nodeType,
                        "attribute": attrName,
                        "value": value,
                    }
                )

        return instructions

    def _listNodeAttrs(self, node: str) -> List[str]:
        """Return list of node attrs if the Maya command is available."""
        if not hasattr(cmds, "listAttr"):
            return []
        try:
            attrs = cmds.listAttr(node, scalar=True, settable=True) or []
            return [attr for attr in attrs if attr not in ("message",)]
        except Exception:
            return []

    def _listConnections(self, plugOrNode: str, source: bool, destination: bool, plugs: bool = True) -> List[str]:
        """Safe wrapper around cmds.listConnections."""
        try:
            return cmds.listConnections(plugOrNode, s=source, d=destination, p=plugs) or []
        except Exception:
            return []

    def _firstConnection(self, plug: str, source: bool, destination: bool) -> Optional[str]:
        """Get first connection from a plug for a given direction."""
        connections = self._listConnections(plug, source=source, destination=destination, plugs=True)
        if not connections:
            return None
        return connections[0]

    def _plugNode(self, plug: str) -> Optional[str]:
        """Return node name from plug notation."""
        if not plug or "." not in plug:
            return None
        return plug.split(".", 1)[0]

    def _shortPlug(self, plug: Optional[str]) -> Optional[str]:
        """Return a short node.attr plug."""
        if plug is None:
            return None
        if "." not in plug:
            return self._shortName(plug)
        node, attr = plug.split(".", 1)
        return f"{self._shortName(node)}.{attr}"

    def _safeNodeType(self, node: str) -> Optional[str]:
        """Safely query Maya node type."""
        if not hasattr(cmds, "nodeType"):
            return None
        try:
            return cmds.nodeType(node)
        except Exception:
            return None

    def _safeGetAttrValue(self, plug: str):
        """Get Maya attribute value, handling scalar/list return conventions."""
        try:
            value = cmds.getAttr(plug)
        except Exception:
            return None

        if isinstance(value, list) and len(value) == 1:
            entry = value[0]
            if isinstance(entry, tuple):
                return list(entry)
        return value

    def _safeGetAttrState(self, plug: str, state: str):
        """Get Maya attribute state flags safely."""
        queryByState = {
            "keyable": {"keyable": True},
            "channelBox": {"channelBox": True},
            "lock": {"lock": True},
        }
        kwargs = queryByState.get(state, {})
        if not kwargs:
            return None

        try:
            return cmds.getAttr(plug, **kwargs)
        except Exception:
            return None

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
        template = '''"""Generated by Rig.Sys UnrealControlRigExport."""

import json
import os

import unreal


MANIFEST_PATH = __MANIFEST_PATH__


def _log_warning(message):
    unreal.log_warning(f"[Rig.Sys] {message}")


def _load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        raise RuntimeError(f"Manifest not found: {MANIFEST_PATH}")

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
            _log_warning(f"Call failed for {method}: {exc}")
            return False
    return False


def _to_transform(translation, rotation, scale):
    return unreal.Transform(
        rotation=unreal.Rotator(rotation[0], rotation[1], rotation[2]),
        translation=unreal.Vector(translation[0], translation[1], translation[2]),
        scale3d=unreal.Vector(scale[0], scale[1], scale[2]),
    )


def _import_fbx_if_present(manifest):
    fbx_path = manifest.get("export_files", {}).get("fbx", "")
    if not fbx_path:
        return
    if not os.path.exists(fbx_path):
        _log_warning(f"FBX path does not exist: {fbx_path}")
        return

    unreal_data = manifest.get("unreal", {})
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
    unreal_data = manifest.get("unreal", {})
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
                    ((joint["name"], parent, transform), {"setup_undo": False}),
                    ((joint["name"], parent, transform, False), {}),
                    ((joint["name"], parent, transform), {}),
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
                    ((control["name"], parent, control_settings, transform), {"setup_undo": False}),
                    ((control["name"], parent, control_settings, transform, transform), {"setup_undo": False}),
                    ((control["name"], parent, control_settings, transform, transform, False), {}),
                    ((control["name"], parent, control_settings, transform, transform, False, False), {}),
                ],
            )

        if not control_added and hasattr(hierarchy, "add_null"):
            _try_call(
                hierarchy.add_null,
                [
                    ((control["name"], parent, transform), {"setup_undo": False}),
                    ((control["name"], parent, transform, False), {}),
                    ((control["name"], parent, transform), {}),
                ],
            )


def _apply_custom_attributes(control_rig_bp, manifest):
    """Try to mirror Maya custom control attrs as Control Rig member variables."""
    attrs = manifest.get("custom_control_attributes", [])
    if not attrs:
        return

    if not hasattr(control_rig_bp, "add_member_variable"):
        _log_warning("Control Rig blueprint does not expose add_member_variable; skipping custom attrs.")
        return

    maya_type_to_unreal = {
        "bool": "bool",
        "long": "int32",
        "short": "int32",
        "byte": "int32",
        "enum": "int32",
        "float": "float",
        "double": "float",
        "doubleAngle": "float",
        "doubleLinear": "float",
        "string": "string",
    }

    for attr in attrs:
        maya_type = attr.get("type")
        unreal_type = maya_type_to_unreal.get(maya_type)
        if unreal_type is None:
            continue

        variable_name = f"{attr.get('control', 'CTRL')}__{attr.get('attribute', 'Attr')}"
        variable_name = variable_name.replace(":", "_").replace("|", "_").replace(".", "_")

        default_value = attr.get("value")
        if default_value is None:
            default_value = attr.get("default")
        if isinstance(default_value, list):
            if len(default_value) == 1:
                default_value = default_value[0]
            else:
                default_value = str(default_value)
        if default_value is None:
            default_value = ""

        _try_call(
            control_rig_bp.add_member_variable,
            [
                ((variable_name, unreal_type), {}),
                ((variable_name, unreal_type, str(default_value)), {}),
                ((variable_name, unreal_type, False, False, str(default_value)), {}),
            ],
        )


def _apply_constraints(control_rig_bp, manifest):
    """Attempt best-effort reconstruction of Maya constraints."""
    if not hasattr(control_rig_bp, "get_hierarchy_controller"):
        return

    hierarchy = control_rig_bp.get_hierarchy_controller()
    if hierarchy is None:
        return

    for constraint in manifest.get("constraints", []):
        ctype = constraint.get("type")
        driven = constraint.get("driven")
        targets = constraint.get("targets", [])
        if not driven or not targets:
            continue

        if ctype == "parentConstraint" and hasattr(hierarchy, "set_parent"):
            parent = targets[0]
            _try_call(
                hierarchy.set_parent,
                [
                    ((driven, parent), {"maintain_global_transform": True, "setup_undo": False}),
                    ((driven, parent), {"maintain_global_transform": True}),
                    ((driven, parent, True), {}),
                    ((driven, parent), {}),
                ],
            )
            continue

        # Point/orient/scale/aim need explicit graph units in Control Rig; keep metadata for follow-up.
        _log_warning(
            f"Constraint type '{ctype}' on '{driven}' requires graph-level reconstruction; metadata preserved."
        )


def _apply_ik_fk_systems(control_rig_bp, manifest):
    """Apply best-effort IK/FK behavior scaffolding."""
    systems = manifest.get("ik_fk_systems", [])
    if not systems:
        return

    supports_member_variables = hasattr(control_rig_bp, "add_member_variable")
    if not supports_member_variables:
        _log_warning("Control Rig blueprint has no add_member_variable; IK/FK vars will be metadata-only.")

    hierarchy = None
    if hasattr(control_rig_bp, "get_hierarchy_controller"):
        hierarchy = control_rig_bp.get_hierarchy_controller()

    for system in systems:
        switch_attr = system.get("switch_attribute", "")
        if not switch_attr:
            continue

        # We keep the naming deterministic so follow-up graph tools can find these vars.
        variable_name = f"IKFK__{switch_attr}".replace(":", "_").replace("|", "_").replace(".", "_")
        if supports_member_variables:
            _try_call(
                control_rig_bp.add_member_variable,
                [
                    ((variable_name, "float"), {}),
                    ((variable_name, "float", "0.0"), {}),
                    ((variable_name, "float", False, False, "0.0"), {}),
                ],
            )

        switch_default = _get_ik_fk_switch_default(manifest, switch_attr)
        switch_visible_default = switch_default >= 0.5

        # Visibility remaps require graph units in most UE versions; apply hierarchy visibility if exposed.
        switch_vis = system.get("visibility_targets", {}).get("switch", [])
        reverse_vis = system.get("visibility_targets", {}).get("reverse", [])
        if hierarchy is not None and (switch_vis or reverse_vis):
            for target in switch_vis:
                _set_hierarchy_visibility(hierarchy, _plug_to_node(target), switch_visible_default)
            for target in reverse_vis:
                _set_hierarchy_visibility(hierarchy, _plug_to_node(target), not switch_visible_default)

        if switch_vis or reverse_vis:
            _log_warning(
                "IK/FK visibility targets detected; graph-level wiring is required for full parity."
            )


def _apply_rig_logic_nodes(control_rig_bp, manifest):
    """Apply best-effort rig-logic utility nodes as exposed variables."""
    logic_nodes = manifest.get("rig_logic_nodes", [])
    if not logic_nodes:
        return

    if not hasattr(control_rig_bp, "add_member_variable"):
        _log_warning("Control Rig blueprint has no add_member_variable; rig-logic vars will be metadata-only.")
        return

    supported_variable_types = (int, float, bool, str)

    for logic_node in logic_nodes:
        node_name = logic_node.get("name", "LogicNode")
        for attr_name, value in (logic_node.get("values") or {}).items():
            if not isinstance(value, supported_variable_types):
                continue

            variable_name = f"Logic__{node_name}__{attr_name}"
            variable_name = variable_name.replace(":", "_").replace("|", "_").replace(".", "_")

            if isinstance(value, bool):
                var_type = "bool"
            elif isinstance(value, int):
                var_type = "int32"
            elif isinstance(value, float):
                var_type = "float"
            else:
                var_type = "string"

            default_literal = str(value).lower() if isinstance(value, bool) else str(value)

            _try_call(
                control_rig_bp.add_member_variable,
                [
                    ((variable_name, var_type), {}),
                    ((variable_name, var_type, default_literal), {}),
                    ((variable_name, var_type, False, False, default_literal), {}),
                ],
            )


def _apply_rigvm_instructions(control_rig_bp, manifest):
    """Apply RigVM instruction nodes and links when controller APIs are available."""
    instructions = manifest.get("rigvm_instructions", [])
    if not instructions:
        return

    controller = None
    if hasattr(control_rig_bp, "get_controller_by_name"):
        for controller_name in ("RigVMModel", "Rig Graph", "RigVM"):
            try:
                controller = control_rig_bp.get_controller_by_name(controller_name)
            except Exception:
                controller = None
            if controller is not None:
                break
    if controller is None and hasattr(control_rig_bp, "get_controller"):
        try:
            controller = control_rig_bp.get_controller()
        except Exception:
            controller = None

    if controller is None:
        _log_warning("RigVM controller API not available; rigvm_instructions kept as metadata.")
        return

    for index, instruction in enumerate(instructions):
        if _apply_single_rigvm_instruction(controller, instruction, index):
            continue

        # Fallback to comment payloads when unit-level construction is unavailable.
        if hasattr(controller, "add_comment_node"):
            payload = json.dumps(instruction, sort_keys=True)
            position = unreal.Vector2D(float(index) * 12.0, 0.0)
            _try_call(
                controller.add_comment_node,
                [
                    ((payload, position, unreal.Vector2D(620.0, 70.0)), {}),
                    ((payload, position), {}),
                    ((payload,), {}),
                ],
            )
        else:
            _log_warning("RigVM controller has no add_comment_node fallback; instruction skipped.")


def _apply_single_rigvm_instruction(controller, instruction, index):
    """Apply one rigvm instruction. Returns True when any concrete operation succeeded."""
    instruction_type = instruction.get("type")

    if instruction_type == "ik_fk_blend":
        return _apply_ik_fk_blend_instruction(controller, instruction, index)
    if instruction_type == "ik_fk_visibility_switch":
        return _apply_visibility_instruction(controller, instruction, index)
    if instruction_type == "logic_constant":
        return _apply_logic_constant_instruction(controller, instruction, index)

    return False


def _apply_ik_fk_blend_instruction(controller, instruction, index):
    """Build a best-effort float-lerp unit and connect instruction pins."""
    if not hasattr(controller, "add_unit_node_from_struct_path"):
        return False

    node_position = unreal.Vector2D(float(index) * 240.0, 200.0)
    node_name = f"RigSys_IKFKBlend_{index}"
    unit_node = _try_add_unit_node(
        controller=controller,
        struct_paths=[
            "/Script/RigVM.RigVMFunction_MathFloatLerp",
            "/Script/ControlRig.RigUnit_MathFloatLerp",
        ],
        position=node_position,
        node_name=node_name,
    )
    if unit_node is None:
        return False

    switch_attr = instruction.get("switch_attribute")
    fk_source = instruction.get("fk_source")
    ik_source = instruction.get("ik_source")
    driven = instruction.get("driven")
    if not all([switch_attr, fk_source, ik_source, driven]):
        return True

    node_path = _resolve_node_path(unit_node, node_name)
    if node_path is None:
        return True

    links_added = False
    links_added |= _add_link_if_possible(controller, switch_attr, f"{node_path}.T")
    links_added |= _add_link_if_possible(controller, fk_source, f"{node_path}.A")
    links_added |= _add_link_if_possible(controller, ik_source, f"{node_path}.B")
    links_added |= _add_link_if_possible(controller, f"{node_path}.Result", driven)

    if not links_added:
        _log_warning(f"IK/FK blend node created but no links could be resolved: {instruction}")
    return True


def _apply_visibility_instruction(controller, instruction, index):
    """Build a best-effort bool invert chain for IK/FK visibility switching."""
    if not hasattr(controller, "add_unit_node_from_struct_path"):
        return False

    node_position = unreal.Vector2D(float(index) * 240.0, 420.0)
    node_name = f"RigSys_IKFKVisibility_{index}"
    not_node = _try_add_unit_node(
        controller=controller,
        struct_paths=[
            "/Script/RigVM.RigVMFunction_MathBoolNot",
            "/Script/ControlRig.RigUnit_MathBoolNot",
        ],
        position=node_position,
        node_name=node_name,
    )
    if not_node is None:
        not_path = _resolve_node_path(not_node, node_name)
        switch_attr = instruction.get("switch_attribute")
        if switch_attr and not_path:
            _add_link_if_possible(controller, switch_attr, f"{not_path}.Value")
            for target in instruction.get("reverse_visible_targets", []):
                _add_link_if_possible(controller, f"{not_path}.Result", target)

    any_direct = False
    switch_attr = instruction.get("switch_attribute")
    if switch_attr:
        for target in instruction.get("switch_visible_targets", []):
            any_direct |= _add_link_if_possible(controller, switch_attr, target)

    return not_node is not None or any_direct


def _apply_logic_constant_instruction(controller, instruction, index):
    """Build constant nodes for scalar rig logic values."""
    if not hasattr(controller, "add_unit_node_from_struct_path"):
        return False

    value = instruction.get("value")
    attr = instruction.get("attribute")
    node = instruction.get("node")
    if attr is None or node is None:
        return False

    if isinstance(value, bool):
        struct_paths = ["/Script/RigVM.RigVMFunction_MathBoolConst", "/Script/ControlRig.RigUnit_MathBoolConst"]
        pin_name = "Value"
    elif isinstance(value, int):
        struct_paths = ["/Script/RigVM.RigVMFunction_MathIntConst", "/Script/ControlRig.RigUnit_MathIntConst"]
        pin_name = "Value"
    elif isinstance(value, float):
        struct_paths = ["/Script/RigVM.RigVMFunction_MathFloatConst", "/Script/ControlRig.RigUnit_MathFloatConst"]
        pin_name = "Value"
    else:
        return False

    node_name = f"RigSys_LogicConst_{index}"
    node_position = unreal.Vector2D(float(index) * 240.0, 620.0)
    const_node = _try_add_unit_node(controller, struct_paths, node_position, node_name)
    if const_node is None:
        return False

    node_path = _resolve_node_path(const_node, node_name)
    if node_path is None:
        return True

    _set_pin_default_if_possible(controller, f"{node_path}.{pin_name}", value)
    return True


def _try_add_unit_node(controller, struct_paths, position, node_name):
    """Try to create a unit node from candidate struct paths."""
    for struct_path in struct_paths:
        added = _try_call(
            controller.add_unit_node_from_struct_path,
            [
                ((struct_path, "Execute", position, node_name), {}),
                ((struct_path, "Execute", position), {}),
                ((struct_path, position), {}),
                ((struct_path,), {}),
            ],
        )
        if added:
            # Try to resolve by node name first; fallback returns None if unavailable.
            return node_name
    return None


def _resolve_node_path(node_handle, fallback_name):
    """Best-effort node path resolver for controller return variants."""
    if node_handle is None:
        return fallback_name
    if isinstance(node_handle, str):
        return node_handle
    if hasattr(node_handle, "get_node_path"):
        try:
            return node_handle.get_node_path()
        except Exception:
            pass
    if hasattr(node_handle, "node_path"):
        try:
            return node_handle.node_path
        except Exception:
            pass
    return fallback_name


def _add_link_if_possible(controller, source_pin, target_pin):
    """Create a RigVM link if controller supports it."""
    if not source_pin or not target_pin:
        return False
    if not hasattr(controller, "add_link"):
        return False
    return _try_call(
        controller.add_link,
        [
            ((source_pin, target_pin), {}),
            ((source_pin, target_pin, False), {}),
        ],
    )


def _set_pin_default_if_possible(controller, pin_path, value):
    """Set default value for a pin when available."""
    if not hasattr(controller, "set_pin_default_value"):
        return False
    value_text = str(value).lower() if isinstance(value, bool) else str(value)
    return _try_call(
        controller.set_pin_default_value,
        [
            ((pin_path, value_text, False), {}),
            ((pin_path, value_text), {}),
        ],
    )


def _plug_to_node(plug):
    if not plug or "." not in plug:
        return plug
    return plug.split(".", 1)[0]


def _get_ik_fk_switch_default(manifest, switch_attribute):
    custom_attrs = manifest.get("custom_control_attributes", [])
    for attr in custom_attrs:
        composed = f"{attr.get('control', '')}.{attr.get('attribute', '')}"
        if composed != switch_attribute:
            continue
        value = attr.get("value")
        if isinstance(value, (float, int)):
            return float(value)
        default = attr.get("default")
        if isinstance(default, (float, int)):
            return float(default)
    return 0.0


def _set_hierarchy_visibility(hierarchy, node_name, is_visible):
    if not node_name:
        return

    if hasattr(hierarchy, "set_control_visibility"):
        _try_call(
            hierarchy.set_control_visibility,
            [
                ((node_name, is_visible), {"setup_undo": False}),
                ((node_name, is_visible), {}),
            ],
        )
        return

    if hasattr(hierarchy, "set_visible"):
        _try_call(
            hierarchy.set_visible,
            [
                ((node_name, is_visible), {"setup_undo": False}),
                ((node_name, is_visible), {}),
            ],
        )
        return


def _persist_metadata(control_rig_bp, manifest):
    """Save high-fidelity rig data as metadata for post-processing passes."""
    if not hasattr(unreal.EditorAssetLibrary, "set_metadata_tag"):
        return

    asset_path = control_rig_bp.get_path_name()
    metadata_payloads = {
        "RigSys.ManifestSchemaVersion": str(manifest.get("schema_version", "")),
        "RigSys.ConstraintCount": str(len(manifest.get("constraints", []))),
        "RigSys.ConnectionCount": str(len(manifest.get("connections", []))),
        "RigSys.CustomAttributeCount": str(len(manifest.get("custom_control_attributes", []))),
        "RigSys.RigLogicNodeCount": str(len(manifest.get("rig_logic_nodes", []))),
        "RigSys.IkFkSystemCount": str(len(manifest.get("ik_fk_systems", []))),
        "RigSys.RigVMInstructionCount": str(len(manifest.get("rigvm_instructions", []))),
        "RigSys.ConstraintsJSON": json.dumps(manifest.get("constraints", [])),
        "RigSys.ConnectionsJSON": json.dumps(manifest.get("connections", [])),
        "RigSys.CustomAttributesJSON": json.dumps(manifest.get("custom_control_attributes", [])),
        "RigSys.RigLogicNodesJSON": json.dumps(manifest.get("rig_logic_nodes", [])),
        "RigSys.IkFkSystemsJSON": json.dumps(manifest.get("ik_fk_systems", [])),
        "RigSys.RigVMInstructionsJSON": json.dumps(manifest.get("rigvm_instructions", [])),
    }

    for key, value in metadata_payloads.items():
        try:
            unreal.EditorAssetLibrary.set_metadata_tag(asset_path, key, value)
        except Exception as exc:
            _log_warning(f"Failed to write metadata '{key}': {exc}")


def main():
    manifest = _load_manifest()
    _import_fbx_if_present(manifest)
    control_rig_bp = _create_control_rig(manifest)
    _populate_hierarchy(control_rig_bp, manifest)
    _apply_custom_attributes(control_rig_bp, manifest)
    _apply_constraints(control_rig_bp, manifest)
    _apply_ik_fk_systems(control_rig_bp, manifest)
    _apply_rig_logic_nodes(control_rig_bp, manifest)
    _apply_rigvm_instructions(control_rig_bp, manifest)
    _persist_metadata(control_rig_bp, manifest)
    unreal.EditorAssetLibrary.save_loaded_asset(control_rig_bp)
    unreal.log("[Rig.Sys] Unreal Control Rig generation complete.")


if __name__ == "__main__":
    main()
'''
        return template.replace("__MANIFEST_PATH__", manifestLiteral)
