import unittest
from pathlib import Path

import yaml


class TestBohriumWorkflow(unittest.TestCase):
    """Protect the trust boundary around secret-backed Bohrium tests."""

    def test_pull_requests_require_an_exact_reviewed_sha(self) -> None:
        """Keep untrusted pull-request code out of pull_request_target."""
        workflow_path = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "test-bohrium.yml"
        )
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        triggers = workflow["on"]

        self.assertNotIn("pull_request_target", triggers)
        dispatch_inputs = triggers["workflow_dispatch"]["inputs"]
        self.assertTrue(dispatch_inputs["pull_request"]["required"])
        self.assertTrue(dispatch_inputs["reviewed_sha"]["required"])

        verification_job = workflow["jobs"]["verify_reviewed_commit"]
        self.assertEqual(verification_job["permissions"], {"pull-requests": "read"})
        verification_step = verification_job["steps"][0]
        self.assertIn(".head.repo.full_name", verification_step["run"])
        self.assertIn("head_repository=", verification_step["run"])

        test_job = workflow["jobs"]["test"]
        self.assertEqual(test_job["environment"], "bohrium")
        self.assertEqual(
            test_job["permissions"], {"contents": "read", "id-token": "write"}
        )
        checkout_options = test_job["steps"][0]["with"]
        self.assertIn("head_repository", checkout_options["repository"])
        self.assertIn("reviewed_sha", checkout_options["ref"])
        self.assertFalse(checkout_options["persist-credentials"])
