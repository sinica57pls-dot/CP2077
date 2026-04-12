"""
TweakDB System Tests
====================

Validates that the TweakDB simulation matches the real CP2077 TweakDB:
  - FNV-1a hashing produces known-good values
  - Record lookup returns correct types and stat values
  - GetFlat / SetFlat API works correctly
  - Override system doesn't mutate the base record
  - Weapon DPS = damagePerHit × attacksPerSecond  (game contract)
  - All seeded records have required flats

Run:
    python tests/run_tests.py
    python -m unittest tests.mods.test_tweakdb -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation, TweakDB, TweakDBID,
    WeaponRecord, ArmorRecord, CyberwareRecord, PerkRecord,
    gamedataDamageType, gamedataQuality, gamedataWeaponEvolution,
    gamedataItemType, gamedataCyberwareType,
)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 1: TweakDBID hashing
# ════════════════════════════════════════════════════════════════════════════

class TestTweakDBID(unittest.TestCase):

    def test_empty_path_is_invalid(self):
        tid = TweakDBID("")
        self.assertFalse(tid.IsValid())

    def test_nonempty_path_is_valid(self):
        tid = TweakDBID("Items.Preset_Yukimura_Default")
        self.assertTrue(tid.IsValid())

    def test_same_path_same_hash(self):
        a = TweakDBID("Items.Preset_Yukimura_Default")
        b = TweakDBID("Items.Preset_Yukimura_Default")
        self.assertEqual(a, b)

    def test_different_paths_different_hashes(self):
        a = TweakDBID("Items.Preset_Yukimura_Default")
        b = TweakDBID("Items.Preset_Revolver_Default")
        self.assertNotEqual(a, b)

    def test_case_insensitive(self):
        """TweakDB paths are case-insensitive in the real engine."""
        a = TweakDBID("Items.Preset_Yukimura_Default")
        b = TweakDBID("items.preset_yukimura_default")
        self.assertEqual(a, b)

    def test_string_equality(self):
        tid = TweakDBID("Items.Preset_Yukimura_Default")
        self.assertEqual(tid, "Items.Preset_Yukimura_Default")

    def test_hash_stability(self):
        """Same path must always produce the same 64-bit hash value."""
        tid = TweakDBID("Items.MaxDOC")
        # Known FNV-1a 64-bit hash of "items.maxdoc" (lower-cased)
        # We just verify it's deterministic across calls.
        self.assertEqual(tid.GetHash(), TweakDBID("Items.MaxDOC").GetHash())

    def test_fnv_known_value(self):
        """FNV-1a 64-bit of empty string = 14695981039346656037."""
        from engine.tweakdb import _fnv1a_64
        self.assertEqual(_fnv1a_64(""), 14695981039346656037)

    def test_usable_as_dict_key(self):
        d = {}
        tid = TweakDBID("Items.MaxDOC")
        d[tid] = 42
        self.assertEqual(d[TweakDBID("Items.MaxDOC")], 42)

    def test_repr(self):
        tid = TweakDBID("Perks.Invincible")
        self.assertIn("Perks.Invincible", repr(tid))


# ════════════════════════════════════════════════════════════════════════════
#  Suite 2: TweakDB record lookup
# ════════════════════════════════════════════════════════════════════════════

class TestTweakDBLookup(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.db  = self.sim.tweakdb

    def tearDown(self):
        self.sim.teardown()

    # ── Weapons ──────────────────────────────────────────────────────────────

    def test_unity_pistol_exists(self):
        rec = self.db.GetRecord("Items.Preset_Yukimura_Default")
        self.assertIsNotNone(rec)

    def test_unity_pistol_dps_matches_formula(self):
        """DPS must equal damagePerHit × attacksPerSecond (game contract)."""
        rec = self.db.GetRecord("Items.Preset_Yukimura_Default")
        dmg = rec.GetFlat("damagePerHit")
        spd = rec.GetFlat("attacksPerSecond")
        dps = rec.GetFlat("DPS")
        self.assertAlmostEqual(dps, dmg * spd, delta=0.1)

    def test_unity_pistol_is_power(self):
        rec = self.db.GetRecord("Items.Preset_Yukimura_Default")
        self.assertEqual(rec.GetFlat("evolution"), gamedataWeaponEvolution.Power)

    def test_unity_pistol_item_type(self):
        rec = self.db.GetRecord("Items.Preset_Yukimura_Default")
        self.assertEqual(rec.GetFlat("itemType"), gamedataItemType.Wea_Pistol)

    def test_unity_pistol_physical_damage(self):
        rec = self.db.GetRecord("Items.Preset_Yukimura_Default")
        self.assertEqual(rec.GetFlat("damageType"), gamedataDamageType.Physical)

    def test_malorian_is_iconic(self):
        """Malorian Arms (Johnny's gun) must be marked iconic."""
        rec = self.db.GetRecord("Items.Preset_Revolver_Pirate")
        self.assertTrue(rec.GetFlat("iconic"))

    def test_malorian_is_legendary(self):
        rec = self.db.GetRecord("Items.Preset_Revolver_Pirate")
        self.assertEqual(rec.GetFlat("quality"), gamedataQuality.Legendary)

    def test_sniper_has_long_range(self):
        rec = self.db.GetRecord("Items.Preset_SniperRifle_Default")
        self.assertGreaterEqual(rec.GetFlat("range"), 80.0)

    def test_shotgun_more_damage_than_pistol(self):
        """Shotguns hit harder per shot than pistols (fewer shots, more impact)."""
        pistol  = self.db.GetRecord("Items.Preset_Yukimura_Default")
        shotgun = self.db.GetRecord("Items.Preset_Shotgun_Default")
        self.assertGreater(shotgun.GetFlat("damagePerHit"),
                           pistol.GetFlat("damagePerHit"))

    def test_all_dps_formula_correct(self):
        """Every weapon record must satisfy DPS = dmg × speed."""
        weapon_ids = [
            "Items.Preset_Yukimura_Default",
            "Items.Preset_Budget_Pistol",
            "Items.Preset_Revolver_Default",
            "Items.Preset_Revolver_Pirate",
            "Items.Preset_Apparition" if False else "Items.Preset_Lexington_Royce",
            "Items.Preset_SMG_Default",
            "Items.Preset_SMG_3rd",
            "Items.Preset_Shotgun_Default",
            "Items.Preset_ShotgunDual_Default",
            "Items.Preset_SniperRifle_Default",
            "Items.Preset_SniperRifle_Tech",
            "Items.Preset_Katana_Default",
            "Items.Preset_Katana_Ninja",
        ]
        for wid in weapon_ids:
            with self.subTest(weapon=wid):
                rec = self.db.GetRecord(wid)
                self.assertIsNotNone(rec, f"Missing record: {wid}")
                dmg = rec.GetFlat("damagePerHit")
                spd = rec.GetFlat("attacksPerSecond")
                dps = rec.GetFlat("DPS")
                self.assertAlmostEqual(dps, dmg * spd, delta=1.0,
                    msg=f"{wid}: DPS={dps} ≠ {dmg}×{spd}={dmg*spd}")

    # ── Armor ────────────────────────────────────────────────────────────────

    def test_heavy_armor_more_than_light(self):
        light = self.db.GetRecord("Items.Preset_LightLeather_01")
        heavy = self.db.GetRecord("Items.Preset_HeavyArasaka_01")
        self.assertGreater(heavy.GetFlat("armorValue"),
                           light.GetFlat("armorValue"))

    # ── Cyberware ────────────────────────────────────────────────────────────

    def test_sandevistan_exists(self):
        rec = self.db.GetRecord(
            "Items.OperatingSystemModule_Sandevistan_Legendary")
        self.assertIsNotNone(rec)

    def test_sandevistan_is_legendary(self):
        rec = self.db.GetRecord(
            "Items.OperatingSystemModule_Sandevistan_Legendary")
        self.assertEqual(rec.GetFlat("quality"), gamedataQuality.Legendary)

    def test_sandevistan_time_dilation(self):
        """Sandy must slow time to ≤30% (factor ≤ 0.30)."""
        rec = self.db.GetRecord(
            "Items.OperatingSystemModule_Sandevistan_Legendary")
        self.assertLessEqual(rec.GetFlat("timeDilationFactor"), 0.30)

    def test_sandevistan_has_cooldown(self):
        rec = self.db.GetRecord(
            "Items.OperatingSystemModule_Sandevistan_Legendary")
        self.assertGreater(rec.GetFlat("cooldown"), 0.0)

    def test_mantis_blades_arm_type(self):
        rec = self.db.GetRecord("Items.MantisBlades")
        self.assertEqual(rec.GetFlat("cyberwareType"),
                         gamedataCyberwareType.ArmsCyberware)

    def test_mantis_blades_armor_penetration(self):
        """Mantis Blades penetrate at least 40% of enemy armor."""
        rec = self.db.GetRecord("Items.MantisBlades")
        self.assertGreaterEqual(rec.GetFlat("armorPenetration"), 0.40)

    # ── Perks ────────────────────────────────────────────────────────────────

    def test_invincible_perk_exists(self):
        rec = self.db.GetRecord("Perks.Invincible")
        self.assertIsNotNone(rec)

    def test_invincible_is_body_tree(self):
        rec = self.db.GetRecord("Perks.Invincible")
        self.assertEqual(rec.GetFlat("attribute"), "Strength")

    def test_assassin_perk_damage_bonus(self):
        """Assassin perk gives +10% bonus to unaware enemies."""
        rec = self.db.GetRecord("Perks.Assassin")
        self.assertAlmostEqual(rec.GetFlat("unwareDamageBonus"), 0.10)

    def test_cold_blood_perk_max_stacks(self):
        rec = self.db.GetRecord("Perks.ColdBloodPerk")
        self.assertEqual(rec.GetFlat("maxStacks"), 5)

    # ── Consumables ──────────────────────────────────────────────────────────

    def test_maxdoc_exists(self):
        rec = self.db.GetRecord("Items.MaxDOC")
        self.assertIsNotNone(rec)

    def test_maxdoc_instant_heal(self):
        """MaxDoc Mk.1 heals immediately (no duration)."""
        rec = self.db.GetRecord("Items.MaxDOC")
        self.assertEqual(rec.GetFlat("duration"), 0.0)
        self.assertGreater(rec.GetFlat("healthRestore"), 0.0)

    def test_bigger_maxdoc_heals_more(self):
        mk1 = self.db.GetRecord("Items.MaxDOC")
        mk3 = self.db.GetRecord("Items.MaxDOC_3")
        self.assertGreater(mk3.GetFlat("healthRestore"),
                           mk1.GetFlat("healthRestore"))


# ════════════════════════════════════════════════════════════════════════════
#  Suite 3: GetFlat / SetFlat / Override API
# ════════════════════════════════════════════════════════════════════════════

class TestTweakDBOverride(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.db  = self.sim.tweakdb

    def tearDown(self):
        self.sim.teardown()

    def test_getflat_dotpath(self):
        """GetFlat should accept 'Record.Path.FlatName' string."""
        dps = self.db.GetFlat("Items.Preset_Yukimura_Default.DPS")
        self.assertIsNotNone(dps)
        self.assertGreater(dps, 0)

    def test_setflat_overrides_value(self):
        """SetFlat (TweakXL-style) should override a flat for the session."""
        original = self.db.GetFlat("Items.Preset_Yukimura_Default.damagePerHit")
        self.db.SetFlat("Items.Preset_Yukimura_Default.damagePerHit", 9999.0)
        overridden = self.db.GetFlat("Items.Preset_Yukimura_Default.damagePerHit")
        self.assertEqual(overridden, 9999.0)
        self.assertNotEqual(overridden, original)

    def test_setflat_does_not_mutate_base_record(self):
        """Override must not change the base record object."""
        base_rec = self.db.GetRecord("Items.Preset_Yukimura_Default")
        original_dmg = base_rec.GetFlat("damagePerHit")
        self.db.SetFlat("Items.Preset_Yukimura_Default.damagePerHit", 1.0)
        # Base record still has original value (override is separate)
        self.assertEqual(base_rec.GetFlat("damagePerHit"), original_dmg)

    def test_getrecord_returns_override_copy(self):
        """GetRecord should reflect active overrides."""
        self.db.SetFlat("Items.Preset_Yukimura_Default.damagePerHit", 500.0)
        rec = self.db.GetRecord("Items.Preset_Yukimura_Default")
        self.assertEqual(rec.GetFlat("damagePerHit"), 500.0)

    def test_setflat_returns_false_for_unknown_record(self):
        result = self.db.SetFlat("Items.DoesNotExist.damagePerHit", 1.0)
        self.assertFalse(result)

    def test_two_simulations_have_independent_tweakdbs(self):
        """Each GameSimulation gets a fresh TweakDB -- no bleed between tests."""
        sim2 = GameSimulation()
        try:
            sim2.tweakdb.SetFlat(
                "Items.Preset_Yukimura_Default.damagePerHit", 1.0)
            # Original sim should NOT see this override
            original = self.sim.tweakdb.GetFlat(
                "Items.Preset_Yukimura_Default.damagePerHit")
            sim2_val  = sim2.tweakdb.GetFlat(
                "Items.Preset_Yukimura_Default.damagePerHit")
            self.assertNotEqual(original, sim2_val)
        finally:
            sim2.teardown()

    def test_create_record_adds_new_entry(self):
        """CreateRecord should allow adding modded items (TweakXL pattern)."""
        from engine import WeaponRecord, gamedataDamageType, gamedataItemType
        new_rec = WeaponRecord(
            "Items.MyModdedWeapon",
            damage_per_hit=999.0,
            attacks_per_sec=1.0,
        )
        created = self.db.CreateRecord(
            TweakDBID("Items.MyModdedWeapon"), new_rec)
        self.assertTrue(created)
        fetched = self.db.GetRecord("Items.MyModdedWeapon")
        self.assertIsNotNone(fetched)
        self.assertAlmostEqual(fetched.GetFlat("damagePerHit"), 999.0)

    def test_create_record_fails_if_exists(self):
        from engine import WeaponRecord
        new_rec = WeaponRecord("Items.Preset_Yukimura_Default",
                               damage_per_hit=1.0, attacks_per_sec=1.0)
        result = self.db.CreateRecord(
            TweakDBID("Items.Preset_Yukimura_Default"), new_rec)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
