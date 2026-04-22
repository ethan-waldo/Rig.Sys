"""Unreal-side helper for importing model data and creating Control Rig structure."""

from __future__ import annotations

import json
import math
import re
import copy
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


def _vec(values: Optional[Iterable[float]], default: Optional[List[float]] = None) -> List[float]:
    if values is None:
        return list(default or [0.0, 0.0, 0.0])
    data = [float(v) for v in values]
    if len(data) != 3:
        return list(default or [0.0, 0.0, 0.0])
    return data


def _vec_add(lhs: List[float], rhs: List[float]) -> List[float]:
    return [lhs[0] + rhs[0], lhs[1] + rhs[1], lhs[2] + rhs[2]]


def _vec_sub(lhs: List[float], rhs: List[float]) -> List[float]:
    return [lhs[0] - rhs[0], lhs[1] - rhs[1], lhs[2] - rhs[2]]


def _vec_scale(value: List[float], scalar: float) -> List[float]:
    return [value[0] * scalar, value[1] * scalar, value[2] * scalar]


def _vec_lerp(start: List[float], end: List[float], alpha: float) -> List[float]:
    return [
        start[0] + (end[0] - start[0]) * alpha,
        start[1] + (end[1] - start[1]) * alpha,
        start[2] + (end[2] - start[2]) * alpha,
    ]


