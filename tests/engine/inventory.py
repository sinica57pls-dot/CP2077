"""
Inventory System Simulation
============================

Mirrors the inventory systems from:
  src/Red/GameInstance.hpp  (GetTransactionSystem, GetInventoryManager)
  scripts/Player/           (equipment, inventory management)

CP2077 inventory architecture:
  - Every item is identified by an ItemID (wraps TweakDBID + optional UniqueID)
  - The *TransactionSystem* handles add / remove / transfer
  - The *EquipmentSystem* handles equipping to body slots
  - Items have quality tiers (Common → Legendary), upgrades, mods
  - Economy is eddies (€$) stored as a special item (Moneybag_Eddies)

Equipment slots (matches the player's Paperdoll UI in-game):
  Head, Eyes, Face, InnerChest, OuterChest, RightArm, LeftArm,
  Legs, Feet, RightHand (weapon), LeftHand (secondary weapon / secondary slot),
  OS (Operating System cyberware)

References:
  https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators-theory/
  WolvenKit: TransactionSystem.cpp, EquipmentSystem.cpp
"""

from __future__ import annotations
import uuid
import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

from .tweakdb import TweakDBID, gamedataRecord, gamedataItemType, gamedataQuality


# ════════════════════════════════════════════════════════════════════════════
#  ItemID
# ════════════════════════════════════════════════════════════════════════════

class ItemID:
    """Unique item instance identifier.

    In CP2077, ItemID = TweakDBID (record) + UniqueID (instance).
    Two items with the same TweakDBID are different instances if UniqueIDs differ.
    UniqueID == 0  for stackable items (ammo, crafting materials, eddies).
    """

    __slots__ = ('tdbid', 'unique_id', 'seed_value')

    def __init__(self, record_id: Union[str, TweakDBID],
                 unique_id: int = 0, seed: int = 0):
        if isinstance(record_id, str):
            record_id = TweakDBID(record_id)
        self.tdbid     = record_id
        self.unique_id = unique_id
        self.seed_value = seed

    @staticmethod
    def Create(record_id: Union[str, TweakDBID]) -> 'ItemID':
        """Create a fresh item instance with a random UniqueID (non-stackable)."""
        uid = int(uuid.uuid4()) & 0xFFFFFFFF
        return ItemID(record_id, unique_id=uid)

    @staticmethod
    def CreateQuery(record_id: Union[str, TweakDBID]) -> 'ItemID':
        """Create a query ID (unique_id=0) for stackable queries."""
        return ItemID(record_id, unique_id=0)

    def IsValid(self) -> bool:
        return self.tdbid.IsValid()

    def __eq__(self, other) -> bool:
        if isinstance(other, ItemID):
            return (self.tdbid == other.tdbid
                    and self.unique_id == other.unique_id)
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.tdbid, self.unique_id))

    def __repr__(self) -> str:
        if self.unique_id:
            return f"ItemID({self.tdbid!r}, uid={self.unique_id})"
        return f"ItemID({self.tdbid!r})"


# ════════════════════════════════════════════════════════════════════════════
#  Equipment slots
# ════════════════════════════════════════════════════════════════════════════

class EquipmentSlot(enum.Enum):
    """Player paperdoll equipment slots  (gamedataEquipmentArea in TweakDB)."""
    # Clothing
    Head       = "Head"
    Eyes       = "Eyes"
    Face       = "Face"
    InnerChest = "InnerChest"
    OuterChest = "OuterChest"
    Legs       = "Legs"
    Feet       = "Feet"
    # Arms (cyberware)
    RightArm   = "RightArm"
    LeftArm    = "LeftArm"
    # Weapons
    WeaponRight = "WeaponRight"       # primary / right hand
    WeaponLeft  = "WeaponLeft"        # secondary / left hand
    # Cyberware slots
    OperatingSystem = "OperatingSystem"  # Sandevistan, Berserk, Cyberdeck


