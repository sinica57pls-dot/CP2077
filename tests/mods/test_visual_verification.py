"""
Visual Verification Test Suite
==============================

Tests for the three visual verification features:
  1. VisualSnapshot  -- capture, compare, and diff entity visual state
  2. SVG Skeleton    -- generate SVG wireframe from rigs
  3. glTF Export     -- export skeleton + scales as glTF 2.0

Mirrors:
  src/App/Entity/VisualScaleEx.cpp    -- visual scale per-component
  src/Red/MorphTarget.hpp             -- morph target application
  modding-guides/npcs/rig-deforming-for-v.md  -- community workflow

Suites:
   1. TestVisualSnapshotCapture       -- capture player/NPC visual state
   2. TestVisualSnapshotToDict        -- serialisation, deep copy
   3. TestVisualSnapshotDiff          -- detect all categories of change
   4. TestSnapshotWithRigChanges      -- rig/morph/scale → snapshot delta
   5. TestSimulationSnapshotHelpers   -- sim.capture_player/npc_snapshot
   6. TestSkeletonHierarchy           -- CP2077_SKELETON integrity
   7. TestSVGGeneration               -- SVG output: structure, colours, labels
   8. TestSVGComparison               -- before/after overlay
   9. TestGLTFExport                  -- valid glTF 2.0 structure
  10. TestGLTFMeshData                -- buffer, accessors, bufferViews
  11. TestGLTFFileOutput              -- write to file, roundtrip
"""

import sys, os, unittest, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation,
    Vector3, Vector4,
    BodyType, BoneTransform, DeformationRig, MorphTargetEntry,
    MeshComponent, entSkinnedMeshComponent,
    entMorphTargetSkinnedMeshComponent,
    Entity, PlayerPuppet, NPCPuppet,
    VisualSnapshot,
    CP2077_SKELETON,
    generate_skeleton_svg,
    generate_skeleton_svg_comparison,
    write_svg,
    export_gltf_json,
)


# =============================================================================
#  1. TestVisualSnapshotCapture
# =============================================================================

class TestVisualSnapshotCapture(unittest.TestCase):
    """Capturing the visual state of entities."""

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0),
                               body_type=BodyType.WomanAverage)

    def tearDown(self):
        self.sim.teardown()

    def test_capture_returns_visual_snapshot(self):
        snap = VisualSnapshot.capture(self.sim.player)
        self.assertIsInstance(snap, VisualSnapshot)

    def test_capture_includes_body_type(self):
        snap = VisualSnapshot.capture(self.sim.player)
        self.assertEqual(snap.to_dict()["body_type"], "woman_average")

    def test_capture_includes_mesh_components(self):
        snap = VisualSnapshot.capture(self.sim.player)
        comps = snap.to_dict()["mesh_components"]
        self.assertGreater(len(comps), 0)
        types = [c["type"] for c in comps]
        self.assertIn("entSkinnedMeshComponent", types)
        self.assertIn("entMorphTargetSkinnedMeshComponent", types)

    def test_capture_includes_visual_scale(self):
        self.sim.set_player_visual_scale(1.5, 1.0, 1.5)
        snap = VisualSnapshot.capture(self.sim.player)
        comps = snap.to_dict()["mesh_components"]
        scales = [c["visual_scale"] for c in comps]
        self.assertIsInstance(scales[0], list)
        self.assertTrue(any(s[0] > 1.4 for s in scales))

    def test_capture_includes_morph_targets(self):
        self.sim.apply_player_morph("BodyFat", "UpperBody", 0.5)
        snap = VisualSnapshot.capture(self.sim.player)
        comps = snap.to_dict()["mesh_components"]
        morph_comp = [c for c in comps if c["morph_targets"]]
        self.assertEqual(len(morph_comp), 1)
        self.assertIn("BodyFat", morph_comp[0]["morph_targets"])

    def test_capture_includes_deformation_rig(self):
        rig = DeformationRig(name="test_rig")
        rig.SetBoneScale("Chest", 1.2, 1.0, 1.1)
        self.sim.apply_deformation_rig(rig)
        snap = VisualSnapshot.capture(self.sim.player)
        rig_data = snap.to_dict()["deformation_rig"]
        self.assertIsNotNone(rig_data)
        self.assertEqual(rig_data["name"], "test_rig")
        self.assertIn("Chest", rig_data["bones"])

    def test_capture_npc_no_rig_fields(self):
        npc = self.sim.spawn_npc(tags=["Test"], pos=(5, 0, 0))
        snap = VisualSnapshot.capture(npc)
        data = snap.to_dict()
        self.assertIsNone(data["body_type"])
        self.assertIsNone(data["deformation_rig"])

    def test_capture_entity_with_no_components(self):
        e = Entity()
        snap = VisualSnapshot.capture(e)
        self.assertEqual(len(snap.to_dict()["mesh_components"]), 0)


