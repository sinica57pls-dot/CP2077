"""
Rig & Visual Deformation Test Suite
====================================

Tests V's rig deforming, visual scale, morph targets, and body type switching
against the offline CP2077 engine simulator.

Source: https://github.com/CDPR-Modding-Documentation/Cyberpunk-Modding-Docs/blob/main/modding-guides/npcs/rig-deforming-for-v.md

Mirrors the C++ layer:
  src/App/Entity/VisualScaleEx.cpp    -- Get/SetVisualScale + RefreshAppearance
  src/Red/MorphTarget.hpp             -- Raw::MorphTargetManager::ApplyMorphTarget
  src/App/Entity/EntityEx.cpp         -- Entity::ApplyMorphTarget (component lookup)
  src/App/Entity/ComponentWrapper.hpp -- MorphTargetSkinnedMeshComponent specialisation

Suites:
   1. TestBoneTransform          -- bone data, identity, mirroring, axis swap
   2. TestDeformationRig         -- rig CRUD, symmetric bones, clone, player rig
   3. TestBodyType               -- body type enum, base mesh paths
   4. TestPlayerRigDeformation   -- full workflow: create rig, apply, verify, clear
   5. TestVisualScale            -- per-component and entity-level scale
   6. TestMorphTargets           -- apply, remove, clear, clamp, entity-level
   7. TestMeshComponent          -- resource path, appearance name, refresh, toggle
   8. TestNPCVisualScale         -- NPC entity-level scale via simulation helper
   9. TestBodyTypeSwitching      -- body type change resets rig, updates mesh path
  10. TestSimulationHelpers      -- GameSimulation convenience methods
"""

import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation,
    Vector3, Vector4,
    BodyType, BoneTransform, DeformationRig, MorphTargetEntry,
    MeshComponent, entSkinnedMeshComponent,
    entMorphTargetSkinnedMeshComponent,
    Entity, PlayerPuppet, NPCPuppet,
)


# ═════════════════════════════════════════════════════════════════════════════
#  1. BoneTransform
# ═════════════════════════════════════════════════════════════════════════════

class TestBoneTransform(unittest.TestCase):
    """Unit tests for BoneTransform data class."""

    def test_default_is_identity(self):
        bt = BoneTransform(name="Spine")
        self.assertTrue(bt.is_identity())

    def test_modified_is_not_identity(self):
        bt = BoneTransform(name="Spine", scaleX=1.5)
        self.assertFalse(bt.is_identity())

    def test_as_vector3(self):
        bt = BoneTransform(name="Thigh_l", scaleX=1.2, scaleY=1.1, scaleZ=0.9)
        v = bt.as_vector3()
        self.assertAlmostEqual(v.X, 1.2)
        self.assertAlmostEqual(v.Y, 1.1)
        self.assertAlmostEqual(v.Z, 0.9)

    def test_from_vector3(self):
        bt = BoneTransform.from_vector3("Calf_r", Vector3(0.8, 1.0, 1.3))
        self.assertEqual(bt.name, "Calf_r")
        self.assertAlmostEqual(bt.scaleX, 0.8)
        self.assertAlmostEqual(bt.scaleZ, 1.3)

    def test_mirror_l_to_r(self):
        bt = BoneTransform(name="Thigh_l", scaleX=1.5, scaleY=1.0, scaleZ=1.2)
        m = bt.mirrored()
        self.assertEqual(m.name, "Thigh_r")
        self.assertAlmostEqual(m.scaleX, 1.5)
        self.assertAlmostEqual(m.scaleZ, 1.2)

    def test_mirror_r_to_l(self):
        bt = BoneTransform(name="UpperArm_r", scaleX=0.9)
        m = bt.mirrored()
        self.assertEqual(m.name, "UpperArm_l")

    def test_mirror_no_suffix_returns_same_name(self):
        bt = BoneTransform(name="Spine")
        m = bt.mirrored()
        self.assertEqual(m.name, "Spine")

    def test_blender_axis_swap_note(self):
        """
        Community doc: Z and Y axes in Blender are flipped vs WolvenKit.
        Verify that we can represent a swap manually.
        """
        blender_y, blender_z = 1.3, 0.8
        # In WolvenKit: Y and Z are swapped
        bt = BoneTransform(name="Chest", scaleX=1.0,
                           scaleY=blender_z, scaleZ=blender_y)
        self.assertAlmostEqual(bt.scaleY, 0.8)
        self.assertAlmostEqual(bt.scaleZ, 1.3)


