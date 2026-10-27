"""只测试评测工具自身，不调用模型。"""

import json

import pytest

from evaluate_live import load_cases, summarize, write_reports


def test_summary_separates_wrong_categories_and_request_errors():
    rows = [
        {"http_status": 200, "expected": "网络", "actual_category": "网络"},
        {"http_status": 200, "expected": "账号", "actual_category": "软件"},
        {"http_status": 503, "expected": "账号", "actual_category": None},
    ]
    result = summarize(rows, planned_count=3)
    assert result["correct_categories"] == 1
    assert result["wrong_categories"] == 1
    assert result["request_errors"] == 1
    assert result["category_hit_rate_on_attempted"] == pytest.approx(1 / 3)


def test_partial_run_is_not_reported_as_complete():
    rows = [{"http_status": 503, "expected": "网络", "actual_category": None}]
    result = summarize(rows, planned_count=12)
    assert result["completed"] is False
    assert result["attempted_count"] == 1
    assert result["planned_count"] == 12


def test_duplicate_case_ids_are_rejected(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": [
        {"id": "A01", "text": "密码忘了", "expected": "账号"},
        {"id": "A01", "text": "账号锁定", "expected": "账号"},
    ]}), encoding="utf-8")
    with pytest.raises(ValueError, match="不重复"):
        load_cases(path)


def test_reports_escape_html_and_keep_badcases(tmp_path):
    output = tmp_path / "run"
    row = {
        "id": "O01", "text": "<script>alert(1)</script>", "expected": "其他",
        "actual_category": "网络", "http_status": 200,
        "reason": "不符合预期的分类", "latency_ms": 1,
    }
    report = {
        "created_at": "2026-10-27T00:00:00+08:00", "model": "test-model",
        "summary": summarize([row], 1), "results": [row],
    }
    write_reports(report, output)
    page = (output / "report.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    badcases = json.loads((output / "badcases.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in badcases] == ["O01"]
