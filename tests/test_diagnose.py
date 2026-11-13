# -*- coding: utf-8 -*-
"""诊断引擎的单元测试。

运行：
    uv run pytest -v
"""

import pytest

from diagnose import (
    仪器,
    仪器状态,
    故障规则,
    诊断,
    评估佐证,
    _评估一个条件,
    差鉴别,
)


# =============================================================================
# 测试用的构造助手
# =============================================================================


def 造仪器(**状态) -> 仪器:
    return 仪器(
        id="TEST-01",
        name="测试仪器",
        device_type="离心机",
        status=仪器状态(**状态),
    )


def 造规则(**kw) -> 故障规则:
    默认 = dict(
        code="E-T01",
        device_type="离心机",
        name="测试故障",
        severity="中",
        checks={},
        cause="测试原因",
        action="测试处置",
    )
    默认.update(kw)
    return 故障规则(**默认)


# =============================================================================
# 一、结论分级
# =============================================================================


def test_没有错误码判为正常():
    d = 诊断(造仪器(error_code=None, running=True), [])
    assert d.conclusion == "正常"
    assert d.error_code is None


def test_错误码不在规则库判为未知故障():
    d = 诊断(造仪器(error_code="E-999"), [造规则(code="E-T01")])
    assert d.conclusion == "未知故障"
    assert d.confidence == 0
    assert "不在规则库" in d.evidence[0]


def test_条件全满足判为确诊且置信度100():
    inst = 造仪器(error_code="E-T01", vibration_mm_s=8.2)
    rule = 造规则(checks={"vibration_mm_s": 5.0})
    d = 诊断(inst, [rule])
    assert d.conclusion == "确诊"
    assert d.confidence == 100
    assert d.fault_name == "测试故障"


def test_条件全不满足判为排除且置信度0():
    inst = 造仪器(error_code="E-T01", vibration_mm_s=1.0)
    rule = 造规则(checks={"vibration_mm_s": 5.0})
    d = 诊断(inst, [rule])
    assert d.conclusion == "排除"
    assert d.confidence == 0


def test_条件部分满足判为疑似且置信度50():
    inst = 造仪器(error_code="E-T01", vibration_mm_s=8.0, rotor_temp_c=4.0)
    rule = 造规则(checks={"vibration_mm_s": 5.0, "rotor_temp_c": {"gt": 15.0}})
    d = 诊断(inst, [rule])
    assert d.conclusion == "疑似"
    assert d.confidence == 50


def test_规则没有条件时直接确诊():
    d = 诊断(造仪器(error_code="E-T01"), [造规则(checks={})])
    assert d.conclusion == "确诊"
    assert d.confidence == 100


# =============================================================================
# 二、操作符
# =============================================================================


@pytest.mark.parametrize(
    "条件,值,期望",
    [
        (5.0, 8.0, True),                      # 简写 = gt
        (5.0, 5.0, False),                     # gt 不含等号
        ({"gt": 5.0}, 5.0, False),
        ({"ge": 5.0}, 5.0, True),              # ge 含等号
        ({"lt": 5.0}, 4.9, True),
        ({"le": 5.0}, 5.0, True),
        ({"eq": 5.0}, 5.0, True),
        ({"ne": 5.0}, 4.0, True),
        ({"between": [0, 10]}, 0, True),       # 区间含两端
        ({"between": [0, 10]}, 10, True),
        ({"between": [0, 10]}, 10.1, False),
    ],
)
def test_操作符(条件, 值, 期望):
    满足, _ = _评估一个条件(值, 条件)
    assert 满足 is 期望


def test_未知操作符返回不满足():
    满足, 说明 = _评估一个条件(5.0, {"乱写": 1})
    assert 满足 is False
    assert "未知操作符" in 说明


# =============================================================================
# 三、数据缺失
# =============================================================================


def test_仪器没上报该字段时不计入通过():
    inst = 造仪器(error_code="E-T01")           # 没有任何传感器值
    rule = 造规则(checks={"vibration_mm_s": 5.0})
    d = 诊断(inst, [rule])
    assert d.confidence == 0
    assert d.conclusion == "排除"
    assert any("未上报" in e for e in d.evidence)


def test_多条件里缺一个字段():
    inst = 造仪器(error_code="E-T01", vibration_mm_s=8.0)
    rule = 造规则(checks={"vibration_mm_s": 5.0, "rotor_temp_c": 10.0})
    d = 诊断(inst, [rule])
    assert d.confidence == 50                    # 1/2
    assert d.conclusion == "疑似"


# =============================================================================
# 四、差鉴别
# =============================================================================


def test_差鉴别只列同设备类型的其它规则():
    inst = 造仪器(error_code="E-T01", vibration_mm_s=8.0)
    目标 = 造规则(code="E-T01", checks={"vibration_mm_s": 5.0})
    同类 = 造规则(code="E-T02", name="另一个离心机故障")
    异类 = 造规则(code="E-T03", name="培养箱故障", device_type="培养箱")

    d = 诊断(inst, [目标, 同类, 异类])
    assert d.conclusion == "确诊"

    名字 = [c.故障 for c in d.alternatives]
    assert "另一个离心机故障" in 名字
    assert "培养箱故障" not in 名字
    assert "测试故障" not in 名字                  # 不列自己


def test_差鉴别给出的理由包含错误码():
    inst = 造仪器(error_code="E-T01", vibration_mm_s=8.0)
    目标 = 造规则(code="E-T01", checks={"vibration_mm_s": 5.0})
    其它 = 造规则(code="E-T02", name="别的故障")

    d = 诊断(inst, [目标, 其它])
    理由 = d.alternatives[0].理由
    assert "E-T01" in 理由 and "E-T02" in 理由


# =============================================================================
# 五、评估佐证
# =============================================================================


def test_评估佐证返回证据说明():
    inst = 造仪器(error_code="E-T01", vibration_mm_s=8.0)
    rule = 造规则(checks={"vibration_mm_s": 5.0})
    分, 证据 = 评估佐证(inst, rule)
    assert 分 == 100
    assert any("vibration_mm_s" in e for e in 证据)
    assert any("佐证完整度" in e for e in 证据)


def test_置信度是满足比例():
    inst = 造仪器(error_code="E-T01", vibration_mm_s=8.0, rotor_temp_c=4.0, speed_rpm=9000)
    rule = 造规则(
        checks={
            "vibration_mm_s": 5.0,     # 8.0 > 5.0   ✅
            "rotor_temp_c": 15.0,      # 4.0 不满足   ❌
            "speed_rpm": {"gt": 15000},# 9000 不满足  ❌
        }
    )
    分, _ = 评估佐证(inst, rule)
    assert 分 == 33                              # 1/3 → 33
