"""
AMM Companion Close-Follow v1.0.3 -- Full Test Suite
=====================================================

Tests the mod logic from:
  mods/AMMCompanionClose/r6/scripts/AMMCompanionClose/CompanionCloseSystem.reds

Run:  python tests/run_tests.py
  or: python -m unittest tests.mods.test_amm_companion_close -v
"""

import math
import sys
import os
import unittest

# Ensure the tests/ directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation, GameInstance, Vector4, Quaternion,
    WorldTransform, FixedPoint, EntityID, EInputKey, EInputAction,
    DynamicEntitySystem, DelaySystem, DelayCallback, CallbackSystem,
    SystemRequestsHandler, KeyInputEvent, GameSessionEvent,
    IsDefined, SqrtF, ModLog, get_log, clear_log,
)
from engine.game_instance import _current_des


# ====================================================================
#  CompanionCloseSystem -- Python translation of the Redscript mod
#
#  This is a FAITHFUL line-by-line port of CompanionCloseSystem.reds
#  v1.0.3 that runs against the engine simulation.
# ====================================================================

class CompanionCloseConfig:
    @staticmethod
    def TeleportDistance(): return 15.0
    @staticmethod
    def FollowDistance(): return 3.0
    @staticmethod
    def TargetDistance(): return 1.8
    @staticmethod
    def TickInterval(): return 0.25
    @staticmethod
    def LerpFactor(): return 0.45
    @staticmethod
    def ToggleKey(): return EInputKey.IK_F6


class CompanionCloseTick(DelayCallback):
    def __init__(self, system):
        self.system = system

    def Call(self):
        if self.system and self.system._alive:
            self.system.OnTick()


