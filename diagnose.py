# -*- coding: utf-8 -*-
"""
科研仪器智能运维 · 故障诊断引擎（台阶 1：命令行版）

用法：
    cd research-agent
    uv run python diagnose.py                    # 诊断全部仪器
    uv run python diagnose.py CEN-01             # 只诊断一台

这份脚本只做一件事：读仪器状态 + 故障规则 → 输出诊断结论。
不依赖网络，不依赖大模型，结果确定、可复现。
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

# =============================================================================
# 日志配置
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


# =============================================================================
# 数据模型（Pydantic —— 阶段 2.2 学的）
# =============================================================================


class 仪器状态(BaseModel):
    """一台仪器当前上报的状态。字段都是可选的——不同仪器的传感器不一样。"""

    running: bool = False
    error_code: Optional[str] = None

    # 离心机
    vibration_mm_s: Optional[float] = None
    rotor_temp_c: Optional[float] = None
    speed_rpm: Optional[int] = None

    # 分光光度计
    lamp_hours: Optional[int] = None
    baseline_drift_abs: Optional[float] = None
    wavelength_error_nm: Optional[float] = None

    # 培养箱
    temp_deviation_c: Optional[float] = None
    humidity_rh: Optional[float] = None
    door_open_seconds: Optional[int] = None


class 仪器(BaseModel):
    id: str
    name: str
    device_type: str
    model: Optional[str] = None
    vendor: Optional[str] = None
    group: Optional[str] = None          # 所属机组（如「A 机组 · 离心机室」）
    status: 仪器状态


class 故障规则(BaseModel):
    """
    一条故障码规则：错误码 + 传感器条件佐证。

    `checks` 支持两种写法（向后兼容）：

        # 简写：等价于 {"gt": 5.0}
        "checks": {"vibration_mm_s": 5.0}

        # 完整写法：支持多种比较
        "checks": {
            "vibration_mm_s": {"gt": 5.0},
            "rotor_temp_c":   {"between": [0, 10]},
            "speed_rpm":      {"le": 15000}
        }

    支持的操作符：

        gt      大于            lt      小于
        ge      大于等于        le      小于等于
        eq      等于            ne      不等于
        between [下限, 上限]    注意：两端都包含
    """

    code: str
    device_type: str
    name: str
    severity: str
    checks: dict[str, Any] = Field(default_factory=dict)
    cause: str
    action: str
    manual: str = ""


class 候选(BaseModel):
    """差鉴别诊断里的一个"被排除的候选"。"""

    故障: str
    错误码: str
    理由: str


class 诊断结论(BaseModel):
    """诊断结果。"""

    instrument_id: str
    instrument_name: str
    error_code: Optional[str]
    conclusion: str        # 正常 / 确诊 / 疑似 / 排除 / 未知故障
    confidence: int = 0    # 0–100，传感器对错误码的佐证完整度
    fault_name: str = ""
    severity: str = ""
    cause: str = ""
    action: str = ""
    manual: str = ""
    evidence: list[str] = Field(default_factory=list)
    alternatives: list[候选] = Field(default_factory=list)


# =============================================================================
# 读取数据（阶段 2.3 + 2.4 学的）
# =============================================================================


class 数据读不了(Exception):
    """数据文件读不出来"""


def 读json(path: Path) -> list[dict[str, Any]]:
    """读一个 JSON 文件，失败时抛出带说明的异常。"""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise 数据读不了(f"文件不存在：{path}") from e
    except UnicodeDecodeError as e:
        raise 数据读不了(f"编码不对，应该用 UTF-8：{path}") from e

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise 数据读不了(f"JSON 格式有错（第 {e.lineno} 行第 {e.colno} 列）：{path}") from e

    if not isinstance(data, list):
        raise 数据读不了(f"顶层应该是列表，实际是 {type(data).__name__}：{path}")

    return data


def 加载规则() -> list[故障规则]:
    raw = 读json(DATA_DIR / "faults.json")
    try:
        return [故障规则.model_validate(item) for item in raw]
    except ValidationError as e:
        raise 数据读不了(f"faults.json 结构不对：{e.errors()[0]['msg']}") from e


def 加载仪器() -> list[仪器]:
    raw = 读json(DATA_DIR / "instruments.json")
    try:
        return [仪器.model_validate(item) for item in raw]
    except ValidationError as e:
        raise 数据读不了(f"instruments.json 结构不对：{e.errors()[0]['msg']}") from e


# =============================================================================
# 诊断逻辑 —— 这是整套系统的核心
# =============================================================================


def 找规则(inst: 仪器, rules: list[故障规则]) -> Optional[故障规则]:
    """按错误码 + 设备类型找规则。同一错误码在不同设备上含义可能不同，所以要两个都匹配。"""
    for r in rules:
        if r.code == inst.status.error_code and r.device_type == inst.device_type:
            return r
    return None


def _评估一个条件(实际值: float, 条件: Any) -> tuple[bool, str]:
    """
    评估单个条件。返回 (是否满足, 人话说明)。

    条件可以是数字（等价于 gt），也可以是 {"操作符": 值}。
    """
    # 简写：数字 → gt
    if isinstance(条件, (int, float)):
        return 实际值 > 条件, f"> {条件}"

    if not isinstance(条件, dict) or len(条件) != 1:
        return False, f"条件格式无法识别：{条件!r}"

    操作符, 目标 = next(iter(条件.items()))

    if 操作符 == "gt":
        return 实际值 > 目标, f"> {目标}"
    if 操作符 == "ge":
        return 实际值 >= 目标, f"≥ {目标}"
    if 操作符 == "lt":
        return 实际值 < 目标, f"< {目标}"
    if 操作符 == "le":
        return 实际值 <= 目标, f"≤ {目标}"
    if 操作符 == "eq":
        return 实际值 == 目标, f"= {目标}"
    if 操作符 == "ne":
        return 实际值 != 目标, f"≠ {目标}"
    if 操作符 == "between":
        if not isinstance(目标, (list, tuple)) or len(目标) != 2:
            return False, f"between 需要 [下限, 上限]：{目标!r}"
        下限, 上限 = 目标
        return 下限 <= 实际值 <= 上限, f"在 [{下限}, {上限}] 区间内"

    return False, f"未知操作符：{操作符}"


def 评估佐证(inst: 仪器, rule: 故障规则) -> tuple[int, list[str]]:
    """
    用传感器数据评估"错误码的可信度"。

    返回 (置信度 0–100, 证据说明列表)。

    置信度 = 条件满足的比例。
        - 规则没写 checks        → 100（只凭错误码判断，无佐证条件）
        - 所有条件都满足          → 100
        - 一半条件满足            → 50
        - 一个都不满足            → 0
    """
    status = inst.status.model_dump()

    if not rule.checks:
        return 100, ["规则未定义传感器条件，仅凭错误码判断（无佐证数据）"]

    evidence: list[str] = []
    通过数 = 0

    for 字段, 条件 in rule.checks.items():
        实际值 = status.get(字段)
        if 实际值 is None:
            evidence.append(f"{字段}：仪器未上报，无法佐证")
            continue

        满足, 说明 = _评估一个条件(实际值, 条件)
        if 满足:
            通过数 += 1
            evidence.append(f"{字段}：{实际值} {说明} ✅ 满足")
        else:
            evidence.append(f"{字段}：{实际值} 不满足 {说明} ⚠️")

    置信度 = round(100 * 通过数 / len(rule.checks))
    evidence.append(f"佐证完整度：{通过数}/{len(rule.checks)} → 置信度 {置信度}")
    return 置信度, evidence


def 差鉴别(inst: 仪器, rule: 故障规则, rules: list[故障规则]) -> list[候选]:
    """
    差鉴别诊断：列出同类型设备的【其它候选故障】，并说明为什么不是它。

    这是专家系统的经典做法——不只回答"是什么"，也回答"为什么不是别的"。
    """
    结果: list[候选] = []
    for other in rules:
        if other.code == rule.code or other.device_type != inst.device_type:
            continue
        if other.code == inst.status.error_code:
            continue
        结果.append(
            候选(
                故障=other.name,
                错误码=other.code,
                理由=f"错误码不匹配（仪器上报 {inst.status.error_code}，该故障对应 {other.code}）",
            )
        )
    return 结果[:5]


def 诊断(inst: 仪器, rules: list[故障规则]) -> 诊断结论:
    """对一台仪器做诊断。"""
    code = inst.status.error_code

    # 情况一：没有错误码 → 正常
    if code is None:
        return 诊断结论(
            instrument_id=inst.id,
            instrument_name=inst.name,
            error_code=None,
            conclusion="正常",
            evidence=[f"未上报错误码；运行状态 = {'运行中' if inst.status.running else '停机'}"],
        )

    # 情况二：有错误码，但规则库里没有 → 未知故障
    rule = 找规则(inst, rules)
    if rule is None:
        logger.warning("%s：错误码 %s 未收录在规则库中", inst.id, code)
        return 诊断结论(
            instrument_id=inst.id,
            instrument_name=inst.name,
            error_code=code,
            conclusion="未知故障",
            evidence=[f"错误码 {code} 不在规则库（共 {len(rules)} 条）中，需人工排查"],
        )

    # 情况三：有规则 → 用传感器数据评估置信度
    置信度, evidence = 评估佐证(inst, rule)
    其它候选 = 差鉴别(inst, rule, rules)

    # 按置信度分级：≥80 确诊 / ≥40 疑似 / <40 排除（错误码疑似误报）
    if 置信度 >= 80:
        结论 = "确诊"
        严重度 = rule.severity
    elif 置信度 >= 40:
        结论 = "疑似"
        严重度 = f"{rule.severity}（待确认）"
    else:
        结论 = "排除"
        严重度 = "—"
        evidence = evidence + [
            "传感器数据与错误码矛盾，判断为【误报】——建议先复查传感器或通信链路，不要直接换件"
        ]

    return 诊断结论(
        instrument_id=inst.id,
        instrument_name=inst.name,
        error_code=code,
        conclusion=结论,
        confidence=置信度,
        fault_name=rule.name,
        severity=严重度,
        cause=rule.cause,
        action=rule.action,
        manual=rule.manual,
        evidence=evidence,
        alternatives=其它候选,
    )


# =============================================================================
# 输出
# =============================================================================

结论标记 = {"正常": "🟢", "确诊": "🔴", "疑似": "🟡", "排除": "🔵", "未知故障": "⚪"}


def 打印结论(d: 诊断结论) -> None:
    行 = "=" * 56
    print()
    print(行)
    print(f"{结论标记.get(d.conclusion, '·')} {d.instrument_name}（{d.instrument_id}）")
    print(f"   错误码：{d.error_code or '无'}")
    print("-" * 56)
    置信 = f"（置信度 {d.confidence}）" if d.confidence else ""
    print(f"   结论：{d.conclusion}{置信}")

    if d.fault_name:
        print(f"   故障：{d.fault_name}")
    if d.severity:
        print(f"   严重度：{d.severity}")

    print("   依据：")
    for e in d.evidence:
        print(f"     · {e}")

    if d.cause:
        print(f"   可能原因：{d.cause}")
    if d.action:
        print(f"   处置建议：{d.action}")
    if d.manual:
        print(f"   参考：{d.manual}")

    if d.alternatives:
        print("   差鉴别（为什么不是别的）：")
        for c in d.alternatives:
            print(f"     ✗ {c.故障}（{c.错误码}）：{c.理由}")

    print(行)


def 打印汇总(results: list[诊断结论]) -> None:
    计数: dict[str, int] = {}
    for r in results:
        计数[r.conclusion] = 计数.get(r.conclusion, 0) + 1

    print()
    print("=" * 56)
    print(f"巡诊汇总：共 {len(results)} 台仪器")
    for 名 in ["正常", "确诊", "疑似", "排除", "未知故障"]:
        if 名 in 计数:
            print(f"   {结论标记[名]} {名}：{计数[名]} 台")
    print("=" * 56)


# =============================================================================
# 入口
# =============================================================================


def main() -> int:
    try:
        rules = 加载规则()
        instruments = 加载仪器()
    except 数据读不了 as e:
        logger.error(str(e))
        return 1

    logger.info("加载完成：%d 条故障规则，%d 台仪器", len(rules), len(instruments))

    # 支持只诊断指定仪器
    目标 = sys.argv[1] if len(sys.argv) > 1 else None
    if 目标:
        instruments = [i for i in instruments if i.id == 目标 or i.name == 目标]
        if not instruments:
            logger.error("找不到仪器：%s", 目标)
            return 1

    results = [诊断(inst, rules) for inst in instruments]

    for d in results:
        打印结论(d)

    打印汇总(results)

    # 有确诊的 → 返回 1，方便脚本判断
    return 1 if any(d.conclusion == "确诊" for d in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
