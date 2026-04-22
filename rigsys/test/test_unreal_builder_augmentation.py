"""Unit tests for Unreal-side control augmentation logic."""

import unittest

from rigsys.translation.unreal_builder import (
    augment_payload_with_generated_controls,
    generate_augmented_controls,
)


class TestUnrealBuilderAugmentation(unittest.TestCase):
    """Validate settings->controls expansion for Unreal payload build."""

    def test_fksegment_generates_offsets_and_reverse_controls(self):
        module = {
            "module_name": "L_ArmRail",
            "module_class": "FKSegment",
            "proxies": [
                {"name": "Start", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "1", "parent": "Start", "position": [0, 5, 0], "rotation": [0, 0, 0]},
            ],
            "controls": [
                {
                    "name": "L_ArmRail_Start_CTRL",
                    "role": "fk",
                    "shape": "circle",
                    "scale": [1, 1, 1],
                    "position": [0, 0, 0],
                    "rotation": [0, 0, 0],
                    "driven_proxy": "Start",
                    "parent_proxy": None,
                },
                {
                    "name": "L_ArmRail_1_CTRL",
                    "role": "fk",
                    "shape": "circle",
                    "scale": [1, 1, 1],
                    "position": [0, 5, 0],
                    "rotation": [0, 0, 0],
                    "driven_proxy": "1",
                    "parent_proxy": "Start",
                    "parent_control": "L_ArmRail_Start_CTRL",
                },
            ],
            "module_settings": {
                "add_offset": True,
                "reverse": True,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("L_ArmRail_Start_CTRL_Local", generated_names)
        self.assertIn("L_ArmRail_1_CTRL_Local", generated_names)
        self.assertIn("L_ArmRail_1_Rev_CTRL", generated_names)
        self.assertIn("L_ArmRail_Start_Rev_CTRL", generated_names)

    def test_limb_generates_pv_and_foot_roll_controls(self):
        module = {
            "module_name": "L_Leg",
            "module_class": "Limb",
            "proxies": [
                {"name": "Root", "parent": None, "position": [0, 10, 0], "rotation": [0, 0, 0]},
                {"name": "Start", "parent": "Root", "position": [0, 10, 0], "rotation": [0, 0, 0]},
                {"name": "Mid", "parent": "Start", "position": [0, 5, 2], "rotation": [0, 0, 0]},
                {"name": "End", "parent": "Mid", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Global", "parent": "End", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Heel", "parent": "End", "position": [-1, 0, -1], "rotation": [0, 0, 0]},
                {"name": "OutBank", "parent": "End", "position": [1, 0, 0], "rotation": [0, 0, 0]},
                {"name": "InBank", "parent": "End", "position": [-1, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Pivot", "parent": "End", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Ball", "parent": "Pivot", "position": [0, -0.5, 1], "rotation": [0, 0, 0]},
                {"name": "Toe", "parent": "Ball", "position": [0, -0.5, 2], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "name_set": {"Root": "Root", "Start": "Start", "Mid": "Mid", "End": "End"},
                "pv_multiplier": 1.0,
                "foot": True,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("L_Leg_PV_CTRL", generated_names)
        self.assertIn("L_Leg_Global_Foot_CTRL", generated_names)
        self.assertIn("L_Leg_Toe_Foot_CTRL", generated_names)

    def test_augment_payload_materializes_generated_controls(self):
        payload = {
            "rig_name": "Demo",
            "modules": [
                {
                    "module_name": "M_Target",
                    "module_class": "PointTarget",
                    "proxies": [{"name": "Point", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]}],
                    "controls": [
                        {
                            "name": "M_Target_Point_CTRL",
                            "role": "point_target",
                            "shape": "sphere",
                            "scale": [1, 1, 1],
                            "position": [0, 0, 0],
                            "rotation": [0, 0, 0],
                            "driven_proxy": "Point",
                            "parent_proxy": None,
                        }
                    ],
                    "module_settings": {
                        "targets": ["L_TargetNode", "R_TargetNode"],
                        "targets_influence": [0.75, 0.25],
                        "constrain_type": "point",
                        "ctrl_scale": [1, 1, 1],
                    },
                }
            ],
        }

        materialized = augment_payload_with_generated_controls(payload)
        controls = materialized["modules"][0]["controls"]
        control_names = {control["name"] for control in controls}

        self.assertIn("M_Target_Point_CTRL", control_names)
        self.assertIn("M_Target_Target_0_CTRL", control_names)
        self.assertIn("M_Target_Target_1_CTRL", control_names)
        self.assertEqual(len(controls), 3)

