"""Base class for export modules."""

import os

import rigsys.modules.moduleBase as moduleBase


class ExportModuleBase(moduleBase.ModuleBase):
    """Base class for export modules."""

    def __init__(self, rig, exportPath: str, label: str = "", buildOrder: int = 5000,
                 isMuted: bool = False, mirror: bool = False, extension: str = "",
                 fileNameSuffix: str = "_FBX") -> None:
        """Initialize the module."""
        super().__init__(rig=rig, label=label, buildOrder=buildOrder, isMuted=isMuted, mirror=mirror)

        self.exportPath = exportPath

        self.fileName = f"{self._rig.name}{fileNameSuffix}"
        self.extension = extension
        self.fullExportPath = self._resolveFullExportPath()

    def _resolveFullExportPath(self) -> str:
        """Return absolute export output path for file or directory style inputs."""
        if self.checkIfExportPathIsFile(self.exportPath):
            return self.exportPath
        return os.path.join(self.exportPath, self.fileName + self.extension)

    def setExtension(self, extension: str) -> None:
        """Update extension and refresh resolved output path."""
        self.extension = extension
        self.fullExportPath = self._resolveFullExportPath()

    @staticmethod
    def checkIfExportPathIsFile(path: str) -> bool:
        """Check if the export path is a file.

        This happens by looking at the last element of the path and checking if it has a file extension.

        Arguments:
            path {str} -- Path to check

        Returns:
            bool -- Is the path a file?
        """
        if os.path.splitext(path)[1] == "":
            return False
        else:
            return True
