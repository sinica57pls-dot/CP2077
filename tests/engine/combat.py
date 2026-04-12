"""
Combat / Damage System Simulation
===================================

Mirrors the damage pipeline from:
  scripts/Combat/         (hit resolution, damage types, status effects)
  src/Red/GameInstance.hpp (GetDamageSystem)

CP2077 damage pipeline (in order):
  1. Weapon base damage (from TweakDB record)
  2. Skill damage bonus (% based on weapon type + skill level)
  3. Perk bonuses (additive % from active perks)
  4. Attack Power modifier (additive flat from gear)
  5. Critical hit calculation (CritChance roll → CritDamage multiplier)
  6. Headshot bonus (2× ranged, 1.4× melee)
  7. Stealth / unaware bonus (if enemy is unaware)
  8. Armor mitigation (reduces incoming physical damage)
  9. Type resistance (reduces specific elemental damage)
  10. Final damage application → HP subtracted

Status effects:
  Burning   -- periodic Thermal damage (30 DMG/s × 4s = 120 total max)
  Bleeding  -- periodic Physical damage (10 DMG/s × 3s = 30 total)
  Poison    -- % of max HP per second (3%/s × 5s = 15% max HP total)
  EMP       -- disables cyberware (no damage, triggers cooldown extension)
  Shock     -- Electric damage + stagger (0.5s stun)
  Burning is also triggered by Thermal hits, Shock by Electric/EMP, etc.

All formulae are calibrated to real in-game observed values documented on:
  https://cyberpunk.fandom.com/wiki/Combat
  https://wiki.redmodding.org/cyberpunk-2077-modding/
"""

from __future__ import annotations
import math
import enum
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable

from .tweakdb import gamedataDamageType, gamedataItemType, gamedataWeaponEvolution


# ════════════════════════════════════════════════════════════════════════════
#  Hit flags
# ════════════════════════════════════════════════════════════════════════════

class HitFlag(enum.Flag):
    """Bitfield flags describing how a hit was landed (gamedataHitFlag)."""
    Normal         = 0
    Critical       = 1          # crit roll succeeded
    Headshot       = 2          # hit registered on head hitbox
    Unaware        = 4          # target had no combat awareness
    WeakSpot       = 8          # hit weak spot (some enemies have special spots)
    DotApplication = 16         # hit applied a status effect
    Charged        = 32         # tech weapon full-charge shot
    Ricochet       = 64         # power weapon bullet bounced
    SmartGuidance  = 128        # smart weapon homing hit


# ════════════════════════════════════════════════════════════════════════════
#  Hit instance  (gamedataHitInstance)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class HitInstance:
    """One resolved hit event -- matches gamedataHitInstance in the real engine.

    The DamageSystem fills this in and it is then used to:
      - subtract HP from the target
      - trigger status effects
      - display on-screen damage numbers
      - award XP / street cred
    """
    # Attacker context
    attacker_id:    str = "player"
    weapon_record_id: str = ""        # TweakDBID path of the weapon used

    # Damage values
    base_damage:    float = 0.0       # weapon base damage per hit
    final_damage:   float = 0.0       # after all modifiers, before armor
    damage_dealt:   float = 0.0       # after armor / resistance, applied to HP
    damage_type:    gamedataDamageType = gamedataDamageType.Physical

    # Hit flags
    flags:          HitFlag = HitFlag.Normal

    # Resolved bonuses (for inspection / test assertions)
    skill_bonus:    float = 0.0       # % from skill
    perk_bonus:     float = 0.0       # % from perks
    crit_bonus:     float = 0.0       # crit damage bonus applied (0 if not crit)
    headshot_mult:  float = 1.0
    stealth_bonus:  float = 0.0
    armor_reduction: float = 0.0     # flat damage reduced by armor

    @property
    def is_crit(self) -> bool:
        return bool(self.flags & HitFlag.Critical)

    @property
    def is_headshot(self) -> bool:
        return bool(self.flags & HitFlag.Headshot)

    @property
    def is_unaware(self) -> bool:
        return bool(self.flags & HitFlag.Unaware)


# ════════════════════════════════════════════════════════════════════════════
#  Status effects
# ════════════════════════════════════════════════════════════════════════════

class StatusEffectType(enum.Enum):
    Burning  = "Burning"
    Bleeding = "Bleeding"
    Poison   = "Poison"
    Shock    = "Shock"
    EMP      = "EMP"
    Stagger  = "Stagger"
    Stun     = "Stun"
    Blind    = "Blind"        # from cyberware / quickhacks


