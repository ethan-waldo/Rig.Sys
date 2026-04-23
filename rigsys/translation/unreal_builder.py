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


def _graph_safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", _safe_name(name))


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


def _axis_to_vec(axis: Optional[str]) -> List[float]:
    if not axis:
        return [0.0, 0.0, 0.0]
    axis = axis.strip().lower()
    sign = -1.0 if axis.startswith("-") else 1.0
    key = axis[-1] if axis else "x"
    if key == "x":
        return [sign, 0.0, 0.0]
    if key == "y":
        return [0.0, sign, 0.0]
    if key == "z":
        return [0.0, 0.0, sign]
    return [0.0, 0.0, 0.0]


def _vec_pin_literal(values: Iterable[float]) -> str:
    x, y, z = _vec(values, [0.0, 0.0, 0.0])
    return f"(X={x},Y={y},Z={z})"


def _module_shape(settings: Dict[str, Any], fallback: str = "Circle") -> str:
    shape = settings.get("ctrl_shape")
    if shape is None:
        return fallback
    return str(shape)


def _build_proxy_map(module: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    proxies = module.get("proxies", [])
    result: Dict[str, Dict[str, Any]] = {}
    for proxy in proxies:
        name = proxy.get("name")
        if not name:
            continue
        result[name] = proxy
    return result


def _ordered_proxy_chain(
    module: Dict[str, Any],
    *,
    exclude_names: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    proxies = module.get("proxies", [])
    if not proxies:
        return []

    excluded = set(exclude_names or [])
    by_name: Dict[str, Dict[str, Any]] = {}
    order_index: Dict[str, int] = {}
    children: Dict[Optional[str], List[str]] = {}
    for idx, proxy in enumerate(proxies):
        name = proxy.get("name")
        if not name:
            continue
        by_name[name] = proxy
        order_index[name] = idx
        children.setdefault(proxy.get("parent"), []).append(name)

    if not by_name:
        return []

    for names in children.values():
        names.sort(key=lambda candidate: order_index.get(candidate, 0))

    roots = [name for name, proxy in by_name.items() if proxy.get("parent") not in by_name]
    if "Start" in by_name:
        current = "Start"
    elif "Root" in by_name:
        current = "Root"
    elif roots:
        current = roots[0]
    else:
        current = next(iter(by_name.keys()))

    chain: List[Dict[str, Any]] = []
    visited = set()
    while current and current not in visited:
        visited.add(current)
        if current not in excluded:
            chain.append(by_name[current])
        child_names = [name for name in children.get(current, []) if name not in visited]
        if not child_names:
            break

        non_upvector = [name for name in child_names if name.lower() != "upvector"]
        current = non_upvector[0] if non_upvector else child_names[0]

    return chain


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
                shape=_module_shape(settings, "Circle"),
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


def _add_limb_deform_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    count = int(settings.get("number_of_joints") or 0)
    if count <= 1:
        return []
    name_set = settings.get("name_set") or {}
    start_name = name_set.get("Start", "Start")
    end_name = name_set.get("End", "End")
    start_proxy = proxy_map.get(start_name)
    end_proxy = proxy_map.get(end_name)
    if not start_proxy or not end_proxy:
        return []

    start_pos = _vec(start_proxy.get("position"))
    end_pos = _vec(end_proxy.get("position"))
    start_rot = _vec(start_proxy.get("rotation"))
    end_rot = _vec(end_proxy.get("rotation"))
    base_scale = _vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0])

    output = []
    parent = None
    for idx in range(count):
        alpha = 0.0 if count == 1 else float(idx) / float(count - 1)
        ctrl_name = f"{module['module_name']}_Deform_{idx}_CTRL"
        output.append(
            _make_control(
                name=ctrl_name,
                role="limb_deform",
                shape=_module_shape(settings, "Circle"),
                scale=_vec_scale(base_scale, 0.6),
                position=_vec_lerp(start_pos, end_pos, alpha),
                rotation=_vec_lerp(start_rot, end_rot, alpha),
                parent_control=parent,
                driven_proxy=end_name,
                metadata={"index": idx, "count": count},
            )
        )
        parent = ctrl_name
    return output


def _add_limb_ik_floor_anchor(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not settings.get("ik_ctrl_to_floor"):
        return []
    name_set = settings.get("name_set") or {}
    end_name = name_set.get("End", "End")
    end_proxy = proxy_map.get(end_name)
    if not end_proxy:
        return []
    pos = _vec(end_proxy.get("position"))
    floor_pos = [pos[0], 0.0, pos[2]]
    return [
        _make_control(
            name=f"{module['module_name']}_IKFloor_CTRL",
            role="ik_floor_anchor",
            shape=_module_shape(settings, "Square"),
            scale=_vec_scale(_vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0]), 0.75),
            position=floor_pos,
            rotation=[0.0, 0.0, 0.0],
            driven_proxy=end_name,
        )
    ]


def _add_segment_driver_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    count = int(settings.get("segments") or 0)
    if count <= 0:
        return []
    start_proxy = proxy_map.get("Start")
    end_proxy = proxy_map.get("End")
    if not start_proxy or not end_proxy:
        return []

    start_pos = _vec(start_proxy.get("position"))
    end_pos = _vec(end_proxy.get("position"))
    start_rot = _vec(start_proxy.get("rotation"))
    end_rot = _vec(end_proxy.get("rotation"))
    output = []
    parent = None
    end_proxy_name = str(end_proxy.get("name") or "End")
    for idx in range(count):
        alpha = 0.0 if count == 1 else float(idx) / float(count - 1)
        name = f"{module['module_name']}_SegmentDriver_{idx}_CTRL"
        output.append(
            _make_control(
                name=name,
                role="segment_driver",
                shape=_module_shape(settings, "Circle"),
                scale=_vec_scale(_vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0]), 0.7),
                position=_vec_lerp(start_pos, end_pos, alpha),
                rotation=_vec_lerp(start_rot, end_rot, alpha),
                parent_control=parent,
                driven_proxy=end_proxy_name,
                metadata={"segment_index": idx},
            )
        )
        parent = name
    return output


def _add_fk_ik_rail_controls(module: Dict[str, Any]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not settings.get("ik_rail"):
        return []

    chain = _ordered_proxy_chain(module, exclude_names={"UpVector"})
    if len(chain) < 2:
        return []

    base_scale = _vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0])
    output = []
    parent = None
    for idx, proxy in enumerate(chain):
        proxy_name = proxy.get("name")
        if not proxy_name:
            continue
        ctrl_name = f"{module['module_name']}_IKRail_{idx}_CTRL"
        output.append(
            _make_control(
                name=ctrl_name,
                role="ik_rail_driver",
                shape=_module_shape(settings, "Circle"),
                scale=_vec_scale(base_scale, 0.65),
                position=proxy.get("position", [0.0, 0.0, 0.0]),
                rotation=proxy.get("rotation", [0.0, 0.0, 0.0]),
                parent_control=parent,
                driven_proxy=proxy_name,
                parent_proxy=proxy.get("parent"),
                metadata={"rail_index": idx},
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
                shape=_module_shape(settings, "Sphere"),
                scale=settings.get("ctrl_scale", [1.0, 1.0, 1.0]),
                position=_vec_lerp(start_pos, end_pos, alpha),
                rotation=_vec_lerp(start_rot, end_rot, alpha),
                parent_control=None if idx == 0 else f"{module['module_name']}_Meta_{idx - 1}_CTRL",
            )
        )
    return output


def _add_ribbon_bind_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    count = int(settings.get("number_of_joints") or 0)
    if count <= 0:
        return []

    start = proxy_map.get("Start")
    end = proxy_map.get("End")
    if not start or not end:
        chain = _ordered_proxy_chain(module, exclude_names={"UpVector"})
        if len(chain) >= 2:
            start = chain[0]
            end = chain[-1]
    if not start or not end:
        return []

    start_pos = _vec(start.get("position"))
    end_pos = _vec(end.get("position"))
    start_rot = _vec(start.get("rotation"))
    end_rot = _vec(end.get("rotation"))
    base_scale = _vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0])
    proxy_chain = _ordered_proxy_chain(module, exclude_names={"UpVector"})
    chain_count = len(proxy_chain)

    output = []
    parent = None
    for idx in range(count):
        alpha = 0.0 if count == 1 else float(idx) / float(count - 1)
        driven_proxy = None
        parent_proxy = None
        if chain_count > 0:
            chain_index = int(round(alpha * float(max(chain_count - 1, 0))))
            chain_index = max(0, min(chain_index, chain_count - 1))
            sampled_proxy = proxy_chain[chain_index]
            driven_proxy = sampled_proxy.get("name")
            parent_proxy = sampled_proxy.get("parent")
        name = f"{module['module_name']}_Bind_{idx}_CTRL"
        output.append(
            _make_control(
                name=name,
                role="ribbon_bind_driver",
                shape=_module_shape(settings, "Sphere"),
                scale=_vec_scale(base_scale, 0.6),
                position=_vec_lerp(start_pos, end_pos, alpha),
                rotation=_vec_lerp(start_rot, end_rot, alpha),
                parent_control=parent,
                driven_proxy=driven_proxy,
                parent_proxy=parent_proxy,
                metadata={"bind_index": idx, "count": count},
            )
        )
        parent = name
    return output


def _add_ribbon_reverse_controls(module: Dict[str, Any]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not settings.get("reverse"):
        return []

    chain = _ordered_proxy_chain(module, exclude_names={"UpVector"})
    if len(chain) < 2:
        return []

    base_scale = _vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0])
    output = []
    parent = None
    for proxy in reversed(chain):
        proxy_name = proxy.get("name")
        if not proxy_name:
            continue
        name = f"{module['module_name']}_{proxy_name}_RibbonRev_CTRL"
        output.append(
            _make_control(
                name=name,
                role="ribbon_reverse",
                shape=_module_shape(settings, "Square"),
                scale=_vec_scale(base_scale, 0.55),
                position=proxy.get("position", [0.0, 0.0, 0.0]),
                rotation=proxy.get("rotation", [0.0, 0.0, 0.0]),
                parent_control=parent,
                driven_proxy=proxy_name,
                parent_proxy=proxy.get("parent"),
            )
        )
        parent = name
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
                    "effect_targets": bool(settings.get("effect_targets", False)),
                    "maintain_offset": bool(settings.get("maintain_offset", True)),
                },
            )
        )
    return output


def _find_proxy_by_name_pattern(proxy_map: Dict[str, Dict[str, Any]], pattern: str) -> Optional[Dict[str, Any]]:
    for name, proxy in proxy_map.items():
        if re.match(pattern, name):
            return proxy
    return None


def _add_hand_digit_driver_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    finger_count = int(settings.get("number_of_fingers") or 0)
    finger_joint_count = int(settings.get("number_of_finger_joints") or 0)
    thumb_joint_count = int(settings.get("number_of_thumb_joints") or 0)
    if finger_count <= 0 and thumb_joint_count <= 0:
        return []

    output = []
    base_scale = _vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0])
    global_parent = f"{module['module_name']}_Global_CTRL" if "Global" in proxy_map else None

    for finger_idx in range(max(finger_count, 0)):
        root_proxy = proxy_map.get(f"Finger{finger_idx}_0")
        if root_proxy is None:
            root_proxy = _find_proxy_by_name_pattern(proxy_map, rf"Finger{finger_idx}_\d+")
        if root_proxy is None:
            continue

        curl_name = f"{module['module_name']}_Finger{finger_idx}_Curl_CTRL"
        output.append(
            _make_control(
                name=curl_name,
                role="hand_finger_curl",
                shape=_module_shape(settings, "Square"),
                scale=_vec_scale(base_scale, 0.7),
                position=root_proxy.get("position", [0.0, 0.0, 0.0]),
                rotation=root_proxy.get("rotation", [0.0, 0.0, 0.0]),
                parent_control=global_parent,
                driven_proxy=root_proxy.get("name"),
                metadata={"finger_index": finger_idx, "joint_count": finger_joint_count},
            )
        )
        parent = curl_name
        for joint_idx in range(max(finger_joint_count, 0)):
            joint_proxy_name = f"Finger{finger_idx}_{joint_idx}"
            joint_proxy = proxy_map.get(joint_proxy_name)
            if not joint_proxy:
                continue
            driver_name = f"{module['module_name']}_{joint_proxy_name}_Driver_CTRL"
            output.append(
                _make_control(
                    name=driver_name,
                    role="hand_finger_driver",
                    shape=_module_shape(settings, "Circle"),
                    scale=_vec_scale(base_scale, 0.55),
                    position=joint_proxy.get("position", [0.0, 0.0, 0.0]),
                    rotation=joint_proxy.get("rotation", [0.0, 0.0, 0.0]),
                    parent_control=parent,
                    driven_proxy=joint_proxy_name,
                    metadata={"finger_index": finger_idx, "joint_index": joint_idx},
                )
            )
            parent = driver_name

    if thumb_joint_count > 0:
        thumb_root = proxy_map.get("Thumb_0")
        if thumb_root:
            curl_name = f"{module['module_name']}_Thumb_Curl_CTRL"
            output.append(
                _make_control(
                    name=curl_name,
                    role="hand_thumb_curl",
                    shape=_module_shape(settings, "Square"),
                    scale=_vec_scale(base_scale, 0.7),
                    position=thumb_root.get("position", [0.0, 0.0, 0.0]),
                    rotation=thumb_root.get("rotation", [0.0, 0.0, 0.0]),
                    parent_control=global_parent,
                    driven_proxy="Thumb_0",
                    metadata={"joint_count": thumb_joint_count},
                )
            )
            parent = curl_name
            for joint_idx in range(thumb_joint_count):
                thumb_proxy_name = f"Thumb_{joint_idx}"
                thumb_proxy = proxy_map.get(thumb_proxy_name)
                if not thumb_proxy:
                    continue
                driver_name = f"{module['module_name']}_{thumb_proxy_name}_Driver_CTRL"
                output.append(
                    _make_control(
                        name=driver_name,
                        role="hand_thumb_driver",
                        shape=_module_shape(settings, "Circle"),
                        scale=_vec_scale(base_scale, 0.55),
                        position=thumb_proxy.get("position", [0.0, 0.0, 0.0]),
                        rotation=thumb_proxy.get("rotation", [0.0, 0.0, 0.0]),
                        parent_control=parent,
                        driven_proxy=thumb_proxy_name,
                        metadata={"joint_index": joint_idx},
                    )
                )
                parent = driver_name

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
                shape=_module_shape(settings, "Square"),
                scale=_vec_scale(_vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0]), 0.8),
                position=proxy_data.get("position", [0.0, 0.0, 0.0]),
                rotation=proxy_data.get("rotation", [0.0, 0.0, 0.0]),
                parent_proxy=proxy_data.get("parent"),
                driven_proxy=proxy_name,
            )
        )
    return output


