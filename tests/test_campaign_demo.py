import unittest

from pilot.campaign_demo import run_demo


class CampaignDemoTests(unittest.TestCase):
    def test_synthetic_xlsx_to_simulated_erp_reconciliation(self):
        result = run_demo()
        self.assertEqual(result["source_total_cents"], 10001)
        self.assertEqual(result["allocated_total_cents"], 10001)
        self.assertEqual(result["export_total_cents"], 10001)
        self.assertEqual(result["simulated_erp_total_cents"], 10001)
        self.assertEqual(result["balance_difference_cents"], 0)
        self.assertEqual(result["synthetic_workflow_decision_events"], 7)
        self.assertEqual(result["synthetic_actor_count"], 6)
        self.assertTrue(result["delivery_retry_replayed"])
        self.assertFalse(result["human_time_or_savings_claimed"])