@dataclass
class StatusEffectInstance:
    """One active status effect on a target.

    Mirrors gamedataStatusEffect_Record applied to a character.
    """
    effect_type:   StatusEffectType
    duration:      float    # total seconds remaining
    tick_interval: float    # seconds between damage ticks (0 = applied once)
    tick_damage:   float    # flat damage / tick (0 for non-damage effects)
    damage_type:   gamedataDamageType = gamedataDamageType.Physical
    source_id:     str = "unknown"    # who applied this

    # Internal tick accumulator
    _elapsed:      float = field(default=0.0, repr=False)

    def is_expired(self) -> bool:
        return self.duration <= 0.0

    def advance(self, dt: float) -> List[float]:
        """Tick the status effect forward by dt seconds.
        Returns a list of damage values that should be applied this step.
        """
        damages = []
        if self.is_expired():
            return damages

        if self.tick_interval > 0:
            self._elapsed += dt
            while self._elapsed >= self.tick_interval and not self.is_expired():
                damages.append(self.tick_damage)
                self._elapsed -= self.tick_interval
                self.duration -= self.tick_interval
        else:
            # Instant effect (EMP, Stun, Stagger)
            self.duration = 0.0

        # Decay overall duration
        if self.tick_interval > 0:
            pass   # duration already decremented above
        else:
            self.duration -= dt
        self.duration = max(0.0, self.duration)
        return damages


# ════════════════════════════════════════════════════════════════════════════
#  DamageSystem
# ════════════════════════════════════════════════════════════════════════════

