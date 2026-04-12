"""
Inventory, Equipment & Quest System Tests
==========================================

Validates:
  - TransactionSystem  (add / remove / query / transfer items)
  - EquipmentSystem    (equip / unequip / slot management)
  - StreetCredSystem   (cred progression, XP thresholds)
  - QuestSystem        (facts, phase execution, journal)

All behaviour should match the real CP2077 game contract:
  - Items stack by TweakDBID for common items; unique items have unique IDs
  - Equipping always requires the item to be in inventory
  - Eddies are a special tracked currency
  - Quest facts are case-insensitive integer counters
  - Phase execution is deterministic and matches FactCheck conditions

Run:
    python tests/run_tests.py
    python -m unittest tests.mods.test_inventory_system -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation,
    ItemID, ItemData, EquipmentSlot,
    TransactionSystem, EquipmentSystem, StreetCredSystem,
    QuestSystem, QuestPhase, QuestNode, QuestNodeType, QuestNodeResult,
    FactManager, JournalManager, ObjectiveStatus,
    TweakDB, TweakDBID,
)


TX  = "player"     # entity_id used in most tests
NPC = "vendor_01"  # vendor entity for transfer tests


# ════════════════════════════════════════════════════════════════════════════
#  Suite 1: TransactionSystem -- item management
# ════════════════════════════════════════════════════════════════════════════

class TestTransactionSystem(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.tx  = self.sim.transaction

    def tearDown(self):
        self.sim.teardown()

    # ── Add / query ───────────────────────────────────────────────────────────

    def test_add_item_has_item(self):
        item_id = ItemID.CreateQuery("Items.MaxDOC")
        self.tx.AddItemToInventory(TX, item_id, 5)
        self.assertTrue(self.tx.HasItem(TX, item_id))

    def test_empty_inventory_no_item(self):
        item_id = ItemID.CreateQuery("Items.MaxDOC")
        self.assertFalse(self.tx.HasItem(TX, item_id))

    def test_quantity_correct(self):
        item_id = ItemID.CreateQuery("Items.MaxDOC")
        self.tx.AddItemToInventory(TX, item_id, 7)
        self.assertEqual(self.tx.GetItemQuantity(TX, item_id), 7)

    def test_stackable_items_merge(self):
        """Adding the same stackable item twice should merge into one stack."""
        item_id = ItemID.CreateQuery("Items.MaxDOC")
        self.tx.AddItemToInventory(TX, item_id, 3)
        self.tx.AddItemToInventory(TX, item_id, 4)
        self.assertEqual(self.tx.GetItemQuantity(TX, item_id), 7)

    def test_unique_items_do_not_merge(self):
        """Unique items (unique_id != 0) should remain separate."""
        uid1 = ItemID.Create("Items.Preset_Revolver_Pirate")
        uid2 = ItemID.Create("Items.Preset_Revolver_Pirate")
        self.assertNotEqual(uid1.unique_id, uid2.unique_id)

    # ── Remove / spend ────────────────────────────────────────────────────────

    def test_remove_item_reduces_quantity(self):
        item_id = ItemID.CreateQuery("Items.MaxDOC")
        self.tx.AddItemToInventory(TX, item_id, 10)
        self.tx.RemoveItemFromInventory(TX, item_id, 3)
        self.assertEqual(self.tx.GetItemQuantity(TX, item_id), 7)

    def test_remove_all_removes_stack(self):
        item_id = ItemID.CreateQuery("Items.MaxDOC")
        self.tx.AddItemToInventory(TX, item_id, 5)
        self.tx.RemoveItemFromInventory(TX, item_id, 5)
        self.assertFalse(self.tx.HasItem(TX, item_id))

    def test_remove_more_than_owned_returns_false(self):
        item_id = ItemID.CreateQuery("Items.MaxDOC")
        self.tx.AddItemToInventory(TX, item_id, 2)
        result = self.tx.RemoveItemFromInventory(TX, item_id, 10)
        self.assertFalse(result)

    def test_remove_nonexistent_returns_false(self):
        item_id = ItemID.CreateQuery("Items.BounceBack_2")
        result = self.tx.RemoveItemFromInventory(TX, item_id, 1)
        self.assertFalse(result)

    # ── Eddies (currency) ─────────────────────────────────────────────────────

    def test_no_money_at_start(self):
        self.assertEqual(self.tx.GetMoney(TX), 0)

    def test_add_money(self):
        self.tx.AddMoney(TX, 500)
        self.assertEqual(self.tx.GetMoney(TX), 500)

    def test_spend_money_success(self):
        self.tx.AddMoney(TX, 1000)
        result = self.tx.SpendMoney(TX, 300)
        self.assertTrue(result)
        self.assertEqual(self.tx.GetMoney(TX), 700)

    def test_spend_money_insufficient(self):
        self.tx.AddMoney(TX, 100)
        result = self.tx.SpendMoney(TX, 500)
        self.assertFalse(result)
        self.assertEqual(self.tx.GetMoney(TX), 100)   # unchanged

    def test_spend_exact_amount(self):
        self.tx.AddMoney(TX, 250)
        self.tx.SpendMoney(TX, 250)
        self.assertEqual(self.tx.GetMoney(TX), 0)

    # ── Item transfer ─────────────────────────────────────────────────────────

    def test_transfer_item_between_entities(self):
        item_id = ItemID.CreateQuery("Items.MaxDOC")
        self.tx.AddItemToInventory(NPC, item_id, 10)
        self.tx.TransferItem(NPC, TX, item_id, 5)
        self.assertEqual(self.tx.GetItemQuantity(NPC, item_id), 5)
        self.assertEqual(self.tx.GetItemQuantity(TX,  item_id), 5)

    def test_transfer_nonexistent_returns_false(self):
        item_id = ItemID.CreateQuery("Items.SomethingRare")
        result  = self.tx.TransferItem(NPC, TX, item_id, 1)
        self.assertFalse(result)

    # ── GetItemList ───────────────────────────────────────────────────────────

    def test_get_item_list_all(self):
        """GetItemList returns all items regardless of type when type=None."""
        for path in ["Items.MaxDOC", "Items.BounceBack_2", "Items.Alcohol_Generic"]:
            self.tx.AddItemToInventory(TX, ItemID.CreateQuery(path), 1)
        items = self.tx.GetItemList(TX)
        self.assertEqual(len(items), 3)

    # ── GameSimulation helpers ────────────────────────────────────────────────

    def test_sim_give_item_helper(self):
        item_id = self.sim.give_item(TX, "Items.MaxDOC", 3)
        self.assertEqual(self.tx.GetItemQuantity(TX, item_id), 3)

    def test_sim_give_money_helper(self):
        self.sim.give_money(TX, 2500)
        self.assertEqual(self.sim.get_money(TX), 2500)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 2: EquipmentSystem
# ════════════════════════════════════════════════════════════════════════════

class TestEquipmentSystem(unittest.TestCase):

    def setUp(self):
        self.sim  = GameSimulation()
        self.tx   = self.sim.transaction
        self.eq   = self.sim.equipment

    def tearDown(self):
        self.sim.teardown()

    def _add_weapon(self, path: str) -> ItemID:
        rec     = self.sim.tweakdb.GetRecord(path)
        item_id = ItemID.Create(path)
        self.tx.AddItemToInventory(TX, item_id, 1, rec)
        return item_id

    def test_equip_weapon_to_right_hand(self):
        item_id = self._add_weapon("Items.Preset_Yukimura_Default")
        result  = self.eq.EquipItem(TX, item_id, EquipmentSlot.WeaponRight)
        self.assertTrue(result)
        self.assertTrue(self.eq.IsSlotOccupied(TX, EquipmentSlot.WeaponRight))

    def test_equip_requires_item_in_inventory(self):
        """Cannot equip an item that isn't in the inventory."""
        item_id = ItemID.Create("Items.Preset_Yukimura_Default")
        result  = self.eq.EquipItem(TX, item_id, EquipmentSlot.WeaponRight)
        self.assertFalse(result)
        self.assertFalse(self.eq.IsSlotOccupied(TX, EquipmentSlot.WeaponRight))

    def test_get_equipped_weapon(self):
        item_id = self._add_weapon("Items.Preset_Revolver_Pirate")
        self.eq.EquipItem(TX, item_id, EquipmentSlot.WeaponRight)
        weapon = self.eq.GetEquippedWeapon(TX, "right")
        self.assertIsNotNone(weapon)

    def test_iconic_weapon_flagged(self):
        """Malorian Arms 3516 (Johnny's gun) must be iconic."""
        item_id = self._add_weapon("Items.Preset_Revolver_Pirate")
        self.eq.EquipItem(TX, item_id, EquipmentSlot.WeaponRight)
        weapon = self.eq.GetEquippedWeapon(TX, "right")
        self.assertTrue(weapon.is_iconic)

    def test_unequip_slot(self):
        item_id = self._add_weapon("Items.Preset_Yukimura_Default")
        self.eq.EquipItem(TX, item_id, EquipmentSlot.WeaponRight)
        self.eq.UnequipSlot(TX, EquipmentSlot.WeaponRight)
        self.assertFalse(self.eq.IsSlotOccupied(TX, EquipmentSlot.WeaponRight))

    def test_item_still_in_inventory_after_unequip(self):
        """Unequipping should not remove the item from inventory."""
        item_id = self._add_weapon("Items.Preset_Yukimura_Default")
        self.eq.EquipItem(TX, item_id, EquipmentSlot.WeaponRight)
        self.eq.UnequipSlot(TX, EquipmentSlot.WeaponRight)
        self.assertTrue(self.tx.HasItem(TX, item_id))

    def test_total_armor_from_gear(self):
        """Equipped armor should contribute to total armor value."""
        rec_outer = self.sim.tweakdb.GetRecord("Items.Preset_HeavyArasaka_01")
        rec_head  = self.sim.tweakdb.GetRecord("Items.Preset_Neuroblocker_Helmet")

        outer_id = ItemID.Create("Items.Preset_HeavyArasaka_01")
        head_id  = ItemID.Create("Items.Preset_Neuroblocker_Helmet")
        self.tx.AddItemToInventory(TX, outer_id, 1, rec_outer)
        self.tx.AddItemToInventory(TX, head_id,  1, rec_head)
        self.eq.EquipItem(TX, outer_id, EquipmentSlot.OuterChest)
        self.eq.EquipItem(TX, head_id,  EquipmentSlot.Head)

        total_armor = self.eq.GetTotalArmor(TX)
        expected    = (rec_outer.GetFlat("armorValue")
                       + rec_head.GetFlat("armorValue"))
        self.assertAlmostEqual(total_armor, expected, delta=0.5)

    def test_no_armor_equipped_zero_total(self):
        self.assertAlmostEqual(self.eq.GetTotalArmor(TX), 0.0)

    def test_sim_equip_item_helper(self):
        result = self.sim.equip_item(TX, "Items.Preset_Yukimura_Default",
                                     EquipmentSlot.WeaponRight)
        self.assertTrue(result)
        self.assertTrue(self.eq.IsSlotOccupied(TX, EquipmentSlot.WeaponRight))


