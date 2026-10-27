from typing import Literal

from fastapi import FastAPI, HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ticket_classifier import classify_ticket, validate_input


app = FastAPI(
    title="IT工单分类服务",
    version="0.1.0",
)


class TicketRequest(BaseModel):
    """接口允许接收的请求格式。"""
    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        min_length=1,
        max_length=2000,
        description="需要分类的IT工单内容",
    )

    @field_validator("text", mode="before")
    @classmethod
    def check_text(cls, value):
        # 复用已有规则：检查类型、去掉空白、检查长度
        return validate_input(value)


class TicketResult(BaseModel):
    """接口成功时返回的格式。"""
    model_config = ConfigDict(extra="forbid")

    category: Literal["账号", "网络", "软件", "其他"]
    reason: str = Field(min_length=1)


@app.get("/health")
def health():
    """只检查本服务能否响应，不调用模型。"""
    return {"status": "ok"}


@app.post("/classify", response_model=TicketResult)
def classify(request: TicketRequest):
    """接收工单并调用分类模块。"""
    try:
        return classify_ticket(request.text)

    except APITimeoutError:
        raise HTTPException(
            status_code=504,
            detail={
                "code": "MODEL_TIMEOUT",
                "message": "模型响应超时，请稍后重试",
            },
        ) from None

    except APIConnectionError:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "MODEL_CONNECTION_ERROR",
                "message": "暂时无法连接模型服务",
            },
        ) from None

    except APIStatusError as error:
        # 上游认证、余额或限流问题，不应归咎于工单提交者
        unavailable = error.status_code in {401, 402, 403, 429}

        raise HTTPException(
            status_code=503 if unavailable else 502,
            detail={
                "code": "MODEL_UNAVAILABLE",
                "message": "模型服务暂时不可用",
            },
        ) from None

    except ValueError:
        # 当前模块的配置错误和输出校验错误都可能抛出ValueError
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CLASSIFICATION_ERROR",
                "message": "分类服务暂时无法完成请求",
            },
        ) from None