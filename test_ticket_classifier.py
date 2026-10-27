import pytest

from ticket_classifier import validate_input, parse_result


def test_valid_input():
    """正常工单可以通过，并去掉首尾空白。"""
    result = validate_input("  Wi-Fi连接不上  ")

    assert result == "Wi-Fi连接不上"


@pytest.mark.parametrize(
    "text",
    [
        "",           # 空字符串
        "   ",        # 只有空格
        None,         # 空值，不是字符串
        123,          # 数字，不是字符串
        "测" * 2001,  # 超过长度限制
    ],
    ids=["empty", "spaces", "none", "number", "too_long"],
)
def test_invalid_input(text):
    """这些输入都应该被明确拒绝。"""
    with pytest.raises(ValueError):
        validate_input(text)


def test_input_length_boundary():
    """恰好2000个字符应当被允许。"""
    text = "测" * 2000

    assert validate_input(text) == text


def test_valid_model_output():
    """符合约定的JSON应转换为字典。"""
    content = '{"category": "网络", "reason": "无法连接Wi-Fi"}'

    result = parse_result(content)

    assert result == {
        "category": "网络",
        "reason": "无法连接Wi-Fi",
    }


@pytest.mark.parametrize(
    "content",
    [
        "",
        "这不是JSON",
        "[]",
        '{"category": "网络"}',
        '{"category": "硬件", "reason": "电脑故障"}',
        '{"category": "网络", "reason": ""}',
    ],
    ids=[
        "empty_response",
        "invalid_json",
        "wrong_structure",
        "missing_reason",
        "unknown_category",
        "empty_reason",
    ],
)
def test_invalid_model_output(content):
    """不符合输出约定的数据应被拒绝。"""
    with pytest.raises(ValueError):
        parse_result(content)