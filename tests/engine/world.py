"""
World Systems
=============
Simulates CP2077's world-level game systems used extensively by AMM.

Systems provided:
  TeleportationFacility   -- Teleport(entity, position, eulerAngles)
  GodModeSystem           -- AddGodMode / ClearGodMode / IsImmortal
  StaticEntitySystem      -- prop / static object spawning (AMM scene builder)
  WorkspotSystem          -- IsActorInWorkspot (guards animation commands)
  TargetingSystem         -- GetLookAtObject / GetTargetParts
  MappinSystem            -- RegisterMappin / UnregisterMappin (minimap pins)
  WeatherSystem           -- SetWeather / GetActiveWeather
  GameTimeSystem          -- GetTime / SetTime / GetHour / GetMinute
  GameplayStatusEffectSystem -- AMM-style status effects (restrictions, invisi…)
  ObserverRegistry        -- lightweight Observe/Override hook simulation
"""

from __future__ import annotations
import enum
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
#  God Mode System
# ═══════════════════════════════════════════════════════════════════════════════

class gameGodModeType(enum.Enum):
    Mortal    = 0
    Immortal  = 1
    FullyDead = 2


class GodModeSystem:
    """
    Simulates Game.GetGodModeSystem().

    AMM uses this for companion invincibility:
      godMode.AddGodMode(eid, gameGodModeType.Immortal, n"AMM_GodMode")
      godMode.ClearGodMode(eid, n"AMM_GodMode")
    """

    def __init__(self):
        # entity_id -> { reason_str -> gameGodModeType }
        self._entries: Dict[Any, Dict[str, gameGodModeType]] = {}

    def AddGodMode(self, entity_id, mode: gameGodModeType,
                   reason: str = "AMM_GodMode"):
        if entity_id not in self._entries:
            self._entries[entity_id] = {}
        self._entries[entity_id][reason] = mode

    def ClearGodMode(self, entity_id, reason: str = "AMM_GodMode"):
        bucket = self._entries.get(entity_id)
        if bucket:
            bucket.pop(reason, None)
            if not bucket:
                del self._entries[entity_id]

    def HasGodMode(self, entity_id) -> bool:
        bucket = self._entries.get(entity_id, {})
        return any(t == gameGodModeType.Immortal for t in bucket.values())

    def IsImmortal(self, entity_id) -> bool:
        return self.HasGodMode(entity_id)

    def GetGodModeType(self, entity_id,
                       reason: str = "AMM_GodMode") -> Optional[gameGodModeType]:
        return self._entries.get(entity_id, {}).get(reason)

    def GetImmortalCount(self) -> int:
        return sum(1 for eid in self._entries
                   if self.HasGodMode(eid))

    def ClearAll(self):
        self._entries.clear()


# ═══════════════════════════════════════════════════════════════════════════════
#  Teleportation Facility
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EulerAngles:
    """Pitch / Roll / Yaw in degrees (CP2077 convention)."""
    pitch: float = 0.0
    roll:  float = 0.0
    yaw:   float = 0.0


class TeleportationFacility:
    """
    Simulates Game.GetTeleportationFacility().

    AMM uses:
      facility.Teleport(player, worldPos, eulerAngles)
      (NPC teleport uses AITeleportCommand sent via GetAIControllerComponent)
    """

    def __init__(self):
        self._log: List[dict] = []

    def Teleport(self, entity, position, euler: Optional[EulerAngles] = None) -> bool:
        """Move entity to position with optional yaw rotation."""
        from .types import Vector4, Quaternion

        if hasattr(entity, '_position'):
            if isinstance(position, Vector4):
                entity._position.X = position.X
                entity._position.Y = position.Y
                entity._position.Z = position.Z
            elif isinstance(position, (list, tuple)) and len(position) >= 3:
                entity._position.X = float(position[0])
                entity._position.Y = float(position[1])
                entity._position.Z = float(position[2])
            if euler is not None and hasattr(entity, '_orientation'):
                entity._orientation = Quaternion.from_yaw(euler.yaw)

        eid = entity.GetEntityID() if hasattr(entity, 'GetEntityID') else None
        self._log.append({"entity_id": eid, "position": position,
                          "yaw": euler.yaw if euler else 0.0})
        return True

    def GetTeleportLog(self) -> List[dict]:
        return list(self._log)

    def TeleportCount(self) -> int:
        return len(self._log)

    def GetLastTeleport(self) -> Optional[dict]:
        return self._log[-1] if self._log else None


