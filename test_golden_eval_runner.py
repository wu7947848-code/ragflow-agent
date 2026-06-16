from __future__ import annotations

import importlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class GoldenEvalRunnerTest(unittest.TestCase):
    def test_eval_file_has_required_structure(self) -> None:
        spec_path = ROOT / "ragflow_agent_v4_golden_eval.json"
        data = json.loads(spec_path.read_text(encoding="utf-8"))

        self.assertEqual(data["version"], "v4")
        self.assertGreaterEqual(len(data["single_turn_cases"]), 8)
        self.assertGreaterEqual(len(data["conversation_cases"]), 3)

        ids: set[str] = set()
        for section in ("single_turn_cases", "conversation_cases"):
            for case in data[section]:
                self.assertNotIn(case["id"], ids)
                ids.add(case["id"])
                self.assertTrue(case["id"])
                self.assertTrue(case["category"])
                self.assertIsInstance(case.get("tags", []), list)

        for case in data["single_turn_cases"]:
            self.assertTrue(case["query"])
            self.assertTrue(case.get("must") or case.get("must_any") or case.get("forbid"))

        for case in data["conversation_cases"]:
            self.assertGreaterEqual(len(case["turns"]), 2)
            for turn in case["turns"]:
                self.assertTrue(turn["query"])
                self.assertTrue(turn.get("must") or turn.get("must_any") or turn.get("forbid"))

    def test_answer_checker_detects_required_forbidden_and_process_leak(self) -> None:
        runner = importlib.import_module("ragflow_agent_v4_golden_eval")
        case = {
            "id": "unit",
            "must": ["接收端", "scie-yz@njupt.edu.cn"],
            "forbid": ["推荐端材料提交邮箱"],
            "must_any": [["通信与信息工程学院", "通信学院"]],
        }

        ok = "答案：通信与信息工程学院邮箱为 scie-yz@njupt.edu.cn。\n依据：细则。\n适用范围：接收端。\n提醒：以官方为准。"
        self.assertEqual(runner.check_answer(ok, case), [])

        bad = "答案：根据检索结果，通信学院是推荐端材料提交邮箱。\n依据：细则。\n适用范围：接收端。\n提醒：以官方为准。"
        failures = runner.check_answer(bad, case)
        self.assertIn("process text leaked", failures)
        self.assertIn("required marker missing: scie-yz@njupt.edu.cn", failures)
        self.assertIn("forbidden marker found: 推荐端材料提交邮箱", failures)


if __name__ == "__main__":
    unittest.main()
