"""
RED4 Engine Simulation -- GameSimulation Orchestrator
=====================================================

Creates a fully wired game engine instance for each test, including:
  - Core engine: DES, DelaySystem, CallbackSystem
  - Game mechanics: TweakDB, Stats, Combat, Inventory, Quests
  - World systems (AMM): GodMode, Teleport, StaticEntities, Workspot,
    Targeting, Mappins, Weather, Time, StatusEffects

v2: Added AMM-facing world systems and stress-test helpers.
"""

import time as _time
from typing import List, Optional

from .types import Vector4, Quaternion, EntityID, EInputKey, EInputAction
from .entity import Entity, PlayerPuppet, NPCPuppet, DynamicEntitySpec
from .systems import (DynamicEntitySystem, DelaySystem, CallbackSystem,
                      SystemRequestsHandler, ScriptableSystemsContainer,
                      KeyInputEvent, GameSessionEvent)
from .tweakdb import TweakDB
from .stats import CharacterStats, NPCStats, StatsSystem
from .inventory import TransactionSystem, EquipmentSystem, ItemID, StreetCredSystem
from .combat import DamageSystem, HitFlag
from .quests import QuestSystem, QuestPhase
from .world import (GodModeSystem, TeleportationFacility, StaticEntitySystem,
                    WorkspotSystem, TargetingSystem, MappinSystem,
                    WeatherSystem, GameTimeSystem, GameplayStatusEffectSystem,
                    ObserverRegistry, gameGodModeType, EulerAngles,
                    StaticEntitySpec, GameplayRestriction)
from .appearance import AppearanceDatabase, AppearanceTriggerSystem
from .ai import (AIFollowerRole, AINoRole, AIRole, EAIAttitude,
                 AIFollowTargetCommand, AITeleportCommand)
from . import game_instance as gi


