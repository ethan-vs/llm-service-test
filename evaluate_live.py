"""显式指定 --live 才会调用付费模型；默认不发起请求。"""

import argparse
import hashlib
import html
import json
import os
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import app
from ticket_classifier import CATEGORIES, SYSTEM_PROMPT, validate_input


ROOT = Path(__file__).resolve().parent


def load_cases(path):
    """调用前检查整批用例，防止无效数据浪费请求。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = data["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("用例列表不能为空")
    seen = set()
    for case in cases:
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError("用例ID必须是非空、不重复的字符串")
        seen.add(case_id)
        validate_input(case["text"])
        if not isinstance(case["expected"], str) or case["expected"] not in CATEGORIES:
            raise ValueError("预期分类不在允许范围内")
    return cases


def summarize(rows, planned_count):
    """错误请求与分类错误分开统计，部分执行不冒充整批通过。"""
    attempted = len(rows)
    successful = sum(row["http_status"] == 200 for row in rows)
    correct = sum(
        row["http_status"] == 200
        and row["actual_category"] == row["expected"]
        for row in rows
    )
    return {
        "planned_count": planned_count,
        "attempted_count": attempted,
        "completed": attempted == planned_count,
        "successful_responses": successful,
        "request_errors": attempted - successful,
        "correct_categories": correct,
        "wrong_categories": successful - correct,
        "category_hit_rate_on_attempted": correct / attempted if attempted else None,
        "reason_review": "未评分：理由需人工检查是否忠于输入，不能用分类命中代替理由正确",
    }


def write_reports(report, output):
    output.mkdir(parents=True, exist_ok=False)
    rows = report["results"]
    badcases = [
        row for row in rows
        if row["http_status"] != 200 or row["actual_category"] != row["expected"]
    ]
    for name, value in [("report.json", report), ("badcases.json", badcases)]:
        (output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def escape(value):
        return html.escape(str(value))

    table = []
    for row in rows:
        passed = row["http_status"] == 200 and row["actual_category"] == row["expected"]
        cells = [
            row["id"], row["text"], row["expected"], row["actual_category"],
            row["http_status"], "命中" if passed else "待排查", row["reason"],
            row["latency_ms"],
        ]
        table.append("<tr>" + "".join(f"<td>{escape(v)}</td>" for v in cells) + "</tr>")
    summary = escape(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    page = f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><title>真实工单分类评测</title>
<style>body{{font-family:Arial,'Microsoft YaHei',sans-serif;margin:30px;line-height:1.6}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px;text-align:left}}
th{{background:#edf3fa}}pre{{white-space:pre-wrap;background:#f5f5f5;padding:16px}}</style>
<h1>真实工单分类评测</h1>
<p>时间：{escape(report['created_at'])}；模型：{escape(report['model'])}</p>
<p>使用真实 API，通过进程内 TestClient 调用本地应用；未经过实际网络端口。
合成小样本，预期标签待维护者复核；不代表生产准确率、吞吐或稳定性。
耗时包含应用与上游等待，不是纯模型推理耗时。理由未自动评分。</p>
<pre>{summary}</pre><table><tr><th>ID</th><th>工单</th><th>预期</th><th>实际</th>
<th>HTTP</th><th>结果</th><th>理由/错误</th><th>耗时ms</th></tr>
{''.join(table)}</table></html>"""
    (output / "report.html").write_text(page, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="真实模型分类小样本评测")
    parser.add_argument("--live", action="store_true", help="明确允许本次付费调用")
    parser.add_argument("--limit", type=int, default=12, help="最多请求多少条，默认12")
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation_cases.json")
    args = parser.parse_args()
    if not args.live:
        parser.error("未执行任何请求。若要真实调用，请显式添加 --live")
    if args.limit < 1 or args.limit > 12:
        parser.error("当前演示每批限制为1到12条")

    cases = load_cases(args.cases)[:args.limit]
    load_dotenv(ROOT / ".env")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip()
    created = datetime.now(timezone(timedelta(hours=8)))
    output = ROOT / "reports" / created.strftime("%Y%m%d_%H%M%S_%f")
    rows = []
    with TestClient(app, raise_server_exceptions=False) as client:
        for case in cases:
            started = perf_counter()
            response = client.post("/classify", json={"text": case["text"]})
            latency_ms = round((perf_counter() - started) * 1000, 2)
            try:
                body = response.json()
            except ValueError:
                body = {"detail": "服务未返回JSON响应"}
            row = {
                **case,
                "http_status": response.status_code,
                "actual_category": body.get("category"),
                "reason": body.get("reason", body.get("detail")),
                "latency_ms": latency_ms,
            }
            rows.append(row)
            print(f"{case['id']}: HTTP {response.status_code}, "
                  f"预期={case['expected']}, 实际={row['actual_category']}", flush=True)
            # 环境或上游不可用时停止，避免重复付费和无意义请求。
            if response.status_code != 200:
                print("出现请求错误，停止本批；已尝试的结果仍会保存。", flush=True)
                break

    report = {
        "created_at": created.isoformat(),
        "execution_mode": "real_deepseek_via_in_process_testclient",
        "model": model,
        "python_version": platform.python_version(),
        "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "selected_cases_sha256": hashlib.sha256(
            json.dumps(cases, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "dataset_scope": "合成示例集，预期标签待维护者复核；非独立业务测试集",
        "summary": summarize(rows, len(cases)),
        "results": rows,
    }
    write_reports(report, output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"报告目录：{output}")


if __name__ == "__main__":
    main()
