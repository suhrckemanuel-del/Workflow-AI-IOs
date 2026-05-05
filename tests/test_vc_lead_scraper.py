import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workflows.vc_lead_scraper.run import (
    LeadCandidate,
    LeadList,
    _apply_outreach_review_fields,
    _is_external_fund_lead,
    _sanitize_lead_for_output,
    _to_csv,
    vc_lead_scraper,
)


class VCLeadScraperTests(unittest.TestCase):
    def test_to_csv_writes_expected_header_and_rows(self):
        csv_text = _to_csv(
            [
                LeadCandidate(
                    fund_name="Test Fund",
                    website="https://testfund.example",
                    geography="Europe",
                    fund_type="Student VC",
                    relevance_score=91,
                    thesis_fit_reason="Strong peer for benchmarking.",
                    likely_contact_person="Investment Team",
                    public_email="hello@testfund.example",
                    email_confidence="publicly_listed",
                    contact_method="email_direct",
                    linkedin_or_contact_url="https://testfund.example/contact",
                    source_url="https://testfund.example",
                    fetch_status="fetched",
                    fetch_verified=True,
                    outreach_angle="Ask about portfolio KPI tracking.",
                    confidence="High",
                )
            ]
        )

        rows = list(csv.DictReader(io.StringIO(csv_text)))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["priority_rank"], "1")
        self.assertEqual(rows[0]["fund_name"], "Test Fund")
        self.assertEqual(rows[0]["email"], "hello@testfund.example")
        self.assertEqual(rows[0]["email_status"], "verified")
        self.assertEqual(rows[0]["fit_score"], "91")

    def test_workflow_saves_markdown_and_csv_sidecar_without_live_apis(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp)

            def fake_save_output(content, folder, filename=None, kb_root=None):
                path = out_root / folder / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return path

            fake_leads = LeadList(
                search_strategy="Use known peer funds.",
                missing_data_notes="Verify all contacts before outreach.",
                leads=[
                    LeadCandidate(
                        fund_name="Peer Fund",
                        website="https://peerfund.example",
                        geography="Netherlands",
                        fund_type="Student VC",
                        relevance_score=88,
                        thesis_fit_reason="Relevant student fund peer.",
                        likely_contact_person="Team",
                        public_email="",
                        email_confidence="not_found",
                        contact_method="contact_form",
                        linkedin_or_contact_url="https://peerfund.example/contact",
                        source_url="https://peerfund.example",
                        fetch_status="fetched",
                        fetch_verified=True,
                        outreach_angle="Benchmark portfolio reporting.",
                        confidence="Medium",
                    )
                ],
            )

            with (
                patch("workflows.vc_lead_scraper.run._exa_search", return_value=[]),
                patch("workflows.vc_lead_scraper.run.call_claude_structured", return_value=fake_leads),
                patch("workflows.vc_lead_scraper.run._enrich_contacts", side_effect=lambda leads, *_: leads),
                patch("workflows.vc_lead_scraper.run.save_output", side_effect=fake_save_output),
            ):
                result = vc_lead_scraper(
                    project_context="ASIF benchmarking",
                    target_profile="student-run VC funds",
                    lead_count="not-a-number",
                )

            self.assertEqual(result["leads_found"], 1)
            self.assertTrue(result["file_path"].endswith(".md"))
            self.assertTrue(result["csv_file_path"].endswith(".csv"))
            self.assertTrue(Path(result["file_path"]).exists())
            self.assertTrue(Path(result["csv_file_path"]).exists())
            self.assertIn("Peer Fund", Path(result["csv_file_path"]).read_text(encoding="utf-8"))

    def test_asif_golden_output_blocks_unsafe_outreach_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp)

            def fake_save_output(content, folder, filename=None, kb_root=None):
                path = out_root / folder / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return path

            fake_leads = LeadList(
                search_strategy="Use official fund pages first; discovery sources only for finding candidates.",
                missing_data_notes="",
                leads=[
                    LeadCandidate(
                        fund_name="ASIF Ventures",
                        website="https://asif.ventures",
                        geography="Netherlands",
                        fund_type="Student VC",
                        relevance_score=99,
                        thesis_fit_reason="The client itself, not an outreach target.",
                        likely_contact_person="Fund Team",
                        contact_person_confidence="Low",
                        contact_role="Fund Team",
                        public_email="hello@asif.ventures",
                        email_confidence="publicly_listed",
                        contact_method="email_direct",
                        linkedin_or_contact_url="https://asif.ventures/contact",
                        source_url="https://asif.ventures",
                        fetch_status="fetched",
                        fetch_verified=True,
                        outreach_angle="Should be excluded.",
                        confidence="High",
                    ),
                    LeadCandidate(
                        fund_name="Alpha Student Fund",
                        website="https://alpha.example",
                        geography="Netherlands",
                        fund_type="Student-run VC",
                        relevance_score=92,
                        thesis_fit_reason="Strong ASIF peer for student-fund portfolio reporting.",
                        likely_contact_person="Fund Team",
                        contact_person_confidence="Low",
                        contact_role="Fund Team",
                        public_email="hello@alpha.example",
                        email_confidence="publicly_listed",
                        contact_method="email_direct",
                        linkedin_or_contact_url="https://alpha.example/contact",
                        source_url="https://alpha.example",
                        fetch_status="fetched",
                        fetch_verified=True,
                        outreach_angle="Ask about student-fund portfolio KPI routines.",
                        confidence="High",
                    ),
                    LeadCandidate(
                        fund_name="Inferred Capital",
                        website="https://inferred.example",
                        geography="Germany",
                        fund_type="Student-run VC",
                        relevance_score=89,
                        thesis_fit_reason="Relevant student VC peer.",
                        likely_contact_person="Fund Team",
                        contact_person_confidence="Low",
                        contact_role="Fund Team",
                        public_email="partner@inferred.example",
                        email_confidence="inferred",
                        hunter_attempted=True,
                        hunter_response_code="http_429_error",
                        contact_method="contact_form",
                        linkedin_or_contact_url="https://inferred.example/contact",
                        source_url="https://inferred.example",
                        fetch_status="fetched",
                        fetch_verified=True,
                        outreach_angle="Ask about reporting templates.",
                        confidence="Medium",
                    ),
                    LeadCandidate(
                        fund_name="Low Confidence Ventures",
                        website="https://lowconfidence.example",
                        geography="United Kingdom",
                        fund_type="Student-led fund",
                        relevance_score=86,
                        thesis_fit_reason="Relevant student-led fund benchmark.",
                        likely_contact_person="Fund Team",
                        contact_person_confidence="Low",
                        contact_role="Fund Team",
                        email_confidence="low_confidence",
                        hunter_attempted=True,
                        hunter_response_code="http_200_low_confidence",
                        contact_method="contact_form",
                        linkedin_or_contact_url="https://lowconfidence.example/contact",
                        source_url="https://lowconfidence.example",
                        fetch_status="fetched",
                        fetch_verified=True,
                        outreach_angle="Ask about portfolio follow-up cadences.",
                        confidence="Medium",
                    ),
                    LeadCandidate(
                        fund_name="Directory Only VC",
                        website="https://directoryonly.example",
                        geography="Europe",
                        fund_type="VC database profile",
                        relevance_score=95,
                        thesis_fit_reason="Only found in a directory.",
                        likely_contact_person="Fund Team",
                        contact_person_confidence="Low",
                        contact_role="Fund Team",
                        email_confidence="not_found",
                        contact_method="website",
                        linkedin_or_contact_url="https://linkedin.com/company/directoryonly",
                        source_url="https://openvc.app/fund/directoryonly",
                        fetch_status="fetched",
                        fetch_verified=True,
                        outreach_angle="Should not use weak directory evidence.",
                        confidence="Low",
                    ),
                ],
            )

            with (
                patch("workflows.vc_lead_scraper.run._exa_search", return_value=[]),
                patch("workflows.vc_lead_scraper.run.call_claude_structured", return_value=fake_leads),
                patch("workflows.vc_lead_scraper.run._enrich_contacts", side_effect=lambda leads, *_: leads),
                patch("workflows.vc_lead_scraper.run._curated_backfill", side_effect=lambda leads, count: leads),
                patch("workflows.vc_lead_scraper.run.save_output", side_effect=fake_save_output),
            ):
                result = vc_lead_scraper(
                    project_context="ASIF Ventures portfolio benchmarking project",
                    target_profile="European student-run VC funds",
                    lead_count="10",
                    geography="Europe",
                )

            rows = list(csv.DictReader(io.StringIO(result["csv"])))
            fund_names = [row["fund_name"] for row in rows]

            self.assertNotIn("ASIF Ventures", fund_names)
            self.assertNotIn("Directory Only VC", fund_names)
            self.assertEqual([int(row["priority_rank"]) for row in rows], sorted(int(row["priority_rank"]) for row in rows))
            for row in rows:
                self.assertIn(row["route_quality"], {"A", "B", "C", "D"})
                self.assertIn(row["validation_status"], {"usable", "needs_review", "blocked"})
                self.assertTrue(row["first_action"])
                self.assertTrue(row["validation_flags"])
                self.assertNotIn("linkedin.com", row["evidence_url"].lower())
                self.assertNotIn("openvc.app", row["evidence_url"].lower())

            inferred = next(row for row in rows if row["fund_name"] == "Inferred Capital")
            self.assertEqual(inferred["email"], "")
            self.assertIn(inferred["email_status"], {"low_confidence", "provider_unavailable"})
            self.assertIn("provider_unavailable", inferred["validation_flags"])
            self.assertNotEqual(inferred["validation_status"], "usable")

            low_confidence = next(row for row in rows if row["fund_name"] == "Low Confidence Ventures")
            self.assertEqual(low_confidence["email"], "")
            self.assertEqual(low_confidence["email_status"], "low_confidence")
            self.assertIn("low_confidence", low_confidence["validation_flags"])

            self.assertNotIn("Missing Data Notes contradiction", result["brief"])

    def test_review_fixture_preserves_manual_review_contract(self):
        fixture_path = Path(__file__).parent / "fixtures" / "vc_lead_scraper_review_cases.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        for case in fixture["approved_examples"]:
            lead = LeadCandidate(**case["row"])
            _sanitize_lead_for_output(lead)
            _apply_outreach_review_fields(lead, strict_student=False, priority_rank=1)

            self.assertEqual(lead.validation_status, case["expected_validation_status"], case["fund_name"])
            self.assertEqual(lead.email_status, case["expected_email_status"], case["fund_name"])
            for trait in case["expected_validation_flags_traits"]:
                self.assertIn(trait, lead.validation_flags, case["fund_name"])

        for case in fixture["rejected_or_problem_examples"]:
            lead = LeadCandidate(**case["row"])
            if case.get("should_be_filtered"):
                self.assertFalse(_is_external_fund_lead(lead), case["fund_name"])
                continue

            _sanitize_lead_for_output(lead)
            _apply_outreach_review_fields(lead, strict_student=False, priority_rank=1)
            self.assertEqual(lead.email, "", case["fund_name"])
            self.assertEqual(lead.validation_status, case["expected_validation_status"], case["fund_name"])
            self.assertEqual(lead.email_status, case["expected_email_status"], case["fund_name"])
            for trait in case["expected_validation_flags_traits"]:
                self.assertIn(trait, lead.validation_flags, case["fund_name"])


if __name__ == "__main__":
    unittest.main()
