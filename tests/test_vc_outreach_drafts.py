import csv
import inspect
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workflows.vc_outreach_drafts.run as outreach_module
from workflows.vc_outreach_drafts.run import vc_outreach_drafts


BASE_ROW = {
    "priority_rank": "1",
    "fund_name": "OpenOcean",
    "website": "https://openocean.vc",
    "geography": "Pan-European",
    "fund_type": "Seed & Series A VC",
    "fit_score": "97",
    "route_quality": "A",
    "contact_name": "Fund Team",
    "contact_role": "Fund Team",
    "contact_confidence": "Low",
    "email": "helsinki@openocean.vc",
    "email_status": "verified",
    "contact_method": "email_direct",
    "contact_url": "https://openocean.vc/contact",
    "evidence_url": "https://openocean.vc",
    "evidence_summary": "Official site text confirmed the fund name and investment purpose.",
    "outreach_angle": "AI-OS fits OpenOcean's thesis on AI-native software for knowledge work.",
    "suggested_subject": "AI-OS workflow automation question",
    "first_action": "Review the evidence, then draft a manual email.",
    "validation_status": "needs_review",
    "validation_flags": "hunter_provider_unavailable:http_429_error; contact_person_unverified",
}


def _csv_text(rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(BASE_ROW.keys()))
    writer.writeheader()
    for row in rows:
        merged = dict(BASE_ROW)
        merged.update(row)
        writer.writerow(merged)
    return buffer.getvalue()


def _run_with_temp_outputs(lead_data, max_drafts="5"):
    temp = tempfile.TemporaryDirectory()
    out_root = Path(temp.name)

    def fake_save_output(content, folder, filename=None, kb_root=None):
        path = out_root / folder / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    patcher = patch("workflows.vc_outreach_drafts.run.save_output", side_effect=fake_save_output)
    patcher.start()
    try:
        result = vc_outreach_drafts(
            lead_data=lead_data,
            campaign_context="Manuel wants careful investor feedback on AI-OS.",
            sender_name="Manuel",
            sender_context="I am building AI-OS after shipping workflow automations with Codex.",
            outreach_goal="Pressure-test AI-OS positioning with B2B SaaS and AI workflow investors.",
            call_to_action="Would you be open to a 20-minute feedback call next week?",
            max_drafts=max_drafts,
        )
    finally:
        patcher.stop()
        temp.cleanup()
    return result


class VCOutreachDraftTests(unittest.TestCase):
    def test_max_five_leads_processed(self):
        rows = [
            {"priority_rank": str(index + 1), "fund_name": f"Fund {index + 1}"}
            for index in range(6)
        ]
        result = _run_with_temp_outputs(_csv_text(rows), max_drafts="5")

        self.assertEqual(len(result["drafts"]), 5)
        self.assertNotIn("Fund 6", result["brief"])

    def test_blocked_rows_are_not_drafted_ready_to_send(self):
        lead_data = _csv_text([
            {
                "fund_name": "Blocked Fund",
                "route_quality": "D",
                "email": "",
                "email_status": "blocked",
                "validation_status": "blocked",
                "validation_flags": "weak_or_missing_primary_evidence; email_blocked",
            }
        ])
        result = _run_with_temp_outputs(lead_data)
        draft = result["drafts"][0]

        self.assertEqual(draft["review_status"], "blocked")
        self.assertEqual(draft["first_touch_email"], "")
        self.assertEqual(result["blocked_count"], 1)
        self.assertIn("BLOCKED", result["brief"])

    def test_missing_evidence_blocks_or_requires_review(self):
        lead_data = _csv_text([
            {
                "fund_name": "Missing Evidence Fund",
                "evidence_url": "",
                "evidence_summary": "",
                "validation_status": "usable",
                "validation_flags": "none",
            }
        ])
        result = _run_with_temp_outputs(lead_data)
        draft = result["drafts"][0]

        self.assertIn(draft["review_status"], {"blocked", "needs_review"})
        self.assertIn("strong_primary_evidence_url", draft["missing_evidence"])
        self.assertGreaterEqual(result["blocked_count"] + result["needs_review_count"], 1)

    def test_no_sending_function_exists(self):
        function_names = {
            name for name, value in inspect.getmembers(outreach_module, inspect.isfunction)
        }

        self.assertNotIn("send_email", function_names)
        self.assertNotIn("send_gmail", function_names)
        self.assertNotIn("gmail_send", function_names)
        self.assertFalse(any("smtp" in name.lower() for name in function_names))

    def test_output_includes_required_draft_sections(self):
        result = _run_with_temp_outputs(_csv_text([{}]))
        draft = result["drafts"][0]

        self.assertEqual(len(draft["subject_lines"]), 2)
        self.assertTrue(draft["first_touch_email"])
        self.assertTrue(draft["follow_up"])
        self.assertTrue(draft["personalization_rationale"])
        self.assertTrue(draft["evidence_used"])
        self.assertTrue(draft["manual_send_checklist"])
        self.assertIn("review_queue_csv_path", result)
        self.assertIn("file_path", result)


if __name__ == "__main__":
    unittest.main()