# =============================================================================
#  2. TestVisualSnapshotToDict
# =============================================================================

class TestVisualSnapshotToDict(unittest.TestCase):
    """Serialisation and deep-copy behaviour."""

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def test_to_dict_is_json_serializable(self):
        snap = VisualSnapshot.capture(self.sim.player)
        # Must not raise
        result = json.dumps(snap.to_dict())
        self.assertIsInstance(result, str)

    def test_to_dict_returns_deep_copy(self):
        snap = VisualSnapshot.capture(self.sim.player)
        d1 = snap.to_dict()
        d2 = snap.to_dict()
        d1["body_type"] = "MUTATED"
        self.assertNotEqual(d2["body_type"], "MUTATED")

    def test_to_dict_roundtrip_preserves_data(self):
        self.sim.apply_player_morph("BodyFat", "UpperBody", 0.7)
        snap = VisualSnapshot.capture(self.sim.player)
        d = snap.to_dict()
        # Round-trip through JSON
        restored = json.loads(json.dumps(d))
        self.assertEqual(d, restored)

    def test_to_dict_includes_all_fields(self):
        snap = VisualSnapshot.capture(self.sim.player)
        d = snap.to_dict()
        for key in ("body_type", "mesh_components", "deformation_rig",
                     "deformation_rig_fpp"):
            self.assertIn(key, d)


# =============================================================================
#  3. TestVisualSnapshotDiff
# =============================================================================

