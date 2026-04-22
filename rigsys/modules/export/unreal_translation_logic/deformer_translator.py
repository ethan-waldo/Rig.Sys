"""Deformer module translator for generated Unreal script."""


def apply_deformer_module(control_rig_bp, module_payload, shared):
    """Apply deformer module payload through shared per-module path."""
    return shared.apply_module_payload(control_rig_bp, module_payload)