# ═════════════════════════════════════════════════════════════════════════════
#  2. DeformationRig
# ═════════════════════════════════════════════════════════════════════════════

class TestDeformationRig(unittest.TestCase):
    """Tests for the DeformationRig system."""

    def test_empty_rig(self):
        rig = DeformationRig(name="empty", body_type=BodyType.WomanAverage)
        self.assertEqual(rig.GetBoneCount(), 0)
        self.assertEqual(rig.GetModifiedBones(), [])

    def test_set_bone_scale(self):
        rig = DeformationRig(name="test")
        rig.SetBoneScale("Thigh_l", 1.5, 1.0, 1.2)
        bone = rig.GetBoneScale("Thigh_l")
        self.assertIsNotNone(bone)
        self.assertAlmostEqual(bone.scaleX, 1.5)
        self.assertAlmostEqual(bone.scaleZ, 1.2)

    def test_set_bone_symmetric(self):
        rig = DeformationRig(name="sym_test")
        rig.SetBoneScaleSymmetric("Thigh_l", 1.3, 1.0, 1.1)
        self.assertIsNotNone(rig.GetBoneScale("Thigh_l"))
        self.assertIsNotNone(rig.GetBoneScale("Thigh_r"))
        self.assertAlmostEqual(rig.GetBoneScale("Thigh_r").scaleX, 1.3)

    def test_symmetric_spine_no_duplicate(self):
        """Spine has no _l/_r suffix -- symmetric should still work."""
        rig = DeformationRig(name="spine_test")
        rig.SetBoneScaleSymmetric("Spine", 1.0, 1.0, 1.5)
        self.assertEqual(rig.GetBoneCount(), 1)

    def test_get_modified_bones_excludes_identity(self):
        rig = DeformationRig()
        rig.SetBoneScale("Thigh_l", 1.0, 1.0, 1.0)  # identity
        rig.SetBoneScale("Calf_l", 1.2, 1.0, 1.0)    # modified
        mods = rig.GetModifiedBones()
        self.assertEqual(len(mods), 1)
        self.assertEqual(mods[0].name, "Calf_l")

    def test_clear_bone(self):
        rig = DeformationRig()
        rig.SetBoneScale("Thigh_l", 1.5, 1.0, 1.0)
        rig.ClearBone("Thigh_l")
        self.assertIsNone(rig.GetBoneScale("Thigh_l"))

    def test_reset_clears_all(self):
        rig = DeformationRig()
        rig.SetBoneScale("A", 1.5, 1.0, 1.0)
        rig.SetBoneScale("B", 1.0, 1.5, 1.0)
        rig.Reset()
        self.assertEqual(rig.GetBoneCount(), 0)

    def test_clone_is_independent(self):
        rig = DeformationRig(name="original", body_type=BodyType.ManAverage)
        rig.SetBoneScale("Thigh_l", 1.5, 1.0, 1.0)
        clone = rig.Clone("variant")
        clone.SetBoneScale("Thigh_l", 2.0, 1.0, 1.0)
        # Original untouched
        self.assertAlmostEqual(rig.GetBoneScale("Thigh_l").scaleX, 1.5)
        self.assertAlmostEqual(clone.GetBoneScale("Thigh_l").scaleX, 2.0)
        self.assertEqual(clone.name, "variant")

    def test_make_player_rig(self):
        rig = DeformationRig(name="body_tpp")
        rig.SetBoneScale("Chest", 1.2, 1.0, 1.0)
        fpp = rig.MakePlayerRig()
        self.assertTrue(fpp._is_player_rig)
        self.assertEqual(fpp.name, "body_tpp_fpp")
        self.assertAlmostEqual(fpp.GetBoneScale("Chest").scaleX, 1.2)

    def test_get_all_bones(self):
        rig = DeformationRig()
        rig.SetBoneScaleSymmetric("Thigh_l", 1.2, 1.0, 1.0)
        all_bones = rig.GetAllBones()
        self.assertIn("Thigh_l", all_bones)
        self.assertIn("Thigh_r", all_bones)


