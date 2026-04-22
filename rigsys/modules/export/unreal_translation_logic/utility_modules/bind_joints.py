"""Translator for Maya BindJoints utility module."""


def translate(control_rig_bp, module_payload, shared):
    """Translate BindJoints through explicit shared callbacks."""
    manifest = shared.build_module_manifest(module_payload)
    shared.apply_constraints(control_rig_bp, manifest)
    shared.apply_rigvm_instructions(control_rig_bp, manifest)
    return shared.translated_result()

