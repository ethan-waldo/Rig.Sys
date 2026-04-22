"""Core helpers used by generated Unreal module translators."""

from typing import Any, Dict, List


def module_name(module_payload: Dict[str, Any]) -> str:
    """Return a readable module name."""
    return str(module_payload.get("module_name") or module_payload.get("module_type") or "Module")


def module_debug_record(module_payload: Dict[str, Any], status: str, notes: List[str] | None = None) -> Dict[str, Any]:
    """Build concise module execution debug payload."""
    return {
        "module_name": module_payload.get("module_name"),
        "module_type": module_payload.get("module_type"),
        "module_class": module_payload.get("module_class"),
        "build_order": module_payload.get("build_order", 0),
        "status": status,
        "notes": notes or [],
        "stats": {
            "joint_count": len(module_payload.get("joints", [])),
            "control_count": len(module_payload.get("controls", [])),
            "constraint_count": len(module_payload.get("constraints", [])),
            "connection_count": len(module_payload.get("connections", [])),
            "custom_attribute_count": len(module_payload.get("custom_control_attributes", [])),
            "rig_logic_node_count": len(module_payload.get("rig_logic_nodes", [])),
            "ik_fk_system_count": len(module_payload.get("ik_fk_systems", [])),
            "rigvm_instruction_count": len(module_payload.get("rigvm_instructions", [])),
        },
    }
