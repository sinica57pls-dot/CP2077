"""
RED4 Engine Simulation -- GameSimulation Orchestrator
=====================================================

Creates a fresh, fully wired game engine instance for each test.
Provides high-level helpers for common test operations.

Usage in tests:
    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()
"""

import math
from .types import (Vector4, Quaternion, EntityID, EInputKey, EInputAction)
from .entity import (Entity, PlayerPuppet, NPCPuppet, DynamicEntitySpec)
from .systems import (DynamicEntitySystem, DelaySystem, CallbackSystem,
                      SystemRequestsHandler, ScriptableSystemsContainer,
                      KeyInputEvent, GameSessionEvent)
from . import game_instance as gi


class GameSimulation:
    """Complete simulated game engine instance."""

    def __init__(self):
        # Create fresh systems
        self.des = DynamicEntitySystem()
        self.delay = DelaySystem()
        self.callback = CallbackSystem()
        self.sys_handler = SystemRequestsHandler()
        self.systems_container = ScriptableSystemsContainer()
        self.player = None

        # Wire into global module state
        gi._current_des = self.des
        gi._current_delay = self.delay
        gi._current_callback = self.callback
        gi._current_sys_handler = self.sys_handler
        gi._current_systems_container = self.systems_container
        gi._current_player = None
        gi._log_buffer = []

        # Reset entity ID counter for deterministic tests
        EntityID.reset_counter()

    def teardown(self):
        """Clean up -- call in test tearDown()."""
        gi._reset_globals()

    # ── Session management ──────────────────────────────────────────

    def start_session(self, player_pos=(0, 0, 0), player_yaw=0):
        """Simulate loading a save or starting new game."""
        self.sys_handler._is_pregame = False
        self.des.OnWorldAttached()
        self.des.OnStreamingWorldLoaded()

        self.player = PlayerPuppet(
            position=Vector4(*player_pos, 0),
            orientation=Quaternion.from_yaw(player_yaw),
        )
        gi._current_player = self.player
        return self.player

    def end_session(self):
        """Simulate returning to main menu."""
        # Dispatch session end event
        self.callback.DispatchEvent("Session/BeforeEnd", GameSessionEvent())
        self.des.OnAfterWorldDetach()
        self.player = None
        gi._current_player = None
        self.sys_handler._is_pregame = True

    # ── Entity helpers ──────────────────────────────────────────────

    def spawn_npc(self, tags, pos, yaw=0):
        """Spawn a tagged NPC at the given position.  Returns the Entity."""
        npc = NPCPuppet(
            position=Vector4(*pos, 0),
            orientation=Quaternion.from_yaw(yaw),
        )
        self.des.AddEntity(npc, tags)
        return npc

    def move_player(self, pos, yaw=None):
        """Teleport player to a new position."""
        if self.player:
            self.player._position = Vector4(*pos, 0)
            if yaw is not None:
                self.player._orientation = Quaternion.from_yaw(yaw)

    # ── Time & tick management ──────────────────────────────────────

    def tick(self, count=1, interval=0.25):
        """Advance the engine by count ticks of interval seconds each."""
        total_fired = 0
        for _ in range(count):
            total_fired += self.delay.Tick(interval)
        return total_fired

    def advance_time(self, seconds):
        """Advance engine time by exactly `seconds`."""
        return self.delay.Tick(seconds)

    # ── Input simulation ────────────────────────────────────────────

    def press_key(self, key=EInputKey.IK_F6):
        """Simulate pressing a key (dispatches Input/Key event)."""
        evt = KeyInputEvent(key=key, action=EInputAction.IACT_Press)
        self.callback.DispatchEvent("Input/Key", evt)

    # ── Log access ──────────────────────────────────────────────────

    def get_log(self):
        return gi.get_log()

    def clear_log(self):
        gi.clear_log()

    # ── Utilities ───────────────────────────────────────────────────

    @staticmethod
    def distance(a, b):
        """3D distance between two Vector4s."""
        return a.distance_to(b)