class DamageSystem:
    """Resolves all damage calculations for one attacker→target interaction.

    Usage:
        from engine.stats import CharacterStats, NPCStats, StatsSystem
        weapon = TweakDB.Get().GetRecord("Items.Preset_Yukimura_Default")
        hit = DamageSystem.resolve_hit(
            attacker_stats=player_stats,
            weapon_record=weapon,
            target_stats=npc_stats,
            flags=HitFlag.Headshot,
        )
        npc_stats.take_damage(hit.damage_dealt)

    Deterministic mode (for tests):
        Pass rng_seed to fix the random number generator so crit rolls are
        deterministic.  rng_seed=None uses real randomness.
    """

    # Armor mitigation formula constant (from community testing).
    # DamageAfterArmor = Damage × (1 - Armor / (Armor + ARMOR_K))
    # ARMOR_K=60 produces:
    #   Armor=0   → 0% mitigation
    #   Armor=60  → 50% mitigation
    #   Armor=240 → 80% mitigation
    #   Armor=540 → 90% mitigation
    ARMOR_K: float = 60.0

    # Max armor mitigation cap (CP2077 caps at 85% physical mitig.)
    ARMOR_CAP: float = 0.85

    @staticmethod
    def compute_armor_mitigation(armor: float) -> float:
        """Returns fraction of damage blocked by armor (0.0–ARMOR_CAP)."""
        if armor <= 0:
            return 0.0
        mitig = armor / (armor + DamageSystem.ARMOR_K)
        return min(mitig, DamageSystem.ARMOR_CAP)

    @classmethod
    def resolve_hit(cls,
                    attacker_stats,          # CharacterStats or None
                    weapon_record,           # gamedataRecord (WeaponRecord)
                    target_stats,            # NPCStats
                    flags: HitFlag = HitFlag.Normal,
                    charged: bool = False,
                    rng_seed: Optional[int] = None) -> HitInstance:
        """Fully resolve a weapon hit.

        Steps:
          1. Base damage from weapon record
          2. Skill bonus
          3. Perk bonus
          4. Attack Power additive
          5. Crit roll → crit multiplier
          6. Headshot multiplier
          7. Stealth / unaware bonus
          8. Total pre-armor damage
          9. Armor mitigation (only for Physical)
          10. Type resistance
          11. Final damage_dealt

        Returns a filled HitInstance.  Callers should apply hit.damage_dealt
        to the target's HP pool.
        """
        from .stats import StatsSystem, gamedataStatType  # deferred import

        rng = random.Random(rng_seed)

        hit = HitInstance()
        hit.flags = flags

        # ── Step 1: Base weapon damage ───────────────────────────────────────
        if weapon_record is None:
            # Unarmed attack
            base_dmg = 20.0
            w_type = gamedataItemType.Wea_OneHandedClub
            dmg_type = gamedataDamageType.Physical
            hit.weapon_record_id = "unarmed"
        else:
            base_dmg = weapon_record.GetFlat("damagePerHit", 20.0)
            w_type   = weapon_record.GetFlat("itemType", gamedataItemType.Wea_Pistol)
            dmg_type = weapon_record.GetFlat("damageType", gamedataDamageType.Physical)
            hit.weapon_record_id = str(weapon_record.GetID())
        hit.base_damage = base_dmg
        hit.damage_type = dmg_type

        # Charged-shot multiplier for Tech weapons
        if charged and weapon_record:
            evolution = weapon_record.GetFlat("evolution", gamedataWeaponEvolution.Power)
            if evolution == gamedataWeaponEvolution.Tech:
                charge_mult = weapon_record.GetFlat("chargeMultiplier", 1.5)
                base_dmg   *= charge_mult
                hit.flags  |= HitFlag.Charged

        # ── Step 2: Skill bonus ──────────────────────────────────────────────
        skill_bonus = 0.0
        if attacker_stats is not None:
            if w_type in (gamedataItemType.Wea_Pistol,
                          gamedataItemType.Wea_Revolver):
                skill_bonus = StatsSystem.compute_handgun_damage_bonus(attacker_stats)
            elif w_type in (gamedataItemType.Wea_AssaultRifle,
                            gamedataItemType.Wea_SubmachineGun,
                            gamedataItemType.Wea_LightMachineGun,
                            gamedataItemType.Wea_HeavyMachineGun):
                skill_bonus = StatsSystem.compute_assault_damage_bonus(attacker_stats)
            elif w_type in (gamedataItemType.Wea_Shotgun,
                            gamedataItemType.Wea_ShotgunDual):
                skill_bonus = StatsSystem.compute_annihilation_damage_bonus(attacker_stats)
            elif w_type in (gamedataItemType.Wea_Melee,
                            gamedataItemType.Wea_Knife):
                skill_bonus = StatsSystem.compute_blade_damage_bonus(attacker_stats)
            elif w_type in (gamedataItemType.Wea_OneHandedClub,
                            gamedataItemType.Wea_TwoHandedClub,
                            gamedataItemType.Cyb_StrongArms):
                skill_bonus = StatsSystem.compute_street_brawler_bonus(attacker_stats)
            elif w_type == gamedataItemType.Wea_SniperRifle:
                skill_bonus = StatsSystem.compute_assault_damage_bonus(attacker_stats)
        hit.skill_bonus = skill_bonus

        # ── Step 3: Perk bonus ───────────────────────────────────────────────
        perk_bonus = 0.0
        if attacker_stats is not None:
            # Short-range shotgun bonus (CloseAndPersonal)
            if (attacker_stats.has_perk("Perks.CloseAndPersonal")
                    and w_type in (gamedataItemType.Wea_Shotgun,
                                   gamedataItemType.Wea_ShotgunDual)):
                perk_bonus += 0.20   # handled separately in real game; simplified here

            # Armour-piercing shotgun (ShotgunSurgeon) -- applied at step 9
        hit.perk_bonus = perk_bonus

        # ── Step 4: Attack Power additive (from gear modifiers) ──────────────
        flat_ap = 0.0
        if attacker_stats is not None:
            flat_ap = attacker_stats.get_additive(gamedataStatType.AttackPower)

        # ── Step 5: Crit roll ────────────────────────────────────────────────
        crit_chance = 0.0
        crit_dmg_bonus = 0.0
        if attacker_stats is not None:
            crit_chance    = StatsSystem.compute_crit_chance(attacker_stats) / 100.0
            crit_dmg_bonus = StatsSystem.compute_crit_damage(attacker_stats) / 100.0
        if rng.random() < crit_chance:
            hit.flags |= HitFlag.Critical
            hit.crit_bonus = crit_dmg_bonus

        # ── Step 6: Headshot multiplier ──────────────────────────────────────
        is_melee = w_type in (
            gamedataItemType.Wea_Melee, gamedataItemType.Wea_Knife,
            gamedataItemType.Wea_OneHandedClub, gamedataItemType.Wea_TwoHandedClub,
            gamedataItemType.Cyb_MantisBlades, gamedataItemType.Cyb_StrongArms,
            gamedataItemType.Cyb_NanoWire,
        )
        headshot_mult = 1.0
        if hit.is_headshot:
            if attacker_stats:
                headshot_mult = (StatsSystem.compute_melee_headshot_multiplier(attacker_stats)
                                 if is_melee
                                 else StatsSystem.compute_headshot_multiplier(attacker_stats))
            else:
                headshot_mult = 1.4 if is_melee else 2.0
        hit.headshot_mult = headshot_mult

        # ── Step 7: Stealth / unaware bonus ──────────────────────────────────
        stealth_bonus = 0.0
        if hit.is_unaware and attacker_stats:
            stealth_bonus = StatsSystem.compute_stealth_damage_bonus(attacker_stats)
        hit.stealth_bonus = stealth_bonus

        # ── Step 8: Pre-armor final damage ───────────────────────────────────
        final = base_dmg + flat_ap
        final *= (1.0 + skill_bonus + perk_bonus + stealth_bonus)
        if hit.is_crit:
            final *= (1.0 + crit_dmg_bonus)
        final *= headshot_mult
        hit.final_damage = round(final, 2)

        # ── Step 9: Armor mitigation (Physical damage only) ──────────────────
        armor_reduction = 0.0
        if dmg_type == gamedataDamageType.Physical:
            t_armor = target_stats.armor if target_stats else 0.0

            # ShotgunSurgeon perk ignores 25% of armor
            if (attacker_stats and
                    attacker_stats.has_perk("Perks.ShotgunSurgeon") and
                    w_type in (gamedataItemType.Wea_Shotgun,
                                gamedataItemType.Wea_ShotgunDual)):
                t_armor *= 0.75

            mitig = cls.compute_armor_mitigation(t_armor)
            armor_reduction = final * mitig
        hit.armor_reduction = round(armor_reduction, 2)

        # ── Step 10: Type resistance (elemental) ─────────────────────────────
        resistance = 0.0
        if target_stats:
            if dmg_type == gamedataDamageType.Thermal:
                resistance = target_stats.thermal_resistance / 100.0
            elif dmg_type == gamedataDamageType.Chemical:
                resistance = target_stats.chemical_resistance / 100.0
            elif dmg_type in (gamedataDamageType.Electric,
                              gamedataDamageType.EMP):
                resistance = target_stats.electric_resistance / 100.0
            elif dmg_type == gamedataDamageType.Physical:
                resistance = target_stats.physical_resistance / 100.0

        resist_reduction = final * resistance

        # ── Step 11: Final damage dealt ──────────────────────────────────────
        damage_dealt = max(0.0, final - armor_reduction - resist_reduction)
        hit.damage_dealt = round(damage_dealt, 2)

        return hit

    # ── Status effect factory ──────────────────────────────────────────────────

    @staticmethod
    def make_burning(source_id: str = "unknown") -> StatusEffectInstance:
        """Burning: 30 thermal DMG/s for 4 seconds.  (avg ~120 total)"""
        return StatusEffectInstance(
            effect_type=StatusEffectType.Burning,
            duration=4.0,
            tick_interval=1.0,
            tick_damage=30.0,
            damage_type=gamedataDamageType.Thermal,
            source_id=source_id,
        )

    @staticmethod
    def make_bleeding(source_id: str = "unknown") -> StatusEffectInstance:
        """Bleeding: 10 physical DMG/s for 3 seconds.  (30 total)"""
        return StatusEffectInstance(
            effect_type=StatusEffectType.Bleeding,
            duration=3.0,
            tick_interval=1.0,
            tick_damage=10.0,
            damage_type=gamedataDamageType.Physical,
            source_id=source_id,
        )

    @staticmethod
    def make_poison(max_hp: float, source_id: str = "unknown") -> StatusEffectInstance:
        """Poison: 3% max HP per second for 5 seconds."""
        return StatusEffectInstance(
            effect_type=StatusEffectType.Poison,
            duration=5.0,
            tick_interval=1.0,
            tick_damage=max_hp * 0.03,
            damage_type=gamedataDamageType.Chemical,
            source_id=source_id,
        )

    @staticmethod
    def make_shock(source_id: str = "unknown") -> StatusEffectInstance:
        """Shock: 50 electric DMG + 0.5s stun on apply."""
        return StatusEffectInstance(
            effect_type=StatusEffectType.Shock,
            duration=0.5,
            tick_interval=0.5,
            tick_damage=50.0,
            damage_type=gamedataDamageType.Electric,
            source_id=source_id,
        )

    @staticmethod
    def make_emp(source_id: str = "unknown") -> StatusEffectInstance:
        """EMP: disables cyberware for 3s, no direct damage."""
        return StatusEffectInstance(
            effect_type=StatusEffectType.EMP,
            duration=3.0,
            tick_interval=0.0,
            tick_damage=0.0,
            damage_type=gamedataDamageType.EMP,
            source_id=source_id,
        )


