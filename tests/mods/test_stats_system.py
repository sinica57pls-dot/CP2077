"""
Stats System Tests
==================

Validates that all CP2077 stat calculations match real-game observed values.

Calibration checkpoints (from community testing data):
  - Default V (Level 1, Body 3, no perks): ~130 HP
  - Body 10, Level 10:  ~330 HP
  - Body 20, Level 50, Athletics 20, Invincible perk: ~1200 HP  (range 1100–1300)
  - Default Crit Chance (Reflexes 3):   ~6%
  - Reflexes 20 Crit Chance:            ~31.5%
  - Default Cool 3, Crit Damage:        60%
  - Cool 20, DeadlyPrecision perk:      ~170%
  - Intelligence 5 RAM:                 ~15
  - Intelligence 20 RAM:                ~45

Run:
    python tests/run_tests.py
    python -m unittest tests.mods.test_stats_system -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation, CharacterStats, NPCStats, StatsSystem,
    StatModifier, StatModifierType, gamedataStatType,
    preset_early_game_v, preset_netrunner_v,
    preset_street_samurai_v, preset_gunslinger_v,
)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 1: Base attributes & health
# ════════════════════════════════════════════════════════════════════════════

class TestHealthFormula(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_default_v_health_range(self):
        """Default V (Level 1, Body 3) health should be ~130 HP."""
        s = preset_early_game_v()
        hp = StatsSystem.compute_max_health(s)
        self.assertGreater(hp, 100, "HP too low for default V")
        self.assertLess(hp, 180, "HP too high for default V")

    def test_body_increases_hp(self):
        """More Body → more HP."""
        s_low  = CharacterStats(); s_low.set_attribute("Body", 3)
        s_high = CharacterStats(); s_high.set_attribute("Body", 20)
        self.assertGreater(StatsSystem.compute_max_health(s_high),
                           StatsSystem.compute_max_health(s_low))

    def test_level_increases_hp(self):
        """Higher level → more HP."""
        s = CharacterStats()
        s.level = 1
        hp1 = StatsSystem.compute_max_health(s)
        s.level = 50
        hp50 = StatsSystem.compute_max_health(s)
        self.assertGreater(hp50, hp1)

    def test_body10_level10_hp_range(self):
        s = CharacterStats()
        s.set_attribute("Body", 10)
        s.level = 10
        hp = StatsSystem.compute_max_health(s)
        self.assertGreater(hp, 250, f"Body=10 Lvl=10 HP too low: {hp}")
        self.assertLess(hp, 450, f"Body=10 Lvl=10 HP too high: {hp}")

    def test_maxed_body_build_hp(self):
        """Body 20, Level 50, Athletics 20, Invincible perk → ~1100-1300 HP."""
        s = CharacterStats()
        s.set_attribute("Body", 20)
        s.level = 50
        s.set_skill("Athletics", 20)
        s.add_perk("Perks.Invincible")
        hp = StatsSystem.compute_max_health(s)
        self.assertGreater(hp, 1000, f"Maxed Body build HP too low: {hp}")
        self.assertLess(hp, 1500, f"Maxed Body build HP too high: {hp}")

    def test_invincible_perk_increases_hp_by_25pct(self):
        """Invincible gives exactly 25% more HP."""
        s = CharacterStats(); s.level = 20
        hp_without = StatsSystem.compute_max_health(s)
        s.add_perk("Perks.Invincible")
        hp_with = StatsSystem.compute_max_health(s)
        ratio = hp_with / hp_without
        self.assertAlmostEqual(ratio, 1.25, delta=0.01)

    def test_athletics_20_multiplier(self):
        """Athletics 20 gives 25% more HP (vs Athletics 1)."""
        s_base = CharacterStats(); s_base.set_skill("Athletics", 1)
        s_high = CharacterStats(); s_high.set_skill("Athletics", 20)
        ratio = StatsSystem.compute_max_health(s_high) / StatsSystem.compute_max_health(s_base)
        self.assertAlmostEqual(ratio, 1.25, delta=0.02)

    def test_athletics_10_multiplier(self):
        """Athletics 10 gives exactly 10% more HP."""
        s_base = CharacterStats()
        s_ath10 = CharacterStats(); s_ath10.set_skill("Athletics", 10)
        ratio = StatsSystem.compute_max_health(s_ath10) / StatsSystem.compute_max_health(s_base)
        self.assertAlmostEqual(ratio, 1.10, delta=0.02)

    def test_gear_additive_modifier(self):
        """Gear with +50 HP should add exactly 50 to MaxHealth."""
        s = CharacterStats()
        base = StatsSystem.compute_max_health(s)
        s.add_modifier(gamedataStatType.MaxHealth, 50.0, source="gear")
        self.assertAlmostEqual(StatsSystem.compute_max_health(s), base + 50.0, delta=0.1)

    def test_multiple_additive_modifiers_stack(self):
        s = CharacterStats()
        base = StatsSystem.compute_max_health(s)
        s.add_modifier(gamedataStatType.MaxHealth, 30.0, source="item1")
        s.add_modifier(gamedataStatType.MaxHealth, 20.0, source="item2")
        self.assertAlmostEqual(StatsSystem.compute_max_health(s), base + 50.0, delta=0.1)

    def test_remove_modifiers_by_source(self):
        s = CharacterStats()
        base = StatsSystem.compute_max_health(s)
        s.add_modifier(gamedataStatType.MaxHealth, 100.0, source="cyberware")
        s.remove_modifiers_by_source("cyberware")
        self.assertAlmostEqual(StatsSystem.compute_max_health(s), base, delta=0.1)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 2: Stamina
# ════════════════════════════════════════════════════════════════════════════

class TestStaminaFormula(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_default_stamina_at_least_100(self):
        s = CharacterStats()
        self.assertGreaterEqual(StatsSystem.compute_max_stamina(s), 100.0)

    def test_body_increases_stamina(self):
        s_low  = CharacterStats(); s_low.set_attribute("Body", 1)
        s_high = CharacterStats(); s_high.set_attribute("Body", 20)
        self.assertGreater(StatsSystem.compute_max_stamina(s_high),
                           StatsSystem.compute_max_stamina(s_low))

    def test_athletics_20_bonus(self):
        """Athletics 20 adds +20% stamina."""
        s_base = CharacterStats()
        s_high = CharacterStats(); s_high.set_skill("Athletics", 20)
        self.assertAlmostEqual(
            StatsSystem.compute_max_stamina(s_high) /
            StatsSystem.compute_max_stamina(s_base),
            1.20, delta=0.02)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 3: RAM (netrunner resource)
# ════════════════════════════════════════════════════════════════════════════

class TestRAMFormula(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_default_intelligence_has_some_ram(self):
        s = CharacterStats()
        self.assertGreater(StatsSystem.compute_max_ram(s), 0)

    def test_intelligence_scales_ram(self):
        s5  = CharacterStats(); s5.set_attribute("Intelligence", 5)
        s20 = CharacterStats(); s20.set_attribute("Intelligence", 20)
        self.assertGreater(StatsSystem.compute_max_ram(s20),
                           StatsSystem.compute_max_ram(s5))

    def test_intelligence_5_ram_range(self):
        s = CharacterStats(); s.set_attribute("Intelligence", 5)
        ram = StatsSystem.compute_max_ram(s)
        self.assertGreater(ram, 10)
        self.assertLess(ram, 25)

    def test_intelligence_20_ram_range(self):
        s = CharacterStats(); s.set_attribute("Intelligence", 20)
        ram = StatsSystem.compute_max_ram(s)
        self.assertGreater(ram, 40)
        self.assertLess(ram, 55)

    def test_breach_protocol_lvl20_adds_3_ram(self):
        s_base = CharacterStats()
        s_bp   = CharacterStats(); s_bp.set_skill("BreachProtocol", 20)
        diff = StatsSystem.compute_max_ram(s_bp) - StatsSystem.compute_max_ram(s_base)
        self.assertEqual(diff, 3)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 4: Crit Chance
# ════════════════════════════════════════════════════════════════════════════

class TestCritChance(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_default_reflexes_crit_chance(self):
        """Default V (Reflexes 3) should have ~3-8% crit chance."""
        s = CharacterStats()
        cc = StatsSystem.compute_crit_chance(s)
        self.assertGreaterEqual(cc, 3.0)
        self.assertLessEqual(cc, 10.0)

    def test_reflexes_20_crit_chance(self):
        """Reflexes 20 should give ~28-35% crit chance."""
        s = CharacterStats(); s.set_attribute("Reflexes", 20)
        cc = StatsSystem.compute_crit_chance(s)
        self.assertGreater(cc, 25.0)
        self.assertLess(cc, 40.0)

    def test_cold_blood_stacks_add_crit_chance(self):
        """ColdBlood perk: each stack adds 3% crit chance."""
        s = CharacterStats()
        s.add_perk("Perks.ColdBloodPerk")
        s.cold_blood_stacks = 0
        cc0 = StatsSystem.compute_crit_chance(s)
        s.cold_blood_stacks = 5
        cc5 = StatsSystem.compute_crit_chance(s)
        self.assertAlmostEqual(cc5 - cc0, 15.0, delta=0.01)  # 5 × 3%

    def test_crit_chance_caps_at_100(self):
        """Crit chance should never exceed 100%."""
        s = CharacterStats()
        s.set_attribute("Reflexes", 20)
        s.add_perk("Perks.ColdBloodPerk")
        s.cold_blood_stacks = 5
        s.add_modifier(gamedataStatType.CritChance, 200.0)  # absurd modifier
        cc = StatsSystem.compute_crit_chance(s)
        self.assertLessEqual(cc, 100.0)

    def test_more_reflexes_more_crit(self):
        s_low  = CharacterStats(); s_low.set_attribute("Reflexes", 1)
        s_high = CharacterStats(); s_high.set_attribute("Reflexes", 20)
        self.assertGreater(StatsSystem.compute_crit_chance(s_high),
                           StatsSystem.compute_crit_chance(s_low))


# ════════════════════════════════════════════════════════════════════════════
#  Suite 5: Crit Damage
# ════════════════════════════════════════════════════════════════════════════

class TestCritDamage(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_default_cool_crit_damage(self):
        """Default V (Cool 3) should have ~60% crit damage bonus."""
        s = CharacterStats()
        cd = StatsSystem.compute_crit_damage(s)
        self.assertAlmostEqual(cd, 60.0, delta=5.0)

    def test_cool_20_crit_damage(self):
        """Cool 20 should give ~145% crit damage bonus."""
        s = CharacterStats(); s.set_attribute("Cool", 20)
        cd = StatsSystem.compute_crit_damage(s)
        self.assertGreater(cd, 130.0)
        self.assertLess(cd, 160.0)

    def test_deadly_precision_adds_crit_damage(self):
        """DeadlyPrecision perk adds +25% crit damage."""
        s = CharacterStats()
        cd_without = StatsSystem.compute_crit_damage(s)
        s.add_perk("Perks.DeadlyPrecision")
        cd_with = StatsSystem.compute_crit_damage(s)
        self.assertAlmostEqual(cd_with - cd_without, 25.0, delta=0.1)

    def test_gunslinger_build_crit_damage(self):
        """Gunslinger build (Cool 20, DeadlyPrecision) → ~170% crit damage."""
        s = preset_gunslinger_v()
        cd = StatsSystem.compute_crit_damage(s)
        self.assertGreater(cd, 150.0)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 6: Armor
# ════════════════════════════════════════════════════════════════════════════

class TestArmor(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_no_gear_no_armor(self):
        """Without gear or perks, base armor = 0."""
        s = CharacterStats()
        self.assertEqual(StatsSystem.compute_armor(s), 0.0)

    def test_gear_adds_armor(self):
        s = CharacterStats()
        s.add_modifier(gamedataStatType.Armor, 200.0, source="subdermal")
        self.assertAlmostEqual(StatsSystem.compute_armor(s), 200.0)

    def test_juggernaut_perk_adds_armor_per_athletics(self):
        """Juggernaut: +5 armor per Athletics level."""
        s = CharacterStats(); s.set_skill("Athletics", 10)
        s.add_perk("Perks.Juggernaut")
        armor = StatsSystem.compute_armor(s)
        self.assertAlmostEqual(armor, 50.0, delta=1.0)  # 5 × 10

    def test_juggernaut_with_gear(self):
        s = CharacterStats()
        s.set_skill("Athletics", 20)
        s.add_perk("Perks.Juggernaut")
        s.add_modifier(gamedataStatType.Armor, 200.0, source="gear")
        armor = StatsSystem.compute_armor(s)
        self.assertAlmostEqual(armor, 300.0, delta=1.0)  # 200gear + 100jugg


# ════════════════════════════════════════════════════════════════════════════
#  Suite 7: Skill damage bonuses
# ════════════════════════════════════════════════════════════════════════════

class TestSkillDamageBonuses(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_handguns_skill1_no_bonus(self):
        s = CharacterStats(); s.set_skill("Handguns", 1)
        self.assertEqual(StatsSystem.compute_handgun_damage_bonus(s), 0.0)

    def test_handguns_skill20_bonus(self):
        """Handguns 20 gives 38% bonus."""
        s = CharacterStats(); s.set_skill("Handguns", 20)
        bonus = StatsSystem.compute_handgun_damage_bonus(s)
        self.assertAlmostEqual(bonus, 0.38, delta=0.01)

    def test_assault_skill20_bonus(self):
        s = CharacterStats(); s.set_skill("Assault", 20)
        bonus = StatsSystem.compute_assault_damage_bonus(s)
        self.assertAlmostEqual(bonus, 0.38, delta=0.01)

    def test_stealth_bonus_with_assassin_perk(self):
        """Assassin perk gives +10% bonus vs unaware enemies."""
        s = CharacterStats(); s.add_perk("Perks.Assassin")
        bonus = StatsSystem.compute_stealth_damage_bonus(s)
        self.assertAlmostEqual(bonus, 0.10)

    def test_stealth_bonus_without_perk(self):
        s = CharacterStats()   # no Assassin perk
        self.assertEqual(StatsSystem.compute_stealth_damage_bonus(s), 0.0)

    def test_quickhack_bonus_scales_with_intelligence(self):
        s5  = CharacterStats(); s5.set_attribute("Intelligence", 5)
        s20 = CharacterStats(); s20.set_attribute("Intelligence", 20)
        self.assertGreater(
            StatsSystem.compute_quickhack_damage_bonus(s20),
            StatsSystem.compute_quickhack_damage_bonus(s5))


# ════════════════════════════════════════════════════════════════════════════
#  Suite 8: Preset builds sanity checks
# ════════════════════════════════════════════════════════════════════════════

class TestPresetBuilds(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_netrunner_high_ram(self):
        s = preset_netrunner_v()
        self.assertGreater(StatsSystem.compute_max_ram(s), 40)

    def test_netrunner_high_qh_bonus(self):
        s = preset_netrunner_v()
        self.assertGreater(StatsSystem.compute_quickhack_damage_bonus(s), 0.5)

    def test_street_samurai_high_hp(self):
        s = preset_street_samurai_v()
        self.assertGreater(StatsSystem.compute_max_health(s), 400)

    def test_street_samurai_armor(self):
        """Street samurai with SubdermalArmor applied should have ≥200 armor."""
        s = preset_street_samurai_v()
        self.assertGreaterEqual(StatsSystem.compute_armor(s), 200.0)

    def test_gunslinger_crit_chance(self):
        s = preset_gunslinger_v()
        cc = StatsSystem.compute_crit_chance(s)
        # Gunslinger: Reflexes 20 + Cold Blood 5 stacks (+15%)
        self.assertGreater(cc, 40.0)

    def test_gunslinger_crit_damage(self):
        s = preset_gunslinger_v()
        self.assertGreater(StatsSystem.compute_crit_damage(s), 150.0)

    def test_snapshot_has_all_keys(self):
        s = CharacterStats()
        snap = StatsSystem.snapshot(s)
        expected_keys = [
            "level", "Body", "Reflexes", "MaxHealth", "MaxStamina",
            "MaxRAM", "Armor", "CritChance_%", "CritDamage_%",
            "HeadshotMult", "HandgunBonus_%",
        ]
        for k in expected_keys:
            self.assertIn(k, snap, f"Snapshot missing key: {k!r}")


# ════════════════════════════════════════════════════════════════════════════
#  Suite 9: NPCStats
# ════════════════════════════════════════════════════════════════════════════

class TestNPCStats(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_npc_starts_at_full_health(self):
        npc = NPCStats(max_health=300.0, current_health=300.0)
        self.assertEqual(npc.current_health, 300.0)
        self.assertTrue(npc.is_alive())

    def test_take_damage_reduces_hp(self):
        npc = NPCStats(max_health=300.0, current_health=300.0)
        npc.take_damage(100.0)
        self.assertAlmostEqual(npc.current_health, 200.0)

    def test_take_damage_cannot_below_zero(self):
        npc = NPCStats(max_health=100.0, current_health=100.0)
        npc.take_damage(999.0)
        self.assertGreaterEqual(npc.current_health, 0.0)
        self.assertFalse(npc.is_alive())

    def test_heal_restores_hp(self):
        npc = NPCStats(max_health=200.0, current_health=100.0)
        restored = npc.heal(50.0)
        self.assertAlmostEqual(restored, 50.0)
        self.assertAlmostEqual(npc.current_health, 150.0)

    def test_heal_cannot_exceed_max(self):
        npc = NPCStats(max_health=200.0, current_health=190.0)
        npc.heal(100.0)
        self.assertAlmostEqual(npc.current_health, 200.0)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 10: Attribute clamping & validation
# ════════════════════════════════════════════════════════════════════════════

class TestAttributeClamping(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()

    def tearDown(self):
        self.sim.teardown()

    def test_attribute_clamped_to_min(self):
        s = CharacterStats()
        s.set_attribute("Body", 0)   # below minimum
        self.assertEqual(s.Body, 1)

    def test_attribute_clamped_to_max(self):
        s = CharacterStats()
        s.set_attribute("Body", 25)  # above maximum
        self.assertEqual(s.Body, 20)

    def test_skill_clamped_to_min(self):
        s = CharacterStats()
        s.set_skill("Handguns", -5)
        self.assertEqual(s.get_skill("Handguns"), 1)

    def test_skill_clamped_to_max(self):
        s = CharacterStats()
        s.set_skill("Handguns", 99)
        self.assertEqual(s.get_skill("Handguns"), 20)

    def test_unknown_attribute_raises(self):
        s = CharacterStats()
        with self.assertRaises(ValueError):
            s.set_attribute("Charisma", 10)

    def test_unknown_skill_raises(self):
        s = CharacterStats()
        with self.assertRaises(ValueError):
            s.set_skill("Luck", 10)

    def test_add_perk_deduplication(self):
        s = CharacterStats()
        s.add_perk("Perks.Invincible", level=1)
        s.add_perk("Perks.Invincible", level=2)   # update, not duplicate
        count = sum(1 for p in s._perks if p.perk_id == "Perks.Invincible")
        self.assertEqual(count, 1)

    def test_perk_level_updates(self):
        s = CharacterStats()
        s.add_perk("Perks.Invincible", level=1)
        s.add_perk("Perks.Invincible", level=2)
        self.assertEqual(s.perk_level("Perks.Invincible"), 2)


if __name__ == '__main__':
    unittest.main()
