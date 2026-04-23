"""Unreal entry point script for importing model and auto-building Control Rig.

Run this inside Unreal's Python environment:

    import example.unreal_import_model_and_build_controlrig as script
    script.run(
        payload_json_path="C:/tmp/ExampleRig_controlrig_payload.json",
        model_fbx_path="C:/tmp/ExampleRig.fbx",
        destination_path="/Game/AutoRig",
    )
"""

from __future__ import annotations

from typing import Dict, Optional

from rigsys.translation.unreal_builder import import_model_and_build_control_rig


def run(
    payload_json_path: str,
    model_fbx_path: str,
    destination_path: str = "/Game/AutoRig",
    control_rig_name: Optional[str] = None,
) -> Dict[str, str]:
    """Import FBX model and build Control Rig from translated Maya payload JSON."""
    result = import_model_and_build_control_rig(
        payload_json_path=payload_json_path,
        model_fbx_path=model_fbx_path,
        destination_path=destination_path,
        control_rig_name=control_rig_name,
    )
    print("Control Rig build complete:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return result

