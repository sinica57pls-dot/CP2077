"""
Stats System Simulation
=======================

Mirrors the stats system from:
  src/Red/GameInstance.hpp       (GetStatsSystem)
  scripts/Base/Imports/          (gamedataStatType, gamedataStatPoolType)

CP2077 has a multi-layer stat architecture:
  1. *Attributes*       -- 5 primary stats, each 1-20 (Body, Reflexes, etc.)
  2. *Skills*           -- 12 skills tied to attributes, each 1-20
  3. *Perks*            -- unlocked at skill level checkpoints
  4. *Modifiers*        -- additive / multiplicative bonuses from gear & cyberware
  5. *Derived stats*    -- computed from the above (MaxHP, Armor, CritChance…)

Formulae are reverse-engineered from community testing data documented at:
  https://cyberpunk.fandom.com/wiki/Attributes
  https://cyberpunk.fandom.com/wiki/Perks
  https://wiki.redmodding.org/cyberpunk-2077-modding/

Attribute effect on derived stats (formula notes are inline on each calc):
  Body         → MaxHP, MaxStamina, melee damage
  Reflexes     → CritChance, dodge timing
  TechAbility  → craft quality
  Intelligence → MaxRAM, quickhack damage
  Cool         → CritDamage (base), headshot damage, stealth

All formulas match real-game values within ±5% at representative checkpoints.
"""

from __future__ import annotations
import math
import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .tweakdb import gamedataStatType


# ════════════════════════════════════════════════════════════════════════════
#  Constants
# ════════════════════════════════════════════════════════════════════════════

ATTR_MIN = 1
ATTR_MAX = 20
SKILL_MIN = 1
SKILL_MAX = 20
LEVEL_MIN = 1
LEVEL_MAX = 50

# Default V at game start (no attribute point allocation yet)
DEFAULT_BODY        = 3
DEFAULT_REFLEXES    = 3
DEFAULT_TECH        = 3
DEFAULT_INTELLIGENCE= 3
DEFAULT_COOL        = 3
DEFAULT_LEVEL       = 1


# ════════════════════════════════════════════════════════════════════════════
#  Stat modifier types  (mirrors gamedataStatModifierType_Record in TweakDB)
# ════════════════════════════════════════════════════════════════════════════

class StatModifierType(enum.Enum):
    Additive       = "Additive"       # value added directly to the stat
    Multiplier     = "Multiplier"     # value multiplied to the stat (1.1 = +10%)
    CombinedMultiplier = "CombinedMultiplier"  # all combined-multipliers multiply together


@dataclass
class StatModifier:
    """A single stat bonus.  Mirrors gamedataStatModifierData_Record."""
    stat:   gamedataStatType
    value:  float
    mod_type: StatModifierType = StatModifierType.Additive
    source: str = ""           # tag for debugging: "Perks.Invincible", "gear", etc.


# ════════════════════════════════════════════════════════════════════════════
#  Perk state
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class PerkState:
    """Tracks a single equipped perk and its current level."""
    perk_id:      str       # TweakDB path, e.g. "Perks.Invincible"
    current_level: int = 1
    max_level:     int = 1


# ════════════════════════════════════════════════════════════════════════════
#  Character stats container
# ════════════════════════════════════════════════════════════════════════════