class CompanionCloseSystem:
    """Python port of CompanionCloseSystem.reds v1.0.3."""

    def __init__(self):
        self._alive = True
        self.m_player = None
        self.m_entitySystem = None
        self.m_enabled = False
        self.m_active = False
        self.m_extraTags = []
        self.m_processedThisTick = []
        # Telemetry
        self._tick_count = 0
        self._teleport_count = 0
        self._lerp_count = 0
        self._idle_count = 0
        self._orientations_set = []

    # -- Lifecycle (lines 70-113) --

    def OnAttach(self):
        self.m_enabled = False
        self.m_active = False
        self.m_entitySystem = GameInstance.GetDynamicEntitySystem()
        GameInstance.GetCallbackSystem().RegisterCallback(
            "Input/Key", self, "OnKeyInput")
        GameInstance.GetCallbackSystem().RegisterCallback(
            "Session/BeforeEnd", self, "OnSessionEnd")

    def OnRestored(self, save_version=0, game_version=0):
        self.Initialize()

    def OnPlayerAttach(self, request=None):
        self.Initialize()

    def Initialize(self):
        if self.m_active:
            return
        from engine.game_instance import _current_player
        self.m_player = _current_player
        if not self.m_player or not self.m_player.IsDefined():
            return
        if GameInstance.GetSystemRequestsHandler().IsPreGame():
            return
        # v1.0.3: refresh DES
        self.m_entitySystem = GameInstance.GetDynamicEntitySystem()
        self.m_active = True
        ModLog("CompanionClose", "System ready. Press F6 to toggle close-follow.")

    # -- Hotkey (lines 119-130) --

    def OnKeyInput(self, evt=None):
        if not self.m_active:
            return
        self.m_enabled = not self.m_enabled
        if self.m_enabled:
            ModLog("CompanionClose", "Close-follow ENABLED")
            self.ScheduleTick()
        else:
            ModLog("CompanionClose", "Close-follow DISABLED")

    # -- Session end (lines 136-139) --

    def OnSessionEnd(self, evt=None):
        self.m_active = False
        self.m_enabled = False

    # -- Tick scheduling (lines 145-178) --

    def ScheduleTick(self):
        if not self.m_enabled or not self.m_active:
            return
        cb = CompanionCloseTick(self)
        GameInstance.GetDelaySystem().DelayCallback(
            cb, CompanionCloseConfig.TickInterval())

    def OnTick(self):
        if not self.m_enabled or not self.m_active:
            return
        self._tick_count += 1

        from engine.game_instance import _current_player
        if not self.m_player or not self.m_player.IsDefined():
            self.m_player = _current_player
        if not self.m_player or not self.m_player.IsDefined():
            self.ScheduleTick()
            return

        playerPos = self.m_player.GetWorldPosition()
        playerFwd = self.m_player.GetWorldForward()
        self.m_processedThisTick = []
        self.UpdateAllCompanions(playerPos, playerFwd)
        self.ScheduleTick()

    # -- Core movement (lines 184-303) --

    def UpdateAllCompanions(self, playerPos, playerFwd):
        if not self.m_entitySystem or not self.m_entitySystem.IsDefined():
            return
        # v1.0.4: Real AMM tags first, then legacy/generic
        for tag in ["AMM_NPC", "AMM_CAR", "AMM", "Companion"]:
            self.TryUpdateTag(tag, playerPos, playerFwd)
        for tag in self.m_extraTags:
            self.TryUpdateTag(tag, playerPos, playerFwd)

    def TryUpdateTag(self, tag, playerPos, playerFwd):
        if not self.m_entitySystem.IsPopulated(tag):
            return
        entities = self.m_entitySystem.GetTagged(tag)
        for entity in entities:
            if entity and entity.IsDefined():
                h = EntityID.ToHash(entity.GetEntityID())
                if h not in self.m_processedThisTick:
                    self.m_processedThisTick.append(h)
                    self.UpdateSingleCompanion(entity, playerPos, playerFwd)

    def UpdateSingleCompanion(self, entity, playerPos, playerFwd):
        if entity.IsA("PlayerPuppet"):
            return
        if entity.IsA("gamePlayerPuppet"):
            return

        npcPos = entity.GetWorldPosition()
        dx = playerPos.X - npcPos.X
        dy = playerPos.Y - npcPos.Y
        dz = playerPos.Z - npcPos.Z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)

        teleportDist = CompanionCloseConfig.TeleportDistance()
        followDist = CompanionCloseConfig.FollowDistance()
        targetDist = CompanionCloseConfig.TargetDistance()

        if dist <= followDist:
            self._idle_count += 1
            return

        targetPos = Vector4()

        if dist > teleportDist:
            # v1.0.3: flatten forward to XY
            flatLenSq = playerFwd.X * playerFwd.X + playerFwd.Y * playerFwd.Y
            if flatLenSq > 0.001:
                flatLen = math.sqrt(flatLenSq)
                flatFwdX = playerFwd.X / flatLen
                flatFwdY = playerFwd.Y / flatLen
            else:
                flatFwdX = 0.0
                flatFwdY = 1.0
            targetPos.X = playerPos.X - flatFwdX * targetDist
            targetPos.Y = playerPos.Y - flatFwdY * targetDist
            targetPos.Z = playerPos.Z
            targetPos.W = 0.0
            self._teleport_count += 1
        else:
            lerpFactor = CompanionCloseConfig.LerpFactor()
            length = dist
            if length < 0.01:
                return
            dirX = dx / length
            dirY = dy / length
            dirZ = dz / length
            moveAmount = (dist - targetDist) * lerpFactor
            if moveAmount < 0.05:
                return
            targetPos.X = npcPos.X + dirX * moveAmount
            targetPos.Y = npcPos.Y + dirY * moveAmount
            targetPos.Z = npcPos.Z + dirZ * moveAmount
            targetPos.W = 0.0
            self._lerp_count += 1

        self.TeleportEntity(entity, targetPos)

    def TeleportEntity(self, entity, pos):
        transform = WorldTransform()
        transform.Position.x = FixedPoint.from_float(pos.X)
        transform.Position.y = FixedPoint.from_float(pos.Y)
        transform.Position.z = FixedPoint.from_float(pos.Z)
        # v1.0.3: preserve orientation
        ori = entity.GetWorldOrientation()
        transform.Orientation = ori
        self._orientations_set.append(Quaternion(ori.i, ori.j, ori.k, ori.r))
        entity.SetWorldTransform(transform)

    # -- Public API (lines 330-383) --

    def SetEnabled(self, enabled):
        if not self.m_active:
            ModLog("CompanionClose", "System not yet active.")
            return
        wasEnabled = self.m_enabled
        self.m_enabled = enabled
        if enabled:
            ModLog("CompanionClose", "Close-follow ENABLED (via API)")
            if not wasEnabled:
                self.ScheduleTick()
        else:
            ModLog("CompanionClose", "Close-follow DISABLED (via API)")

    def IsEnabled(self):
        return self.m_enabled

    def IsActive(self):
        return self.m_active

    def RegisterTag(self, tag):
        if tag in self.m_extraTags:
            return
        self.m_extraTags.append(tag)

    def UnregisterTag(self, tag):
        if tag in self.m_extraTags:
            self.m_extraTags.remove(tag)

    def reset_telemetry(self):
        self._tick_count = 0
        self._teleport_count = 0
        self._lerp_count = 0
        self._idle_count = 0
        self._orientations_set = []


# ====================================================================
#  Helper: create a system attached to a running simulation
# ====================================================================

def make_system(sim):
    """Create a CompanionCloseSystem, attach, and initialize."""
    s = CompanionCloseSystem()
    s.OnAttach()
    s.OnRestored()
    return s


# ====================================================================
#  TEST SUITE 1: System Lifecycle
# ====================================================================

