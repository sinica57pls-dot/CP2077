"""
TweakDB Simulation
==================

Mirrors the TweakDB system from:
  src/Red/TweakDB.hpp
  scripts/Base/Imports/  (record type imports)

TweakDB is Cyberpunk 2077's central data database.  Every item, NPC, weapon,
vehicle, perk, ability, and stat is a *record* in TweakDB, keyed by a
TweakDBID (FNV-1a 64-bit hash of the full record path string).

REDscript syntax:  t"Items.Preset_Power_Pistol_Epic"
C++ API:           TweakDB::GetRecord(TweakDBID id)
                   TweakDB::GetFlat(TweakDBID id) -> IRTTIType*
                   TweakDB::SetFlat(TweakDBID id, value)
                   TweakDB::CreateRecord(TweakDBID id, type)

This module provides:
  TweakDBID     -- FNV-1a hash wrapping a record/flat path
  gamedataRecord -- base record type (all CP2077 record types inherit this)
  Typed records  -- WeaponRecord, ArmorRecord, CyberwareRecord, PerkRecord, etc.
  TweakDB       -- singleton runtime database, pre-seeded with real game data
  TweakDBQuery  -- helper for querying nested record paths

Seeded data is drawn from:
  - WolvenKit TweakDB viewer (community-maintained dumps)
  - https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators-theory/
  - Community reverse-engineering at https://github.com/WolvenKit/WolvenKit
"""

from __future__ import annotations
import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


# ════════════════════════════════════════════════════════════════════════════
#  TweakDBID  (FNV-1a 64-bit hash)
# ════════════════════════════════════════════════════════════════════════════

_FNV1A_PRIME  = 0x100000001B3
_FNV1A_OFFSET = 0xCBF29CE484222325
_MASK64       = 0xFFFFFFFFFFFFFFFF


def _fnv1a_64(text: str) -> int:
    """FNV-1a 64-bit hash matching the CP2077 TweakDB hashing algorithm.

    Note: TweakDB paths are stored in lower-case in the game binary.  We
    reproduce that here so  t"Items.Foo"  and  t"items.foo"  resolve to the
    same ID, matching the real engine behaviour.
    """
    h = _FNV1A_OFFSET
    for ch in text.lower():
        h = ((h ^ ord(ch)) * _FNV1A_PRIME) & _MASK64
    return h


class TweakDBID:
    """Unique TweakDB record identifier.

    In REDscript: ``t"Items.Preset_Power_Pistol_Epic"``
    In C++:       ``TweakDBID("Items.Preset_Power_Pistol_Epic")``
    """

    __slots__ = ('_hash', '_path')

    def __init__(self, path: str = ""):
        self._path = path
        self._hash = _fnv1a_64(path) if path else 0

    @staticmethod
    def FromHash(h: int) -> 'TweakDBID':
        obj = object.__new__(TweakDBID)
        obj._hash = h
        obj._path = f"<hash:0x{h:016x}>"
        return obj

    # ─── API matching src/Red/TweakDB.hpp ──────────────────────────────

    def IsValid(self) -> bool:
        return self._hash != 0

    def GetHash(self) -> int:
        return self._hash

    # ─── Python housekeeping ─────────────────────────────────────────────

    def __eq__(self, other) -> bool:
        if isinstance(other, TweakDBID):
            return self._hash == other._hash
        if isinstance(other, str):
            return self._hash == _fnv1a_64(other)
        return NotImplemented

    def __hash__(self) -> int:
        # Fold to positive signed range Python expects
        return self._hash & 0x7FFFFFFFFFFFFFFF

    def __repr__(self) -> str:
        return f't"{self._path}"'

    def __str__(self) -> str:
        return self._path


# ════════════════════════════════════════════════════════════════════════════
#  Record types  (gamedataXxxItem_Record in REDscript)
# ════════════════════════════════════════════════════════════════════════════

class gamedataRecord:
    """Base for all TweakDB records.  Holds a dict of named flat values."""

    _record_type: str = "gamedataRecord"

    def __init__(self, record_id: Union[str, TweakDBID], **flats):
        if isinstance(record_id, str):
            record_id = TweakDBID(record_id)
        self.id: TweakDBID = record_id
        self._flats: Dict[str, Any] = dict(flats)

    # REDscript / C++ API
    def GetID(self) -> TweakDBID:
        return self.id

    def GetRecordType(self) -> str:
        return self._record_type

    def GetFlat(self, flat_name: str, default=None) -> Any:
        return self._flats.get(flat_name, default)

    def SetFlat(self, flat_name: str, value: Any) -> None:
        self._flats[flat_name] = value

    def __repr__(self) -> str:
        return f"{self._record_type}({self.id!r})"


# ── Damage types used across weapon / cyberware records ─────────────────────

class gamedataDamageType(enum.Enum):
    """CP2077 damage types (gamedataDamageType in TweakDB)."""
    Invalid   = "Invalid"
    Physical  = "Physical"
    Thermal   = "Thermal"
    Chemical  = "Chemical"
    Electric  = "Electric"
    EMP       = "EMP"


# ── Weapon quality tiers ──────────────────────────────────────────────────────

class gamedataQuality(enum.Enum):
    """Item quality tiers."""
    Common     = "Common"
    Uncommon   = "Uncommon"
    Rare       = "Rare"
    Epic       = "Epic"
    Legendary  = "Legendary"
    Iconic     = "Iconic"      # Special sub-tier of Legendary


# ── Weapon category ──────────────────────────────────────────────────────────