# ═════════════════════════════════════════════════════════════════════════════
#  3. BodyType
# ═════════════════════════════════════════════════════════════════════════════

class TestBodyType(unittest.TestCase):
    """Body type enum and base mesh path resolution."""

    def test_woman_average_value(self):
        self.assertEqual(BodyType.WomanAverage.value, "woman_average")

    def test_man_average_value(self):
        self.assertEqual(BodyType.ManAverage.value, "man_average")

    def test_man_big_value(self):
        self.assertEqual(BodyType.ManBig.value, "man_big")

    def test_woman_average_mesh_path(self):
        sim = GameSimulation()
        sim.start_session(body_type=BodyType.WomanAverage)
        self.assertIn("woman_average", sim.player._body_mesh._mesh_path)
        self.assertIn("t0_000_wa_base__full.mesh", sim.player._body_mesh._mesh_path)
        sim.teardown()

    def test_man_average_mesh_path(self):
        sim = GameSimulation()
        sim.start_session(body_type=BodyType.ManAverage)
        self.assertIn("man_average", sim.player._body_mesh._mesh_path)
        self.assertIn("t0_000_ma_base__full.mesh", sim.player._body_mesh._mesh_path)
        sim.teardown()

    def test_man_big_mesh_path(self):
        sim = GameSimulation()
        sim.start_session(body_type=BodyType.ManBig)
        self.assertIn("man_big", sim.player._body_mesh._mesh_path)
        sim.teardown()


# ═════════════════════════════════════════════════════════════════════════════
#  4. PlayerRigDeformation (full workflow)
# ═════════════════════════════════════════════════════════════════════════════

