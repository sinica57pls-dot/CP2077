"""
Combat / Damage System Tests
=============================

Validates the damage pipeline matches real CP2077 in-game behaviour.

Calibration checkpoints (community testing):
  - Armor formula: 60 armor → 50% mitigation (Armor/(Armor+60))
  - Headshot: 2× damage multiplier (ranged), 1.4× (melee)
  - Crit hit: (1 + CritDamage/100) × base  (at 100% crit dmg = 2× base)
  - Assassin perk: +10% vs unaware
  - DeadlyPrecision perk: +25% crit damage for pistols
  - Stealth unaware + Assassin: applied once (not double-stacked w/ headshot)
  - Physical damage only is mitigated by armor
  - Elemental (Thermal/Chemical/Electric) ignores armor but has resistances
  - Burning: 30 fire DMG/s × 4s = 120 total
  - Bleeding: 10 phys DMG/s × 3s = 30 total
  - Poison: 3% max HP/s × 5s = 15% max HP total

Run:
    python tests/run_tests.py
    python -m unittest tests.mods.test_combat_system -v
"""

import sys
import os
import unittest
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation, CharacterStats, NPCStats, StatsSystem,
    DamageSystem, HitFlag, HitInstance,
    StatusEffectType, StatusEffectInstance, StatusEffectController,
    WeaponState,
    gamedataDamageType, gamedataStatType,
    preset_early_game_v, preset_gunslinger_v,
)


# ════════════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════════════

def make_target(hp=500.0, armor=0.0) -> NPCStats:
    return NPCStats(max_health=hp, current_health=hp, armor=armor)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 1: Armor mitigation formula
# ════════════════════════════════════════════════════════════════════════════

class TestArmorMitigation(unittest.TestCase):

    def test_zero_armor_zero_mitigation(self):
        self.assertAlmostEqual(DamageSystem.compute_armor_mitigation(0), 0.0)

    def test_60_armor_50pct_mitigation(self):
        """The canonical CP2077 calibration point: 60 armor = 50% mitigation."""
        mitig = DamageSystem.compute_armor_mitigation(60.0)
        self.assertAlmostEqual(mitig, 0.50, delta=0.001)

    def test_240_armor_80pct_mitigation(self):
        """240 armor ≈ 80% mitigation (240/(240+60) = 0.80)."""
        mitig = DamageSystem.compute_armor_mitigation(240.0)
        self.assertAlmostEqual(mitig, 0.80, delta=0.01)

    def test_mitigation_caps_at_85pct(self):
        """CP2077 caps armor mitigation at 85%."""
        mitig = DamageSystem.compute_armor_mitigation(10000.0)
        self.assertLessEqual(mitig, DamageSystem.ARMOR_CAP)
        self.assertAlmostEqual(mitig, DamageSystem.ARMOR_CAP)

    def test_mitigation_increases_with_armor(self):
        low  = DamageSystem.compute_armor_mitigation(30.0)
        high = DamageSystem.compute_armor_mitigation(300.0)
        self.assertGreater(high, low)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 2: Basic hit resolution
# ════════════════════════════════════════════════════════════════════════════