class gamedataWeaponEvolution(enum.Enum):
    """Weapon sub-category (attack style)."""
    Power    = "Power"    # Bullets bounce off walls
    Tech     = "Tech"     # Charged shots, penetrate walls
    Smart    = "Smart"    # Homing bullets via smart chip


class gamedataItemType(enum.Enum):
    """Broad item category."""
    Wea_Pistol         = "Wea_Pistol"
    Wea_Revolver       = "Wea_Revolver"
    Wea_AssaultRifle   = "Wea_AssaultRifle"
    Wea_SniperRifle    = "Wea_SniperRifle"
    Wea_Shotgun        = "Wea_Shotgun"
    Wea_ShotgunDual    = "Wea_ShotgunDual"
    Wea_HeavyMachineGun= "Wea_HeavyMachineGun"
    Wea_LightMachineGun= "Wea_LightMachineGun"
    Wea_SubmachineGun  = "Wea_SubmachineGun"
    Wea_Melee          = "Wea_Melee"
    Wea_Knife          = "Wea_Knife"
    Wea_OneHandedClub  = "Wea_OneHandedClub"
    Wea_TwoHandedClub  = "Wea_TwoHandedClub"
    Cyb_Launcher       = "Cyb_Launcher"
    Cyb_MantisBlades   = "Cyb_MantisBlades"
    Cyb_NanoWire       = "Cyb_NanoWire"
    Cyb_StrongArms     = "Cyb_StrongArms"
    Itm_Armor          = "Itm_Armor"
    Itm_Cyberware      = "Itm_Cyberware"
    Itm_Consumable     = "Itm_Consumable"
    Itm_CraftingMaterial = "Itm_CraftingMaterial"
    Itm_Grenade        = "Itm_Grenade"
    Itm_Junk           = "Itm_Junk"
    Itm_QuestItem      = "Itm_QuestItem"
    Moneybag_Eddies    = "Moneybag_Eddies"


# ── Weapon record ────────────────────────────────────────────────────────────

class WeaponRecord(gamedataRecord):
    """gamedataWeaponItem_Record  -- weapon stats from TweakDB.

    Key flats (matching the real game's flat names):
      damageType         gamedataDamageType
      itemType           gamedataItemType
      evolution          gamedataWeaponEvolution
      quality            gamedataQuality
      DPS                Float   -- damage per second (base, no upgrades)
      damagePerHit       Float   -- damage per bullet/swing
      attacksPerSecond   Float   -- fire/swing rate
      magazineSize       Int     -- rounds per magazine
      reloadTime         Float   -- seconds
      range              Float   -- effective range in metres
      isAutomatic        Bool
      iconic             Bool    -- unique/iconic weapon flag
      iconicDescription  String
    """

    _record_type = "gamedataWeaponItem_Record"

    def __init__(self, path: str, damage_per_hit: float,
                 attacks_per_sec: float,
                 item_type: gamedataItemType = gamedataItemType.Wea_Pistol,
                 damage_type: gamedataDamageType = gamedataDamageType.Physical,
                 evolution: gamedataWeaponEvolution = gamedataWeaponEvolution.Power,
                 quality: gamedataQuality = gamedataQuality.Common,
                 magazine: int = 12,
                 reload_time: float = 1.6,
                 effective_range: float = 20.0,
                 is_automatic: bool = False,
                 iconic: bool = False,
                 iconic_desc: str = "",
                 **extra):
        dps = round(damage_per_hit * attacks_per_sec, 2)
        super().__init__(path,
            damageType=damage_type,
            itemType=item_type,
            evolution=evolution,
            quality=quality,
            DPS=dps,
            damagePerHit=damage_per_hit,
            attacksPerSecond=attacks_per_sec,
            magazineSize=magazine,
            reloadTime=reload_time,
            range=effective_range,
            isAutomatic=is_automatic,
            iconic=iconic,
            iconicDescription=iconic_desc,
            **extra)

    @property
    def DPS(self) -> float:
        return self._flats['DPS']

    @property
    def damagePerHit(self) -> float:
        return self._flats['damagePerHit']

    @property
    def attacksPerSecond(self) -> float:
        return self._flats['attacksPerSecond']


# ── Armor record ─────────────────────────────────────────────────────────────

class ArmorRecord(gamedataRecord):
    """gamedataClothingItem_Record  -- clothing / armor slot item."""

    _record_type = "gamedataClothingItem_Record"

    def __init__(self, path: str, armor_value: float,
                 slot: str, quality: gamedataQuality = gamedataQuality.Common,
                 **extra):
        super().__init__(path,
            armorValue=armor_value,
            slot=slot,
            quality=quality,
            itemType=gamedataItemType.Itm_Armor,
            **extra)


# ── Cyberware record ─────────────────────────────────────────────────────────

class gamedataCyberwareType(enum.Enum):
    """Cyberware slot categories."""
    SystemReplacementCyberware = "SystemReplacementCyberware"  # Operating System
    NeuralProcessorCyberware   = "NeuralProcessorCyberware"    # Neural Processor
    EyesCyberware              = "EyesCyberware"               # Kiroshi optics
    HandsCyberware             = "HandsCyberware"              # Palm Shielding, etc.
    ArmsCyberware              = "ArmsCyberware"               # Mantis, Gorilla, etc.
    LegsCyberware              = "LegsCyberware"               # Reinforced Tendons, etc.
    SkeletonCyberware          = "SkeletonCyberware"           # Titanium Bones, etc.
    IntegumentaryCyberware     = "IntegumentaryCyberware"      # Subdermal Armor, etc.
    CirculatorySystemCyberware = "CirculatorySystemCyberware"  # Blood Pump, etc.
    NervousSystemCyberware     = "NervousSystemCyberware"      # Kerenzikov, etc.
    ImmuneSystemCyberware      = "ImmuneSystemCyberware"       # Metabolic Editor, etc.


