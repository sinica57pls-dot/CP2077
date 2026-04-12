"""
Quest System Simulation
========================

Mirrors the quest systems from:
  src/Red/QuestsSystem.hpp       (QuestSystem, FactManager)
  src/App/Quest/                 (QuestPhaseExecutor, QuestPhaseRegistry)
  scripts/Quest/                 (FactDB, quest utilities)

CP2077 quest architecture:
  ┌─────────────────────────────────────────────────────┐
  │  QuestSystem                                        │
  │    ├── QuestPhaseGraph  (branching quest execution) │
  │    │     ├── QuestPhaseNode (logic node)            │
  │    │     └── QuestPhaseSocket (connections)         │
  │    └── FactManager  (shared fact/var store)         │
  │          ├── Fact  (integer counter, any source)    │
  │          └── QuestVar (typed variable per quest)    │
  │                                                     │
  │  JournalManager  (player-visible objectives/log)   │
  └─────────────────────────────────────────────────────┘

Facts are the core currency of CP2077's quest system.  Any system can
write an integer fact (SetFact) and any quest node can read it (GetFact)
to branch.  This makes the system extremely composable -- combat, economy,
conversations, and mods all communicate through facts.

References:
  src/Red/QuestsSystem.hpp
  https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/
  Cyberpunk 2077 Modding Discord #quest-scripting channel
"""

from __future__ import annotations
import enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ════════════════════════════════════════════════════════════════════════════
#  FactID  (mirrors src/Red/QuestsSystem.hpp FactID)
# ════════════════════════════════════════════════════════════════════════════

class FactID:
    """Hashed ID for a named quest fact.

    In the real game, facts are looked up by CName hash.
    Here we use str for readability.
    """
    __slots__ = ('_name',)

    def __init__(self, name: str):
        self._name = name.lower()   # facts are case-insensitive in the game

    @property
    def name(self) -> str:
        return self._name

    def __eq__(self, other) -> bool:
        if isinstance(other, FactID):
            return self._name == other._name
        if isinstance(other, str):
            return self._name == other.lower()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._name)

    def __repr__(self) -> str:
        return f"FactID({self._name!r})"


# ════════════════════════════════════════════════════════════════════════════
#  FactManager  (mirrors src/Red/QuestsSystem.hpp  FactManager)
# ════════════════════════════════════════════════════════════════════════════

class FactManager:
    """Global fact store.  Facts are named integer counters/flags.

    In CP2077 quests, the pattern is:
      SetFact("q001_met_jackie", 1)   -- flag set when player meets Jackie
      GetFact("q001_met_jackie")      -- returns 1 later
      AddFact("kill_count", 1)        -- increment a running counter

    REDscript API (from scripts/Quest/):
      GameInstance.GetQuestsSystem().SetFact(name, value)
      GameInstance.GetQuestsSystem().GetFact(name)  → Int
      GameInstance.GetQuestsSystem().AddFact(name, delta)
    """

    def __init__(self):
        self._facts: Dict[FactID, int] = {}
        self._listeners: Dict[FactID, List[Callable]] = {}

    # ── Core API ─────────────────────────────────────────────────────────────

    def SetFact(self, name: str, value: int) -> None:
        fid = FactID(name)
        self._facts[fid] = value
        self._notify(fid, value)

    def GetFact(self, name: str) -> int:
        fid = FactID(name)
        return self._facts.get(fid, 0)

    def AddFact(self, name: str, delta: int = 1) -> int:
        """Increment a fact by delta and return the new value."""
        fid   = FactID(name)
        new   = self._facts.get(fid, 0) + delta
        self._facts[fid] = new
        self._notify(fid, new)
        return new

    def FactDefined(self, name: str) -> bool:
        return FactID(name) in self._facts

    def ResetFact(self, name: str) -> None:
        fid = FactID(name)
        self._facts.pop(fid, None)
        self._notify(fid, 0)

    def ResetAll(self) -> None:
        """Clear all facts (e.g. on new game)."""
        self._facts.clear()

    # ── Observation ──────────────────────────────────────────────────────────

    def RegisterListener(self, name: str, callback: Callable[[int], None]) -> None:
        """Call `callback(new_value)` whenever this fact changes."""
        fid = FactID(name)
        self._listeners.setdefault(fid, []).append(callback)

    def UnregisterListener(self, name: str, callback: Callable) -> None:
        fid = FactID(name)
        listeners = self._listeners.get(fid, [])
        self._listeners[fid] = [l for l in listeners if l is not callback]

    def _notify(self, fid: FactID, value: int) -> None:
        for cb in self._listeners.get(fid, []):
            cb(value)

    # ── Bulk helpers ──────────────────────────────────────────────────────────

    def SetFacts(self, facts: Dict[str, int]) -> None:
        for name, value in facts.items():
            self.SetFact(name, value)

    def Snapshot(self) -> Dict[str, int]:
        """Return a plain dict copy of all current facts (for test assertions)."""
        return {fid.name: v for fid, v in self._facts.items()}