class TestPlayerRigDeformation(unittest.TestCase):
    """
    End-to-end rig deformation workflow matching the community guide:
      1. Create rig with bone scale modifications
      2. Apply symmetric bones (both _l and _r)
      3. Install on player (auto-creates FPP variant)
      4. Verify both TPP and FPP rigs are installed
      5. Clear rig and verify reset
    """

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0),
                               body_type=BodyType.WomanAverage)

    def tearDown(self):
        self.sim.teardown()

    def test_apply_rig_installs_tpp(self):
        rig = DeformationRig(name="curvy", body_type=BodyType.WomanAverage)
        rig.SetBoneScaleSymmetric("Thigh_l", 1.3, 1.0, 1.2)
        self.sim.apply_deformation_rig(rig)
        installed = self.sim.player.GetDeformationRig()
        self.assertIsNotNone(installed)
        self.assertEqual(installed.name, "curvy")

    def test_apply_rig_auto_creates_fpp(self):
        rig = DeformationRig(name="wide", body_type=BodyType.WomanAverage)
        rig.SetBoneScale("Chest", 1.4, 1.0, 1.2)
        self.sim.apply_deformation_rig(rig, auto_fpp=True)
        fpp = self.sim.player.GetDeformationRigFPP()
        self.assertIsNotNone(fpp)
        self.assertTrue(fpp._is_player_rig)
        self.assertEqual(fpp.name, "wide_fpp")

    def test_apply_rig_no_auto_fpp(self):
        rig = DeformationRig(name="tpp_only")
        self.sim.apply_deformation_rig(rig, auto_fpp=False)
        self.assertIsNotNone(self.sim.player.GetDeformationRig())
        self.assertIsNone(self.sim.player.GetDeformationRigFPP())

    def test_clear_rig(self):
        rig = DeformationRig(name="temp")
        self.sim.apply_deformation_rig(rig)
        self.sim.clear_deformation_rig()
        self.assertIsNone(self.sim.player.GetDeformationRig())
        self.assertIsNone(self.sim.player.GetDeformationRigFPP())

    def test_rig_bones_survive_install(self):
        """Bone modifications should be readable after install."""
        rig = DeformationRig(name="muscular")
        rig.SetBoneScaleSymmetric("UpperArm_l", 1.4, 1.2, 1.3)
        self.sim.apply_deformation_rig(rig)
        installed = self.sim.player.GetDeformationRig()
        bone = installed.GetBoneScale("UpperArm_l")
        self.assertIsNotNone(bone)
        self.assertAlmostEqual(bone.scaleX, 1.4)
        mirror = installed.GetBoneScale("UpperArm_r")
        self.assertIsNotNone(mirror)
        self.assertAlmostEqual(mirror.scaleX, 1.4)

    def test_replace_rig_overwrites(self):
        rig1 = DeformationRig(name="v1")
        rig2 = DeformationRig(name="v2")
        self.sim.apply_deformation_rig(rig1)
        self.sim.apply_deformation_rig(rig2)
        self.assertEqual(self.sim.player.GetDeformationRig().name, "v2")

    def test_apply_triggers_refresh(self):
        """Installing a rig should trigger RefreshAppearance on body mesh."""
        self.sim.player._body_mesh._appearance_refreshed = False
        rig = DeformationRig(name="refresh_test")
        self.sim.apply_deformation_rig(rig)
        self.assertTrue(self.sim.player._body_mesh._appearance_refreshed)

    def test_workflow_leaf_bones_only(self):
        """
        From the guide: 'Generally you want to scale bones that do not
        effect other bones. Joints, or those parenting other bones can
        break the mesh in game.'
        Verify leaf bones (Thigh, Calf, UpperArm, Chest) work correctly.
        """
        rig = DeformationRig(name="safe_bones", body_type=BodyType.WomanAverage)
        leaf_bones = [
            ("Thigh_l", 1.2, 1.0, 1.1),
            ("Calf_l", 0.9, 1.0, 0.9),
            ("UpperArm_l", 1.3, 1.1, 1.2),
            ("Chest", 1.1, 1.0, 1.2),
        ]
        for name, sx, sy, sz in leaf_bones:
            rig.SetBoneScaleSymmetric(name, sx, sy, sz)
        self.sim.apply_deformation_rig(rig)
        installed = self.sim.player.GetDeformationRig()
        # 4 bones with _l, 3 with auto-mirrored _r (Chest has no suffix)
        self.assertEqual(installed.GetBoneCount(), 7)
        modified = installed.GetModifiedBones()
        self.assertEqual(len(modified), 7)


# ═════════════════════════════════════════════════════════════════════════════
#  5. VisualScale
# ═════════════════════════════════════════════════════════════════════════════

