"""Modular rigging system for Autodesk Maya."""


import logging

try:
    from rigsys.api.api_rig import Rig
except ModuleNotFoundError as exc:
    # Allow importing non-Maya utilities from rigsys in environments where maya.cmds is unavailable.
    if exc.name != "maya":
        raise
    Rig = None

logger = logging.getLogger(__name__)

__all__ = ["Rig"]
