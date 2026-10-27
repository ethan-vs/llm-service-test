## 离线自动化测试

执行命令：

```powershell
python -m pytest test_ticket_classifier.py test_classifier_flow.py test_api.py test_live_evaluation.py -q --junitxml=offline-test-results.xml
```

实际结果：`32 passed in 1.47s`。包含输入与输出校验14项、模拟分类调用4项、接口测试10项、评测工具测试4项。1.47秒仅为这批离线测试耗时，不是模型响应速度。

## 真实模型验证

- 充值前：一次独立连接检查返回 HTTP 402，确认是上游余额不足；不是模型分类错误。
- 充值后：使用进程内 TestClient 向本地应用提交一条 Wi-Fi 示例，`/health` 和 `/classify` 均返回200，分类为网络。
- 小批量评测：`python evaluate_live.py --live --limit 12`。
- 实际使用的模型名称：`deepseek-flash`。
- 批次开始时间：2026-10-27T22:32:20.483199+08:00。
- 计划12条，实际执行12条，成功响应12条，分类命中12条，请求错误0条。
- 本次示例集命中率12/12；不是独立业务测试集准确率，也没有进行重复运行或并发负载测试。
- 工单与预期标签在请求前写入数据文件，由AI按既定规则拟定，仍需维护者逐条复核标签。
- 已阅读本批次12条理由，未发现明显编造故障原因或修复结果；没有独立专家复核或量化理由评分，机器报告保留“理由未评分”。

原始逐条报告位于本地：`reports/20261027_223220_483199/`，包含 `report.json`、`report.html`、`badcases.json`。本批 `badcases.json` 为空列表；不能为了展示缺陷而编造失败案例。

