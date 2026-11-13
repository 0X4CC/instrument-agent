# -*- coding: utf-8 -*-
"""数据文件校验测试。

目的：**防止手改 JSON 改坏**——字段拼错、类型写错、规则重复，
这些都是运行时才会炸、而且报错不直观的问题。
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from diagnose import 故障规则, 仪器, 仪器状态

数据目录 = Path(__file__).resolve().parent.parent / "data"
项目根 = 数据目录.parent


def 读(name: str):
    return json.loads((数据目录 / name).read_text(encoding="utf-8"))


规则列表 = 读("faults.json")
仪器列表 = 读("instruments.json")

合法严重度 = {"低", "中", "高", "紧急"}
合法操作符 = {"gt", "ge", "lt", "le", "eq", "ne", "between"}
状态字段 = set(仪器状态.model_fields.keys())


# =============================================================================
# 一、结构合法
# =============================================================================


def test_faults_顶层是列表():
    assert isinstance(规则列表, list)
    assert len(规则列表) > 0


def test_instruments_顶层是列表():
    assert isinstance(仪器列表, list)
    assert len(仪器列表) > 0


@pytest.mark.parametrize("原始", 规则列表, ids=lambda r: r.get("code", "?"))
def test_每条规则都能被模型接受(原始):
    try:
        故障规则.model_validate(原始)
    except ValidationError as e:
        pytest.fail(f"规则 {原始.get('code')} 结构不对：{e.errors()[0]['msg']}")


@pytest.mark.parametrize("原始", 仪器列表, ids=lambda r: r.get("id", "?"))
def test_每台仪器都能被模型接受(原始):
    try:
        仪器.model_validate(原始)
    except ValidationError as e:
        pytest.fail(f"仪器 {原始.get('id')} 结构不对：{e.errors()[0]['msg']}")


# =============================================================================
# 二、规则内容合法
# =============================================================================


def test_规则code不重复():
    组合 = [(r["code"], r["device_type"]) for r in 规则列表]
    重复 = {x for x in 组合 if 组合.count(x) > 1}
    assert not 重复, f"同一设备类型下错误码重复：{重复}"


def test_严重度取值合法():
    for r in 规则列表:
        assert r["severity"] in 合法严重度, f"{r['code']} 的严重度 {r['severity']!r} 不合法"


def test_必填文本字段非空():
    for r in 规则列表:
        for 字段 in ("name", "cause", "action"):
            assert str(r.get(字段, "")).strip(), f"{r['code']} 的 {字段} 是空的"


def test_checks的字段名都是仪器状态里存在的():
    """写错字段名 = 永远匹配不到，而且不报错。这是最容易踩的坑。"""
    for r in 规则列表:
        for 字段 in r.get("checks", {}):
            assert 字段 in 状态字段, f"{r['code']} 用了不存在的传感器字段：{字段}"


def test_checks的操作符合法():
    for r in 规则列表:
        for 字段, 条件 in r.get("checks", {}).items():
            if isinstance(条件, (int, float)):
                continue                      # 简写
            assert isinstance(条件, dict), f"{r['code']}.{字段} 条件格式不对"
            assert len(条件) == 1, f"{r['code']}.{字段} 只能写一个操作符"
            操作符 = next(iter(条件))
            assert 操作符 in 合法操作符, f"{r['code']}.{字段} 未知操作符：{操作符}"


def test_between的上限大于下限():
    for r in 规则列表:
        for 字段, 条件 in r.get("checks", {}).items():
            if isinstance(条件, dict) and "between" in 条件:
                下限, 上限 = 条件["between"]
                assert 下限 <= 上限, f"{r['code']}.{字段} 的区间写反了"


# =============================================================================
# 三、两个文件之间对得上
# =============================================================================


def test_仪器的设备类型都在规则库里出现过():
    """否则这台仪器的错误码永远匹配不到规则。"""
    规则类型 = {r["device_type"] for r in 规则列表}
    for i in 仪器列表:
        assert i["device_type"] in 规则类型, (
            f"仪器 {i['id']} 的设备类型 {i['device_type']!r} 在规则库里没有"
        )


def test_仪器的错误码要么是null要么是字符串():
    for i in 仪器列表:
        code = i["status"].get("error_code")
        assert code is None or isinstance(code, str), f"{i['id']} 的 error_code 类型不对"


# =============================================================================
# 四、acs.json
# =============================================================================


def test_acs_json合法且字段齐全():
    p = 项目根 / "partners" / "online" / "instrument_diagnosis" / "acs.json"
    acs = json.loads(p.read_text(encoding="utf-8"))

    必需 = {
        "aic", "active", "lastModifiedTime", "protocolVersion", "name",
        "description", "version", "provider", "endPoints",
        "defaultInputModes", "defaultOutputModes", "skills",
    }
    缺 = 必需 - set(acs)
    assert not 缺, f"acs.json 缺少字段：{缺}"


def test_acs的skills结构完整():
    p = 项目根 / "partners" / "online" / "instrument_diagnosis" / "acs.json"
    acs = json.loads(p.read_text(encoding="utf-8"))
    assert acs["skills"], "skills 不能为空"
    for s in acs["skills"]:
        for 字段 in ("id", "name", "description"):
            assert s.get(字段), f"skill 缺少 {字段}"
        assert isinstance(s.get("examples", []), list)


def test_acs不含校名等敏感信息():
    p = 项目根 / "partners" / "online" / "instrument_diagnosis" / "acs.json"
    全文 = p.read_text(encoding="utf-8")
    for w in ("大学", "学院", "学校", "指导教师"):
        assert w not in 全文, f"acs.json 里出现了敏感词「{w}」"