class TestVisualScale(unittest.TestCase):
    """
    Tests Get/SetVisualScale matching VisualScaleEx.cpp.
    SetVisualScale must call RefreshAppearance() automatically.
    """

    def test_default_scale_is_identity(self):
        mc = MeshComponent()
        v = mc.GetVisualScale()
        self.assertAlmostEqual(v.X, 1.0)
        self.assertAlmostEqual(v.Y, 1.0)
        self.assertAlmostEqual(v.Z, 1.0)

    def test_set_visual_scale(self):
        mc = MeshComponent()
        mc.SetVisualScale(Vector3(2.0, 1.5, 0.5))
        v = mc.GetVisualScale()
        self.assertAlmostEqual(v.X, 2.0)
        self.assertAlmostEqual(v.Y, 1.5)
        self.assertAlmostEqual(v.Z, 0.5)

    def test_set_triggers_refresh(self):
        """VisualScaleEx.cpp: SetVisualScale calls RefreshAppearance."""
        mc = MeshComponent()
        mc._appearance_refreshed = False
        mc.SetVisualScale(Vector3(1.5, 1.0, 1.0))
        self.assertTrue(mc._appearance_refreshed)

    def test_get_returns_copy(self):
        """GetVisualScale should return a copy, not a reference."""
        mc = MeshComponent()
        v1 = mc.GetVisualScale()
        v1.X = 99.0
        v2 = mc.GetVisualScale()
        self.assertAlmostEqual(v2.X, 1.0)

    def test_skinned_mesh_inherits_scale(self):
        smc = entSkinnedMeshComponent()
        smc.SetVisualScale(Vector3(1.2, 1.0, 1.2))
        v = smc.GetVisualScale()
        self.assertAlmostEqual(v.X, 1.2)

    def test_morph_target_mesh_inherits_scale(self):
        mtc = entMorphTargetSkinnedMeshComponent()
        mtc.SetVisualScale(Vector3(0.8, 1.0, 0.8))
        v = mtc.GetVisualScale()
        self.assertAlmostEqual(v.X, 0.8)

    def test_entity_level_set_visual_scale(self):
        """Entity.SetVisualScale sets all mesh components."""
        e = Entity()
        mc1 = MeshComponent()
        mc2 = entSkinnedMeshComponent()
        e.AddComponent(mc1)
        e.AddComponent(mc2)
        result = e.SetVisualScale(Vector3(1.5, 1.5, 1.5))
        self.assertTrue(result)
        self.assertAlmostEqual(mc1.GetVisualScale().X, 1.5)
        self.assertAlmostEqual(mc2.GetVisualScale().X, 1.5)

    def test_entity_level_get_visual_scale(self):
        e = Entity()
        mc = MeshComponent()
        mc.SetVisualScale(Vector3(2.0, 2.0, 2.0))
        e.AddComponent(mc)
        v = e.GetVisualScale()
        self.assertIsNotNone(v)
        self.assertAlmostEqual(v.X, 2.0)

    def test_entity_no_mesh_returns_none(self):
        e = Entity()
        self.assertIsNone(e.GetVisualScale())

    def test_entity_no_mesh_set_returns_false(self):
        e = Entity()
        self.assertFalse(e.SetVisualScale(Vector3(1.5, 1.5, 1.5)))


# ═════════════════════════════════════════════════════════════════════════════
#  6. MorphTargets
# ═════════════════════════════════════════════════════════════════════════════

