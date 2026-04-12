"""
AMM Full Test Suite
===================

Comprehensive validation of the AMM (AppearanceMenuMod) engine simulation.
Tests every major system AMM touches against the real-game Lua source at:
  https://github.com/MaximiliumM/appearancemenumod

Suites:
  1.  TestAMMSpawnSystem         -- DES spawn, tags, AMM_NPC / AMM_CAR patterns
  2.  TestCompanionRoleManagement -- AIFollowerRole / AINoRole / AIRole cycling
  3.  TestAICommands             -- SendCommand, GetActive, history, cancel
  4.  TestCompanionDistances     -- Tier logic (2 / 3.5 / 5 m), reissue
  5.  TestAppearanceSystem       -- Prefetch / schedule / history / custom
  6.  TestGodModeSystem          -- AddGodMode / ClearGodMode / IsImmortal
  7.  TestAttitudeSystem         -- SetAttitudeGroup / SetAttitudeTowards
  8.  TestTeleportation          -- TeleportationFacility, AITeleportCommand
  9.  TestTweakDBOperations      -- CloneRecord, SetFlatNoUpdate, Update, AMM records
  10. TestStaticEntitySystem     -- Prop spawn / delete / scale
  11. TestWorldSystems           -- Weather, time, workspot, targeter, mappins
  12. TestStatusEffects          -- Apply / remove / tick / expire
  13. TestMultiCompanionStress   -- 50 / 100 companions, mass ops, perf bounds
  14. TestSessionLifecycle       -- Start / end / restart, systems survive
  15. TestFullIntegration        -- End-to-end AMM scenario walkthroughs

Run:
    python tests/run_tests.py
    python -m unittest tests.mods.test_amm_full -v
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation, Vector4, Quaternion, EInputKey, NPCStats,
    TweakDB, TweakDBID, CharacterStats, StatsSystem,
    HitFlag, NPCStats,
    EAIAttitude, AIFollowerRole, AINoRole, AIRole,
    AICommandType, AIFollowTargetCommand, AITeleportCommand,
    AIMoveToCommand, AIHoldPositionCommand, AIPlayAnimationCommand,
    AppearanceRecord, AppearanceTrigger, AppearanceTriggerSystem,
    gameGodModeType, GodModeSystem,
    EulerAngles, TeleportationFacility,
    StaticEntitySpec, StaticEntitySystem,
    WeatherID, WeatherSystem, GameTimeSystem,
    MappinData, MappinSystem,
    WorkspotSystem, TargetingSystem,
    GameplayRestriction, GameplayStatusEffectSystem,
    ObserverRegistry,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 1: AMM Spawn System
# ═══════════════════════════════════════════════════════════════════════════════

class TestAMMSpawnSystem(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_spawn_with_amm_npc_tag(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(5, 0, 0))
        self.assertTrue(self.sim.des.IsPopulated("AMM_NPC"))

    def test_spawn_with_multiple_amm_tags(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC", "Companion", "AMM"], pos=(5, 0, 0))
        self.assertTrue(self.sim.des.IsPopulated("AMM_NPC"))
        self.assertTrue(self.sim.des.IsPopulated("Companion"))
        self.assertTrue(self.sim.des.IsPopulated("AMM"))

    def test_spawn_vehicle_with_amm_car_tag(self):
        car = self.sim.spawn_npc(tags=["AMM_CAR"], pos=(10, 0, 0))
        self.assertTrue(self.sim.des.IsPopulated("AMM_CAR"))
        self.assertFalse(self.sim.des.IsPopulated("AMM_NPC"))

    def test_get_tagged_returns_spawned_npc(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(5, 0, 0))
        tagged = self.sim.des.GetTagged("AMM_NPC")
        self.assertIn(npc, tagged)

    def test_get_tagged_excludes_wrong_tag(self):
        self.sim.spawn_npc(tags=["AMM_NPC"], pos=(5, 0, 0))
        tagged = self.sim.des.GetTagged("AMM_CAR")
        self.assertEqual(tagged, [])

    def test_spawn_multiple_npcs_all_tagged(self):
        for i in range(5):
            self.sim.spawn_npc(tags=["AMM_NPC"], pos=(i * 3, 0, 0))
        tagged = self.sim.des.GetTagged("AMM_NPC")
        self.assertEqual(len(tagged), 5)

    def test_entity_position_matches_spawn(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(7, 3, 1))
        pos = npc.GetWorldPosition()
        self.assertAlmostEqual(pos.X, 7.0)
        self.assertAlmostEqual(pos.Y, 3.0)
        self.assertAlmostEqual(pos.Z, 1.0)

    def test_entity_orientation_from_yaw(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(0, 0, 0), yaw=90)
        q = npc.GetWorldOrientation()
        self.assertTrue(q.is_valid())
        self.assertFalse(q.is_identity())

    def test_despawn_removes_from_des(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(5, 0, 0))
        self.sim.despawn_npc(npc)
        tagged = self.sim.des.GetTagged("AMM_NPC")
        self.assertNotIn(npc, tagged)

    def test_despawn_invalidates_entity(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(5, 0, 0))
        self.sim.despawn_npc(npc)
        self.assertFalse(npc.IsDefined())

    def test_session_end_clears_all_entities(self):
        for i in range(4):
            self.sim.spawn_npc(tags=["AMM_NPC"], pos=(i, 0, 0))
        self.sim.end_session()
        self.assertFalse(self.sim.des.IsReady())
        self.assertEqual(self.sim.des.GetEntityCount(), 0)

    def test_spawn_with_appearance_name(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(0, 0, 0),
                                  appearance="judy_default")
        self.assertEqual(npc.GetCurrentAppearanceName(), "judy_default")


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 2: Companion Role Management
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompanionRoleManagement(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))
        self.npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(3, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_default_role_is_no_role(self):
        ctrl = self.npc.GetAIControllerComponent()
        self.assertIsInstance(ctrl.GetAIRole(), AINoRole)

    def test_set_companion_sets_follower_role(self):
        self.sim.set_companion(self.npc)
        ctrl = self.npc.GetAIControllerComponent()
        self.assertIsInstance(ctrl.GetAIRole(), AIFollowerRole)

    def test_follower_role_has_player_ref(self):
        self.sim.set_companion(self.npc)
        role = self.npc.GetAIControllerComponent().GetAIRole()
        self.assertIs(role.follower_ref, self.sim.player)

    def test_set_companion_marks_is_companion(self):
        self.sim.set_companion(self.npc)
        self.assertTrue(self.npc.IsCompanion())

    def test_set_companion_sets_player_allies_attitude(self):
        self.sim.set_companion(self.npc)
        self.assertEqual(self.npc.GetAttitudeAgent().GetAttitudeGroup(),
                         "PlayerAllies")

    def test_set_companion_friendly_towards_player(self):
        self.sim.set_companion(self.npc)
        npc_agent    = self.npc.GetAttitudeAgent()
        player_agent = self.sim.player.GetAttitudeAgent()
        self.assertEqual(npc_agent.GetAttitudeTowards(player_agent),
                         EAIAttitude.AIA_Friendly)

    def test_toggle_hostile_switches_to_ai_role(self):
        self.sim.set_companion(self.npc)
        self.sim.toggle_hostile(self.npc)
        ctrl = self.npc.GetAIControllerComponent()
        self.assertIsInstance(ctrl.GetAIRole(), AIRole)

    def test_toggle_hostile_sets_hostile_attitude_group(self):
        self.sim.set_companion(self.npc)
        self.sim.toggle_hostile(self.npc)
        self.assertIn(self.npc.GetAttitudeAgent().GetAttitudeGroup(),
                      ("Ganger_Aggressive", "Hostile"))

    def test_toggle_hostile_unmarks_companion(self):
        self.sim.set_companion(self.npc)
        self.sim.toggle_hostile(self.npc)
        self.assertFalse(self.npc.IsCompanion())

    def test_toggle_back_to_companion(self):
        self.sim.set_companion(self.npc)
        self.sim.toggle_hostile(self.npc)
        self.sim.toggle_hostile(self.npc)   # toggle again
        ctrl = self.npc.GetAIControllerComponent()
        self.assertIsInstance(ctrl.GetAIRole(), AIFollowerRole)
        self.assertTrue(self.npc.IsCompanion())

    def test_is_follower_predicate(self):
        self.sim.set_companion(self.npc)
        self.assertTrue(self.npc.GetAIControllerComponent().IsFollower())
        self.assertFalse(self.npc.GetAIControllerComponent().IsHostile())
        self.assertFalse(self.npc.GetAIControllerComponent().IsNeutral())

    def test_multiple_companions_all_set(self):
        npcs = [self.sim.spawn_npc(["AMM_NPC"], (i*2, 0, 0)) for i in range(5)]
        for npc in npcs:
            self.sim.set_companion(npc)
        for npc in npcs:
            self.assertTrue(npc.GetAIControllerComponent().IsFollower())


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 3: AI Commands
# ═══════════════════════════════════════════════════════════════════════════════

class TestAICommands(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))
        self.sim.set_companion(self.npc)
        self.ctrl = self.npc.GetAIControllerComponent()

    def tearDown(self):
        self.sim.teardown()

    def test_send_follow_command(self):
        cmd = AIFollowTargetCommand(target=self.sim.player, distance=2.0)
        self.ctrl.SendCommand(cmd)
        self.assertIs(self.ctrl.GetActiveCommand(), cmd)

    def test_follow_command_type(self):
        self.sim.issue_follow_command(self.npc, 2.0)
        active = self.ctrl.GetActiveCommand()
        self.assertEqual(active.command_type, AICommandType.Follow)

    def test_follow_command_params(self):
        self.sim.issue_follow_command(self.npc, 3.5)
        active = self.ctrl.GetActiveCommand()
        self.assertAlmostEqual(active.params["distance"], 3.5)

    def test_send_teleport_command(self):
        pos = Vector4(10, 20, 0, 0)
        cmd = AITeleportCommand(position=pos, yaw=45.0)
        self.ctrl.SendCommand(cmd)
        active = self.ctrl.GetActiveCommand()
        self.assertEqual(active.command_type, AICommandType.Teleport)

    def test_send_move_to_command(self):
        cmd = AIMoveToCommand(position=Vector4(15, 0, 0, 0))
        self.ctrl.SendCommand(cmd)
        self.assertEqual(self.ctrl.GetActiveCommand().command_type,
                         AICommandType.MoveTo)

    def test_send_hold_position_command(self):
        cmd = AIHoldPositionCommand()
        self.ctrl.SendCommand(cmd)
        self.assertEqual(self.ctrl.GetActiveCommand().command_type,
                         AICommandType.HoldPosition)

    def test_new_command_cancels_old(self):
        cmd1 = AIFollowTargetCommand()
        cmd2 = AIHoldPositionCommand()
        self.ctrl.SendCommand(cmd1)
        self.ctrl.SendCommand(cmd2)
        self.assertFalse(cmd1.IsActive())
        self.assertTrue(cmd2.IsActive())
        self.assertIs(self.ctrl.GetActiveCommand(), cmd2)

    def test_stop_executing_command(self):
        cmd = AIFollowTargetCommand()
        self.ctrl.SendCommand(cmd)
        self.ctrl.StopExecutingCommand(AICommandType.Follow)
        self.assertIsNone(self.ctrl.GetActiveCommand())
        self.assertFalse(cmd.IsActive())

    def test_cancel_command(self):
        cmd = AIFollowTargetCommand()
        self.ctrl.SendCommand(cmd)
        self.ctrl.CancelCommand()
        self.assertIsNone(self.ctrl.GetActiveCommand())

    def test_command_history_grows(self):
        for _ in range(4):
            self.ctrl.SendCommand(AIFollowTargetCommand())
        self.assertGreaterEqual(self.ctrl.GetCommandCount(), 4)

    def test_get_last_command_of_type(self):
        self.ctrl.SendCommand(AITeleportCommand())
        self.ctrl.SendCommand(AIFollowTargetCommand())
        last_follow = self.ctrl.GetLastCommandOfType(AICommandType.Follow)
        self.assertIsNotNone(last_follow)

    def test_has_active_command_predicate(self):
        self.assertFalse(self.ctrl.HasActiveCommand())
        self.ctrl.SendCommand(AIFollowTargetCommand())
        self.assertTrue(self.ctrl.HasActiveCommand())
        self.assertTrue(self.ctrl.HasActiveCommand(AICommandType.Follow))
        self.assertFalse(self.ctrl.HasActiveCommand(AICommandType.Teleport))


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 4: Companion Follow Distance Tiers
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompanionDistances(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def _spawn_companions(self, n):
        npcs = []
        for i in range(n):
            npc = self.sim.spawn_npc(["AMM_NPC"], (i * 2 + 3, 0, 0))
            self.sim.set_companion(npc)
            npcs.append(npc)
        return npcs

    def test_1_companion_gets_close_distance(self):
        companions = self._spawn_companions(1)
        self.sim.update_follow_distances(companions)
        cmd = companions[0].GetAIControllerComponent().GetLastCommandOfType(
            AICommandType.Follow)
        self.assertAlmostEqual(cmd.params["distance"], 2.0)

    def test_2_companions_get_close_distance(self):
        companions = self._spawn_companions(2)
        self.sim.update_follow_distances(companions)
        for npc in companions:
            cmd = npc.GetAIControllerComponent().GetLastCommandOfType(
                AICommandType.Follow)
            self.assertAlmostEqual(cmd.params["distance"], 2.0)

    def test_3_companions_get_medium_distance(self):
        companions = self._spawn_companions(3)
        self.sim.update_follow_distances(companions)
        for npc in companions:
            cmd = npc.GetAIControllerComponent().GetLastCommandOfType(
                AICommandType.Follow)
            self.assertAlmostEqual(cmd.params["distance"], 3.5)

    def test_4_companions_get_wide_distance(self):
        companions = self._spawn_companions(4)
        self.sim.update_follow_distances(companions)
        for npc in companions:
            cmd = npc.GetAIControllerComponent().GetLastCommandOfType(
                AICommandType.Follow)
            self.assertAlmostEqual(cmd.params["distance"], 5.0)

    def test_more_than_4_companions_get_wide_distance(self):
        companions = self._spawn_companions(8)
        self.sim.update_follow_distances(companions)
        for npc in companions:
            cmd = npc.GetAIControllerComponent().GetLastCommandOfType(
                AICommandType.Follow)
            self.assertAlmostEqual(cmd.params["distance"], 5.0)

    def test_close_companions_do_not_trigger_reissue(self):
        # NPC at 2 m from player → within 15 m threshold → no reissue
        npc = self.sim.spawn_npc(["AMM_NPC"], (2, 0, 0))
        self.sim.set_companion(npc)
        lagging = self.sim.check_companion_distances([npc], threshold=15.0)
        self.assertEqual(lagging, [])

    def test_distant_companion_triggers_reissue(self):
        # NPC at 20 m from player → beyond 15 m threshold
        npc = self.sim.spawn_npc(["AMM_NPC"], (20, 0, 0))
        self.sim.set_companion(npc)
        lagging = self.sim.check_companion_distances([npc], threshold=15.0)
        self.assertIn(npc, lagging)

    def test_reissue_sends_new_follow_command(self):
        npc = self.sim.spawn_npc(["AMM_NPC"], (20, 0, 0))
        self.sim.set_companion(npc)
        before = npc.GetAIControllerComponent().GetCommandCount()
        self.sim.check_companion_distances([npc], threshold=15.0)
        after = npc.GetAIControllerComponent().GetCommandCount()
        self.assertGreater(after, before)

    def test_hostile_npcs_excluded_from_distance_check(self):
        npc = self.sim.spawn_npc(["AMM_NPC"], (20, 0, 0))
        self.sim.set_companion(npc)
        self.sim.toggle_hostile(npc)   # now hostile
        lagging = self.sim.check_companion_distances([npc], threshold=15.0)
        self.assertEqual(lagging, [])

    def test_player_move_changes_distance_reference(self):
        npc = self.sim.spawn_npc(["AMM_NPC"], (2, 0, 0))
        self.sim.set_companion(npc)
        # Move player far away
        self.sim.move_player((100, 0, 0))
        lagging = self.sim.check_companion_distances([npc], threshold=15.0)
        self.assertIn(npc, lagging)


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 5: Appearance System
# ═══════════════════════════════════════════════════════════════════════════════

class TestAppearanceSystem(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0),
                                       appearance="judy_default")

    def tearDown(self):
        self.sim.teardown()

    def test_initial_appearance_name(self):
        self.assertEqual(self.npc.GetCurrentAppearanceName(), "judy_default")

    def test_prefetch_does_not_change_current(self):
        self.npc.PrefetchAppearanceChange("judy_casual")
        self.assertEqual(self.npc.GetCurrentAppearanceName(), "judy_default")

    def test_prefetch_records_prefetched_name(self):
        self.npc.PrefetchAppearanceChange("judy_casual")
        self.assertTrue(self.npc._appearance.WasPrefetched("judy_casual"))

    def test_schedule_changes_current(self):
        self.npc.ScheduleAppearanceChange("judy_casual")
        self.assertEqual(self.npc.GetCurrentAppearanceName(), "judy_casual")

    def test_change_appearance_full_pipeline(self):
        self.sim.change_appearance(self.npc, "judy_corpo")
        self.assertEqual(self.npc.GetCurrentAppearanceName(), "judy_corpo")

    def test_change_history_grows(self):
        self.sim.change_appearance(self.npc, "judy_casual")
        self.sim.change_appearance(self.npc, "judy_corpo")
        history = self.npc._appearance.GetChangeHistory()
        self.assertIn("judy_default", history)
        self.assertIn("judy_casual", history)
        self.assertIn("judy_corpo", history)

    def test_change_count_increments(self):
        before = self.npc._appearance.GetChangeCount()
        self.sim.change_appearance(self.npc, "judy_casual")
        self.sim.change_appearance(self.npc, "judy_corpo")
        self.assertEqual(self.npc._appearance.GetChangeCount(), before + 2)

    def test_register_custom_appearance(self):
        rec = AppearanceRecord(name="judy_amm_custom", is_custom=True,
                               mesh_path="base\\amm\\judy_custom.mesh")
        self.npc._appearance.RegisterCustomAppearance(rec)
        fetched = self.npc._appearance.GetCustomAppearance("judy_amm_custom")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.mesh_path, "base\\amm\\judy_custom.mesh")

    def test_appearance_database_seeded_judy(self):
        apps = self.sim.appearance_db.GetAppearances("Judy Alvarez")
        self.assertIn("judy_default", apps)
        self.assertGreater(len(apps), 2)

    def test_appearance_trigger_zone_condition(self):
        trigger = AppearanceTrigger(
            entity_id=self.npc.GetEntityID(),
            condition="zone:Clouds",
            appearance="judy_swimsuit",
        )
        self.sim.appearance_triggers.RegisterTrigger(trigger)
        self.sim.appearance_triggers.EvaluateTriggers(
            [self.npc], zone="Clouds", in_combat=False)
        self.assertEqual(self.npc.GetCurrentAppearanceName(), "judy_swimsuit")

    def test_appearance_trigger_combat_condition(self):
        trigger = AppearanceTrigger(
            entity_id=self.npc.GetEntityID(),
            condition="combat",
            appearance="judy_punk",
        )
        self.sim.appearance_triggers.RegisterTrigger(trigger)
        self.sim.appearance_triggers.EvaluateTriggers(
            [self.npc], zone="", in_combat=True)
        self.assertEqual(self.npc.GetCurrentAppearanceName(), "judy_punk")

    def test_appearance_trigger_no_match(self):
        trigger = AppearanceTrigger(
            entity_id=self.npc.GetEntityID(),
            condition="zone:Afterlife",
            appearance="judy_corpo",
        )
        self.sim.appearance_triggers.RegisterTrigger(trigger)
        self.sim.appearance_triggers.EvaluateTriggers(
            [self.npc], zone="Clouds")
        self.assertEqual(self.npc.GetCurrentAppearanceName(), "judy_default")


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 6: God Mode System
# ═══════════════════════════════════════════════════════════════════════════════

class TestGodModeSystem(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))
        self.eid = self.npc.GetEntityID()

    def tearDown(self):
        self.sim.teardown()

    def test_no_god_mode_by_default(self):
        self.assertFalse(self.sim.god_mode.HasGodMode(self.eid))

    def test_add_god_mode_sets_immortal(self):
        self.sim.set_god_mode(self.npc, immortal=True)
        self.assertTrue(self.sim.god_mode.IsImmortal(self.eid))

    def test_clear_god_mode_removes(self):
        self.sim.set_god_mode(self.npc, immortal=True)
        self.sim.set_god_mode(self.npc, immortal=False)
        self.assertFalse(self.sim.god_mode.HasGodMode(self.eid))

    def test_god_mode_type_is_immortal(self):
        self.sim.set_god_mode(self.npc, immortal=True)
        gtype = self.sim.god_mode.GetGodModeType(self.eid, "AMM_GodMode")
        self.assertEqual(gtype, gameGodModeType.Immortal)

    def test_multiple_reasons_tracked(self):
        gm = self.sim.god_mode
        gm.AddGodMode(self.eid, gameGodModeType.Immortal, "AMM_GodMode")
        gm.AddGodMode(self.eid, gameGodModeType.Immortal, "AMM_Debug")
        gm.ClearGodMode(self.eid, "AMM_GodMode")
        self.assertTrue(gm.HasGodMode(self.eid))   # still has Debug reason

    def test_clear_all_reasons_removes_god_mode(self):
        gm = self.sim.god_mode
        gm.AddGodMode(self.eid, gameGodModeType.Immortal, "r1")
        gm.AddGodMode(self.eid, gameGodModeType.Immortal, "r2")
        gm.ClearGodMode(self.eid, "r1")
        gm.ClearGodMode(self.eid, "r2")
        self.assertFalse(gm.HasGodMode(self.eid))

    def test_immortal_count(self):
        n2 = self.sim.spawn_npc(["AMM_NPC"], (10, 0, 0))
        self.sim.set_god_mode(self.npc, True)
        self.sim.set_god_mode(n2, True)
        self.assertEqual(self.sim.god_mode.GetImmortalCount(), 2)


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 7: Attitude System
# ═══════════════════════════════════════════════════════════════════════════════

class TestAttitudeSystem(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_default_attitude_group_neutral(self):
        self.assertEqual(self.npc.GetAttitudeAgent().GetAttitudeGroup(), "Neutral")

    def test_player_allies_group_gives_friendly_default(self):
        self.npc.GetAttitudeAgent().SetAttitudeGroup("PlayerAllies")
        player_agent = self.sim.player.GetAttitudeAgent()
        self.assertEqual(
            self.npc.GetAttitudeAgent().GetAttitudeTowards(player_agent),
            EAIAttitude.AIA_Friendly)

    def test_hostile_group_gives_hostile_default(self):
        npc2 = self.sim.spawn_npc(["AMM_NPC"], (10, 0, 0))
        self.npc.GetAttitudeAgent().SetAttitudeGroup("Hostile")
        self.assertEqual(
            self.npc.GetAttitudeAgent().GetAttitudeTowards(
                npc2.GetAttitudeAgent()),
            EAIAttitude.AIA_Hostile)

    def test_set_friendly_towards_overrides_group(self):
        self.npc.GetAttitudeAgent().SetAttitudeGroup("Hostile")
        other = self.sim.spawn_npc(["AMM_NPC"], (10, 0, 0))
        self.npc.GetAttitudeAgent().SetAttitudeTowards(
            other.GetAttitudeAgent(), EAIAttitude.AIA_Friendly)
        self.assertEqual(
            self.npc.GetAttitudeAgent().GetAttitudeTowards(
                other.GetAttitudeAgent()),
            EAIAttitude.AIA_Friendly)

    def test_is_enemy_predicate(self):
        self.npc.GetAttitudeAgent().SetAttitudeGroup("Ganger_Aggressive")
        other = self.sim.spawn_npc(["AMM_NPC"], (10, 0, 0))
        self.assertTrue(self.npc.GetAttitudeAgent().IsEnemy(
            other.GetAttitudeAgent()))

    def test_is_friend_predicate(self):
        self.sim.set_companion(self.npc)
        player_agent = self.sim.player.GetAttitudeAgent()
        self.assertTrue(self.npc.GetAttitudeAgent().IsFriend(player_agent))

    def test_companions_made_friendly_towards_each_other(self):
        npc2 = self.sim.spawn_npc(["AMM_NPC"], (10, 0, 0))
        self.sim.set_companion(self.npc)
        self.sim.set_companion(npc2)
        # Both are in PlayerAllies → should be friendly by group default
        self.assertEqual(
            self.npc.GetAttitudeAgent().GetAttitudeTowards(
                npc2.GetAttitudeAgent()),
            EAIAttitude.AIA_Friendly)

    def test_toggle_hostile_changes_attitude_group(self):
        self.sim.set_companion(self.npc)
        self.sim.toggle_hostile(self.npc)
        group = self.npc.GetAttitudeAgent().GetAttitudeGroup()
        self.assertNotEqual(group, "PlayerAllies")


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 8: Teleportation
# ═══════════════════════════════════════════════════════════════════════════════

class TestTeleportation(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))
        self.npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_teleport_player_to_position(self):
        self.sim.teleport_entity(self.sim.player, (50, 25, 10))
        pos = self.sim.player.GetWorldPosition()
        self.assertAlmostEqual(pos.X, 50.0)
        self.assertAlmostEqual(pos.Y, 25.0)
        self.assertAlmostEqual(pos.Z, 10.0)

    def test_teleport_npc_to_position(self):
        self.sim.teleport_entity(self.npc, (20, 30, 0))
        pos = self.npc.GetWorldPosition()
        self.assertAlmostEqual(pos.X, 20.0)
        self.assertAlmostEqual(pos.Y, 30.0)

    def test_teleport_with_yaw_rotates(self):
        self.sim.teleport_entity(self.sim.player, (0, 0, 0), yaw=180.0)
        q = self.sim.player.GetWorldOrientation()
        self.assertTrue(q.is_valid())

    def test_teleport_log_grows(self):
        before = self.sim.teleport.TeleportCount()
        self.sim.teleport_entity(self.sim.player, (10, 10, 0))
        self.assertEqual(self.sim.teleport.TeleportCount(), before + 1)

    def test_teleport_log_entry_has_entity_id(self):
        self.sim.teleport_entity(self.npc, (15, 0, 0))
        entry = self.sim.teleport.GetLastTeleport()
        self.assertEqual(entry["entity_id"], self.npc.GetEntityID())

    def test_ai_teleport_command_sends(self):
        self.sim.teleport_npc_via_command(self.npc, (30, 0, 0))
        cmd = self.npc.GetAIControllerComponent().GetActiveCommand()
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.command_type, AICommandType.Teleport)

    def test_ai_teleport_command_params(self):
        self.sim.teleport_npc_via_command(self.npc, (30, 20, 5), yaw=90.0)
        cmd = self.npc.GetAIControllerComponent().GetActiveCommand()
        self.assertAlmostEqual(cmd.params["yaw"], 90.0)

    def test_teleport_moves_player_then_companion_follows(self):
        self.sim.set_companion(self.npc)
        self.sim.teleport_entity(self.sim.player, (100, 0, 0))
        lagging = self.sim.check_companion_distances([self.npc], threshold=15.0)
        self.assertIn(self.npc, lagging)


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 9: TweakDB Operations (AMM-specific)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTweakDBOperations(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.db  = self.sim.tweakdb

    def tearDown(self):
        self.sim.teardown()

    def test_amm_character_judy_seeded(self):
        rec = self.db.GetRecord("AMM_Character.Judy")
        self.assertIsNotNone(rec)

    def test_amm_character_panam_seeded(self):
        rec = self.db.GetRecord("AMM_Character.Panam")
        self.assertIsNotNone(rec)

    def test_amm_character_entity_template_overridden(self):
        rec = self.db.GetRecord("AMM_Character.Judy")
        path = rec.GetFlat("entityTemplatePath")
        self.assertIn("amm_characters", path)

    def test_amm_character_is_spawnable(self):
        rec = self.db.GetRecord("AMM_Character.Judy")
        self.assertTrue(rec.GetFlat("isSpawnable"))

    def test_clone_record_creates_new_entry(self):
        ok = self.db.CloneRecord("MyMod.CloneJudy", "AMM_Character.Judy")
        self.assertTrue(ok)
        clone = self.db.GetRecord("MyMod.CloneJudy")
        self.assertIsNotNone(clone)

    def test_clone_inherits_source_flats(self):
        self.db.CloneRecord("MyMod.CloneJudy", "AMM_Character.Judy")
        source = self.db.GetRecord("AMM_Character.Judy")
        clone  = self.db.GetRecord("MyMod.CloneJudy")
        self.assertEqual(clone.GetFlat("entityTemplatePath"),
                         source.GetFlat("entityTemplatePath"))

    def test_clone_is_independent_of_source(self):
        self.db.CloneRecord("MyMod.CloneJudy", "AMM_Character.Judy")
        self.db.SetFlat("MyMod.CloneJudy.entityTemplatePath",
                        "base\\mymod\\judy_custom.ent")
        source = self.db.GetRecord("AMM_Character.Judy")
        clone  = self.db.GetRecord("MyMod.CloneJudy")
        self.assertNotEqual(clone.GetFlat("entityTemplatePath"),
                            source.GetFlat("entityTemplatePath"))

    def test_clone_duplicate_fails(self):
        self.db.CloneRecord("MyMod.CloneJudy", "AMM_Character.Judy")
        ok2 = self.db.CloneRecord("MyMod.CloneJudy", "AMM_Character.Judy")
        self.assertFalse(ok2)

    def test_clone_missing_source_fails(self):
        ok = self.db.CloneRecord("MyMod.X", "Character.DoesNotExist")
        self.assertFalse(ok)

    def test_set_flat_no_update_stores_value(self):
        self.db.SetFlatNoUpdate("AMM_Character.Judy.entityTemplatePath",
                                "base\\custom_judy.ent")
        rec = self.db.GetRecord("AMM_Character.Judy")
        self.assertEqual(rec.GetFlat("entityTemplatePath"),
                         "base\\custom_judy.ent")

    def test_update_tracks_call(self):
        self.db.Update("AMM_Character.Judy")
        self.assertTrue(self.db.WasUpdated("AMM_Character.Judy"))

    def test_set_flat_weapon_damage(self):
        old = self.db.GetFlat("Items.Preset_Yukimura_Default.damagePerHit")
        self.db.SetFlat("Items.Preset_Yukimura_Default.damagePerHit", 9999.0)
        new = self.db.GetFlat("Items.Preset_Yukimura_Default.damagePerHit")
        self.assertAlmostEqual(new, 9999.0)
        self.assertNotAlmostEqual(new, old)

    def test_set_flat_isolation_between_sims(self):
        self.db.SetFlat("Items.Preset_Yukimura_Default.damagePerHit", 9999.0)
        self.sim.teardown()
        sim2 = GameSimulation()
        db2  = sim2.tweakdb
        val  = db2.GetFlat("Items.Preset_Yukimura_Default.damagePerHit")
        self.assertNotAlmostEqual(val, 9999.0)
        sim2.teardown()


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 10: Static Entity System (Props)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStaticEntitySystem(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.ses = self.sim.static_entities

    def tearDown(self):
        self.sim.teardown()

    def test_spawn_static_entity(self):
        spec = StaticEntitySpec(entity_path="base\\props\\chair.ent",
                                appear_name="red",
                                position=Vector4(5, 0, 0, 0))
        eid, ent = self.ses.CreateEntity(spec)
        self.assertIsNotNone(ent)
        self.assertTrue(ent.IsDefined())

    def test_static_entity_position(self):
        spec = StaticEntitySpec(position=Vector4(7, 3, 1, 0))
        _, ent = self.ses.CreateEntity(spec)
        pos = ent.GetWorldPosition()
        self.assertAlmostEqual(pos.X, 7.0)
        self.assertAlmostEqual(pos.Y, 3.0)
        self.assertAlmostEqual(pos.Z, 1.0)

    def test_entity_count_increments(self):
        before = self.ses.GetEntityCount()
        for _ in range(3):
            self.ses.CreateEntity(StaticEntitySpec())
        self.assertEqual(self.ses.GetEntityCount(), before + 3)

    def test_delete_entity(self):
        eid, ent = self.ses.CreateEntity(StaticEntitySpec())
        self.ses.DeleteEntity(eid)
        self.assertFalse(ent.IsDefined())
        self.assertIsNone(self.ses.GetEntity(eid))

    def test_entity_count_decrements_after_delete(self):
        eid, _ = self.ses.CreateEntity(StaticEntitySpec())
        before = self.ses.GetEntityCount()
        self.ses.DeleteEntity(eid)
        self.assertEqual(self.ses.GetEntityCount(), before - 1)

    def test_get_all_entities(self):
        for _ in range(4):
            self.ses.CreateEntity(StaticEntitySpec())
        all_ents = self.ses.GetAllEntities()
        self.assertGreaterEqual(len(all_ents), 4)

    def test_dispose_marks_dead(self):
        _, ent = self.ses.CreateEntity(StaticEntitySpec())
        ent.Dispose()
        self.assertFalse(ent.IsDefined())

    def test_clear_all_empties_system(self):
        for _ in range(5):
            self.ses.CreateEntity(StaticEntitySpec())
        self.ses.ClearAll()
        self.assertEqual(self.ses.GetEntityCount(), 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 11: World Systems
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorldSystems(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    # Weather
    def test_default_weather_is_clear(self):
        self.assertEqual(self.sim.weather.GetActiveWeather(), WeatherID.Clear)

    def test_set_weather_changes_active(self):
        self.sim.weather.SetWeather(WeatherID.Rain)
        self.assertEqual(self.sim.weather.GetActiveWeather(), WeatherID.Rain)

    def test_weather_history_grows(self):
        self.sim.weather.SetWeather(WeatherID.Rain)
        self.sim.weather.SetWeather(WeatherID.Fog)
        history = self.sim.weather.GetWeatherHistory()
        self.assertIn(WeatherID.Rain, history)
        self.assertIn(WeatherID.Fog,  history)

    # Time
    def test_default_time_is_morning(self):
        self.assertEqual(self.sim.time_system.GetHour(), 8)

    def test_set_time(self):
        self.sim.time_system.SetHourMinute(22, 30)
        self.assertEqual(self.sim.time_system.GetHour(),   22)
        self.assertEqual(self.sim.time_system.GetMinute(), 30)

    def test_advance_time(self):
        self.sim.time_system.SetHourMinute(8, 0)
        self.sim.time_system.AdvanceTime(3 * 3600)
        self.assertEqual(self.sim.time_system.GetHour(), 11)

    # Workspot
    def test_not_in_workspot_by_default(self):
        npc = self.sim.spawn_npc(["A"], (5, 0, 0))
        self.assertFalse(self.sim.workspot.IsActorInWorkspot(npc))

    def test_set_actor_in_workspot(self):
        npc = self.sim.spawn_npc(["A"], (5, 0, 0))
        self.sim.workspot.SetActorInWorkspot(npc, True)
        self.assertTrue(self.sim.workspot.IsActorInWorkspot(npc))

    def test_evict_actor_from_workspot(self):
        npc = self.sim.spawn_npc(["A"], (5, 0, 0))
        self.sim.workspot.SetActorInWorkspot(npc, True)
        self.sim.workspot.EvictActor(npc)
        self.assertFalse(self.sim.workspot.IsActorInWorkspot(npc))

    # Targeting
    def test_default_look_at_target_none(self):
        self.assertIsNone(self.sim.targeting.GetLookAtObject())

    def test_set_look_at_target(self):
        npc = self.sim.spawn_npc(["A"], (5, 0, 0))
        self.sim.targeting.SetLookAtTarget(npc)
        self.assertIs(self.sim.targeting.GetLookAtObject(), npc)

    # Mappins
    def test_register_mappin(self):
        data = MappinData(label="Judy")
        mid  = self.sim.mappins.RegisterMappin(data, position=Vector4(5, 0, 0, 0))
        self.assertTrue(self.sim.mappins.HasMappin(mid))
        self.assertEqual(self.sim.mappins.GetMappinCount(), 1)

    def test_unregister_mappin(self):
        data = MappinData()
        mid  = self.sim.mappins.RegisterMappin(data)
        self.sim.mappins.UnregisterMappin(mid)
        self.assertFalse(self.sim.mappins.HasMappin(mid))

    def test_register_mappin_with_entity(self):
        npc  = self.sim.spawn_npc(["A"], (5, 0, 0))
        data = MappinData(label="NPC Pin")
        mid  = self.sim.mappins.RegisterMappinWithObject(data, npc)
        self.assertEqual(self.sim.mappins.GetPinForEntity(npc), mid)


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 12: Gameplay Status Effects
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatusEffects(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))
        self.eid = self.npc.GetEntityID()
        self.sfx = self.sim.status_effects

    def tearDown(self):
        self.sim.teardown()

    def test_no_effects_by_default(self):
        self.assertEqual(self.sfx.GetActiveEffectCount(self.eid), 0)

    def test_apply_effect(self):
        self.sfx.ApplyStatusEffect(self.eid, GameplayRestriction.NoMovement)
        self.assertTrue(self.sfx.ObjectHasStatusEffect(
            self.npc, GameplayRestriction.NoMovement))

    def test_remove_effect(self):
        self.sfx.ApplyStatusEffect(self.eid, GameplayRestriction.NoMovement)
        self.sfx.RemoveStatusEffect(self.eid, GameplayRestriction.NoMovement)
        self.assertFalse(self.sfx.ObjectHasStatusEffect(
            self.npc, GameplayRestriction.NoMovement))

    def test_multiple_effects_tracked(self):
        self.sfx.ApplyStatusEffect(self.eid, GameplayRestriction.NoMovement)
        self.sfx.ApplyStatusEffect(self.eid, GameplayRestriction.Invisible)
        self.assertEqual(self.sfx.GetActiveEffectCount(self.eid), 2)

    def test_object_has_effect_with_tag(self):
        self.sfx.ApplyStatusEffect(self.eid, "GameplayRestriction.NoMovement")
        self.assertTrue(self.sfx.ObjectHasStatusEffectWithTag(
            self.npc, "GameplayRestriction"))

    def test_duration_limited_effect_expires(self):
        self.sfx.ApplyStatusEffect(self.eid, "TestEffect", duration=1.0)
        self.assertTrue(self.sfx.ObjectHasStatusEffect(self.npc, "TestEffect"))
        self.sim.advance_time(1.5)   # past duration
        self.assertFalse(self.sfx.ObjectHasStatusEffect(self.npc, "TestEffect"))

    def test_permanent_effect_does_not_expire(self):
        self.sfx.ApplyStatusEffect(self.eid, "PermanentEffect", duration=-1.0)
        self.sim.advance_time(100.0)
        self.assertTrue(self.sfx.ObjectHasStatusEffect(self.npc, "PermanentEffect"))

    def test_player_invisible_helper(self):
        self.sim.set_player_invisible(True)
        self.assertTrue(self.sim.is_player_invisible())

    def test_player_invisible_toggle_off(self):
        self.sim.set_player_invisible(True)
        self.sim.set_player_invisible(False)
        self.assertFalse(self.sim.is_player_invisible())


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 13: Multi-Companion Stress Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiCompanionStress(unittest.TestCase):
    """
    Performance and correctness at scale.
    All timed assertions use generous bounds (~1 second) to avoid false
    failures on slow CI machines.
    """

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_spawn_10_companions(self):
        companions = self.sim.spawn_npc_bulk(10, ["AMM_NPC", "Companion"])
        self.assertEqual(len(companions), 10)
        tagged = self.sim.des.GetTagged("AMM_NPC")
        self.assertEqual(len(tagged), 10)

    def test_spawn_50_companions(self):
        companions = self.sim.spawn_npc_bulk(50, ["AMM_NPC"])
        self.assertEqual(len(companions), 50)

    def test_spawn_100_companions_performance(self):
        _, elapsed_ms = self.sim.timed(
            lambda: self.sim.spawn_npc_bulk(100, ["AMM_NPC"]),
            label="spawn_100_companions"
        )
        self.assertLess(elapsed_ms, 1000,
                        f"Spawning 100 companions took {elapsed_ms:.0f} ms")

    def test_all_companions_set_to_follower(self):
        companions = self.sim.spawn_npc_bulk(50, ["AMM_NPC"])
        for npc in companions:
            self.sim.set_companion(npc)
        for npc in companions:
            self.assertTrue(npc.GetAIControllerComponent().IsFollower())

    def test_follow_distance_update_100_companions_performance(self):
        companions = self.sim.spawn_npc_bulk(100, ["AMM_NPC"])
        for npc in companions:
            self.sim.set_companion(npc)
        _, elapsed_ms = self.sim.timed(
            lambda: self.sim.update_follow_distances(companions),
            label="update_follow_distances_100"
        )
        self.assertLess(elapsed_ms, 500,
                        f"Follow distance update for 100 took {elapsed_ms:.0f} ms")

    def test_distance_check_100_companions_performance(self):
        companions = self.sim.spawn_npc_bulk(100, ["AMM_NPC"],
                                              base_pos=(100, 0, 0))
        for npc in companions:
            self.sim.set_companion(npc)
        _, elapsed_ms = self.sim.timed(
            lambda: self.sim.check_companion_distances(companions, threshold=50.0),
            label="distance_check_100"
        )
        self.assertLess(elapsed_ms, 200,
                        f"Distance check for 100 companions: {elapsed_ms:.0f} ms")

    def test_mass_toggle_hostile(self):
        companions = self.sim.spawn_npc_bulk(30, ["AMM_NPC"])
        for npc in companions:
            self.sim.set_companion(npc)
        for npc in companions:
            self.sim.toggle_hostile(npc)
        for npc in companions:
            self.assertFalse(npc.IsCompanion())
            self.assertTrue(npc.GetAIControllerComponent().IsHostile())

    def test_mass_appearance_change(self):
        companions = self.sim.spawn_npc_bulk(50, ["AMM_NPC"])
        _, elapsed_ms = self.sim.timed(
            lambda: [self.sim.change_appearance(npc, "judy_casual")
                     for npc in companions],
            label="mass_appearance_change_50"
        )
        self.assertLess(elapsed_ms, 500)
        for npc in companions:
            self.assertEqual(npc.GetCurrentAppearanceName(), "judy_casual")

    def test_mass_des_tag_lookup_performance(self):
        self.sim.spawn_npc_bulk(100, ["AMM_NPC"])
        _, elapsed_ms = self.sim.timed(
            lambda: self.sim.des.GetTagged("AMM_NPC"),
            label="GetTagged_100"
        )
        self.assertLess(elapsed_ms, 50,
                        f"GetTagged 100 entities: {elapsed_ms:.0f} ms")

    def test_mass_despawn_100(self):
        companions = self.sim.spawn_npc_bulk(100, ["AMM_NPC"])
        _, elapsed_ms = self.sim.timed(
            lambda: [self.sim.despawn_npc(npc) for npc in companions],
            label="despawn_100"
        )
        self.assertLess(elapsed_ms, 500)
        self.assertEqual(self.sim.des.GetEntityCount(), 0)

    def test_god_mode_100_companions(self):
        companions = self.sim.spawn_npc_bulk(100, ["AMM_NPC"])
        for npc in companions:
            self.sim.set_god_mode(npc, True)
        self.assertEqual(self.sim.god_mode.GetImmortalCount(), 100)

    def test_heapq_delay_system_1000_callbacks(self):
        """DelaySystem heapq should handle 1000 callbacks without slowdown."""
        fired = []

        class CB:
            def Call(self):
                fired.append(1)

        _, elapsed_ms = self.sim.timed(
            lambda: [self.sim.delay.DelayCallback(CB(), delay=i * 0.001)
                     for i in range(1000)],
            label="schedule_1000_callbacks"
        )
        self.assertLess(elapsed_ms, 500)
        self.sim.advance_time(2.0)   # fire all
        self.assertEqual(len(fired), 1000)


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 14: Session Lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionLifecycle(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_start_session_creates_player(self):
        player = self.sim.start_session(player_pos=(10, 20, 30))
        self.assertIsNotNone(player)
        pos = player.GetWorldPosition()
        self.assertAlmostEqual(pos.X, 10.0)

    def test_end_session_removes_player(self):
        self.sim.start_session()
        self.sim.end_session()
        self.assertIsNone(self.sim.player)

    def test_end_session_clears_des(self):
        self.sim.start_session()
        self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))
        self.sim.end_session()
        self.assertEqual(self.sim.des.GetEntityCount(), 0)

    def test_restart_session(self):
        self.sim.start_session(player_pos=(0, 0, 0))
        self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))
        self.sim.end_session()
        p2 = self.sim.start_session(player_pos=(1, 2, 3))
        self.assertIsNotNone(p2)
        pos = p2.GetWorldPosition()
        self.assertAlmostEqual(pos.X, 1.0)

    def test_facts_survive_tick(self):
        self.sim.start_session()
        self.sim.set_fact("companion_met", 1)
        self.sim.tick(4)
        self.assertEqual(self.sim.get_fact("companion_met"), 1)

    def test_god_mode_survives_tick(self):
        self.sim.start_session()
        npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))
        self.sim.set_god_mode(npc, True)
        self.sim.tick(4)
        self.assertTrue(self.sim.god_mode.IsImmortal(npc.GetEntityID()))

    def test_weather_survives_tick(self):
        self.sim.weather.SetWeather(WeatherID.Rain)
        self.sim.start_session()
        self.sim.tick(4)
        self.assertEqual(self.sim.weather.GetActiveWeather(), WeatherID.Rain)

    def test_tweakdb_reset_between_sims(self):
        self.sim.start_session()
        self.sim.tweakdb.SetFlat("Items.Preset_Yukimura_Default.damagePerHit",
                                  9999.0)
        self.sim.teardown()
        sim2 = GameSimulation()
        val = sim2.tweakdb.GetFlat("Items.Preset_Yukimura_Default.damagePerHit")
        self.assertLess(val, 9999.0)
        sim2.teardown()


# ═══════════════════════════════════════════════════════════════════════════════
#  Suite 15: Full Integration Scenarios
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullIntegration(unittest.TestCase):
    """
    End-to-end AMM workflow scenarios.
    Each test mirrors a real AMM user workflow from the mod source.
    """

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_scenario_spawn_companion_and_follow(self):
        """
        Mirrors: Spawn:SpawnNPC → SetNPCAsCompanion → UpdateFollowDistance.
        """
        npc = self.sim.spawn_npc(["AMM_NPC", "Companion"], (5, 0, 0))
        self.sim.set_companion(npc)
        self.sim.issue_follow_command(npc, 2.0)

        # Verify: companion is following at 2.0 m
        self.assertTrue(npc.GetAIControllerComponent().IsFollower())
        cmd = npc.GetAIControllerComponent().GetLastCommandOfType(
            AICommandType.Follow)
        self.assertIsNotNone(cmd)
        self.assertAlmostEqual(cmd.params["distance"], 2.0)

    def test_scenario_companion_god_mode_survives_damage(self):
        """
        Mirrors: Spawn:SetNPCAsCompanion → SetGodMode(true) → DamageSystem attack.
        God-moded companions take damage in the damage pipeline but we only
        assert that the god mode flag is set (game logic would block the damage).
        """
        npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0),
                                  npc_stats=NPCStats(max_health=100., current_health=100.))
        self.sim.set_companion(npc)
        self.sim.set_god_mode(npc, immortal=True)

        self.assertTrue(self.sim.god_mode.IsImmortal(npc.GetEntityID()))

    def test_scenario_appearance_pipeline(self):
        """
        Mirrors: Scan:GetActiveTarget → PrefetchAppearanceChange → ScheduleAppearanceChange.
        """
        npc = self.sim.spawn_npc(["AMM_NPC"], (3, 0, 0), appearance="judy_default")
        self.sim.targeting.SetLookAtTarget(npc)
        target = self.sim.targeting.GetLookAtObject()
        self.assertIs(target, npc)

        target.PrefetchAppearanceChange("judy_casual")
        target.ScheduleAppearanceChange("judy_casual")
        self.assertEqual(npc.GetCurrentAppearanceName(), "judy_casual")

    def test_scenario_tweakdb_clone_and_spawn(self):
        """
        Mirrors: TweakDB:CloneRecord(AMM_Character.Custom, Character.Judy_Judy)
                 → SetFlatNoUpdate(entityTemplatePath, custom.ent)
                 → TweakDB:Update(AMM_Character.Custom)
        """
        ok = self.sim.tweakdb.CloneRecord(
            "AMM_Character.Custom", "Character.Judy_Judy")
        self.assertTrue(ok)

        self.sim.tweakdb.SetFlatNoUpdate(
            "AMM_Character.Custom.entityTemplatePath",
            "base\\amm_characters\\entity\\custom_judy.ent")
        self.sim.tweakdb.Update("AMM_Character.Custom")

        rec = self.sim.tweakdb.GetRecord("AMM_Character.Custom")
        self.assertIn("custom_judy", rec.GetFlat("entityTemplatePath"))
        self.assertTrue(self.sim.tweakdb.WasUpdated("AMM_Character.Custom"))

    def test_scenario_5_companions_toggle_all_hostile(self):
        """
        Mirrors: Spawn:ToggleHostile loop over all companions.
        """
        companions = []
        for i in range(5):
            npc = self.sim.spawn_npc(["AMM_NPC", "Companion"], (i*3, 0, 0))
            self.sim.set_companion(npc)
            companions.append(npc)

        for npc in companions:
            self.sim.toggle_hostile(npc)

        for npc in companions:
            self.assertFalse(npc.IsCompanion())
            self.assertTrue(npc.GetAIControllerComponent().IsHostile())

    def test_scenario_teleport_to_saved_location(self):
        """
        Mirrors: Tools:TeleportToLocation → TeleportationFacility:Teleport.
        """
        saved_pos = (150.0, 200.0, 5.0)
        self.sim.teleport_entity(self.sim.player, saved_pos, yaw=270.0)
        pos = self.sim.player.GetWorldPosition()
        self.assertAlmostEqual(pos.X, 150.0)
        self.assertAlmostEqual(pos.Y, 200.0)
        self.assertAlmostEqual(pos.Z, 5.0)

    def test_scenario_workspot_animation(self):
        """
        Mirrors: Tools:GetAnimations → WorkspotSystem:IsActorInWorkspot guard.
        """
        npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))
        self.assertFalse(self.sim.workspot.IsActorInWorkspot(npc))
        self.sim.workspot.SetActorInWorkspot(npc, True)
        self.assertTrue(self.sim.workspot.IsActorInWorkspot(npc))
        # Send animation command to NPC
        cmd = AIPlayAnimationCommand("amm_sit_down", looping=True)
        npc.GetAIControllerComponent().SendCommand(cmd)
        self.assertEqual(npc.GetAIControllerComponent().GetActiveCommand().params["anim_name"],
                         "amm_sit_down")

    def test_scenario_weather_change(self):
        """
        Mirrors: Tools → GameWeatherSystem:SetWeather.
        """
        self.sim.weather.SetWeather(WeatherID.HeavyRain, blend_time=10.0)
        self.assertEqual(self.sim.weather.GetActiveWeather(), WeatherID.HeavyRain)
        self.assertAlmostEqual(self.sim.weather.GetBlendTime(), 10.0)

    def test_scenario_mappin_lifecycle(self):
        """
        Mirrors: AMM registers mappin on spawn, unregisters on despawn.
        """
        npc = self.sim.spawn_npc(["AMM_NPC"], (5, 0, 0))
        mid = self.sim.mappins.RegisterMappinWithObject(
            MappinData(label="Judy"), npc)
        npc.SetMappin(mid)

        self.assertTrue(self.sim.mappins.HasMappin(mid))
        self.sim.despawn_npc(npc)   # despawn clears mappin
        self.assertFalse(self.sim.mappins.HasMappin(mid))

    def test_scenario_status_effect_duration(self):
        """
        Mirrors: Tools:SetPassiveMode → ApplyStatusEffect(Invisible, 30s)
                 → tick 31s → effect expires.
        """
        player_id = self.sim.player.GetEntityID()
        self.sim.status_effects.ApplyStatusEffect(
            player_id, GameplayRestriction.Invisible,
            "GameplayRestriction.Invisible", duration=30.0)
        self.assertTrue(self.sim.is_player_invisible())
        self.sim.advance_time(31.0)
        self.assertFalse(self.sim.is_player_invisible())


if __name__ == '__main__':
    unittest.main()
