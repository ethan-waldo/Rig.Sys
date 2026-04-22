"""Unit tests for Unreal-side control augmentation logic."""

import unittest

from rigsys.translation.unreal_builder import (
    augment_payload_with_generated_controls,
    build_behavior_graph_plan,
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

    def test_fk_generates_segment_driver_controls(self):
        module = {
            "module_name": "M_Spine",
            "module_class": "FK",
            "proxies": [
                {"name": "Start", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "End", "parent": "Start", "position": [0, 9, 0], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "segments": 4,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("M_Spine_SegmentDriver_0_CTRL", generated_names)
        self.assertIn("M_Spine_SegmentDriver_3_CTRL", generated_names)

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

    def test_limb_generates_deform_chain_and_floor_anchor(self):
        module = {
            "module_name": "L_Arm",
            "module_class": "Limb",
            "proxies": [
                {"name": "Root", "parent": None, "position": [0, 10, 0], "rotation": [0, 0, 0]},
                {"name": "Start", "parent": "Root", "position": [0, 9, 0], "rotation": [0, 0, 0]},
                {"name": "Mid", "parent": "Start", "position": [2, 6, 0], "rotation": [0, 0, 0]},
                {"name": "End", "parent": "Mid", "position": [4, 3, 0], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "name_set": {"Root": "Root", "Start": "Start", "Mid": "Mid", "End": "End"},
                "number_of_joints": 5,
                "ik_ctrl_to_floor": True,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("L_Arm_Deform_0_CTRL", generated_names)
        self.assertIn("L_Arm_Deform_4_CTRL", generated_names)
        self.assertIn("L_Arm_IKFloor_CTRL", generated_names)

    def test_hand_generates_explicit_offset_chain_controls(self):
        module = {
            "module_name": "L_Hand",
            "module_class": "Hand",
            "proxies": [
                {"name": "Root", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Finger0_0", "parent": "Root", "position": [1, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Thumb_0", "parent": "Root", "position": [-1, 0, 0], "rotation": [0, 0, 0]},
            ],
            "controls": [
                {
                    "name": "L_Hand_Finger0_0_CTRL",
                    "role": "finger",
                    "shape": "circle",
                    "scale": [1, 1, 1],
                    "position": [1, 0, 0],
                    "rotation": [0, 0, 0],
                    "driven_proxy": "Finger0_0",
                    "parent_proxy": "Root",
                    "parent_control": None,
                },
                {
                    "name": "L_Hand_Thumb_0_CTRL",
                    "role": "thumb",
                    "shape": "circle",
                    "scale": [1, 1, 1],
                    "position": [-1, 0, 0],
                    "rotation": [0, 0, 0],
                    "driven_proxy": "Thumb_0",
                    "parent_proxy": "Root",
                    "parent_control": None,
                },
            ],
            "module_settings": {
                "add_offset": True,
                "meta": True,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("L_Hand_Finger0_0_UpDn_CTRL", generated_names)
        self.assertIn("L_Hand_Finger0_0_Twist_CTRL", generated_names)
        self.assertIn("L_Hand_Finger0_0_Splay_CTRL", generated_names)
        self.assertIn("L_Hand_Thumb_0_UpDn_CTRL", generated_names)
        self.assertIn("L_Hand_Thumb_0_Twist_CTRL", generated_names)
        self.assertIn("L_Hand_Thumb_0_Splay_CTRL", generated_names)

    def test_hand_generates_digit_driver_controls(self):
        module = {
            "module_name": "L_Hand",
            "module_class": "Hand",
            "proxies": [
                {"name": "Root", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Global", "parent": "Root", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Finger0_0", "parent": "Root", "position": [1, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Finger0_1", "parent": "Finger0_0", "position": [2, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Thumb_0", "parent": "Root", "position": [-1, 0, 0], "rotation": [0, 0, 0]},
                {"name": "Thumb_1", "parent": "Thumb_0", "position": [-2, 0, 0], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "number_of_fingers": 1,
                "number_of_finger_joints": 2,
                "number_of_thumb_joints": 2,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("L_Hand_Finger0_Curl_CTRL", generated_names)
        self.assertIn("L_Hand_Finger0_0_Driver_CTRL", generated_names)
        self.assertIn("L_Hand_Finger0_1_Driver_CTRL", generated_names)
        self.assertIn("L_Hand_Thumb_Curl_CTRL", generated_names)
        self.assertIn("L_Hand_Thumb_0_Driver_CTRL", generated_names)

    def test_quad_limb_generates_auto_roll_controls(self):
        module = {
            "module_name": "L_QuadLeg",
            "module_class": "QuadLimb",
            "proxies": [
                {"name": "Root", "parent": None, "position": [0, 12, 0], "rotation": [0, 0, 0]},
                {"name": "Start", "parent": "Root", "position": [1, 10, 0], "rotation": [0, 0, 0]},
                {"name": "UpMid", "parent": "Start", "position": [1, 7, 1], "rotation": [0, 0, 0]},
                {"name": "LoMid", "parent": "UpMid", "position": [1, 4, -1], "rotation": [0, 0, 0]},
                {"name": "End", "parent": "LoMid", "position": [1, 1, 0], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "name_set": {"Root": "Root", "Start": "Start", "UpMid": "UpMid", "LoMid": "LoMid", "End": "End"},
                "curved_calf": True,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("L_QuadLeg_UpperAutoRoll_0_CTRL", generated_names)
        self.assertIn("L_QuadLeg_UpperAutoRoll_2_CTRL", generated_names)
        self.assertIn("L_QuadLeg_LowerAutoRoll_4_CTRL", generated_names)
        self.assertIn("L_QuadLeg_AutoRollSettings_CTRL", generated_names)

    def test_fksegment_generates_ik_rail_controls(self):
        module = {
            "module_name": "M_Tail",
            "module_class": "FKSegment",
            "proxies": [
                {"name": "Start", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "1", "parent": "Start", "position": [0, 3, 0], "rotation": [0, 0, 0]},
                {"name": "2", "parent": "1", "position": [0, 6, 0], "rotation": [0, 0, 0]},
                {"name": "End", "parent": "2", "position": [0, 9, 0], "rotation": [0, 0, 0]},
                {"name": "UpVector", "parent": "Start", "position": [0, 0, -3], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "ik_rail": True,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("M_Tail_IKRail_0_CTRL", generated_names)
        self.assertIn("M_Tail_IKRail_3_CTRL", generated_names)

    def test_ribbon_bind_ik_generates_bind_and_reverse_controls(self):
        module = {
            "module_name": "M_RibbonSpine",
            "module_class": "RibbonBindIK",
            "proxies": [
                {"name": "Start", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "1", "parent": "Start", "position": [0, 2, 0], "rotation": [0, 0, 0]},
                {"name": "End", "parent": "1", "position": [0, 4, 0], "rotation": [0, 0, 0]},
                {"name": "UpVector", "parent": "Start", "position": [0, 0, -2], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "spans": 3,
                "meta": True,
                "reverse": True,
                "number_of_joints": 5,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("M_RibbonSpine_Meta_0_CTRL", generated_names)
        self.assertIn("M_RibbonSpine_Bind_0_CTRL", generated_names)
        self.assertIn("M_RibbonSpine_Bind_4_CTRL", generated_names)
        self.assertIn("M_RibbonSpine_End_RibbonRev_CTRL", generated_names)
        self.assertIn("M_RibbonSpine_Start_RibbonRev_CTRL", generated_names)

    def test_lips_generates_segment_and_jaw_controls(self):
        module = {
            "module_name": "M_Lips",
            "module_class": "Lips",
            "proxies": [
                {"name": "Mouth", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]},
                {"name": "L_CornerLip", "parent": "Mouth", "position": [2, 0, 0], "rotation": [0, 0, 0]},
                {"name": "R_CornerLip", "parent": "Mouth", "position": [-2, 0, 0], "rotation": [0, 0, 0]},
                {"name": "M_UpLip", "parent": "Mouth", "position": [0, 1, 0], "rotation": [0, 0, 0]},
                {"name": "M_LoLip", "parent": "Mouth", "position": [0, -1, 0], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "lip_segments": 3,
                "jaw_target": "jaw_CTRL",
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("M_Lips_UpperSegment_0_CTRL", generated_names)
        self.assertIn("M_Lips_LowerSegment_2_CTRL", generated_names)
        self.assertIn("M_Lips_JawFollow_CTRL", generated_names)

    def test_follicle_eye_generates_segment_attach_and_aim_controls(self):
        module = {
            "module_name": "L_Eye",
            "module_class": "FollicleEye",
            "proxies": [
                {"name": "Eyeball", "parent": None, "position": [1, 2, 3], "rotation": [0, 0, 0]},
                {"name": "In", "parent": "Eyeball", "position": [2, 2, 3], "rotation": [0, 0, 0]},
                {"name": "Out", "parent": "Eyeball", "position": [0, 2, 3], "rotation": [0, 0, 0]},
                {"name": "Up", "parent": "Eyeball", "position": [1, 2.4, 3], "rotation": [0, 0, 0]},
                {"name": "Lo", "parent": "Eyeball", "position": [1, 1.6, 3], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "lid_segments": 2,
                "follicle_surface": "faceSurface",
                "eyeball": True,
                "ctrl_scale": [1, 1, 1],
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("L_Eye_LidUpperSegment_0_CTRL", generated_names)
        self.assertIn("L_Eye_LidLowerSegment_1_CTRL", generated_names)
        self.assertIn("L_Eye_LidAttach_CTRL", generated_names)
        self.assertIn("L_Eye_EyeballAim_CTRL", generated_names)

    def test_axis_guides_generate_from_module_metadata(self):
        module = {
            "module_name": "M_Chest",
            "module_class": "FK",
            "proxies": [
                {"name": "Start", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]},
            ],
            "controls": [],
            "module_settings": {
                "segments": 1,
                "ctrl_scale": [1, 1, 1],
            },
            "metadata": {
                "aim_axis": "+x",
                "up_axis": "-z",
            },
        }
        generated = generate_augmented_controls(module)
        generated_names = {control["name"] for control in generated}

        self.assertIn("M_Chest_AimGuide_CTRL", generated_names)
        self.assertIn("M_Chest_UpGuide_CTRL", generated_names)

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

    def test_graph_plan_generates_link_ops_for_limb_and_point_target(self):
        payload = {
            "rig_name": "GraphRig",
            "modules": [
                {
                    "module_name": "L_Leg",
                    "module_class": "Limb",
                    "proxies": [
                        {"name": "Root", "parent": None, "position": [0, 10, 0], "rotation": [0, 0, 0]},
                        {"name": "Start", "parent": "Root", "position": [0, 10, 0], "rotation": [0, 0, 0]},
                        {"name": "Mid", "parent": "Start", "position": [0, 5, 0], "rotation": [0, 0, 0]},
                        {"name": "End", "parent": "Mid", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                        {"name": "Global", "parent": "End", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                    ],
                    "controls": [
                        {
                            "name": "L_Leg_Start_CTRL",
                            "role": "limb_fk",
                            "shape": "circle",
                            "scale": [1, 1, 1],
                            "position": [0, 10, 0],
                            "rotation": [0, 0, 0],
                            "driven_proxy": "Start",
                            "parent_proxy": "Root",
                        },
                        {
                            "name": "L_Leg_IK_CTRL",
                            "role": "ik_effector",
                            "shape": "circle",
                            "scale": [1, 1, 1],
                            "position": [0, 0, 0],
                            "rotation": [0, 0, 0],
                            "driven_proxy": "End",
                            "parent_proxy": "Mid",
                        },
                    ],
                    "module_settings": {
                        "name_set": {"Root": "Root", "Start": "Start", "Mid": "Mid", "End": "End"},
                        "foot": True,
                    },
                },
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
                        },
                        {
                            "name": "M_Target_Target_0_CTRL",
                            "role": "point_target_reference",
                            "shape": "circle",
                            "scale": [1, 1, 1],
                            "position": [0, 0, 0],
                            "rotation": [0, 0, 0],
                            "driven_proxy": None,
                            "parent_proxy": None,
                            "metadata": {"target_node": "A", "influence": 0.7},
                        },
                        {
                            "name": "M_Target_Target_1_CTRL",
                            "role": "point_target_reference",
                            "shape": "circle",
                            "scale": [1, 1, 1],
                            "position": [0, 0, 0],
                            "rotation": [0, 0, 0],
                            "driven_proxy": None,
                            "parent_proxy": None,
                            "metadata": {"target_node": "B", "influence": 0.3},
                        }
                    ],
                    "module_settings": {
                        "targets": ["A", "B"],
                        "targets_influence": [0.7, 0.3],
                        "constrain_type": "point",
                        "effect_targets": True,
                        "maintain_offset": True,
                    },
                },
            ],
        }

        materialized = augment_payload_with_generated_controls(payload)
        plan = build_behavior_graph_plan(materialized)

        self.assertGreater(len(plan.get("nodes", [])), 0)
        self.assertGreater(len(plan.get("links", [])), 0)
        self.assertGreater(len(plan.get("pin_defaults", [])), 0)
        self.assertTrue(any("SetTransform" in node["struct_path"] for node in plan["nodes"]))
        self.assertTrue(any("GetControlTransform" in node["struct_path"] for node in plan["nodes"]))
        self.assertIsInstance(plan.get("warnings", []), list)

        point_module = next(module for module in plan["modules"] if module["module_name"] == "M_Target")
        self.assertTrue(
            any(
                pin_default["pin_path"].endswith("FWD_Set_1.Weight") and pin_default["value"] == "0.7"
                for pin_default in point_module["pin_defaults"]
            )
        )
        self.assertTrue(
            any(
                '(Type=Bone,Name="A")' in pin_default["value"]
                or '(Type=Bone,Name="B")' in pin_default["value"]
                for pin_default in point_module["pin_defaults"]
                if pin_default["pin_path"].endswith(".Item")
            )
        )
        self.assertIn("forward", plan["stages"])
        self.assertIn("backward", plan["stages"])
        self.assertIn("construction", plan["stages"])
        self.assertGreater(plan["stages"]["forward"]["links"], 0)
        self.assertGreater(plan["stages"]["backward"]["links"], 0)
        self.assertGreater(plan["stages"]["construction"]["links"], 0)
        self.assertTrue(any("source_candidates" in link for link in plan["links"]))
        self.assertTrue(any(link.get("stage") == "forward" for link in plan["links"]))
        self.assertTrue(any(link.get("stage") == "backward" for link in plan["links"]))
        self.assertTrue(any(link.get("stage") == "construction" for link in plan["links"]))
        self.assertTrue(
            any(
                link.get("stage") == "forward" and ".Weight" in str(link.get("target", ""))
                for link in plan["links"]
            )
        )
        self.assertTrue(
            any(
                "pin_path_candidates" in pin_default
                for pin_default in plan["pin_defaults"]
            )
        )
        self.assertGreater(len(plan.get("math_models", [])), 0)
        self.assertTrue(any(model.get("module_class") == "Limb" for model in plan["math_models"]))
        limb_model = next(model for model in plan["math_models"] if model.get("module_class") == "Limb")
        self.assertTrue(any(eq.get("id") == "ik_fk_rotation_blend" for eq in limb_model.get("equations", [])))
        point_model = next(model for model in plan["math_models"] if model.get("module_class") == "PointTarget")
        self.assertEqual(point_model.get("implementation_status"), "implemented")
        self.assertFalse(any("maintain_offset" in gap for gap in point_model.get("approximation_gaps", [])))

    def test_graph_plan_point_target_maintain_offset_and_aim_math_nodes(self):
        payload = {
            "rig_name": "GraphRig",
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
                        },
                        {
                            "name": "M_Target_Target_0_CTRL",
                            "role": "point_target_reference",
                            "shape": "circle",
                            "scale": [1, 1, 1],
                            "position": [0, 0, 0],
                            "rotation": [0, 0, 0],
                            "driven_proxy": None,
                            "parent_proxy": None,
                            "metadata": {"target_node": "A", "influence": 1.0},
                        },
                    ],
                    "metadata": {
                        "aim_axis": "+x",
                        "up_axis": "-z",
                    },
                    "module_settings": {
                        "targets": ["A"],
                        "targets_influence": [1.0],
                        "constrain_type": "aim",
                        "effect_targets": True,
                        "maintain_offset": True,
                    },
                }
            ],
        }
        materialized = augment_payload_with_generated_controls(payload)
        plan = build_behavior_graph_plan(materialized)
        point_module = plan["modules"][0]
        node_structs = [node["struct_path"] for node in point_module["nodes"]]
        node_names = [node["name"] for node in point_module["nodes"]]

        self.assertTrue(any("MathVectorSub" in path for path in node_structs))
        self.assertTrue(any("MathVectorAdd" in path for path in node_structs))
        self.assertTrue(any("AimBone" in path for path in node_structs))
        self.assertTrue(any("_Offset_" in name for name in node_names))
        self.assertTrue(any(link.get("stage") == "construction" for link in point_module["links"]))
        self.assertTrue(
            any(
                pin_default.get("pin_path", "").endswith(".PrimaryAxis")
                and "(X=1.0" in pin_default.get("value", "")
                for pin_default in point_module["pin_defaults"]
            )
        )

        point_model = next(model for model in plan["math_models"] if model.get("module_class") == "PointTarget")
        self.assertEqual(point_model.get("implementation_status"), "implemented")
        self.assertFalse(any("maintain_offset" in gap for gap in point_model.get("approximation_gaps", [])))
        self.assertFalse(any("aim axis" in gap for gap in point_model.get("approximation_gaps", [])))

    def test_graph_plan_hand_generates_operator_network_nodes(self):
        payload = {
            "rig_name": "GraphRig",
            "modules": [
                {
                    "module_name": "L_Hand",
                    "module_class": "Hand",
                    "proxies": [
                        {"name": "Root", "parent": None, "position": [0, 0, 0], "rotation": [0, 0, 0]},
                        {"name": "Global", "parent": "Root", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                        {"name": "Finger0_0", "parent": "Root", "position": [1, 0, 0], "rotation": [0, 0, 0]},
                    ],
                    "controls": [
                        {
                            "name": "L_Hand_Global_CTRL",
                            "role": "hand_global",
                            "shape": "sphere",
                            "scale": [1, 1, 1],
                            "position": [0, 0, 0],
                            "rotation": [0, 0, 0],
                            "driven_proxy": "Global",
                            "parent_proxy": "Root",
                        },
                        {
                            "name": "L_Hand_Finger0_0_CTRL",
                            "role": "finger",
                            "shape": "circle",
                            "scale": [1, 1, 1],
                            "position": [1, 0, 0],
                            "rotation": [0, 0, 0],
                            "driven_proxy": "Finger0_0",
                            "parent_proxy": "Root",
                        },
                    ],
                    "metadata": {
                        "aim_axis": "+x",
                        "up_axis": "-z",
                    },
                    "module_settings": {
                        "add_offset": True,
                    },
                }
            ],
        }
        materialized = augment_payload_with_generated_controls(payload)
        plan = build_behavior_graph_plan(materialized)
        hand_module = plan["modules"][0]
        node_structs = [node["struct_path"] for node in hand_module["nodes"]]

        self.assertTrue(any("MathDoubleMul" in path for path in node_structs))
        self.assertTrue(any("MathDoubleAdd" in path for path in node_structs))
        self.assertTrue(any("MathDoubleNegate" in path for path in node_structs))
        self.assertTrue(any("SetRotation" in path for path in node_structs))
        self.assertTrue(any("SetTranslation" in path for path in node_structs))
        self.assertTrue(any(link.get("stage") == "forward" for link in hand_module["links"]))

        hand_model = next(model for model in plan["math_models"] if model.get("module_class") == "Hand")
        self.assertEqual(hand_model.get("implementation_status"), "implemented")
        self.assertFalse(any("multiplyDivide" in gap for gap in hand_model.get("approximation_gaps", [])))

    def test_graph_plan_limb_foot_roll_generates_operator_nodes(self):
        payload = {
            "rig_name": "GraphRig",
            "modules": [
                {
                    "module_name": "L_Leg",
                    "module_class": "Limb",
                    "proxies": [
                        {"name": "Root", "parent": None, "position": [0, 10, 0], "rotation": [0, 0, 0]},
                        {"name": "Start", "parent": "Root", "position": [0, 10, 0], "rotation": [0, 0, 0]},
                        {"name": "Mid", "parent": "Start", "position": [0, 5, 0], "rotation": [0, 0, 0]},
                        {"name": "End", "parent": "Mid", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                        {"name": "Global", "parent": "End", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                        {"name": "Heel", "parent": "End", "position": [-1, 0, -1], "rotation": [0, 0, 0]},
                        {"name": "OutBank", "parent": "End", "position": [1, 0, 0], "rotation": [0, 0, 0]},
                        {"name": "InBank", "parent": "End", "position": [-1, 0, 0], "rotation": [0, 0, 0]},
                        {"name": "Pivot", "parent": "End", "position": [0, 0, 0], "rotation": [0, 0, 0]},
                        {"name": "Ball", "parent": "Pivot", "position": [0, -0.5, 1], "rotation": [0, 0, 0]},
                        {"name": "Toe", "parent": "Ball", "position": [0, -0.5, 2], "rotation": [0, 0, 0]},
                    ],
                    "controls": [
                        {
                            "name": "L_Leg_IK_CTRL",
                            "role": "ik_effector",
                            "shape": "circle",
                            "scale": [1, 1, 1],
                            "position": [0, 0, 0],
                            "rotation": [0, 0, 0],
                            "driven_proxy": "End",
                            "parent_proxy": "Mid",
                        }
                    ],
                    "module_settings": {
                        "name_set": {"Root": "Root", "Start": "Start", "Mid": "Mid", "End": "End"},
                        "foot": True,
                        "ctrl_scale": [1, 1, 1],
                    },
                }
            ],
        }
        materialized = augment_payload_with_generated_controls(payload)
        plan = build_behavior_graph_plan(materialized)
        limb_module = plan["modules"][0]
        node_structs = [node["struct_path"] for node in limb_module["nodes"]]
        node_names = [node["name"] for node in limb_module["nodes"]]

        self.assertTrue(any("MathDoubleMul" in path for path in node_structs))
        self.assertTrue(any("MathDoubleAdd" in path for path in node_structs))
        self.assertTrue(any("MathDoubleNegate" in path for path in node_structs))
        self.assertTrue(any("_Foot_" in name for name in node_names))
        self.assertTrue(
            any(
                ".Value.X" in str(link.get("target", "")) or ".Value.Z" in str(link.get("target", ""))
                for link in limb_module["links"]
                if link.get("stage") == "forward"
            )
        )

        limb_model = next(model for model in plan["math_models"] if model.get("module_class") == "Limb")
        self.assertEqual(limb_model.get("implementation_status"), "implemented")
        self.assertFalse(any("Foot roll math operators" in gap for gap in limb_model.get("approximation_gaps", [])))