class TestMorphTargets(unittest.TestCase):
    """
    Tests morph target system matching Raw::MorphTargetManager::ApplyMorphTarget.
    """

    def test_apply_morph_target(self):
        mtc = entMorphTargetSkinnedMeshComponent()
        result = mtc.ApplyMorphTarget("BodyFat", "UpperBody", 0.5)
        self.assertTrue(result)
        entry = mtc.GetMorphTarget("BodyFat")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.target, "BodyFat")
        self.assertEqual(entry.region, "UpperBody")
        self.assertAlmostEqual(entry.value, 0.5)

    def test_morph_value_clamped_to_0_1(self):
        mtc = entMorphTargetSkinnedMeshComponent()
        mtc.ApplyMorphTarget("Oversize", value=2.5)
        self.assertAlmostEqual(mtc.GetMorphTargetValue("Oversize"), 1.0)
        mtc.ApplyMorphTarget("Undersize", value=-0.5)
        self.assertAlmostEqual(mtc.GetMorphTargetValue("Undersize"), 0.0)

    def test_remove_morph_target(self):
        mtc = entMorphTargetSkinnedMeshComponent()
        mtc.ApplyMorphTarget("BodyFat", value=0.5)
        result = mtc.RemoveMorphTarget("BodyFat")
        self.assertTrue(result)
        self.assertIsNone(mtc.GetMorphTarget("BodyFat"))

    def test_remove_nonexistent_returns_false(self):
        mtc = entMorphTargetSkinnedMeshComponent()
        self.assertFalse(mtc.RemoveMorphTarget("Nonexistent"))

    def test_clear_all_morphs(self):
        mtc = entMorphTargetSkinnedMeshComponent()
        mtc.ApplyMorphTarget("A", value=0.1)
        mtc.ApplyMorphTarget("B", value=0.2)
        mtc.ApplyMorphTarget("C", value=0.3)
        mtc.ClearMorphTargets()
        self.assertEqual(len(mtc.GetAppliedMorphTargets()), 0)

    def test_get_applied_morphs(self):
        mtc = entMorphTargetSkinnedMeshComponent()
        mtc.ApplyMorphTarget("BodyFat", "UpperBody", 0.5)
        mtc.ApplyMorphTarget("MuscleTone", "UpperBody", 0.8)
        morphs = mtc.GetAppliedMorphTargets()
        self.assertEqual(len(morphs), 2)

    def test_overwrite_existing_morph(self):
        mtc = entMorphTargetSkinnedMeshComponent()
        mtc.ApplyMorphTarget("BodyFat", value=0.3)
        mtc.ApplyMorphTarget("BodyFat", value=0.9)
        self.assertAlmostEqual(mtc.GetMorphTargetValue("BodyFat"), 0.9)
        self.assertEqual(len(mtc.GetAppliedMorphTargets()), 1)

    def test_morph_triggers_refresh(self):
        mtc = entMorphTargetSkinnedMeshComponent()
        mtc._appearance_refreshed = False
        mtc.ApplyMorphTarget("Test", value=0.5)
        self.assertTrue(mtc._appearance_refreshed)

    def test_entity_apply_morph_target(self):
        """Entity.ApplyMorphTarget mirrors EntityEx.cpp: find component, apply."""
        e = Entity()
        mtc = entMorphTargetSkinnedMeshComponent()
        e.AddComponent(mtc)
        result = e.ApplyMorphTarget("FaceFat", "Head", 0.7)
        self.assertTrue(result)
        self.assertAlmostEqual(mtc.GetMorphTargetValue("FaceFat"), 0.7)

    def test_entity_apply_morph_no_component(self):
        """Entity without morph component returns False."""
        e = Entity()
        e.AddComponent(MeshComponent())
        self.assertFalse(e.ApplyMorphTarget("Anything"))

    def test_morph_resource_path(self):
        """MorphTarget component uses morphResource, not mesh."""
        mtc = entMorphTargetSkinnedMeshComponent()
        mtc.SetMorphResourcePath("base\\morph\\body_fat.morphtarget")
        self.assertEqual(mtc.GetMorphResourcePath(),
                         "base\\morph\\body_fat.morphtarget")

    def test_player_body_morph(self):
        """Player convenience: ApplyBodyMorphTarget."""
        sim = GameSimulation()
        sim.start_session()
        result = sim.apply_player_morph("BodyFat", "UpperBody", 0.6)
        self.assertTrue(result)
        morphs = sim.player.GetBodyMorphTargets()
        self.assertEqual(len(morphs), 1)
        self.assertEqual(morphs[0].target, "BodyFat")
        self.assertAlmostEqual(morphs[0].value, 0.6)
        sim.teardown()


# ═════════════════════════════════════════════════════════════════════════════
#  7. MeshComponent (resource path, appearance name, toggle)
# ═════════════════════════════════════════════════════════════════════════════

class TestMeshComponent(unittest.TestCase):
    """Tests for MeshComponent API surface."""

    def test_default_visibility(self):
        mc = MeshComponent()
        self.assertTrue(mc._visible)
        self.assertFalse(mc._temp_hidden)

    def test_toggle_visibility(self):
        mc = MeshComponent()
        mc.Toggle(False)
        self.assertFalse(mc._visible)
        mc.Toggle(True)
        self.assertTrue(mc._visible)

    def test_temporary_hide(self):
        mc = MeshComponent()
        mc.TemporaryHide(True)
        self.assertTrue(mc._temp_hidden)

    def test_change_resource(self):
        mc = MeshComponent()
        mc.ChangeResource("base\\meshes\\custom.mesh")
        self.assertEqual(mc.GetResourcePath(), "base\\meshes\\custom.mesh")

    def test_set_appearance_name(self):
        mc = MeshComponent()
        mc.SetAppearanceName("battle_worn")
        self.assertEqual(str(mc.GetAppearanceName()), "battle_worn")

    def test_set_appearance_triggers_refresh(self):
        mc = MeshComponent()
        mc._appearance_refreshed = False
        mc.SetAppearanceName("new_look")
        self.assertTrue(mc._appearance_refreshed)

    def test_refresh_appearance_flag(self):
        mc = MeshComponent()
        mc._appearance_refreshed = False
        mc.RefreshAppearance()
        self.assertTrue(mc._appearance_refreshed)

    def test_find_components_by_type(self):
        e = Entity()
        mc1 = MeshComponent()
        mc2 = entSkinnedMeshComponent()
        mc3 = entMorphTargetSkinnedMeshComponent()
        e.AddComponent(mc1)
        e.AddComponent(mc2)
        e.AddComponent(mc3)
        # All three are MeshComponents
        found = e.FindComponentsByType("MeshComponent")
        self.assertEqual(len(found), 3)
        # Only one is morph target
        morph = e.FindComponentsByType("entMorphTargetSkinnedMeshComponent")
        self.assertEqual(len(morph), 1)


