"""
RED4 Engine Simulation
======================

Offline simulation of Cyberpunk 2077's RED4 engine for testing mods
without launching the game.

v2 additions (AMM-focused):
  - AI system (ai.py)          : commands, roles, attitude agent
  - Appearance system          : prefetch/schedule, trigger system
  - World systems (world.py)   : teleport, god mode, static entities,
                                  workspot, targeting, mappins,
                                  weather, time, status effects, observers
  - Optimized DES              : O(1) reverse tag index
  - Optimized DelaySystem      : heapq replaces O(n^2) list scan
  - Extended TweakDB           : CloneRecord, SetFlatNoUpdate, Update,
                                  AMM_Character.* seeded records
"""

# ── Value types ────────────────────────────────────────────────────
from .types import (
    FixedPoint, Vector4, Vector3, Quaternion,
    WorldPosition, WorldTransform, CName, EntityID,
    EInputKey, EInputAction, DelayID,
)

# ── Entity hierarchy ───────────────────────────────────────────────
from .entity import (
    IScriptable, IComponent, IVisualComponent,
    MeshComponent, entSkinnedMeshComponent,
    entMorphTargetSkinnedMeshComponent,
    Entity, GameObject, gamePuppet, ScriptedPuppet,
    PlayerPuppet, NPCPuppet, DynamicEntitySpec,
    # v3: Rig deformation / visual subsystem
    BodyType, BoneTransform, DeformationRig, MorphTargetEntry,
)

# ── Core engine systems ────────────────────────────────────────────
from .systems import (
    DynamicEntitySystem, DelaySystem, DelayCallback,
    CallbackSystem, CallbackSystemHandler, CallbackSystemEvent,
    KeyInputEvent, GameSessionEvent, InputTarget,
    SystemRequestsHandler, ScriptableSystem,
    ScriptableSystemsContainer,
)

# ── GameInstance facade & globals ──────────────────────────────────
from .game_instance import (
    GameInstance, GetPlayer, FindEntityByID, IsDefined, SqrtF, Cast,
    Equals, ArraySize, ArrayClear, ArrayPush, ArrayErase,
    NameToString, ModLog, get_log, clear_log,
)

# ── TweakDB ────────────────────────────────────────────────────────
from .tweakdb import (
    TweakDBID, gamedataRecord,
    gamedataDamageType, gamedataQuality,
    gamedataWeaponEvolution, gamedataItemType,
    gamedataCyberwareType, gamedataStatType, gamedataStatPoolType,
    WeaponRecord, ArmorRecord, CyberwareRecord, PerkRecord, ConsumableRecord,
    TweakDB,
)

# ── Stats system ───────────────────────────────────────────────────
from .stats import (
    CharacterStats, NPCStats, StatsSystem,
    StatModifier, StatModifierType, PerkState,
    preset_early_game_v, preset_netrunner_v,
    preset_street_samurai_v, preset_gunslinger_v,
    ATTR_MIN, ATTR_MAX, SKILL_MIN, SKILL_MAX,
    LEVEL_MIN, LEVEL_MAX,
)

# ── Inventory system ───────────────────────────────────────────────
from .inventory import (
    ItemID, ItemData, EquipmentSlot,
    TransactionSystem, EquipmentSystem,
    StreetCredSystem,
)

# ── Combat / damage system ─────────────────────────────────────────
from .combat import (
    HitFlag, HitInstance, DamageSystem,
    StatusEffectType, StatusEffectInstance, StatusEffectController,
    WeaponState,
)

# ── Quest system ───────────────────────────────────────────────────
from .quests import (
    FactID, FactManager,
    QuestNodeType, QuestNodeResult, QuestNode,
    QuestObjective, ObjectiveStatus, QuestPhase,
    JournalManager, QuestJournalEntry,
    QuestSystem,
)

# ── AI system (NEW) ────────────────────────────────────────────────
from .ai import (
    EAIAttitude, AttitudeAgent,
    AICommandType, AICommand,
    AIFollowTargetCommand, AITeleportCommand, AIMoveToCommand,
    AIHoldPositionCommand, AIPlayAnimationCommand, AIPlayVoiceOverCommand,
    AITriggerCombatCommand,
    AIFollowerRole, AINoRole, AIRole,
    AIControllerComponent,
)

# ── Appearance system (NEW) ────────────────────────────────────────
from .appearance import (
    AppearanceRecord, EntityAppearanceDB, AppearanceComponent,
    AppearanceDatabase, AppearanceTrigger, AppearanceTriggerSystem,
)

# ── World systems (NEW) ────────────────────────────────────────────
from .world import (
    gameGodModeType, GodModeSystem,
    EulerAngles, TeleportationFacility,
    StaticEntitySpec, StaticEntity, StaticEntitySystem,
    WorkspotSystem,
    TargetingSystem,
    MappinData, MappinSystem,
    WeatherID, WeatherSystem,
    GameTimeSystem,
    GameplayRestriction, GameplayStatusEffect, GameplayStatusEffectSystem,
    ObserverRegistry,
)

# ── Visual verification ────────────────────────────────────────────
from .visual_snapshot import VisualSnapshot
from .skeleton import (
    CP2077_SKELETON,
    generate_skeleton_svg, generate_skeleton_svg_comparison,
    render_skeleton_png, render_comparison_png,
    write_svg, export_gltf_json,
)

# ── Simulation orchestrator ────────────────────────────────────────
from .simulation import GameSimulation
