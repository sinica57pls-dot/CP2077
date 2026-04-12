"""
RED4 Engine Simulation -- Entity Hierarchy
==========================================

Mirrors the entity system from:
  scripts/Entity/Entity.reds          -- SetWorldTransform, GetComponents, etc.
  src/App/Entity/EntityEx.hpp         -- Entity extensions
  src/App/World/DynamicEntitySpec.hpp  -- Spawn specification

Each class registers its RTTI type names so IsA() works like the real engine.
"""

import math
from .types import (Vector4, Vector3, Quaternion, WorldTransform,
                    FixedPoint, EntityID, CName)


class IScriptable:
    """Base for all scriptable objects."""

    # Subclasses extend this with their RTTI names.
    _type_names = frozenset({"IScriptable"})

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Inherit parent type names and add the class's own name.
        parent_names = set()
        for base in cls.__mro__:
            names = getattr(base, '_type_names', None)
            if names is not None:
                parent_names |= names
        parent_names.add(cls.__name__)
        cls._type_names = frozenset(parent_names)

    def IsA(self, type_name):
        """RTTI type check -- matches class name or any ancestor."""
        return type_name in self._type_names

    def IsDefined(self):
        return True


class IComponent(IScriptable):
    _type_names = frozenset({"IComponent", "IScriptable"})


class IVisualComponent(IComponent):
    _type_names = frozenset({"IVisualComponent", "IComponent", "IScriptable"})


class MeshComponent(IVisualComponent):
    _type_names = frozenset({"MeshComponent", "IVisualComponent",
                              "IComponent", "IScriptable"})

    def __init__(self):
        self.visualScale = Vector3(1, 1, 1)
        self.chunkMask = 0xFFFFFFFFFFFFFFFF

    def GetVisualScale(self):
        return Vector3(self.visualScale.X, self.visualScale.Y, self.visualScale.Z)

    def SetVisualScale(self, v):
        self.visualScale.X = v.X
        self.visualScale.Y = v.Y
        self.visualScale.Z = v.Z


class entSkinnedMeshComponent(MeshComponent):
    _type_names = frozenset({"entSkinnedMeshComponent", "MeshComponent",
                              "IVisualComponent", "IComponent", "IScriptable"})


class entMorphTargetSkinnedMeshComponent(MeshComponent):
    _type_names = frozenset({"entMorphTargetSkinnedMeshComponent",
                              "MeshComponent", "IVisualComponent",
                              "IComponent", "IScriptable"})


# ── Entity ──────────────────────────────────────────────────────────

class Entity(IScriptable):
    _type_names = frozenset({"Entity", "IScriptable"})

    def __init__(self, entity_id=None, position=None, orientation=None):
        self._entity_id = entity_id or EntityID.next_id()
        self._position = position or Vector4(0, 0, 0, 0)
        self._orientation = orientation or Quaternion.identity()
        self._components = []
        self._alive = True
        self._transform_history = []

    def GetEntityID(self):
        return self._entity_id

    def GetWorldPosition(self):
        return Vector4(self._position.X, self._position.Y,
                       self._position.Z, self._position.W)

    def GetWorldForward(self):
        """Derive forward direction (+Y local) from orientation quaternion."""
        q = self._orientation
        fx = 2 * (q.i * q.j + q.k * q.r)
        fy = 1 - 2 * (q.i * q.i + q.k * q.k)
        fz = 2 * (q.j * q.k - q.i * q.r)
        return Vector4(fx, fy, fz, 0)

    def GetWorldOrientation(self):
        return self._orientation.copy()

    def SetWorldTransform(self, transform):
        self._position.X = transform.Position.x.to_float()
        self._position.Y = transform.Position.y.to_float()
        self._position.Z = transform.Position.z.to_float()
        self._orientation = Quaternion(
            transform.Orientation.i, transform.Orientation.j,
            transform.Orientation.k, transform.Orientation.r)
        self._transform_history.append({
            'pos': self.GetWorldPosition(),
            'ori': self.GetWorldOrientation(),
        })

    def GetComponents(self):
        return list(self._components)

    def FindComponentByType(self, type_name):
        for c in self._components:
            if c.IsA(type_name):
                return c
        return None

    def AddComponent(self, component):
        self._components.append(component)

    def IsDefined(self):
        return self._alive

    def Invalidate(self):
        self._alive = False

    def __repr__(self):
        names = sorted(self._type_names - {"IScriptable"})
        return f"Entity(id={self._entity_id}, types={names}, pos={self._position})"


class GameObject(Entity):
    _type_names = frozenset({"GameObject", "Entity", "IScriptable"})


class gamePuppet(Entity):
    _type_names = frozenset({"gamePuppet", "Entity", "IScriptable"})


class ScriptedPuppet(gamePuppet):
    _type_names = frozenset({"ScriptedPuppet", "gamePuppet",
                              "Entity", "IScriptable"})


class PlayerPuppet(ScriptedPuppet):
    _type_names = frozenset({"PlayerPuppet", "gamePlayerPuppet",
                              "ScriptedPuppet", "gamePuppet",
                              "GameObject", "Entity", "IScriptable"})


class NPCPuppet(ScriptedPuppet):
    _type_names = frozenset({"NPCPuppet", "ScriptedPuppet", "gamePuppet",
                              "GameObject", "Entity", "IScriptable"})


# ── DynamicEntitySpec ──────────────────────────────────────────────

class DynamicEntitySpec:
    """Spawn specification (src/App/World/DynamicEntitySpec.hpp)."""

    def __init__(self, tags=None, position=None, orientation=None,
                 appearance_name="", persist_state=False, persist_spawn=False,
                 always_spawned=True, spawn_in_view=True, active=True):
        self.tags = [CName(t) if isinstance(t, str) else t for t in (tags or [])]
        self.position = position or Vector4(0, 0, 0, 0)
        self.orientation = orientation or Quaternion.identity()
        self.appearanceName = CName(appearance_name)
        self.persistState = persist_state
        self.persistSpawn = persist_spawn
        self.alwaysSpawned = always_spawned
        self.spawnInView = spawn_in_view
        self.active = active
