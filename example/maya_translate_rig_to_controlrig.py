"""Maya script: translate rigsys rig modules to Control Rig payload JSON.

Usage in Maya script editor:
    from example.maya_translate_rig_to_controlrig import run
    run(
        rig_class_path="example.exampleCharacter.ExampleCharacter",
        output_json_path="C:/temp/example_controlrig_payload.json",
        build_rig=False,
    )
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Optional, Tuple

from rigsys.translation.pipeline import export_rig_definition_to_json


def _load_rig_class(rig_module_path: str, rig_class_name: str):
    """Load a Rig subclass from a dotted module path."""
    module = importlib.import_module(rig_module_path)
    rig_class = getattr(module, rig_class_name)
    return rig_class


def _split_rig_class_path(rig_class_path: str) -> Tuple[str, str]:
    """Split dotted class path into module path and class name."""
    if "." not in rig_class_path:
        raise ValueError("rig_class_path must include module and class name.")
    module_path, class_name = rig_class_path.rsplit(".", 1)
    return module_path, class_name


def export_character_payload(
    *,
    rig_module_path: str,
    rig_class_name: str,
    output_json_path: str,
) -> str:
    """Instantiate a rigsys rig class and export its translated payload to JSON."""
    rig_class = _load_rig_class(rig_module_path, rig_class_name)
    rig = rig_class()
    exported_path = export_rig_definition_to_json(rig, output_json_path)
    print(f"[rigsys] Exported translated payload: {exported_path}")
    return exported_path


def run(
    *,
    rig_class_path: str,
    output_json_path: str,
    build_rig: bool = False,
    use_saved_proxy_data: bool = False,
    proxy_data_file: Optional[str] = None,
) -> str:
    """Convenience Maya entry point to build and export translated rig payload."""
    rig_module_path, rig_class_name = _split_rig_class_path(rig_class_path)
    rig_class = _load_rig_class(rig_module_path, rig_class_name)
    rig = rig_class()

    if build_rig:
        build_kwargs = {
            "usedSavedProxyData": use_saved_proxy_data,
        }
        if use_saved_proxy_data:
            if not proxy_data_file:
                raise ValueError("proxy_data_file is required when use_saved_proxy_data is True.")
            build_kwargs["proxyDataFile"] = proxy_data_file
        rig.build(**build_kwargs)

    exported_path = export_rig_definition_to_json(rig, output_json_path)
    print(f"[rigsys] Exported translated payload: {exported_path}")
    return exported_path


if __name__ == "__main__":
    default_output = Path(__file__).resolve().parent / "example_controlrig_payload.json"
    run(
        rig_class_path="example.exampleCharacter.ExampleCharacter",
        output_json_path=str(default_output),
        build_rig=False,
    )
