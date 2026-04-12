"""
RED4 Engine Simulation -- Game Systems
======================================

Mirrors the engine systems from:
  src/App/World/DynamicEntitySystem.cpp  -- Entity lifecycle manager
  scripts/World/DynamicEntitySystem.reds -- DES API stubs
  scripts/Scheduling/DelaySystem.reds    -- Timed callbacks
  scripts/Callback/CallbackSystem.reds   -- Event dispatch

Each system is faithful to the actual C++ implementation.
"""

from collections import defaultdict
from .types import EntityID, CName, EInputKey, EInputAction
from .entity import Entity, NPCPuppet, DynamicEntitySpec


# ── DynamicEntitySystem ────────────────────────────────────────────

class DynamicEntitySystem:
    """Faithful Python port of src/App/World/DynamicEntitySystem.cpp.

    Core data structures (from the C++ header):
      m_entityStatesByTag : Map<CName, Set<EntityID>>
      m_entityStateByID   : Map<EntityID, EntityState>
    """

    def __init__(self):
        self._ready = False
        self._restored = False
        self._entities = {}              # EntityID -> Entity
        self._tags_to_ids = defaultdict(set)  # tag_str -> {EntityID, ...}
        self._alive = True

    # -- Engine lifecycle (called by simulation) --

    def OnWorldAttached(self):
        self._ready = True

    def OnStreamingWorldLoaded(self):
        self._restored = True

    def OnAfterWorldDetach(self):
        """Session end -- mirrors C++ OnAfterWorldDetach which clears everything."""
        self._ready = False
        self._restored = False
        self._entities.clear()
        self._tags_to_ids.clear()

    # -- Validity (for wref simulation) --

    def IsDefined(self):
        return self._alive and self._ready

    def Invalidate(self):
        self._alive = False

    # -- Public API (mirrors scripts/World/DynamicEntitySystem.reds) --

    def IsReady(self):
        return self._ready

    def IsRestored(self):
        return self._restored

    def CreateEntity(self, spec):
        """Create and register an entity from a spec.  Returns (EntityID, Entity)."""
        if not self._ready:
            return EntityID(), None

        entity = NPCPuppet(
            position=spec.position,
            orientation=spec.orientation,
        )
        eid = entity.GetEntityID()
        self._entities[eid] = entity

        for tag in spec.tags:
            tag_str = str(tag)
            self._tags_to_ids[tag_str].add(eid)

        return eid, entity

    def AddEntity(self, entity, tags):
        """Register an already-created entity (e.g. player or manually spawned)."""
        eid = entity.GetEntityID()
        self._entities[eid] = entity
        for tag in tags:
            tag_str = str(tag) if isinstance(tag, CName) else tag
            self._tags_to_ids[tag_str].add(eid)

    def DeleteEntity(self, eid):
        if eid in self._entities:
            del self._entities[eid]
            for tag_set in self._tags_to_ids.values():
                tag_set.discard(eid)
            return True
        return False

    def IsManaged(self, eid):
        return self._ready and eid in self._entities

    def IsSpawned(self, eid):
        e = self._entities.get(eid)
        return e is not None and e.IsDefined()

    def GetEntity(self, eid):
        return self._entities.get(eid)

    def GetTags(self, eid):
        tags = []
        for tag_str, ids in self._tags_to_ids.items():
            if eid in ids:
                tags.append(CName(tag_str))
        return tags

    def AssignTag(self, eid, tag):
        if eid in self._entities:
            tag_str = str(tag) if isinstance(tag, CName) else tag
            self._tags_to_ids[tag_str].add(eid)

    def UnassignTag(self, eid, tag):
        tag_str = str(tag) if isinstance(tag, CName) else tag
        self._tags_to_ids[tag_str].discard(eid)

    def IsPopulated(self, tag):
        """Returns True if any entity is registered under this tag."""
        if not self._ready:
            return False
        tag_str = str(tag) if isinstance(tag, CName) else tag
        return len(self._tags_to_ids.get(tag_str, set())) > 0

    def GetTagged(self, tag):
        """Returns list of Entity refs for all entities with this tag."""
        if not self._ready:
            return []
        tag_str = str(tag) if isinstance(tag, CName) else tag
        result = []
        for eid in list(self._tags_to_ids.get(tag_str, set())):
            entity = self._entities.get(eid)
            if entity and entity.IsDefined():
                result.append(entity)
        return result

    def GetTaggedIDs(self, tag):
        if not self._ready:
            return []
        tag_str = str(tag) if isinstance(tag, CName) else tag
        return list(self._tags_to_ids.get(tag_str, set()))

    def DeleteTagged(self, tag):
        tag_str = str(tag) if isinstance(tag, CName) else tag
        for eid in list(self._tags_to_ids.get(tag_str, set())):
            self.DeleteEntity(eid)