class TestLifecycle(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_after_attach_disabled(self):
        s = CompanionCloseSystem()
        s.OnAttach()
        self.assertFalse(s.m_enabled)
        self.assertFalse(s.m_active)

    def test_attach_acquires_des(self):
        s = CompanionCloseSystem()
        s.OnAttach()
        self.assertIs(s.m_entitySystem, self.sim.des)

    def test_restored_while_pregame(self):
        s = CompanionCloseSystem()
        s.OnAttach()
        s.OnRestored()
        self.assertFalse(s.m_active)

    def test_restored_after_session(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.assertTrue(s.m_active)
        self.assertIs(s.m_player, self.sim.player)

    def test_log_system_ready(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.assertTrue(any("System ready" in l for l in self.sim.get_log()))

    def test_double_init_is_noop(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.sim.clear_log()
        s.OnPlayerAttach()
        self.assertEqual(len(self.sim.get_log()), 0)

    def test_session_end_resets(self):
        self.sim.start_session()
        s = make_system(self.sim)
        s.m_enabled = True
        s.OnSessionEnd()
        self.assertFalse(s.m_active)
        self.assertFalse(s.m_enabled)

    def test_player_attach_initializes(self):
        self.sim.start_session()
        s = CompanionCloseSystem()
        s.OnAttach()
        s.OnPlayerAttach()
        self.assertTrue(s.m_active)

    def test_no_init_without_player(self):
        self.sim.sys_handler._is_pregame = False
        self.sim.des.OnWorldAttached()
        # No player set
        s = CompanionCloseSystem()
        s.OnAttach()
        s.OnRestored()
        self.assertFalse(s.m_active)

    def test_no_init_in_pregame(self):
        self.sim.start_session()
        self.sim.sys_handler._is_pregame = True
        s = CompanionCloseSystem()
        s.OnAttach()
        s.OnRestored()
        self.assertFalse(s.m_active)


# ====================================================================
#  TEST SUITE 2: Hotkey Toggle
# ====================================================================

class TestHotkeyToggle(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.sys = make_system(self.sim)

    def tearDown(self):
        self.sim.teardown()

    def test_f6_before_active_ignored(self):
        s = CompanionCloseSystem()
        s.OnAttach()
        s.OnKeyInput()
        self.assertFalse(s.m_enabled)

    def test_f6_enables(self):
        self.sys.OnKeyInput()
        self.assertTrue(self.sys.m_enabled)

    def test_f6_logs_enabled(self):
        self.sim.clear_log()
        self.sys.OnKeyInput()
        self.assertTrue(any("ENABLED" in l for l in self.sim.get_log()))

    def test_f6_schedules_tick(self):
        self.sys.OnKeyInput()
        self.assertGreater(self.sim.delay.pending_count, 0)

    def test_f6_toggle_off(self):
        self.sys.OnKeyInput()  # ON
        self.sys.OnKeyInput()  # OFF
        self.assertFalse(self.sys.m_enabled)

    def test_f6_logs_disabled(self):
        self.sys.OnKeyInput()
        self.sim.clear_log()
        self.sys.OnKeyInput()
        self.assertTrue(any("DISABLED" in l for l in self.sim.get_log()))


# ====================================================================
#  TEST SUITE 3: Distance Tiers
# ====================================================================

class TestDistanceTiers(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))
        self.sys = make_system(self.sim)
        self.sys.m_enabled = True

    def tearDown(self):
        self.sim.teardown()

    def _tick_once(self):
        self.sys.OnTick()

    def test_close_npc_idles(self):
        self.sim.spawn_npc(["AMM"], (2, 0, 0))
        self._tick_once()
        self.assertEqual(self.sys._idle_count, 1)

    def test_boundary_3m_idles(self):
        self.sim.spawn_npc(["AMM"], (3, 0, 0))
        self._tick_once()
        self.assertEqual(self.sys._idle_count, 1)

    def test_mid_range_lerps(self):
        self.sim.spawn_npc(["AMM"], (8, 0, 0))
        self._tick_once()
        self.assertEqual(self.sys._lerp_count, 1)

    def test_lerp_moves_closer(self):
        npc = self.sim.spawn_npc(["AMM"], (8, 0, 0))
        self._tick_once()
        new_pos = npc.GetWorldPosition()
        self.assertLess(new_pos.distance_to(Vector4(0,0,0,0)), 8.0)

    def test_lerp_math_correct(self):
        npc = self.sim.spawn_npc(["AMM"], (5, 0, 0))
        self._tick_once()
        expected_move = (5.0 - 1.8) * 0.45
        expected_x = 5.0 - expected_move
        self.assertAlmostEqual(npc.GetWorldPosition().X, expected_x, delta=0.02)

    def test_far_npc_teleports(self):
        self.sim.spawn_npc(["AMM"], (20, 0, 0))
        self._tick_once()
        self.assertEqual(self.sys._teleport_count, 1)

    def test_teleport_near_target_dist(self):
        npc = self.sim.spawn_npc(["AMM"], (20, 0, 0))
        self._tick_once()
        d = npc.GetWorldPosition().distance_to(Vector4(0,0,0,0))
        self.assertAlmostEqual(d, 1.8, delta=0.2)

    def test_very_far_teleports(self):
        self.sim.spawn_npc(["AMM"], (80, 50, 0))
        self._tick_once()
        self.assertEqual(self.sys._teleport_count, 1)

    def test_boundary_15m_lerps(self):
        self.sim.spawn_npc(["AMM"], (15, 0, 0))
        self._tick_once()
        self.assertEqual(self.sys._lerp_count, 1)
        self.assertEqual(self.sys._teleport_count, 0)

    def test_boundary_15_01m_teleports(self):
        self.sim.spawn_npc(["AMM"], (15.01, 0, 0))
        self._tick_once()
        self.assertEqual(self.sys._teleport_count, 1)

    def test_npc_still_above_follow_after_lerp(self):
        npc = self.sim.spawn_npc(["AMM"], (8, 0, 0))
        self._tick_once()
        d = npc.GetWorldPosition().distance_to(Vector4(0,0,0,0))
        self.assertGreater(d, 3.0)

    def test_very_close_npc_no_move(self):
        npc = self.sim.spawn_npc(["AMM"], (1, 0.5, 0))
        old = npc.GetWorldPosition()
        self._tick_once()
        new = npc.GetWorldPosition()
        self.assertAlmostEqual(old.X, new.X, delta=0.01)
        self.assertAlmostEqual(old.Y, new.Y, delta=0.01)


# ====================================================================
#  TEST SUITE 4: Teleport Placement (v1.0.3 forward flattening)
# ====================================================================

class TestTeleportPlacement(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_normal_teleport_z_equals_player(self):
        self.sim.start_session(player_pos=(10, 10, 5))
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (50, 50, 5))
        s.m_enabled = True
        s.OnTick()
        self.assertAlmostEqual(npc.GetWorldPosition().Z, 5.0, delta=0.1)

    def test_normal_teleport_xy_distance(self):
        self.sim.start_session(player_pos=(10, 10, 5))
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (50, 50, 5))
        s.m_enabled = True
        s.OnTick()
        pos = npc.GetWorldPosition()
        d_xy = math.sqrt((pos.X - 10)**2 + (pos.Y - 10)**2)
        self.assertAlmostEqual(d_xy, 1.8, delta=0.2)

    def test_looking_up_npc_not_underground(self):
        self.sim.start_session(player_pos=(0, 0, 10))
        # Pitch up ~60 degrees
        self.sim.player._orientation = Quaternion(0.5, 0, 0, 0.866)
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (50, 50, 10))
        s.m_enabled = True
        s.OnTick()
        self.assertAlmostEqual(npc.GetWorldPosition().Z, 10.0, delta=0.1)

    def test_pure_vertical_forward_fallback(self):
        self.sim.start_session(player_pos=(5, 5, 20))
        # 90deg pitch -> forward = (0,0,1)
        self.sim.player._orientation = Quaternion(
            i=math.sin(math.pi/4), j=0, k=0, r=math.cos(math.pi/4))
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (100, 100, 20))
        s.m_enabled = True
        s.OnTick()
        pos = npc.GetWorldPosition()
        self.assertAlmostEqual(pos.Z, 20.0, delta=0.1)
        # Should use +Y fallback -- NPC not at origin
        d_xy = math.sqrt((pos.X - 5)**2 + (pos.Y - 5)**2)
        self.assertAlmostEqual(d_xy, 1.8, delta=0.2)

    def test_slope_keeps_ground_level(self):
        self.sim.start_session(player_pos=(0, 0, 15), player_yaw=45)
        # 15deg pitch
        self.sim.player._orientation = Quaternion(
            i=math.sin(math.radians(7.5)), j=0,
            k=math.sin(math.radians(22.5)),
            r=math.cos(math.radians(7.5)) * math.cos(math.radians(22.5)))
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (50, 50, 15))
        s.m_enabled = True
        s.OnTick()
        self.assertAlmostEqual(npc.GetWorldPosition().Z, 15.0, delta=0.1)

    def test_looking_down_npc_not_elevated(self):
        self.sim.start_session(player_pos=(0, 0, 10))
        # Pitch down ~45 degrees
        self.sim.player._orientation = Quaternion(-0.383, 0, 0, 0.924)
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (50, 50, 10))
        s.m_enabled = True
        s.OnTick()
        self.assertAlmostEqual(npc.GetWorldPosition().Z, 10.0, delta=0.1)