class TestVisualSnapshotDiff(unittest.TestCase):
    """Detecting all categories of visual change."""

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(body_type=BodyType.WomanAverage)

    def tearDown(self):
        self.sim.teardown()

    def test_identical_snapshots_no_diff(self):
        s1 = VisualSnapshot.capture(self.sim.player)
        s2 = VisualSnapshot.capture(self.sim.player)
        self.assertEqual(s1.diff(s2), {})

    def test_differs_from_returns_false_for_identical(self):
        s1 = VisualSnapshot.capture(self.sim.player)
        s2 = VisualSnapshot.capture(self.sim.player)
        self.assertFalse(s1.differs_from(s2))

    def test_body_type_change_detected(self):
        before = VisualSnapshot.capture(self.sim.player)
        self.sim.set_player_body_type(BodyType.ManAverage)
        after = VisualSnapshot.capture(self.sim.player)
        self.assertTrue(after.differs_from(before))
        diff = after.diff(before)
        self.assertIn("body_type", diff)

    def test_visual_scale_change_detected(self):
        before = VisualSnapshot.capture(self.sim.player)
        self.sim.set_player_visual_scale(2.0, 1.0, 2.0)
        after = VisualSnapshot.capture(self.sim.player)
        self.assertTrue(after.differs_from(before))

    def test_bone_scale_change_detected(self):
        before = VisualSnapshot.capture(self.sim.player)
        rig = DeformationRig(name="bone_test")
        rig.SetBoneScale("Thigh_l", 1.5, 1.0, 1.3)
        self.sim.apply_deformation_rig(rig)
        after = VisualSnapshot.capture(self.sim.player)
        self.assertTrue(after.differs_from(before))
        diff = after.diff(before)
        # Should mention deformation_rig somewhere in the diff keys
        rig_keys = [k for k in diff if "deformation_rig" in k]
        self.assertGreater(len(rig_keys), 0)

    def test_morph_target_change_detected(self):
        before = VisualSnapshot.capture(self.sim.player)
        self.sim.apply_player_morph("BodyFat", "UpperBody", 0.5)
        after = VisualSnapshot.capture(self.sim.player)
        self.assertTrue(after.differs_from(before))

    def test_component_visibility_change_detected(self):
        before = VisualSnapshot.capture(self.sim.player)
        self.sim.player._body_mesh.Toggle(False)
        after = VisualSnapshot.capture(self.sim.player)
        self.assertTrue(after.differs_from(before))

    def test_mesh_path_change_detected(self):
        before = VisualSnapshot.capture(self.sim.player)
        self.sim.player._body_mesh.ChangeResource("custom\\body.mesh")
        after = VisualSnapshot.capture(self.sim.player)
        self.assertTrue(after.differs_from(before))

    def test_multiple_simultaneous_changes(self):
        before = VisualSnapshot.capture(self.sim.player)
        self.sim.set_player_visual_scale(1.2, 1.0, 1.2)
        self.sim.apply_player_morph("MuscleTone", value=0.8)
        rig = DeformationRig(name="multi")
        rig.SetBoneScale("Chest", 1.3, 1.0, 1.2)
        self.sim.apply_deformation_rig(rig)
        after = VisualSnapshot.capture(self.sim.player)
        diff = after.diff(before)
        self.assertGreater(len(diff), 2)

    def test_rig_added_detected(self):
        """Adding a rig where there was none should show a diff."""
        before = VisualSnapshot.capture(self.sim.player)
        self.assertIsNone(before.to_dict()["deformation_rig"])
        rig = DeformationRig(name="new_rig")
        self.sim.apply_deformation_rig(rig)
        after = VisualSnapshot.capture(self.sim.player)
        self.assertTrue(after.differs_from(before))


# =============================================================================
#  4. TestSnapshotWithRigChanges
# =============================================================================

class TestSnapshotWithRigChanges(unittest.TestCase):
    """End-to-end: apply rig/morph/scale, verify snapshot changes."""

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def test_applying_rig_changes_snapshot(self):
        before = self.sim.capture_player_snapshot()
        rig = DeformationRig(name="test")
        rig.SetBoneScaleSymmetric("Thigh_l", 1.3, 1.0, 1.2)
        self.sim.apply_deformation_rig(rig)
        after = self.sim.capture_player_snapshot()
        self.assertTrue(after.differs_from(before))

    def test_applying_morph_changes_snapshot(self):
        before = self.sim.capture_player_snapshot()
        self.sim.apply_player_morph("BodyFat", "UpperBody", 0.5)
        after = self.sim.capture_player_snapshot()
        self.assertTrue(after.differs_from(before))

    def test_applying_visual_scale_changes_snapshot(self):
        before = self.sim.capture_player_snapshot()
        self.sim.set_player_visual_scale(1.5, 1.0, 1.5)
        after = self.sim.capture_player_snapshot()
        self.assertTrue(after.differs_from(before))

    def test_body_type_switch_changes_snapshot(self):
        before = self.sim.capture_player_snapshot()
        self.sim.set_player_body_type(BodyType.ManAverage)
        after = self.sim.capture_player_snapshot()
        self.assertTrue(after.differs_from(before))

    def test_clear_rig_changes_snapshot(self):
        rig = DeformationRig(name="temp")
        rig.SetBoneScale("Chest", 1.2, 1.0, 1.1)
        self.sim.apply_deformation_rig(rig)
        with_rig = self.sim.capture_player_snapshot()
        self.sim.clear_deformation_rig()
        without_rig = self.sim.capture_player_snapshot()
        self.assertTrue(without_rig.differs_from(with_rig))

    def test_full_workflow_snapshot_comparison(self):
        """Full rig-deforming workflow: baseline → modify → verify changed."""
        baseline = self.sim.capture_player_snapshot()

        rig = DeformationRig(name="curvy_v", body_type=BodyType.WomanAverage)
        rig.SetBoneScaleSymmetric("Thigh_l", 1.25, 1.0, 1.15)
        rig.SetBoneScale("Chest", 1.15, 1.0, 1.1)
        self.sim.apply_deformation_rig(rig)
        self.sim.apply_player_morph("BodyFat", "UpperBody", 0.3)
        self.sim.set_player_visual_scale(1.02, 1.0, 1.02)

        modified = self.sim.capture_player_snapshot()
        self.assertTrue(modified.differs_from(baseline))

        diff = modified.diff(baseline)
        self.assertGreater(len(diff), 0)