# ── DelayCallback / DelaySystem ────────────────────────────────────

class DelayCallback:
    """Base class for delayed callbacks.  Override Call()."""

    def Call(self):
        raise NotImplementedError


class DelaySystem:
    """Time-stepped callback scheduler.

    Mirrors the game's DelaySystem:
      DelayCallback(cb, delay, timeDilation) -> schedules cb after delay seconds
      Tick(dt) fires all callbacks whose scheduled time has arrived.

    Handles cascading re-schedules (callback registers new callback).
    """

    def __init__(self):
        self._pending = []   # [(fire_at, callback)]
        self._time = 0.0
        self._next_id = 1

    @property
    def current_time(self):
        return self._time

    @property
    def pending_count(self):
        return len(self._pending)

    def DelayCallback(self, callback, delay, is_affected_by_time_dilation=False):
        fire_at = self._time + delay
        self._pending.append((fire_at, callback))
        did = self._next_id
        self._next_id += 1
        return did

    def DelayCallbackNextFrame(self, callback):
        self._pending.append((self._time, callback))

    def Tick(self, dt):
        """Advance time by dt and fire all ready callbacks.  Returns count fired."""
        self._time += dt
        fired = 0
        # Process in time order; new callbacks added during processing
        # may fire in the same Tick if their fire_at <= current time.
        while True:
            ready = [(t, cb) for (t, cb) in self._pending if t <= self._time]
            if not ready:
                break
            # Sort by time so earlier callbacks fire first
            ready.sort(key=lambda x: x[0])
            for item in ready:
                self._pending.remove(item)
            for _, cb in ready:
                cb.Call()
                fired += 1
        return fired


# ── CallbackSystem events and handlers ─────────────────────────────

class CallbackSystemEvent:
    pass


class KeyInputEvent(CallbackSystemEvent):
    def __init__(self, key=EInputKey.IK_None, action=EInputAction.IACT_Press):
        self._key = key
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
        self._registrations = defaultdict(list)  # event_name -> [(target, func_name)]

    def RegisterCallback(self, event_name, target, func_name, sticky=False):
        self._registrations[event_name].append((target, func_name))
        return CallbackSystemHandler()

    def UnregisterCallback(self, event_name, target, func_name=None):
        regs = self._registrations.get(event_name, [])
        self._registrations[event_name] = [
            (t, f) for (t, f) in regs
            if not (t is target and (func_name is None or f == func_name))
        ]

    def DispatchEvent(self, event_name, event_obj=None):
        for target, func_name in self._registrations.get(event_name, []):
            method = getattr(target, func_name, None)
            if method:
                if event_obj is not None:
                    method(event_obj)
                else:
                    method()


# ── SystemRequestsHandler ──────────────────────────────────────────

class SystemRequestsHandler:
    def __init__(self):
        self._is_pregame = True

    def IsPreGame(self):
        return self._is_pregame


# ── ScriptableSystem ───────────────────────────────────────────────

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


# ── ScriptableSystemsContainer ─────────────────────────────────────

class ScriptableSystemsContainer:
    def __init__(self):
        self._systems = {}

    def Register(self, name, system):
        self._systems[name] = system

    def Get(self, name):
        return self._systems.get(name)
