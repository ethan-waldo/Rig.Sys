"""Deformer module translator for generated Unreal script."""

from . import workflow_core


def apply_deformer_module(control_rig_bp, module_payload, shared):
    """Apply deformer module payload through shared per-module path."""
    module_type = str(module_payload.get("module_type") or "")
    if module_type in {"skinClusterImportExport"}:
        return workflow_core.run_shared_payload(control_rig_bp, module_payload, shared)
    return workflow_core.mark_custom_node_required(
        module_payload,
        f"Unsupported deformer module type '{module_type}' requires custom node/plugin workflow.",
    )
