"""Control Rig translation export module.

This export target writes a rigsys motion-module translation JSON payload that
can be consumed by Unreal Python tooling to build a Control Rig blueprint.
"""

import json
import os

import rigsys.modules.export.exportBase as exportBase
from rigsys.translation.pipeline import build_rig_definition_payload


class ControlRigExport(exportBase.ExportModuleBase):
    """Export module that writes a Control Rig translation payload JSON."""

    def __init__(self, rig, exportPath: str, label: str = "", buildOrder: int = 5000,
                 isMuted: bool = False, mirror: bool = False,
                 includeModuleSettings: bool = True) -> None:
        """Initialize module."""
        super().__init__(rig, exportPath, label, buildOrder, isMuted, mirror)

        self.extension = ".json"
        self.fileName = f"{self._rig.name}_ControlRig"
        if self.checkIfExportPathIsFile(self.exportPath):
            self.fullExportPath = self.exportPath
        else:
            self.fullExportPath = os.path.join(self.exportPath, self.fileName + self.extension)
        self.includeModuleSettings = includeModuleSettings

    def run(self) -> None:
        """Write rig translation JSON payload for Unreal consumption."""
        exportDir = os.path.dirname(self.fullExportPath)
        if not os.path.exists(exportDir):
            os.makedirs(exportDir)

        payload = build_rig_definition_payload(self._rig)
        if not self.includeModuleSettings:
            for module in payload.get("modules", []):
                module.pop("module_settings", None)

        with open(self.fullExportPath, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=4)
