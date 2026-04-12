"""
RED4 Engine Simulation -- Game Systems
======================================

Mirrors the engine systems from:
  src/App/World/DynamicEntitySystem.cpp  -- Entity lifecycle manager
  scripts/World/DynamicEntitySystem.reds -- DES API stubs
  scripts/Scheduling/DelaySystem.reds    -- Timed callbacks
  scripts/Callback/CallbackSystem.reds   -- Event dispatch

v2 Performance optimizations:
  DynamicEntitySystem:
    - Added reverse index  _ids_to_tags: Dict[EntityID, Set[str]]
      → GetTags(eid) is now O(1) instead of O(# unique tag strings)
      → DeleteEntity is now O(# tags on entity) instead of O(# unique tags)
    - Tags stored as plain strings throughout (no CName wrapping in hot paths)

  DelaySystem:
    - Replaced O(n²) list scan with O(n log n) heapq
      Under 500 callbacks the old code was measurably slower on tick-heavy tests.
"""

import heapq
from collections import defaultdict
from typing import Dict, List, Optional, Set

from .types import EntityID, CName, EInputKey, EInputAction
from .entity import Entity, NPCPuppet, DynamicEntitySpec


# ── DynamicEntitySystem ────────────────────────────────────────────────────────

class DynamicEntitySystem:
    """Faithful Python port of src/App/World/DynamicEntitySystem.cpp.

    Core data structures (from the C++ header):
      m_entityStatesByTag : Map<CName, Set<EntityID>>
      m_entityStateByID   : Map<EntityID, EntityState>

    Added for O(1) tag resolution:
      _ids_to_tags        : Dict[EntityID, Set[str]]
    """

    def __init__(self):
        self._ready    = False
        self._restored = False
        self._alive    = True

        # Forward index: tag_str → {EntityID, …}
        self._tags_to_ids: Dict[str, Set[EntityID]] = defaultdict(set)
        # Reverse index: EntityID → {tag_str, …}  (NEW - enables O(1) GetTags)
        self._ids_to_tags: Dict[EntityID, Set[str]] = {}
        # Entity storage
        self._entities:   Dict[EntityID, Entity]    = {}

    # ── Engine lifecycle ────────────────────────────────────────────────────

    def OnWorldAttached(self):
        self._ready = True

    def OnStreamingWorldLoaded(self):
        self._restored = True

    def OnAfterWorldDetach(self):
        """Session end -- mirrors C++ which clears everything."""
        self._ready    = False
        self._restored = False
        self._entities.clear()
        self._tags_to_ids.clear()
        self._ids_to_tags.clear()

    # ── Validity ─────────────────────────────────────────────────────────────

    def IsDefined(self) -> bool:
        return self._alive and self._ready

    def Invalidate(self):
        self._alive = False

    # ── Public API (mirrors scripts/World/DynamicEntitySystem.reds) ──────────

    def IsReady(self) -> bool:
        return self._ready

    def IsRestored(self) -> bool:
        return self._restored

    def CreateEntity(self, spec: DynamicEntitySpec):
        """Create and register an entity from a spec.  Returns (EntityID, Entity)."""
        if not self._ready:
            return EntityID(), None

        # Preserve appearance from spec if provided
        appear = str(spec.appearanceName) if spec.appearanceName else "default"
        entity = NPCPuppet(
            position=spec.position,
            orientation=spec.orientation,
            appearance=appear,
        )
        eid = entity.GetEntityID()
        self._entities[eid] = entity
        self._ids_to_tags[eid] = set()

        for tag in spec.tags:
            tag_str = str(tag)
            self._tags_to_ids[tag_str].add(eid)
            self._ids_to_tags[eid].add(tag_str)

        return eid, entity

    def AddEntity(self, entity: Entity, tags):
        """Register an already-created entity (e.g. player or test NPC)."""
        eid = entity.GetEntityID()
        self._entities[eid] = entity

        if eid not in self._ids_to_tags:
            self._ids_to_tags[eid] = set()

        for tag in tags:
            tag_str = str(tag) if isinstance(tag, CName) else tag
            self._tags_to_ids[tag_str].add(eid)
            self._ids_to_tags[eid].add(tag_str)

    def DeleteEntity(self, eid: EntityID) -> bool:
        if eid not in self._entities:
            return False
        # Use reverse index to only touch the relevant tag sets – O(T)
        for tag_str in self._ids_to_tags.pop(eid, set()):
            self._tags_to_ids[tag_str].discard(eid)
        del self._entities[eid]
        return True

    def IsManaged(self, eid: EntityID) -> bool:
        return self._ready and eid in self._entities

    def IsSpawned(self, eid: EntityID) -> bool:
        e = self._entities.get(eid)
        return e is not None and e.IsDefined()

    def GetEntity(self, eid: EntityID) -> Optional[Entity]:
        return self._entities.get(eid)

    def GetTags(self, eid: EntityID) -> List[CName]:
        """O(1) via reverse index."""
        return [CName(t) for t in self._ids_to_tags.get(eid, set())]

    def AssignTag(self, eid: EntityID, tag):
        if eid not in self._entities:
            return
        tag_str = str(tag) if isinstance(tag, CName) else tag
        self._tags_to_ids[tag_str].add(eid)
        if eid not in self._ids_to_tags:
            self._ids_to_tags[eid] = set()
        self._ids_to_tags[eid].add(tag_str)

    def UnassignTag(self, eid: EntityID, tag):
        tag_str = str(tag) if isinstance(tag, CName) else tag
        self._tags_to_ids[tag_str].discard(eid)
        if eid in self._ids_to_tags:
            self._ids_to_tags[eid].discard(tag_str)

    def IsPopulated(self, tag) -> bool:
        """Returns True if any live entity has this tag."""
        if not self._ready:
            return False
        tag_str = str(tag) if isinstance(tag, CName) else tag
        return len(self._tags_to_ids.get(tag_str, set())) > 0

    def GetTagged(self, tag) -> List[Entity]:
        """Returns live entities matching tag.  O(k) where k = matching count."""
        if not self._ready:
            return []
        tag_str = str(tag) if isinstance(tag, CName) else tag
        result = []
        for eid in list(self._tags_to_ids.get(tag_str, set())):
            entity = self._entities.get(eid)
            if entity and entity.IsDefined():
                result.append(entity)
        return result

    def GetTaggedIDs(self, tag) -> List[EntityID]:
        if not self._ready:
            return []
        tag_str = str(tag) if isinstance(tag, CName) else tag
        return list(self._tags_to_ids.get(tag_str, set()))

    def DeleteTagged(self, tag):
        tag_str = str(tag) if isinstance(tag, CName) else tag
        for eid in list(self._tags_to_ids.get(tag_str, set())):
            self.DeleteEntity(eid)

    def GetEntityCount(self) -> int:
        return len(self._entities)

    def GetAllEntities(self) -> List[Entity]:
        return list(self._entities.values())


