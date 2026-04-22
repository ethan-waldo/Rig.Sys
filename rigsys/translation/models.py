"""Typed payload models for Maya-to-Control Rig translation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProxyDefinition:
    """Serializable proxy data from a rigsys module."""

    key: str
    name: str
    parent: Optional[str]
    position: List[float]
    rotation: List[float]
    side: str
    label: str
    up_vector: bool = False
    is_plug: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "key": self.key,
            "name": self.name,
            "parent": self.parent,
            "position": self.position,
            "rotation": self.rotation,
            "side": self.side,
            "label": self.label,
            "up_vector": self.up_vector,
            "is_plug": self.is_plug,
        }


@dataclass
class ControlDefinition:
    """Serializable target Control Rig control data."""

    name: str
    shape: str
    scale: List[float]
    role: str
    driven_proxy: Optional[str] = None
    parent_control: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "name": self.name,
            "shape": self.shape,
            "scale": self.scale,
            "role": self.role,
            "driven_proxy": self.driven_proxy,
            "parent_control": self.parent_control,
            "metadata": self.metadata,
        }


@dataclass
class RigModuleDefinition:
    """Serialized definition of one translated motion module."""

    module_name: str
    module_class: str
    side: str
    label: str
    build_order: int
    parent_module: Optional[str]
    selected_plug: str
    selected_socket: str
    sockets: List[str]
    plugs: List[str]
    proxies: List[ProxyDefinition]
    controls: List[ControlDefinition]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "module_name": self.module_name,
            "module_class": self.module_class,
            "side": self.side,
            "label": self.label,
            "build_order": self.build_order,
            "parent_module": self.parent_module,
            "selected_plug": self.selected_plug,
            "selected_socket": self.selected_socket,
            "sockets": self.sockets,
            "plugs": self.plugs,
            "proxies": [proxy.to_dict() for proxy in self.proxies],
            "controls": [control.to_dict() for control in self.controls],
            "metadata": self.metadata,
        }


@dataclass
class RigDefinition:
    """Top-level payload for Unreal-side import and Control Rig build."""

    rig_name: str
    modules: List[RigModuleDefinition]
    format_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "format_version": self.format_version,
            "rig_name": self.rig_name,
            "modules": [module.to_dict() for module in self.modules],
        }