def _add_lips_segment_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    segment_count = int(settings.get("lip_segments") or 0)
    if segment_count <= 0:
        return []

    mouth = proxy_map.get("Mouth")
    left_corner = _find_proxy_by_name_pattern(proxy_map, r"L_Corner.*")
    right_corner = _find_proxy_by_name_pattern(proxy_map, r"R_Corner.*")
    upper_center = _find_proxy_by_name_pattern(proxy_map, r"M_Up.*")
    lower_center = _find_proxy_by_name_pattern(proxy_map, r"M_Lo.*")
    if not mouth or not left_corner or not right_corner:
        return []

    left_pos = _vec(left_corner.get("position"))
    right_pos = _vec(right_corner.get("position"))
    line_mid = _vec_lerp(left_pos, right_pos, 0.5)
    up_offset = _vec_sub(_vec(upper_center.get("position")), line_mid) if upper_center else [0.0, 0.25, 0.0]
    lo_offset = _vec_sub(_vec(lower_center.get("position")), line_mid) if lower_center else [0.0, -0.25, 0.0]
    mouth_pos = _vec(mouth.get("position"))
    base_scale = _vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0])

    output = []
    upper_proxy_name = str(upper_center.get("name") if upper_center else "Mouth")
    lower_proxy_name = str(lower_center.get("name") if lower_center else "Mouth")
    for idx in range(segment_count):
        alpha = float(idx + 1) / float(segment_count + 1)
        base = _vec_lerp(left_pos, right_pos, alpha)
        output.append(
            _make_control(
                name=f"{module['module_name']}_UpperSegment_{idx}_CTRL",
                role="lip_segment_upper",
                shape=_module_shape(settings, "Circle"),
                scale=_vec_scale(base_scale, 0.7),
                position=_vec_add(base, up_offset),
                rotation=[0.0, 0.0, 0.0],
                driven_proxy=upper_proxy_name,
                parent_proxy=str(mouth.get("name") or "Mouth"),
                metadata={"segment_index": idx},
            )
        )
        output.append(
            _make_control(
                name=f"{module['module_name']}_LowerSegment_{idx}_CTRL",
                role="lip_segment_lower",
                shape=_module_shape(settings, "Circle"),
                scale=_vec_scale(base_scale, 0.7),
                position=_vec_add(base, lo_offset),
                rotation=[0.0, 0.0, 0.0],
                driven_proxy=lower_proxy_name,
                parent_proxy=str(mouth.get("name") or "Mouth"),
                metadata={"segment_index": idx},
            )
        )

    jaw_target = settings.get("jaw_target")
    if jaw_target:
        output.append(
            _make_control(
                name=f"{module['module_name']}_JawFollow_CTRL",
                role="lip_jaw_follow",
                shape=_module_shape(settings, "Square"),
                scale=_vec_scale(base_scale, 0.9),
                position=mouth_pos,
                rotation=[0.0, 0.0, 0.0],
                driven_proxy="Mouth",
                metadata={"jaw_target": jaw_target},
            )
        )
    return output


def _add_follicle_eye_segment_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    segment_count = int(settings.get("lid_segments") or 0)
    if segment_count <= 0:
        return []

    eye_center = proxy_map.get("Eyeball")
    inner = proxy_map.get("In")
    outer = proxy_map.get("Out")
    upper = proxy_map.get("Up")
    lower = proxy_map.get("Lo")
    if not eye_center or not inner or not outer:
        return []

    inner_pos = _vec(inner.get("position"))
    outer_pos = _vec(outer.get("position"))
    line_mid = _vec_lerp(inner_pos, outer_pos, 0.5)
    upper_offset = _vec_sub(_vec(upper.get("position")), line_mid) if upper else [0.0, 0.2, 0.0]
    lower_offset = _vec_sub(_vec(lower.get("position")), line_mid) if lower else [0.0, -0.2, 0.0]
    base_scale = _vec(settings.get("ctrl_scale"), [1.0, 1.0, 1.0])

    output = []
    eye_proxy_name = str(eye_center.get("name") or "Eyeball")
    for idx in range(segment_count):
        alpha = float(idx + 1) / float(segment_count + 1)
        base = _vec_lerp(inner_pos, outer_pos, alpha)
        output.append(
            _make_control(
                name=f"{module['module_name']}_LidUpperSegment_{idx}_CTRL",
                role="lid_segment_upper",
                shape=_module_shape(settings, "Circle"),
                scale=_vec_scale(base_scale, 0.65),
                position=_vec_add(base, upper_offset),
                rotation=[0.0, 0.0, 0.0],
                driven_proxy=eye_proxy_name,
                parent_proxy=eye_proxy_name,
                metadata={"segment_index": idx},
            )
        )
        output.append(
            _make_control(
                name=f"{module['module_name']}_LidLowerSegment_{idx}_CTRL",
                role="lid_segment_lower",
                shape=_module_shape(settings, "Circle"),
                scale=_vec_scale(base_scale, 0.65),
                position=_vec_add(base, lower_offset),
                rotation=[0.0, 0.0, 0.0],
                driven_proxy=eye_proxy_name,
                parent_proxy=eye_proxy_name,
                metadata={"segment_index": idx},
            )
        )

    attachment_target = settings.get("follicle_surface") or settings.get("follicle_mesh")
    if attachment_target:
        output.append(
            _make_control(
                name=f"{module['module_name']}_LidAttach_CTRL",
                role="lid_attach",
                shape=_module_shape(settings, "Square"),
                scale=_vec_scale(base_scale, 0.8),
                position=_vec(eye_center.get("position")),
                rotation=[0.0, 0.0, 0.0],
                driven_proxy="Eyeball",
                metadata={"attachment_target": attachment_target},
            )
        )
    if settings.get("eyeball"):
        eye_pos = _vec(eye_center.get("position"))
        output.append(
            _make_control(
                name=f"{module['module_name']}_EyeballAim_CTRL",
                role="eyeball_aim",
                shape=_module_shape(settings, "Circle"),
                scale=_vec_scale(base_scale, 0.75),
                position=[eye_pos[0], eye_pos[1], eye_pos[2] + 2.0],
                rotation=[0.0, 0.0, 0.0],
                driven_proxy="Eyeball",
            )
        )
    return output


