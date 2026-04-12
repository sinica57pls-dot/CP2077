"""
AI System
=========
Simulates CP2077's AI command processing, role management, and attitude system.

Mirrors the real AMM Lua patterns:
  - AIFollowerRole / AINoRole / AIRole  (companion vs hostile vs neutral)
  - AICommand hierarchy  (Follow, Teleport, MoveTo, HoldPosition, PlayAnimation, …)
  - AttitudeAgent  (friend / neutral / enemy tracking per entity)
  - EAIAttitude enum

Used by AMM:
  handle:GetAIControllerComponent():SetAIRole(AIFollowerRole.new())
  handle:GetAIControllerComponent():SendCommand(cmd)
  handle:GetAttitudeAgent():SetAttitudeGroup("PlayerAllies")
  handle:GetAttitudeAgent():SetAttitudeTowards(otherAgent, EAIAttitude.AIA_Friendly)
"""

from __future__ import annotations
import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
#  Attitude
# ═══════════════════════════════════════════════════════════════════════════════

class EAIAttitude(enum.Enum):
    AIA_Friendly = 0
    AIA_Neutral  = 1
    AIA_Hostile  = 2


# Attitude inferred from group name (mirrors CP2077 faction tables)
_GROUP_ATTITUDES: Dict[str, EAIAttitude] = {
    "PlayerAllies":        EAIAttitude.AIA_Friendly,
    "Friendly":            EAIAttitude.AIA_Friendly,
    "Hostile":             EAIAttitude.AIA_Hostile,
    "Ganger_Aggressive":   EAIAttitude.AIA_Hostile,
    "Ganger_Civilized":    EAIAttitude.AIA_Neutral,
    "Neutral":             EAIAttitude.AIA_Neutral,
    "Police":              EAIAttitude.AIA_Neutral,
}


class AttitudeAgent:
    """
    Simulates gamePuppet.GetAttitudeAgent().

    AMM usage:
      agent.SetAttitudeGroup("PlayerAllies")
      agent.SetAttitudeTowards(otherAgent, EAIAttitude.AIA_Friendly)
      agent.GetAttitudeTowards(otherAgent)
    """

    def __init__(self):
        self._group: str = "Neutral"
        # per-agent overrides keyed by id(other_agent)
        self._overrides: Dict[int, EAIAttitude] = {}

    # ── Group (affects default attitude towards all unspecified agents) ────────

    def SetAttitudeGroup(self, group: str):
        self._group = group

    def GetAttitudeGroup(self) -> str:
        return self._group

    # ── Per-agent overrides ───────────────────────────────────────────────────

    def SetAttitudeTowards(self, other_agent: "AttitudeAgent",
                           attitude: EAIAttitude):
        self._overrides[id(other_agent)] = attitude

    def GetAttitudeTowards(self, other_agent: "AttitudeAgent") -> EAIAttitude:
        override = self._overrides.get(id(other_agent))
        if override is not None:
            return override
        return _GROUP_ATTITUDES.get(self._group, EAIAttitude.AIA_Neutral)

    # ── Convenience predicates ────────────────────────────────────────────────

    def IsEnemy(self, other_agent: "AttitudeAgent") -> bool:
        return self.GetAttitudeTowards(other_agent) == EAIAttitude.AIA_Hostile

    def IsFriend(self, other_agent: "AttitudeAgent") -> bool:
        return self.GetAttitudeTowards(other_agent) == EAIAttitude.AIA_Friendly

    def IsNeutral(self, other_agent: "AttitudeAgent") -> bool:
        return self.GetAttitudeTowards(other_agent) == EAIAttitude.AIA_Neutral


# ═══════════════════════════════════════════════════════════════════════════════
#  AI Commands
# ═══════════════════════════════════════════════════════════════════════════════

class AICommandType(enum.Enum):
    Follow              = "Follow"
    Teleport            = "Teleport"
    MoveTo              = "MoveTo"
    HoldPosition        = "HoldPosition"
    PlayAnimation       = "PlayAnimation"
    PlayVoiceOver       = "PlayVoiceOver"
    SwitchPrimary       = "SwitchPrimaryWeapon"
    SwitchSecondary     = "SwitchSecondaryWeapon"
    Equip               = "Equip"
    TriggerCombat       = "TriggerCombat"


@dataclass
class AICommand:
    """Base for all AI commands sent via GetAIControllerComponent().SendCommand()."""
    command_type: AICommandType
    params:       dict  = field(default_factory=dict)
    _active:      bool  = field(default=True, init=False)

    def IsActive(self) -> bool:
        return self._active

    def Cancel(self):
        self._active = False


# ── Command factory functions (match AMM's Lua call patterns) ──────────────────

