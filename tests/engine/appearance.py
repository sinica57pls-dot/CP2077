"""
Appearance System
=================
Simulates CP2077's NPC appearance management used heavily by AMM.

AMM's core loop:
  1. User picks appearance from SQLite db
  2. handle:PrefetchAppearanceChange(appName)   -- loads texture/mesh assets
  3. handle:ScheduleAppearanceChange(appName)   -- applies on next game tick
  4. Custom appearances (Collabs/) inject mesh/material overrides

This module provides:
  AppearanceRecord        -- one entry from AMM's appearances / custom_appearances table
  AppearanceComponent     -- per-entity appearance state
  AppearanceDatabase      -- lightweight in-memory replica of AMM's SQLite
  AppearanceTrigger       -- zone / combat / stealth auto-trigger
  AppearanceTriggerSystem -- evaluates triggers and fires ScheduleAppearanceChange
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ═══════════════════════════════════════════════════════════════════════════════
#  Data records  (mirror AMM's SQLite tables)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AppearanceRecord:
    """One row from AMM's appearances / custom_appearances SQLite tables."""
    name: str
    entity_id:   int    = 0
    base:        str    = ""       # base appearance it inherits from
    mesh_path:   str    = ""       # override mesh resource path
    mesh_app:    str    = ""       # override mesh appearance name
    mesh_mask:   int    = 0        # chunk visibility bitmask
    collab_tag:  str    = ""       # mod collaboration tag
    is_custom:   bool   = False

    def IsCustom(self) -> bool:
        return self.is_custom


@dataclass
class EntityAppearanceDB:
    """All known appearances for one entity (mirror of AMM SQLite join)."""
    entity_name: str
    entity_path: str  = ""
    appearances: List[AppearanceRecord] = field(default_factory=list)

    def GetAppearanceNames(self) -> List[str]:
        return [a.name for a in self.appearances]

    def GetAppearance(self, name: str) -> Optional[AppearanceRecord]:
        for a in self.appearances:
            if a.name == name:
                return a
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  AppearanceComponent  (attached to every NPCPuppet)
# ═══════════════════════════════════════════════════════════════════════════════

class AppearanceComponent:
    """
    Simulates the appearance state of a puppet entity.

    Mirrors:
      handle:GetCurrentAppearanceName()    -> CName (str)
      handle:PrefetchAppearanceChange(app) -> async asset load
      handle:ScheduleAppearanceChange(app) -> apply on next tick

    In our simulation 'next tick' is immediate since we don't have a real
    game loop -- ScheduleAppearanceChange applies instantly.
    """

    def __init__(self, initial: str = "default"):
        self._current:   str            = initial
        self._prefetched: Optional[str] = None
        self._pending:   Optional[str]  = None     # scheduled but not yet applied
        self._history:   List[str]      = [initial]
        # custom appearances registered by Collabs/ mods
        self._custom: Dict[str, AppearanceRecord] = {}

    # ── Core appearance API ───────────────────────────────────────────────────

    def GetCurrentAppearanceName(self) -> str:
        return self._current

    def PrefetchAppearanceChange(self, app_name: str):
        """Pre-load assets for app_name (does not switch yet)."""
        self._prefetched = app_name

    def ScheduleAppearanceChange(self, app_name: str):
        """Schedule an appearance switch.  In sim-time this is immediate."""
        self._pending = app_name
        self._flush_pending()

    def _flush_pending(self):
        if self._pending is not None:
            self._current = self._pending
            self._history.append(self._current)
            self._pending = None

    # ── Tick (if caller wants deferred application) ───────────────────────────

    def Tick(self):
        """Apply any pending scheduled appearance change."""
        self._flush_pending()

    # ── Custom appearance registry ────────────────────────────────────────────

    def RegisterCustomAppearance(self, record: AppearanceRecord):
        self._custom[record.name] = record

    def UnregisterCustomAppearance(self, name: str):
        self._custom.pop(name, None)

    def GetCustomAppearance(self, name: str) -> Optional[AppearanceRecord]:
        return self._custom.get(name)

    def GetCustomAppearanceNames(self) -> List[str]:
        return list(self._custom)

    # ── Queries ───────────────────────────────────────────────────────────────

    def GetChangeHistory(self) -> List[str]:
        return list(self._history)

    def GetChangeCount(self) -> int:
        """Number of appearance changes (initial appearance doesn't count)."""
        return len(self._history) - 1

    def WasPrefetched(self, app_name: str) -> bool:
        return self._prefetched == app_name