def _build_proxy_map(module: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    proxies = module.get("proxies", [])
    result: Dict[str, Dict[str, Any]] = {}
    for proxy in proxies:
        name = proxy.get("name")
        if not name:
            continue
        result[name] = proxy
    return result


def _make_control(
    *,
    name: str,
    role: str,
    position: Iterable[float],
    rotation: Iterable[float],
    shape: str = "Circle",
    scale: Optional[Iterable[float]] = None,
    driven_proxy: Optional[str] = None,
    parent_proxy: Optional[str] = None,
    parent_control: Optional[str] = None,
    space: str = "global",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "name": name,
        "shape": shape,
        "scale": _vec(scale, [1.0, 1.0, 1.0]),
        "role": role,
        "position": _vec(position, [0.0, 0.0, 0.0]),
        "rotation": _vec(rotation, [0.0, 0.0, 0.0]),
        "driven_proxy": driven_proxy,
        "parent_proxy": parent_proxy,
        "parent_control": parent_control,
        "space": space,
        "metadata": metadata or {},
    }


def _infer_limb_pv(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    name_set = settings.get("name_set") or {}
    start_name = name_set.get("Start", "Start")
    mid_name = name_set.get("Mid", name_set.get("UpMid", "Mid"))
    end_name = name_set.get("End", "End")
    start_proxy = proxy_map.get(start_name)
    mid_proxy = proxy_map.get(mid_name)
    end_proxy = proxy_map.get(end_name)
    if not start_proxy or not mid_proxy or not end_proxy:
        return None

    start_pos = _vec(start_proxy.get("position"))
    mid_pos = _vec(mid_proxy.get("position"))
    end_pos = _vec(end_proxy.get("position"))
    line_mid = _vec_scale(_vec_add(start_pos, end_pos), 0.5)
    pv_dir = _vec_sub(mid_pos, line_mid)
    pv_len = math.sqrt(pv_dir[0] ** 2 + pv_dir[1] ** 2 + pv_dir[2] ** 2)
    if pv_len < 1e-5:
        pv_dir = [0.0, 0.0, 5.0]
    pv_mult = float(settings.get("pv_multiplier") or 1.0)
    pv_position = _vec_add(mid_pos, _vec_scale(pv_dir, max(pv_mult, 0.25)))
    return _make_control(
        name=f"{module['module_name']}_PV_CTRL",
        role="pole_vector",
        shape="Sphere",
        scale=settings.get("ctrl_scale", [1.0, 1.0, 1.0]),
        position=pv_position,
        rotation=[0.0, 0.0, 0.0],
        parent_control=None,
        driven_proxy=mid_name,
    )


def _add_fk_offsets(
    module: Dict[str, Any],
    existing_controls: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not settings.get("add_offsets") and not settings.get("add_offset"):
        return []
    output = []
    for control in existing_controls:
        role = control.get("role", "")
        if role not in {"fk", "limb_fk", "finger", "thumb", "ribbon"}:
            continue
        name = control["name"]
        output.append(
            _make_control(
                name=f"{name}_Local",
                role=f"{role}_offset",
                shape=control.get("shape", "Circle"),
                scale=_vec_scale(_vec(control.get("scale"), [1.0, 1.0, 1.0]), 0.85),
                position=control.get("position", [0.0, 0.0, 0.0]),
                rotation=control.get("rotation", [0.0, 0.0, 0.0]),
                parent_control=name,
                parent_proxy=control.get("parent_proxy"),
                driven_proxy=control.get("driven_proxy"),
                metadata={"generated_from": name},
            )
        )
    return output


def _add_hand_offset_controls(
    module: Dict[str, Any],
    existing_controls: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not settings.get("add_offset"):
        return []
    output = []
    for control in existing_controls:
        role = control.get("role", "")
        if role not in {"finger", "thumb", "hand_root", "hand_global"}:
            continue

        base_name = control["name"]
        updn_name = re.sub(r"_CTRL$", "_UpDn_CTRL", base_name)
        if updn_name == base_name:
            updn_name = f"{base_name}_UpDn"
        twist_name = re.sub(r"_CTRL$", "_Twist_CTRL", base_name)
        if twist_name == base_name:
            twist_name = f"{base_name}_Twist"
        splay_name = re.sub(r"_CTRL$", "_Splay_CTRL", base_name)
        if splay_name == base_name:
            splay_name = f"{base_name}_Splay"

        base_scale = _vec(control.get("scale"), [1.0, 1.0, 1.0])
        updn_scale = _vec_scale(base_scale, 0.9)
        twist_scale = _vec_scale(base_scale, 0.8)
        splay_scale = _vec_scale(base_scale, 0.75)

        base_position = control.get("position", [0.0, 0.0, 0.0])
        base_rotation = control.get("rotation", [0.0, 0.0, 0.0])
        driven_proxy = control.get("driven_proxy")
        parent_proxy = control.get("parent_proxy")

        output.append(
            _make_control(
                name=updn_name,
                role="hand_updn_offset",
                shape="Circle",
                scale=updn_scale,
                position=base_position,
                rotation=base_rotation,
                parent_control=base_name,
                parent_proxy=parent_proxy,
                driven_proxy=driven_proxy,
                metadata={"generated_from": base_name},
            )
        )
        output.append(
            _make_control(
                name=twist_name,
                role="hand_twist_offset",
                shape="Circle",
                scale=twist_scale,
                position=base_position,
                rotation=base_rotation,
                parent_control=updn_name,
                parent_proxy=parent_proxy,
                driven_proxy=driven_proxy,
                metadata={"generated_from": base_name},
            )
        )
        output.append(
            _make_control(
                name=splay_name,
                role="hand_splay_offset",
                shape="Circle",
                scale=splay_scale,
                position=base_position,
                rotation=base_rotation,
                parent_control=twist_name,
                parent_proxy=parent_proxy,
                driven_proxy=driven_proxy,
                metadata={"generated_from": base_name},
            )
        )
    return output


def _add_fk_reverse(module: Dict[str, Any], existing_controls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not settings.get("reverse"):
        return []
    chain = [c for c in existing_controls if c.get("role") in {"fk", "limb_fk"}]
    output = []
    parent_name = None
    for control in reversed(chain):
        name = control["name"]
        rev_name = re.sub(r"_CTRL$", "_Rev_CTRL", name)
        if rev_name == name:
            rev_name = f"{name}_Rev"
        output.append(
            _make_control(
                name=rev_name,
                role="reverse_fk",
                shape="Square",
                scale=_vec_scale(_vec(control.get("scale"), [1.0, 1.0, 1.0]), 0.75),
                position=control.get("position", [0.0, 0.0, 0.0]),
                rotation=control.get("rotation", [0.0, 0.0, 0.0]),
                parent_control=parent_name,
                parent_proxy=control.get("parent_proxy"),
                driven_proxy=control.get("driven_proxy"),
                metadata={"generated_from": name},
            )
        )
        parent_name = rev_name
    return output


def _add_quad_limb_auto_roll_controls(
    module: Dict[str, Any],
    proxy_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    name_set = settings.get("name_set") or {}
    start_name = name_set.get("Start", "Start")
    up_mid_name = name_set.get("UpMid", "UpMid")
    lo_mid_name = name_set.get("LoMid", "LoMid")
    end_name = name_set.get("End", "End")

    start_proxy = proxy_map.get(start_name)
    up_mid_proxy = proxy_map.get(up_mid_name)
    lo_mid_proxy = proxy_map.get(lo_mid_name)
    end_proxy = proxy_map.get(end_name)
    if not start_proxy or not up_mid_proxy or not lo_mid_proxy or not end_proxy:
        return []

    upper_count = 3
    lower_count = 5 if settings.get("curved_calf") else 3
    base_scale = _vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0])
    output = []

    start_pos = _vec(start_proxy.get("position"))
    up_mid_pos = _vec(up_mid_proxy.get("position"))
    start_rot = _vec(start_proxy.get("rotation"))
    up_mid_rot = _vec(up_mid_proxy.get("rotation"))
    previous = None
    for idx in range(upper_count):
        alpha = float(idx + 1) / float(upper_count + 1)
        ctrl_name = f"{module['module_name']}_UpperAutoRoll_{idx}_CTRL"
        output.append(
            _make_control(
                name=ctrl_name,
                role="quad_upper_auto_roll",
                shape="Circle",
                scale=_vec_scale(base_scale, 0.9),
                position=_vec_lerp(start_pos, up_mid_pos, alpha),
                rotation=_vec_lerp(start_rot, up_mid_rot, alpha),
                parent_control=previous,
                driven_proxy=up_mid_name,
                metadata={"alpha": alpha},
            )
        )
        previous = ctrl_name

    lo_mid_pos = _vec(lo_mid_proxy.get("position"))
    end_pos = _vec(end_proxy.get("position"))
    lo_mid_rot = _vec(lo_mid_proxy.get("rotation"))
    end_rot = _vec(end_proxy.get("rotation"))
    previous = None
    for idx in range(lower_count):
        alpha = float(idx + 1) / float(lower_count + 1)
        ctrl_name = f"{module['module_name']}_LowerAutoRoll_{idx}_CTRL"
        output.append(
            _make_control(
                name=ctrl_name,
                role="quad_lower_auto_roll",
                shape="Circle",
                scale=_vec_scale(base_scale, 0.85),
                position=_vec_lerp(lo_mid_pos, end_pos, alpha),
                rotation=_vec_lerp(lo_mid_rot, end_rot, alpha),
                parent_control=previous,
                driven_proxy=end_name,
                metadata={"alpha": alpha, "curved_calf": bool(settings.get("curved_calf"))},
            )
        )
        previous = ctrl_name

    output.append(
        _make_control(
            name=f"{module['module_name']}_AutoRollSettings_CTRL",
            role="quad_auto_roll_settings",
            shape="Square",
            scale=_vec_scale(base_scale, 1.1),
            position=start_pos,
            rotation=start_rot,
            metadata={
                "upper_controls": upper_count,
                "lower_controls": lower_count,
                "curved_calf": bool(settings.get("curved_calf")),
            },
        )
    )
    return output


def _add_limb_foot_roll(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not settings.get("foot"):
        return []
    chain = ["Global", "Heel", "OutBank", "InBank", "Pivot", "Ball", "Toe"]
    output = []
    parent = None
    for proxy_name in chain:
        proxy = proxy_map.get(proxy_name)
        if not proxy:
            continue
        ctrl_name = f"{module['module_name']}_{proxy_name}_Foot_CTRL"
        output.append(
            _make_control(
                name=ctrl_name,
                role="foot_roll",
                shape="Circle",
                scale=settings.get("ctrl_scale", [1.0, 1.0, 1.0]),
                position=proxy.get("position", [0.0, 0.0, 0.0]),
                rotation=proxy.get("rotation", [0.0, 0.0, 0.0]),
                driven_proxy=proxy_name,
                parent_proxy=proxy.get("parent"),
                parent_control=parent,
            )
        )
        parent = ctrl_name
    return output


def _add_ribbon_meta_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not settings.get("meta"):
        return []
    spans = int(settings.get("spans") or 0)
    if spans <= 0:
        return []
    start = proxy_map.get("Start")
    end = proxy_map.get("End")
    if not start or not end:
        return []
    start_pos = _vec(start.get("position"))
    end_pos = _vec(end.get("position"))
    start_rot = _vec(start.get("rotation"))
    end_rot = _vec(end.get("rotation"))
    output = []
    for idx in range(spans):
        alpha = 0.0 if spans == 1 else float(idx) / float(spans - 1)
        output.append(
            _make_control(
                name=f"{module['module_name']}_Meta_{idx}_CTRL",
                role="ribbon_meta",
                shape="Sphere",
                scale=settings.get("ctrl_scale", [1.0, 1.0, 1.0]),
                position=_vec_lerp(start_pos, end_pos, alpha),
                rotation=_vec_lerp(start_rot, end_rot, alpha),
                parent_control=None if idx == 0 else f"{module['module_name']}_Meta_{idx - 1}_CTRL",
            )
        )
    return output


def _add_point_target_controls(module: Dict[str, Any], existing_controls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    targets = settings.get("targets", [])
    influences = settings.get("targets_influence", [])
    if not targets:
        return []
    root_parent = existing_controls[0]["name"] if existing_controls else None
    output = []
    for idx, target in enumerate(targets):
        influence = influences[idx] if idx < len(influences) else 1.0
        output.append(
            _make_control(
                name=f"{module['module_name']}_Target_{idx}_CTRL",
                role="point_target_reference",
                shape="Circle",
                scale=settings.get("ctrl_scale", [1.0, 1.0, 1.0]),
                position=[0.0, 0.0, 0.0],
                rotation=[0.0, 0.0, 0.0],
                parent_control=root_parent,
                metadata={
                    "target_node": target,
                    "influence": influence,
                    "constrain_type": settings.get("constrain_type"),
                },
            )
        )
    return output


def _add_hand_meta_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not settings.get("meta"):
        return []
    output = []
    for proxy_name, proxy_data in proxy_map.items():
        if not (re.match(r"Finger\d+_0$", proxy_name) or proxy_name == "Thumb_0"):
            continue
        output.append(
            _make_control(
                name=f"{module['module_name']}_{proxy_name}_Meta_CTRL",
                role="metacarpal",
                shape="Square",
                scale=_vec_scale(_vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0]), 0.8),
                position=proxy_data.get("position", [0.0, 0.0, 0.0]),
                rotation=proxy_data.get("rotation", [0.0, 0.0, 0.0]),
                parent_proxy=proxy_data.get("parent"),
                driven_proxy=proxy_name,
            )
        )
    return output


def _add_face_settings_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    class_name = module.get("module_class")
    settings = module.get("module_settings", {})
    if class_name == "Lips":
        mouth = proxy_map.get("Mouth")
        if mouth:
            return [
                _make_control(
                    name=f"{module['module_name']}_LipSettings_CTRL",
                    role="lip_settings",
                    shape="Square",
                    scale=_vec_scale(_vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0]), 1.25),
                    position=mouth.get("position", [0.0, 0.0, 0.0]),
                    rotation=mouth.get("rotation", [0.0, 0.0, 0.0]),
                    driven_proxy="Mouth",
                )
            ]
    if class_name == "FollicleEye":
        eyeball = proxy_map.get("Eyeball")
        if eyeball:
            return [
                _make_control(
                    name=f"{module['module_name']}_LidSettings_CTRL",
                    role="lid_settings",
                    shape="Square",
                    scale=_vec_scale(_vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0]), 1.2),
                    position=eyeball.get("position", [0.0, 0.0, 0.0]),
                    rotation=eyeball.get("rotation", [0.0, 0.0, 0.0]),
                    driven_proxy="Eyeball",
                )
            ]
    return []