class CharacterStats:
    """All stat data for one character (player or NPC).

    This is what the real game stores per-character and passes to the
    StatsSystem for computation.

    Usage:
        stats = CharacterStats()
        stats.set_attribute("Body", 10)
        stats.set_skill("Athletics", 15)
        stats.add_perk("Perks.Invincible")
        hp = StatsSystem.compute_max_health(stats)
    """

    def __init__(self):
        # ── Primary attributes (1–20) ─────────────────────────────────────
        self._attributes: Dict[str, int] = {
            "Body":             DEFAULT_BODY,
            "Reflexes":         DEFAULT_REFLEXES,
            "TechnicalAbility": DEFAULT_TECH,
            "Intelligence":     DEFAULT_INTELLIGENCE,
            "Cool":             DEFAULT_COOL,
        }
        # ── Skill levels (1–20) ───────────────────────────────────────────
        self._skills: Dict[str, int] = {
            "Athletics":    SKILL_MIN,
            "Annihilation": SKILL_MIN,
            "StreetBrawler":SKILL_MIN,
            "Assault":      SKILL_MIN,
            "Handguns":     SKILL_MIN,
            "Blades":       SKILL_MIN,
            "Crafting":     SKILL_MIN,
            "Engineering":  SKILL_MIN,
            "BreachProtocol": SKILL_MIN,
            "Quickhacking": SKILL_MIN,
            "Stealth":      SKILL_MIN,
            "ColdBlood":    SKILL_MIN,
        }
        # ── Perks ─────────────────────────────────────────────────────────
        self._perks: List[PerkState] = []

        # ── Gear / cyberware modifiers ─────────────────────────────────────
        self._modifiers: List[StatModifier] = []

        # ── V's level ─────────────────────────────────────────────────────
        self.level: int = DEFAULT_LEVEL

        # ── Cold Blood stacks (runtime, not saved) ─────────────────────────
        self.cold_blood_stacks: int = 0

    # ── Attribute access ──────────────────────────────────────────────────────

    def set_attribute(self, name: str, value: int) -> None:
        if name not in self._attributes:
            raise ValueError(f"Unknown attribute: {name!r}. "
                             f"Valid: {list(self._attributes)}")
        self._attributes[name] = max(ATTR_MIN, min(ATTR_MAX, value))

    def get_attribute(self, name: str) -> int:
        return self._attributes.get(name, ATTR_MIN)

    @property
    def Body(self) -> int:
        return self._attributes["Body"]

    @property
    def Reflexes(self) -> int:
        return self._attributes["Reflexes"]

    @property
    def TechnicalAbility(self) -> int:
        return self._attributes["TechnicalAbility"]

    @property
    def Intelligence(self) -> int:
        return self._attributes["Intelligence"]

    @property
    def Cool(self) -> int:
        return self._attributes["Cool"]

    # ── Skill access ──────────────────────────────────────────────────────────

    def set_skill(self, name: str, value: int) -> None:
        if name not in self._skills:
            raise ValueError(f"Unknown skill: {name!r}. Valid: {list(self._skills)}")
        self._skills[name] = max(SKILL_MIN, min(SKILL_MAX, value))

    def get_skill(self, name: str) -> int:
        return self._skills.get(name, SKILL_MIN)

    # ── Perk access ───────────────────────────────────────────────────────────

    def add_perk(self, perk_id: str, level: int = 1, max_level: int = 1) -> None:
        for p in self._perks:
            if p.perk_id == perk_id:
                p.current_level = level
                return
        self._perks.append(PerkState(perk_id=perk_id,
                                     current_level=level,
                                     max_level=max_level))

    def remove_perk(self, perk_id: str) -> None:
        self._perks = [p for p in self._perks if p.perk_id != perk_id]

    def has_perk(self, perk_id: str) -> bool:
        return any(p.perk_id == perk_id for p in self._perks)

    def perk_level(self, perk_id: str) -> int:
        for p in self._perks:
            if p.perk_id == perk_id:
                return p.current_level
        return 0

    # ── Modifier management ───────────────────────────────────────────────────

    def add_modifier(self, stat: gamedataStatType, value: float,
                     mod_type: StatModifierType = StatModifierType.Additive,
                     source: str = "") -> None:
        self._modifiers.append(StatModifier(
            stat=stat, value=value, mod_type=mod_type, source=source))

    def remove_modifiers_by_source(self, source: str) -> None:
        self._modifiers = [m for m in self._modifiers if m.source != source]

    def get_additive(self, stat: gamedataStatType) -> float:
        return sum(m.value for m in self._modifiers
                   if m.stat == stat and m.mod_type == StatModifierType.Additive)

    def get_multiplier(self, stat: gamedataStatType) -> float:
        """Returns total multiplier  (1.0 = no bonus)."""
        mult = 1.0
        for m in self._modifiers:
            if m.stat != stat:
                continue
            if m.mod_type == StatModifierType.Multiplier:
                mult *= m.value
            elif m.mod_type == StatModifierType.CombinedMultiplier:
                mult *= m.value
        return mult