# ═══════════════════════════════════════════════════════════════════════════════
#  AppearanceDatabase  (in-memory replacement for AMM's SQLite)
# ═══════════════════════════════════════════════════════════════════════════════

class AppearanceDatabase:
    """
    Lightweight in-memory version of AMM's db.sqlite3.

    Stores appearances per entity name.  Tests can seed it with
    representative data from the real AMM database.
    """

    # A representative slice of AMM's entities + appearances
    _BUILTIN: Dict[str, List[str]] = {
        "Judy Alvarez": [
            "judy_default", "judy_casual", "judy_corpo",
            "judy_swimsuit", "judy_punk",
        ],
        "Panam Palmer": [
            "panam_default", "panam_nomad", "panam_corpo",
        ],
        "V (Female)": [
            "v_default", "v_tshirt", "v_corpo",
        ],
        "Johnny Silverhand": [
            "johnny_default", "johnny_rockerboy",
        ],
        "Rogue Amendiares": [
            "rogue_default", "rogue_youngself",
        ],
        "Maelstrom Ganger": [
            "maelstrom_01", "maelstrom_02", "maelstrom_03",
        ],
    }

    def __init__(self):
        # entity_name -> EntityAppearanceDB
        self._entities: Dict[str, EntityAppearanceDB] = {}
        self._seed_builtin()

    def _seed_builtin(self):
        for name, apps in self._BUILTIN.items():
            db = EntityAppearanceDB(entity_name=name)
            for app_name in apps:
                db.appearances.append(AppearanceRecord(name=app_name,
                                                       entity_id=id(name)))
            self._entities[name] = db

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def RegisterEntity(self, db: EntityAppearanceDB):
        self._entities[db.entity_name] = db

    def GetEntity(self, name: str) -> Optional[EntityAppearanceDB]:
        return self._entities.get(name)

    def GetAppearances(self, entity_name: str) -> List[str]:
        db = self._entities.get(entity_name)
        return db.GetAppearanceNames() if db else []

    def AddAppearance(self, entity_name: str, record: AppearanceRecord):
        if entity_name not in self._entities:
            self._entities[entity_name] = EntityAppearanceDB(entity_name=entity_name)
        self._entities[entity_name].appearances.append(record)

    def GetEntityCount(self) -> int:
        return len(self._entities)

    def GetTotalAppearanceCount(self) -> int:
        return sum(len(e.appearances) for e in self._entities.values())


# ═══════════════════════════════════════════════════════════════════════════════
#  Appearance Triggers  (AMM's appearance_triggers table)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AppearanceTrigger:
    """
    Automatic appearance change rule.
    Mirrors AMM's appearance_triggers feature (change appearance
    when entering a zone, entering combat, or entering stealth).
    """
    entity_id:  Any          # EntityID of the puppet
    condition:  str          # "zone:<name>", "combat", "stealth", "always"
    appearance: str          # appearance to switch to when condition is met

    def matches(self, zone: str = "", in_combat: bool = False,
                in_stealth: bool = False) -> bool:
        c = self.condition
        if c == "always":
            return True
        if c == "combat":
            return in_combat
        if c == "stealth":
            return in_stealth
        if c.startswith("zone:"):
            return zone == c[5:]
        return False


class AppearanceTriggerSystem:
    """
    Evaluates AppearanceTriggers and fires ScheduleAppearanceChange on match.

    AMM uses this for zone-based and combat-based appearance switches
    (e.g. Judy switches to swimwear near the baths).
    """

    def __init__(self):
        self._triggers: List[AppearanceTrigger] = []

    def RegisterTrigger(self, trigger: AppearanceTrigger):
        self._triggers.append(trigger)

    def RemoveTriggers(self, entity_id):
        self._triggers = [t for t in self._triggers
                          if t.entity_id != entity_id]

    def GetTriggerCount(self, entity_id=None) -> int:
        if entity_id is None:
            return len(self._triggers)
        return sum(1 for t in self._triggers if t.entity_id == entity_id)

    def EvaluateTriggers(self, entities: Sequence, zone: str = "",
                         in_combat: bool = False, in_stealth: bool = False):
        """
        Check all triggers against the current world state and apply
        matching appearance changes to the relevant entities.

        `entities` is a list of puppet objects that expose:
          - GetEntityID() -> EntityID
          - _appearance: AppearanceComponent
        """
        for trigger in self._triggers:
            if not trigger.matches(zone, in_combat, in_stealth):
                continue
            for entity in entities:
                if entity.GetEntityID() == trigger.entity_id:
                    if hasattr(entity, '_appearance'):
                        entity._appearance.ScheduleAppearanceChange(
                            trigger.appearance)
                    break
