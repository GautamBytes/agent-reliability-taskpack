import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("collect_trials", Path(__file__).resolve().parents[1] / "collect_trials.py")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class CollectorHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.previous_root = collector.ROOT
        collector.ROOT = self.root
        self.name = "better-auth-indexes-standard"
        self.task = self.root / "tasks/better-auth-indexes"
        self.native = self.root / "evidence/coding-agents" / self.name / "native-trial"
        self.output = self.root / "evidence/trials" / self.name
        self.old_hash = hashlib.sha256(b"old verifier").hexdigest()
        self.new_hash = hashlib.sha256(b"corrected verifier").hexdigest()
        for scope in collector.SCOPES["better-auth-indexes"]:
            self.write(self.task / "environment/repo" / scope / "index.ts", "export const value = 1;\n")
            self.write(self.native / "artifacts/app/repo" / scope / "index.ts", "export const value = 1;\n")
        self.write(self.task / "tests/holdout.ts", "corrected verifier")
        self.write(self.native / "artifacts/app/repo/.network-boundary.json", {"github_proxy_denied": True, "direct_internet_blocked": True})
        self.write(self.native / "artifacts/network-proxy/connections.jsonl", '{"host":"chatgpt.com","decision":"allow"}\n{"host":"github.com","decision":"deny"}\n')
        self.write(self.native / "result.json", {"verifier_result": {"rewards": {"reward": 0}}, "exception_info": None})
        self.metrics = {"tests_run": 1, "passed": 0, "failed": 1, "skipped": 0, "cases": [{"name": "regression", "status": "failed"}]}
        self.write(self.native / "verifier/results.json", self.metrics)
        self.episode = {"task": "better-auth-indexes", "profile": "standard", "model": "test-model", "reasoning": "medium", "agent_timeout_seconds": 300, "started_at": "2026-10-30T11:00:00Z", "finished_at": "2026-10-30T11:01:00Z", "task_unchanged_during_trial": True, "task_fingerprint": {"tests/holdout.ts": self.new_hash}}
        self.episode_path = self.root / "evidence/coding-agents" / (self.name + ".episode.json")
        self.write(self.episode_path, self.episode)
        self.write(self.root / "FAIRNESS_REVISION.json", {"id": "revision-1", "changes": [{"path": "tests/holdout.ts", "original_sha256": self.old_hash, "corrected_sha256": self.new_hash}]})
        self.rescore = self.root / "evidence/rescored" / self.name
        self.write(self.rescore / "results.json", {"tests_run": 1, "passed": 1, "failed": 0, "skipped": 0, "cases": [{"name": "regression", "status": "passed"}]})
        self.write(self.rescore / "reward.txt", "1\n")
        self.write(self.rescore / "replay.json", {"trial": self.name, "patch_sha256": hashlib.sha256(b"").hexdigest(), "fairness_revision": "revision-1", "source_hashes_verified": True})

    def tearDown(self):
        collector.ROOT = self.previous_root
        self.temporary.cleanup()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value, dict) else value)

    def collect(self):
        with contextlib.redirect_stdout(io.StringIO()):
            collector.collect(False)

    def test_corrected_verifier_run_keeps_its_native_failure(self):
        self.collect()
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(summary["reward"], 0)
        self.assertFalse(summary["fairness_rescored"])

    def test_different_episode_cannot_overwrite_archive(self):
        previous = dict(self.episode, started_at="2026-10-29T11:00:00Z")
        self.write(self.output / "episode.json", previous)
        before = (self.output / "episode.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "[Ee]pisode|[Aa]rchive|[Oo]verwrite"):
            self.collect()
        self.assertEqual((self.output / "episode.json").read_bytes(), before)
        self.assertFalse((self.output / "harbor-result.json").exists())

    def test_old_episode_requires_matching_rescore_patch(self):
        self.episode["task_fingerprint"]["tests/holdout.ts"] = self.old_hash
        self.write(self.episode_path, self.episode)
        self.write(self.rescore / "replay.json", {"trial": self.name, "patch_sha256": "different-source", "fairness_revision": "revision-1", "source_hashes_verified": True})
        with self.assertRaisesRegex((ValueError, AssertionError), "[Pp]atch|[Rr]escore"):
            self.collect()

    def test_original_episode_accepts_verified_same_patch_rescore(self):
        self.episode["task_fingerprint"]["tests/holdout.ts"] = self.old_hash
        self.write(self.episode_path, self.episode)
        self.collect()
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["original_reward"], 0)
        self.assertTrue(summary["fairness_rescored"])

    def test_final_corrected_verifier_runs_do_not_require_historical_rescores(self):
        for task in collector.SCOPES:
            for profile in ("standard", "extended"):
                name = task + "-" + profile
                if name == self.name:
                    continue
                native = self.root / "evidence/coding-agents" / name / "native-trial"
                shutil.copytree(self.native, native)
                for scope in collector.SCOPES[task]:
                    self.write(self.root / "tasks" / task / "environment/repo" / scope / "index.ts", "export const value = 1;\n")
                    self.write(native / "artifacts/app/repo" / scope / "index.ts", "export const value = 1;\n")
                self.write(self.root / "tasks" / task / "tests/holdout.ts", "corrected verifier")
                self.write(self.root / "evidence/coding-agents" / (name + ".episode.json"), dict(self.episode, task=task, profile=profile))
        with contextlib.redirect_stdout(io.StringIO()):
            collector.collect(True)
        summary = json.loads((self.root / "evidence/trial-summary.json").read_text())
        self.assertEqual(summary["completed"], 6)
        self.assertEqual(summary["failed"], 6)
        self.assertFalse(any(trial["fairness_rescored"] for trial in summary["trials"]))


if __name__ == "__main__":
    unittest.main()
