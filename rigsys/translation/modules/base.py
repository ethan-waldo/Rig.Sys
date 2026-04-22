"""Base translator interfaces and shared conversion helpers."""

from __future__ import annotations

from abc import ABC
from collections.abc import Iterable
from typing import Any, Dict, List, Optional

from rigsys.translation.models import (
    ControlDefinition,
    ProxyDefinition,
    RigModuleDefinition,
)


def _as_list(value: Any, default: Optional[List[float]] = None) -> List[float]:
    """Return value as list with a safe default."""
    if value is None:
        return default[:] if default is not None else []
    return list(value)


class ModuleTranslator(ABC):
    """Base translator for a specific motion module class."""

    module_type = "MotionModuleBase"

    def translate(self, module: Any) -> RigModuleDefinition:
        """Translate one rigsys motion module to a serializable definition."""
        return RigModuleDefinition(
            module_name=module.getFullName(),
            module_class=type(module).__name__,
            side=getattr(module, "side", ""),
            label=getattr(module, "label", ""),
            build_order=getattr(module, "buildOrder", 0),
            parent_module=getattr(module, "parent", None),
            selected_plug=getattr(module, "selectedPlug", ""),
            selected_socket=getattr(module, "selectedSocket", ""),
            sockets=self._extract_key_list(getattr(module, "sockets", {})),
            plugs=self._extract_key_list(getattr(module, "plugs", {})),
            proxies=self.build_proxies(module),
            controls=self.build_controls(module),
            metadata=self.build_metadata(module),
        )

    def build_metadata(self, module: Any) -> Dict[str, Any]:
        """Return module-specific metadata for Unreal-side builder logic."""
        return {
            "aim_axis": getattr(module, "aimAxis", None),
            "up_axis": getattr(module, "upAxis", None),
            "mirror": bool(getattr(module, "mirror", False)),
            "mirrored": bool(getattr(module, "mirrored", False)),
        }

    def build_controls(self, module: Any) -> List[ControlDefinition]:
        """Return translated controls for this module."""
        controls: List[ControlDefinition] = []
        for proxy in getattr(module, "proxies", {}).values():
            controls.append(
                ControlDefinition(
                    name=f"{module.getFullName()}_{proxy.name}_CTRL",
                    shape=self._default_shape(module),
                    scale=_as_list(getattr(module, "ctrlScale", None), [1.0, 1.0, 1.0]),
                    role="fk",
                    driven_proxy=proxy.name,
                )
            )
        return controls

    def build_proxies(self, module: Any) -> List[ProxyDefinition]:
        """Return translated proxy list for this module."""
        proxies: List[ProxyDefinition] = []
        for key, proxy in getattr(module, "proxies", {}).items():
            proxies.append(
                ProxyDefinition(
                    key=key,
                    name=getattr(proxy, "name", key),
                    parent=getattr(proxy, "parent", None),
                    position=_as_list(getattr(proxy, "position", None), [0.0, 0.0, 0.0]),
                    rotation=_as_list(getattr(proxy, "rotation", None), [0.0, 0.0, 0.0]),
                    side=getattr(proxy, "side", getattr(module, "side", "")),
                    label=getattr(proxy, "label", getattr(module, "label", "")),
                    up_vector=bool(getattr(proxy, "upVector", False)),
                    is_plug=bool(getattr(proxy, "plug", False)),
                )
            )
        return proxies

    def _default_shape(self, module: Any) -> str:
        return str(getattr(module, "ctrlShapes", "circle"))

    def _extract_key_list(self, value: Any) -> List[str]:
        if isinstance(value, dict):
            return list(value.keys())
        if isinstance(value, Iterable):
            return [str(item) for item in value]
        return []