# ── DelayCallback / DelaySystem ────────────────────────────────────────────────

class DelayCallback:
    """Base class for delayed callbacks.  Override Call()."""

    def Call(self):
        raise NotImplementedError


class DelaySystem:
    """Time-stepped callback scheduler.

    Mirrors the game's DelaySystem:
      DelayCallback(cb, delay, timeDilation) -> schedules cb after delay seconds
      Tick(dt) fires all callbacks whose scheduled time has arrived.

    v2 Performance: uses heapq instead of list scan.
    Worst-case Tick() is now O(k log n) where k = callbacks fired, n = total pending.
    Previously it was O(n²) due to repeated list.remove() in the inner loop.
    """

    def __init__(self):
        # heap elements: (fire_at: float, seq: int, callback: DelayCallback)
        self._heap:    list = []
        self._time:    float = 0.0
        self._seq:     int   = 0   # tie-breaker to keep heap stable

    @property
    def current_time(self) -> float:
        return self._time

    @property
    def pending_count(self) -> int:
        return len(self._heap)

    def DelayCallback(self, callback: DelayCallback, delay: float,
                      is_affected_by_time_dilation: bool = False) -> int:
        fire_at = self._time + max(0.0, delay)
        seq = self._seq
        self._seq += 1
        heapq.heappush(self._heap, (fire_at, seq, callback))
        return seq   # acts as a DelayID

    def DelayCallbackNextFrame(self, callback: DelayCallback):
        self.DelayCallback(callback, delay=0.0)

    def CancelCallback(self, seq: int):
        """Cancel a scheduled callback by its sequence number."""
        # Mark as cancelled -- we use a tombstone approach since heapq
        # doesn't support arbitrary removal.
        self._heap = [(t, s, cb) for (t, s, cb) in self._heap if s != seq]
        heapq.heapify(self._heap)

    def Tick(self, dt: float) -> int:
        """Advance time by dt and fire all ready callbacks.  Returns count fired."""
        self._time += dt
        fired = 0
        # Pop and fire everything at or before _time.
        # New callbacks added during Call() will be pushed onto _heap and
        # picked up in the same Tick if their fire_at <= self._time.
        while self._heap and self._heap[0][0] <= self._time:
            _, _, cb = heapq.heappop(self._heap)
            cb.Call()
            fired += 1
        return fired


