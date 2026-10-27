from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError, APIStatusError

from app import app


@pytest.fixture(autouse=True)
def mock_classifier():
    """每项测试都替换分类模块，避免调用真实API。"""
    with patch("app.classify_ticket") as mocked:
        yield mocked


@pytest.fixture
def client():
    """创建测试客户端，不需要启动uvicorn。"""
    with TestClient(app) as test_client:
        yield test_client


def test_health(client, mock_classifier):
    """健康检查应返回200，且不调用分类模块。"""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_classifier.assert_not_called()


def test_classify_success(client, mock_classifier):
    """正常请求应返回200和分类结果。"""
    mock_classifier.return_value = {
        "category": "网络",
        "reason": "无法连接Wi-Fi",
    }

    response = client.post(
        "/classify",
        json={"text": "  Wi-Fi连接不上  "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "category": "网络",
        "reason": "无法连接Wi-Fi",
    }

    # 确认接口去掉空白后，将工单传给分类模块
    mock_classifier.assert_called_once_with("Wi-Fi连接不上")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"text": ""},
        {"text": "   "},
        {"text": None},
        {"text": 123},
        {"text": "测" * 2001},
    ],
    ids=["missing", "empty", "spaces", "none", "number", "too_long"],
)
def test_invalid_request(client, mock_classifier, body):
    """非法请求应返回422，并且不调用分类模块。"""
    response = client.post("/classify", json=body)

    assert response.status_code == 422
    assert "detail" in response.json()
    mock_classifier.assert_not_called()


def test_timeout_response(client, mock_classifier):
    """分类模块超时时，接口应返回504。"""
    request = httpx.Request(
        "POST", "https://api.deepseek.com/chat/completions"
    )
    mock_classifier.side_effect = APITimeoutError(request=request)

    response = client.post(
        "/classify",
        json={"text": "Wi-Fi连接不上"},
    )

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "MODEL_TIMEOUT"
    mock_classifier.assert_called_once()


def test_balance_error_response(client, mock_classifier):
    """上游余额不足时，接口应转换为503。"""
    request = httpx.Request(
        "POST", "https://api.deepseek.com/chat/completions"
    )
    upstream_response = httpx.Response(402, request=request)

    mock_classifier.side_effect = APIStatusError(
        "Insufficient Balance",
        response=upstream_response,
        body={"error": {"message": "Insufficient Balance"}},
    )

    response = client.post(
        "/classify",
        json={"text": "Wi-Fi连接不上"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_UNAVAILABLE"
    mock_classifier.assert_called_once()