# ════════════════════════════════════════════════════════════════════════════
#  StatusEffectController  (per-entity status effect tracker)
# ════════════════════════════════════════════════════════════════════════════

class StatusEffectController:
    """Tracks active status effects on one entity and processes ticks.

    In the real game this lives inside the character's gamedataStatusEffectManager.
    Here it is a standalone helper driven by the GameSimulation tick.

    Usage:
        controller = StatusEffectController()
        controller.apply(DamageSystem.make_burning())
        tick_damages = controller.tick(dt=1.0)   # list of (gamedataDamageType, float)
    """

    def __init__(self):
        self._effects: List[StatusEffectInstance] = []

    def apply(self, effect: 'StatusEffectInstance') -> None:
        """Apply a status effect, refreshing duration if already active."""
        for existing in self._effects:
            if existing.effect_type == effect.effect_type:
                existing.duration = max(existing.duration, effect.duration)
                existing._elapsed = 0.0
                return
        self._effects.append(effect)

    def remove(self, effect_type: StatusEffectType) -> bool:
        before = len(self._effects)
        self._effects = [e for e in self._effects
                         if e.effect_type != effect_type]
        return len(self._effects) < before

    def has_effect(self, effect_type: StatusEffectType) -> bool:
        return any(e.effect_type == effect_type for e in self._effects)

    def tick(self, dt: float) -> List[tuple]:
        """Advance all effects.  Returns list of (damage_type, damage_amount) tuples."""
        damages = []
        new_effects = []
        for effect in self._effects:
            tick_damages = effect.advance(dt)
            for d in tick_damages:
                damages.append((effect.damage_type, d))
            if not effect.is_expired():
                new_effects.append(effect)
        self._effects = new_effects
        return damages

    def get_active(self) -> List[StatusEffectType]:
        return [e.effect_type for e in self._effects]

    def clear(self) -> None:
        self._effects.clear()