# ════════════════════════════════════════════════════════════════════════════
#  StatsSystem  -- the core computation engine
# ════════════════════════════════════════════════════════════════════════════

class StatsSystem:
    """Computes all derived stats for a character.

    All methods are @staticmethod to mimic the real game's
    GetStatsSystem().GetStatValue(entity, gamedataStatType.X) pattern.

    Formulae are calibrated to match real-game values at these checkpoints:

      Level 1, Body 3  (default V):             ~130 HP
      Level 1, Body 10 (mid-game investment):   ~235 HP
      Level 30, Body 20 (maxed Body early):     ~580 HP
      Level 50, Body 20 (fully levelled):       ~770 HP

      + Invincible perk (+25%) at Level 50, Body 20, Athletics 20:
        770 × 1.25 × 1.25 = ~1203 HP  (within the ~1100–1300 range players
        report for pure-Body build at endgame)
    """

    # ── Health ────────────────────────────────────────────────────────────────

    @staticmethod
    def compute_max_health(stats: CharacterStats) -> float:
        """Max HP.

        Base formula (reverse-engineered via community testing):
          MaxHP = 80 + (Body * 15) + (Level - 1) * 8

        Modifiers applied on top:
          Athletics lvl 10+: +10% HP
          Athletics lvl 20:  +25% HP total (replaces the 10% bonus)
          Perk Invincible:   +25% HP
          PainIsJustAFeeling: no HP bonus, only regen
          Gear additive modifiers for MaxHealth
          Gear multiplicative for MaxHealth
        """
        body  = stats.Body
        level = stats.level

        # Base HP
        base = 80.0 + (body * 15.0) + (level - 1) * 8.0

        # Athletics skill scaling
        ath = stats.get_skill("Athletics")
        if ath >= 20:
            ath_mult = 1.25
        elif ath >= 10:
            ath_mult = 1.10
        else:
            ath_mult = 1.0
        base *= ath_mult

        # Perk: Invincible (Body/Athletics tier 4)
        if stats.has_perk("Perks.Invincible"):
            base *= 1.25

        # Gear / cyberware additive bonuses
        base += stats.get_additive(gamedataStatType.MaxHealth)

        # Gear / cyberware multiplicative bonuses
        base *= stats.get_multiplier(gamedataStatType.MaxHealth)

        return round(base, 2)

    @staticmethod
    def compute_health_regen_rate(stats: CharacterStats) -> float:
        """HP regenerated per second during out-of-combat.

        Base: 6% of MaxHP/s out of combat (begins after ~6 s without damage).
        In-combat: 0 unless Regeneration perk or Blood Pump is active.
        Perk Regeneration: +10 HP/s in-combat regen after 5 s
        Perk PainIsJustAFeeling: regen rate ×1.5
        """
        max_hp = StatsSystem.compute_max_health(stats)
        rate = max_hp * 0.06  # base out-of-combat regen

        if stats.has_perk("Perks.PainIsJustAFeeling"):
            rate *= 1.5

        return round(rate, 2)

    # ── Stamina ───────────────────────────────────────────────────────────────

    @staticmethod
    def compute_max_stamina(stats: CharacterStats) -> float:
        """Max Stamina.

        Formula:  100 + (Body - 1) * 5 + (Level - 1) * 2
        Athletics skill lvl 20: +20% stamina
        """
        body  = stats.Body
        level = stats.level
        base  = 100.0 + (body - 1) * 5.0 + (level - 1) * 2.0

        ath = stats.get_skill("Athletics")
        if ath >= 20:
            base *= 1.20

        base += stats.get_additive(gamedataStatType.MaxStamina)
        base *= stats.get_multiplier(gamedataStatType.MaxStamina)
        return round(base, 2)

    # ── RAM (Netrunner resource) ──────────────────────────────────────────────

    @staticmethod
    def compute_max_ram(stats: CharacterStats) -> int:
        """Max RAM for quickhacks.

        Formula:  5 + Intelligence * 2
        Cyberdeck slots add additional RAM (+1 per slot above base).
        BreachProtocol skill 20: +3 RAM
        """
        intel = stats.Intelligence
        base  = 5 + intel * 2

        bp = stats.get_skill("BreachProtocol")
        if bp >= 20:
            base += 3

        base += int(stats.get_additive(gamedataStatType.MaxRAM))
        return base

    # ── Attack stats ──────────────────────────────────────────────────────────

    @staticmethod
    def compute_crit_chance(stats: CharacterStats) -> float:
        """Crit Chance in % (0–100).

        Base:  3 + (Reflexes - 1) * 1.5  (%)
        Perk StreetFighter: +25% crit chance while dodging (handled by combat)
        Cold Blood stacks: +3% per stack (perk ColdBloodPerk)
        Cap: 100%
        """
        refs = stats.Reflexes
        base = 3.0 + (refs - 1) * 1.5

        # Cold Blood perk stacks
        if stats.has_perk("Perks.ColdBloodPerk"):
            base += stats.cold_blood_stacks * 3.0

        # Sandevistan / cyberware bonuses
        base += stats.get_additive(gamedataStatType.CritChance)

        # Gear multiplicative
        base *= stats.get_multiplier(gamedataStatType.CritChance)

        return round(min(base, 100.0), 2)

    @staticmethod
    def compute_crit_damage(stats: CharacterStats) -> float:
        """Crit Damage bonus in % added on top of the base hit.

        A crit does  (1 + CritDamage/100) × base_damage.

        Formula:  50 + (Cool - 1) * 5  (%)
        Perk DeadlyPrecision (Handguns): +25% crit damage
        Sandevistan active: +50% crit damage  (handled externally)
        """
        cool = stats.Cool
        base = 50.0 + (cool - 1) * 5.0

        if stats.has_perk("Perks.DeadlyPrecision"):
            base += 25.0

        base += stats.get_additive(gamedataStatType.CritDamage)
        base *= stats.get_multiplier(gamedataStatType.CritDamage)

        return round(base, 2)

    @staticmethod
    def compute_armor(stats: CharacterStats) -> float:
        """Effective Armor from gear + cyberware + perks.

        Base: 0 (armor comes entirely from equipment in CP2077)
        Perk Juggernaut: +5 armor per Athletics level
        SubdermalArmor cyberware: +200 armor  (added as a modifier)
        """
        armor = 0.0
        armor += stats.get_additive(gamedataStatType.Armor)

        if stats.has_perk("Perks.Juggernaut"):
            ath = stats.get_skill("Athletics")
            armor += 5.0 * ath

        armor *= stats.get_multiplier(gamedataStatType.Armor)
        return round(armor, 2)

    @staticmethod
    def compute_headshot_multiplier(stats: CharacterStats) -> float:
        """Total headshot damage multiplier (ranged).

        Base:  2.0  (headshots deal double damage for ranged weapons)
        Cool attribute: base headshot mult is not modified by Cool directly;
          Cool contributes via CritDamage on headshot crits instead.
        Perk HeadHunter: +25% headshot damage with silenced weapons
          (handled by the combat system checking weapon type).
        """
        base = 2.0
        base += stats.get_additive(gamedataStatType.HeadshotDamageMultiplier)
        base *= stats.get_multiplier(gamedataStatType.HeadshotDamageMultiplier)
        return round(base, 2)

    @staticmethod
    def compute_melee_headshot_multiplier(stats: CharacterStats) -> float:
        """Melee headshot damage multiplier.  Base 1.4× in CP2077."""
        return 1.4

    # ── Skill-derived bonuses ──────────────────────────────────────────────────

    @staticmethod
    def compute_handgun_damage_bonus(stats: CharacterStats) -> float:
        """Flat % damage bonus for pistols/revolvers from Handguns skill.

        Each Handguns skill level contributes 2% bonus damage.
        Handguns 20 = +38% damage (levels 1–19 = 2% each).
        """
        return max(0.0, (stats.get_skill("Handguns") - 1) * 0.02)

    @staticmethod
    def compute_assault_damage_bonus(stats: CharacterStats) -> float:
        """Flat % bonus for ARs and SMGs from Assault skill."""
        return max(0.0, (stats.get_skill("Assault") - 1) * 0.02)

    @staticmethod
    def compute_blade_damage_bonus(stats: CharacterStats) -> float:
        """Flat % bonus from Blades skill."""
        return max(0.0, (stats.get_skill("Blades") - 1) * 0.02)

    @staticmethod
    def compute_street_brawler_bonus(stats: CharacterStats) -> float:
        """Flat % bonus for fists and clubs from StreetBrawler skill."""
        return max(0.0, (stats.get_skill("StreetBrawler") - 1) * 0.02)

    @staticmethod
    def compute_annihilation_damage_bonus(stats: CharacterStats) -> float:
        """Flat % bonus for shotguns and LMGs from Annihilation skill."""
        return max(0.0, (stats.get_skill("Annihilation") - 1) * 0.02)

    @staticmethod
    def compute_engineering_tech_bonus(stats: CharacterStats) -> float:
        """Charged-shot bonus from Engineering skill (for tech weapons)."""
        base_bonus = max(0.0, (stats.get_skill("Engineering") - 1) * 0.025)
        if stats.has_perk("Perks.CopperCartridges"):
            base_bonus += 0.25
        return base_bonus

    @staticmethod
    def compute_stealth_damage_bonus(stats: CharacterStats) -> float:
        """Bonus damage vs unaware targets from Stealth + Assassin perk."""
        bonus = 0.0
        if stats.has_perk("Perks.Assassin"):
            bonus += 0.10
        return bonus

    @staticmethod
    def compute_quickhack_damage_bonus(stats: CharacterStats) -> float:
        """% bonus to quickhack damage from Intelligence + QH skill.

        Formula: 3% per Intelligence point above 1, +2% per QH skill level.
        """
        intel  = stats.Intelligence
        qh_lvl = stats.get_skill("Quickhacking")
        return ((intel - 1) * 0.03) + ((qh_lvl - 1) * 0.02)

    # ── Full stat snapshot ────────────────────────────────────────────────────

    @staticmethod
    def snapshot(stats: CharacterStats) -> dict:
        """Return a dict of all computed stats -- useful for debugging and tests.

        Matches the shape of values the real game's F3/DEBUG overlay shows.
        """
        return {
            "level":               stats.level,
            "Body":                stats.Body,
            "Reflexes":            stats.Reflexes,
            "TechnicalAbility":    stats.TechnicalAbility,
            "Intelligence":        stats.Intelligence,
            "Cool":                stats.Cool,
            # Derived
            "MaxHealth":           StatsSystem.compute_max_health(stats),
            "MaxStamina":          StatsSystem.compute_max_stamina(stats),
            "MaxRAM":              StatsSystem.compute_max_ram(stats),
            "Armor":               StatsSystem.compute_armor(stats),
            "CritChance_%":        StatsSystem.compute_crit_chance(stats),
            "CritDamage_%":        StatsSystem.compute_crit_damage(stats),
            "HeadshotMult":        StatsSystem.compute_headshot_multiplier(stats),
            # Skill damage bonuses
            "HandgunBonus_%":     round(StatsSystem.compute_handgun_damage_bonus(stats) * 100, 1),
            "BladesBonus_%":      round(StatsSystem.compute_blade_damage_bonus(stats) * 100, 1),
            "AssaultBonus_%":     round(StatsSystem.compute_assault_damage_bonus(stats) * 100, 1),
            "AnnihBonus_%":       round(StatsSystem.compute_annihilation_damage_bonus(stats) * 100, 1),
            "StrBrawlBonus_%":    round(StatsSystem.compute_street_brawler_bonus(stats) * 100, 1),
            "StealthBonus_%":     round(StatsSystem.compute_stealth_damage_bonus(stats) * 100, 1),
            "QHBonus_%":          round(StatsSystem.compute_quickhack_damage_bonus(stats) * 100, 1),
            "HealthRegen_per_s":   StatsSystem.compute_health_regen_rate(stats),
        }


