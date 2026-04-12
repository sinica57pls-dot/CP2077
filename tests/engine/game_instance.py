"""
RED4 Engine Simulation -- GameInstance Facade & Global Functions
===============================================================

Mirrors the global accessors that mods use:
  GameInstance.GetDynamicEntitySystem()
  GameInstance.GetDelaySystem()
  GameInstance.GetCallbackSystem()
  GameInstance.GetSystemRequestsHandler()
  GetPlayer()
  ModLog(), SqrtF(), Cast(), IsDefined(), etc.
"""

import math
from .types import FixedPoint


# ── Module-level state (set by GameSimulation) ──────────────────────

_current_des = None
_current_delay = None
_current_callback = None
_current_sys_handler = None
_current_systems_container = None
_current_player = None
_log_buffer = []


def _reset_globals():
    global _current_des, _current_delay, _current_callback
    global _current_sys_handler, _current_systems_container
    global _current_player, _log_buffer
    _current_des = None
    _current_delay = None
    _current_callback = None
    _current_sys_handler = None
    _current_systems_container = None
    _current_player = None
    _log_buffer = []


# ── GameInstance ────────────────────────────────────────────────────

class GameInstance:
    """Static facade -- delegates to the current simulation's systems."""

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


# ── Global functions (Redscript builtins) ───────────────────────────

def GetPlayer(game_instance=None):
    return _current_player


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