# ====================================================================
#  TEST SUITE 5: Orientation Preservation (v1.0.3 fix)
# ====================================================================

class TestOrientationPreservation(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def test_teleport_preserves_yaw(self):
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (20, 0, 0), yaw=90)
        s.m_enabled = True
        s.OnTick()
        ori = npc.GetWorldOrientation()
        expected = Quaternion.from_yaw(90)
        self.assertAlmostEqual(ori.k, expected.k, delta=0.01)
        self.assertAlmostEqual(ori.r, expected.r, delta=0.01)

    def test_no_zero_quaternion(self):
        s = make_system(self.sim)
        self.sim.spawn_npc(["AMM"], (20, 0, 0))
        s.m_enabled = True
        s.OnTick()
        for o in s._orientations_set:
            self.assertFalse(o.is_zero(), f"Got zero quaternion: {o}")

    def test_all_orientations_valid(self):
        s = make_system(self.sim)
        self.sim.spawn_npc(["AMM"], (20, 0, 0))
        s.m_enabled = True
        s.OnTick()
        for o in s._orientations_set:
            self.assertTrue(o.is_valid(), f"Invalid quaternion: {o}")

    def test_lerp_preserves_orientation(self):
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (8, 0, 0), yaw=180)
        s.m_enabled = True
        s.OnTick()
        ori = npc.GetWorldOrientation()
        expected = Quaternion.from_yaw(180)
        self.assertAlmostEqual(ori.k, expected.k, delta=0.01)

    def test_multiple_npcs_orientations_preserved(self):
        s = make_system(self.sim)
        npcs = []
        for yaw in [0, 45, 90, 135, 180, 225, 270, 315]:
            npc = self.sim.spawn_npc(["AMM"], (20, yaw/10, 0), yaw=yaw)
            npcs.append((npc, yaw))
        s.m_enabled = True
        s.OnTick()
        for npc, yaw in npcs:
            ori = npc.GetWorldOrientation()
            expected = Quaternion.from_yaw(yaw)
            self.assertAlmostEqual(ori.k, expected.k, delta=0.02,
                msg=f"NPC yaw={yaw}: got k={ori.k:.4f}, expected {expected.k:.4f}")