def _add_axis_guide_controls(module: Dict[str, Any], proxy_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    metadata = module.get("metadata", {})
    aim_axis = metadata.get("aim_axis")
    up_axis = metadata.get("up_axis")
    if not aim_axis and not up_axis:
        return []

    anchor = proxy_map.get("Root") or proxy_map.get("Start") or proxy_map.get("Mouth") or proxy_map.get("Eyeball")
    if not anchor and proxy_map:
        anchor = list(proxy_map.values())[0]
    if not anchor:
        return []

    anchor_pos = _vec(anchor.get("position"))
    output = []
    if aim_axis:
        aim_pos = _vec_add(anchor_pos, _vec_scale(_axis_to_vec(aim_axis), 2.0))
        output.append(
            _make_control(
                name=f"{module['module_name']}_AimGuide_CTRL",
                role="axis_guide_aim",
                shape="Square",
                scale=[0.25, 0.25, 0.25],
                position=aim_pos,
                rotation=[0.0, 0.0, 0.0],
                metadata={"axis": aim_axis},
            )
        )
    if up_axis:
        up_pos = _vec_add(anchor_pos, _vec_scale(_axis_to_vec(up_axis), 2.0))
        output.append(
            _make_control(
                name=f"{module['module_name']}_UpGuide_CTRL",
                role="axis_guide_up",
                shape="Square",
                scale=[0.25, 0.25, 0.25],
                position=up_pos,
                rotation=[0.0, 0.0, 0.0],
                metadata={"axis": up_axis},
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
                    shape=_module_shape(settings, "Square"),
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
                    shape=_module_shape(settings, "Square"),
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
    if module_class in {"FK", "FKSegment"}:
        add_many(_add_segment_driver_controls(module, proxy_map))
    if module_class == "FKSegment":
        add_many(_add_fk_ik_rail_controls(module))
    if module_class in {"Limb", "QuadLimb"}:
        pv_ctrl = _infer_limb_pv(module, proxy_map)
        if pv_ctrl:
            add_many([pv_ctrl])
        add_many(_add_limb_deform_controls(module, proxy_map))
        add_many(_add_limb_ik_floor_anchor(module, proxy_map))
        add_many(_add_limb_foot_roll(module, proxy_map))
    if module_class == "QuadLimb":
        add_many(_add_quad_limb_auto_roll_controls(module, proxy_map))
    if module_class == "RibbonBindIK":
        add_many(_add_ribbon_bind_controls(module, proxy_map))
        add_many(_add_ribbon_meta_controls(module, proxy_map))
        add_many(_add_ribbon_reverse_controls(module))
    if module_class == "PointTarget":
        add_many(_add_point_target_controls(module, existing_controls))
    if module_class == "Hand":
        add_many(_add_hand_digit_driver_controls(module, proxy_map))
        add_many(_add_hand_meta_controls(module, proxy_map))
    if module_class == "Lips":
        add_many(_add_lips_segment_controls(module, proxy_map))
    if module_class == "FollicleEye":
        add_many(_add_follicle_eye_segment_controls(module, proxy_map))
    if module_class in {"Lips", "FollicleEye"}:
        add_many(_add_face_settings_controls(module, proxy_map))
    add_many(_add_axis_guide_controls(module, proxy_map))
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


def _control_depth_map(module: Dict[str, Any]) -> Dict[str, int]:
    controls = module.get("controls", [])
    parent_lookup = {control.get("name"): control.get("parent_control") for control in controls if control.get("name")}
    depth_map: Dict[str, int] = {}

    def resolve_depth(name: str) -> int:
        cached = depth_map.get(name)
        if cached is not None:
            return cached
        parent = parent_lookup.get(name)
        if not parent or parent == name:
            depth_map[name] = 0
            return 0
        depth = resolve_depth(parent) + 1
        depth_map[name] = depth
        return depth

    for control_name in parent_lookup.keys():
        resolve_depth(control_name)
    return depth_map


def _control_to_proxy_bindings(module: Dict[str, Any]) -> List[Dict[str, Any]]:
    module_name = module.get("module_name", "")
    controls = module.get("controls", [])
    depth_map = _control_depth_map(module)
    ordered_controls = sorted(controls, key=lambda control: (depth_map.get(control.get("name", ""), 0), control.get("name", "")))
    bindings: List[Dict[str, Any]] = []
    for control in ordered_controls:
        control_name = control.get("name")
        driven_proxy = control.get("driven_proxy")
        if not control_name or not driven_proxy:
            continue
        bindings.append(
            {
                "source_control": control_name,
                "source_role": control.get("role"),
                "target_item_type": "Bone",
                "target_item_name": f"{module_name}_{driven_proxy}_Proxy",
                "weight": 1.0,
                "source_space": "GlobalSpace",
                "target_space": "GlobalSpace",
                "constraint_type": "parent",
                "tag": "control_proxy_bind",
            }
        )
    return bindings


def _point_target_behavior_bindings(module: Dict[str, Any], default_target_bone_name: Optional[str]) -> List[Dict[str, Any]]:
    controls = module.get("controls", [])
    settings = module.get("module_settings", {})
    effect_targets = bool(settings.get("effect_targets", False))
    constrain_type = str(settings.get("constrain_type") or "point").lower()
    maintain_offset = bool(settings.get("maintain_offset", True))
    influences = list(settings.get("targets_influence", []) or [])

    root_control = next((control for control in controls if control.get("role") == "point_target"), None)
    source_root_name = root_control.get("name") if root_control else None
    ref_controls = [control for control in controls if control.get("role") == "point_target_reference"]
    output: List[Dict[str, Any]] = []
    for index, control in enumerate(ref_controls):
        metadata = control.get("metadata") or {}
        target_node = metadata.get("target_node")
        influence_value = metadata.get("influence")
        if influence_value is None and index < len(influences):
            influence_value = influences[index]
        try:
            weight = float(influence_value)
        except (TypeError, ValueError):
            weight = 1.0
        if weight < 0.0:
            weight = 0.0

        if effect_targets:
            source_control = source_root_name
            target_item_name = str(target_node or "")
        else:
            source_control = control.get("name")
            target_item_name = str(default_target_bone_name or "")
        if not source_control or not target_item_name:
            continue

        output.append(
            {
                "source_control": source_control,
                "target_item_type": "Bone",
                "target_item_name": target_item_name,
                "weight": weight,
                "source_space": "GlobalSpace",
                "target_space": "GlobalSpace",
                "constraint_type": constrain_type,
                "maintain_offset": maintain_offset,
                "tag": "point_target_constraint",
            }
        )
    return output


def _limb_ik_fk_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    controls = module.get("controls", [])
    ik_control = next((control for control in controls if control.get("role") == "ik_effector"), None)
    if not ik_control:
        return bindings

    switch_pin = f"{ik_control.get('name')}.IK_FK_Switch"
    output: List[Dict[str, Any]] = []
    has_ik = bool(settings.get("ik_ctrl_to_floor")) or bool(settings.get("foot"))
    for binding in bindings:
        role = str(binding.get("source_role", ""))
        if role == "limb_fk":
            data = dict(binding)
            data["weight_pin_path"] = switch_pin
            data["visibility_pin_path"] = switch_pin
            data["visibility_channel"] = "Visibility"
            data["math_mode"] = "ik_fk_fk_branch"
            output.append(data)
            continue

        if role in {"ik_effector", "pole_vector", "ik_floor_anchor", "foot_roll"} or (role.startswith("quad_") and has_ik):
            data = dict(binding)
            data["weight_pin_path"] = switch_pin
            data["weight_invert"] = True
            data["visibility_pin_path"] = switch_pin
            data["visibility_invert"] = True
            data["visibility_channel"] = "Visibility"
            data["math_mode"] = "ik_fk_ik_branch"
            output.append(data)
            continue

        output.append(binding)
    return output


def _limb_foot_roll_operator_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    if not bool(settings.get("foot", False)):
        return bindings

    foot_profile = {
        "Toe": {"operator": "inverse_toe_roll", "input_channel": "rotateX", "target_axis": "X", "factor": -1.0},
        "Ball": {"operator": "ball_roll_compensation", "input_channel": "rotateX", "target_axis": "X", "factor": 1.0},
        "InBank": {"operator": "inbank_compensation", "input_channel": "rotateZ", "target_axis": "Z", "factor": 1.0},
        "OutBank": {"operator": "outbank_compensation", "input_channel": "rotateZ", "target_axis": "Z", "factor": 1.0},
    }
    output: List[Dict[str, Any]] = []
    for binding in bindings:
        if str(binding.get("source_role", "")) != "foot_roll":
            output.append(binding)
            continue

        source_control = str(binding.get("source_control", ""))
        data = dict(binding)
        data["target_channel"] = "rotation"
        for proxy_name, profile in foot_profile.items():
            if f"_{proxy_name}_Foot_CTRL" not in source_control:
                continue
            data["foot_roll_operator"] = profile["operator"]
            data["foot_roll_input_channel"] = profile["input_channel"]
            data["foot_roll_target_axis"] = profile["target_axis"]
            data["foot_roll_factor"] = float(profile["factor"])
            data["math_mode"] = f"limb_foot_{profile['operator']}"
            break
        output.append(data)
    return output


def _ribbon_bind_operator_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if module.get("module_class") != "RibbonBindIK":
        return bindings
    output: List[Dict[str, Any]] = []
    for binding in bindings:
        role = str(binding.get("source_role", ""))
        if role != "ribbon_bind_driver":
            output.append(binding)
            continue
        metadata = dict(binding.get("source_metadata") or {})
        bind_index = int(metadata.get("bind_index", 0))
        bind_count = max(int(metadata.get("count", 1)), 1)
        alpha = 0.0 if bind_count <= 1 else float(bind_index) / float(bind_count - 1)
        data = dict(binding)
        data["ribbon_bind_operator"] = "distribution_lerp"
        data["ribbon_bind_alpha"] = alpha
        data["ribbon_bind_index"] = bind_index
        data["ribbon_bind_count"] = bind_count
        data["math_mode"] = "ribbon_bind_distribution_operator_network"
        output.append(data)
    return output


def _point_target_channel_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    constrain_type = str(settings.get("constrain_type") or "parent").lower()
    if constrain_type in {"parent", ""}:
        return bindings

    channel_map = {
        "point": ["translation"],
        "orient": ["rotation"],
        "scale": ["scale"],
        "aim": ["rotation"],
    }
    channels = channel_map.get(constrain_type, ["translation", "rotation", "scale"])
    output: List[Dict[str, Any]] = []
    for binding in bindings:
        if str(binding.get("tag", "")) != "point_target_constraint":
            output.append(binding)
            continue
        for channel in channels:
            data = dict(binding)
            data["target_channel"] = channel
            data["math_mode"] = f"point_target_{constrain_type}_{channel}"
            output.append(data)
    return output


def _point_target_operator_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    metadata = module.get("metadata", {}) or {}
    constrain_type = str(settings.get("constrain_type") or "point").lower()
    control_lookup = {control.get("name"): control for control in module.get("controls", []) if control.get("name")}
    target_lookup = {}
    for control in module.get("controls", []):
        if control.get("role") != "point_target_reference":
            continue
        target_node = str((control.get("metadata") or {}).get("target_node") or "")
        if target_node:
            target_lookup[target_node] = control

    aim_axis_vector = _axis_to_vec(settings.get("aim_axis") or metadata.get("aim_axis"))
    up_axis_vector = _axis_to_vec(settings.get("up_axis") or metadata.get("up_axis"))
    aim_axis_sign = next((component for component in aim_axis_vector if abs(component) > 1e-6), 1.0)
    output: List[Dict[str, Any]] = []
    for binding in bindings:
        if str(binding.get("tag", "")) != "point_target_constraint":
            output.append(binding)
            continue

        data = dict(binding)
        source_control = control_lookup.get(str(binding.get("source_control", "")), {})
        reference_control = target_lookup.get(str(binding.get("target_item_name", "")), {})
        source_position = _vec(source_control.get("position"), [0.0, 0.0, 0.0])
        reference_position = _vec(reference_control.get("position"), [0.0, 0.0, 0.0])
        data["offset_vector"] = _vec_sub(reference_position, source_position)
        if bool(binding.get("maintain_offset", False)):
            data["use_offset_buffer"] = True
            data["math_mode"] = f"{binding.get('math_mode', 'point_target')}_maintain_offset"
        if constrain_type == "aim":
            data["use_aim_axis_math"] = True
            data["aim_axis_vector"] = aim_axis_vector
            data["up_axis_vector"] = up_axis_vector
            data["aim_axis_sign"] = float(aim_axis_sign)
            data["math_mode"] = f"{binding.get('math_mode', 'point_target_aim')}_axis_tighten"
        output.append(data)
    return output


def _hand_operator_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    settings = module.get("module_settings", {})
    metadata = module.get("metadata", {}) or {}
    controls = module.get("controls", [])
    control_lookup = {control.get("name"): control for control in controls if control.get("name")}
    global_control = next((control.get("name") for control in controls if control.get("role") == "hand_global"), None)
    if not global_control:
        return bindings

    digit_keys = []
    for control in controls:
        driven_proxy = str(control.get("driven_proxy") or "")
        finger_match = re.match(r"Finger(\d+)_", driven_proxy)
        if finger_match:
            key = f"Finger{finger_match.group(1)}"
            if key not in digit_keys:
                digit_keys.append(key)
            continue
        if driven_proxy.startswith("Thumb_") and "Thumb" not in digit_keys:
            digit_keys.append("Thumb")
    digit_keys = sorted([key for key in digit_keys if key.startswith("Finger")], key=lambda item: int(item[6:])) + (
        ["Thumb"] if "Thumb" in digit_keys else []
    )
    if not digit_keys:
        return bindings

    ratio = 1.0 / (len(digit_keys) * 0.5)
    rate_map: Dict[str, float] = {}
    rate_value = 0.0
    for key in digit_keys:
        rate_map[key] = rate_value
        rate_value -= ratio

    aim_axis = settings.get("aim_axis") or metadata.get("aim_axis")
    aim_axis_vector = _axis_to_vec(aim_axis)
    aim_direction = next((component for component in aim_axis_vector if abs(component) > 1e-6), 1.0)
    output: List[Dict[str, Any]] = []
    for binding in bindings:
        role = str(binding.get("source_role", ""))
        if role not in {"hand_updn_offset", "hand_twist_offset", "hand_splay_offset"}:
            output.append(binding)
            continue

        source_control = control_lookup.get(str(binding.get("source_control", "")), {})
        driven_proxy = str(source_control.get("driven_proxy") or "")
        finger_match = re.match(r"Finger(\d+)_", driven_proxy)
        if finger_match:
            digit_key = f"Finger{finger_match.group(1)}"
        elif driven_proxy.startswith("Thumb_"):
            digit_key = "Thumb"
        else:
            generated_from = str((source_control.get("metadata") or {}).get("generated_from") or "")
            gen_match = re.search(r"Finger(\d+)_", generated_from)
            if gen_match:
                digit_key = f"Finger{gen_match.group(1)}"
            elif "Thumb" in generated_from:
                digit_key = "Thumb"
            else:
                output.append(binding)
                continue

        rate = float(rate_map.get(digit_key, 0.0))
        data = dict(binding)
        data["hand_global_control"] = global_control
        data["hand_rate"] = rate
        data["hand_aim_direction"] = float(aim_direction)
        if role == "hand_updn_offset":
            data["hand_operator"] = "updn"
            data["hand_input_channel"] = "rotateZ"
            data["target_channel"] = "rotation"
            data["hand_target_axis"] = "Y"
            data["hand_factor"] = float(1.0 * aim_direction)
        elif role == "hand_twist_offset":
            data["hand_operator"] = "twist"
            data["hand_input_channel"] = "rotateX"
            data["target_channel"] = "rotation"
            data["hand_target_axis"] = "Y"
            data["hand_factor"] = float((1.0 + rate) * -1.0)
        else:
            data["hand_operator"] = "splay"
            data["hand_input_channel"] = "translateX"
            data["target_channel"] = "translation"
            data["hand_target_axis"] = "Z"
            data["hand_factor"] = float(((1.0 + rate) * -1.5) * aim_direction)
        data["math_mode"] = f"hand_{data['hand_operator']}_multiply_divide"
        output.append(data)
    return output


def _ribbon_bind_operator_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if module.get("module_class") != "RibbonBindIK":
        return bindings

    controls = module.get("controls", []) or []
    bind_controls = [control for control in controls if control.get("role") == "ribbon_bind_driver" and control.get("name")]
    if not bind_controls:
        return bindings

    bind_controls.sort(
        key=lambda control: (
            int((control.get("metadata") or {}).get("bind_index", 0)),
            str(control.get("name", "")),
        )
    )
    start_control = str(bind_controls[0].get("name"))
    end_control = str(bind_controls[-1].get("name"))
    control_lookup = {str(control.get("name")): control for control in bind_controls}

    output: List[Dict[str, Any]] = []
    for binding in bindings:
        if str(binding.get("source_role", "")) != "ribbon_bind_driver":
            output.append(binding)
            continue

        data = dict(binding)
        source_name = str(binding.get("source_control", ""))
        source_control = control_lookup.get(source_name, {})
        metadata = source_control.get("metadata") or {}
        bind_index = int(metadata.get("bind_index", 0))
        bind_count = int(metadata.get("count", len(bind_controls)))
        denominator = max(bind_count - 1, 1)
        alpha = float(bind_index) / float(denominator)
        data["ribbon_distribution_operator"] = True
        data["ribbon_alpha"] = alpha
        data["ribbon_start_control"] = start_control
        data["ribbon_end_control"] = end_control
        data["distribution_operator"] = True
        data["distribution_alpha"] = alpha
        data["distribution_start_control"] = start_control
        data["distribution_end_control"] = end_control
        data["distribution_tag"] = "Ribbon"
        data["target_channel"] = "translation"
        data["math_mode"] = "ribbon_bind_distribution_operator"
        output.append(data)
    return output


def _fk_distribution_operator_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    module_class = str(module.get("module_class") or "")
    if module_class not in {"FK", "FKSegment"}:
        return bindings

    controls = module.get("controls", []) or []
    settings = module.get("module_settings", {}) or {}
    by_name = {str(control.get("name")): control for control in controls if control.get("name")}
    start_control = next((control.get("name") for control in controls if control.get("driven_proxy") == "Start"), None)
    end_control = next((control.get("name") for control in controls if control.get("driven_proxy") == "End"), None)
    if not start_control:
        start_control = next((control.get("name") for control in controls if control.get("role") == "segment_driver"), None)
    if not end_control:
        segment_controls = [control for control in controls if control.get("role") == "segment_driver" and control.get("name")]
        segment_controls.sort(key=lambda control: int((control.get("metadata") or {}).get("segment_index", 0)))
        if segment_controls:
            end_control = segment_controls[-1].get("name")

    segment_count = int(settings.get("segments") or 0)
    rail_controls = [control for control in controls if control.get("role") == "ik_rail_driver" and control.get("name")]
    rail_controls.sort(key=lambda control: int((control.get("metadata") or {}).get("rail_index", 0)))
    rail_count = len(rail_controls)
    rail_start = str(rail_controls[0].get("name")) if rail_controls else None
    rail_end = str(rail_controls[-1].get("name")) if rail_controls else None

    output: List[Dict[str, Any]] = []
    for binding in bindings:
        role = str(binding.get("source_role", ""))
        if role not in {"segment_driver", "ik_rail_driver"}:
            output.append(binding)
            continue
        data = dict(binding)
        source_name = str(binding.get("source_control", ""))
        source_control = by_name.get(source_name, {})
        source_meta = source_control.get("metadata") or {}

        if role == "segment_driver" and start_control and end_control:
            segment_index = int(source_meta.get("segment_index", 0))
            denominator = max(segment_count - 1, 1)
            alpha = float(segment_index) / float(denominator)
            data["distribution_operator"] = True
            data["distribution_alpha"] = alpha
            data["distribution_start_control"] = str(start_control)
            data["distribution_end_control"] = str(end_control)
            data["distribution_tag"] = "FKSegment"
            data["target_channel"] = "translation"
            data["math_mode"] = "fk_segment_distribution_operator"
        elif role == "ik_rail_driver" and rail_start and rail_end:
            rail_index = int(source_meta.get("rail_index", 0))
            denominator = max(rail_count - 1, 1)
            alpha = float(rail_index) / float(denominator)
            data["distribution_operator"] = True
            data["distribution_alpha"] = alpha
            data["distribution_start_control"] = str(rail_start)
            data["distribution_end_control"] = str(rail_end)
            data["distribution_tag"] = "IKRail"
            data["target_channel"] = "translation"
            data["math_mode"] = "fksegment_ik_rail_distribution_operator"
        output.append(data)
    return output


def _lips_operator_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if module.get("module_class") != "Lips":
        return bindings
    controls = module.get("controls", []) or []
    settings = module.get("module_settings", {}) or {}
    by_name = {str(control.get("name")): control for control in controls if control.get("name")}
    corners = [control for control in controls if control.get("role") == "lip_corner" and control.get("name")]
    if not corners:
        corners = [
            control
            for control in controls
            if str(control.get("driven_proxy") or "").lower().endswith("cornerlip") and control.get("name")
        ]
    left_corner = next((control.get("name") for control in corners if "_L_" in str(control.get("name"))), None)
    right_corner = next((control.get("name") for control in corners if "_R_" in str(control.get("name"))), None)
    if not left_corner and corners:
        left_corner = corners[0].get("name")
    if not right_corner and len(corners) > 1:
        right_corner = corners[-1].get("name")
    upper_segments = [control for control in controls if control.get("role") == "lip_segment_upper" and control.get("name")]
    lower_segments = [control for control in controls if control.get("role") == "lip_segment_lower" and control.get("name")]
    upper_segments.sort(key=lambda control: int((control.get("metadata") or {}).get("segment_index", 0)))
    lower_segments.sort(key=lambda control: int((control.get("metadata") or {}).get("segment_index", 0)))
    role_endpoints = {
        "lip_segment_upper": {
            "start": str(upper_segments[0].get("name")) if upper_segments else None,
            "end": str(upper_segments[-1].get("name")) if upper_segments else None,
        },
        "lip_segment_lower": {
            "start": str(lower_segments[0].get("name")) if lower_segments else None,
            "end": str(lower_segments[-1].get("name")) if lower_segments else None,
        },
    }
    segment_count = int(settings.get("lip_segments") or 0)

    output: List[Dict[str, Any]] = []
    for binding in bindings:
        role = str(binding.get("source_role", ""))
        if role not in {"lip_segment_upper", "lip_segment_lower"}:
            output.append(binding)
            continue
        endpoints = role_endpoints.get(role, {})
        start_control = endpoints.get("start") or left_corner
        end_control = endpoints.get("end") or right_corner
        if not start_control or not end_control:
            output.append(binding)
            continue
        data = dict(binding)
        source_control = by_name.get(str(binding.get("source_control", "")), {})
        source_meta = source_control.get("metadata") or {}
        segment_index = int(source_meta.get("segment_index", 0))
        alpha = float(segment_index + 1) / float(max(segment_count + 1, 1))
        data["distribution_operator"] = True
        data["distribution_alpha"] = alpha
        data["distribution_start_control"] = str(start_control)
        data["distribution_end_control"] = str(end_control)
        data["distribution_tag"] = "LipsUpper" if role.endswith("upper") else "LipsLower"
        data["target_channel"] = "translation"
        data["math_mode"] = f"lips_{role}_distribution_operator"
        output.append(data)
    return output


def _follicle_eye_operator_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if module.get("module_class") != "FollicleEye":
        return bindings
    controls = module.get("controls", []) or []
    settings = module.get("module_settings", {}) or {}
    by_name = {str(control.get("name")): control for control in controls if control.get("name")}
    corners = [control for control in controls if control.get("role") == "lid_corner" and control.get("name")]
    if not corners:
        corners = [
            control
            for control in controls
            if str(control.get("driven_proxy") or "") in {"In", "Out"} and control.get("name")
        ]
    inner_corner = next((control.get("name") for control in corners if "_In_" in str(control.get("name"))), None)
    outer_corner = next((control.get("name") for control in corners if "_Out_" in str(control.get("name"))), None)
    if not inner_corner and corners:
        inner_corner = corners[0].get("name")
    if not outer_corner and len(corners) > 1:
        outer_corner = corners[-1].get("name")
    upper_segments = [control for control in controls if control.get("role") == "lid_segment_upper" and control.get("name")]
    lower_segments = [control for control in controls if control.get("role") == "lid_segment_lower" and control.get("name")]
    upper_segments.sort(key=lambda control: int((control.get("metadata") or {}).get("segment_index", 0)))
    lower_segments.sort(key=lambda control: int((control.get("metadata") or {}).get("segment_index", 0)))
    role_endpoints = {
        "lid_segment_upper": {
            "start": str(upper_segments[0].get("name")) if upper_segments else None,
            "end": str(upper_segments[-1].get("name")) if upper_segments else None,
        },
        "lid_segment_lower": {
            "start": str(lower_segments[0].get("name")) if lower_segments else None,
            "end": str(lower_segments[-1].get("name")) if lower_segments else None,
        },
    }
    segment_count = int(settings.get("lid_segments") or 0)

    output: List[Dict[str, Any]] = []
    for binding in bindings:
        role = str(binding.get("source_role", ""))
        if role not in {"lid_segment_upper", "lid_segment_lower"}:
            output.append(binding)
            continue
        endpoints = role_endpoints.get(role, {})
        start_control = endpoints.get("start") or inner_corner
        end_control = endpoints.get("end") or outer_corner
        if not start_control or not end_control:
            output.append(binding)
            continue
        data = dict(binding)
        source_control = by_name.get(str(binding.get("source_control", "")), {})
        source_meta = source_control.get("metadata") or {}
        segment_index = int(source_meta.get("segment_index", 0))
        alpha = float(segment_index + 1) / float(max(segment_count + 1, 1))
        data["distribution_operator"] = True
        data["distribution_alpha"] = alpha
        data["distribution_start_control"] = str(start_control)
        data["distribution_end_control"] = str(end_control)
        data["distribution_tag"] = "LidUpper" if role.endswith("upper") else "LidLower"
        data["target_channel"] = "translation"
        data["math_mode"] = f"follicle_eye_{role}_distribution_operator"
        output.append(data)
    return output


def _ensure_distribution_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    module_class = str(module.get("module_class") or "")
    controls = module.get("controls", []) or []
    if module_class == "FK":
        segment_controls = [control for control in controls if control.get("role") == "segment_driver" and control.get("name")]
        segment_controls.sort(key=lambda control: int((control.get("metadata") or {}).get("segment_index", 0)))
        if segment_controls:
            start_control = str(segment_controls[0].get("name"))
            end_control = str(segment_controls[-1].get("name"))
            segment_count = len(segment_controls)
            for idx, control in enumerate(segment_controls):
                alpha = float(idx) / float(max(segment_count - 1, 1))
                bindings.append(
                    {
                        "source_control": str(control.get("name")),
                        "source_role": "segment_driver",
                        "target_item_type": "Control",
                        "target_item_name": str(control.get("name")),
                        "weight": 1.0,
                        "source_space": "GlobalSpace",
                        "target_space": "GlobalSpace",
                        "distribution_operator": True,
                        "distribution_alpha": alpha,
                        "distribution_start_control": start_control,
                        "distribution_end_control": end_control,
                        "distribution_tag": "FKSegment",
                        "target_channel": "translation",
                        "math_mode": "fk_segment_distribution_operator",
                        "tag": "distribution_operator",
                    }
                )
        return bindings

    if module_class == "Lips":
        upper = [control for control in controls if control.get("role") == "lip_segment_upper" and control.get("name")]
        lower = [control for control in controls if control.get("role") == "lip_segment_lower" and control.get("name")]
        corners = [control for control in controls if control.get("role") == "lip_corner" and control.get("name")]
        if corners:
            left_corner = str(corners[0].get("name"))
            right_corner = str(corners[-1].get("name"))
            for group, tag in ((upper, "LipsUpper"), (lower, "LipsLower")):
                group.sort(key=lambda control: int((control.get("metadata") or {}).get("segment_index", 0)))
                segment_count = len(group)
                for idx, control in enumerate(group):
                    alpha = float(idx + 1) / float(max(segment_count + 1, 1))
                    bindings.append(
                        {
                            "source_control": str(control.get("name")),
                            "source_role": str(control.get("role")),
                            "target_item_type": "Control",
                            "target_item_name": str(control.get("name")),
                            "weight": 1.0,
                            "source_space": "GlobalSpace",
                            "target_space": "GlobalSpace",
                            "distribution_operator": True,
                            "distribution_alpha": alpha,
                            "distribution_start_control": left_corner,
                            "distribution_end_control": right_corner,
                            "distribution_tag": tag,
                            "target_channel": "translation",
                            "math_mode": f"lips_{str(control.get('role'))}_distribution_operator",
                            "tag": "distribution_operator",
                        }
                    )
        return bindings

    if module_class == "FollicleEye":
        upper = [control for control in controls if control.get("role") == "lid_segment_upper" and control.get("name")]
        lower = [control for control in controls if control.get("role") == "lid_segment_lower" and control.get("name")]
        corners = [control for control in controls if control.get("role") == "lid_corner" and control.get("name")]
        if corners:
            inner_corner = str(corners[0].get("name"))
            outer_corner = str(corners[-1].get("name"))
            for group, tag in ((upper, "LidUpper"), (lower, "LidLower")):
                group.sort(key=lambda control: int((control.get("metadata") or {}).get("segment_index", 0)))
                segment_count = len(group)
                for idx, control in enumerate(group):
                    alpha = float(idx + 1) / float(max(segment_count + 1, 1))
                    bindings.append(
                        {
                            "source_control": str(control.get("name")),
                            "source_role": str(control.get("role")),
                            "target_item_type": "Control",
                            "target_item_name": str(control.get("name")),
                            "weight": 1.0,
                            "source_space": "GlobalSpace",
                            "target_space": "GlobalSpace",
                            "distribution_operator": True,
                            "distribution_alpha": alpha,
                            "distribution_start_control": inner_corner,
                            "distribution_end_control": outer_corner,
                            "distribution_tag": tag,
                            "target_channel": "translation",
                            "math_mode": f"follicle_eye_{str(control.get('role'))}_distribution_operator",
                            "tag": "distribution_operator",
                        }
                    )
        return bindings

    return bindings


def _limb_foot_roll_operator_nodes(
    *,
    stage_name: str,
    graph_module_name: str,
    stage_tag: str,
    index: int,
    binding: Dict[str, Any],
    base_x: float,
    stage_y: float,
    set_node: str,
    set_defaults: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if stage_name != "forward":
        return {"nodes": [], "links": []}
    if not binding.get("foot_roll_operator"):
        return {"nodes": [], "links": []}

    operator = str(binding.get("foot_roll_operator"))
    source_control = str(binding.get("source_control", ""))
    input_channel = str(binding.get("foot_roll_input_channel") or "rotateX")
    target_axis = str(binding.get("foot_roll_target_axis") or "X").upper()
    factor = float(binding.get("foot_roll_factor", 1.0))

    foot_get = f"{graph_module_name}_{stage_tag}_Foot_{index}_{operator}_Get"
    foot_mul = f"{graph_module_name}_{stage_tag}_Foot_{index}_{operator}_Mul"
    foot_add = f"{graph_module_name}_{stage_tag}_Foot_{index}_{operator}_Add"
    foot_neg = f"{graph_module_name}_{stage_tag}_Foot_{index}_{operator}_Neg"
    nodes = [
        {
            "name": foot_get,
            "struct_path": "/Script/ControlRig.RigUnit_GetControlFloat",
            "method_name": "Execute",
            "position": [base_x + 110.0, stage_y + 80.0],
        },
        {
            "name": foot_mul,
            "struct_path": "/Script/RigVM.RigVMFunction_MathDoubleMul",
            "method_name": "Execute",
            "position": [base_x + 270.0, stage_y + 80.0],
        },
        {
            "name": foot_add,
            "struct_path": "/Script/RigVM.RigVMFunction_MathDoubleAdd",
            "method_name": "Execute",
            "position": [base_x + 430.0, stage_y + 80.0],
        },
        {
            "name": foot_neg,
            "struct_path": "/Script/RigVM.RigVMFunction_MathDoubleNegate",
            "method_name": "Execute",
            "position": [base_x + 590.0, stage_y + 80.0],
        },
    ]

    _add_pin_default(
        set_defaults,
        pin_path=f"{foot_get}.Control",
        pin_path_candidates=[f"{foot_get}.ControlFloat", f"{foot_get}.Name"],
        value=source_control,
    )
    _add_pin_default(
        set_defaults,
        pin_path=f"{foot_get}.Name",
        pin_path_candidates=[f"{foot_get}.Channel", f"{foot_get}.FloatName"],
        value=input_channel,
    )
    _add_pin_default(set_defaults, pin_path=f"{foot_mul}.B", value=str(factor))
    _add_pin_default(set_defaults, pin_path=f"{foot_add}.A", value="1.0")
    _add_pin_default(set_defaults, pin_path=f"{foot_neg}.Value", value="0.0")

    axis_pin = "X"
    if target_axis in {"Y", "Z"}:
        axis_pin = target_axis
    _add_pin_default(set_defaults, pin_path=f"{set_node}.Value.{axis_pin}", value="0.0")

    links = [
        {"source": f"{foot_get}.Float", "target": f"{foot_mul}.A", "stage": stage_name},
        {"source": f"{foot_mul}.Result", "target": f"{foot_add}.B", "stage": stage_name},
        {"source": f"{foot_add}.Result", "target": f"{foot_neg}.Value", "stage": stage_name},
        {"source": f"{foot_neg}.Result", "target": f"{set_node}.Value.{axis_pin}", "stage": stage_name},
    ]
    return {"nodes": nodes, "links": links}


def _limb_visibility_operator_nodes(
    *,
    stage_name: str,
    graph_module_name: str,
    stage_tag: str,
    index: int,
    binding: Dict[str, Any],
    base_x: float,
    stage_y: float,
    set_node: str,
    set_defaults: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if stage_name != "forward":
        return {"nodes": [], "links": []}
    visibility_pin_path = str(binding.get("visibility_pin_path") or "")
    if not visibility_pin_path:
        return {"nodes": [], "links": []}

    channel = str(binding.get("visibility_channel") or "Visibility")
    invert = bool(binding.get("visibility_invert", False))
    vis_get = f"{graph_module_name}_{stage_tag}_Vis_{index}"
    vis_neg = f"{graph_module_name}_{stage_tag}_VisOneMinus_{index}"
    nodes = [
        {
            "name": vis_get,
            "struct_path": "/Script/ControlRig.RigUnit_GetControlFloat",
            "method_name": "Execute",
            "position": [base_x + 110.0, stage_y - 220.0],
        }
    ]
    _add_pin_default(
        set_defaults,
        pin_path=f"{vis_get}.Control",
        pin_path_candidates=[f"{vis_get}.ControlFloat", f"{vis_get}.Name"],
        value=str(binding.get("source_control", "")),
    )
    _add_pin_default(
        set_defaults,
        pin_path=f"{vis_get}.Name",
        pin_path_candidates=[f"{vis_get}.Channel", f"{vis_get}.FloatName"],
        value=channel,
    )

    links: List[Dict[str, Any]] = []
    if invert:
        nodes.append(
            {
                "name": vis_neg,
                "struct_path": "/Script/RigVM.RigVMFunction_MathDoubleSub",
                "method_name": "Execute",
                "position": [base_x + 290.0, stage_y - 220.0],
            }
        )
        _add_pin_default(set_defaults, pin_path=f"{vis_neg}.A", value="1.0")
        links.append({"source": f"{vis_get}.Float", "target": f"{vis_neg}.B", "stage": stage_name})
        links.append({"source": f"{vis_neg}.Result", "target": f"{set_node}.Weight", "stage": stage_name})
    else:
        links.append({"source": f"{vis_get}.Float", "target": f"{set_node}.Weight", "stage": stage_name})

    return {"nodes": nodes, "links": links}


def _ribbon_bind_operator_nodes(
    *,
    stage_name: str,
    graph_module_name: str,
    stage_tag: str,
    index: int,
    binding: Dict[str, Any],
    base_x: float,
    stage_y: float,
    set_node: str,
    set_defaults: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if stage_name != "forward":
        return {"nodes": [], "links": []}
    if not bool(binding.get("distribution_operator") or binding.get("ribbon_distribution_operator")):
        return {"nodes": [], "links": []}

    alpha = float(binding.get("distribution_alpha", binding.get("ribbon_alpha", 0.0)))
    start_control = str(binding.get("distribution_start_control") or binding.get("ribbon_start_control") or "")
    end_control = str(binding.get("distribution_end_control") or binding.get("ribbon_end_control") or "")
    tag = re.sub(r"[^A-Za-z0-9_]", "", str(binding.get("distribution_tag") or "Ribbon")) or "Ribbon"
    if not start_control or not end_control:
        return {"nodes": [], "links": []}

    start_get = f"{graph_module_name}_{stage_tag}_{tag}Start_{index}"
    end_get = f"{graph_module_name}_{stage_tag}_{tag}End_{index}"
    delta = f"{graph_module_name}_{stage_tag}_{tag}Delta_{index}"
    alpha_mul = f"{graph_module_name}_{stage_tag}_{tag}AlphaMul_{index}"
    result_add = f"{graph_module_name}_{stage_tag}_{tag}Result_{index}"
    nodes = [
        {
            "name": start_get,
            "struct_path": "/Script/ControlRig.RigUnit_GetControlTransform",
            "method_name": "Execute",
            "position": [base_x + 110.0, stage_y + 240.0],
        },
        {
            "name": end_get,
            "struct_path": "/Script/ControlRig.RigUnit_GetControlTransform",
            "method_name": "Execute",
            "position": [base_x + 110.0, stage_y + 320.0],
        },
        {
            "name": delta,
            "struct_path": "/Script/RigVM.RigVMFunction_MathVectorSub",
            "method_name": "Execute",
            "position": [base_x + 300.0, stage_y + 280.0],
        },
        {
            "name": alpha_mul,
            "struct_path": "/Script/RigVM.RigVMFunction_MathVectorMul",
            "method_name": "Execute",
            "position": [base_x + 490.0, stage_y + 280.0],
        },
        {
            "name": result_add,
            "struct_path": "/Script/RigVM.RigVMFunction_MathVectorAdd",
            "method_name": "Execute",
            "position": [base_x + 680.0, stage_y + 280.0],
        },
    ]

    _add_pin_default(
        set_defaults,
        pin_path=f"{start_get}.Control",
        pin_path_candidates=[f"{start_get}.ControlFloat", f"{start_get}.Name"],
        value=start_control,
    )
    _add_pin_default(set_defaults, pin_path=f"{start_get}.Space", value="GlobalSpace")
    _add_pin_default(
        set_defaults,
        pin_path=f"{end_get}.Control",
        pin_path_candidates=[f"{end_get}.ControlFloat", f"{end_get}.Name"],
        value=end_control,
    )
    _add_pin_default(set_defaults, pin_path=f"{end_get}.Space", value="GlobalSpace")
    _add_pin_default(set_defaults, pin_path=f"{alpha_mul}.B", value=str(alpha))

    links = [
        {"source": f"{end_get}.Transform.Translation", "target": f"{delta}.A", "stage": stage_name},
        {"source": f"{start_get}.Transform.Translation", "target": f"{delta}.B", "stage": stage_name},
        {"source": f"{delta}.Result", "target": f"{alpha_mul}.A", "stage": stage_name},
        {"source": f"{alpha_mul}.Result", "target": f"{result_add}.A", "stage": stage_name},
        {"source": f"{start_get}.Transform.Translation", "target": f"{result_add}.B", "stage": stage_name},
        {"source": f"{result_add}.Result", "target": f"{set_node}.Value", "stage": stage_name},
    ]
    return {"nodes": nodes, "links": links}


def _generic_distribution_operator_nodes(
    *,
    stage_name: str,
    graph_module_name: str,
    stage_tag: str,
    index: int,
    binding: Dict[str, Any],
    base_x: float,
    stage_y: float,
    set_node: str,
    set_defaults: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if stage_name != "forward":
        return {"nodes": [], "links": []}
    if not bool(binding.get("distribution_operator")):
        return {"nodes": [], "links": []}

    alpha = float(binding.get("distribution_alpha", 0.0))
    start_control = str(binding.get("distribution_start_control") or "")
    end_control = str(binding.get("distribution_end_control") or "")
    tag = str(binding.get("distribution_tag") or "Generic")
    if not start_control or not end_control:
        return {"nodes": [], "links": []}

    start_get = f"{graph_module_name}_{stage_tag}_{tag}Start_{index}"
    end_get = f"{graph_module_name}_{stage_tag}_{tag}End_{index}"
    delta = f"{graph_module_name}_{stage_tag}_{tag}Delta_{index}"
    alpha_mul = f"{graph_module_name}_{stage_tag}_{tag}AlphaMul_{index}"
    result_add = f"{graph_module_name}_{stage_tag}_{tag}Result_{index}"
    nodes = [
        {
            "name": start_get,
            "struct_path": "/Script/ControlRig.RigUnit_GetControlTransform",
            "method_name": "Execute",
            "position": [base_x + 110.0, stage_y + 360.0],
        },
        {
            "name": end_get,
            "struct_path": "/Script/ControlRig.RigUnit_GetControlTransform",
            "method_name": "Execute",
            "position": [base_x + 110.0, stage_y + 440.0],
        },
        {
            "name": delta,
            "struct_path": "/Script/RigVM.RigVMFunction_MathVectorSub",
            "method_name": "Execute",
            "position": [base_x + 300.0, stage_y + 400.0],
        },
        {
            "name": alpha_mul,
            "struct_path": "/Script/RigVM.RigVMFunction_MathVectorMul",
            "method_name": "Execute",
            "position": [base_x + 490.0, stage_y + 400.0],
        },
        {
            "name": result_add,
            "struct_path": "/Script/RigVM.RigVMFunction_MathVectorAdd",
            "method_name": "Execute",
            "position": [base_x + 680.0, stage_y + 400.0],
        },
    ]

    _add_pin_default(
        set_defaults,
        pin_path=f"{start_get}.Control",
        pin_path_candidates=[f"{start_get}.ControlFloat", f"{start_get}.Name"],
        value=start_control,
    )
    _add_pin_default(set_defaults, pin_path=f"{start_get}.Space", value="GlobalSpace")
    _add_pin_default(
        set_defaults,
        pin_path=f"{end_get}.Control",
        pin_path_candidates=[f"{end_get}.ControlFloat", f"{end_get}.Name"],
        value=end_control,
    )
    _add_pin_default(set_defaults, pin_path=f"{end_get}.Space", value="GlobalSpace")
    _add_pin_default(set_defaults, pin_path=f"{alpha_mul}.B", value=str(alpha))

    links = [
        {"source": f"{end_get}.Transform.Translation", "target": f"{delta}.A", "stage": stage_name},
        {"source": f"{start_get}.Transform.Translation", "target": f"{delta}.B", "stage": stage_name},
        {"source": f"{delta}.Result", "target": f"{alpha_mul}.A", "stage": stage_name},
        {"source": f"{alpha_mul}.Result", "target": f"{result_add}.A", "stage": stage_name},
        {"source": f"{start_get}.Transform.Translation", "target": f"{result_add}.B", "stage": stage_name},
        {"source": f"{result_add}.Result", "target": f"{set_node}.Value", "stage": stage_name},
    ]
    return {"nodes": nodes, "links": links}


def _annotate_point_target_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    metadata = module.get("metadata", {}) or {}
    aim_axis = str(metadata.get("aim_axis") or "+x")
    up_axis = str(metadata.get("up_axis") or "-z")
    output: List[Dict[str, Any]] = []
    for binding in bindings:
        if str(binding.get("tag", "")) != "point_target_constraint":
            output.append(binding)
            continue
        data = dict(binding)
        data["aim_axis"] = aim_axis
        data["up_axis"] = up_axis
        output.append(data)
    return output


def _annotate_hand_bindings(module: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if module.get("module_class") != "Hand":
        return bindings
    controls = module.get("controls", []) or []
    finger_roots = sorted(
        control
        for control in controls
        if str(control.get("role", "")).startswith("hand_finger_curl")
    )
    thumb_roots = sorted(
        control
        for control in controls
        if str(control.get("role", "")).startswith("hand_thumb_curl")
    )
    root_controls = finger_roots + thumb_roots
    if not root_controls:
        return bindings

    denominator = max(len(root_controls), 1) * 0.5
    ratio = 1.0 / denominator if denominator > 0.0 else 1.0
    rate_lookup: Dict[str, float] = {}
    rate = 0.0
    for control in root_controls:
        control_name = control.get("name")
        if not control_name:
            continue
        rate_lookup[control_name] = rate
        rate -= ratio

    output: List[Dict[str, Any]] = []
    for binding in bindings:
        data = dict(binding)
        control_name = str(data.get("source_control", ""))
        if control_name in rate_lookup:
            data["hand_operator_profile"] = "curl_root"
            data["hand_rate"] = rate_lookup[control_name]
        output.append(data)
    return output


def _build_module_math_model(module: Dict[str, Any]) -> Dict[str, Any]:
    module_name = module.get("module_name", "Module")
    module_class = module.get("module_class", "")
    settings = module.get("module_settings", {})
    equations: List[Dict[str, str]] = []
    implemented: List[str] = []
    approximations: List[str] = []

    if module_class in {"Limb", "QuadLimb"}:
        equations.extend(
            [
                {
                    "id": "ik_fk_rotation_blend",
                    "expression": "base_joint.rotate = lerp(FK.rotate, IK.rotate, IK_FK_Switch)",
                    "source": "blendColors FK/IK rotation chain",
                },
                {
                    "id": "ik_fk_visibility_reverse",
                    "expression": "IK_visibility = 1.0 - IK_FK_Switch; FK_visibility = IK_FK_Switch",
                    "source": "reverse node driving control visibility",
                },
            ]
        )
        implemented.append("staged_forward_backward_construction_transform_mapping")
        if bool(settings.get("foot", False)):
            equations.append(
                {
                    "id": "foot_roll_pivot_chain",
                    "expression": "Toe/Ball/Pivot/InBank/OutBank/Heel transforms compose in ordered parent pivot chain.",
                    "source": "foot pivot hierarchy + multiplyDivide inv-toe roll compensation",
                }
            )
            implemented.append("foot_roll_hierarchy_and_stage_links")
            implemented.append("foot_roll_inverse_toe_and_bank_compensation_operators")
        if module_class == "QuadLimb":
            equations.append(
                {
                    "id": "quad_auto_roll_distribution",
                    "expression": "Auto-roll controls are sampled along upper/lower segments with alpha-based interpolation.",
                    "source": "upper/lower auto-roll control series",
                }
            )
            implemented.append("quad_auto_roll_control_sampling")

    if module_class == "Hand":
        equations.extend(
            [
                {
                    "id": "twist_splay_multiply_divide",
                    "expression": "twist = rotateX * (-1-rate); splay = translateX * (-1.5*(1-rate)*aimDir)",
                    "source": "twistSplay multiplyDivide network",
                },
                {
                    "id": "updn_multiply_divide",
                    "expression": "upDn = rotateZ * aimDir",
                    "source": "upDn multiplyDivide network",
                },
            ]
        )
        implemented.append("hand_offset_chain_and_digit_driver_controls")
        implemented.append("hand_multiply_divide_rate_falloff_operator_network")

    if module_class == "PointTarget":
        constrain_type = str(settings.get("constrain_type") or "point").lower()
        equations.append(
            {
                "id": "weighted_target_constraint",
                "expression": "target_transform = sum_i(weight_i * source_i_transform)",
                "source": "targetsInfluence weighted constraints",
            }
        )
        implemented.append("weighted_point_target_binding_generation")
        if constrain_type not in {"parent", ""}:
            implemented.append("point_target_channel_isolated_set_units")
        if constrain_type == "aim":
            implemented.append("point_target_aim_axis_vector_reconstruction")
        if bool(settings.get("maintain_offset", True)):
            implemented.append("point_target_maintain_offset_buffer_reconstruction")

    if module_class == "RibbonBindIK":
        equations.append(
            {
                "id": "ribbon_bind_distribution",
                "expression": "bind_i = lerp(start, end, i/(count-1)); optional reverse chain inverts driver order",
                "source": "bind and reverse control generation",
            }
        )
        implemented.append("ribbon_bind_and_reverse_control_mapping")
        implemented.append("ribbon_bind_distribution_operator_network")

    if module_class == "Root":
        equations.append(
            {
                "id": "root_direct_mapping",
                "expression": "root/base proxies follow root controls in staged global mapping.",
                "source": "Root control and optional offset control mapping",
            }
        )
        implemented.append("root_transform_mapping")
        if bool(settings.get("add_offset", False)):
            implemented.append("root_offset_chain_mapping")

    if module_class == "FK":
        equations.append(
            {
                "id": "fk_chain_mapping",
                "expression": "fk_joint_i follows fk_control_i transform across solve stages.",
                "source": "FK proxy/control staged mapping",
            }
        )
        implemented.append("fk_chain_transform_mapping")
        if int(settings.get("segments") or 0) > 0:
            implemented.append("fk_segment_driver_distribution_operator_network")

    if module_class == "FKSegment":
        equations.append(
            {
                "id": "fksegment_chain_mapping",
                "expression": "segment chain follows fk controls; optional reverse and rail controls remap distribution.",
                "source": "FKSegment controls, reverse chain, IK rail controls",
            }
        )
        implemented.append("fksegment_chain_transform_mapping")
        if bool(settings.get("reverse", False)):
            implemented.append("fksegment_reverse_chain_mapping")
        if bool(settings.get("ik_rail", False)):
            implemented.append("fksegment_ik_rail_distribution_operator_network")

    if module_class == "Lips":
        equations.append(
            {
                "id": "lips_corner_segment_distribution",
                "expression": "lip_segment_i = lerp(left_corner, right_corner, alpha_i) + upper/lower offsets",
                "source": "Lips segment controls and center offset references",
            }
        )
        implemented.append("lips_segment_distribution_operator_network")
        if bool(settings.get("jaw_target")):
            implemented.append("lips_jaw_follow_control_mapping")

    if module_class == "FollicleEye":
        equations.append(
            {
                "id": "follicle_eye_lid_distribution",
                "expression": "lid_segment_i = lerp(inner_corner, outer_corner, alpha_i) + upper/lower lid offsets",
                "source": "FollicleEye lid segment controls",
            }
        )
        implemented.append("follicle_eye_segment_distribution_operator_network")
        if bool(settings.get("eyeball", False)):
            implemented.append("follicle_eye_eyeball_aim_mapping")
        if settings.get("follicle_surface") or settings.get("follicle_mesh"):
            implemented.append("follicle_eye_attachment_control_mapping")

    if module_class == "IK":
        equations.append(
            {
                "id": "ik_placeholder_mapping",
                "expression": "ik controls map directly to driven proxies where present",
                "source": "IK translator fallback mapping",
            }
        )
        implemented.append("ik_placeholder_transform_mapping")

    if module_class == "Floating":
        equations.append(
            {
                "id": "floating_placeholder_mapping",
                "expression": "floating controls map directly to driven proxies where present",
                "source": "Floating translator fallback mapping",
            }
        )
        implemented.append("floating_placeholder_transform_mapping")

    if module_class == "TestMotionModule":
        equations.append(
            {
                "id": "test_motion_mapping",
                "expression": "test motion controls map directly to expected proxy chain for validation.",
                "source": "TestMotionModule translator mapping",
            }
        )
        implemented.append("test_motion_module_transform_mapping")

    implementation_status = "implemented" if not approximations else "approximate"
    if not equations and not implemented and not approximations:
        implementation_status = "unknown"

    return {
        "module_name": module_name,
        "module_class": module_class,
        "implementation_status": implementation_status,
        "equations": equations,
        "implemented": implemented,
        "approximations": approximations,
        "approximation_gaps": approximations,
    }


def _execution_stage_specs() -> Dict[str, Dict[str, Any]]:
    return {
        "construction": {
            "tag": "CNS",
            "event_name": "Construction",
            "entry_sources": [
                "PrepareForExecution.ExecuteContext",
                "PreBeginExecution.ExecuteContext",
                "Construction.ExecuteContext",
            ],
        },
        "forward": {
            "tag": "FWD",
            "event_name": "ForwardSolve",
            "entry_sources": [
                "BeginExecution.ExecuteContext",
                "ForwardsSolve.ExecuteContext",
                "ForwardSolve.ExecuteContext",
            ],
        },
        "backward": {
            "tag": "BWD",
            "event_name": "BackwardSolve",
            "entry_sources": [
                "InverseExecution.ExecuteContext",
                "BackwardsSolve.ExecuteContext",
                "BackwardSolve.ExecuteContext",
            ],
        },
    }


def _add_pin_default(
    pin_defaults: List[Dict[str, Any]],
    *,
    pin_path: Optional[str] = None,
    pin_path_candidates: Optional[List[str]] = None,
    value: Any,
) -> None:
    entry: Dict[str, Any] = {"value": str(value)}
    if pin_path is not None:
        entry["pin_path"] = pin_path
    if pin_path_candidates:
        entry["pin_path_candidates"] = list(pin_path_candidates)
    pin_defaults.append(entry)


def _make_stage_nodes_for_binding(
    *,
    stage_name: str,
    stage_tag: str,
    graph_module_name: str,
    index: int,
    binding: Dict[str, Any],
) -> Dict[str, Any]:
    source_control = binding["source_control"]
    target_item_type = binding.get("target_item_type", "Bone")
    target_item_name = binding["target_item_name"]
    source_space = str(binding.get("source_space", "GlobalSpace"))
    target_space = str(binding.get("target_space", "GlobalSpace"))
    weight = float(binding.get("weight", 1.0))
    target_channel = str(binding.get("target_channel", "transform"))
    get_node = f"{graph_module_name}_{stage_tag}_Get_{index}"
    set_node = f"{graph_module_name}_{stage_tag}_Set_{index}"
    base_x = 200.0 + (index * 380.0)
    stage_y = {
        "construction": -300.0,
        "forward": 200.0,
        "backward": 700.0,
    }.get(stage_name, 200.0)

    weight_pin_path = binding.get("weight_pin_path")
    weight_pin_path_candidates = list(binding.get("weight_pin_path_candidates") or [])
    invert_weight = bool(binding.get("weight_invert", False))
    if stage_name == "forward":
        get_struct = "/Script/ControlRig.RigUnit_GetControlTransform"
        get_defaults: List[Dict[str, Any]] = []
        _add_pin_default(get_defaults, pin_path=f"{get_node}.Control", value=str(source_control))
        _add_pin_default(get_defaults, pin_path=f"{get_node}.Space", value=source_space)
        if target_channel == "translation":
            set_struct = "/Script/ControlRig.RigUnit_SetTranslation"
        elif target_channel == "rotation":
            set_struct = "/Script/ControlRig.RigUnit_SetRotation"
        elif target_channel == "scale":
            set_struct = "/Script/ControlRig.RigUnit_SetScale"
        else:
            set_struct = "/Script/ControlRig.RigUnit_SetTransform"
        set_item = f'(Type={target_item_type},Name="{target_item_name}")'
        set_b_initial = "False"
        set_weight = str(weight)
    else:
        get_struct = "/Script/ControlRig.RigUnit_GetTransform"
        get_defaults = []
        _add_pin_default(
            get_defaults,
            pin_path=f"{get_node}.Item",
            value=f'(Type={target_item_type},Name="{target_item_name}")',
        )
        _add_pin_default(get_defaults, pin_path=f"{get_node}.Space", value=target_space)
        _add_pin_default(get_defaults, pin_path=f"{get_node}.bInitial", value="False")
        set_struct = "/Script/ControlRig.RigUnit_SetTransform"
        set_item = f'(Type=Control,Name="{source_control}")'
        set_b_initial = "True" if stage_name == "construction" else "False"
        set_weight = "1.0"

    set_defaults: List[Dict[str, Any]] = []
    _add_pin_default(set_defaults, pin_path=f"{set_node}.Item", value=set_item)
    _add_pin_default(set_defaults, pin_path=f"{set_node}.Space", value=source_space)
    _add_pin_default(set_defaults, pin_path=f"{set_node}.Weight", value=set_weight)
    _add_pin_default(set_defaults, pin_path=f"{set_node}.bInitial", value=set_b_initial)

    extra_nodes: List[Dict[str, Any]] = []
    extra_links: List[Dict[str, Any]] = []
    transform_source_pin = f"{get_node}.Transform"

    if stage_name == "forward" and (weight_pin_path or weight_pin_path_candidates):
        weight_node = f"{graph_module_name}_{stage_tag}_Weight_{index}"
        extra_nodes.append(
            {
                "name": weight_node,
                "struct_path": "/Script/ControlRig.RigUnit_GetControlFloat",
                "method_name": "Execute",
                "position": [base_x + 110.0, stage_y - 120.0],
            }
        )
        _add_pin_default(
            set_defaults,
            pin_path=f"{weight_node}.Control",
            pin_path_candidates=[f"{weight_node}.ControlFloat", f"{weight_node}.Name"],
            value=str(source_control),
        )
        channel_name = str(weight_pin_path.split(".")[-1]) if weight_pin_path else "IK_FK_Switch"
        _add_pin_default(
            set_defaults,
            pin_path=f"{weight_node}.Name",
            pin_path_candidates=[f"{weight_node}.Channel", f"{weight_node}.FloatName"],
            value=channel_name,
        )

        if invert_weight:
            invert_node = f"{graph_module_name}_{stage_tag}_OneMinus_{index}"
            extra_nodes.append(
                {
                    "name": invert_node,
                    "struct_path": "/Script/RigVM.RigVMFunction_MathDoubleSub",
                    "method_name": "Execute",
                    "position": [base_x + 290.0, stage_y - 120.0],
                }
            )
            _add_pin_default(set_defaults, pin_path=f"{invert_node}.A", value="1.0")
            extra_links.append({"source": f"{weight_node}.Float", "target": f"{invert_node}.B", "stage": stage_name})
            extra_links.append({"source": f"{invert_node}.Result", "target": f"{set_node}.Weight", "stage": stage_name})
        else:
            extra_links.append({"source": f"{weight_node}.Float", "target": f"{set_node}.Weight", "stage": stage_name})

    if stage_name == "forward" and bool(binding.get("use_offset_buffer")):
        offset_node = f"{graph_module_name}_{stage_tag}_Offset_{index}"
        extra_nodes.append(
            {
                "name": offset_node,
                "struct_path": "/Script/RigVM.RigVMFunction_MathVectorAdd",
                "method_name": "Execute",
                "position": [base_x + 120.0, stage_y + 120.0],
            }
        )
        offset_vector = binding.get("offset_vector") or [0.0, 0.0, 0.0]
        _add_pin_default(set_defaults, pin_path=f"{offset_node}.B", value=_vec_pin_literal(offset_vector))
        extra_links.append({"source": f"{get_node}.Transform.Translation", "target": f"{offset_node}.A", "stage": stage_name})
        if target_channel == "translation":
            extra_links.append({"source": f"{offset_node}.Result", "target": f"{set_node}.Value", "stage": stage_name})
            transform_source_pin = ""

    if stage_name == "forward" and bool(binding.get("use_aim_axis_math")):
        aim_vector_node = f"{graph_module_name}_{stage_tag}_AimVec_{index}"
        aim_add_node = f"{graph_module_name}_{stage_tag}_AimOffset_{index}"
        aim_apply_node = f"{graph_module_name}_{stage_tag}_AimApply_{index}"
        extra_nodes.extend(
            [
                {
                    "name": aim_vector_node,
                    "struct_path": "/Script/RigVM.RigVMFunction_MathVectorSub",
                    "method_name": "Execute",
                    "position": [base_x + 120.0, stage_y + 160.0],
                },
                {
                    "name": aim_add_node,
                    "struct_path": "/Script/RigVM.RigVMFunction_MathVectorAdd",
                    "method_name": "Execute",
                    "position": [base_x + 300.0, stage_y + 160.0],
                },
                {
                    "name": aim_apply_node,
                    "struct_path": "/Script/ControlRig.RigUnit_AimBone",
                    "method_name": "Execute",
                    "position": [base_x + 500.0, stage_y + 160.0],
                },
            ]
        )
        _add_pin_default(
            set_defaults,
            pin_path=f"{aim_apply_node}.PrimaryAxis",
            value=_vec_pin_literal(binding.get("aim_axis_vector") or [1.0, 0.0, 0.0]),
        )
        _add_pin_default(
            set_defaults,
            pin_path=f"{aim_apply_node}.SecondaryAxis",
            value=_vec_pin_literal(binding.get("up_axis_vector") or [0.0, 0.0, 1.0]),
        )
        _add_pin_default(set_defaults, pin_path=f"{aim_apply_node}.Weight", value=str(binding.get("weight", 1.0)))
        _add_pin_default(set_defaults, pin_path=f"{aim_apply_node}.Item", value=f'(Type={target_item_type},Name="{target_item_name}")')
        _add_pin_default(set_defaults, pin_path=f"{aim_apply_node}.Space", value=source_space)
        _add_pin_default(set_defaults, pin_path=f"{aim_apply_node}.bPropagateToChildren", value="True")
        _add_pin_default(set_defaults, pin_path=f"{aim_add_node}.B", value=_vec_pin_literal(binding.get("offset_vector") or [0.0, 0.0, 0.0]))
        extra_links.append({"source": f"{get_node}.Transform.Translation", "target": f"{aim_vector_node}.A", "stage": stage_name})
        extra_links.append({"source": f"{set_node}.Value.Translation", "target": f"{aim_vector_node}.B", "stage": stage_name})
        extra_links.append({"source": f"{aim_vector_node}.Result", "target": f"{aim_add_node}.A", "stage": stage_name})
        extra_links.append({"source": f"{aim_add_node}.Result", "target": f"{aim_apply_node}.Target", "stage": stage_name})
        extra_links.append({"source": f"{set_node}.ExecuteContext", "target": f"{aim_apply_node}.ExecuteContext", "stage": stage_name})

    if stage_name == "forward" and binding.get("hand_operator"):
        operator = str(binding.get("hand_operator"))
        hand_control = str(binding.get("hand_global_control") or source_control)
        input_channel = str(binding.get("hand_input_channel") or "rotateX")
        target_axis = str(binding.get("hand_target_axis") or "Y")
        factor = float(binding.get("hand_factor", 1.0))

        hand_get = f"{graph_module_name}_{stage_tag}_Hand_{index}_{operator}_Get"
        hand_mul = f"{graph_module_name}_{stage_tag}_Hand_{index}_{operator}_Mul"
        hand_add = f"{graph_module_name}_{stage_tag}_Hand_{index}_{operator}_Add"
        hand_neg = f"{graph_module_name}_{stage_tag}_Hand_{index}_{operator}_Neg"
        extra_nodes.extend(
            [
                {
                    "name": hand_get,
                    "struct_path": "/Script/ControlRig.RigUnit_GetControlFloat",
                    "method_name": "Execute",
                    "position": [base_x + 110.0, stage_y + 120.0],
                },
                {
                    "name": hand_mul,
                    "struct_path": "/Script/RigVM.RigVMFunction_MathDoubleMul",
                    "method_name": "Execute",
                    "position": [base_x + 270.0, stage_y + 120.0],
                },
                {
                    "name": hand_add,
                    "struct_path": "/Script/RigVM.RigVMFunction_MathDoubleAdd",
                    "method_name": "Execute",
                    "position": [base_x + 430.0, stage_y + 120.0],
                },
                {
                    "name": hand_neg,
                    "struct_path": "/Script/RigVM.RigVMFunction_MathDoubleNegate",
                    "method_name": "Execute",
                    "position": [base_x + 590.0, stage_y + 120.0],
                },
            ]
        )
        _add_pin_default(
            set_defaults,
            pin_path=f"{hand_get}.Control",
            pin_path_candidates=[f"{hand_get}.ControlFloat", f"{hand_get}.Name"],
            value=hand_control,
        )
        _add_pin_default(
            set_defaults,
            pin_path=f"{hand_get}.Name",
            pin_path_candidates=[f"{hand_get}.Channel", f"{hand_get}.FloatName"],
            value=input_channel,
        )
        _add_pin_default(set_defaults, pin_path=f"{hand_mul}.B", value=str(factor))
        _add_pin_default(set_defaults, pin_path=f"{hand_add}.A", value="1.0")
        _add_pin_default(set_defaults, pin_path=f"{hand_neg}.Value", value="0.0")
        if target_axis.upper() == "Z":
            _add_pin_default(set_defaults, pin_path=f"{set_node}.Value.Z", value="0.0")
        else:
            _add_pin_default(set_defaults, pin_path=f"{set_node}.Value.Y", value="0.0")

        extra_links.append({"source": f"{hand_get}.Float", "target": f"{hand_mul}.A", "stage": stage_name})
        extra_links.append({"source": f"{hand_mul}.Result", "target": f"{hand_add}.B", "stage": stage_name})
        extra_links.append({"source": f"{hand_add}.Result", "target": f"{hand_neg}.Value", "stage": stage_name})
        if target_axis.upper() == "Z":
            extra_links.append({"source": f"{hand_neg}.Result", "target": f"{set_node}.Value.Z", "stage": stage_name})
        else:
            extra_links.append({"source": f"{hand_neg}.Result", "target": f"{set_node}.Value.Y", "stage": stage_name})

    foot_roll_ops = _limb_foot_roll_operator_nodes(
        stage_name=stage_name,
        graph_module_name=graph_module_name,
        stage_tag=stage_tag,
        index=index,
        binding=binding,
        base_x=base_x,
        stage_y=stage_y,
        set_node=set_node,
        set_defaults=set_defaults,
    )
    extra_nodes.extend(foot_roll_ops["nodes"])
    extra_links.extend(foot_roll_ops["links"])

    visibility_ops = _limb_visibility_operator_nodes(
        stage_name=stage_name,
        graph_module_name=graph_module_name,
        stage_tag=stage_tag,
        index=index,
        binding=binding,
        base_x=base_x,
        stage_y=stage_y,
        set_node=set_node,
        set_defaults=set_defaults,
    )
    extra_nodes.extend(visibility_ops["nodes"])
    extra_links.extend(visibility_ops["links"])

    ribbon_ops = _ribbon_bind_operator_nodes(
        stage_name=stage_name,
        graph_module_name=graph_module_name,
        stage_tag=stage_tag,
        index=index,
        binding=binding,
        base_x=base_x,
        stage_y=stage_y,
        set_node=set_node,
        set_defaults=set_defaults,
    )
    extra_nodes.extend(ribbon_ops["nodes"])
    extra_links.extend(ribbon_ops["links"])

    distribution_ops = _generic_distribution_operator_nodes(
        stage_name=stage_name,
        graph_module_name=graph_module_name,
        stage_tag=stage_tag,
        index=index,
        binding=binding,
        base_x=base_x,
        stage_y=stage_y,
        set_node=set_node,
        set_defaults=set_defaults,
    )
    extra_nodes.extend(distribution_ops["nodes"])
    extra_links.extend(distribution_ops["links"])

    links: List[Dict[str, Any]] = []
    if transform_source_pin:
        links.append({"source": transform_source_pin, "target": f"{set_node}.Value", "stage": stage_name})
    links.extend(extra_links)

    return {
        "nodes": [
            {
                "name": get_node,
                "struct_path": get_struct,
                "method_name": "Execute",
                "position": [base_x, stage_y],
            },
            {
                "name": set_node,
                "struct_path": set_struct,
                "method_name": "Execute",
                "position": [base_x + 220.0, stage_y],
            },
        ]
        + extra_nodes,
        "pin_defaults": get_defaults + set_defaults,
        "transform_link": None,
        "extra_links": links,
        "set_exec_pin": f"{set_node}.ExecuteContext",
        "stage": stage_name,
        "get_node_name": get_node,
        "set_node_name": set_node,
    }


def build_module_behavior_graph_plan(module: Dict[str, Any]) -> Dict[str, Any]:
    """Build a RigVM graph node/link plan for one module.

    The plan is consumed by Unreal-side graph application and can be unit-tested
    outside Unreal.
    """
    module_name = module.get("module_name", "Module")
    module_class = module.get("module_class", "")
    graph_module_name = _graph_safe_name(module_name)
    bindings = _control_to_proxy_bindings(module)
    math_model = _build_module_math_model(module)
    warnings: List[str] = list(math_model.get("approximations", []))
    control_lookup = {control.get("name"): control for control in module.get("controls", []) if control.get("name")}

    if module_class == "PointTarget":
        point_root = next((control for control in module.get("controls", []) if control.get("role") == "point_target"), None)
        default_target_bone_name = None
        if point_root and point_root.get("driven_proxy"):
            default_target_bone_name = f"{module_name}_{point_root['driven_proxy']}_Proxy"

        bindings = [
            binding
            for binding in bindings
            if control_lookup.get(binding["source_control"], {}).get("role") != "point_target_reference"
        ]
        point_bindings = _point_target_behavior_bindings(module, default_target_bone_name=default_target_bone_name)
        bindings.extend(point_bindings)
        bindings = _point_target_channel_bindings(module, bindings)
        bindings = _annotate_point_target_bindings(module, bindings)
        bindings = _point_target_operator_bindings(module, bindings)
    if module_class == "Hand":
        bindings = _annotate_hand_bindings(module, bindings)
        bindings = _hand_operator_bindings(module, bindings)
    if module_class == "RibbonBindIK":
        bindings = _ribbon_bind_operator_bindings(module, bindings)
    if module_class in {"IK", "Floating", "TestMotionModule"}:
        bindings = _direct_drive_operator_bindings(module, bindings)
    if module_class in {"FK", "FKSegment"}:
        bindings = _fk_distribution_operator_bindings(module, bindings)
    if module_class == "Lips":
        bindings = _lips_operator_bindings(module, bindings)
    if module_class == "FollicleEye":
        bindings = _follicle_eye_operator_bindings(module, bindings)
    if module_class in {"Limb", "QuadLimb"}:
        bindings = _limb_ik_fk_bindings(module, bindings)
        bindings = _limb_foot_roll_operator_bindings(module, bindings)
    nodes: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []
    pin_defaults: List[Dict[str, str]] = []
    stage_summaries: Dict[str, Dict[str, int]] = {}
    event_nodes = [
        {
            "name": spec.get("event_name", stage_name.title()),
            "stage": stage_name,
            "entry_sources": list(spec.get("entry_sources", [])),
        }
        for stage_name, spec in _execution_stage_specs().items()
    ]

    for stage_name, stage_spec in _execution_stage_specs().items():
        stage_exec_pin: Optional[str] = None
        stage_link_count = 0
        stage_node_count = 0
        for index, binding in enumerate(bindings):
            stage_nodes = _make_stage_nodes_for_binding(
                stage_name=stage_name,
                stage_tag=stage_spec["tag"],
                graph_module_name=graph_module_name,
                index=index,
                binding=binding,
            )
            nodes.extend(stage_nodes["nodes"])
            pin_defaults.extend(stage_nodes["pin_defaults"])
            transform_link = stage_nodes.get("transform_link")
            if transform_link:
                links.append(transform_link)
                stage_link_count += 1
            links.extend(stage_nodes.get("extra_links", []))
            stage_node_count += len(stage_nodes["nodes"])
            stage_link_count += len(stage_nodes.get("extra_links", []))

            exec_link_target = stage_nodes["set_exec_pin"]
            if stage_exec_pin is None:
                links.append(
                    {
                        "source_candidates": list(stage_spec["entry_sources"]),
                        "target": exec_link_target,
                        "stage": stage_name,
                    }
                )
                stage_link_count += 1
            else:
                links.append({"source": stage_exec_pin, "target": exec_link_target, "stage": stage_name})
                stage_link_count += 1
            stage_exec_pin = exec_link_target

        stage_summaries[stage_name] = {
            "nodes": stage_node_count,
            "links": stage_link_count,
        }

    return {
        "module_name": module_name,
        "nodes": nodes,
        "links": links,
        "pin_defaults": pin_defaults,
        "warnings": warnings,
        "stages": stage_summaries,
        "event_nodes": event_nodes,
        "math_model": math_model,
    }


def build_behavior_graph_plan(translated_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build aggregate RigVM graph plan from translated payload."""
    module_plans = [build_module_behavior_graph_plan(module) for module in translated_payload.get("modules", [])]
    nodes: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []
    pin_defaults: List[Dict[str, str]] = []
    warnings: List[str] = []
    stages: Dict[str, Dict[str, int]] = {}
    event_nodes: List[Dict[str, Any]] = []
    math_models: List[Dict[str, Any]] = []
    seen_event_nodes = set()
    for module_plan in module_plans:
        nodes.extend(module_plan["nodes"])
        links.extend(module_plan["links"])
        pin_defaults.extend(module_plan["pin_defaults"])
        for stage_name, stage_data in module_plan.get("stages", {}).items():
            aggregate = stages.setdefault(stage_name, {"nodes": 0, "links": 0})
            aggregate["nodes"] += int(stage_data.get("nodes", 0))
            aggregate["links"] += int(stage_data.get("links", 0))
        for warning in module_plan.get("warnings", []):
            warning_message = f"{module_plan.get('module_name', 'Module')}: {warning}"
            if warning_message not in warnings:
                warnings.append(warning_message)
        for event_node in module_plan.get("event_nodes", []):
            event_key = (event_node.get("name"), tuple(event_node.get("entry_sources", [])))
            if event_key in seen_event_nodes:
                continue
            seen_event_nodes.add(event_key)
            event_nodes.append(event_node)
        if module_plan.get("math_model"):
            math_models.append(module_plan["math_model"])
    return {
        "modules": module_plans,
        "nodes": nodes,
        "links": links,
        "pin_defaults": pin_defaults,
        "warnings": warnings,
        "stages": stages,
        "event_nodes": event_nodes,
        "math_models": math_models,
    }


def _get_rigvm_controller(control_rig):
    model = None
    get_model = getattr(control_rig, "get_model", None)
    if callable(get_model):
        try:
            model = get_model()
        except Exception:
            model = None

    get_or_create_controller = getattr(control_rig, "get_or_create_controller", None)
    if callable(get_or_create_controller):
        for args in ((model,), tuple()):
            try:
                controller = get_or_create_controller(*args)
                if controller is not None:
                    return controller
            except Exception:
                continue

    get_controller = getattr(control_rig, "get_controller", None)
    if callable(get_controller):
        for args in ((model,), tuple()):
            try:
                controller = get_controller(*args)
                if controller is not None:
                    return controller
            except Exception:
                continue

    get_controller_by_name = getattr(control_rig, "get_controller_by_name", None)
    if callable(get_controller_by_name):
        for graph_name in ("Rig Graph", "RigVMModel", "Model"):
            try:
                controller = get_controller_by_name(graph_name)
                if controller is not None:
                    return controller
            except Exception:
                continue

    controllers_map = getattr(control_rig, "controllers", None)
    if controllers_map:
        try:
            for _, controller in controllers_map.items():
                if controller is not None:
                    return controller
        except Exception:
            pass

    raise RuntimeError("Unable to acquire RigVMController from ControlRigBlueprint")


def _controller_add_unit_node(controller, node_spec: Dict[str, Any]) -> Any:
    unreal = _load_unreal()
    add_unit = getattr(controller, "add_unit_node_from_struct_path", None)
    if not callable(add_unit):
        raise RuntimeError("RigVMController.add_unit_node_from_struct_path is unavailable")

    position = unreal.Vector2D(float(node_spec["position"][0]), float(node_spec["position"][1]))
    struct_path = node_spec["struct_path"]
    method_name = node_spec.get("method_name", "Execute")
    node_name = node_spec["name"]

    # Keep fallbacks strict to avoid invoking ambiguous positional signatures.
    # Some UE Python bindings can crash editor-native code when argument ordering
    # is invalid but still marshaled across the C++ boundary.
    call_variants = [
        (
            tuple(),
            {
                "script_struct_path": struct_path,
                "method_name": method_name,
                "position": position,
                "node_name": node_name,
                "setup_undo_redo": True,
                "print_python_command": False,
            },
        ),
        (
            tuple(),
            {
                "script_struct_path": struct_path,
                "method_name": method_name,
                "position": position,
                "node_name": node_name,
                "setup_undo_redo": True,
            },
        ),
        (
            tuple(),
            {
                "script_struct_path": struct_path,
                "method_name": method_name,
                "position": position,
                "node_name": node_name,
            },
        ),
        (
            tuple(),
            {
                "struct_path": struct_path,
                "method_name": method_name,
                "position": position,
                "node_name": node_name,
                "setup_undo_redo": True,
                "print_python_command": False,
            },
        ),
        (
            tuple(),
            {
                "struct_path": struct_path,
                "method_name": method_name,
                "position": position,
                "node_name": node_name,
                "setup_undo_redo": True,
            },
        ),
        (
            tuple(),
            {
                "struct_path": struct_path,
                "method_name": method_name,
                "position": position,
                "node_name": node_name,
            },
        ),
    ]
    last_error: Optional[Exception] = None
    for args, kwargs in call_variants:
        try:
            return add_unit(*args, **kwargs)
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return None


def _controller_set_pin_default(controller, pin_path: str, value: str) -> bool:
    setter = getattr(controller, "set_pin_default_value", None)
    if not callable(setter):
        return False
    call_variants = [
        (
            tuple(),
            {
                "pin_path": pin_path,
                "default_value": value,
                "setup_undo_redo": True,
                "print_python_command": False,
            },
        ),
        (
            tuple(),
            {
                "pin_path": pin_path,
                "default_value": value,
                "setup_undo_redo": True,
            },
        ),
        (
            tuple(),
            {
                "pin_path": pin_path,
                "default_value": value,
            },
        ),
        (
            tuple(),
            {
                "pin_path": pin_path,
                "value": value,
            },
        ),
    ]
    for args, kwargs in call_variants:
        try:
            setter(*args, **kwargs)
            return True
        except Exception:
            continue
    return False


def _controller_set_pin_default_with_candidates(
    controller,
    *,
    pin_path: Optional[str],
    pin_path_candidates: Optional[List[str]],
    value: str,
) -> bool:
    candidate_paths: List[str] = []
    if pin_path:
        candidate_paths.append(pin_path)
    if pin_path_candidates:
        candidate_paths.extend([candidate for candidate in pin_path_candidates if candidate not in candidate_paths])
    for candidate_path in candidate_paths:
        if _controller_set_pin_default(controller, candidate_path, value):
            return True
    return False


def _controller_add_link(controller, source: str, target: str) -> bool:
    add_link = getattr(controller, "add_link", None)
    if not callable(add_link):
        return False
    call_variants = [
        (
            tuple(),
            {
                "source_pin_path": source,
                "target_pin_path": target,
                "setup_undo_redo": True,
                "print_python_command": False,
            },
        ),
        (
            tuple(),
            {
                "source_pin_path": source,
                "target_pin_path": target,
                "setup_undo_redo": True,
            },
        ),
        (
            tuple(),
            {
                "source_pin_path": source,
                "target_pin_path": target,
            },
        ),
        (
            tuple(),
            {
                "source": source,
                "target": target,
            },
        ),
    ]
    for args, kwargs in call_variants:
        try:
            result = add_link(*args, **kwargs)
            return bool(result) if result is not None else True
        except Exception:
            continue
    return False


def apply_behavior_graph_to_control_rig(control_rig, translated_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Emit RigVM nodes and links for control-to-proxy behavior."""
    plan = build_behavior_graph_plan(translated_payload)
    if not plan["nodes"]:
        return {"nodes_added": 0, "links_added": 0, "defaults_set": 0, "warnings": []}

    controller = _get_rigvm_controller(control_rig)
    warnings: List[str] = list(plan.get("warnings", []))
    nodes_added = 0
    for node_spec in plan["nodes"]:
        try:
            _controller_add_unit_node(controller, node_spec)
            nodes_added += 1
        except Exception as exc:
            warnings.append(f"Failed to add node {node_spec['name']}: {exc}")

    defaults_set = 0
    for pin_default in plan["pin_defaults"]:
        pin_path = pin_default.get("pin_path")
        pin_path_candidates = pin_default.get("pin_path_candidates")
        value = str(pin_default.get("value", ""))
        if _controller_set_pin_default_with_candidates(
            controller,
            pin_path=pin_path,
            pin_path_candidates=pin_path_candidates,
            value=value,
        ):
            defaults_set += 1
        else:
            if pin_path_candidates:
                warnings.append(f"Failed to set default {pin_path or pin_path_candidates[0]} with candidates {pin_path_candidates}")
            else:
                warnings.append(f"Failed to set default {pin_path}")

    links_added = 0
    for link in plan["links"]:
        if "source" in link:
            if _controller_add_link(controller, link["source"], link["target"]):
                links_added += 1
            else:
                warnings.append(f"Failed to add link {link['source']} -> {link['target']}")
            continue

        source_candidates = list(link.get("source_candidates", []))
        target = link.get("target")
        if not source_candidates or not target:
            warnings.append(f"Invalid link spec: {link}")
            continue
        linked = False
        for source_candidate in source_candidates:
            if _controller_add_link(controller, source_candidate, target):
                links_added += 1
                linked = True
                break
        if not linked:
            warnings.append(f"Failed to add link from any {source_candidates} -> {target}")

    return {
        "nodes_added": nodes_added,
        "links_added": links_added,
        "defaults_set": defaults_set,
        "warnings": warnings,
    }


def import_skeletal_mesh(fbx_file: str, destination_path: str, asset_name: Optional[str] = None) -> str:
    """Import a skeletal mesh FBX into Unreal content browser."""
    unreal = _load_unreal()
    destination = destination_path.rstrip("/")
    if not destination.startswith("/Game"):
        raise ValueError("destination_path must be inside /Game")

    # Reuse existing skeletal mesh when present to avoid repeated destructive
    # import cycles that can destabilize editor sessions on some UE versions.
    if asset_name:
        expected_path = f"{destination}/{_safe_name(asset_name)}"
        existing_asset = unreal.EditorAssetLibrary.load_asset(expected_path)
        if existing_asset is not None and isinstance(existing_asset, unreal.SkeletalMesh):
            return expected_path

    task = unreal.AssetImportTask()
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    task.set_editor_property("filename", str(Path(fbx_file).expanduser().resolve()))
    task.set_editor_property("destination_path", destination)
    if asset_name:
        safe_asset_name = _safe_name(asset_name)
        existing_mesh_path = f"{destination}/{safe_asset_name}"
        existing_mesh = unreal.EditorAssetLibrary.load_asset(existing_mesh_path)
        if isinstance(existing_mesh, unreal.SkeletalMesh):
            return existing_mesh_path
        task.set_editor_property("destination_name", safe_asset_name)

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


def _asset_object_path(asset: Any) -> Optional[str]:
    """Return package asset path (/Game/Path/Asset) from a UObject."""
    if asset is None:
        return None

    get_path_name = getattr(asset, "get_path_name", None)
    if callable(get_path_name):
        try:
            object_path = str(get_path_name())
        except Exception:
            object_path = ""
        if object_path:
            return object_path.split(".", 1)[0]

    raw_path_name = getattr(asset, "path_name", None)
    if raw_path_name:
        return str(raw_path_name).split(".", 1)[0]
    return None


def _make_empty_rig_key(unreal):
    key_class = getattr(unreal, "RigElementKey", None)
    if key_class is None:
        return None
    try:
        return key_class()
    except Exception:
        return None


def _rig_element_type(unreal, kind: str):
    element_type = getattr(unreal, "RigElementType", None)
    if element_type is None:
        return None
    candidates = {
        "bone": ("BONE", "Bone"),
        "control": ("CONTROL", "Control"),
    }
    for candidate in candidates.get(kind, ()):
        value = getattr(element_type, candidate, None)
        if value is not None:
            return value
    return None


def _make_rig_key(unreal, *, name: str, kind: str):
    key_class = getattr(unreal, "RigElementKey", None)
    if key_class is None:
        return None
    element_type = _rig_element_type(unreal, kind)
    call_variants = []
    if element_type is not None:
        call_variants.extend(
            [
                (tuple(), {"name": name, "type": element_type}),
                (tuple(), {"name": name, "type_": element_type}),
                ((name, element_type), {}),
                ((element_type, name), {}),
            ]
        )
    call_variants.extend(
        [
            (tuple(), {"name": name}),
            ((name,), {}),
            (tuple(), {}),
        ]
    )
    for args, kwargs in call_variants:
        try:
            key = key_class(*args, **kwargs)
            if key is not None:
                return key
        except Exception:
            continue
    return None


def _hierarchy_contains_key(hierarchy, key) -> bool:
    if key is None:
        return False
    for method_name in ("contains", "contains_element", "contains_key"):
        method = getattr(hierarchy, method_name, None)
        if not callable(method):
            continue
        try:
            return bool(method(key))
        except Exception:
            continue
    return False


def _hierarchy_lookup_key(hierarchy, *, name: Optional[str], kind: str):
    unreal = _load_unreal()
    if not name:
        return _make_empty_rig_key(unreal)

    lookup_methods = {
        "bone": ("get_bone_key", "find_bone", "find_bone_key"),
        "control": ("get_control_key", "find_control", "find_control_key"),
    }
    for method_name in lookup_methods.get(kind, ()):
        method = getattr(hierarchy, method_name, None)
        if not callable(method):
            continue
        try:
            key = method(name)
            if key is not None:
                return key
        except Exception:
            continue

    generic_methods = ("get_key", "find_key", "get_element_key", "find_element_key")
    element_type = _rig_element_type(unreal, kind)
    for method_name in generic_methods:
        method = getattr(hierarchy, method_name, None)
        if not callable(method):
            continue
        call_variants = [((name,), {})]
        if element_type is not None:
            call_variants.extend(
                [
                    ((name, element_type), {}),
                    (tuple(), {"name": name, "type": element_type}),
                    (tuple(), {"name": name, "element_type": element_type}),
                ]
            )
        for args, kwargs in call_variants:
            try:
                key = method(*args, **kwargs)
                if key is not None:
                    return key
            except Exception:
                continue

    return _make_rig_key(unreal, name=name, kind=kind)


def create_control_rig_asset(package_path: str, asset_name: str, skeletal_mesh_path: str) -> str:
    """Create or load a Control Rig asset bound to skeletal mesh."""
    unreal = _load_unreal()
    package = package_path.rstrip("/")
    if not package.startswith("/Game"):
        raise ValueError("package_path must be inside /Game")

    name = _safe_name(asset_name)
    control_rig_path = f"{package}/{name}"

    skeletal_mesh = unreal.EditorAssetLibrary.load_asset(skeletal_mesh_path)
    if skeletal_mesh is None:
        raise RuntimeError(f"Could not load skeletal mesh: {skeletal_mesh_path}")

    # Prefer direct load over existence query to avoid false negatives from
    # transient registry states during editor startup/import churn.
    existing_asset = unreal.EditorAssetLibrary.load_asset(control_rig_path)
    if existing_asset is not None:
        set_preview_mesh = getattr(existing_asset, "set_preview_mesh", None)
        if callable(set_preview_mesh):
            set_preview_mesh(skeletal_mesh)
        unreal.EditorAssetLibrary.save_asset(control_rig_path, only_if_is_dirty=False)
        return control_rig_path

    factory = unreal.ControlRigBlueprintFactory
    skeleton = getattr(skeletal_mesh, "skeleton", None)
    control_rig_asset = None
    last_error: Optional[Exception] = None

    create_new_control_rig_asset = getattr(factory, "create_new_control_rig_asset", None)
    if callable(create_new_control_rig_asset):
        # Support legacy and newer Unreal Python signatures.
        call_variants = [
            (tuple(), {"package_path": package, "asset_name": name, "skeleton": skeleton}),
            ((package, name, skeleton), {}),
            ((control_rig_path,), {}),
            ((control_rig_path, False), {}),
        ]
        for args, kwargs in call_variants:
            try:
                control_rig_asset = create_new_control_rig_asset(*args, **kwargs)
                if control_rig_asset is not None:
                    break
            except Exception as exc:
                last_error = exc

    if control_rig_asset is None:
        create_from_selected = getattr(factory, "create_control_rig_from_skeletal_mesh_or_skeleton", None)
        if callable(create_from_selected):
            selected_candidates = [skeletal_mesh]
            if skeleton is not None:
                selected_candidates.append(skeleton)
            for selected in selected_candidates:
                for args in ((selected, False), (selected,)):
                    try:
                        control_rig_asset = create_from_selected(*args)
                        if control_rig_asset is not None:
                            break
                    except Exception as exc:
                        last_error = exc
                if control_rig_asset is not None:
                    break

    if control_rig_asset is None:
        if last_error is not None:
            raise RuntimeError(
                f"Failed to create Control Rig asset at {control_rig_path}: {last_error}"
            ) from last_error
        raise RuntimeError(f"Failed to create Control Rig asset at {control_rig_path}")

    created_path = _asset_object_path(control_rig_asset)
    final_control_rig_path = control_rig_path
    if created_path and created_path != control_rig_path:
        rename_asset = getattr(unreal.EditorAssetLibrary, "rename_asset", None)
        # Avoid force-delete / replacement flows; they can destabilize some editor sessions.
        if callable(rename_asset) and not unreal.EditorAssetLibrary.does_asset_exist(control_rig_path):
            if rename_asset(created_path, control_rig_path):
                final_control_rig_path = control_rig_path
            else:
                final_control_rig_path = created_path
        else:
            final_control_rig_path = created_path
        control_rig_asset = unreal.EditorAssetLibrary.load_asset(final_control_rig_path) or control_rig_asset

    set_preview_mesh = getattr(control_rig_asset, "set_preview_mesh", None)
    if callable(set_preview_mesh):
        set_preview_mesh(skeletal_mesh)
    unreal.EditorAssetLibrary.save_asset(final_control_rig_path, only_if_is_dirty=False)
    return final_control_rig_path


def _add_bone_if_missing(hierarchy, parent: str, name: str, position: List[float], rotation: List[float]):
    unreal = _load_unreal()
    element_key = _hierarchy_lookup_key(hierarchy, name=name, kind="bone")
    if _hierarchy_contains_key(hierarchy, element_key):
        return

    parent_key = _hierarchy_lookup_key(hierarchy, name=parent, kind="bone") if parent else _make_empty_rig_key(unreal)
    if parent and not _hierarchy_contains_key(hierarchy, parent_key):
        parent_key = _make_empty_rig_key(unreal)
    transform = unreal.Transform(
        location=_vector_from_list(position),
        rotation=_rotator_from_list(rotation).quaternion(),
        scale=unreal.Vector(1.0, 1.0, 1.0),
    )
    hierarchy_controller = hierarchy.get_controller()
    add_bone = getattr(hierarchy_controller, "add_bone", None)
    if not callable(add_bone):
        raise RuntimeError("RigHierarchyController.add_bone is unavailable")

    # Keep call variants explicit and conservative to avoid unstable native marshaling.
    call_variants = [
        (
            tuple(),
            {
                "name": name,
                "parent": parent_key,
                "transform": transform,
                "transform_in_global": True,
                "setup_undo": False,
                "print_python_command": False,
            },
        ),
        (
            tuple(),
            {
                "name": name,
                "parent": parent_key,
                "transform": transform,
                "transform_in_global": True,
            },
        ),
        (
            tuple(),
            {
                "name": name,
                "parent_key": parent_key,
                "transform": transform,
                "transform_in_global": True,
            },
        ),
    ]
    last_error: Optional[Exception] = None
    for args, kwargs in call_variants:
        try:
            add_bone(*args, **kwargs)
            return
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error


def _add_control_if_missing(hierarchy, parent_control: Optional[str], control: Dict[str, Any]):
    unreal = _load_unreal()
    control_name = control["name"]
    key = _hierarchy_lookup_key(hierarchy, name=control_name, kind="control")
    if _hierarchy_contains_key(hierarchy, key):
        return

    parent_key = (
        _hierarchy_lookup_key(hierarchy, name=parent_control, kind="control")
        if parent_control
        else _make_empty_rig_key(unreal)
    )
    if parent_control and not _hierarchy_contains_key(hierarchy, parent_key):
        parent_key = _make_empty_rig_key(unreal)
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
    add_control = getattr(hierarchy_controller, "add_control", None)
    if not callable(add_control):
        raise RuntimeError("RigHierarchyController.add_control is unavailable")

    control_value = unreal.RigControlValue.make_euler_transform(unreal.EulerTransform())
    call_variants = [
        (
            tuple(),
            {
                "name": control_name,
                "parent": parent_key,
                "settings": settings,
                "value": control_value,
                "setup_undo": True,
                "print_python_command": False,
            },
        ),
        (
            tuple(),
            {
                "name": control_name,
                "parent": parent_key,
                "settings": settings,
                "value": control_value,
            },
        ),
        (
            tuple(),
            {
                "name": control_name,
                "parent_key": parent_key,
                "settings": settings,
                "value": control_value,
            },
        ),
    ]
    last_error: Optional[Exception] = None
    for args, kwargs in call_variants:
        try:
            add_control(*args, **kwargs)
            break
        except Exception as exc:
            last_error = exc
    else:
        if last_error is not None:
            raise last_error
        return

    # Note: offset/shape post-mutation calls are intentionally skipped for stability.
    # Some Unreal builds expose variant signatures that can trigger native instability.


def build_control_rig_from_payload(
    control_rig_path: str,
    translated_payload: Dict[str, Any],
    *,
    build_behavior_graph: bool = True,
) -> str:
    """Create hierarchy controls and bones from translated Maya payload."""
    unreal = _load_unreal()
    control_rig = unreal.EditorAssetLibrary.load_asset(control_rig_path)
    if control_rig is None:
        raise RuntimeError(f"Could not load Control Rig asset: {control_rig_path}")

    logger = getattr(unreal, "log", None)
    if callable(logger):
        logger(f"[rigsys] Building Control Rig payload into {control_rig_path}")

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

    if build_behavior_graph:
        graph_result = apply_behavior_graph_to_control_rig(control_rig=control_rig, translated_payload=materialized_payload)
        if callable(logger):
            logger(
                "[rigsys] Graph build result: "
                f"nodes={graph_result.get('nodes_added', 0)} "
                f"links={graph_result.get('links_added', 0)} "
                f"defaults={graph_result.get('defaults_set', 0)} "
                f"warnings={len(graph_result.get('warnings', []))}"
            )
    elif callable(logger):
        logger("[rigsys] Skipping behavior graph build (build_behavior_graph=False)")

    control_rig.request_auto_vm_recompilation()
    unreal.EditorAssetLibrary.save_asset(control_rig_path, only_if_is_dirty=False)
    if callable(logger):
        logger(f"[rigsys] Finished building Control Rig {control_rig_path}")
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
    build_behavior_graph: bool = True,
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
        build_behavior_graph=build_behavior_graph,
    )

    return {
        "payload": str(Path(payload_json_path).expanduser().resolve()),
        "skeletal_mesh": skeletal_mesh_path,
        "control_rig": control_rig_path,
    }
