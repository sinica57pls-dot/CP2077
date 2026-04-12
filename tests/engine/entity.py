"""
RED4 Engine Simulation -- Entity Hierarchy
==========================================

Mirrors the entity system from:
  scripts/Entity/Entity.reds          -- SetWorldTransform, GetComponents, etc.
  src/App/Entity/EntityEx.hpp         -- Entity extensions
  src/App/Entity/VisualScaleEx.cpp    -- Visual scale per-component
  src/App/Entity/ComponentWrapper.hpp -- Mesh component type hierarchy
  src/Red/MorphTarget.hpp             -- ApplyMorphTarget raw binding
  src/App/World/DynamicEntitySpec.hpp -- Spawn specification

Each class registers its RTTI type names so IsA() works like the real engine.

v2: NPCPuppet and PlayerPuppet now carry AIControllerComponent, AttitudeAgent,
and AppearanceComponent -- matching the real engine's component model and
enabling full AMM companion/appearance test coverage.

v3: Added rig-deformation and visual-scale subsystem (MorphTarget, BoneTransform,
DeformationRig, BodyType) -- mirrors the VisualScaleEx / MorphTarget C++ layer
and the community rig-deforming workflow documented at
CDPR-Modding-Documentation/Cyberpunk-Modding-Docs.
"""

import math
import enum
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .types import (Vector4, Vector3, Quaternion, WorldTransform,
                    FixedPoint, EntityID, CName)
from .ai import AIControllerComponent, AttitudeAgent, AINoRole
from .appearance import AppearanceComponent


# ── Body Type (mirrors base\characters\common\base_bodies\*) ────────────────

class BodyType(enum.Enum):
    """
    Body type presets matching Cyberpunk 2077's base body directories.

      woman_average -> WomanAverage (t0_000_wa_base__full.mesh)
      man_average   -> ManAverage   (t0_000_ma_base__full.mesh)
      man_big       -> ManBig       (t0_000_mb_base__full.mesh)

    Used by DeformationRig to resolve the correct base rig paths.
    """
    WomanAverage = "woman_average"
    ManAverage   = "man_average"
    ManBig       = "man_big"


# ── Bone Transform (one entry in a .rig file's BoneTransforms array) ────────

@dataclass
class BoneTransform:
    """
    One bone entry in a deformation rig.

    Mirrors the BoneTransforms array inside a .rig file.
    Scale values default to (1,1,1) = no deformation.

    NOTE (from community docs): Blender Z and Y axes are **flipped** compared
    to WolvenKit, so exported values must be swapped before injection.
    Bones ending with ``_l`` pair with ``_r`` for bilateral symmetry.
    """
    name:   str     = ""
    scaleX: float   = 1.0
    scaleY: float   = 1.0
    scaleZ: float   = 1.0

    def is_identity(self) -> bool:
        """True when the bone is unmodified (scale 1,1,1)."""
        return (abs(self.scaleX - 1.0) < 1e-6
                and abs(self.scaleY - 1.0) < 1e-6
                and abs(self.scaleZ - 1.0) < 1e-6)

    def as_vector3(self) -> Vector3:
        return Vector3(self.scaleX, self.scaleY, self.scaleZ)

    @staticmethod
    def from_vector3(name: str, v: Vector3) -> "BoneTransform":
        return BoneTransform(name=name, scaleX=v.X, scaleY=v.Y, scaleZ=v.Z)

    def mirrored(self) -> "BoneTransform":
        """
        Return a mirrored copy (_l ↔ _r) with same scale values.
        Rig deforming guide: modifications must be applied to both body sides.
        """
        if self.name.endswith("_l"):
            mirror_name = self.name[:-2] + "_r"
        elif self.name.endswith("_r"):
            mirror_name = self.name[:-2] + "_l"
        else:
            mirror_name = self.name
        return BoneTransform(name=mirror_name, scaleX=self.scaleX,
                             scaleY=self.scaleY, scaleZ=self.scaleZ)


# ── Deformation Rig (a complete set of bone transforms for a body) ──────────

