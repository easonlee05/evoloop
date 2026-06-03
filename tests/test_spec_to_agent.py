import unittest

from app.workflows.spec_to_agent import build_spec_to_agent_definition


class TestSpecToAgentWorkflow(unittest.TestCase):
    def test_spec_to_agent_workflow_structure(self):
        definition = build_spec_to_agent_definition()

        self.assertEqual(definition.type, "spec_to_agent")
        self.assertEqual(definition.metadata["is_native_3_0"], True)
        self.assertEqual(definition.metadata["source_of_truth"], "machine_spec.yaml")

        steps = definition.workflow.steps
        step_ids = [step.id for step in steps]

        # Verify core lane steps
        self.assertIn("ingest_requirements", step_ids)
        self.assertIn("pm_draft_machine_spec", step_ids)
        self.assertIn("writer_machine_spec", step_ids)
        self.assertIn("writer_human_brief", step_ids)
        self.assertIn("writer_agent_package", step_ids)
        self.assertIn("writer_acceptance", step_ids)
        self.assertIn("writer_review_checklist", step_ids)
        self.assertIn("writer_traceability", step_ids)

        # Verify output spec
        self.assertEqual(definition.output_spec["machine_spec"], "machine_spec.yaml")
        self.assertEqual(definition.output_spec["human_brief"], "human_brief.md")
        self.assertEqual(definition.output_spec["agent_package"], "agent_package_codex.md")
        self.assertEqual(definition.output_spec["acceptance"], "acceptance.md")
        self.assertEqual(definition.output_spec["review_checklist"], "review_checklist.md")
        self.assertEqual(definition.output_spec["traceability"], "traceability.json")


if __name__ == "__main__":
    unittest.main()
