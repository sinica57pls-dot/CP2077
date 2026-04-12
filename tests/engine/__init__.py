"""
RED4 Engine Simulation
======================

Offline simulation of Cyberpunk 2077's RED4 engine for testing mods
without launching the game.  Built from:
  - Codeware C++ source (src/App/World/DynamicEntitySystem.cpp, etc.)
  - RedScript API stubs (scripts/World/, scripts/Entity/, etc.)

Usage:
    from engine import GameSimulation, Vector4, Quaternion
    sim = GameSimulation()
    sim.start_session(player_pos=(0, 0, 0))
    npc = sim.spawn_npc(tags=["AMM"], pos=(10, 0, 0))
    sim.tick(count=4)
    sim.teardown()
"""

# Types
from .types import (
    FixedPoint, Vector4, Vector3, Quaternion,
    WorldPosition, WorldTransform, CName, EntityID,
    EInputKey, EInputAction, DelayID,
)

# Entities
from .entity import (
    IScriptable, IComponent, IVisualComponent,
    MeshComponent, entSkinnedMeshComponent,
    entMorphTargetSkinnedMeshComponent,
    Entity, GameObject, gamePuppet, ScriptedPuppet,
    PlayerPuppet, NPCPuppet, DynamicEntitySpec,
)

# Systems
from .systems import (
    DynamicEntitySystem, DelaySystem, DelayCallback,
    CallbackSystem, CallbackSystemHandler, CallbackSystemEvent,
    KeyInputEvent, GameSessionEvent, InputTarget,
    SystemRequestsHandler, ScriptableSystem,
    ScriptableSystemsContainer,
)

# GameInstance facade & globals
from .game_instance import (
    GameInstance, GetPlayer, IsDefined, SqrtF, Cast,
    Equals, ArraySize, ArrayClear, ArrayPush, ArrayErase,
    NameToString, ModLog, get_log, clear_log,
)

# Simulation orchestrator
from .simulation import GameSimulation