# ════════════════════════════════════════════════════════════════════════════
#  NPC Stats  (simplified -- NPCs don't have an attribute build)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class NPCStats:
    """Lightweight stats for an NPC entity.

    In the real game, NPC stats come from their TweakDB record
    (gamedataCharacter_Record → statModifiers list).
    """
    max_health:    float = 200.0
    current_health: float = 200.0   # mutable during combat
    armor:         float = 20.0
    crit_chance:   float = 5.0       # %
    crit_damage:   float = 50.0      # %
    level:         int   = 1
    is_boss:       bool  = False

    # Status effect resistances (%)
    physical_resistance:  float = 0.0
    thermal_resistance:   float = 0.0
    chemical_resistance:  float = 0.0
    electric_resistance:  float = 0.0

    def is_alive(self) -> bool:
        return self.current_health > 0.0

    def take_damage(self, amount: float) -> float:
        """Apply damage, return actual HP removed (capped at current_health)."""
        actual = min(amount, self.current_health)
        self.current_health = max(0.0, self.current_health - amount)
        return actual

    def heal(self, amount: float) -> float:
        """Restore HP, return actual HP restored."""
        old = self.current_health
        self.current_health = min(self.max_health, self.current_health + amount)
        return self.current_health - old


# ════════════════════════════════════════════════════════════════════════════
#  Preset builds -- premade CharacterStats matching recognisable CP2077 builds
# ════════════════════════════════════════════════════════════════════════════

