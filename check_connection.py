import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def main():
    # 从当前代码文件所在目录读取 .env
    env_path = Path(__file__).with_name(".env")
    load_dotenv(env_path)

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip()

    if not api_key:
        raise ValueError("没有读取到 API Key，请检查项目根目录的 .env")

    # 创建调用客户端；失败时不自动重试，便于观察第一次请求
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=0,
    )

    # 发送一次简短请求
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "请只回复：连接成功"}
        ],
        max_tokens=32,
        extra_body={"thinking": {"type": "disabled"}},
    )

    print("接口返回：", response.choices[0].message.content)

    if response.usage:
        print("本次总 Token 数：", response.usage.total_tokens)


if __name__ == "__main__":
    main()