class DeformationRig:
    """
    A named set of bone transforms representing one deformation rig.

    Mirrors the .rig files under
      base\\characters\\common\\base_bodies\\<body>\\deformations_rigs\\

    Two rig views are tracked per body:
      - third-person rig (world / photo mode)
      - player rig (first-person / FPP)

    The community workflow:
      1. Export base body mesh + rig from WolvenKit
      2. Scale individual bones in Blender Pose Mode
      3. Copy BoneTransform values back into the .rig CR2W
      4. Install both TPP and FPP .rig files

    IMPORTANT: Only scale leaf bones (no children).  Scaling parent bones or
    joints can break the mesh in-game.
    """

    def __init__(self, name: str = "", body_type: BodyType = BodyType.WomanAverage):
        self.name = name
        self.body_type = body_type
        # bone_name -> BoneTransform
        self._bones: Dict[str, BoneTransform] = {}
        self._is_player_rig = False   # True = FPP rig, False = TPP rig

    # ── Bone manipulation ────────────────────────────────────────────────────

    def SetBoneScale(self, bone_name: str, sx: float, sy: float, sz: float):
        """Set the scale of a single bone.  Creates the entry if needed."""
        self._bones[bone_name] = BoneTransform(name=bone_name,
                                                scaleX=sx, scaleY=sy, scaleZ=sz)

    def SetBoneScaleSymmetric(self, bone_name: str,
                               sx: float, sy: float, sz: float):
        """Set scale on both _l and _r sides simultaneously."""
        bt = BoneTransform(name=bone_name, scaleX=sx, scaleY=sy, scaleZ=sz)
        self._bones[bone_name] = bt
        mirror = bt.mirrored()
        if mirror.name != bone_name:
            self._bones[mirror.name] = mirror

    def GetBoneScale(self, bone_name: str) -> Optional[BoneTransform]:
        return self._bones.get(bone_name)

    def GetModifiedBones(self) -> List[BoneTransform]:
        """Return only bones whose scale differs from identity."""
        return [b for b in self._bones.values() if not b.is_identity()]

    def GetAllBones(self) -> Dict[str, BoneTransform]:
        return dict(self._bones)

    def GetBoneCount(self) -> int:
        return len(self._bones)

    def ClearBone(self, bone_name: str):
        self._bones.pop(bone_name, None)

    def Reset(self):
        """Clear all bone modifications."""
        self._bones.clear()

    def Clone(self, new_name: str = "") -> "DeformationRig":
        """Deep-copy for creating variants."""
        rig = DeformationRig(name=new_name or self.name,
                              body_type=self.body_type)
        rig._bones = deepcopy(self._bones)
        rig._is_player_rig = self._is_player_rig
        return rig

    def MakePlayerRig(self) -> "DeformationRig":
        """Clone this rig and mark it as first-person (player) variant."""
        rig = self.Clone(new_name=self.name + "_fpp")
        rig._is_player_rig = True
        return rig


# ── Morph Target (named blend-shape applied to a mesh component) ────────────

@dataclass
class MorphTargetEntry:
    """
    One applied morph target on a component.

    Mirrors Raw::MorphTargetManager::ApplyMorphTarget(component, target,
    region, value, false) from src/Red/MorphTarget.hpp.
    """
    target: str         # CName -- morph target identifier
    region: str = ""    # CName -- body region (e.g. "Head", "UpperBody")
    value:  float = 0.0 # 0.0 – 1.0 blend weight


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
    """
    Base mesh component -- visual geometry attached to an entity.

    Mirrors src/App/Entity/VisualScaleEx.cpp:
      GetVisualScale()  -> reads ``visualScale`` property (default 1,1,1)
      SetVisualScale()  -> writes property + calls RefreshAppearance()
    """
    _type_names = frozenset({"MeshComponent", "IVisualComponent",
                              "IComponent", "IScriptable"})

    def __init__(self):
        self.visualScale = Vector3(1, 1, 1)
        self.chunkMask = 0xFFFFFFFFFFFFFFFF
        self.meshAppearance = CName("")
        self.LODMode = 0
        self._mesh_path = ""
        self._visible = True
        self._temp_hidden = False
        self._appearance_refreshed = False

    def GetVisualScale(self):
        return Vector3(self.visualScale.X, self.visualScale.Y, self.visualScale.Z)

    def SetVisualScale(self, v):
        """
        Set visual scale and trigger RefreshAppearance.
        Mirrors VisualScaleEx.cpp -- SetVisualScale writes the property
        then calls Raw::MeshComponent::RefreshAppearance(this).
        """
        self.visualScale.X = v.X
        self.visualScale.Y = v.Y
        self.visualScale.Z = v.Z
        self.RefreshAppearance()

    def RefreshAppearance(self):
        """
        Force the renderer to reload visual properties.
        In the real engine this flushes material cache and triggers a
        VisualController dependency reload.  Here we just set a flag.
        """
        self._appearance_refreshed = True

    def Toggle(self, visible: bool):
        """AMM uses Toggle() to show/hide components."""
        self._visible = visible

    def TemporaryHide(self, hide: bool):
        self._temp_hidden = hide

    def ChangeResource(self, mesh_path: str, async_load: bool = True):
        """AMM swaps mesh resources for custom appearances."""
        self._mesh_path = mesh_path

    def GetResourcePath(self) -> str:
        return self._mesh_path

    def GetAppearanceName(self) -> CName:
        return self.meshAppearance

    def SetAppearanceName(self, name):
        self.meshAppearance = CName(name) if isinstance(name, str) else name
        self.RefreshAppearance()


