"""Unit tests for Maya-to-Control Rig translation pipeline."""

import unittest

from rigsys.translation.pipeline import build_rig_definition_payload


class _FakeProxy:
    def __init__(
        self,
        name,
        position=None,
        rotation=None,
        side="M",
        label="",
        parent=None,
        up_vector=False,
        plug=False,
    ):
        self.name = name
        self.position = position or [0.0, 0.0, 0.0]
        self.rotation = rotation or [0.0, 0.0, 0.0]
        self.side = side
        self.label = label
        self.parent = parent
        self.upVector = up_vector
        self.plug = plug


class Root:
    def __init__(self):
        self.side = "M"
        self.label = "Root"
        self.buildOrder = 100
        self.parent = None
        self.selectedPlug = "Local"
        self.selectedSocket = "Base"
        self.sockets = {"Base": None}
        self.plugs = {"Local": None, "World": None}
        self.proxies = {
            "Root": _FakeProxy(
                name="Base",
                position=[1.0, 2.0, 3.0],
                rotation=[10.0, 20.0, 30.0],
                side="M",
                label="Root",
            )
        }
        self.ctrlShapes = "circle"
        self.ctrlScale = [1.0, 1.0, 1.0]
        self.addOffset = True
        self.aimAxis = "+x"
        self.upAxis = "-z"
        self.mirror = False
        self.mirrored = False

    def getFullName(self):
        return "M_Root"


class TestMotionModule:
    def __init__(self):
        self.side = "L"
        self.label = "Arm"
        self.buildOrder = 200
        self.parent = "M_Root"
        self.selectedPlug = "SomePlug"
        self.selectedSocket = "SomeSocket"
        self.sockets = {"SomeSocket": None}
        self.plugs = {"SomePlug": None}
        self.proxies = {
            "Proxy1": _FakeProxy(
                name="Proxy1",
                position=[4.0, 5.0, 6.0],
                rotation=[0.0, 0.0, 0.0],
                side="L",
                label="Arm",
            )
        }
        self.ctrlShapes = "box"
        self.ctrlScale = [2.0, 2.0, 2.0]
        self.aimAxis = "+x"
        self.upAxis = "-z"
        self.mirror = True
        self.mirrored = False

    def getFullName(self):
        return "L_Arm"


class _FakeRig:
    name = "UnitTestRig"

    def __init__(self):
        self.motionModules = {
            "L_Arm": TestMotionModule(),
            "M_Root": Root(),
        }


class TestTranslationPipeline(unittest.TestCase):
    """Test module translation output payload."""

    def test_translation_payload_structure(self):
        rig = _FakeRig()

        payload = build_rig_definition_payload(rig)

        self.assertEqual(payload["rig_name"], "UnitTestRig")
        self.assertEqual(payload["format_version"], "1.0")
        self.assertEqual([mod["module_name"] for mod in payload["modules"]], ["M_Root", "L_Arm"])

        root = payload["modules"][0]
        self.assertEqual(root["module_class"], "Root")
        self.assertEqual(root["controls"][0]["name"], "M_Root_CTRL")
        self.assertEqual(root["controls"][1]["name"], "M_RootOffset_CTRL")
        self.assertEqual(root["controls"][1]["parent_control"], "M_Root_CTRL")

        arm = payload["modules"][1]
        self.assertEqual(arm["module_class"], "TestMotionModule")
        self.assertEqual(arm["controls"][0]["name"], "L_Arm_Proxy1_CTRL")
        self.assertEqual(arm["controls"][0]["shape"], "box")
        self.assertEqual(arm["metadata"]["mirror"], True)
        self.assertEqual(arm["metadata"]["aim_axis"], "+x")
