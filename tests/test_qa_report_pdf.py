import json
from pathlib import Path

from scripts.qa_report_pdf import _status, render_report


def test_seeded_mutant_detection_is_not_misreported_as_benchmark_failure():
    report = {
        "summary": {"total_variants": 2, "passed_expectations": 2, "failed_expectations": 0},
        "results": [
            {"case": "checkbox", "variant": "good", "observed": "PASS", "benchmark_pass": True},
            {"case": "checkbox", "variant": "mutant", "observed": "FAIL", "benchmark_pass": True},
        ],
    }
    assert _status(report)[0] == "PASS"


def test_failed_benchmark_expectation_is_reported_as_failure():
    report = {
        "summary": {"total_variants": 2, "passed_expectations": 1, "failed_expectations": 1},
        "results": [{"variant": "mutant", "observed": "PASS", "benchmark_pass": False}],
    }
    assert _status(report)[0] == "FAIL"


def test_pdf_is_generated_with_plain_language_sections(tmp_path: Path):
    source = tmp_path / "report.json"
    output = tmp_path / "report.pdf"
    source.write_text(json.dumps({
        "title": "CYDRA QA Sample",
        "target": "Controlled local fixture",
        "summary": {"total": 1, "passed": 1, "failed": 0, "inconclusive": 0},
        "tests": [{"id": "QA-001", "name": "Checkbox toggles", "status": "PASS",
                   "observed": {"changed": True}, "notes": []}],
        "interpretation": "A controlled fixture was checked.",
        "limitations": ["This is not a production finding."],
    }), encoding="utf-8")
    render_report(source, output)
    content = output.read_bytes()
    assert content.startswith(b"%PDF")
    assert len(content) > 1000