class entSkinnedMeshComponent(MeshComponent):
    """
    Skinned mesh component -- has skeleton binding for skeletal animation.
    Mirrors src/App/Entity/ComponentWrapper.hpp ComponentType::SkinnedMeshComponent.
    """
    _type_names = frozenset({"entSkinnedMeshComponent", "MeshComponent",
                              "IVisualComponent", "IComponent", "IScriptable"})


class entMorphTargetSkinnedMeshComponent(MeshComponent):
    """
    Morph-target skinned mesh -- supports named blend-shapes (morph targets)
    on top of skeletal deformation.

    Mirrors:
      src/Red/MorphTarget.hpp         -- Raw::MorphTargetManager::ApplyMorphTarget
      src/App/Entity/EntityEx.cpp      -- Entity::ApplyMorphTarget (component lookup)
      src/App/Entity/ComponentWrapper  -- morphResource field instead of mesh

    The morph target resource path uses ``morphResource`` (not ``mesh``),
    and the ComponentWrapper resolves it via Red::MorphTargetMesh → baseMesh.
    """
    _type_names = frozenset({"entMorphTargetSkinnedMeshComponent",
                              "MeshComponent", "IVisualComponent",
                              "IComponent", "IScriptable"})

    def __init__(self):
        super().__init__()
        # morph target name -> MorphTargetEntry
        self._morph_targets: Dict[str, MorphTargetEntry] = {}
        self._morph_resource_path: str = ""

    def ApplyMorphTarget(self, target: str, region: str = "",
                         value: float = 1.0) -> bool:
        """
        Apply a named morph target to this component.

        Mirrors Raw::MorphTargetManager::ApplyMorphTarget(component,
        target, region, value, false).

        Args:
            target: CName of the morph target (e.g. "BodyFat", "MuscleTone")
            region: Body region CName (e.g. "Head", "UpperBody")
            value:  Blend weight 0.0–1.0

        Returns:
            True (component found and morph applied).
        """
        value = max(0.0, min(1.0, value))
        self._morph_targets[target] = MorphTargetEntry(
            target=target, region=region, value=value)
        self.RefreshAppearance()
        return True

    def RemoveMorphTarget(self, target: str) -> bool:
        if target in self._morph_targets:
            del self._morph_targets[target]
            self.RefreshAppearance()
            return True
        return False

    def GetMorphTarget(self, target: str) -> Optional[MorphTargetEntry]:
        return self._morph_targets.get(target)

    def GetAppliedMorphTargets(self) -> List[MorphTargetEntry]:
        return list(self._morph_targets.values())

    def GetMorphTargetValue(self, target: str) -> float:
        entry = self._morph_targets.get(target)
        return entry.value if entry else 0.0

    def ClearMorphTargets(self):
        self._morph_targets.clear()
        self.RefreshAppearance()

    def SetMorphResourcePath(self, path: str):
        """Set the morph target resource (uses morphResource, not mesh)."""
        self._morph_resource_path = path

    def GetMorphResourcePath(self) -> str:
        return self._morph_resource_path


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

    def FindComponentsByType(self, type_name) -> list:
        """Return ALL components matching the RTTI type name."""
        return [c for c in self._components if c.IsA(type_name)]

    def AddComponent(self, component):
        self._components.append(component)

    def ApplyMorphTarget(self, target: str, region: str = "",
                         value: float = 1.0) -> bool:
        """
        Apply a morph target to the first MorphTargetManagerComponent found.

        Mirrors src/App/Entity/EntityEx.cpp lines 4-15:
          1. Iterate all components
          2. Find entMorphTargetSkinnedMeshComponent via RTTI
          3. Call ApplyMorphTarget on it
          4. Return True if found, False otherwise
        """
        comp = self.FindComponentByType("entMorphTargetSkinnedMeshComponent")
        if comp is not None and hasattr(comp, 'ApplyMorphTarget'):
            return comp.ApplyMorphTarget(target, region, value)
        return False

    def GetVisualScale(self) -> Optional[Vector3]:
        """
        Get visual scale from the first mesh component on this entity.
        Convenience wrapper matching the C++ VisualScaleEx pattern.
        """
        comp = self.FindComponentByType("MeshComponent")
        if comp is not None:
            return comp.GetVisualScale()
        return None

    def SetVisualScale(self, scale: Vector3) -> bool:
        """
        Set visual scale on ALL mesh components of this entity.
        Returns True if at least one component was updated.
        """
        comps = self.FindComponentsByType("MeshComponent")
        for c in comps:
            c.SetVisualScale(scale)
        return len(comps) > 0

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


