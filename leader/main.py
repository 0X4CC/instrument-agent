# -*- coding: utf-8 -*-
"""
AIP Leader · 运维调度（三 Partner 并发编排）

流程（三阶段，每阶段内并发）：
    阶段 1  状态采集 Partner  ← 按机组并发拉取状态
    阶段 2  故障诊断 Partner  ← 对每台异常仪器并发诊断
    阶段 3  维护资源 Partner  ← 对每个故障并发查手册/备件/工单
    汇总    并给出「并发 vs 串行」耗时对比

先启动三个 Partner（三个终端）：
    uv run uvicorn partners.status_server:app   --port 8011
    uv run uvicorn partners.main:app            --port 8012
    uv run uvicorn partners.resource_server:app --port 8013

再跑 Leader：
    uv run python -m leader.main
    uv run python -m leader.main --serial      # 串行跑，用于对比
"""

import asyncio
import logging
import sys
import time
import uuid

from acps_sdk.aip.aip_base_model import TaskState, TextDataItem
from acps_sdk.aip.aip_rpc_client import AipRpcClient

logging.basicConfig(level=logging.WARNING, format="%(levelname)-8s %(message)s")

状态URL = "http://127.0.0.1:8012/rpc"
诊断URL = "http://127.0.0.1:8011/rpc"
资源URL = "http://127.0.0.1:8013/rpc"

机组列表 = ["A 机组", "B 机组", "C 机组", "D 机组"]


def 取正文(task) -> str:
    parts = []
    for item in task.status.dataItems or []:
        if isinstance(item, TextDataItem) and item.text:
            parts.append(item.text)
    return "\n".join(parts)


def 从正文提异常(正文: str) -> list[tuple[str, str]]:
    """
    从状态采集的正文里抠出 (仪器编号, 错误码)。

    状态行格式：`CEN-01   高速冷冻离心机 A-01      E-201`
    只保留有错误码的行（「正常」行没有 E- 开头的码）。
    """
    结果: list[tuple[str, str]] = []
    for line in 正文.split("\n"):
        parts = line.split()
        if len(parts) >= 3 and parts[-1].startswith("E-"):
            编号, 码 = parts[0], parts[-1]
            if (编号, 码) not in 结果:
                结果.append((编号, 码))
    return 结果


async def 一次调用(client: AipRpcClient, 文本: str, 会话: str) -> tuple[str, float]:
    t0 = time.perf_counter()
    task = await client.start_task(session_id=会话, user_input=文本)
    dt = (time.perf_counter() - t0) * 1000
    # 验收：Leader 必须显式 complete
    if task.status.state == TaskState.AwaitingCompletion:
        await client.complete_task(task.taskId, 会话)
    return 取正文(task), dt


async def 并发(all_coros):
    return await asyncio.gather(*all_coros)


async def 串行(all_coros_fn):
    out = []
    for fn in all_coros_fn:
        out.append(await fn())
    return out


async def 编排(串行模式: bool = False) -> None:
    会话 = f"s-{uuid.uuid4().hex[:6]}"

    # SDK 2.2.0 起客户端也默认开启身份绑定（要求 expected_partner_aic）；
    # 我们还没领证书，先关闭。拿到 AIC 后改回 True 并传 expected_partner_aic。
    def 建客户端(url: str) -> AipRpcClient:
        return AipRpcClient(url, leader_id="ops-leader", identity_binding_enabled=False)

    c状态 = 建客户端(状态URL)
    c诊断 = 建客户端(诊断URL)
    c资源 = 建客户端(资源URL)

    try:
        print()
        print("=" * 62)
        print("运维调度 Leader · 多智能体并发编排" + ("（串行模式）" if 串行模式 else ""))
        print("=" * 62)

        # ── 阶段 1：状态采集（按机组并发） ──────────────────────────
        print(f"\n【阶段 1】状态采集 → {len(机组列表)} 个机组")
        t1 = time.perf_counter()
        if 串行模式:
            r1 = await 串行([(lambda g=g: 一次调用(c状态, g, 会话)) for g in 机组列表])
        else:
            r1 = await 并发([一次调用(c状态, g, 会话) for g in 机组列表])
        d1 = (time.perf_counter() - t1) * 1000

        异常: list[tuple[str, str]] = []
        for 正文, _ in r1:
            for line in 正文.split("\n"):
                if "  E-" in line:
                    print(f"    {line.strip()}")
            异常.extend(从正文提异常(正文))
        print(f"    └ 阶段耗时 {d1:.1f} ms，发现异常 {len(异常)} 项")

        # ── 阶段 2：故障诊断（按仪器编号并发） ──────────────────────
        print(f"\n【阶段 2】故障诊断 → {len(异常)} 台异常仪器")
        t2 = time.perf_counter()
        if 串行模式:
            r2 = await 串行([(lambda i=i: 一次调用(c诊断, i, 会话)) for i, _ in 异常])
        else:
            r2 = await 并发([一次调用(c诊断, i, 会话) for i, _ in 异常])
        d2 = (time.perf_counter() - t2) * 1000
        for 正文, _ in r2:
            首行 = 正文.split("\n")[0] if 正文 else ""
            print(f"    {首行}")
        print(f"    └ 阶段耗时 {d2:.1f} ms")

        # ── 阶段 3：维护资源（按错误码并发） ────────────────────────
        错误码 = [c for _, c in 异常]
        print(f"\n【阶段 3】维护资源 → {len(错误码)} 份档案")
        t3 = time.perf_counter()
        if 串行模式:
            r3 = await 串行([(lambda c=c: 一次调用(c资源, c, 会话)) for c in 错误码])
        else:
            r3 = await 并发([一次调用(c资源, c, 会话) for c in 错误码])
        d3 = (time.perf_counter() - t3) * 1000
        for 正文, _ in r3:
            for line in 正文.split("\n"):
                if "手册参考" in line or "预计工时" in line:
                    print(f"    {line.strip()}")
        print(f"    └ 阶段耗时 {d3:.1f} ms")

        print()
        print("=" * 62)
        print(f"总耗时：{d1 + d2 + d3:.1f} ms")
        print("=" * 62)
        print()

    finally:
        for c in (c状态, c诊断, c资源):
            await c.close()


def main() -> int:
    串行模式 = "--serial" in sys.argv
    try:
        asyncio.run(编排(串行模式))
    except Exception as e:
        logging.error("编排失败：%s", e)
        logging.error("确认三个 Partner 都启动了：8011 / 8012 / 8013")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