# ════════════════════════════════════════════════════════════════════════════
#  Item data  (instance stored in inventory)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class ItemData:
    """One item instance in an inventory.

    Mirrors the structure resolved from TweakDB + game engine state.
    """
    item_id:    ItemID
    record:     Optional[gamedataRecord] = None   # resolved TweakDB record
    quantity:   int    = 1
    quality:    gamedataQuality = gamedataQuality.Common
    upgrade_level: int = 0         # 0–5 upgrades via crafting

    # Weapon-specific mutable state
    current_ammo: int  = -1        # -1 = not a ranged weapon or not tracked
    is_iconic:    bool = False

    def get_flat(self, flat_name: str, default=None):
        if self.record:
            return self.record.GetFlat(flat_name, default)
        return default


# ════════════════════════════════════════════════════════════════════════════
#  TransactionSystem  -- add / remove / query items
# ════════════════════════════════════════════════════════════════════════════

class TransactionSystem:
    """Manages item inventories.

    Each entity (player, vendor, container) has its own inventory stored here.
    The player's entity hash is TransactionSystem.PLAYER_ID.

    API mirrors the real TransactionSystem script bindings:
      AddItemToInventory(entity, itemID, amount)
      RemoveItemFromInventory(entity, itemID, amount)
      GetItemQuantity(entity, itemID)
      HasItem(entity, itemID)
      GetItemList(entity, itemType)
    """

    PLAYER_ID = "player"   # sentinel key for the player's inventory

    def __init__(self):
        # inventory_id → {ItemID → ItemData}
        self._inventories: Dict[str, Dict[ItemID, ItemData]] = {}
        # eddies stored separately for fast access
        self._eddies: Dict[str, int] = {}

    def _get_inv(self, entity_id: str) -> Dict[ItemID, ItemData]:
        return self._inventories.setdefault(entity_id, {})

    # ── Item add / remove ─────────────────────────────────────────────────────

    def AddItemToInventory(self, entity_id: str, item_id: ItemID,
                           amount: int = 1,
                           record: Optional[gamedataRecord] = None) -> bool:
        """Add `amount` copies of item to entity's inventory.
        For stackable items (unique_id == 0), merges the quantity.
        For unique items, stores each as a separate entry.
        Returns True on success.
        """
        if amount <= 0:
            return False

        if item_id.tdbid == TweakDBID("Items.money"):
            self._eddies[entity_id] = self._eddies.get(entity_id, 0) + amount
            return True

        inv = self._get_inv(entity_id)

        if item_id.unique_id == 0:
            # Stackable: find existing stack or create new
            key = ItemID.CreateQuery(item_id.tdbid)
            for k, v in inv.items():
                if k.tdbid == item_id.tdbid and k.unique_id == 0:
                    v.quantity += amount
                    return True
            # New stack
            inv[item_id] = ItemData(
                item_id=item_id, record=record, quantity=amount)
        else:
            # Unique item (weapon, iconic, etc.)
            inv[item_id] = ItemData(
                item_id=item_id, record=record, quantity=1,
                quality=record.GetFlat("quality", gamedataQuality.Common)
                        if record else gamedataQuality.Common,
                is_iconic=record.GetFlat("iconic", False) if record else False,
            )
        return True

    def RemoveItemFromInventory(self, entity_id: str, item_id: ItemID,
                                amount: int = 1) -> bool:
        """Remove `amount` copies.  Returns True if successful."""
        if item_id.tdbid == TweakDBID("Items.money"):
            current = self._eddies.get(entity_id, 0)
            if current < amount:
                return False
            self._eddies[entity_id] = current - amount
            return True

        inv = self._get_inv(entity_id)
        for k, v in list(inv.items()):
            if k.tdbid == item_id.tdbid:
                if item_id.unique_id and k.unique_id != item_id.unique_id:
                    continue
                if v.quantity <= amount:
                    del inv[k]
                else:
                    v.quantity -= amount
                return True
        return False

    def HasItem(self, entity_id: str, item_id: ItemID) -> bool:
        """Returns True if entity has at least 1 of this item."""
        if item_id.tdbid == TweakDBID("Items.money"):
            return self._eddies.get(entity_id, 0) > 0
        inv = self._get_inv(entity_id)
        for k in inv:
            if k.tdbid == item_id.tdbid:
                if item_id.unique_id == 0 or k.unique_id == item_id.unique_id:
                    return True
        return False

    def GetItemQuantity(self, entity_id: str, item_id: ItemID) -> int:
        """Total quantity of this item in the inventory."""
        if item_id.tdbid == TweakDBID("Items.money"):
            return self._eddies.get(entity_id, 0)
        inv = self._get_inv(entity_id)
        total = 0
        for k, v in inv.items():
            if k.tdbid == item_id.tdbid:
                total += v.quantity
        return total

    def GetItemList(self, entity_id: str,
                    item_type: Optional[gamedataItemType] = None
                    ) -> List[ItemData]:
        """List all items of a given type (or all items if type is None)."""
        inv = self._get_inv(entity_id)
        items = list(inv.values())
        if item_type is not None:
            items = [i for i in items
                     if i.get_flat("itemType") == item_type]
        return items

    # ── Eddies (€$) shortcuts ─────────────────────────────────────────────────

    def GetMoney(self, entity_id: str) -> int:
        """Return eddies balance."""
        return self._eddies.get(entity_id, 0)

    def AddMoney(self, entity_id: str, amount: int) -> None:
        """Add eddies."""
        self._eddies[entity_id] = self._eddies.get(entity_id, 0) + amount

    def SpendMoney(self, entity_id: str, amount: int) -> bool:
        """Spend eddies. Returns False if insufficient funds."""
        current = self._eddies.get(entity_id, 0)
        if current < amount:
            return False
        self._eddies[entity_id] = current - amount
        return True

    def TransferItem(self, from_id: str, to_id: str,
                     item_id: ItemID, amount: int = 1) -> bool:
        """Move item between inventories (e.g. loot → player)."""
        if not self.HasItem(from_id, item_id):
            return False
        data = self._get_inv(from_id).get(item_id)
        record = data.record if data else None
        removed = self.RemoveItemFromInventory(from_id, item_id, amount)
        if not removed:
            return False
        self.AddItemToInventory(to_id, item_id, amount, record=record)
        return True


