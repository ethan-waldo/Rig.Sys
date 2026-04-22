"""Base translator interfaces and shared conversion helpers."""

from __future__ import annotations

from abc import ABC
from collections.abc import Iterable
from typing import Any, Dict, List, Optional

from rigsys.translation.models import ControlDefinition, ProxyDefinition, RigModuleDefinition


def _as_list(value: Any, default: Optional[List[float]] = None) -> List[float]:
    """Return value as list with a safe default."""
    if value is None:
        return default[:] if default is not None else []
    return list(value)


class ModuleTranslator(ABC):
    """Base translator for a specific motion module class."""

    module_type = "MotionModuleBase"

    def __init__(self) -> None:
        self._last_warnings: List[str] = []

    def translate(self, module: Any) -> RigModuleDefinition:
        """Translate one rigsys motion module to a serializable definition."""
        self._last_warnings = []
        proxy_lookup = self._build_proxy_lookup(module)
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
            proxies=self.build_proxies(module, proxy_lookup),
            controls=self.build_controls(module, proxy_lookup),
            module_settings=self.build_module_settings(module),
            metadata=self.build_metadata(module),
        )

    def build_metadata(self, module: Any) -> Dict[str, Any]:
        """Return module-specific metadata for Unreal-side builder logic."""
        metadata = {
            "aim_axis": getattr(module, "aimAxis", None),
            "up_axis": getattr(module, "upAxis", None),
            "mirror": bool(getattr(module, "mirror", False)),
            "mirrored": bool(getattr(module, "mirrored", False)),
        }
        if self._last_warnings:
            metadata["translation_warnings"] = list(self._last_warnings)
        return metadata

    def build_module_settings(self, module: Any) -> Dict[str, Any]:
        """Return module settings used by Unreal builder logic."""
        return {
            "ctrl_shape": getattr(module, "ctrlShapes", None),
            "ctrl_scale": _as_list(getattr(module, "ctrlScale", None), [1.0, 1.0, 1.0]),
            "add_offset": bool(getattr(module, "addOffset", False)),
            "add_offsets": bool(getattr(module, "addOffsets", False)),
        }

    def build_controls(self, module: Any, proxy_lookup: Dict[str, Any]) -> List[ControlDefinition]:
        """Return translated controls for this module."""
        controls: List[ControlDefinition] = []
        for proxy in proxy_lookup.values():
            control_name = self.control_name(module, proxy)
            parent_proxy = getattr(proxy, "parent", None)
            controls.append(
                ControlDefinition(
                    name=control_name,
                    shape=self._default_shape(module),
                    scale=_as_list(getattr(module, "ctrlScale", None), [1.0, 1.0, 1.0]),
                    role="fk",
                    position=_as_list(getattr(proxy, "position", None), [0.0, 0.0, 0.0]),
                    rotation=_as_list(getattr(proxy, "rotation", None), [0.0, 0.0, 0.0]),
                    driven_proxy=proxy.name,
                    parent_proxy=parent_proxy,
                    parent_control=self.parent_control_name(module, proxy, proxy_lookup),
                    metadata={"proxy_key": self.find_proxy_key_for_name(proxy_lookup, proxy.name)},
                )
            )
        return controls

    def build_proxies(self, module: Any, proxy_lookup: Dict[str, Any]) -> List[ProxyDefinition]:
        """Return translated proxy list for this module."""
        proxies: List[ProxyDefinition] = []
        for key, proxy in proxy_lookup.items():
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

    def control_name(self, module: Any, proxy: Any) -> str:
        """Return control name for a proxy."""
        return f"{module.getFullName()}_{proxy.name}_CTRL"

    def parent_control_name(self, module: Any, proxy: Any, proxy_lookup: Dict[str, Any]) -> Optional[str]:
        """Return expected parent control name if proxy has a parent."""
        parent_proxy_name = getattr(proxy, "parent", None)
        if not parent_proxy_name:
            return None
        parent_proxy_key = self.find_proxy_key_for_name(proxy_lookup, parent_proxy_name)
        if parent_proxy_key is None:
            return None
        parent_proxy = proxy_lookup[parent_proxy_key]
        return self.control_name(module, parent_proxy)

    def _default_shape(self, module: Any) -> str:
        return str(getattr(module, "ctrlShapes", "circle"))

    def _build_proxy_lookup(self, module: Any) -> Dict[str, Any]:
        proxies = getattr(module, "proxies", {})
        if isinstance(proxies, dict):
            return proxies
        self._last_warnings.append("Module proxies were not a dictionary; exported as empty.")
        return {}

    def find_proxy_key_for_name(self, proxy_lookup: Dict[str, Any], proxy_name: str) -> Optional[str]:
        """Find dictionary key for a given proxy node name."""
        for key, proxy in proxy_lookup.items():
            if getattr(proxy, "name", None) == proxy_name:
                return key
        return None

    def _extract_key_list(self, value: Any) -> List[str]:
        if isinstance(value, dict):
            return list(value.keys())
        if isinstance(value, Iterable):
            return [str(item) for item in value]
        return []