# ── Player body mesh lookup (from rig-deforming guide) ────────────────────────

_BASE_BODY_MESH = {
    BodyType.WomanAverage: "base\\characters\\common\\base_bodies\\woman_average\\t0_000_wa_base__full.mesh",
    BodyType.ManAverage:   "base\\characters\\common\\base_bodies\\man_average\\t0_000_ma_base__full.mesh",
    BodyType.ManBig:       "base\\characters\\common\\base_bodies\\man_big\\t0_000_mb_base__full.mesh",
}


# ── PlayerPuppet ──────────────────────────────────────────────────────────────

class PlayerPuppet(ScriptedPuppet):
    _type_names = frozenset({"PlayerPuppet", "gamePlayerPuppet",
                              "ScriptedPuppet", "gamePuppet",
                              "GameObject", "Entity", "IScriptable"})

    def __init__(self, entity_id=None, position=None, orientation=None,
                 body_type: BodyType = BodyType.WomanAverage):
        super().__init__(entity_id=entity_id, position=position,
                         orientation=orientation)
        self._attitude_agent = AttitudeAgent()
        self._attitude_agent.SetAttitudeGroup("PlayerAllies")
        # Player doesn't have an AI controller but AMM probes attitude agent
        self._npc_stats = None

        # ── Visual / Rig subsystem (v3) ──────────────────────────────────────
        self._body_type = body_type
        # Deformation rig (TPP + FPP pair).
        self._deformation_rig:     Optional[DeformationRig] = None
        self._deformation_rig_fpp: Optional[DeformationRig] = None

        # Default body mesh component + morph-target component
        self._body_mesh = entSkinnedMeshComponent()
        self._body_mesh._mesh_path = _BASE_BODY_MESH[body_type]
        self._body_morph = entMorphTargetSkinnedMeshComponent()
        self.AddComponent(self._body_mesh)
        self.AddComponent(self._body_morph)

    def GetAttitudeAgent(self) -> AttitudeAgent:
        return self._attitude_agent

    # ── Body Type ────────────────────────────────────────────────────────────

    def GetBodyType(self) -> BodyType:
        return self._body_type

    def SetBodyType(self, body_type: BodyType):
        """
        Switch body type — updates the base body mesh resource path and
        resets any active deformation rig (it's body-type-specific).
        """
        self._body_type = body_type
        self._body_mesh._mesh_path = _BASE_BODY_MESH[body_type]
        self._body_mesh.RefreshAppearance()
        # Rig is body-type-specific; must be re-applied after switch
        self._deformation_rig = None
        self._deformation_rig_fpp = None

    # ── Deformation Rig ──────────────────────────────────────────────────────

    def SetDeformationRig(self, rig: DeformationRig,
                           auto_fpp: bool = True):
        """
        Install a deformation rig (third-person).
        If auto_fpp is True, a first-person (player) variant is cloned
        automatically, matching the community workflow of updating both
        TPP and FPP .rig files.
        """
        self._deformation_rig = rig
        if auto_fpp:
            self._deformation_rig_fpp = rig.MakePlayerRig()
        self._body_mesh.RefreshAppearance()

    def SetDeformationRigFPP(self, rig: DeformationRig):
        """Install a first-person-specific deformation rig."""
        rig._is_player_rig = True
        self._deformation_rig_fpp = rig

    def GetDeformationRig(self) -> Optional[DeformationRig]:
        return self._deformation_rig

    def GetDeformationRigFPP(self) -> Optional[DeformationRig]:
        return self._deformation_rig_fpp

    def ClearDeformationRig(self):
        self._deformation_rig = None
        self._deformation_rig_fpp = None
        self._body_mesh.RefreshAppearance()

    # ── Morph Target (convenience) ───────────────────────────────────────────

    def ApplyBodyMorphTarget(self, target: str, region: str = "",
                              value: float = 1.0) -> bool:
        """Apply a morph target to the player's body morph component."""
        return self._body_morph.ApplyMorphTarget(target, region, value)

    def GetBodyMorphTargets(self) -> list:
        return self._body_morph.GetAppliedMorphTargets()

    # ── Visual Scale (convenience) ───────────────────────────────────────────

    def GetBodyVisualScale(self) -> Vector3:
        return self._body_mesh.GetVisualScale()

    def SetBodyVisualScale(self, scale: Vector3):
        """
        Scale the player body mesh.
        Mirrors VisualScaleEx.cpp -- sets visualScale then RefreshAppearance.
        """
        self._body_mesh.SetVisualScale(scale)
        self._body_morph.SetVisualScale(scale)