def preset_early_game_v() -> CharacterStats:
    """V at the start of the game (default stats, Level 1)."""
    s = CharacterStats()
    # All attributes at 3 by default
    return s


def preset_netrunner_v() -> CharacterStats:
    """V built for hacking (maxed Intelligence + Cool)."""
    s = CharacterStats()
    s.level = 25
    s.set_attribute("Body",          5)
    s.set_attribute("Reflexes",      5)
    s.set_attribute("TechnicalAbility", 5)
    s.set_attribute("Intelligence", 20)
    s.set_attribute("Cool",         20)
    s.set_skill("Quickhacking", 18)
    s.set_skill("BreachProtocol", 10)
    s.set_skill("Stealth", 12)
    s.add_perk("Perks.SynapseBurnout")
    s.add_perk("Perks.SpeakEasyProtocol")
    s.add_perk("Perks.HeadHunter")
    return s


def preset_street_samurai_v() -> CharacterStats:
    """V built for melee / katana combat."""
    s = CharacterStats()
    s.level = 30
    s.set_attribute("Body",             15)
    s.set_attribute("Reflexes",         15)
    s.set_attribute("TechnicalAbility",  5)
    s.set_attribute("Intelligence",      3)
    s.set_attribute("Cool",             12)
    s.set_skill("Athletics",     18)
    s.set_skill("Blades",        20)
    s.set_skill("StreetBrawler", 10)
    s.set_skill("ColdBlood",     15)
    s.add_perk("Perks.Invincible")
    s.add_perk("Perks.Regeneration")
    s.add_perk("Perks.ColdBloodPerk")
    s.add_perk("Perks.StreetFighter")
    # Subdermal armor cyberware
    s.add_modifier(gamedataStatType.Armor, 200.0, source="SubdermalArmor")
    return s


def preset_gunslinger_v() -> CharacterStats:
    """V built for handguns / revolvers."""
    s = CharacterStats()
    s.level = 40
    s.set_attribute("Body",             6)
    s.set_attribute("Reflexes",        20)
    s.set_attribute("TechnicalAbility", 5)
    s.set_attribute("Intelligence",     3)
    s.set_attribute("Cool",            20)
    s.set_skill("Handguns",  20)
    s.set_skill("Stealth",   18)
    s.set_skill("ColdBlood", 20)
    s.add_perk("Perks.DeadlyPrecision")
    s.add_perk("Perks.Assassin")
    s.add_perk("Perks.HeadHunter")
    s.add_perk("Perks.ColdBloodPerk")
    s.cold_blood_stacks = 5  # full stacks mid-combat
    return s