# ═════════════════════════════════════════════════════════════════════════════
#  8. NPC Visual Scale
# ═════════════════════════════════════════════════════════════════════════════

class TestNPCVisualScale(unittest.TestCase):
    """Tests for NPC entity-level visual scale."""

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_npc_set_visual_scale(self):
        npc = self.sim.spawn_npc(tags=["Test"], pos=(5, 0, 0))
        mc = entSkinnedMeshComponent()
        npc.AddComponent(mc)
        self.sim.set_npc_visual_scale(npc, 1.5, 1.0, 1.5)
        v = mc.GetVisualScale()
        self.assertAlmostEqual(v.X, 1.5)
        self.assertAlmostEqual(v.Z, 1.5)

    def test_npc_add_morph_component(self):
        npc = self.sim.spawn_npc(tags=["Test"], pos=(5, 0, 0))
        comp = self.sim.add_body_mesh_component(npc, morph=True)
        self.assertIsInstance(comp, entMorphTargetSkinnedMeshComponent)
        found = npc.FindComponentByType("entMorphTargetSkinnedMeshComponent")
        self.assertIs(found, comp)

    def test_npc_add_skinned_component(self):
        npc = self.sim.spawn_npc(tags=["Test"], pos=(5, 0, 0))
        comp = self.sim.add_body_mesh_component(npc,
                                                 mesh_path="base\\custom.mesh")
        self.assertIsInstance(comp, entSkinnedMeshComponent)
        self.assertEqual(comp.GetResourcePath(), "base\\custom.mesh")


# ═════════════════════════════════════════════════════════════════════════════
#  9. BodyTypeSwitching
# ═════════════════════════════════════════════════════════════════════════════

class TestBodyTypeSwitching(unittest.TestCase):
    """
    Switching body type should:
      - Update the base body mesh path
      - Reset any active deformation rig (it's body-type-specific)
      - Trigger RefreshAppearance
    """

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0),
                               body_type=BodyType.WomanAverage)

    def tearDown(self):
        self.sim.teardown()

    def test_switch_to_man_average(self):
        self.sim.set_player_body_type(BodyType.ManAverage)
        self.assertEqual(self.sim.player.GetBodyType(), BodyType.ManAverage)
        self.assertIn("man_average", self.sim.player._body_mesh._mesh_path)

    def test_switch_resets_rig(self):
        rig = DeformationRig(name="old_rig")
        self.sim.apply_deformation_rig(rig)
        self.assertIsNotNone(self.sim.player.GetDeformationRig())
        self.sim.set_player_body_type(BodyType.ManBig)
        self.assertIsNone(self.sim.player.GetDeformationRig())
        self.assertIsNone(self.sim.player.GetDeformationRigFPP())

    def test_switch_triggers_refresh(self):
        self.sim.player._body_mesh._appearance_refreshed = False
        self.sim.set_player_body_type(BodyType.ManAverage)
        self.assertTrue(self.sim.player._body_mesh._appearance_refreshed)

    def test_start_session_with_body_type(self):
        """GameSimulation.start_session accepts body_type parameter."""
        sim2 = GameSimulation()
        sim2.start_session(body_type=BodyType.ManBig)
        self.assertEqual(sim2.player.GetBodyType(), BodyType.ManBig)
        self.assertIn("man_big", sim2.player._body_mesh._mesh_path)
        sim2.teardown()

    def test_default_body_type_is_woman_average(self):
        sim2 = GameSimulation()
        sim2.start_session()
        self.assertEqual(sim2.player.GetBodyType(), BodyType.WomanAverage)
        sim2.teardown()