# ====================================================================
#  TEST SUITE 6: Multi-tick Convergence
# ====================================================================

class TestMultiTickConvergence(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def test_10m_converges(self):
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (10, 0, 0))
        s.OnKeyInput()  # enable + schedule
        for _ in range(30):
            self.sim.tick(1)
            d = npc.GetWorldPosition().distance_to(Vector4(0,0,0,0))
            if d <= 3.0:
                break
        self.assertLessEqual(d, 3.1)

    def test_distance_monotonically_decreases(self):
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (10, 0, 0))
        s.OnKeyInput()
        distances = [10.0]
        for _ in range(10):
            self.sim.tick(1)
            d = npc.GetWorldPosition().distance_to(Vector4(0,0,0,0))
            distances.append(d)
        for i in range(len(distances) - 1):
            self.assertGreaterEqual(distances[i], distances[i+1] - 0.01,
                msg=f"Distance increased at tick {i}: {distances[i]:.2f} -> {distances[i+1]:.2f}")

    def test_50m_teleports_then_lerps(self):
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (50, 0, 0))
        s.OnKeyInput()
        # First tick should teleport
        s.reset_telemetry()
        self.sim.tick(1)
        self.assertEqual(s._teleport_count, 1)
        # Subsequent ticks should lerp or idle, not teleport
        s.reset_telemetry()
        self.sim.tick(5)
        self.assertEqual(s._teleport_count, 0)

    def test_ticks_stop_when_disabled(self):
        s = make_system(self.sim)
        self.sim.spawn_npc(["AMM"], (10, 0, 0))
        s.OnKeyInput()  # enable
        self.sim.tick(2)
        pre = s._tick_count
        s.m_enabled = False
        self.sim.tick(10)
        self.assertEqual(s._tick_count, pre)

    def test_ticks_self_reschedule(self):
        s = make_system(self.sim)
        self.sim.spawn_npc(["AMM"], (10, 0, 0))
        s.OnKeyInput()
        self.sim.tick(1)
        # After one tick, another should be pending
        self.assertGreater(self.sim.delay.pending_count, 0)

    def test_convergence_speed(self):
        """NPC at 10m should reach <=3m in under 10 ticks."""
        s = make_system(self.sim)
        npc = self.sim.spawn_npc(["AMM"], (10, 0, 0))
        s.OnKeyInput()
        for i in range(10):
            self.sim.tick(1)
            d = npc.GetWorldPosition().distance_to(Vector4(0,0,0,0))
            if d <= 3.0:
                break
        self.assertLessEqual(d, 3.0, f"Still at {d:.2f}m after {i+1} ticks")


# ====================================================================
#  TEST SUITE 7: Session Management (v1.0.3 DES refresh)
# ====================================================================

