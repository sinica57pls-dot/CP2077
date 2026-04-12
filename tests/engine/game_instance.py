"""
RED4 Engine Simulation -- GameInstance Facade & Global Functions
===============================================================

Mirrors the global accessors that mods use:
  GameInstance.GetDynamicEntitySystem()
  GameInstance.GetDelaySystem()
  GameInstance.GetCallbackSystem()
  GameInstance.GetSystemRequestsHandler()
  GameInstance.GetTransactionSystem()       -- inventory / items
  GameInstance.GetEquipmentSystem()         -- paperdoll equipment
  GameInstance.GetQuestsSystem()            -- facts + journal
  GameInstance.GetStatsSystem()             -- stat computation
  GameInstance.GetStreetCredSystem()        -- street cred progression
  GameInstance.GetGodModeSystem()           -- companion invincibility (NEW)
  GameInstance.GetTeleportationFacility()   -- player / NPC teleport (NEW)
  GameInstance.GetStaticEntitySystem()      -- prop spawning (NEW)
  GameInstance.GetWorkspotSystem()          -- workspot queries (NEW)
  GameInstance.GetTargetingSystem()         -- look-at / targeting (NEW)
  GameInstance.GetMappinSystem()            -- minimap pins (NEW)
  GameInstance.GetWeatherSystem()           -- weather control (NEW)
  GameInstance.GetTimeSystem()              -- time of day (NEW)
  GameInstance.GetStatusEffectSystem()      -- gameplay status effects (NEW)
  FindEntityByID()                          -- lookup entity by ID (NEW)
  GetPlayer()
  ModLog(), SqrtF(), Cast(), IsDefined(), etc.
"""

import math
from .types import FixedPoint


# ── Module-level state (set by GameSimulation) ──────────────────────────────

_current_des              = None
_current_delay            = None
_current_callback         = None
_current_sys_handler      = None
_current_systems_container = None
_current_player           = None
_current_transaction      = None   # TransactionSystem
_current_equipment        = None   # EquipmentSystem
_current_quests           = None   # QuestSystem
_current_street_cred      = None   # StreetCredSystem
# World systems (new)
_current_god_mode         = None   # GodModeSystem
_current_teleport         = None   # TeleportationFacility
_current_static_entities  = None   # StaticEntitySystem
_current_workspot         = None   # WorkspotSystem
_current_targeting        = None   # TargetingSystem
_current_mappins          = None   # MappinSystem
_current_weather          = None   # WeatherSystem
_current_time_system      = None   # GameTimeSystem
_current_status_effects   = None   # GameplayStatusEffectSystem
_current_observers        = None   # ObserverRegistry
_log_buffer               = []


def _reset_globals():
    global _current_des, _current_delay, _current_callback
    global _current_sys_handler, _current_systems_container
    global _current_player, _log_buffer
    global _current_transaction, _current_equipment
    global _current_quests, _current_street_cred
    global _current_god_mode, _current_teleport, _current_static_entities
    global _current_workspot, _current_targeting, _current_mappins
    global _current_weather, _current_time_system, _current_status_effects
    global _current_observers
    _current_des              = None
    _current_delay            = None
    _current_callback         = None
    _current_sys_handler      = None
    _current_systems_container = None
    _current_player           = None
    _current_transaction      = None
    _current_equipment        = None
    _current_quests           = None
    _current_street_cred      = None
    _current_god_mode         = None
    _current_teleport         = None
    _current_static_entities  = None
    _current_workspot         = None
    _current_targeting        = None
    _current_mappins          = None
    _current_weather          = None
    _current_time_system      = None
    _current_status_effects   = None
    _current_observers        = None
    _log_buffer               = []


# ── GameInstance ────────────────────────────────────────────────────────────

class GameInstance:
    """Static facade -- delegates to the current simulation's systems.

    All methods are @staticmethod to match the REDscript / CET Lua pattern:
      GameInstance.GetDynamicEntitySystem()
      Game.GetGodModeSystem()          (CET uses Game.* prefix)
    """

    @staticmethod
    def GetDynamicEntitySystem():
        return _current_des

    @staticmethod
    def GetDelaySystem(game_instance=None):
        return _current_delay

    @staticmethod
    def GetCallbackSystem():
        return _current_callback

    @staticmethod
    def GetSystemRequestsHandler():
        return _current_sys_handler

    @staticmethod
    def GetScriptableSystemsContainer(game_instance=None):
        return _current_systems_container

    @staticmethod
    def GetTransactionSystem():
        """Inventory / item transaction system."""
        return _current_transaction

    @staticmethod
    def GetEquipmentSystem():
        """Equipment paperdoll system."""
        return _current_equipment

    @staticmethod
    def GetQuestsSystem():
        """Quest system -- facts, journal, phase execution."""
        return _current_quests

    @staticmethod
    def GetStatsSystem():
        """Returns the StatsSystem class (stat computation is stateless)."""
        from .stats import StatsSystem
        return StatsSystem

    @staticmethod
    def GetStreetCredSystem():
        """Street Cred progression system."""
        return _current_street_cred

    # ── New world systems (AMM) ───────────────────────────────────────────────

    @staticmethod
    def GetGodModeSystem():
        """Companion / player immortality system."""
        return _current_god_mode

    @staticmethod
    def GetTeleportationFacility():
        """Player and NPC teleportation."""
        return _current_teleport

    @staticmethod
    def GetStaticEntitySystem():
        """Prop / scene object spawning."""
        return _current_static_entities

    @staticmethod
    def GetWorkspotSystem():
        """Workspot / animation slot queries."""
        return _current_workspot

    @staticmethod
    def GetTargetingSystem():
        """Look-at target and combat targeting."""
        return _current_targeting

    @staticmethod
    def GetMappinSystem():
        """Minimap pin registration."""
        return _current_mappins

    @staticmethod
    def GetWeatherSystem():
        """In-game weather control."""
        return _current_weather

    @staticmethod
    def GetTimeSystem():
        """In-game time of day control."""
        return _current_time_system

    @staticmethod
    def GetStatusEffectSystem():
        """Gameplay status effects (invisibility, restrictions, etc.)."""
        return _current_status_effects

    @staticmethod
    def GetObserverRegistry():
        """CET-style Observe / Override hook registry."""
        return _current_observers


# ── Global functions (Redscript builtins / CET Game.*) ───────────────────────

def GetPlayer(game_instance=None):
    return _current_player


def FindEntityByID(entity_id, game_instance=None):
    """
    Game.FindEntityByID(entityID) -- AMM polls this after CreateEntity.
    Returns the entity handle or None if not yet spawned.
    """
    if _current_des is None:
        return None
    return _current_des.GetEntity(entity_id)


def IsDefined(obj):
    if obj is None:
        return False
    if hasattr(obj, 'IsDefined'):
        return obj.IsDefined()
    return True


def SqrtF(val):
    return math.sqrt(val)


def Cast(float_val):
    """Cast Float -> FixedPoint (used by WorldPosition assignment)."""
    return FixedPoint.from_float(float_val)


def Equals(a, b):
    return a == b


def ArraySize(arr):
    return len(arr)


def ArrayClear(arr):
    arr.clear()


def ArrayPush(arr, item):
    arr.append(item)


def ArrayErase(arr, index):
    if 0 <= index < len(arr):
        arr.pop(index)


def NameToString(cname):
    return str(cname)


def ModLog(mod_name, text):
    """Captures log output for test assertions."""
    _log_buffer.append(f"[{mod_name}] {text}")


def get_log():
    """Returns captured ModLog messages (for test assertions)."""
    return list(_log_buffer)


def clear_log():
    _log_buffer.clear()
