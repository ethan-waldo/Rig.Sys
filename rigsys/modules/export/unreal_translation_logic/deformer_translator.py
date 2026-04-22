"""Deformer module translator dispatcher."""

from .workflow_core import module_name
from .deformer_modules import skin_cluster_import_export


DEFORMER_TRANSLATORS = {
    "skinClusterImportExport": skin_cluster_import_export.translate,
}


def apply_deformer_module(control_rig_bp, module_payload, shared):
    """Apply one deformer module payload via dedicated translator file."""
    module_type = str(module_payload.get("module_type") or "")
    translator = DEFORMER_TRANSLATORS.get(module_type)
    if translator is None:
        name = module_name(module_payload)
        logger = shared.get("log_warning")
        note = f"Unsupported deformer module type '{module_type}'."
        if callable(logger):
            logger(f"[Rig.Sys][Module:{name}] {note}")
        return {"status": "unsupported", "notes": [note]}
    return translator(control_rig_bp, module_payload, shared)