# ── CallbackSystem events and handlers ────────────────────────────────────────

class CallbackSystemEvent:
    pass


class KeyInputEvent(CallbackSystemEvent):
    def __init__(self, key=EInputKey.IK_None, action=EInputAction.IACT_Press):
        self._key    = key
        self._action = action

    def GetKey(self):
        return self._key

    def GetAction(self):
        return self._action


class GameSessionEvent(CallbackSystemEvent):
    def __init__(self, is_restored=False, is_pre_game=False):
        self._is_restored = is_restored
        self._is_pre_game = is_pre_game


class InputTarget:
    @staticmethod
    def Key(key, action=None):
        return ('key', key, action)


class CallbackSystemHandler:
    def AddTarget(self, *args):
        return self  # Chainable no-op in simulation


class CallbackSystem:
    """Event dispatch (scripts/Callback/CallbackSystem.reds)."""

    def __init__(self):
        self._registrations: Dict[str, list] = defaultdict(list)

    def RegisterCallback(self, event_name: str, target, func_name: str,
                         sticky: bool = False):
        self._registrations[event_name].append((target, func_name))
        return CallbackSystemHandler()

    def UnregisterCallback(self, event_name: str, target, func_name=None):
        regs = self._registrations.get(event_name, [])
        self._registrations[event_name] = [
            (t, f) for (t, f) in regs
            if not (t is target and (func_name is None or f == func_name))
        ]

    def DispatchEvent(self, event_name: str, event_obj=None):
        for target, func_name in self._registrations.get(event_name, []):
            method = getattr(target, func_name, None)
            if method:
                if event_obj is not None:
                    method(event_obj)
                else:
                    method()


# ── SystemRequestsHandler ──────────────────────────────────────────────────────

class SystemRequestsHandler:
    def __init__(self):
        self._is_pregame = True

    def IsPreGame(self) -> bool:
        return self._is_pregame


# ── ScriptableSystem ───────────────────────────────────────────────────────────

class ScriptableSystem:
    """Base class for mod systems (Codeware ScriptableSystem)."""

    def __init__(self):
        self._game_instance = None

    def GetGameInstance(self):
        return self._game_instance

    def OnAttach(self):
        pass

    def OnDetach(self):
        pass

    def OnRestored(self, save_version=0, game_version=0):
        pass

    def OnPlayerAttach(self, request=None):
        pass


# ── ScriptableSystemsContainer ─────────────────────────────────────────────────

class ScriptableSystemsContainer:
    def __init__(self):
        self._systems: Dict[str, ScriptableSystem] = {}

    def Register(self, name: str, system: ScriptableSystem):
        self._systems[name] = system

    def Get(self, name: str) -> Optional[ScriptableSystem]:
        return self._systems.get(name)