# ═══════════════════════════════════════════════════════════════════════════════
#  Static Entity System  (prop / scene object spawning)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StaticEntitySpec:
    """Spawn spec for world props (StaticEntitySystem equivalent)."""
    entity_path:  str  = ""
    appear_name:  str  = ""
    position:     Any  = None    # Vector4
    orientation:  Any  = None    # Quaternion
    scale:        Any  = None    # Vector3
    tags:         list = field(default_factory=list)


class StaticEntity:
    """A spawned prop / static world object (AMM scene builder)."""

    def __init__(self, entity_id, spec: StaticEntitySpec):
        from .types import Vector4, Quaternion, Vector3
        self._entity_id   = entity_id
        self._position    = spec.position    or Vector4()
        self._orientation = spec.orientation or Quaternion.identity()
        self._scale       = spec.scale       or Vector3(1, 1, 1)
        self._appearance  = spec.appear_name
        self._tags        = list(spec.tags)
        self._alive       = True

    def GetEntityID(self):
        return self._entity_id

    def GetWorldPosition(self):
        return self._position

    def GetScale(self):
        return self._scale

    def SetScale(self, v):
        self._scale = v

    def IsDefined(self) -> bool:
        return self._alive

    def Dispose(self):
        self._alive = False


class StaticEntitySystem:
    """
    Simulates Game.GetStaticEntitySystem() for AMM's scene / prop builder.
    AMM spawns props as static entities (no AI, no animations).
    """

    def __init__(self):
        from .types import EntityID
        self._entities: Dict[Any, StaticEntity] = {}
        self._next_id = 9000

    def CreateEntity(self, spec: StaticEntitySpec) -> Tuple[Any, StaticEntity]:
        from .types import EntityID
        eid = EntityID(self._next_id)
        self._next_id += 1
        ent = StaticEntity(eid, spec)
        self._entities[eid] = ent
        return eid, ent

    def DeleteEntity(self, eid) -> bool:
        ent = self._entities.pop(eid, None)
        if ent:
            ent.Dispose()
            return True
        return False

    def GetEntity(self, eid) -> Optional[StaticEntity]:
        return self._entities.get(eid)

    def GetAllEntities(self) -> List[StaticEntity]:
        return [e for e in self._entities.values() if e.IsDefined()]

    def GetEntityCount(self) -> int:
        return sum(1 for e in self._entities.values() if e.IsDefined())

    def ClearAll(self):
        for ent in self._entities.values():
            ent.Dispose()
        self._entities.clear()


# ═══════════════════════════════════════════════════════════════════════════════
#  Workspot System
# ═══════════════════════════════════════════════════════════════════════════════

class WorkspotSystem:
    """
    Simulates Game.GetWorkspotSystem().

    AMM checks IsActorInWorkspot() before sending AIPlayAnimationCommand to
    avoid conflicts with active workspot animations.
    """

    def __init__(self):
        self._in_workspot: Set[Any] = set()   # entity_ids

    def IsActorInWorkspot(self, entity) -> bool:
        eid = entity.GetEntityID() if hasattr(entity, 'GetEntityID') else entity
        return eid in self._in_workspot

    def SetActorInWorkspot(self, entity, in_ws: bool):
        eid = entity.GetEntityID() if hasattr(entity, 'GetEntityID') else entity
        if in_ws:
            self._in_workspot.add(eid)
        else:
            self._in_workspot.discard(eid)

    def EvictActor(self, entity):
        self.SetActorInWorkspot(entity, False)

    def GetActorsInWorkspot(self) -> List[Any]:
        return list(self._in_workspot)


# ═══════════════════════════════════════════════════════════════════════════════
#  Targeting System
# ═══════════════════════════════════════════════════════════════════════════════

class TargetingSystem:
    """
    Simulates Game.GetTargetingSystem().

    AMM uses GetLookAtObject() to find the currently aimed-at entity
    (for appearance editing, companion toggle, etc.).
    """

    def __init__(self):
        self._look_at_target: Any = None

    def SetLookAtTarget(self, entity):
        self._look_at_target = entity

    def GetLookAtObject(self, player=None, include_dead: bool = False,
                        precise: bool = False) -> Any:
        return self._look_at_target

    def GetTargetParts(self, player=None, search_query=None) -> List[Any]:
        if self._look_at_target is None:
            return []
        return [self._look_at_target]

    def ClearTarget(self):
        self._look_at_target = None


# ═══════════════════════════════════════════════════════════════════════════════
#  Mappin System  (minimap pins for spawned entities)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MappinData:
    variant: str    = "WorldMapMappin"
    label:   str    = ""
    visible: bool   = True