# ════════════════════════════════════════════════════════════════════════════
#  Quest node types  (mirrors QuestPhaseNode kinds)
# ════════════════════════════════════════════════════════════════════════════

class QuestNodeType(enum.Enum):
    Start        = "Start"
    End          = "End"
    FactCheck    = "FactCheck"      # branch on fact value
    SetFact      = "SetFact"        # write a fact
    ObjectiveAdd = "ObjectiveAdd"   # add journal objective
    ObjectiveDone = "ObjectiveDone" # mark objective complete
    Cutscene     = "Cutscene"
    ItemGrant    = "ItemGrant"
    ItemCheck    = "ItemCheck"
    AreaEnter    = "AreaEnter"      # player enters a trigger zone
    Dialogue     = "Dialogue"       # conversation node
    Custom       = "Custom"         # arbitrary callback


class QuestNodeResult(enum.Enum):
    Continue  = "Continue"   # move to next node in sequence
    Jump      = "Jump"       # jump to a named node
    Fail      = "Fail"       # quest failed
    End       = "End"        # quest ended


@dataclass
class QuestNode:
    """One node in a quest phase graph."""
    node_id:   str
    node_type: QuestNodeType
    # Outgoing socket connections: "out_true" / "out_false" / "out" → node_id
    outputs:   Dict[str, str] = field(default_factory=dict)
    # Payload specific to each node type
    payload:   Dict[str, Any] = field(default_factory=dict)
    # Optional callback for Custom nodes
    callback:  Optional[Callable[['QuestPhase', 'FactManager'], QuestNodeResult]] = field(
        default=None, repr=False)


# ════════════════════════════════════════════════════════════════════════════
#  QuestObjective  (player-facing journal entry)
# ════════════════════════════════════════════════════════════════════════════

class ObjectiveStatus(enum.Enum):
    Inactive  = "Inactive"
    Active    = "Active"
    Done      = "Done"
    Failed    = "Failed"


@dataclass
class QuestObjective:
    objective_id: str
    description:  str
    status:       ObjectiveStatus = ObjectiveStatus.Inactive
    optional:     bool = False


# ════════════════════════════════════════════════════════════════════════════
#  QuestPhase  -- one self-contained phase of a quest
# ════════════════════════════════════════════════════════════════════════════