# =============================================================================
#  5. TestSimulationSnapshotHelpers
# =============================================================================

class TestSimulationSnapshotHelpers(unittest.TestCase):
    """GameSimulation convenience methods for snapshots."""

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def test_capture_player_snapshot(self):
        snap = self.sim.capture_player_snapshot()
        self.assertIsInstance(snap, VisualSnapshot)

    def test_capture_player_snapshot_no_player(self):
        self.sim.end_session()
        self.assertIsNone(self.sim.capture_player_snapshot())

    def test_capture_npc_snapshot(self):
        npc = self.sim.spawn_npc(tags=["Test"], pos=(5, 0, 0))
        snap = self.sim.capture_npc_snapshot(npc)
        self.assertIsInstance(snap, VisualSnapshot)

    def test_capture_npc_with_components(self):
        npc = self.sim.spawn_npc(tags=["Test"], pos=(5, 0, 0))
        self.sim.add_body_mesh_component(npc, mesh_path="test.mesh")
        snap = self.sim.capture_npc_snapshot(npc)
        comps = snap.to_dict()["mesh_components"]
        self.assertGreater(len(comps), 0)

    def test_snapshot_before_after_rig_apply(self):
        before = self.sim.capture_player_snapshot()
        rig = DeformationRig(name="helper_test")
        rig.SetBoneScale("Spine", 1.1, 1.0, 1.1)
        self.sim.apply_deformation_rig(rig)
        after = self.sim.capture_player_snapshot()
        self.assertTrue(after.differs_from(before))


# =============================================================================
#  6. TestSkeletonHierarchy
# =============================================================================

class TestSkeletonHierarchy(unittest.TestCase):
    """CP2077_SKELETON data integrity."""

    def test_skeleton_has_expected_bone_count(self):
        self.assertEqual(len(CP2077_SKELETON), 22)

    def test_all_parents_exist_in_skeleton(self):
        for name, (x, y, parent) in CP2077_SKELETON.items():
            if parent is not None:
                self.assertIn(parent, CP2077_SKELETON,
                              f"{name}'s parent '{parent}' not in skeleton")

    def test_hips_is_root(self):
        _, _, parent = CP2077_SKELETON["Hips"]
        self.assertIsNone(parent)

    def test_bilateral_bones_present(self):
        """Every _l bone should have a matching _r bone."""
        left = [n for n in CP2077_SKELETON if n.endswith("_l")]
        for name in left:
            right = name[:-2] + "_r"
            self.assertIn(right, CP2077_SKELETON,
                          f"{name} has no matching {right}")

    def test_test_bones_all_in_skeleton(self):
        """All bones from test_rig_visual.py should exist in the hierarchy."""
        expected = ["Spine", "Chest", "Hips", "Thigh_l", "Thigh_r",
                    "Calf_l", "Calf_r", "UpperArm_l", "UpperArm_r"]
        for name in expected:
            self.assertIn(name, CP2077_SKELETON)


# =============================================================================
#  7. TestSVGGeneration
# =============================================================================

