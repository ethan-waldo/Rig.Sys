"""Root motion-module translator."""

from ..workflow_core import run_payload_pipeline


def translate(control_rig_bp, module_payload, shared):
    """Translate Root module payload."""
    run_payload_pipeline(control_rig_bp, module_payload, shared)
    return {"status": "translated", "notes": []}