# ── NPCPuppet ─────────────────────────────────────────────────────────────────

class NPCPuppet(ScriptedPuppet):
    """
    Full-featured NPC puppet with AI controller, attitude agent, and
    appearance component -- matching the real engine's gamePuppet interface.

    AMM interacts with all three:
      npc.GetAIControllerComponent().SetAIRole(AIFollowerRole.new())
      npc.GetAttitudeAgent().SetAttitudeGroup("PlayerAllies")
      npc.GetCurrentAppearanceName()
      npc.ScheduleAppearanceChange(appName)
    """

    _type_names = frozenset({"NPCPuppet", "ScriptedPuppet", "gamePuppet",
                              "GameObject", "Entity", "IScriptable"})

    def __init__(self, entity_id=None, position=None, orientation=None,
                 appearance: str = "default"):
        super().__init__(entity_id=entity_id, position=position,
                         orientation=orientation)
        # AMM-facing subsystems
        self._ai_ctrl      = AIControllerComponent()
        self._attitude     = AttitudeAgent()
        self._appearance   = AppearanceComponent(initial=appearance)

        # AMM companion metadata
        self._is_companion: bool   = False
        self._mappin_id:    int    = -1   # from MappinSystem
        self._npc_stats            = None  # NPCStats (optional)

    # ── AI Controller (matches AMM's GetAIControllerComponent() calls) ────────

    def GetAIControllerComponent(self) -> AIControllerComponent:
        return self._ai_ctrl

    # ── Attitude Agent ────────────────────────────────────────────────────────

    def GetAttitudeAgent(self) -> AttitudeAgent:
        return self._attitude

    # ── Appearance (matches AMM's direct puppet calls) ────────────────────────

    def GetCurrentAppearanceName(self) -> str:
        return self._appearance.GetCurrentAppearanceName()

    def PrefetchAppearanceChange(self, app_name: str):
        self._appearance.PrefetchAppearanceChange(app_name)

    def ScheduleAppearanceChange(self, app_name: str):
        self._appearance.ScheduleAppearanceChange(app_name)

    def GetAppearanceHistory(self) -> list:
        return self._appearance.GetChangeHistory()

    # ── Companion helpers (AMM sets/reads these) ──────────────────────────────

    def SetIsCompanion(self, flag: bool):
        self._is_companion = flag

    def IsCompanion(self) -> bool:
        return self._is_companion

    def SetMappin(self, mappin_id: int):
        self._mappin_id = mappin_id

    def GetMappin(self) -> int:
        return self._mappin_id


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