def AIFollowTargetCommand(target=None, distance: float = 2.0,
                          radius: float = 0.5) -> AICommand:
    """Companion follow command -- AMM calls this on Util:FollowTarget()."""
    return AICommand(AICommandType.Follow,
                     {"target": target, "distance": distance, "radius": radius})


def AITeleportCommand(position=None, yaw: float = 0.0) -> AICommand:
    """Teleport NPC to position -- AMM calls this on Util:TeleportNPCTo()."""
    return AICommand(AICommandType.Teleport,
                     {"position": position, "yaw": yaw})


def AIMoveToCommand(position=None, tolerance: float = 0.5) -> AICommand:
    return AICommand(AICommandType.MoveTo,
                     {"position": position, "tolerance": tolerance})


def AIHoldPositionCommand() -> AICommand:
    return AICommand(AICommandType.HoldPosition, {})


def AIPlayAnimationCommand(anim_name: str, looping: bool = False) -> AICommand:
    return AICommand(AICommandType.PlayAnimation,
                     {"anim_name": anim_name, "looping": looping})


def AIPlayVoiceOverCommand(vo_name: str) -> AICommand:
    return AICommand(AICommandType.PlayVoiceOver, {"vo_name": vo_name})


def AITriggerCombatCommand(target=None) -> AICommand:
    return AICommand(AICommandType.TriggerCombat, {"target": target})


# ═══════════════════════════════════════════════════════════════════════════════
#  AI Roles
# ═══════════════════════════════════════════════════════════════════════════════

class AIFollowerRole:
    """
    Companion role -- set by AMM when spawning a companion NPC.

    AMM: Spawn:SetNPCAsCompanion() creates AIFollowerRole with follower_ref = player
    """
    def __init__(self, follower_ref=None, follow_distance: float = 2.0):
        self.follower_ref    = follower_ref      # entity ref to follow (usually player)
        self.follow_distance = follow_distance


class AINoRole:
    """Neutral / no-role state (default for freshly spawned NPCs)."""
    pass


class AIRole:
    """Generic (hostile) role.  AMM uses this when toggling companion → hostile."""
    def __init__(self, attitude_group: str = "Hostile"):
        self.attitude_group = attitude_group


# ═══════════════════════════════════════════════════════════════════════════════
#  AI Controller Component
# ═══════════════════════════════════════════════════════════════════════════════

class AIControllerComponent:
    """
    Simulates gamePuppet.GetAIControllerComponent().

    AMM uses:
      GetAIRole() / SetAIRole(role)
      SendCommand(cmd)
      StopExecutingCommand(cmd_type, interrupt)
      CancelCommand(cmd)
    """

    def __init__(self):
        self._role: Any                          = AINoRole()
        self._active_cmd: Optional[AICommand]    = None
        self._history:    List[AICommand]        = []

    # ── Role management ──────────────────────────────────────────────────────

    def GetAIRole(self):
        return self._role

    def SetAIRole(self, role):
        self._role = role

    def IsFollower(self) -> bool:
        return isinstance(self._role, AIFollowerRole)

    def IsHostile(self) -> bool:
        return isinstance(self._role, AIRole)

    def IsNeutral(self) -> bool:
        return isinstance(self._role, AINoRole)

    # ── Command processing ───────────────────────────────────────────────────

    def SendCommand(self, cmd: AICommand):
        """Replaces the active command (cancelling the previous one)."""
        if self._active_cmd and self._active_cmd.IsActive():
            self._active_cmd.Cancel()
        self._active_cmd = cmd
        self._history.append(cmd)

    def StopExecutingCommand(self, cmd_type: AICommandType,
                             interrupt: bool = False):
        if (self._active_cmd
                and self._active_cmd.command_type == cmd_type
                and self._active_cmd.IsActive()):
            self._active_cmd.Cancel()
            self._active_cmd = None

    def CancelCommand(self, cmd: Optional[AICommand] = None):
        if cmd is None:
            if self._active_cmd:
                self._active_cmd.Cancel()
            self._active_cmd = None
        elif self._active_cmd is cmd:
            self._active_cmd.Cancel()
            self._active_cmd = None

    # ── Queries ──────────────────────────────────────────────────────────────

    def GetActiveCommand(self) -> Optional[AICommand]:
        return self._active_cmd

    def GetCommandHistory(self) -> List[AICommand]:
        return list(self._history)

    def GetCommandCount(self) -> int:
        return len(self._history)

    def GetLastCommandOfType(self, cmd_type: AICommandType) -> Optional[AICommand]:
        for cmd in reversed(self._history):
            if cmd.command_type == cmd_type:
                return cmd
        return None

    def HasActiveCommand(self, cmd_type: Optional[AICommandType] = None) -> bool:
        if self._active_cmd is None or not self._active_cmd.IsActive():
            return False
        if cmd_type is not None:
            return self._active_cmd.command_type == cmd_type
        return True
