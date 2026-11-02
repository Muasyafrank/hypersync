import unittest

from app.core.lifestyle_factors import is_data_supported, is_risk_direction, rank_factors

HEALTHY = {"salt_score": 0, "alcohol_consumed": 0, "activity_minutes": 90, "diet_adherence": 1, "smoked": 0}


def effect(lo, hi):
    return {"odds_ratio": (lo + hi) / 2, "ci_low": lo, "ci_high": hi}


class RankFactors(unittest.TestCase):
    def test_healthy_log_yields_nothing(self):
        self.assertEqual(rank_factors(HEALTHY, {}), [])

    def test_only_unhealthy_factors_are_mentioned(self):
        values = {**HEALTHY, "salt_score": 3, "smoked": 1}
        self.assertEqual([r["feature"] for r in rank_factors(values, {})], ["salt_score", "smoked"])

    def test_data_supported_factor_jumps_the_queue(self):
        values = {**HEALTHY, "salt_score": 3, "alcohol_consumed": 1, "smoked": 1}
        effects = {"smoked": effect(1.1, 1.9), "salt_score": effect(0.9, 1.1)}
        ranked = rank_factors(values, effects)
        self.assertEqual(ranked[0]["feature"], "smoked")
        self.assertTrue(ranked[0]["data_supported"])
        self.assertFalse(ranked[1]["data_supported"])
        self.assertIn("survey data", ranked[0]["message"])
        self.assertNotIn("survey data", ranked[1]["message"])

    def test_limit_is_respected(self):
        values = {"salt_score": 3, "alcohol_consumed": 1, "activity_minutes": 0, "diet_adherence": 0, "smoked": 1}
        self.assertEqual(len(rank_factors(values, {}, limit=3)), 3)

    def test_protective_factor_support_uses_upper_bound(self):
        self.assertTrue(is_data_supported("activity_minutes", effect(0.5, 0.9)))
        self.assertFalse(is_data_supported("activity_minutes", effect(0.97, 1.01)))
        self.assertFalse(is_data_supported("smoked", None))

    def test_risk_direction(self):
        self.assertTrue(is_risk_direction("activity_minutes", 5))
        self.assertFalse(is_risk_direction("activity_minutes", 60))
        self.assertTrue(is_risk_direction("diet_adherence", 0))


if __name__ == "__main__":
    unittest.main()