def generate_augmented_controls(module: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate extra controls from module settings and proxy layout.

    This upgrades module setting metadata into concrete Control Rig controls.
    """
    module_class = module.get("module_class", "")
    proxy_map = _build_proxy_map(module)
    existing_controls = list(module.get("controls", []))
    existing_names = {ctrl.get("name") for ctrl in existing_controls if ctrl.get("name")}
    output: List[Dict[str, Any]] = []

    def add_many(items: List[Dict[str, Any]]):
        for item in items:
            name = item.get("name")
            if not name or name in existing_names:
                continue
            existing_names.add(name)
            output.append(item)

    if module_class in {"FK", "FKSegment"}:
        add_many(_add_fk_offsets(module, existing_controls))
    if module_class == "Hand":
        add_many(_add_hand_offset_controls(module, existing_controls))
    if module_class == "FKSegment":
        add_many(_add_fk_reverse(module, existing_controls))
    if module_class in {"Limb", "QuadLimb"}:
        pv_ctrl = _infer_limb_pv(module, proxy_map)
        if pv_ctrl:
            add_many([pv_ctrl])
        add_many(_add_limb_foot_roll(module, proxy_map))
    if module_class == "QuadLimb":
        add_many(_add_quad_limb_auto_roll_controls(module, proxy_map))
    if module_class == "RibbonBindIK":
        add_many(_add_ribbon_meta_controls(module, proxy_map))
    if module_class == "PointTarget":
        add_many(_add_point_target_controls(module, existing_controls))
    if module_class == "Hand":
        add_many(_add_hand_meta_controls(module, proxy_map))
    if module_class in {"Lips", "FollicleEye"}:
        add_many(_add_face_settings_controls(module, proxy_map))
    return output


def get_module_controls(module: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return base controls plus generated module-logic controls."""
    controls = list(module.get("controls", []))
    controls.extend(generate_augmented_controls(module))
    return controls


def augment_payload_with_generated_controls(translated_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return payload copy with generated controls materialized.

    This converts module setting intent into concrete control entries
    before Unreal hierarchy creation, replacing metadata-only behavior.
    """
    payload = copy.deepcopy(translated_payload)
    for module in payload.get("modules", []):
        module["controls"] = get_module_controls(module)
    return payload


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

    materialized_payload = augment_payload_with_generated_controls(translated_payload)

    for module in materialized_payload.get("modules", []):
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

        module_controls = module.get("controls", [])
        control_name_to_proxy_bone = {}
        for control in module_controls:
            driven_proxy = control.get("driven_proxy")
            if driven_proxy and driven_proxy in proxy_root_lookup:
                control_name_to_proxy_bone[control["name"]] = proxy_root_lookup[driven_proxy]
            else:
                control_name_to_proxy_bone[control["name"]] = module_root

        for control in module_controls:
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