# ════════════════════════════════════════════════════════════════════════════
#  EquipmentSystem  -- equip / unequip items to paperdoll slots
# ════════════════════════════════════════════════════════════════════════════

class EquipmentSystem:
    """Tracks what is equipped in each slot for each entity.

    In the real game, this drives the stat system and visual appearance.
    Here it tracks slot→ItemData and provides the total armor value.

    API mirrors gamedataEquipmentSystem REDscript bindings.
    """

    def __init__(self, transaction: TransactionSystem):
        self._tx = transaction
        # entity_id → { EquipmentSlot → ItemData }
        self._equipped: Dict[str, Dict[EquipmentSlot, ItemData]] = {}

    def _eq(self, entity_id: str) -> Dict[EquipmentSlot, ItemData]:
        return self._equipped.setdefault(entity_id, {})

    # ── Equip / unequip ───────────────────────────────────────────────────────

    def EquipItem(self, entity_id: str, item_id: ItemID,
                  slot: EquipmentSlot) -> bool:
        """Equip item to a slot.  The item must be in the inventory.
        Any previously equipped item in that slot is unequipped (but stays
        in inventory -- it's not removed, matching the real game's system).
        """
        if not self._tx.HasItem(entity_id, item_id):
            return False
        inv = self._tx._get_inv(entity_id)
        data = None
        for k, v in inv.items():
            if k.tdbid == item_id.tdbid:
                if item_id.unique_id == 0 or k.unique_id == item_id.unique_id:
                    data = v
                    break
        if data is None:
            return False
        self._eq(entity_id)[slot] = data
        return True

    def UnequipSlot(self, entity_id: str, slot: EquipmentSlot) -> bool:
        """Remove item from slot (item stays in inventory)."""
        eq = self._eq(entity_id)
        if slot not in eq:
            return False
        del eq[slot]
        return True

    def GetEquippedItem(self, entity_id: str,
                        slot: EquipmentSlot) -> Optional[ItemData]:
        return self._eq(entity_id).get(slot)

    def IsSlotOccupied(self, entity_id: str, slot: EquipmentSlot) -> bool:
        return slot in self._eq(entity_id)

    # ── Stat contributions ────────────────────────────────────────────────────

    def GetTotalArmor(self, entity_id: str) -> float:
        """Sum armor values from all equipped clothing."""
        total = 0.0
        for slot, item in self._eq(entity_id).items():
            armor = item.get_flat("armorValue", 0.0)
            total += armor
        return total

    def GetEquippedWeapon(self, entity_id: str,
                          hand: str = "right") -> Optional[ItemData]:
        """Return the active weapon.  hand='right' or 'left'."""
        slot = EquipmentSlot.WeaponRight if hand == "right" else EquipmentSlot.WeaponLeft
        return self._eq(entity_id).get(slot)

    def GetEquippedOS(self, entity_id: str) -> Optional[ItemData]:
        """Return the Operating System cyberware."""
        return self._eq(entity_id).get(EquipmentSlot.OperatingSystem)

    def GetAllEquipped(self, entity_id: str) -> Dict[EquipmentSlot, ItemData]:
        return dict(self._eq(entity_id))