class TestSVGGeneration(unittest.TestCase):
    """SVG skeleton diagram output."""

    def test_svg_returns_string(self):
        svg = generate_skeleton_svg()
        self.assertIsInstance(svg, str)

    def test_svg_contains_svg_element(self):
        svg = generate_skeleton_svg()
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("xmlns", svg)

    def test_svg_contains_bone_circles(self):
        svg = generate_skeleton_svg()
        self.assertIn("<circle", svg)

    def test_svg_contains_connecting_lines(self):
        svg = generate_skeleton_svg()
        self.assertIn("<line", svg)

    def test_svg_identity_rig_all_green(self):
        """Unmodified rig should have only green (#4CAF50) bones."""
        svg = generate_skeleton_svg(rig=DeformationRig())
        self.assertIn("#4CAF50", svg)
        self.assertNotIn("#FF9800", svg)

    def test_svg_modified_bones_orange(self):
        rig = DeformationRig()
        rig.SetBoneScale("Chest", 1.3, 1.0, 1.2)
        svg = generate_skeleton_svg(rig=rig)
        self.assertIn("#FF9800", svg)

    def test_svg_modified_bones_have_labels(self):
        rig = DeformationRig()
        rig.SetBoneScale("Chest", 1.30, 1.00, 1.20)
        svg = generate_skeleton_svg(rig=rig)
        self.assertIn("Chest:", svg)
        self.assertIn("1.30", svg)

    def test_svg_title_rendered(self):
        svg = generate_skeleton_svg(title="My Custom Title")
        self.assertIn("My Custom Title", svg)


# =============================================================================
#  8. TestSVGComparison
# =============================================================================

class TestSVGComparison(unittest.TestCase):
    """Before/after SVG overlay."""

    def test_comparison_returns_string(self):
        svg = generate_skeleton_svg_comparison(rig_after=DeformationRig())
        self.assertIsInstance(svg, str)

    def test_comparison_before_in_grey(self):
        svg = generate_skeleton_svg_comparison(rig_after=DeformationRig())
        self.assertIn("#9E9E9E", svg)

    def test_comparison_after_in_colour(self):
        rig = DeformationRig()
        rig.SetBoneScale("Chest", 1.3, 1.0, 1.2)
        svg = generate_skeleton_svg_comparison(rig_after=rig)
        self.assertIn("#FF9800", svg)

    def test_comparison_changed_bones_highlighted(self):
        rig = DeformationRig()
        rig.SetBoneScale("Thigh_l", 1.5, 1.0, 1.3)
        svg = generate_skeleton_svg_comparison(
            rig_before=None, rig_after=rig)
        # Red highlight ring
        self.assertIn("#F44336", svg)

    def test_comparison_none_before_uses_identity(self):
        rig = DeformationRig()
        rig.SetBoneScale("Chest", 1.2, 1.0, 1.1)
        svg = generate_skeleton_svg_comparison(
            rig_before=None, rig_after=rig)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)


# =============================================================================
#  9. TestGLTFExport
# =============================================================================

class TestGLTFExport(unittest.TestCase):
    """glTF 2.0 JSON structure validation."""

    def test_gltf_returns_valid_json(self):
        result = export_gltf_json(rig=DeformationRig())
        data = json.loads(result)  # must not raise
        self.assertIsInstance(data, dict)

    def test_gltf_has_asset_version(self):
        data = json.loads(export_gltf_json(rig=DeformationRig()))
        self.assertEqual(data["asset"]["version"], "2.0")
        self.assertEqual(data["asset"]["generator"], "CP2077-Engine-Sim")

    def test_gltf_has_scene_and_nodes(self):
        data = json.loads(export_gltf_json(rig=DeformationRig()))
        self.assertIn("scene", data)
        self.assertIn("scenes", data)
        self.assertIn("nodes", data)

    def test_gltf_node_count_matches_skeleton(self):
        data = json.loads(export_gltf_json(rig=DeformationRig()))
        self.assertEqual(len(data["nodes"]), len(CP2077_SKELETON))

    def test_gltf_bone_scales_from_rig(self):
        rig = DeformationRig()
        rig.SetBoneScale("Chest", 1.3, 1.0, 1.2)
        data = json.loads(export_gltf_json(rig=rig))
        chest_node = next(n for n in data["nodes"] if n["name"] == "Chest")
        self.assertIn("scale", chest_node)
        self.assertAlmostEqual(chest_node["scale"][0], 1.3)
        self.assertAlmostEqual(chest_node["scale"][2], 1.2)

    def test_gltf_identity_bones_no_scale(self):
        """Identity bones should not have an explicit scale property."""
        data = json.loads(export_gltf_json(rig=DeformationRig()))
        head_node = next(n for n in data["nodes"] if n["name"] == "Head")
        self.assertNotIn("scale", head_node)

    def test_gltf_parent_child_hierarchy(self):
        data = json.loads(export_gltf_json(rig=DeformationRig()))
        # Find Hips node and verify it has children
        hips = next(n for n in data["nodes"] if n["name"] == "Hips")
        self.assertIn("children", hips)
        self.assertGreater(len(hips["children"]), 0)

    def test_gltf_includes_mesh_when_requested(self):
        data = json.loads(export_gltf_json(rig=DeformationRig(),
                                            include_mesh=True))
        self.assertIn("meshes", data)
        self.assertEqual(data["meshes"][0]["name"], "BoneCube")