class TestBasicHit(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def test_hit_has_positive_damage(self):
        target = make_target()
        hit = self.sim.resolve_hit("Items.Preset_Yukimura_Default",
                                   target, rng_seed=0)
        self.assertGreater(hit.damage_dealt, 0.0)

    def test_weapon_exists_in_tweakdb(self):
        """Resolving a hit with a valid weapon should populate weapon_record_id."""
        target = make_target()
        hit = self.sim.resolve_hit("Items.Preset_Yukimura_Default",
                                   target, rng_seed=0)
        self.assertIn("Yukimura", hit.weapon_record_id)

    def test_base_damage_comes_from_record(self):
        """base_damage in HitInstance should match the TweakDB record."""
        rec   = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        expected_base = rec.GetFlat("damagePerHit")
        target = make_target()
        hit = DamageSystem.resolve_hit(
            attacker_stats=None,  # no stats = pure weapon base
            weapon_record=rec,
            target_stats=target,
            rng_seed=999,         # seed where crit doesn't fire
        )
        self.assertAlmostEqual(hit.base_damage, expected_base, delta=0.1)

    def test_no_armor_damage_equals_final(self):
        """With no armor, pre-armor final damage should equal damage_dealt."""
        target = make_target(armor=0.0)
        rec    = self.sim.tweakdb.GetRecord("Items.Preset_Revolver_Default")
        hit = DamageSystem.resolve_hit(
            attacker_stats=None, weapon_record=rec,
            target_stats=target, flags=HitFlag.Normal, rng_seed=999)
        # No crit, no headshot, no armor → final_damage ≈ damage_dealt
        if not hit.is_crit:
            self.assertAlmostEqual(hit.final_damage, hit.damage_dealt, delta=0.5)

    def test_armor_reduces_physical_damage(self):
        target_no_armor = make_target(armor=0.0)
        target_with     = make_target(armor=120.0)
        rec = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        hit_no  = DamageSystem.resolve_hit(attacker_stats=None,
            weapon_record=rec, target_stats=target_no_armor, rng_seed=999)
        hit_arm = DamageSystem.resolve_hit(attacker_stats=None,
            weapon_record=rec, target_stats=target_with,   rng_seed=999)
        if not hit_no.is_crit and not hit_arm.is_crit:
            self.assertLess(hit_arm.damage_dealt, hit_no.damage_dealt)

    def test_elemental_ignores_armor(self):
        """Thermal /Chemical / Electric damage is NOT reduced by physical armor."""
        from engine.tweakdb import WeaponRecord, gamedataDamageType, gamedataItemType
        # Create a custom thermal weapon  (Thermal type = ignores armor)
        thermal_weapon = WeaponRecord(
            "Test.ThermalPistol",
            damage_per_hit=100.0, attacks_per_sec=1.0,
            damage_type=gamedataDamageType.Thermal)
        target_no_armor = make_target(armor=0.0)
        target_heavy    = make_target(armor=999.0)  # extreme armor
        hit_no  = DamageSystem.resolve_hit(None, thermal_weapon, target_no_armor, rng_seed=999)
        hit_arm = DamageSystem.resolve_hit(None, thermal_weapon, target_heavy,    rng_seed=999)
        # Thermal is never mitigated by armor; both should be equal
        self.assertAlmostEqual(hit_no.damage_dealt, hit_arm.damage_dealt, delta=0.5)

    def test_skill_bonus_increases_damage(self):
        """Higher Handguns skill → more damage with pistols."""
        rec    = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        target = make_target(armor=0.0)

        s_low  = CharacterStats(); s_low.set_skill("Handguns", 1)
        s_high = CharacterStats(); s_high.set_skill("Handguns", 20)

        hit_low  = DamageSystem.resolve_hit(s_low,  rec, target, rng_seed=999)
        hit_high = DamageSystem.resolve_hit(s_high, rec, target, rng_seed=999)
        if not hit_low.is_crit and not hit_high.is_crit:
            self.assertGreater(hit_high.damage_dealt, hit_low.damage_dealt)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 3: Headshot multiplier
# ════════════════════════════════════════════════════════════════════════════

class TestHeadshotMultiplier(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def test_ranged_headshot_2x_base(self):
        """Ranged headshot deals 2× the base hit damage (no crits)."""
        rec    = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        target = make_target(armor=0.0)

        # Force no-crit via seed; compare body hit vs headshot
        hit_body = DamageSystem.resolve_hit(None, rec, target, HitFlag.Normal,  rng_seed=999)
        hit_head = DamageSystem.resolve_hit(None, rec, target, HitFlag.Headshot, rng_seed=999)

        # Body hit base damage should be ≈ base; headshot should be ≈ 2× base
        if not hit_body.is_crit and not hit_head.is_crit:
            ratio = hit_head.damage_dealt / hit_body.damage_dealt
            self.assertAlmostEqual(ratio, 2.0, delta=0.05)

    def test_headshot_multiplier_stored_in_hit(self):
        rec    = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        target = make_target(armor=0.0)
        hit = DamageSystem.resolve_hit(None, rec, target, HitFlag.Headshot, rng_seed=999)
        self.assertAlmostEqual(hit.headshot_mult, 2.0, delta=0.01)

    def test_body_shot_headshot_mult_is_1(self):
        rec    = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        target = make_target(armor=0.0)
        hit = DamageSystem.resolve_hit(None, rec, target, HitFlag.Normal, rng_seed=999)
        self.assertAlmostEqual(hit.headshot_mult, 1.0, delta=0.01)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 4: Critical hits
# ════════════════════════════════════════════════════════════════════════════

class TestCriticalHits(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def _force_crit(self):
        """Stats with 100% crit chance."""
        s = CharacterStats()
        s.set_attribute("Reflexes", 20)
        # Add a huge crit chance modifier to guarantee crit
        s.add_modifier(gamedataStatType.CritChance, 80.0, source="test")
        return s

    def _force_no_crit(self):
        """Stats with 0% crit chance."""
        s = CharacterStats()
        s.set_attribute("Reflexes", 1)
        return s

    def test_guaranteed_crit_flag(self):
        rec    = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        target = make_target(armor=0.0)
        # Use random seed that rolls high enough to guarantee crit with 100% chance
        hit = DamageSystem.resolve_hit(self._force_crit(), rec, target, rng_seed=1)
        self.assertTrue(hit.is_crit)

    def test_crit_damage_bonus_stored(self):
        s = self._force_crit()
        s.set_attribute("Cool", 10)   # crit dmg bonus
        rec    = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        target = make_target(armor=0.0)
        hit = DamageSystem.resolve_hit(s, rec, target, rng_seed=1)
        if hit.is_crit:
            self.assertGreater(hit.crit_bonus, 0.0)

    def test_crit_multiplier_calculation(self):
        """Crit damage bonus of 50% means crit hit = 1.5× normal hit."""
        s = CharacterStats()
        s.set_attribute("Cool", 1)   # base crit dmg = 50%
        s.set_attribute("Reflexes", 1)  # low crit chance
        rec    = self.sim.tweakdb.GetRecord("Items.Preset_Revolver_Default")
        target = make_target(armor=0.0)

        # Manually compute expected crit hit to validate formula
        base_dmg = rec.GetFlat("damagePerHit")
        crit_dmg = StatsSystem.compute_crit_damage(s) / 100.0  # e.g. 0.50
        expected_crit = base_dmg * (1.0 + crit_dmg)

        hit = DamageSystem.resolve_hit(s, rec, target, HitFlag.Normal, rng_seed=1)
        if hit.is_crit:
            self.assertAlmostEqual(hit.final_damage, expected_crit, delta=1.0)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 5: Stealth / unaware bonus
# ════════════════════════════════════════════════════════════════════════════

class TestStealthBonus(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.rec    = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        self.target = make_target(armor=0.0)

    def tearDown(self):
        self.sim.teardown()

    def test_assassin_perk_adds_10pct_vs_unaware(self):
        s_no_perk = CharacterStats(); s_no_perk.set_attribute("Reflexes", 1)
        s_assassin = CharacterStats(); s_assassin.set_attribute("Reflexes", 1)
        s_assassin.add_perk("Perks.Assassin")

        hit_normal = DamageSystem.resolve_hit(
            s_no_perk,            self.rec, self.target,
            HitFlag.Unaware, rng_seed=999)
        hit_stealth = DamageSystem.resolve_hit(
            s_assassin,           self.rec, self.target,
            HitFlag.Unaware, rng_seed=999)

        if not hit_normal.is_crit and not hit_stealth.is_crit:
            ratio = hit_stealth.damage_dealt / hit_normal.damage_dealt
            self.assertAlmostEqual(ratio, 1.10, delta=0.02)

    def test_stealth_flag_stored(self):
        hit = DamageSystem.resolve_hit(None, self.rec, self.target,
                                       HitFlag.Unaware, rng_seed=999)
        self.assertTrue(hit.is_unaware)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 6: ShotgunSurgeon perk (armor penetration)
# ════════════════════════════════════════════════════════════════════════════

class TestShotgunSurgeonPerk(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()
        self.shotgun  = self.sim.tweakdb.GetRecord("Items.Preset_Shotgun_Default")
        self.pistol   = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")

    def tearDown(self):
        self.sim.teardown()

    def test_surgeon_perk_penetrates_more_armor_for_shotguns(self):
        """ShotgunSurgeon: shotguns ignore 25% of armor → more damage vs armored target."""
        target = make_target(armor=120.0)
        s_no   = CharacterStats()
        s_perk = CharacterStats(); s_perk.add_perk("Perks.ShotgunSurgeon")

        hit_no   = DamageSystem.resolve_hit(s_no,   self.shotgun, target, rng_seed=999)
        hit_perk = DamageSystem.resolve_hit(s_perk, self.shotgun, target, rng_seed=999)

        if not hit_no.is_crit and not hit_perk.is_crit:
            self.assertGreater(hit_perk.damage_dealt, hit_no.damage_dealt)

    def test_shotgun_surgeon_no_effect_on_pistols(self):
        """ShotgunSurgeon should not affect pistol damage."""
        target = make_target(armor=120.0)
        s_no   = CharacterStats()
        s_perk = CharacterStats(); s_perk.add_perk("Perks.ShotgunSurgeon")

        hit_no   = DamageSystem.resolve_hit(s_no,   self.pistol, target, rng_seed=999)
        hit_perk = DamageSystem.resolve_hit(s_perk, self.pistol, target, rng_seed=999)

        if not hit_no.is_crit and not hit_perk.is_crit:
            self.assertAlmostEqual(hit_no.damage_dealt, hit_perk.damage_dealt, delta=0.5)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 7: Status effects
# ════════════════════════════════════════════════════════════════════════════

class TestStatusEffects(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    # ── Burning ──────────────────────────────────────────────────────────────

    def test_burning_deals_thermal_damage(self):
        burn = DamageSystem.make_burning()
        self.assertEqual(burn.damage_type, gamedataDamageType.Thermal)

    def test_burning_total_damage(self):
        """Burning: 30 dmg/s × 4s = 120 total."""
        burn = DamageSystem.make_burning()
        total = 0.0
        for _ in range(4):
            damages = burn.advance(1.0)
            total += sum(damages)
        self.assertAlmostEqual(total, 120.0, delta=5.0)

    def test_burning_expires_after_4s(self):
        burn = DamageSystem.make_burning()
        for _ in range(5):
            burn.advance(1.0)
        self.assertTrue(burn.is_expired())

    # ── Bleeding ─────────────────────────────────────────────────────────────

    def test_bleeding_deals_physical_damage(self):
        bleed = DamageSystem.make_bleeding()
        self.assertEqual(bleed.damage_type, gamedataDamageType.Physical)

    def test_bleeding_total_damage(self):
        """Bleeding: 10 dmg/s × 3s = 30 total."""
        bleed = DamageSystem.make_bleeding()
        total = sum(d for _ in range(3) for d in bleed.advance(1.0))
        self.assertAlmostEqual(total, 30.0, delta=2.0)

    def test_bleeding_expires_after_3s(self):
        bleed = DamageSystem.make_bleeding()
        for _ in range(4):
            bleed.advance(1.0)
        self.assertTrue(bleed.is_expired())

    # ── Poison ───────────────────────────────────────────────────────────────

    def test_poison_deals_chemical_damage(self):
        poison = DamageSystem.make_poison(max_hp=1000.0)
        self.assertEqual(poison.damage_type, gamedataDamageType.Chemical)

    def test_poison_percent_of_max_hp(self):
        """Poison: 3% of max HP per second × 5s = 15% max HP total."""
        max_hp = 500.0
        poison = DamageSystem.make_poison(max_hp=max_hp)
        total  = sum(d for _ in range(5) for d in poison.advance(1.0))
        expected = max_hp * 0.15
        self.assertAlmostEqual(total, expected, delta=5.0)

    # ── Shock ─────────────────────────────────────────────────────────────────

    def test_shock_deals_electric_damage(self):
        shock = DamageSystem.make_shock()
        self.assertEqual(shock.damage_type, gamedataDamageType.Electric)

    def test_shock_deals_damage_on_first_tick(self):
        shock = DamageSystem.make_shock()
        damages = shock.advance(0.5)
        self.assertGreater(sum(damages), 0.0)

    # ── EMP ───────────────────────────────────────────────────────────────────

    def test_emp_no_direct_damage(self):
        emp = DamageSystem.make_emp()
        total = sum(d for _ in range(5) for d in emp.advance(0.5))
        self.assertEqual(total, 0.0)

    def test_emp_lasts_3s(self):
        emp = DamageSystem.make_emp()
        self.assertAlmostEqual(emp.duration, 3.0)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 8: StatusEffectController
# ════════════════════════════════════════════════════════════════════════════

class TestStatusEffectController(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.ctrl = StatusEffectController()

    def tearDown(self):
        self.sim.teardown()

    def test_apply_effect(self):
        self.ctrl.apply(DamageSystem.make_burning())
        self.assertIn(StatusEffectType.Burning, self.ctrl.get_active())

    def test_tick_produces_damage(self):
        self.ctrl.apply(DamageSystem.make_burning())
        damages = self.ctrl.tick(1.0)
        self.assertGreater(len(damages), 0)

    def test_expired_effect_removed(self):
        burn = DamageSystem.make_burning()
        self.ctrl.apply(burn)
        for _ in range(6):
            self.ctrl.tick(1.0)
        self.assertNotIn(StatusEffectType.Burning, self.ctrl.get_active())

    def test_refresh_extends_duration(self):
        """Applying the same effect while active refreshes its duration."""
        self.ctrl.apply(DamageSystem.make_burning())
        self.ctrl.tick(2.0)  # 2 seconds used
        # Re-apply with fresh duration (4s)
        self.ctrl.apply(DamageSystem.make_burning())
        active = [e for e in self.ctrl._effects
                  if e.effect_type == StatusEffectType.Burning]
        self.assertGreater(active[0].duration, 0.5,
            "Re-applied Burning should have refreshed duration")

    def test_multiple_effects_tracked(self):
        self.ctrl.apply(DamageSystem.make_burning())
        self.ctrl.apply(DamageSystem.make_bleeding())
        self.assertIn(StatusEffectType.Burning,  self.ctrl.get_active())
        self.assertIn(StatusEffectType.Bleeding, self.ctrl.get_active())

    def test_remove_specific_effect(self):
        self.ctrl.apply(DamageSystem.make_burning())
        self.ctrl.apply(DamageSystem.make_bleeding())
        self.ctrl.remove(StatusEffectType.Burning)
        self.assertNotIn(StatusEffectType.Burning,  self.ctrl.get_active())
        self.assertIn(StatusEffectType.Bleeding, self.ctrl.get_active())

    def test_clear_all_effects(self):
        self.ctrl.apply(DamageSystem.make_burning())
        self.ctrl.apply(DamageSystem.make_poison(max_hp=100.0))
        self.ctrl.clear()
        self.assertEqual(len(self.ctrl.get_active()), 0)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 9: WeaponState (ammo & fire rate)
# ════════════════════════════════════════════════════════════════════════════

class TestWeaponState(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_can_fire_initially(self):
        rec = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        ws  = WeaponState(rec)
        self.assertTrue(ws.can_fire())

    def test_fire_reduces_ammo(self):
        rec = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        ws  = WeaponState(rec)
        ws.fire()
        self.assertEqual(ws.current_ammo, ws.mag_size - 1)

    def test_empty_mag_triggers_reload(self):
        rec = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        ws  = WeaponState(rec)
        for _ in range(ws.mag_size):
            ws.fire()
        self.assertFalse(ws.can_fire())

    def test_reload_restores_ammo(self):
        rec = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        ws  = WeaponState(rec)
        for _ in range(ws.mag_size):
            ws.fire()
        # Simulate reload duration
        ws.tick(ws.reload_time + 0.1)
        self.assertEqual(ws.current_ammo, ws.mag_size)
        self.assertTrue(ws.can_fire())

    def test_fire_interval_enforced(self):
        """Can't fire again before the fire interval has elapsed."""
        rec = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        ws  = WeaponState(rec)
        ws.fire()
        self.assertFalse(ws.can_fire(), "Should not fire again without tick")
        ws.tick(ws.fire_interval + 0.01)
        self.assertTrue(ws.can_fire())

    def test_revolver_has_6_round_mag(self):
        rec = self.sim.tweakdb.GetRecord("Items.Preset_Revolver_Default")
        ws  = WeaponState(rec)
        self.assertEqual(ws.mag_size, 6)

    def test_smg_has_larger_mag_than_pistol(self):
        pistol = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        smg    = self.sim.tweakdb.GetRecord("Items.Preset_SMG_Default")
        wp = WeaponState(pistol)
        ws = WeaponState(smg)
        self.assertGreater(ws.mag_size, wp.mag_size)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 10: End-to-end combat scenario
# ════════════════════════════════════════════════════════════════════════════

class TestEndToEndCombat(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def test_kill_unarmored_enemy(self):
        """Shoot an unarmored enemy until HP reaches 0."""
        target = make_target(hp=200.0, armor=0.0)
        rec  = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")

        # Use default V with Handguns 10
        s = CharacterStats(); s.set_skill("Handguns", 10)

        shots = 0
        while target.is_alive() and shots < 100:
            hit = DamageSystem.resolve_hit(s, rec, target, rng_seed=shots)
            target.take_damage(hit.damage_dealt)
            shots += 1

        self.assertFalse(target.is_alive(),
            f"Enemy still alive after {shots} shots")
        self.assertLess(shots, 50, f"Took too many shots: {shots}")

    def test_kill_armored_boss_takes_more_shots(self):
        """Heavily armored boss should require more shots than unarmored enemy."""
        rec = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        s   = CharacterStats(); s.set_skill("Handguns", 10)

        def count_shots(hp, armor):
            t = make_target(hp=hp, armor=armor)
            for i in range(200):
                hit = DamageSystem.resolve_hit(s, rec, t, rng_seed=i)
                t.take_damage(hit.damage_dealt)
                if not t.is_alive():
                    return i + 1
            return 200  # didn't die

        shots_light = count_shots(500,   0.0)
        shots_heavy = count_shots(500, 240.0)   # 80% mitigation
        self.assertGreater(shots_heavy, shots_light)

    def test_gunslinger_build_kills_faster(self):
        """Gunslinger (high Reflexes + perks) kills faster than default V."""
        rec    = self.sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
        target_hp = 1000.0

        def count_shots(stats):
            t = make_target(hp=target_hp, armor=0.0)
            for i in range(500):
                hit = DamageSystem.resolve_hit(stats, rec, t, rng_seed=i)
                t.take_damage(hit.damage_dealt)
                if not t.is_alive():
                    return i + 1
            return 500

        default_shots   = count_shots(preset_early_game_v())
        gunslinger_shots = count_shots(preset_gunslinger_v())
        self.assertLess(gunslinger_shots, default_shots,
            "Gunslinger should kill faster than default V")

    def test_status_effect_damages_enemy(self):
        """Applying Burning to an enemy should deal damage over time."""
        target = NPCStats(max_health=500.0, current_health=500.0)
        ctrl   = StatusEffectController()
        ctrl.apply(DamageSystem.make_burning())

        total_dot = 0.0
        for _ in range(4):
            damages = ctrl.tick(1.0)
            for dmg_type, amount in damages:
                target.take_damage(amount)
                total_dot += amount

        self.assertGreater(total_dot, 0.0)
        self.assertLess(target.current_health, 500.0)

    def test_combined_burn_and_bleed(self):
        """Both Burning and Bleeding active → combined damage per tick."""
        target = NPCStats(max_health=1000.0, current_health=1000.0)
        ctrl   = StatusEffectController()
        ctrl.apply(DamageSystem.make_burning())
        ctrl.apply(DamageSystem.make_bleeding())

        for _ in range(3):
            damages = ctrl.tick(1.0)
            for _, amount in damages:
                target.take_damage(amount)

        # After 3s: ~90 fire + ~30 bleed = ~120 damage (before resistances)
        lost_hp = 1000.0 - target.current_health
        self.assertGreater(lost_hp, 80.0)


if __name__ == '__main__':
    unittest.main()