# ════════════════════════════════════════════════════════════════════════════
#  Weapon state  (ammo, reload, cooldown)
# ════════════════════════════════════════════════════════════════════════════

class WeaponState:
    """Runtime weapon state for a single weapon instance.

    Tracks ammo, reload timing, and fire rate so tests can simulate
    "can the player fire right now?" decisions accurately.
    """

    def __init__(self, record):
        """record -- WeaponRecord from TweakDB."""
        self.record = record
        mag_size   = record.GetFlat("magazineSize", 10) if record else 10
        reload_t   = record.GetFlat("reloadTime", 2.0)  if record else 2.0
        atk_speed  = record.GetFlat("attacksPerSecond", 1.0) if record else 1.0

        self.mag_size     = mag_size
        self.current_ammo = mag_size
        self.reload_time  = reload_t
        self.attack_speed = atk_speed
        self.fire_interval = 1.0 / atk_speed

        self._reload_timer = 0.0    # >0 means reloading
        self._fire_timer   = 0.0    # >0 means fire animation in progress

    def can_fire(self) -> bool:
        return (self.current_ammo > 0
                and self._reload_timer <= 0.0
                and self._fire_timer <= 0.0)

    def fire(self) -> bool:
        """Consume one round.  Returns True if fired."""
        if not self.can_fire():
            return False
        self.current_ammo -= 1
        self._fire_timer = self.fire_interval
        if self.current_ammo == 0:
            self._reload_timer = self.reload_time
        return True

    def reload(self) -> None:
        """Manually start a reload."""
        if self._reload_timer <= 0.0:
            self._reload_timer = self.reload_time

    def tick(self, dt: float) -> None:
        if self._reload_timer > 0.0:
            self._reload_timer = max(0.0, self._reload_timer - dt)
            if self._reload_timer == 0.0:
                self.current_ammo = self.mag_size
        if self._fire_timer > 0.0:
            self._fire_timer = max(0.0, self._fire_timer - dt)