class MappinSystem:
    """
    Simulates Game.GetMappinSystem().

    AMM registers map pins for spawned companions and removes them on despawn.
    """

    def __init__(self):
        self._pins:    Dict[int, dict] = {}
        self._next_id: int = 1

    def RegisterMappin(self, data: MappinData, position=None) -> int:
        mid = self._next_id
        self._next_id += 1
        self._pins[mid] = {"data": data, "position": position, "entity": None}
        return mid

    def RegisterMappinWithObject(self, data: MappinData, entity,
                                  slot=None, offset=None) -> int:
        mid = self._next_id
        self._next_id += 1
        self._pins[mid] = {"data": data, "position": None, "entity": entity}
        return mid

    def UnregisterMappin(self, mappin_id: int):
        self._pins.pop(mappin_id, None)

    def HasMappin(self, mappin_id: int) -> bool:
        return mappin_id in self._pins

    def GetMappinCount(self) -> int:
        return len(self._pins)

    def GetPinForEntity(self, entity) -> Optional[int]:
        for mid, pin in self._pins.items():
            if pin["entity"] is entity:
                return mid
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Weather System
# ═══════════════════════════════════════════════════════════════════════════════

class WeatherID(enum.Enum):
    Clear      = "Weather.Clear"
    Overcast   = "Weather.Overcast"
    Rain       = "Weather.Rain"
    HeavyRain  = "Weather.HeavyRain"
    Fog        = "Weather.Fog"
    Clouds     = "Weather.LightClouds"
    Toxic      = "Weather.Toxic"


class WeatherSystem:
    """
    Simulates Game.GetWeatherSystem() (AMM Tools tab → weather control).
    """

    def __init__(self):
        self._active: WeatherID           = WeatherID.Clear
        self._history: List[WeatherID]    = [WeatherID.Clear]
        self._blend_time: float           = 5.0

    def SetWeather(self, weather: WeatherID, blend_time: float = 5.0):
        self._active    = weather
        self._blend_time = blend_time
        self._history.append(weather)

    def GetActiveWeather(self) -> WeatherID:
        return self._active

    def GetWeatherHistory(self) -> List[WeatherID]:
        return list(self._history)

    def GetBlendTime(self) -> float:
        return self._blend_time


# ═══════════════════════════════════════════════════════════════════════════════
#  Game Time System
# ═══════════════════════════════════════════════════════════════════════════════

