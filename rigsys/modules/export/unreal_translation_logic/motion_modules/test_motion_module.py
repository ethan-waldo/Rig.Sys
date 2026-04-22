"""Translator for TestMotionModule motion module."""


def translate(control_rig_bp, module_payload, shared):
    """Translate TestMotionModule via shared module payload path."""
    shared["apply_module_payload"](control_rig_bp, module_payload)
    return {"status": "translated", "notes": []}