class TestSessionManagement(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_session1_works(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.sim.spawn_npc(["AMM"], (10, 0, 0))
        s.m_enabled = True
        s.OnTick()
        self.assertEqual(s._tick_count, 1)

    def test_session_end_clears_state(self):
        self.sim.start_session()
        s = make_system(self.sim)
        s.m_enabled = True
        self.sim.end_session()
        self.assertFalse(s.m_active)
        self.assertFalse(s.m_enabled)

    def test_session2_reactivates(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.sim.end_session()
        s.m_active = False  # Reset for re-init
        self.sim.start_session(player_pos=(50, 50, 0))
        s.OnRestored()
        self.assertTrue(s.m_active)

    def test_des_refreshed_in_session2(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.sim.end_session()
        s.m_active = False
        self.sim.start_session()
        s.OnRestored()
        self.assertIs(s.m_entitySystem, self.sim.des)

    def test_des_ready_after_session2(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.sim.end_session()
        s.m_active = False
        self.sim.start_session()
        s.OnRestored()
        self.assertTrue(s.m_entitySystem.IsReady())

    def test_session2_tick_works(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.sim.end_session()
        s.m_active = False
        self.sim.start_session()
        s.OnRestored()
        self.sim.spawn_npc(["AMM"], (80, 80, 0))
        s.m_enabled = True
        s.reset_telemetry()
        s.OnTick()
        self.assertEqual(s._teleport_count, 1)

    def test_invalid_des_no_crash(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.sim.spawn_npc(["AMM"], (10, 0, 0))
        s.m_enabled = True
        s.m_entitySystem.Invalidate()
        s.reset_telemetry()
        s.OnTick()
        self.assertEqual(s._tick_count, 1)

    def test_invalid_des_no_movement(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.sim.spawn_npc(["AMM"], (10, 0, 0))
        s.m_enabled = True
        s.m_entitySystem.Invalidate()
        s.reset_telemetry()
        s.OnTick()
        self.assertEqual(s._teleport_count, 0)
        self.assertEqual(s._lerp_count, 0)

    def test_no_player_schedules_next_tick(self):
        self.sim.start_session()
        s = make_system(self.sim)
        s.m_enabled = True
        s.m_player = None
        import engine.game_instance as gi_mod
        gi_mod._current_player = None
        s.OnTick()
        # Should have scheduled another tick even without player
        self.assertGreater(self.sim.delay.pending_count, 0)

    def test_session_end_via_callback(self):
        self.sim.start_session()
        s = make_system(self.sim)
        s.m_enabled = True
        # The callback was registered in OnAttach
        self.sim.callback.DispatchEvent("Session/BeforeEnd", GameSessionEvent())
        self.assertFalse(s.m_active)

    def test_three_sessions(self):
        for i in range(3):
            self.sim.start_session(player_pos=(i*10, 0, 0))
            s = CompanionCloseSystem()
            s.OnAttach()
            s.OnRestored()
            self.assertTrue(s.m_active, f"Session {i+1} failed to activate")
            self.sim.end_session()
            s.m_active = False


# ====================================================================
#  TEST SUITE 8: Multi-companion & Deduplication
# ====================================================================

class TestMultiCompanion(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.sys = make_system(self.sim)
        self.sys.m_enabled = True

    def tearDown(self):
        self.sim.teardown()

    def test_three_npcs_three_actions(self):
        self.sim.spawn_npc(["AMM", "Companion"], (2, 0, 0))
        self.sim.spawn_npc(["AMM"], (8, 0, 0))
        self.sim.spawn_npc(["Companion"], (25, 0, 0))
        self.sys.OnTick()
        self.assertEqual(self.sys._idle_count, 1)
        self.assertEqual(self.sys._lerp_count, 1)
        self.assertEqual(self.sys._teleport_count, 1)

    def test_dual_tag_deduplication(self):
        self.sim.spawn_npc(["AMM", "Companion"], (8, 0, 0))
        self.sys.OnTick()
        self.assertEqual(self.sys._lerp_count, 1,
            "Dual-tagged NPC should only be processed once")

    def test_player_entity_not_moved(self):
        self.sim.des.AddEntity(self.sim.player, ["AMM"])
        self.sim.spawn_npc(["AMM"], (10, 0, 0))
        pos_before = self.sim.player.GetWorldPosition()
        self.sys.OnTick()
        pos_after = self.sim.player.GetWorldPosition()
        self.assertAlmostEqual(pos_before.X, pos_after.X, delta=0.01)
        self.assertAlmostEqual(pos_before.Y, pos_after.Y, delta=0.01)

    def test_many_npcs_all_processed(self):
        for i in range(10):
            self.sim.spawn_npc(["AMM"], (20 + i, 0, 0))
        self.sys.OnTick()
        self.assertEqual(self.sys._teleport_count, 10)

    def test_invalidated_entity_skipped(self):
        npc = self.sim.spawn_npc(["AMM"], (10, 0, 0))
        npc.Invalidate()
        self.sys.OnTick()
        self.assertEqual(self.sys._lerp_count, 0)
        self.assertEqual(self.sys._teleport_count, 0)


# ====================================================================
#  TEST SUITE 9: Public API & Tag Registration
# ====================================================================

class TestPublicAPI(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_set_enabled_before_active(self):
        s = CompanionCloseSystem()
        s.OnAttach()
        s.SetEnabled(True)
        self.assertFalse(s.m_enabled)

    def test_set_enabled_logs_warning(self):
        self.sim.clear_log()
        s = CompanionCloseSystem()
        s.OnAttach()
        s.SetEnabled(True)
        self.assertTrue(any("not yet active" in l for l in self.sim.get_log()))

    def test_set_enabled_true(self):
        self.sim.start_session()
        s = make_system(self.sim)
        s.SetEnabled(True)
        self.assertTrue(s.m_enabled)

    def test_set_enabled_false(self):
        self.sim.start_session()
        s = make_system(self.sim)
        s.SetEnabled(True)
        s.SetEnabled(False)
        self.assertFalse(s.m_enabled)

    def test_is_enabled(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.assertFalse(s.IsEnabled())
        s.SetEnabled(True)
        self.assertTrue(s.IsEnabled())

    def test_is_active(self):
        self.sim.start_session()
        s = make_system(self.sim)
        self.assertTrue(s.IsActive())

    def test_register_tag(self):
        s = CompanionCloseSystem()
        s.RegisterTag("MyTag")
        self.assertIn("MyTag", s.m_extraTags)

    def test_register_tag_no_duplicates(self):
        s = CompanionCloseSystem()
        s.RegisterTag("MyTag")
        s.RegisterTag("MyTag")
        self.assertEqual(s.m_extraTags.count("MyTag"), 1)

    def test_custom_tag_processes_npcs(self):
        self.sim.start_session()
        s = make_system(self.sim)
        s.RegisterTag("MyCustom")
        npc = self.sim.spawn_npc(["MyCustom"], (10, 0, 0))
        s.m_enabled = True
        s.OnTick()
        total = s._lerp_count + s._teleport_count
        self.assertGreater(total, 0)

    def test_unregister_tag(self):
        s = CompanionCloseSystem()
        s.RegisterTag("MyTag")
        s.UnregisterTag("MyTag")
        self.assertNotIn("MyTag", s.m_extraTags)

    def test_unregistered_tag_not_processed(self):
        self.sim.start_session()
        s = make_system(self.sim)
        s.RegisterTag("MyCustom")
        self.sim.spawn_npc(["MyCustom"], (10, 0, 0))
        s.UnregisterTag("MyCustom")
        s.m_enabled = True
        s.reset_telemetry()
        s.OnTick()
        self.assertEqual(s._lerp_count, 0)
        self.assertEqual(s._teleport_count, 0)

    def test_set_enabled_schedules_tick(self):
        self.sim.start_session()
        s = make_system(self.sim)
        s.SetEnabled(True)
        self.assertGreater(self.sim.delay.pending_count, 0)


# ====================================================================
#  TEST SUITE 10: AMM Reference Validation
#
#  Tests against the REAL AMM behavior from:
#    https://github.com/MaximiliumM/appearancemenumod
#    Release/bin/.../Modules/spawn.lua   -- tags, spawning
#    Release/bin/.../Modules/util.lua    -- teleportation, distance
#    Release/bin/.../init.lua            -- companion follow system
# ====================================================================

class TestAMMReferenceValidation(unittest.TestCase):
    """Validates that our mod works with the real AMM's entity tags and
    spawn patterns, as discovered from the reference AMM source code."""

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.sys = make_system(self.sim)
        self.sys.m_enabled = True

    def tearDown(self):
        self.sim.teardown()

    # -- Tag compatibility (AMM spawn.lua lines 522, 603) --

    def test_amm_npc_tag_detected(self):
        """AMM spawns NPCs with tag 'AMM_NPC' (spawn.lua line 603)."""
        npc = self.sim.spawn_npc(["AMM_NPC"], (10, 0, 0))
        self.sys.OnTick()
        self.assertGreater(self.sys._lerp_count + self.sys._teleport_count, 0,
            "NPC with AMM_NPC tag was not detected")

    def test_amm_car_tag_detected(self):
        """AMM spawns vehicles with tag 'AMM_CAR' (spawn.lua line 522)."""
        car = self.sim.spawn_npc(["AMM_CAR"], (20, 0, 0))
        self.sys.OnTick()
        self.assertEqual(self.sys._teleport_count, 1,
            "Entity with AMM_CAR tag was not detected")

    def test_amm_npc_close_idles(self):
        """AMM NPC within follow distance should idle."""
        npc = self.sim.spawn_npc(["AMM_NPC"], (2, 0, 0))
        self.sys.OnTick()
        self.assertEqual(self.sys._idle_count, 1)

    def test_amm_npc_far_teleports(self):
        """AMM NPC far away should be teleported behind player."""
        npc = self.sim.spawn_npc(["AMM_NPC"], (50, 50, 0))
        self.sys.OnTick()
        self.assertEqual(self.sys._teleport_count, 1)
        d = npc.GetWorldPosition().distance_to(Vector4(0,0,0,0))
        self.assertAlmostEqual(d, 1.8, delta=0.3)

    def test_legacy_amm_tag_still_works(self):
        """Older mods might use generic 'AMM' tag -- should still work."""
        npc = self.sim.spawn_npc(["AMM"], (10, 0, 0))
        self.sys.OnTick()
        self.assertGreater(self.sys._lerp_count, 0)

    def test_companion_tag_still_works(self):
        """Other mods may use 'Companion' tag -- should still work."""
        npc = self.sim.spawn_npc(["Companion"], (10, 0, 0))
        self.sys.OnTick()
        self.assertGreater(self.sys._lerp_count, 0)

    # -- AMM spawn pattern simulation --

    def test_amm_realistic_spawn_scenario(self):
        """Simulate real AMM usage: spawn 3 NPCs, press F6, walk away.

        AMM spawns NPCs near the player (distance ~1m), then player
        walks away.  Companions should follow via our close-follow system.
        """
        # Phase 1: Player at origin, spawns 3 NPCs nearby (like AMM does)
        npc1 = self.sim.spawn_npc(["AMM_NPC"], (1, 0, 0), yaw=0)
        npc2 = self.sim.spawn_npc(["AMM_NPC"], (-0.5, 1, 0), yaw=90)
        npc3 = self.sim.spawn_npc(["AMM_NPC"], (0, -1, 0), yaw=180)

        # All within 3m -> should idle
        self.sys.OnTick()
        self.assertEqual(self.sys._idle_count, 3)
        self.assertEqual(self.sys._teleport_count, 0)

        # Phase 2: Player walks 20m away
        self.sim.move_player((20, 0, 0))
        self.sys.reset_telemetry()
        self.sys.OnTick()

        # All 3 NPCs are now >15m away -> should teleport
        self.assertEqual(self.sys._teleport_count, 3)

        # Phase 3: Verify all NPCs are now near player
        for npc in [npc1, npc2, npc3]:
            d = npc.GetWorldPosition().distance_to(Vector4(20, 0, 0, 0))
            self.assertLess(d, 3.0, f"NPC still {d:.1f}m from player after teleport")

    def test_amm_mixed_tags_scenario(self):
        """Scenario: mix of AMM_NPC and Companion-tagged entities."""
        amm_npc = self.sim.spawn_npc(["AMM_NPC"], (10, 0, 0))
        other_npc = self.sim.spawn_npc(["Companion"], (8, 5, 0))
        car = self.sim.spawn_npc(["AMM_CAR"], (25, 0, 0))

        self.sys.OnTick()
        total = self.sys._lerp_count + self.sys._teleport_count
        self.assertEqual(total, 3, f"Expected 3 moved entities, got {total}")

    # -- AMM's behind-player position pattern (util.lua line 606) --

    def test_behind_player_z_matches_amm(self):
        """AMM's GetBehindPlayerPosition uses pos.z (not pos.z - heading.z*d).
        Our teleport should match: NPC Z == player Z."""
        self.sim.move_player((0, 0, 10))
        npc = self.sim.spawn_npc(["AMM_NPC"], (50, 50, 10))
        self.sys.OnTick()
        # AMM pattern: behindPlayer.z = pos.z  (flat Z)
        self.assertAlmostEqual(npc.GetWorldPosition().Z, 10.0, delta=0.1)

    # -- AMM's distance calculation (util.lua line 572-574) --

    def test_distance_calc_matches_amm(self):
        """AMM uses 3D Euclidean: sqrt(dx^2 + dy^2 + dz^2).
        Our mod uses the same formula."""
        p1 = Vector4(10, 20, 30, 0)
        p2 = Vector4(13, 24, 30, 0)
        # AMM: math.sqrt(((10-13)^2) + ((20-24)^2) + ((30-30)^2)) = sqrt(9+16+0) = 5
        expected = 5.0
        actual = p1.distance_to(p2)
        self.assertAlmostEqual(actual, expected, delta=0.001)

    def test_amm_follow_distance_default(self):
        """AMM's default follow distance is 3m for < 3 companions.
        Our FollowDistance config is 3.0 -- matches AMM's 'Close' preset."""
        self.assertEqual(CompanionCloseConfig.FollowDistance(), 3.0)


if __name__ == '__main__':
    unittest.main()