class QuestPhase:
    """Executable quest phase graph.

    Mirrors QuestPhaseInstance from src/App/Quest/QuestPhaseExecutor.hpp.
    Each phase has a graph of nodes and executes them in sequence /
    branch order, communicating via the FactManager.

    Usage:
        phase = QuestPhase("q001_meet_jackie")
        phase.add_node(QuestNode("start", QuestNodeType.Start,
                                 outputs={"out": "set_met"}))
        phase.add_node(QuestNode("set_met", QuestNodeType.SetFact,
                                 outputs={"out": "end"},
                                 payload={"fact": "q001_met_jackie", "value": 1}))
        phase.add_node(QuestNode("end", QuestNodeType.End))
        phase.execute(fact_manager)
    """

    def __init__(self, phase_id: str):
        self.phase_id  = phase_id
        self._nodes:   Dict[str, QuestNode] = {}
        self._current: Optional[str]        = None   # current node id
        self._done:    bool                 = False
        self._failed:  bool                 = False

    def add_node(self, node: QuestNode) -> 'QuestPhase':
        self._nodes[node.node_id] = node
        return self

    def execute(self, facts: FactManager,
                journal: Optional['JournalManager'] = None) -> bool:
        """Execute the phase from its Start node until End or Fail.
        Returns True if phase completed normally.
        """
        # Find start node
        start = next(
            (n for n in self._nodes.values()
             if n.node_type == QuestNodeType.Start), None)
        if start is None:
            raise RuntimeError(f"Phase {self.phase_id!r} has no Start node")

        self._current = start.node_id
        self._done    = False
        self._failed  = False

        for _ in range(1000):   # safety iteration cap
            if self._current is None:
                break
            node = self._nodes.get(self._current)
            if node is None:
                break

            result, next_key = self._execute_node(node, facts, journal)

            if result == QuestNodeResult.End or node.node_type == QuestNodeType.End:
                self._done = True
                break
            if result == QuestNodeResult.Fail:
                self._failed = True
                break

            # Resolve next node
            if result == QuestNodeResult.Jump:
                # next_key is the target node id directly
                self._current = next_key
            else:
                # Continue: follow the "out" socket (or "out_true" etc.)
                out_key = next_key or "out"
                self._current = node.outputs.get(out_key)
                if self._current is None:
                    # No outgoing connection = implicit end
                    self._done = True
                    break

        return self._done

    def _execute_node(self, node: QuestNode, facts: FactManager,
                      journal: Optional['JournalManager']) -> Tuple[QuestNodeResult, Optional[str]]:
        """Process a single node.  Returns (result, output_socket_key)."""
        t = node.node_type

        if t == QuestNodeType.Start:
            return QuestNodeResult.Continue, "out"

        if t == QuestNodeType.End:
            return QuestNodeResult.End, None

        if t == QuestNodeType.SetFact:
            fact_name = node.payload.get("fact", "")
            value     = node.payload.get("value", 1)
            delta     = node.payload.get("delta", None)
            if delta is not None:
                facts.AddFact(fact_name, delta)
            else:
                facts.SetFact(fact_name, value)
            return QuestNodeResult.Continue, "out"

        if t == QuestNodeType.FactCheck:
            fact_name = node.payload.get("fact", "")
            condition = node.payload.get("condition", ">=")
            threshold = node.payload.get("threshold", 1)
            val = facts.GetFact(fact_name)
            passed = (
                (condition == ">="  and val >= threshold) or
                (condition == ">"   and val > threshold)  or
                (condition == "<="  and val <= threshold) or
                (condition == "<"   and val < threshold)  or
                (condition == "=="  and val == threshold) or
                (condition == "!="  and val != threshold)
            )
            out_socket = "out_true" if passed else "out_false"
            return QuestNodeResult.Continue, out_socket

        if t == QuestNodeType.ObjectiveAdd:
            if journal:
                obj_id   = node.payload.get("objective_id", "")
                obj_desc = node.payload.get("description", "")
                optional = node.payload.get("optional", False)
                journal.add_objective(self.phase_id, obj_id, obj_desc, optional)
            return QuestNodeResult.Continue, "out"

        if t == QuestNodeType.ObjectiveDone:
            if journal:
                obj_id = node.payload.get("objective_id", "")
                journal.complete_objective(self.phase_id, obj_id)
            return QuestNodeResult.Continue, "out"

        if t == QuestNodeType.ItemGrant:
            # Handled externally by the caller / GameSimulation
            # just record the intent
            return QuestNodeResult.Continue, "out"

        if t == QuestNodeType.ItemCheck:
            # In a real test, the caller must wire in a check callback via Custom
            # Default: assume player has the item (optimistic)
            has_item = node.payload.get("_result", True)
            socket = "out_true" if has_item else "out_false"
            return QuestNodeResult.Continue, socket

        if t == QuestNodeType.Dialogue:
            # Record choice made (payload["choice_made"] set externally)
            choice = node.payload.get("choice_made", "default")
            out = node.outputs.get(f"out_{choice}", node.outputs.get("out"))
            if out:
                return QuestNodeResult.Jump, out
            return QuestNodeResult.Continue, "out"

        if t == QuestNodeType.Custom:
            if node.callback:
                result = node.callback(self, facts)
                return result, "out"
            return QuestNodeResult.Continue, "out"

        # Unknown node type -- log and skip
        return QuestNodeResult.Continue, "out"

    @property
    def is_done(self) -> bool:
        return self._done

    @property
    def is_failed(self) -> bool:
        return self._failed