# ════════════════════════════════════════════════════════════════════════════
#  Suite 3: StreetCredSystem
# ════════════════════════════════════════════════════════════════════════════

class TestStreetCredSystem(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sc  = self.sim.street_cred

    def tearDown(self):
        self.sim.teardown()

    def test_starts_at_zero_xp(self):
        self.assertEqual(self.sc.GetStreetCredPoints(TX), 0)

    def test_starts_at_level_1(self):
        self.assertEqual(self.sc.GetStreetCredLevel(TX), 1)

    def test_add_xp_increases_points(self):
        self.sc.AddStreetCredPoints(TX, 250)
        self.assertEqual(self.sc.GetStreetCredPoints(TX), 250)

    def test_level_2_at_500_xp(self):
        """Street Cred level 2 requires 500 XP."""
        self.sc.AddStreetCredPoints(TX, 500)
        self.assertEqual(self.sc.GetStreetCredLevel(TX), 2)

    def test_level_stays_1_below_500(self):
        self.sc.AddStreetCredPoints(TX, 499)
        self.assertEqual(self.sc.GetStreetCredLevel(TX), 1)

    def test_xp_to_next_level_correct(self):
        """At 0 XP, need 500 to reach level 2."""
        remaining = self.sc.GetXPToNextLevel(TX)
        self.assertEqual(remaining, 500)

    def test_xp_to_next_level_decreases_with_xp(self):
        remaining_0   = self.sc.GetXPToNextLevel(TX)
        self.sc.AddStreetCredPoints(TX, 200)
        remaining_200 = self.sc.GetXPToNextLevel(TX)
        self.assertLess(remaining_200, remaining_0)

    def test_level_caps_at_50(self):
        self.sc.AddStreetCredPoints(TX, 10_000_000)
        self.assertEqual(self.sc.GetStreetCredLevel(TX), 50)

    def test_max_level_xp_to_next_is_zero(self):
        self.sc.AddStreetCredPoints(TX, 10_000_000)
        self.assertEqual(self.sc.GetXPToNextLevel(TX), 0)

    def test_add_negative_xp_ignored(self):
        self.sc.AddStreetCredPoints(TX, 100)
        self.sc.AddStreetCredPoints(TX, -50)
        # Negative deltas should be ignored
        self.assertGreaterEqual(self.sc.GetStreetCredPoints(TX), 100)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 4: FactManager (quest facts)
# ════════════════════════════════════════════════════════════════════════════

class TestFactManager(unittest.TestCase):

    def setUp(self):
        self.sim   = GameSimulation()
        self.facts = self.sim.quests.facts

    def tearDown(self):
        self.sim.teardown()

    def test_unset_fact_returns_0(self):
        self.assertEqual(self.facts.GetFact("any_fact"), 0)

    def test_set_and_get_fact(self):
        self.facts.SetFact("q001_met_jackie", 1)
        self.assertEqual(self.facts.GetFact("q001_met_jackie"), 1)

    def test_add_fact_increments(self):
        self.facts.SetFact("kill_count", 5)
        new = self.facts.AddFact("kill_count", 3)
        self.assertEqual(new, 8)
        self.assertEqual(self.facts.GetFact("kill_count"), 8)

    def test_case_insensitive_lookup(self):
        """Facts are case-insensitive in CP2077."""
        self.facts.SetFact("Q001_MET_JACKIE", 1)
        self.assertEqual(self.facts.GetFact("q001_met_jackie"), 1)

    def test_fact_defined_after_set(self):
        self.facts.SetFact("my_flag", 0)
        self.assertTrue(self.facts.FactDefined("my_flag"))

    def test_fact_not_defined_before_set(self):
        self.assertFalse(self.facts.FactDefined("never_set"))

    def test_reset_fact(self):
        self.facts.SetFact("temp_flag", 42)
        self.facts.ResetFact("temp_flag")
        self.assertFalse(self.facts.FactDefined("temp_flag"))
        self.assertEqual(self.facts.GetFact("temp_flag"), 0)

    def test_reset_all(self):
        self.facts.SetFacts({"a": 1, "b": 2, "c": 3})
        self.facts.ResetAll()
        self.assertEqual(len(self.facts.Snapshot()), 0)

    def test_listener_called_on_set(self):
        received = []
        self.facts.RegisterListener("alarm_triggered", lambda v: received.append(v))
        self.facts.SetFact("alarm_triggered", 1)
        self.assertEqual(received, [1])

    def test_listener_called_on_add(self):
        received = []
        self.facts.RegisterListener("score", lambda v: received.append(v))
        self.facts.AddFact("score", 10)
        self.assertEqual(received, [10])

    def test_listener_not_called_for_other_facts(self):
        received = []
        self.facts.RegisterListener("my_fact", lambda v: received.append(v))
        self.facts.SetFact("other_fact", 99)
        self.assertEqual(received, [])

    def test_snapshot_returns_copy(self):
        self.facts.SetFact("key", 5)
        snap = self.facts.Snapshot()
        snap["key"] = 999
        self.assertEqual(self.facts.GetFact("key"), 5)

    def test_game_sim_set_get_fact_helpers(self):
        self.sim.set_fact("tutorial_complete", 1)
        self.assertEqual(self.sim.get_fact("tutorial_complete"), 1)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 5: QuestPhase execution
# ════════════════════════════════════════════════════════════════════════════

class TestQuestPhaseExecution(unittest.TestCase):

    def setUp(self):
        self.sim   = GameSimulation()
        self.facts = self.sim.quests.facts

    def tearDown(self):
        self.sim.teardown()

    def _make_linear_phase(self, phase_id="test_phase"):
        """A simple 3-node phase: Start → SetFact("ran", 1) → End."""
        p = QuestPhase(phase_id)
        p.add_node(QuestNode("start", QuestNodeType.Start,
                             outputs={"out": "set_ran"}))
        p.add_node(QuestNode("set_ran", QuestNodeType.SetFact,
                             outputs={"out": "end"},
                             payload={"fact": "ran", "value": 1}))
        p.add_node(QuestNode("end", QuestNodeType.End))
        return p

    def test_linear_phase_completes(self):
        p = self._make_linear_phase()
        result = p.execute(self.facts)
        self.assertTrue(result)
        self.assertTrue(p.is_done)

    def test_linear_phase_sets_fact(self):
        p = self._make_linear_phase()
        p.execute(self.facts)
        self.assertEqual(self.facts.GetFact("ran"), 1)

    def test_fact_check_true_branch(self):
        """FactCheck node should follow out_true when condition passes."""
        self.facts.SetFact("flag", 1)
        p = QuestPhase("branch_test")
        p.add_node(QuestNode("start", QuestNodeType.Start, outputs={"out": "check"}))
        p.add_node(QuestNode("check", QuestNodeType.FactCheck,
                             outputs={"out_true": "mark_true", "out_false": "mark_false"},
                             payload={"fact": "flag", "condition": ">=", "threshold": 1}))
        p.add_node(QuestNode("mark_true",  QuestNodeType.SetFact, outputs={"out": "end"},
                             payload={"fact": "branch_result", "value": 100}))
        p.add_node(QuestNode("mark_false", QuestNodeType.SetFact, outputs={"out": "end"},
                             payload={"fact": "branch_result", "value": 0}))
        p.add_node(QuestNode("end", QuestNodeType.End))
        p.execute(self.facts)
        self.assertEqual(self.facts.GetFact("branch_result"), 100)

    def test_fact_check_false_branch(self):
        """FactCheck node should follow out_false when condition fails."""
        self.facts.SetFact("flag", 0)
        p = QuestPhase("branch_false_test")
        p.add_node(QuestNode("start",  QuestNodeType.Start, outputs={"out": "check"}))
        p.add_node(QuestNode("check",  QuestNodeType.FactCheck,
                             outputs={"out_true": "mark_t", "out_false": "mark_f"},
                             payload={"fact": "flag", "condition": ">=", "threshold": 1}))
        p.add_node(QuestNode("mark_t", QuestNodeType.SetFact, outputs={"out": "end"},
                             payload={"fact": "result", "value": 1}))
        p.add_node(QuestNode("mark_f", QuestNodeType.SetFact, outputs={"out": "end"},
                             payload={"fact": "result", "value": 0}))
        p.add_node(QuestNode("end",    QuestNodeType.End))
        p.execute(self.facts)
        self.assertEqual(self.facts.GetFact("result"), 0)

    def test_increment_fact_via_phase(self):
        """AddFact (delta payload) should increment the fact."""
        self.facts.SetFact("counter", 3)
        p = QuestPhase("inc_test")
        p.add_node(QuestNode("start", QuestNodeType.Start, outputs={"out": "inc"}))
        p.add_node(QuestNode("inc",   QuestNodeType.SetFact, outputs={"out": "end"},
                             payload={"fact": "counter", "delta": 2}))
        p.add_node(QuestNode("end",   QuestNodeType.End))
        p.execute(self.facts)
        self.assertEqual(self.facts.GetFact("counter"), 5)

    def test_objectives_added_via_phase(self):
        """ObjectiveAdd nodes should appear in the journal."""
        p = QuestPhase("q001")
        p.add_node(QuestNode("start", QuestNodeType.Start, outputs={"out": "add_obj"}))
        p.add_node(QuestNode("add_obj", QuestNodeType.ObjectiveAdd,
                             outputs={"out": "end"},
                             payload={"objective_id": "meet_jackie",
                                      "description": "Meet Jackie at the alley"}))
        p.add_node(QuestNode("end", QuestNodeType.End))
        journal = JournalManager()
        p.execute(self.facts, journal)
        journal.add_quest("q001", "The Ripperdoc")
        obj = journal.get_quest("q001")
        # Objective was added during execution
        self.assertIn("meet_jackie", obj.objectives if obj else {})

    def test_quest_system_execute_phase(self):
        """QuestSystem.execute_phase should run a registered phase."""
        qs = self.sim.quests
        p  = self._make_linear_phase("registered_phase")
        qs.register_phase(p)
        result = qs.execute_phase("registered_phase")
        self.assertTrue(result)
        self.assertEqual(qs.GetFact("ran"), 1)

    def test_questsystem_setfact_and_getfact(self):
        qs = self.sim.quests
        qs.SetFact("heist_done", 1)
        self.assertEqual(qs.GetFact("heist_done"), 1)

    def test_questsystem_add_fact(self):
        qs = self.sim.quests
        qs.AddFact("missions_done", 1)
        qs.AddFact("missions_done", 1)
        self.assertEqual(qs.GetFact("missions_done"), 2)

    def test_questsystem_reset(self):
        qs = self.sim.quests
        qs.SetFact("some_flag", 5)
        qs.reset()
        self.assertEqual(qs.GetFact("some_flag"), 0)


# ════════════════════════════════════════════════════════════════════════════
#  Suite 6: JournalManager
# ════════════════════════════════════════════════════════════════════════════

class TestJournalManager(unittest.TestCase):

    def setUp(self):
        self.sim     = GameSimulation()
        self.journal = self.sim.quests.journal

    def tearDown(self):
        self.sim.teardown()

    def test_add_quest(self):
        self.journal.add_quest("q001", "The Ripperdoc")
        entry = self.journal.get_quest("q001")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.title, "The Ripperdoc")

    def test_quest_starts_active(self):
        self.journal.add_quest("q001", "The Ripperdoc")
        entry = self.journal.get_quest("q001")
        self.assertEqual(entry.status, ObjectiveStatus.Active)

    def test_add_objective(self):
        self.journal.add_quest("q001", "The Ripperdoc")
        self.journal.add_objective("q001", "meet_jackie",
                                   "Meet Jackie at the alley")
        entry = self.journal.get_quest("q001")
        self.assertIn("meet_jackie", entry.objectives)

    def test_objective_starts_active(self):
        self.journal.add_quest("q001", "The Ripperdoc")
        self.journal.add_objective("q001", "meet_jackie", "Meet Jackie")
        obj = self.journal.get_quest("q001").objectives["meet_jackie"]
        self.assertEqual(obj.status, ObjectiveStatus.Active)

    def test_complete_objective(self):
        self.journal.add_quest("q001", "The Ripperdoc")
        self.journal.add_objective("q001", "meet_jackie", "Meet Jackie")
        self.journal.complete_objective("q001", "meet_jackie")
        self.assertTrue(self.journal.is_objective_done("q001", "meet_jackie"))

    def test_fail_objective(self):
        self.journal.add_quest("q001", "The Ripperdoc")
        self.journal.add_objective("q001", "save_sample", "Save the Flathead sample")
        self.journal.fail_objective("q001", "save_sample")
        obj = self.journal.get_quest("q001").objectives["save_sample"]
        self.assertEqual(obj.status, ObjectiveStatus.Failed)

    def test_complete_quest(self):
        self.journal.add_quest("q001", "The Ripperdoc")
        self.journal.complete_quest("q001")
        entry = self.journal.get_quest("q001")
        self.assertEqual(entry.status, ObjectiveStatus.Done)

    def test_get_active_quests(self):
        self.journal.add_quest("q001", "Active Quest")
        self.journal.add_quest("q002", "Completed Quest")
        self.journal.complete_quest("q002")
        active = self.journal.get_active_quests()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].quest_id, "q001")

    def test_unknown_quest_returns_none(self):
        result = self.journal.get_quest("nonexistent")
        self.assertIsNone(result)

    def test_complete_unknown_objective_returns_false(self):
        self.journal.add_quest("q001", "Quest")
        result = self.journal.complete_objective("q001", "missing_obj")
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
