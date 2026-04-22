"""1:1 translator for Maya skinClusterImportExport deformer module."""

from ..workflow_core import apply_module_payload_explicit, custom_node_required_result


def translate(control_rig_bp, module_payload, shared):
    """Translate skinClusterImportExport deformer payload."""
    apply_module_payload_explicit(control_rig_bp, module_payload, shared)
    return custom_node_required_result("Skin weight import/export pipeline requires custom tooling node on Unreal side.")
