# IT 工单分类服务与自动化测试 Demo

个人学习项目，用于练习 Python 模块测试、HTTP 接口测试、上游异常模拟和真实模型分类评测。

## 文件与职责

- `ticket_classifier.py`：输入校验、DeepSeek 调用、JSON 结果校验。
- `app.py`：FastAPI HTTP 服务，包含 `/health` 和 `/classify`。
- `test_ticket_classifier.py`：输入和输出校验测试。
- `test_classifier_flow.py`：模拟模型返回、超时和余额不足的流程测试。
- `test_api.py`：使用 TestClient 进行 HTTP 接口测试，分类模块被模拟。
- `evaluation_cases.json`：12 条预先拟定标签的合成工单，四类各三条；标签需维护者复核。
- `evaluate_live.py`：需要显式 `--live` 才会真实调用模型，生成 JSON、HTML 和 badcase 报告。
- `test_live_evaluation.py`：检查评测统计、部分执行、重复ID和 HTML 转义；不调用模型。

## 环境

当前开发环境为 Python 3.11。依赖安装命令：

```powershell
python -m pip install -r requirements.txt
```

在项目根目录自行创建 `.env`，

```dotenv
DEEPSEEK_API_KEY=替换为你自己的Key
DEEPSEEK_MODEL=deepseek-flash
```

## 离线测试（不调用模型、不需要真实 Key）

```powershell
python -m pytest test_ticket_classifier.py test_classifier_flow.py test_api.py test_live_evaluation.py -v --junitxml=offline-test-results.xml
```

这些测试不能用来声称真实模型准确率。

## 启动服务

```powershell
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

本机打开 `http://127.0.0.1:8000/docs` 进行手动接口测试。`/health` 只检查应用能否响应，不能证明模型可用。

## 真实评测（按 API 规则收费）

先检查用例内容和预期标签，再显式运行：

```powershell
python evaluate_live.py --live --limit 12
```

不加 `--live` 不会发起请求；每批最多12条，不自动重试，遇到请求错误后停止。每次运行建立新的 `reports/时间戳/` 目录，包含：

- `report.json`：逐条输入、预期、实际分类、理由、HTTP状态和耗时，以及批次统计。
- `report.html`：本地浏览器可阅读的报告，无需启动服务。
- `badcases.json`：分类不符或请求失败的记录。

真实评测通过进程内 TestClient 调用应用，再由应用访问 DeepSeek；不验证实际 TCP 端口、反向代理或网络部署。

## 指标与边界

本机已执行结果与复现命令见 `VERIFIED_RESULTS.md`。该记录只描述已运行的验证，不将计划功能计为完成。

- 请求成功与分类正确分开统计；分类命中率分母为本次实际尝试数量，包含请求失败。
- 批次是否执行完整单独记录，部分执行不能当作整批通过。
- 分类命中不代表理由正确；理由是否忠于输入需要人工复核。
- 数据为12条合成示例，没有独立业务分布代表性；不能宣传为生产准确率。
- 记录的是客户端观察到的串行请求耗时，包含应用与上游等待；不是纯模型推理时间、压力测试或稳定性结论。
- 提示词哈希与所选数据哈希便于核对版本；云端模型仍可能更新或存在输出波动。
- 当前没有真实派单、故障诊断修复、权限认证、生产监控、CI或性能压测.
