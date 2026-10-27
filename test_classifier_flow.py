from unittest.mock import MagicMock, patch

import httpx
import pytest
from openai import APITimeoutError, APIStatusError

from ticket_classifier import classify_ticket


@pytest.fixture
def fake_client(monkeypatch):
    """为每个测试准备独立的模拟客户端。"""

    # 使用假的Key，并阻止读取真实.env文件
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key-for-tests")

    with patch("ticket_classifier.load_dotenv"):
        with patch("ticket_classifier.OpenAI") as fake_factory:
            client = fake_factory.return_value.__enter__.return_value
            yield client


def test_classify_success(fake_client):
    """模拟模型正常返回，检查整个流程的结果。"""
    response = MagicMock()
    response.choices = [
        MagicMock(
            finish_reason="stop",
            message=MagicMock(
                content='{"category":"网络","reason":"无法连接Wi-Fi"}'
            ),
        )
    ]

    fake_client.chat.completions.create.return_value = response

    result = classify_ticket("Wi-Fi连接不上")

    assert result == {
        "category": "网络",
        "reason": "无法连接Wi-Fi",
    }

    # 确认调用了一次，并且发送了正确的工单内容
    create = fake_client.chat.completions.create
    create.assert_called_once()
    assert create.call_args.kwargs["messages"][1]["content"] == "Wi-Fi连接不上"


def test_empty_input_does_not_call_api(fake_client):
    """空输入应提前拒绝，不应该调用模型。"""
    with pytest.raises(ValueError, match="工单内容不能为空"):
        classify_ticket("   ")

    fake_client.chat.completions.create.assert_not_called()


def test_model_timeout(fake_client):
    """模拟调用超时，错误应向上传递。"""
    request = httpx.Request(
        "POST", "https://api.deepseek.com/chat/completions"
    )
    error = APITimeoutError(request=request)

    fake_client.chat.completions.create.side_effect = error

    with pytest.raises(APITimeoutError):
        classify_ticket("Wi-Fi连接不上")

    fake_client.chat.completions.create.assert_called_once()


def test_insufficient_balance(fake_client):
    """模拟余额不足，不能伪装成分类成功。"""
    request = httpx.Request(
        "POST", "https://api.deepseek.com/chat/completions"
    )
    response = httpx.Response(402, request=request)

    error = APIStatusError(
        "Insufficient Balance",
        response=response,
        body={"error": {"message": "Insufficient Balance"}},
    )

    fake_client.chat.completions.create.side_effect = error

    with pytest.raises(APIStatusError) as caught:
        classify_ticket("Wi-Fi连接不上")

    assert caught.value.status_code == 402
    fake_client.chat.completions.create.assert_called_once()