# =============================================================================
#  10. TestGLTFMeshData
# =============================================================================

class TestGLTFMeshData(unittest.TestCase):
    """glTF buffer, accessor, and bufferView validation."""

    def setUp(self):
        self.data = json.loads(export_gltf_json(
            rig=DeformationRig(), include_mesh=True))

    def test_gltf_has_buffer_data_uri(self):
        self.assertIn("buffers", self.data)
        uri = self.data["buffers"][0]["uri"]
        self.assertTrue(uri.startswith("data:application/octet-stream;base64,"))

    def test_gltf_buffer_is_valid_base64(self):
        import base64
        uri = self.data["buffers"][0]["uri"]
        b64_data = uri.split(",", 1)[1]
        decoded = base64.b64decode(b64_data)
        expected_len = self.data["buffers"][0]["byteLength"]
        self.assertEqual(len(decoded), expected_len)

    def test_gltf_has_accessors(self):
        self.assertIn("accessors", self.data)
        self.assertEqual(len(self.data["accessors"]), 2)
        # Index accessor
        self.assertEqual(self.data["accessors"][0]["type"], "SCALAR")
        # Vertex accessor
        self.assertEqual(self.data["accessors"][1]["type"], "VEC3")

    def test_gltf_has_buffer_views(self):
        self.assertIn("bufferViews", self.data)
        self.assertEqual(len(self.data["bufferViews"]), 2)

    def test_gltf_no_mesh_when_disabled(self):
        data = json.loads(export_gltf_json(
            rig=DeformationRig(), include_mesh=False))
        self.assertNotIn("meshes", data)
        self.assertNotIn("buffers", data)


# =============================================================================
#  11. TestGLTFFileOutput
# =============================================================================

class TestGLTFFileOutput(unittest.TestCase):
    """Writing glTF to files."""

    def test_gltf_write_to_file(self):
        rig = DeformationRig(name="file_test")
        rig.SetBoneScale("Spine", 1.1, 1.0, 1.1)
        with tempfile.NamedTemporaryFile(suffix=".gltf", delete=False) as f:
            path = f.name
        try:
            result = export_gltf_json(rig=rig, output_path=path)
            self.assertTrue(os.path.exists(path))
            with open(path, 'r') as f:
                file_content = f.read()
            self.assertEqual(result, file_content)
        finally:
            os.unlink(path)

    def test_gltf_file_is_valid_json(self):
        with tempfile.NamedTemporaryFile(suffix=".gltf", delete=False) as f:
            path = f.name
        try:
            export_gltf_json(rig=DeformationRig(), output_path=path)
            with open(path, 'r') as f:
                data = json.load(f)
            self.assertIn("nodes", data)
        finally:
            os.unlink(path)

    def test_gltf_string_and_file_match(self):
        rig = DeformationRig()
        rig.SetBoneScale("Chest", 1.2, 1.0, 1.1)
        string_result = export_gltf_json(rig=rig)
        with tempfile.NamedTemporaryFile(suffix=".gltf", delete=False) as f:
            path = f.name
        try:
            file_result = export_gltf_json(rig=rig, output_path=path)
            self.assertEqual(string_result, file_result)
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