class CyberwareRecord(gamedataRecord):
    """gamedataCyberwareItem_Record -- cyberware implant."""

    _record_type = "gamedataCyberwareItem_Record"

    def __init__(self, path: str,
                 cyberware_type: gamedataCyberwareType,
                 quality: gamedataQuality = gamedataQuality.Common,
                 slots: int = 0,
                 **extra):
        super().__init__(path,
            cyberwareType=cyberware_type,
            quality=quality,
            itemType=gamedataItemType.Itm_Cyberware,
            slotCount=slots,
            **extra)


# ── Perk record ──────────────────────────────────────────────────────────────

class gamedataStatPoolType(enum.Enum):
    """Stat pools (gamedataStatPoolType)."""
    Health        = "Health"
    Stamina       = "Stamina"
    RAM           = "RAM"
    Oxygen        = "Oxygen"
    InspiredStamina = "InspiredStamina"

class gamedataStatType(enum.Enum):
    """All stat types from TweakDB (gamedataStatType)."""
    # ── Primary Attributes ───────────────────────────────────────────────
    Strength            = "Strength"          # Body
    Reflexes            = "Reflexes"
    TechnicalAbility    = "TechnicalAbility"
    Intelligence        = "Intelligence"
    Cool                = "Cool"
    # ── Skills ───────────────────────────────────────────────────────────
    Athletics           = "Athletics"
    Annihilation        = "Annihilation"
    StreetBrawler       = "StreetBrawler"
    Assault             = "Assault"
    Handguns            = "Handguns"
    Blades              = "Blades"
    Crafting            = "Crafting"
    Engineering         = "Engineering"
    BreachProtocol      = "BreachProtocol"
    Quickhacking        = "Quickhacking"
    Stealth             = "Stealth"
    ColdBlood           = "ColdBlood"
    # ── Derived combat stats ─────────────────────────────────────────────
    Health              = "Health"
    MaxHealth           = "MaxHealth"
    Stamina             = "Stamina"
    MaxStamina          = "MaxStamina"
    Armor               = "Armor"
    CritChance          = "CritChance"          # base % (0-100)
    CritDamage          = "CritDamage"          # bonus % on top of 100%
    RAM                 = "RAM"
    MaxRAM              = "MaxRAM"
    # ── Damage bonuses ───────────────────────────────────────────────────
    AttackPower         = "AttackPower"         # flat additive to all damage
    BulletDamageMultiplier = "BulletDamageMultiplier"
    PhysicalDamageBonus = "PhysicalDamageBonus"
    ThermalDamageBonus  = "ThermalDamageBonus"
    ChemicalDamageBonus = "ChemicalDamageBonus"
    ElectricDamageBonus = "ElectricDamageBonus"
    MeleeDamageBonus    = "MeleeDamageBonus"
    RangedDamageBonus   = "RangedDamageBonus"
    HeadshotDamageMultiplier = "HeadshotDamageMultiplier"  # extra % on headshots
    # ── Resistances ──────────────────────────────────────────────────────
    PhysicalResistance  = "PhysicalResistance"  # %
    ThermalResistance   = "ThermalResistance"
    ChemicalResistance  = "ChemicalResistance"
    ElectricResistance  = "ElectricResistance"
    # ── Misc ─────────────────────────────────────────────────────────────
    HackingSpeed        = "HackingSpeed"
    StealthMovementSpeedMultiplier = "StealthMovementSpeedMultiplier"
    MemoryReplenishmentRate = "MemoryReplenishmentRate"
    StreetCredPoints    = "StreetCredPoints"


class PerkRecord(gamedataRecord):
    """gamedataPerk_Record -- a perk definition in TweakDB."""

    _record_type = "gamedataPerk_Record"

    def __init__(self, path: str, attribute: str, skill: str,
                 tier: int = 1, max_level: int = 1,
                 description: str = "", **flats):
        super().__init__(path,
            attribute=attribute,
            skill=skill,
            tier=tier,
            maxLevel=max_level,
            description=description,
            **flats)


# ── Consumable record ────────────────────────────────────────────────────────

class ConsumableRecord(gamedataRecord):
    """gamedataConsumableItem_Record -- food, drinks, MaxDocs, etc."""

    _record_type = "gamedataConsumableItem_Record"

    def __init__(self, path: str, health_restore: float = 0.0,
                 stamina_restore: float = 0.0, duration: float = 0.0,
                 quality: gamedataQuality = gamedataQuality.Common, **extra):
        super().__init__(path,
            healthRestore=health_restore,
            staminaRestore=stamina_restore,
            duration=duration,
            quality=quality,
            itemType=gamedataItemType.Itm_Consumable,
            **extra)


# ══════════════════════════════════════════════════════════════════════════════
#  TweakDB singleton with seeded CP2077 data
# ══════════════════════════════════════════════════════════════════════════════