# ════════════════════════════════════════════════════════════════════════════
#  Street Cred
# ════════════════════════════════════════════════════════════════════════════

_STREET_CRED_XP_TABLE = [
    0,       # level 1
    500,     # level 2
    1250,    # level 3
    2500,    # level 4
    4500,    # level 5
    7500,    # level 6
    11_000,  # level 7
    16_000,  # level 8
    22_000,  # level 9
    30_000,  # level 10
    40_000,  # level 11
    52_000,  # level 12
    67_000,  # level 13
    84_500,  # level 14  (estimate from community data)
    105_000, # level 15
    129_000, # level 16
    157_000, # level 17
    189_500, # level 18
    226_500, # level 19
    269_000, # level 50 (max)
]


class StreetCredSystem:
    """Street Cred -- fame/reputation in Night City.

    Street Cred (SC) is a secondary progression track (1-50) that unlocks
    access to vendors, gigs, and cyberware implants independent of V's level.

    Earned by: completing gigs, NCPD scanner hustles, public executions,
    and discovering locations.
    """

    def __init__(self):
        self._xp: Dict[str, int] = {}      # entity_id → total XP
        self._level: Dict[str, int] = {}   # entity_id → cached level

    def GetStreetCredPoints(self, entity_id: str) -> int:
        return self._xp.get(entity_id, 0)

    def GetStreetCredLevel(self, entity_id: str) -> int:
        xp = self._xp.get(entity_id, 0)
        level = 1
        for i, threshold in enumerate(_STREET_CRED_XP_TABLE):
            if xp >= threshold:
                level = i + 1
            else:
                break
        return min(level, 50)

    def AddStreetCredPoints(self, entity_id: str, amount: int) -> int:
        """Add SC XP, return new level."""
        self._xp[entity_id] = self._xp.get(entity_id, 0) + max(0, amount)
        return self.GetStreetCredLevel(entity_id)

    def GetXPToNextLevel(self, entity_id: str) -> int:
        """XP needed to reach the next SC level."""
        current_level = self.GetStreetCredLevel(entity_id)
        if current_level >= 50:
            return 0
        current_xp = self._xp.get(entity_id, 0)
        next_threshold = _STREET_CRED_XP_TABLE[current_level]
        return max(0, next_threshold - current_xp)