class GameSimulation:
    """
    Complete offline CP2077 engine instance for testing.

    Usage:
        sim = GameSimulation()
        sim.start_session(player_pos=(0, 0, 0))
        npc = sim.spawn_npc(tags=["AMM_NPC", "Companion"], pos=(5, 0, 0))
        sim.set_companion(npc)
        sim.tick(4)
        sim.teardown()
    """

    def __init__(self):
        # ── Core engine ─────────────────────────────────────────────────────────
        self.des               = DynamicEntitySystem()
        self.delay             = DelaySystem()
        self.callback          = CallbackSystem()
        self.sys_handler       = SystemRequestsHandler()
        self.systems_container = ScriptableSystemsContainer()
        self.player: Optional[PlayerPuppet] = None

        # ── TweakDB ──────────────────────────────────────────────────────────────
        TweakDB.Reset()
        self.tweakdb = TweakDB.Get()

        # ── Game mechanics ───────────────────────────────────────────────────────
        self.transaction  = TransactionSystem()
        self.equipment    = EquipmentSystem(self.transaction)
        self.quests       = QuestSystem()
        self.street_cred  = StreetCredSystem()
        self.player_stats = CharacterStats()

        # ── World systems (AMM) ──────────────────────────────────────────────────
        self.god_mode        = GodModeSystem()
        self.teleport        = TeleportationFacility()
        self.static_entities = StaticEntitySystem()
        self.workspot        = WorkspotSystem()
        self.targeting       = TargetingSystem()
        self.mappins         = MappinSystem()
        self.weather         = WeatherSystem()
        self.time_system     = GameTimeSystem()
        self.status_effects  = GameplayStatusEffectSystem()
        self.observers       = ObserverRegistry()

        # ── Appearance layer ─────────────────────────────────────────────────────
        self.appearance_db      = AppearanceDatabase()
        self.appearance_triggers = AppearanceTriggerSystem()

        # ── Wire into GameInstance globals ───────────────────────────────────────
        gi._current_des               = self.des
        gi._current_delay             = self.delay
        gi._current_callback          = self.callback
        gi._current_sys_handler       = self.sys_handler
        gi._current_systems_container = self.systems_container
        gi._current_player            = None
        gi._current_transaction       = self.transaction
        gi._current_equipment         = self.equipment
        gi._current_quests            = self.quests
        gi._current_street_cred       = self.street_cred
        gi._current_god_mode          = self.god_mode
        gi._current_teleport          = self.teleport
        gi._current_static_entities   = self.static_entities
        gi._current_workspot          = self.workspot
        gi._current_targeting         = self.targeting
        gi._current_mappins           = self.mappins
        gi._current_weather           = self.weather
        gi._current_time_system       = self.time_system
        gi._current_status_effects    = self.status_effects
        gi._current_observers         = self.observers
        gi._log_buffer                = []

        EntityID.reset_counter()

    # ── Session lifecycle ────────────────────────────────────────────────────────

    def teardown(self):
        gi._reset_globals()
        TweakDB.Reset()

    def start_session(self, player_pos=(0, 0, 0), player_yaw: float = 0):
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
        self.callback.DispatchEvent("Session/BeforeEnd", GameSessionEvent())
        self.des.OnAfterWorldDetach()
        self.player = None
        gi._current_player = None
        self.sys_handler._is_pregame = True

    # ── Entity spawning ──────────────────────────────────────────────────────────

    def spawn_npc(self, tags, pos, yaw: float = 0,
                  npc_stats: Optional[NPCStats] = None,
                  appearance: str = "default") -> NPCPuppet:
        npc = NPCPuppet(
            position=Vector4(*pos, 0),
            orientation=Quaternion.from_yaw(yaw),
            appearance=appearance,
        )
        if npc_stats is not None:
            npc._npc_stats = npc_stats
        self.des.AddEntity(npc, tags)
        return npc

    def spawn_npc_bulk(self, count: int, base_tags=None,
                       base_pos=(0, 0, 0)) -> List[NPCPuppet]:
        """Spawn many NPCs efficiently (stress test helper)."""
        base_tags = base_tags or ["AMM_NPC"]
        bx, by, bz = base_pos
        npcs: List[NPCPuppet] = []
        for i in range(count):
            npc = self.spawn_npc(
                tags=base_tags,
                pos=(bx + i * 2.0, by, bz),
            )
            npcs.append(npc)
        return npcs

    def despawn_npc(self, npc: NPCPuppet):
        eid = npc.GetEntityID()
        if npc._mappin_id >= 0:
            self.mappins.UnregisterMappin(npc._mappin_id)
        self.des.DeleteEntity(eid)
        npc.Invalidate()

    # ── Companion helpers ────────────────────────────────────────────────────────

    def set_companion(self, npc: NPCPuppet,
                      player: Optional[PlayerPuppet] = None,
                      follow_distance: float = 2.0) -> NPCPuppet:
        """
        SetNPCAsCompanion logic (mirrors AMM Spawn:SetNPCAsCompanion).
        Sets AIFollowerRole, marks entity as companion, aligns attitudes.
        """
        target = player or self.player
        role = AIFollowerRole(follower_ref=target,
                              follow_distance=follow_distance)
        npc.GetAIControllerComponent().SetAIRole(role)
        npc.SetIsCompanion(True)
        npc.GetAttitudeAgent().SetAttitudeGroup("PlayerAllies")
        if target is not None:
            npc.GetAttitudeAgent().SetAttitudeTowards(
                target.GetAttitudeAgent(), EAIAttitude.AIA_Friendly)
        return npc

    def toggle_hostile(self, npc: NPCPuppet):
        """Mirror AMM's Spawn:ToggleHostile()."""
        ctrl = npc.GetAIControllerComponent()
        if ctrl.IsFollower():
            ctrl.SetAIRole(AIRole("Ganger_Aggressive"))
            npc.GetAttitudeAgent().SetAttitudeGroup("Ganger_Aggressive")
            npc.SetIsCompanion(False)
        else:
            self.set_companion(npc)

    def set_god_mode(self, npc: NPCPuppet, immortal: bool = True):
        eid = npc.GetEntityID()
        if immortal:
            self.god_mode.AddGodMode(eid, gameGodModeType.Immortal, "AMM_GodMode")
        else:
            self.god_mode.ClearGodMode(eid, "AMM_GodMode")

    def issue_follow_command(self, npc: NPCPuppet, distance: float = 2.0):
        cmd = AIFollowTargetCommand(target=self.player, distance=distance)
        npc.GetAIControllerComponent().SendCommand(cmd)

    def update_follow_distances(self, companions: List[NPCPuppet]):
        """
        AMM's tiered follow-distance logic:
          1-2 → 2.0 m,  3 → 3.5 m,  4+ → 5.0 m
        """
        n = len(companions)
        dist = 2.0 if n <= 2 else (3.5 if n == 3 else 5.0)
        for npc in companions:
            if npc.GetAIControllerComponent().IsFollower():
                self.issue_follow_command(npc, distance=dist)

    def check_companion_distances(self, companions: List[NPCPuppet],
                                   threshold: float = 15.0) -> List[NPCPuppet]:
        """
        Re-issue follow command for companions that strayed > threshold.
        Returns companions that needed reissue.
        """
        if self.player is None:
            return []
        player_pos = self.player.GetWorldPosition()
        lagging: List[NPCPuppet] = []
        for npc in companions:
            if not npc.GetAIControllerComponent().IsFollower():
                continue
            if player_pos.distance_to(npc.GetWorldPosition()) > threshold:
                self.issue_follow_command(npc)
                lagging.append(npc)
        return lagging

    # ── Appearance helpers ────────────────────────────────────────────────────────

    def change_appearance(self, npc: NPCPuppet, app_name: str,
                          prefetch: bool = True):
        if prefetch:
            npc.PrefetchAppearanceChange(app_name)
        npc.ScheduleAppearanceChange(app_name)

    # ── Teleport helpers ──────────────────────────────────────────────────────────

    def teleport_entity(self, entity, pos, yaw: float = 0.0):
        self.teleport.Teleport(entity, Vector4(*pos, 0), EulerAngles(yaw=yaw))

    def teleport_npc_via_command(self, npc: NPCPuppet, pos, yaw: float = 0.0):
        cmd = AITeleportCommand(position=Vector4(*pos, 0), yaw=yaw)
        npc.GetAIControllerComponent().SendCommand(cmd)

    # ── Player visibility (AMM passive mode) ────────────────────────────────────

    def set_player_invisible(self, invisible: bool = True):
        if self.player is None:
            return
        eid = self.player.GetEntityID()
        if invisible:
            self.status_effects.ApplyStatusEffect(
                eid, GameplayRestriction.Invisible,
                "GameplayRestriction.Invisible")
        else:
            self.status_effects.RemoveStatusEffect(
                eid, GameplayRestriction.Invisible)

    def is_player_invisible(self) -> bool:
        if self.player is None:
            return False
        return self.status_effects.ObjectHasStatusEffect(
            self.player, GameplayRestriction.Invisible)

    # ── Standard mechanics helpers ───────────────────────────────────────────────

    def move_player(self, pos, yaw: Optional[float] = None):
        if self.player:
            self.player._position = Vector4(*pos, 0)
            if yaw is not None:
                self.player._orientation = Quaternion.from_yaw(yaw)

    def tick(self, count: int = 1, interval: float = 0.25) -> int:
        total = 0
        for _ in range(count):
            total += self.delay.Tick(interval)
            self.status_effects.Tick(interval)
        return total

    def advance_time(self, seconds: float) -> int:
        result = self.delay.Tick(seconds)
        self.status_effects.Tick(seconds)
        return result

    def press_key(self, key=EInputKey.IK_F6):
        evt = KeyInputEvent(key=key, action=EInputAction.IACT_Press)
        self.callback.DispatchEvent("Input/Key", evt)

    def give_item(self, entity_id, record_path: str, amount: int = 1):
        record  = self.tweakdb.GetRecord(record_path)
        item_id = (ItemID.Create(record_path) if amount == 1
                   else ItemID.CreateQuery(record_path))
        self.transaction.AddItemToInventory(entity_id, item_id, amount, record)
        return item_id

    def give_money(self, entity_id, amount: int) -> int:
        self.transaction.AddMoney(entity_id, amount)
        return self.transaction.GetMoney(entity_id)

    def get_money(self, entity_id) -> int:
        return self.transaction.GetMoney(entity_id)

    def equip_item(self, entity_id, record_path: str, slot):
        item_id = self.give_item(entity_id, record_path)
        return self.equipment.EquipItem(entity_id, item_id, slot)

    def resolve_hit(self, weapon_record_path: str, target_stats,
                    flags=HitFlag.Normal, attacker_stats=None, rng_seed=None):
        weapon = self.tweakdb.GetRecord(weapon_record_path)
        stats  = attacker_stats if attacker_stats is not None else self.player_stats
        return DamageSystem.resolve_hit(
            attacker_stats=stats, weapon_record=weapon,
            target_stats=target_stats, flags=flags, rng_seed=rng_seed)

    def set_fact(self, name: str, value: int):
        self.quests.SetFact(name, value)

    def get_fact(self, name: str) -> int:
        return self.quests.GetFact(name)

    def get_log(self):
        return gi.get_log()

    def clear_log(self):
        gi.clear_log()

    # ── Performance measurement ──────────────────────────────────────────────────

    def timed(self, fn, label: str = "", warn_ms: float = 500.0):
        """Run fn(), return (result, elapsed_ms)."""
        t0 = _time.perf_counter()
        result = fn()
        elapsed_ms = (_time.perf_counter() - t0) * 1000.0
        return result, elapsed_ms

    @staticmethod
    def distance(a, b) -> float:
        return a.distance_to(b)
