#!/usr/bin/env python3
"""Regression tests for structural GitHub Pages workflow validation."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pages_workflow import WorkflowValidationError, validate_pages_workflow


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "workflows"


class PagesWorkflowTests(unittest.TestCase):
    def assert_invalid_mutation(self, old: str, new: str, message: str) -> None:
        self.assert_invalid_mutations(((old, new),), message)

    def assert_invalid_mutations(
        self, replacements: tuple[tuple[str, str], ...], message: str
    ) -> None:
        source = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(
            encoding="utf-8"
        )
        for old, new in replacements:
            self.assertIn(old, source)
            source = source.replace(old, new, 1)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(WorkflowValidationError, message):
                validate_pages_workflow(path)

    def test_repository_workflow_is_valid(self) -> None:
        validate_pages_workflow(ROOT / ".github" / "workflows" / "deploy-pages.yml")

    def test_rejects_push_trigger_relocated_under_env(self) -> None:
        with self.assertRaisesRegex(WorkflowValidationError, r"on\.push\.branches"):
            validate_pages_workflow(FIXTURES / "push-under-env.yml")

    def test_rejects_permissions_relocated_under_job(self) -> None:
        with self.assertRaisesRegex(WorkflowValidationError, r"permissions\.pages"):
            validate_pages_workflow(FIXTURES / "permissions-under-job.yml")

    def test_rejects_branch_filter_that_excludes_main(self) -> None:
        with self.assertRaisesRegex(WorkflowValidationError, r"exactly.*main"):
            validate_pages_workflow(FIXTURES / "main-excluded.yml")

    def test_rejects_paths_ignore_that_disables_all_push_deployments(self) -> None:
        with self.assertRaisesRegex(WorkflowValidationError, r"on\.push.*branches"):
            validate_pages_workflow(FIXTURES / "paths-ignore-all.yml")

    def test_rejects_job_permissions_that_override_top_level_grants(self) -> None:
        with self.assertRaisesRegex(WorkflowValidationError, r"jobs\.deploy\.permissions"):
            validate_pages_workflow(FIXTURES / "job-permissions-override.yml")

    def test_rejects_version_comment_relocated_outside_the_step(self) -> None:
        pin = "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
        self.assert_invalid_mutations(
            (
                (f"{pin} # v7.0.1", pin),
                ("jobs:\n", f"env:\n  uses: {pin.removeprefix('uses: ')} # v7.0.1\n\njobs:\n"),
            ),
            "version comment",
        )

    def test_rejects_over_indented_step_property(self) -> None:
        self.assert_invalid_mutation(
            "        uses: actions/checkout@",
            "          uses: actions/checkout@",
            "indentation",
        )

    def test_rejects_disabled_deploy_job(self) -> None:
        self.assert_invalid_mutation(
            "  deploy:\n    environment:",
            "  deploy:\n    if: false\n    environment:",
            "jobs.deploy",
        )

    def test_requires_manual_dispatch_trigger(self) -> None:
        self.assert_invalid_mutation(
            "  workflow_dispatch:\n",
            "",
            r"on\.workflow_dispatch",
        )


if __name__ == "__main__":
    unittest.main()
