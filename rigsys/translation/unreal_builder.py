"""Unreal-side helper for importing model data and creating Control Rig structure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _load_unreal():
    """Import unreal lazily so this module can be imported outside Unreal."""
    import unreal  # type: ignore

    return unreal


def _safe_name(name: str) -> str:
    return name.replace(" ", "_")


def _vector_from_list(values: Iterable[float]):
    unreal = _load_unreal()
    x, y, z = [float(v) for v in values]
    return unreal.Vector(x, y, z)


def _rotator_from_list(values: Iterable[float]):
    unreal = _load_unreal()
    rx, ry, rz = [float(v) for v in values]
    return unreal.Rotator(rx, ry, rz)


def import_skeletal_mesh(fbx_file: str, destination_path: str, asset_name: Optional[str] = None) -> str:
    """Import a skeletal mesh FBX into Unreal content browser."""
    unreal = _load_unreal()
    destination = destination_path.rstrip("/")
    if not destination.startswith("/Game"):
        raise ValueError("destination_path must be inside /Game")

    task = unreal.AssetImportTask()
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    task.set_editor_property("filename", str(Path(fbx_file).expanduser().resolve()))
    task.set_editor_property("destination_path", destination)
    if asset_name:
        task.set_editor_property("destination_name", _safe_name(asset_name))

    fbx_options = unreal.FbxImportUI()
    fbx_options.set_editor_property("import_as_skeletal", True)
    fbx_options.set_editor_property("import_mesh", True)
    fbx_options.set_editor_property("import_animations", False)
    fbx_options.set_editor_property("create_physics_asset", False)
    task.set_editor_property("options", fbx_options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    if not task.imported_object_paths:
        raise RuntimeError(f"FBX import returned no assets for {fbx_file}")

    for imported_path in task.imported_object_paths:
        asset = unreal.EditorAssetLibrary.load_asset(imported_path)
        if isinstance(asset, unreal.SkeletalMesh):
            return imported_path

    raise RuntimeError(f"No SkeletalMesh was imported from {fbx_file}; imported={task.imported_object_paths}")


def create_control_rig_asset(package_path: str, asset_name: str, skeletal_mesh_path: str) -> str:
    """Create or replace a Control Rig asset bound to skeletal mesh."""
    unreal = _load_unreal()
    package = package_path.rstrip("/")
    if not package.startswith("/Game"):
        raise ValueError("package_path must be inside /Game")

    name = _safe_name(asset_name)
    control_rig_path = f"{package}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(control_rig_path):
        unreal.EditorAssetLibrary.delete_asset(control_rig_path)

    skeletal_mesh = unreal.EditorAssetLibrary.load_asset(skeletal_mesh_path)
    if skeletal_mesh is None:
        raise RuntimeError(f"Could not load skeletal mesh: {skeletal_mesh_path}")

    control_rig_asset = unreal.ControlRigBlueprintFactory.create_new_control_rig_asset(
        package_path=package,
        asset_name=name,
        skeleton=skeletal_mesh.skeleton,
    )
    if control_rig_asset is None:
        raise RuntimeError(f"Failed to create Control Rig asset at {control_rig_path}")

    control_rig_asset.set_preview_mesh(skeletal_mesh)
    unreal.EditorAssetLibrary.save_asset(control_rig_path, only_if_is_dirty=False)
    return control_rig_path


def _add_bone_if_missing(hierarchy, parent: str, name: str, position: List[float], rotation: List[float]):
    unreal = _load_unreal()
    element_key = hierarchy.get_bone_key(name)
    if element_key and hierarchy.contains(element_key):
        return

    parent_key = hierarchy.get_bone_key(parent) if parent else unreal.RigElementKey()
    transform = unreal.Transform(
        location=_vector_from_list(position),
        rotation=_rotator_from_list(rotation).quaternion(),
        scale=unreal.Vector(1.0, 1.0, 1.0),
    )
    hierarchy_controller = hierarchy.get_controller()
    hierarchy_controller.add_bone(name=name, parent_key=parent_key, transform=transform, transform_in_global=True)


def _add_control_if_missing(hierarchy, parent_control: Optional[str], control: Dict[str, Any]):
    unreal = _load_unreal()
    control_name = control["name"]
    key = hierarchy.get_control_key(control_name)
    if key and hierarchy.contains(key):
        return

    parent_key = hierarchy.get_control_key(parent_control) if parent_control else unreal.RigElementKey()
    shape_scale = control.get("scale", [1.0, 1.0, 1.0])
    control_position = control.get("position", [0.0, 0.0, 0.0])
    control_rotation = control.get("rotation", [0.0, 0.0, 0.0])
    initial_transform = unreal.Transform(
        location=_vector_from_list(control_position),
        rotation=_rotator_from_list(control_rotation).quaternion(),
        scale=_vector_from_list(shape_scale),
    )
    settings = unreal.RigControlSettings()
    settings.control_type = unreal.RigControlType.EULER_TRANSFORM
    settings.display_name = control_name
    settings.shape_name = control.get("shape", "Circle")

    hierarchy_controller = hierarchy.get_controller()
    hierarchy_controller.add_control(
        name=control_name,
        parent_key=parent_key,
        settings=settings,
        value=unreal.RigControlValue.make_euler_transform(unreal.EulerTransform()),
        offset_transform=initial_transform,
        shape_transform=initial_transform,
    )


def build_control_rig_from_payload(
    control_rig_path: str,
    translated_payload: Dict[str, Any],
) -> str:
    """Create hierarchy controls and bones from translated Maya payload."""
    unreal = _load_unreal()
    control_rig = unreal.EditorAssetLibrary.load_asset(control_rig_path)
    if control_rig is None:
        raise RuntimeError(f"Could not load Control Rig asset: {control_rig_path}")

    hierarchy = control_rig.hierarchy

    for module in translated_payload.get("modules", []):
        module_name = module["module_name"]
        parent_module = module.get("parent_module")
        module_root = f"{module_name}_ModuleRoot"
        parent_root = f"{parent_module}_ModuleRoot" if parent_module else ""

        _add_bone_if_missing(
            hierarchy=hierarchy,
            parent=parent_root,
            name=module_root,
            position=[0.0, 0.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
        )

        proxy_root_lookup = {}
        for proxy in module.get("proxies", []):
            proxy_name = proxy["name"]
            parent_proxy = proxy.get("parent")
            parent_bone = proxy_root_lookup.get(parent_proxy, module_root)
            proxy_bone_name = f"{module_name}_{proxy_name}_Proxy"
            proxy_root_lookup[proxy_name] = proxy_bone_name
            _add_bone_if_missing(
                hierarchy=hierarchy,
                parent=parent_bone,
                name=proxy_bone_name,
                position=proxy.get("position", [0.0, 0.0, 0.0]),
                rotation=proxy.get("rotation", [0.0, 0.0, 0.0]),
            )

        control_name_to_proxy_bone = {}
        for control in module.get("controls", []):
            driven_proxy = control.get("driven_proxy")
            if driven_proxy and driven_proxy in proxy_root_lookup:
                control_name_to_proxy_bone[control["name"]] = proxy_root_lookup[driven_proxy]
            else:
                control_name_to_proxy_bone[control["name"]] = module_root

        for control in module.get("controls", []):
            declared_parent = control.get("parent_control")
            if not declared_parent:
                parent_proxy_name = control.get("parent_proxy")
                if parent_proxy_name:
                    parent_proxy_bone = proxy_root_lookup.get(parent_proxy_name)
                    if parent_proxy_bone:
                        for existing_name, proxy_bone in control_name_to_proxy_bone.items():
                            if proxy_bone == parent_proxy_bone and existing_name != control["name"]:
                                declared_parent = existing_name
                                break
            _add_control_if_missing(hierarchy=hierarchy, parent_control=declared_parent, control=control)

    control_rig.request_auto_vm_recompilation()
    unreal.EditorAssetLibrary.save_asset(control_rig_path, only_if_is_dirty=False)
    return control_rig_path


def load_payload_from_json(payload_json_path: str) -> Dict[str, Any]:
    """Load Maya translated rig payload JSON from disk."""
    path = Path(payload_json_path).expanduser().resolve()
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def import_model_and_build_control_rig(
    *,
    payload_json_path: str,
    model_fbx_path: str,
    destination_path: str = "/Game/AutoRig",
    control_rig_name: Optional[str] = None,
) -> Dict[str, str]:
    """Import model FBX and auto-build control rig from translated payload."""
    payload = load_payload_from_json(payload_json_path)
    rig_name = payload.get("rig_name", "AutoRig")
    chosen_name = control_rig_name or f"{rig_name}_ControlRig"

    skeletal_mesh_path = import_skeletal_mesh(
        fbx_file=model_fbx_path,
        destination_path=destination_path,
        asset_name=f"{rig_name}_SK",
    )
    control_rig_path = create_control_rig_asset(
        package_path=destination_path,
        asset_name=chosen_name,
        skeletal_mesh_path=skeletal_mesh_path,
    )
    build_control_rig_from_payload(
        control_rig_path=control_rig_path,
        translated_payload=payload,
    )

    return {
        "payload": str(Path(payload_json_path).expanduser().resolve()),
        "skeletal_mesh": skeletal_mesh_path,
        "control_rig": control_rig_path,
    }
