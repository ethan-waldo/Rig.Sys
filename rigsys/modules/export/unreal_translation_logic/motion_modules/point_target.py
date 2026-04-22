"""Translator for Maya PointTarget motion module."""

from ..workflow_core import run_pipeline_steps, translated_result


def translate(control_rig_bp, module_payload, shared):
    """Translate PointTarget module payload."""
    run_pipeline_steps(control_rig_bp, module_payload, shared)
    return translated_result()