# ═════════════════════════════════════════════════════════════════════════════
#  10. Simulation Helpers
# ═════════════════════════════════════════════════════════════════════════════

class TestSimulationHelpers(unittest.TestCase):
    """Tests for GameSimulation visual/rig convenience methods."""

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_set_and_get_player_visual_scale(self):
        self.sim.set_player_visual_scale(1.2, 1.0, 1.3)
        v = self.sim.get_player_visual_scale()
        self.assertAlmostEqual(v.X, 1.2)
        self.assertAlmostEqual(v.Y, 1.0)
        self.assertAlmostEqual(v.Z, 1.3)

    def test_visual_scale_no_player_returns_none(self):
        self.sim.end_session()
        v = self.sim.get_player_visual_scale()
        self.assertIsNone(v)

    def test_player_has_body_components(self):
        """Player should have body mesh + morph target components by default."""
        comps = self.sim.player.GetComponents()
        types = [type(c).__name__ for c in comps]
        self.assertIn("entSkinnedMeshComponent", types)
        self.assertIn("entMorphTargetSkinnedMeshComponent", types)

    def test_player_body_visual_scale(self):
        """SetBodyVisualScale should update both body mesh and morph."""
        self.sim.player.SetBodyVisualScale(Vector3(1.3, 1.1, 1.3))
        mesh_scale = self.sim.player._body_mesh.GetVisualScale()
        morph_scale = self.sim.player._body_morph.GetVisualScale()
        self.assertAlmostEqual(mesh_scale.X, 1.3)
        self.assertAlmostEqual(morph_scale.X, 1.3)

    def test_full_rig_deform_workflow(self):
        """
        End-to-end test mirroring the community rig-deforming guide:
          1. Start with female V
          2. Create a deformation rig with bilateral bone scales
          3. Install it (auto FPP)
          4. Also apply morph targets
          5. Set visual scale
          6. Verify everything is in place
        """
        # Step 1: female V (default)
        self.assertEqual(self.sim.player.GetBodyType(), BodyType.WomanAverage)

        # Step 2: create rig with curvy body modifications
        rig = DeformationRig(name="curvy_v", body_type=BodyType.WomanAverage)
        rig.SetBoneScaleSymmetric("Thigh_l", 1.25, 1.0, 1.15)
        rig.SetBoneScaleSymmetric("Calf_l", 0.95, 1.0, 0.95)
        rig.SetBoneScale("Chest", 1.15, 1.0, 1.1)
        rig.SetBoneScale("Hips", 1.2, 1.0, 1.15)

        # Step 3: install
        self.sim.apply_deformation_rig(rig)
        self.assertIsNotNone(self.sim.player.GetDeformationRig())
        self.assertIsNotNone(self.sim.player.GetDeformationRigFPP())

        # Step 4: morph targets
        self.sim.apply_player_morph("BodyFat", "UpperBody", 0.3)
        self.sim.apply_player_morph("MuscleTone", "UpperBody", 0.6)
        morphs = self.sim.player.GetBodyMorphTargets()
        self.assertEqual(len(morphs), 2)

        # Step 5: slight visual scale tweak
        self.sim.set_player_visual_scale(1.02, 1.0, 1.02)
        v = self.sim.get_player_visual_scale()
        self.assertAlmostEqual(v.X, 1.02)

        # Step 6: verify bone count (4 unique + 2 mirrored = 6 total)
        installed = self.sim.player.GetDeformationRig()
        self.assertEqual(installed.GetBoneCount(), 6)
        self.assertEqual(len(installed.GetModifiedBones()), 6)


if __name__ == '__main__':
    unittest.main()