class TweakDB:
    """Runtime TweakDB -- mirrors the in-game TweakDB singleton.

    Pre-seeded with a representative subset of real CP2077 records:
      - Weapons (powers, tech, smart, melee)
      - Armor pieces
      - Cyberware (OS, arms, legs, nervous system)
      - Perks (from all 5 attribute trees)
      - Consumables (MaxDoc, Bounce Back, alcohol)

    Override system:
      - Override(id, flat, value) mirrors TweakDB.SetFlat runtime overrides
        used by mods (TweakXL, Codeware TweakDB API).

    Ref: src/Red/TweakDB.hpp  GetRecord / GetFlat / SetFlat
    """

    _instance: Optional['TweakDB'] = None

    def __init__(self):
        self._records:      Dict[TweakDBID, gamedataRecord]     = {}
        self._overrides:    Dict[TweakDBID, Dict[str, Any]]     = {}
        self._update_calls: set                                  = set()
        self._seed()
        self._seed_amm_records()

    @classmethod
    def Get(cls) -> 'TweakDB':
        """Return the process-global TweakDB instance (mirrors the real engine)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def Reset(cls) -> None:
        """Reset database to seeded state (use in test tearDown)."""
        cls._instance = None

    # ── Record access ────────────────────────────────────────────────────────

    def GetFlat(self, flat_id: Union[str, TweakDBID]) -> Any:
        """Get a flat value by its full flat path (e.g. "Items.Unity.DPS")."""
        if isinstance(flat_id, str):
            # Split "Record.Path.FlatName" into record path + flat name
            parts = flat_id.rsplit('.', 1)
            if len(parts) == 2:
                record_path, flat_name = parts
                rec = self.GetRecord(record_path)
                if rec:
                    return rec.GetFlat(flat_name)
        return None

    def SetFlat(self, flat_id: Union[str, TweakDBID], value: Any) -> bool:
        """Runtime override of a flat value (mirrors TweakDB.SetFlat).
        Used by mods via TweakXL or Codeware TweakDB API.
        Returns True on success."""
        if isinstance(flat_id, str):
            parts = flat_id.rsplit('.', 1)
            if len(parts) == 2:
                record_path, flat_name = parts
                rid = TweakDBID(record_path)
                if rid in self._records:
                    self._overrides.setdefault(rid, {})[flat_name] = value
                    return True
        return False

    def CreateRecord(self, record_id: Union[str, TweakDBID],
                     base_record: gamedataRecord) -> bool:
        """Dynamically create a new record (used by TweakXL .yaml mods)."""
        if isinstance(record_id, str):
            record_id = TweakDBID(record_id)
        if record_id in self._records:
            return False
        self._records[record_id] = base_record
        return True

    def CloneRecord(self, new_id: Union[str, TweakDBID],
                    source_id: Union[str, TweakDBID]) -> bool:
        """
        Clone a record to a new ID -- key AMM operation.

        AMM uses this in onTweak to create AMM_Character.* from vanilla records:
          TweakDB:CloneRecord(AMM_Character.Judy, Character.Judy_Judy)

        The clone carries all flats from the source at clone time.
        Subsequent SetFlat / SetFlatNoUpdate calls on either record do NOT
        affect the other (clone isolation).
        """
        if isinstance(new_id, str):
            new_id = TweakDBID(new_id)
        if isinstance(source_id, str):
            source_id = TweakDBID(source_id)

        source = self._records.get(source_id)
        if source is None:
            return False
        if new_id in self._records:
            return False   # already exists

        # Deep-copy the flats dict so clone is independent
        clone = object.__new__(type(source))
        clone.__dict__.update(source.__dict__)
        clone._flats = dict(source._flats)
        clone.id     = new_id
        self._records[new_id] = clone
        return True

    def SetFlatNoUpdate(self, flat_id: Union[str, TweakDBID],
                        value: Any) -> bool:
        """
        Set a flat value without propagating the change immediately.
        Must be followed by Update(record_path) to apply.

        AMM uses this for model-swapping (Swap module):
          TweakDB:SetFlatNoUpdate(TweakDBID.new(path, ".entityTemplatePath"), newPath)
          TweakDB:Update(entityPath)
        """
        # In our simulation, no-update and immediate update behave the same
        # because we have no real propagation pipeline.  Store in a separate
        # pending dict keyed off entity path.
        return self.SetFlat(flat_id, value)   # delegates to SetFlat

    def Update(self, record_path: Union[str, TweakDBID]) -> bool:
        """
        Force propagation of all pending flat changes for a record.

        In the real engine this triggers component re-loading.  In our
        simulation it's a no-op (SetFlat changes are already live) but we
        track calls so tests can assert AMM called Update correctly.
        """
        if isinstance(record_path, str):
            record_path = TweakDBID(record_path)
        self._update_calls.add(record_path)
        return record_path in self._records

    def WasUpdated(self, record_path: Union[str, TweakDBID]) -> bool:
        """Test helper: was Update() called for this record path?"""
        if isinstance(record_path, str):
            record_path = TweakDBID(record_path)
        return record_path in self._update_calls

    def GetRecord(self, record_id: Union[str, TweakDBID]) -> Optional[gamedataRecord]:
        """Returns the record for this ID, applying any active overrides."""
        if isinstance(record_id, str):
            record_id = TweakDBID(record_id)
        rec = self._records.get(record_id)
        if rec is None:
            return None
        # Apply overrides
        overrides = self._overrides.get(record_id, {})
        if overrides:
            # Return a shallow copy with overrides applied
            copy = object.__new__(type(rec))
            copy.__dict__.update(rec.__dict__)
            copy._flats = dict(rec._flats)
            copy._flats.update(overrides)
            return copy
        return rec

    def _add(self, record: gamedataRecord) -> None:
        self._records[record.id] = record

    # ── Seeded data ───────────────────────────────────────────────────────────

    def _seed(self) -> None:
        """Populate the database with representative real CP2077 records.

        All values come from community-documented dumps of the real TweakDB.
        DPS, damage-per-hit, and attacks-per-second are averaged across the
        base (unupgraded) weapon stats for each archetype.
        """

        # ── Weapons: Pistols ─────────────────────────────────────────────────
        # Unity (HJKE-11 Yukimura) -- Militech power pistol, V's default
        self._add(WeaponRecord(
            "Items.Preset_Yukimura_Default",
            damage_per_hit=45.5, attacks_per_sec=3.33,
            item_type=gamedataItemType.Wea_Pistol,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Common,
            magazine=14, reload_time=1.56, effective_range=21.0,
            is_automatic=False,
        ))
        # Budget variant  (street-quality)
        self._add(WeaponRecord(
            "Items.Preset_Budget_Pistol",
            damage_per_hit=22.0, attacks_per_sec=2.5,
            item_type=gamedataItemType.Wea_Pistol,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Common,
            magazine=12, reload_time=1.7, effective_range=15.0,
        ))
        # Malorian Arms 3516 -- Johnny Silverhand's iconic revolver
        self._add(WeaponRecord(
            "Items.Preset_Revolver_Pirate",
            damage_per_hit=148.0, attacks_per_sec=3.13,
            item_type=gamedataItemType.Wea_Revolver,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Legendary,
            magazine=6, reload_time=2.1, effective_range=35.0,
            is_automatic=False, iconic=True,
            iconic_desc="Johnny Silverhand's iconic weapon.  "
                        "The gun that killed Alt Cunningham.",
        ))
        # Overture (base revolver)
        self._add(WeaponRecord(
            "Items.Preset_Revolver_Default",
            damage_per_hit=98.0, attacks_per_sec=1.51,
            item_type=gamedataItemType.Wea_Revolver,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Common,
            magazine=6, reload_time=2.1, effective_range=30.0,
        ))
        # Apparition -- Iconic power pistol (Royce's gun)
        self._add(WeaponRecord(
            "Items.Preset_Lexington_Royce",
            damage_per_hit=52.0, attacks_per_sec=4.0,
            item_type=gamedataItemType.Wea_Pistol,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Legendary,
            magazine=15, reload_time=1.5, effective_range=22.0,
            iconic=True,
            iconic_desc="An Apparition that feeds on greed.",
        ))

        # ── Weapons: SMGs ────────────────────────────────────────────────────
        # Sidewinder -- base SMG
        self._add(WeaponRecord(
            "Items.Preset_SMG_Default",
            damage_per_hit=19.5, attacks_per_sec=10.0,
            item_type=gamedataItemType.Wea_SubmachineGun,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Common,
            magazine=30, reload_time=2.0, effective_range=18.0,
            is_automatic=True,
        ))
        # Buzzsaw -- auto-fire SMG
        self._add(WeaponRecord(
            "Items.Preset_SMG_3rd",
            damage_per_hit=17.0, attacks_per_sec=12.0,
            item_type=gamedataItemType.Wea_SubmachineGun,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Rare,
            magazine=40, reload_time=1.9, effective_range=16.0,
            is_automatic=True,
        ))

        # ── Weapons: Assault Rifles ───────────────────────────────────────────
        # Constitutional Arms M-179e Achilles  -- tech assault rifle
        self._add(WeaponRecord(
            "Items.Preset_Assault_Rifle_Tech",
            damage_per_hit=38.0, attacks_per_sec=6.67,
            item_type=gamedataItemType.Wea_AssaultRifle,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Tech,
            quality=gamedataQuality.Rare,
            magazine=25, reload_time=2.1, effective_range=45.0,
            is_automatic=True,
        ))
        # Divided We Stand -- smart assault rifle
        self._add(WeaponRecord(
            "Items.Preset_Assault_Rifle_Smart",
            damage_per_hit=30.0, attacks_per_sec=8.0,
            item_type=gamedataItemType.Wea_AssaultRifle,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Smart,
            quality=gamedataQuality.Epic,
            magazine=30, reload_time=2.2, effective_range=50.0,
            is_automatic=True,
            # Smart: bullets track targets
            guidanceTime=1.2,
        ))

        # ── Weapons: Shotguns ────────────────────────────────────────────────
        # Carnage -- pump-action shotgun
        self._add(WeaponRecord(
            "Items.Preset_Shotgun_Default",
            damage_per_hit=250.0, attacks_per_sec=0.85,
            item_type=gamedataItemType.Wea_Shotgun,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Common,
            magazine=6, reload_time=3.0, effective_range=12.0,
            pellets=8,   # 8 pellets per shot
        ))
        # Sovereign -- double-barrel
        self._add(WeaponRecord(
            "Items.Preset_ShotgunDual_Default",
            damage_per_hit=420.0, attacks_per_sec=1.2,
            item_type=gamedataItemType.Wea_ShotgunDual,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Rare,
            magazine=2, reload_time=2.8, effective_range=10.0,
            pellets=12,
        ))

        # ── Weapons: Sniper Rifles ───────────────────────────────────────────
        # Widowmaker -- power sniper
        self._add(WeaponRecord(
            "Items.Preset_SniperRifle_Default",
            damage_per_hit=445.0, attacks_per_sec=0.5,
            item_type=gamedataItemType.Wea_SniperRifle,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Rare,
            magazine=4, reload_time=3.5, effective_range=100.0,
        ))
        # Grad -- tech sniper (charged shot)
        self._add(WeaponRecord(
            "Items.Preset_SniperRifle_Tech",
            damage_per_hit=700.0, attacks_per_sec=0.4,
            item_type=gamedataItemType.Wea_SniperRifle,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Tech,
            quality=gamedataQuality.Epic,
            magazine=1, reload_time=4.0, effective_range=150.0,
            chargeMultiplier=1.5,   # charged shot multiplier
        ))

        # ── Weapons: Melee ───────────────────────────────────────────────────
        # Baseball bat
        self._add(WeaponRecord(
            "Items.Preset_OneHandedClub_Baseball",
            damage_per_hit=55.0, attacks_per_sec=2.5,
            item_type=gamedataItemType.Wea_OneHandedClub,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Common,
            effective_range=2.0,
        ))
        # Katana (power)
        self._add(WeaponRecord(
            "Items.Preset_Katana_Default",
            damage_per_hit=78.0, attacks_per_sec=2.8,
            item_type=gamedataItemType.Wea_Melee,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Uncommon,
            effective_range=2.2,
        ))
        # Satori -- Iconic katana (from Arasaka tower)
        self._add(WeaponRecord(
            "Items.Preset_Katana_Ninja",
            damage_per_hit=120.0, attacks_per_sec=3.0,
            item_type=gamedataItemType.Wea_Melee,
            damage_type=gamedataDamageType.Physical,
            evolution=gamedataWeaponEvolution.Power,
            quality=gamedataQuality.Iconic,
            effective_range=2.3, iconic=True,
            iconic_desc="Satori.  Deals bonus damage when health is below 50%.",
            lowHpDamageBonus=0.5,
        ))

        # ── Armor ────────────────────────────────────────────────────────────
        self._add(ArmorRecord("Items.Preset_LightLeather_01",    armor_value=20.0, slot="OuterChest", quality=gamedataQuality.Common))
        self._add(ArmorRecord("Items.Preset_MediumNomad_01",     armor_value=60.0, slot="OuterChest", quality=gamedataQuality.Rare))
        self._add(ArmorRecord("Items.Preset_HeavyArasaka_01",    armor_value=130.0, slot="OuterChest", quality=gamedataQuality.Epic))
        self._add(ArmorRecord("Items.Preset_Neuroblocker_Helmet", armor_value=35.0, slot="Head",      quality=gamedataQuality.Uncommon))
        self._add(ArmorRecord("Items.Preset_Corpo_Pants_01",     armor_value=25.0, slot="Legs",       quality=gamedataQuality.Common))
        self._add(ArmorRecord("Items.Preset_SteelVorsa_Boots",   armor_value=15.0, slot="Feet",       quality=gamedataQuality.Common))

        # ── Cyberware: Operating Systems ─────────────────────────────────────
        # Sandevistan Mk.5  (Sandy -- time dilation OS)
        self._add(CyberwareRecord(
            "Items.OperatingSystemModule_Sandevistan_Legendary",
            cyberware_type=gamedataCyberwareType.SystemReplacementCyberware,
            quality=gamedataQuality.Legendary,
            slots=4,
            timeDilationFactor=0.25,   # slows time to 25% for V
            duration=8.0,              # active for 8 seconds
            cooldown=30.0,             # 30 second cooldown
            # Bonus stats while active
            critChanceBonus=15.0,
            critDamageBonus=50.0,
        ))
        # Berserk Mk.5  (melee OS)
        self._add(CyberwareRecord(
            "Items.OperatingSystemModule_Berserk_Legendary",
            cyberware_type=gamedataCyberwareType.SystemReplacementCyberware,
            quality=gamedataQuality.Legendary,
            slots=4,
            duration=10.0,
            cooldown=30.0,
            meleeDamageBonus=20.0,     # +20% melee damage
            armorBonus=10.0,           # +10% armor while active
            maxHealthBonus=10.0,       # +10% HP while active
        ))
        # Netrunner Tier-4 Cyberdeck
        self._add(CyberwareRecord(
            "Items.CyberdeckTier4",
            cyberware_type=gamedataCyberwareType.SystemReplacementCyberware,
            quality=gamedataQuality.Epic,
            slots=8,                   # RAM slots for quickhacks
            ramCapacity=8,
            uploadSpeedBonus=15.0,     # +15% upload speed
        ))

        # ── Cyberware: Arms ──────────────────────────────────────────────────
        # Mantis Blades (unfolding blades)
        self._add(CyberwareRecord(
            "Items.MantisBlades",
            cyberware_type=gamedataCyberwareType.ArmsCyberware,
            quality=gamedataQuality.Rare,
            slots=0,
            damagePerHit=80.0,
            attacksPerSecond=3.0,
            damageType=gamedataDamageType.Physical,
            armorPenetration=0.45,     # ignores 45% of enemy armor
            leapAttack=True,
        ))
        # Gorilla Arms
        self._add(CyberwareRecord(
            "Items.StrongArms",
            cyberware_type=gamedataCyberwareType.ArmsCyberware,
            quality=gamedataQuality.Common,
            slots=0,
            meleeDamageBonus=15.0,     # +15% melee damage
            bodyCheckBonus=True,       # allows hard Body attribute doors
            chargeAttack=True,
        ))
        # Monowire
        self._add(CyberwareRecord(
            "Items.NanoWire",
            cyberware_type=gamedataCyberwareType.ArmsCyberware,
            quality=gamedataQuality.Uncommon,
            slots=0,
            damagePerHit=60.0,
            attacksPerSecond=2.0,
            damageType=gamedataDamageType.Electric,
            hackChance=0.3,            # 30% chance to hack target on hit
        ))
        # Projectile Launch System
        self._add(CyberwareRecord(
            "Items.ProjectileLaunchSystem",
            cyberware_type=gamedataCyberwareType.ArmsCyberware,
            quality=gamedataQuality.Rare,
            slots=0,
            damagePerShot=300.0,
            ammoCapacity=3,
            reloadTime=3.0,
            damageType=gamedataDamageType.Physical,
        ))

        # ── Cyberware: Nervous System ────────────────────────────────────────
        # Kerenzikov  (dodge bullet-time)
        self._add(CyberwareRecord(
            "Items.NervousSystemCyberware_Kerenzikov",
            cyberware_type=gamedataCyberwareType.NervousSystemCyberware,
            quality=gamedataQuality.Rare,
            slots=0,
            timeDilationFactor=0.5,   # 50% time during dodge
            duration=0.5,
            cooldown=3.0,
        ))

        # ── Cyberware: Integumentary (skin) ──────────────────────────────────
        # Subdermal Armor
        self._add(CyberwareRecord(
            "Items.IntegumentarySystemCyberware_SubdermalArmor",
            cyberware_type=gamedataCyberwareType.IntegumentaryCyberware,
            quality=gamedataQuality.Uncommon,
            slots=0,
            armorBonus=200.0,         # flat armor
        ))

        # ── Cyberware: Circulatory system ────────────────────────────────────
        # Blood Pump (instant heal)
        self._add(CyberwareRecord(
            "Items.BloodPump",
            cyberware_type=gamedataCyberwareType.CirculatorySystemCyberware,
            quality=gamedataQuality.Rare,
            slots=0,
            healPercent=25.0,         # restore 25% HP
            cooldown=30.0,
        ))

        # ── Cyberware: Skeleton ──────────────────────────────────────────────
        # Titanium Bones
        self._add(CyberwareRecord(
            "Items.SkeletonCyberware_TitaniumBones",
            cyberware_type=gamedataCyberwareType.SkeletonCyberware,
            quality=gamedataQuality.Common,
            slots=0,
            carryWeightBonus=60.0,
            meleeDamageBonus=5.0,
        ))

        # ── Perks: Body tree ─────────────────────────────────────────────────
        self._add(PerkRecord("Perks.Multitasker",
            attribute="Strength", skill="Athletics", tier=1,
            description="Allows shooting while sprinting, sliding, or vaulting."))
        self._add(PerkRecord("Perks.Transporter",
            attribute="Strength", skill="Athletics", tier=1,
            description="Allows sprinting while carrying a body and shoot while sliding.",
            maxHealthBonus=0.0))
        self._add(PerkRecord("Perks.Invincible",
            attribute="Strength", skill="Athletics", tier=4,
            description="+25% max Health.",
            bonusStatType=gamedataStatType.MaxHealth, bonusValue=0.25))
        self._add(PerkRecord("Perks.PainIsJustAFeeling",
            attribute="Strength", skill="Athletics", tier=5,
            description="+50% health regeneration rate.",
            healthRegenMultiplier=1.50))
        self._add(PerkRecord("Perks.Regeneration",
            attribute="Strength", skill="Athletics", tier=2,
            description="Regenerate health during combat (10 HP/s after 5 seconds)."))

        # Body/Annihilation
        self._add(PerkRecord("Perks.ShotgunSurgeon",
            attribute="Strength", skill="Annihilation", tier=3,
            description="Shotgun and LMG attacks ignore 25% of target armor.",
            armorPenetration=0.25))
        self._add(PerkRecord("Perks.CloseAndPersonal",
            attribute="Strength", skill="Annihilation", tier=1,
            description="+20% shotgun damage against enemies within 4 m.",
            shortRangeDamageBonus=0.20, shortRangeThreshold=4.0))

        # Body/StreetBrawler
        self._add(PerkRecord("Perks.Juggernaut",
            attribute="Strength", skill="StreetBrawler", tier=1,
            description="+5 Armor per Athletics level.",
            armorPerAthleticsLevel=5.0))

        # ── Perks: Reflex tree ───────────────────────────────────────────────
        self._add(PerkRecord("Perks.DeadlyPrecision",
            attribute="Reflexes", skill="Handguns", tier=3,
            description="+25% Crit Damage with pistols and revolvers.",
            critDamageBonus=0.25))
        self._add(PerkRecord("Perks.SixthSense",
            attribute="Reflexes", skill="Handguns", tier=2,
            description="Revealed enemies take +10% damage from your weapons."))
        self._add(PerkRecord("Perks.TightGrip",
            attribute="Reflexes", skill="Assault", tier=1,
            description="Reduces weapon spread when shooting from the hip by 15%."))
        self._add(PerkRecord("Perks.StreetFighter",
            attribute="Reflexes", skill="Blades", tier=2,
            description="+25% Crit Chance and Crit Damage while dodging.",
            critChanceBonus=0.25, critDamageBonus=0.25))

        # ── Perks: Tech tree ─────────────────────────────────────────────────
        self._add(PerkRecord("Perks.CopperCartridges",
            attribute="TechnicalAbility", skill="Engineering", tier=1,
            description="Tech weapon charged shots deal +25% damage.",
            techChargedDamageBonus=0.25))
        self._add(PerkRecord("Perks.PrimitiveNerveSurgery",
            attribute="TechnicalAbility", skill="Crafting", tier=3,
            description="Crafted items have +5% chance of being upgraded."))

        # ── Perks: Intelligence tree ─────────────────────────────────────────
        self._add(PerkRecord("Perks.SynapseBurnout",
            attribute="Intelligence", skill="Quickhacking", tier=3,
            description="Cybersystem quickhacks deal 10% more damage per RAM point spent."))
        self._add(PerkRecord("Perks.SpeakEasyProtocol",
            attribute="Intelligence", skill="BreachProtocol", tier=2,
            description="Daemons upload 20% faster."))

        # ── Perks: Cool tree ─────────────────────────────────────────────────
        self._add(PerkRecord("Perks.Assassin",
            attribute="Cool", skill="Stealth", tier=1,
            description="+10% damage to unaware enemies.",
            unwareDamageBonus=0.10))
        self._add(PerkRecord("Perks.HeadHunter",
            attribute="Cool", skill="Stealth", tier=2,
            description="Critical hits and headshots with silenced weapons deal "
                        "+25% more damage.",
            silencedCritDamageBonus=0.25))
        self._add(PerkRecord("Perks.MarbleGhost",
            attribute="Cool", skill="Stealth", tier=3,
            description="Sliding no longer breaks stealth."))
        self._add(PerkRecord("Perks.ColdBloodPerk",
            attribute="Cool", skill="ColdBlood", tier=1,
            description="On kill: gain Cold Blood stack (+3% movement speed, "
                        "+3% crit change per stack, max 5 stacks, lasts 10s).",
            maxStacks=5, stackDuration=10.0,
            speedBonusPerStack=0.03, critBonusPerStack=0.03))

        # ── Consumables ──────────────────────────────────────────────────────
        # MaxDoc Mk.1  -- common healing item
        self._add(ConsumableRecord(
            "Items.MaxDOC",
            health_restore=15.0,   # restores 15 HP immediately
            stamina_restore=0.0,
            duration=0.0,
            quality=gamedataQuality.Common,
        ))
        # MaxDoc Mk.3  -- uncommon
        self._add(ConsumableRecord(
            "Items.MaxDOC_3",
            health_restore=40.0,
            duration=0.0,
            quality=gamedataQuality.Uncommon,
        ))
        # Bounce Back Mk.2  -- health regen stim
        self._add(ConsumableRecord(
            "Items.BounceBack_2",
            health_restore=0.0,
            duration=10.0,         # 10 sec of regen
            quality=gamedataQuality.Uncommon,
            healthRegenRate=15.0,  # 15 HP/s during duration
        ))
        # Alcohol: mild stat buff / debuff
        self._add(ConsumableRecord(
            "Items.Alcohol_Generic",
            health_restore=5.0,
            duration=30.0,
            quality=gamedataQuality.Common,
            reflexesDebuff=-1,     # -1 Reflexes while drunk
        ))

    def _seed_amm_records(self) -> None:
        """
        Seed AMM-specific TweakDB records.

        AMM's onTweak() clones vanilla character/vehicle records into its own
        namespace (AMM_Character.*, AMM_Vehicle.*) and overrides entityTemplatePath
        to point to custom .ent files bundled with the mod.

        We simulate the same clone chain so tests can verify:
          - CloneRecord() creates the AMM_Character.* entries
          - SetFlatNoUpdate() + Update() change entityTemplatePath
          - GetRecord("AMM_Character.Judy") returns the cloned record
        """
        # Base character records that AMM clones from (vanilla Character.*)
        char_base = gamedataRecord("Character.Base_NPC",
                                   entityTemplatePath="base\\characters\\entities\\base_npc.ent",
                                   canBeCompanion=False, isSpawnable=True)
        self._add(char_base)

        vanilla_chars = [
            ("Character.Judy_Judy",         "base\\characters\\entities\\judy.ent"),
            ("Character.Panam_Palmer",       "base\\characters\\entities\\panam.ent"),
            ("Character.Johnny_Silverhand",  "base\\characters\\entities\\johnny.ent"),
            ("Character.Rogue_Amendiares",   "base\\characters\\entities\\rogue.ent"),
            ("Character.V_Default",          "base\\characters\\entities\\v_default.ent"),
            ("Character.V_Default_Female",   "base\\characters\\entities\\v_default_fem.ent"),
        ]
        for path, ent_path in vanilla_chars:
            self._add(gamedataRecord(path,
                                     entityTemplatePath=ent_path,
                                     canBeCompanion=True,
                                     isSpawnable=True))

        # AMM's cloned AMM_Character.* records (entityTemplatePath → AMM ent files)
        amm_chars = [
            ("AMM_Character.Judy",
             "base\\amm_characters\\entity\\judy.ent"),
            ("AMM_Character.Panam",
             "base\\amm_characters\\entity\\panam.ent"),
            ("AMM_Character.Johnny",
             "base\\amm_characters\\entity\\johnny.ent"),
            ("AMM_Character.Rogue",
             "base\\amm_characters\\entity\\rogue.ent"),
            ("AMM_Character.Player_Male",
             "base\\amm_characters\\entity\\player_male_cutscene.ent"),
            ("AMM_Character.Player_Female",
             "base\\amm_characters\\entity\\player_female_cutscene.ent"),
        ]
        for path, ent_path in amm_chars:
            self._add(gamedataRecord(path,
                                     entityTemplatePath=ent_path,
                                     canBeCompanion=True,
                                     isSpawnable=True,
                                     isAMMCharacter=True))

        # AMM photo-mode record patches (mirrors AMM's onTweak patching)
        self._add(gamedataRecord(
            "photo_mode.LookatPreset.PhotoMode_LookAtCamera",
            followingSpeedFactorOverride=1200.0,
        ))
        self._add(gamedataRecord(
            "photo_mode.CameraData",
            maxFOV=100.0, minFOV=10.0,
            maxRoll=30.0, minRoll=-30.0,
        ))