class GameTimeSystem:
    """
    Simulates CP2077's in-game clock (AMM Tools tab → time of day control).
    Time is stored in seconds from midnight (0–86399).
    """

    _SECONDS_PER_DAY = 86400

    def __init__(self):
        self._time: float = 8.0 * 3600   # 08:00 default

    def GetTime(self) -> float:
        return self._time

    def SetTime(self, seconds: float, skip_transition: bool = False):
        self._time = seconds % self._SECONDS_PER_DAY

    def SetHourMinute(self, hour: int, minute: int = 0):
        self._time = float(hour * 3600 + minute * 60)

    def GetHour(self) -> int:
        return int(self._time // 3600)

    def GetMinute(self) -> int:
        return int((self._time % 3600) // 60)

    def AdvanceTime(self, seconds: float):
        self._time = (self._time + seconds) % self._SECONDS_PER_DAY


# ═══════════════════════════════════════════════════════════════════════════════
#  Gameplay Status Effect System  (AMM's invisibility, no-movement, etc.)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GameplayStatusEffect:
    """A single status effect entry (AMM gameplay restriction effects)."""
    effect_id:  str
    record_id:  str   = ""
    source_id:  Any   = None
    duration:   float = -1.0   # -1 = permanent until explicitly removed
    _elapsed:   float = field(default=0.0, init=False)
    _active:    bool  = field(default=True, init=False)

    def Tick(self, dt: float) -> bool:
        """Advance time.  Returns True if still active."""
        if not self._active:
            return False
        if self.duration > 0:
            self._elapsed += dt
            if self._elapsed >= self.duration:
                self._active = False
                return False
        return True

    def IsActive(self) -> bool:
        return self._active

    def Remove(self):
        self._active = False


# Constants for AMM-used status effect IDs
class GameplayRestriction:
    NoMovement      = "GameplayRestriction.NoMovement"
    NoCameraControl = "GameplayRestriction.NoCameraControl"
    NoAI            = "GameplayRestriction.NoAI"
    Invisible       = "GameplayRestriction.Invisible"
    NoHUD           = "GameplayRestriction.NoHUD"


class GameplayStatusEffectSystem:
    """
    Simulates Game.GetStatusEffectSystem() for AMM's usage patterns.

    AMM uses status effects for:
      - Player invisibility / "passive mode"
      - No-movement restrictions
      - Companion god mode immortality tracking (complementary to GodModeSystem)
    """

    def __init__(self):
        # entity_id -> { effect_id -> GameplayStatusEffect }
        self._effects: Dict[Any, Dict[str, GameplayStatusEffect]] = {}

    def ApplyStatusEffect(self, entity_id, effect_id: str,
                          record_id: str = "", source_id: Any = None,
                          duration: float = -1.0):
        if entity_id not in self._effects:
            self._effects[entity_id] = {}
        self._effects[entity_id][effect_id] = GameplayStatusEffect(
            effect_id=effect_id, record_id=record_id,
            source_id=source_id, duration=duration,
        )

    def RemoveStatusEffect(self, entity_id, effect_id: str,
                           stack_count: int = 1):
        bucket = self._effects.get(entity_id, {})
        eff = bucket.pop(effect_id, None)
        if eff:
            eff.Remove()

    def ObjectHasStatusEffect(self, entity, effect_id: str) -> bool:
        eid = entity.GetEntityID() if hasattr(entity, 'GetEntityID') else entity
        bucket = self._effects.get(eid, {})
        return effect_id in bucket and bucket[effect_id].IsActive()

    def ObjectHasStatusEffectWithTag(self, entity, tag: str) -> bool:
        """Matches effects whose ID starts with tag (AMM pattern)."""
        eid = entity.GetEntityID() if hasattr(entity, 'GetEntityID') else entity
        bucket = self._effects.get(eid, {})
        return any(eid_str.startswith(tag) and eff.IsActive()
                   for eid_str, eff in bucket.items())

    def GetActiveEffects(self, entity_id) -> List[GameplayStatusEffect]:
        return [e for e in self._effects.get(entity_id, {}).values()
                if e.IsActive()]

    def GetActiveEffectCount(self, entity_id) -> int:
        return len(self.GetActiveEffects(entity_id))

    def Tick(self, dt: float):
        """Expire duration-limited effects."""
        for eid in list(self._effects):
            expired = [k for k, e in self._effects[eid].items()
                       if not e.Tick(dt)]
            for k in expired:
                del self._effects[eid][k]

    def ClearAll(self, entity_id=None):
        if entity_id is not None:
            self._effects.pop(entity_id, None)
        else:
            self._effects.clear()


# ═══════════════════════════════════════════════════════════════════════════════
#  Observer Registry  (lightweight Observe / Override hook simulation)
# ═══════════════════════════════════════════════════════════════════════════════

class ObserverRegistry:
    """
    Simulates CET's Observe / ObserveAfter / Override mechanism.

    AMM registers observers for:
      Observe('PlayerPuppet', 'OnAction', ...)
      Observe('DamageSystem', 'ProcessRagdollHit', ...)
      Override('gameuiWorldMapMenuGameController', 'IsFastTravelEnabled', ...)

    In test code you can fire an observed event with:
      registry.fire('PlayerPuppet', 'OnCombatStateChanged', payload)
    """

    def __init__(self):
        # (class_name, method_name) -> list of callables
        self._observers:  Dict[Tuple[str, str], List[Callable]] = {}
        self._overrides:  Dict[Tuple[str, str], Callable]       = {}

    def Observe(self, class_name: str, method_name: str,
                handler: Callable, after: bool = False):
        key = (class_name, method_name)
        if key not in self._observers:
            self._observers[key] = []
        self._observers[key].append(handler)

    def ObserveAfter(self, class_name: str, method_name: str,
                     handler: Callable):
        self.Observe(class_name, method_name, handler, after=True)

    def Override(self, class_name: str, method_name: str,
                 handler: Callable):
        self._overrides[(class_name, method_name)] = handler

    def Fire(self, class_name: str, method_name: str, *args, **kwargs):
        """Invoke all registered observers for this class/method."""
        key = (class_name, method_name)
        for handler in self._observers.get(key, []):
            handler(*args, **kwargs)

    def CallOverride(self, class_name: str, method_name: str,
                     *args, **kwargs) -> Any:
        """Invoke override handler (if registered) or raise KeyError."""
        key = (class_name, method_name)
        override = self._overrides.get(key)
        if override:
            return override(*args, **kwargs)
        raise KeyError(f"No override registered for {class_name}.{method_name}")

    def HasObserver(self, class_name: str, method_name: str) -> bool:
        return bool(self._observers.get((class_name, method_name)))

    def HasOverride(self, class_name: str, method_name: str) -> bool:
        return (class_name, method_name) in self._overrides

    def ClearAll(self):
        self._observers.clear()
        self._overrides.clear()