# ════════════════════════════════════════════════════════════════════════════
#  JournalManager  (player-facing quest log)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class QuestJournalEntry:
    """One quest in V's journal."""
    quest_id:     str
    title:        str
    status:       ObjectiveStatus = ObjectiveStatus.Inactive
    objectives:   Dict[str, QuestObjective] = field(default_factory=dict)
    description:  str = ""


class JournalManager:
    """Player-visible quest journal.

    Mirrors JournalManager from src/Red/GameInstance.hpp.
    Tracks quests and their objectives as shown in the in-game journal UI.
    """

    def __init__(self):
        self._quests: Dict[str, QuestJournalEntry] = {}

    def add_quest(self, quest_id: str, title: str,
                  description: str = "") -> QuestJournalEntry:
        entry = QuestJournalEntry(quest_id=quest_id, title=title,
                                  description=description,
                                  status=ObjectiveStatus.Active)
        self._quests[quest_id] = entry
        return entry

    def add_objective(self, quest_id: str, objective_id: str,
                      description: str, optional: bool = False) -> None:
        if quest_id not in self._quests:
            self.add_quest(quest_id, quest_id)
        obj = QuestObjective(
            objective_id=objective_id,
            description=description,
            status=ObjectiveStatus.Active,
            optional=optional,
        )
        self._quests[quest_id].objectives[objective_id] = obj

    def complete_objective(self, quest_id: str, objective_id: str) -> bool:
        entry = self._quests.get(quest_id)
        if not entry:
            return False
        obj = entry.objectives.get(objective_id)
        if not obj:
            return False
        obj.status = ObjectiveStatus.Done
        return True

    def fail_objective(self, quest_id: str, objective_id: str) -> bool:
        entry = self._quests.get(quest_id)
        if not entry:
            return False
        obj = entry.objectives.get(objective_id)
        if not obj:
            return False
        obj.status = ObjectiveStatus.Failed
        return True

    def complete_quest(self, quest_id: str) -> bool:
        entry = self._quests.get(quest_id)
        if not entry:
            return False
        entry.status = ObjectiveStatus.Done
        return True

    def fail_quest(self, quest_id: str) -> bool:
        entry = self._quests.get(quest_id)
        if not entry:
            return False
        entry.status = ObjectiveStatus.Failed
        return True

    def get_quest(self, quest_id: str) -> Optional[QuestJournalEntry]:
        return self._quests.get(quest_id)

    def get_active_quests(self) -> List[QuestJournalEntry]:
        return [q for q in self._quests.values()
                if q.status == ObjectiveStatus.Active]

    def is_objective_done(self, quest_id: str, objective_id: str) -> bool:
        entry = self._quests.get(quest_id)
        if not entry:
            return False
        obj = entry.objectives.get(objective_id)
        return obj is not None and obj.status == ObjectiveStatus.Done


# ════════════════════════════════════════════════════════════════════════════
#  QuestSystem  (top-level aggregate, exposed via GameInstance)
# ════════════════════════════════════════════════════════════════════════════

class QuestSystem:
    """Top-level quest coordinator.

    Provides the combined FactManager + JournalManager interface that
    mods access via  GameInstance.GetQuestsSystem().

    All in-game quest scripting routes through this class.
    """

    def __init__(self):
        self.facts   = FactManager()
        self.journal = JournalManager()
        self._phases: Dict[str, QuestPhase] = {}

    # ── FactManager pass-through (real API) ──────────────────────────────────

    def SetFact(self, name: str, value: int) -> None:
        self.facts.SetFact(name, value)

    def GetFact(self, name: str) -> int:
        return self.facts.GetFact(name)

    def AddFact(self, name: str, delta: int = 1) -> int:
        return self.facts.AddFact(name, delta)

    def FactDefined(self, name: str) -> bool:
        return self.facts.FactDefined(name)

    # ── Phase management ──────────────────────────────────────────────────────

    def register_phase(self, phase: QuestPhase) -> None:
        self._phases[phase.phase_id] = phase

    def execute_phase(self, phase_id: str) -> bool:
        phase = self._phases.get(phase_id)
        if not phase:
            raise KeyError(f"Phase {phase_id!r} not registered")
        return phase.execute(self.facts, self.journal)

    def get_phase(self, phase_id: str) -> Optional[QuestPhase]:
        return self._phases.get(phase_id)

    def reset(self) -> None:
        """Reset all facts and journal (new game)."""
        self.facts.ResetAll()
        self.journal = JournalManager()
        self._phases.clear()
