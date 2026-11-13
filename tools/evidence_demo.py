# -*- coding: utf-8 -*-
"""一键打印四环节留档（用于截图做 PPT / 佐证）。

用法（在 instrument-agent 目录下）：
    uv run python tools/evidence_demo.py

输出四块：
    ① 注册状态（平台返回的 APPROVED + AIC）
    ② 发现结果（discover query）
    ③ 本作品被调（AIP 直连自测，非叮当）
    ④ 跨智能体互联 + 访问（校园报修调度）
"""
import asyncio
import json
import ssl
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from acps_sdk.aip.aip_base_model import TaskState, TextDataItem
from acps_sdk.aip.aip_rpc_client import AipRpcClient

ROOT = Path(__file__).resolve().parent.parent
OUR_URL = "https://YOUR_SERVER_IP:8011/rpc"
REPAIR_URL = "http://47.106.182.157:9031/rpc"

BAR = "=" * 66


def cli(*args: str) -> str:
    """调用 acps-cli 并返回 stdout。"""
    r = subprocess.run(
        ["uv", "run", "acps-cli", "--config", "acps-cli.toml", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return r.stdout


def 取正文(task) -> str:
    parts = []
    for p in task.products or []:
        for d in p.dataItems or []:
            if isinstance(d, TextDataItem) and d.text:
                parts.append(d.text)
    return "\n".join(parts)


async def 调用(url: str, 文本: str, insecure: bool = False):
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    c = AipRpcClient(url, leader_id="evidence", ssl_context=ctx, identity_binding_enabled=False)
    try:
        t = await c.start_task(session_id="s-evidence", user_input=文本)
        state = t.status.state.value if hasattr(t.status.state, "value") else t.status.state
        body = 取正文(t)
        if t.status.state == TaskState.AwaitingCompletion:
            await c.complete_task(t.taskId, "s-evidence")
        return state, t.taskId, body
    finally:
        await c.close()


def 标题(n: int, text: str) -> None:
    print()
    print(BAR)
    print(f"  {n}. {text}")
    print(BAR)


def main() -> int:
    now = datetime.now(timezone(timedelta(hours=8)))
    print(BAR)
    print("  异构科研仪器智能运维协同体 · 平台验证留档")
    print(f"  时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）")
    print(BAR)

    # ① 注册
    标题(1, "注册 · 平台返回")
    items = json.loads(cli("agent", "list", "--json"))["items"]
    for i in items:
        print(f"  名称：{i['name']}")
        print(f"  版本：{i['version']}")
        print(f"  状态：{i['approval_status']}")
        print(f"  AIC ：{i['aic']}")
        print(f"  提交：{i.get('submitted_at', '')}")

    # ② 发现
    标题(2, "发现 · discover query「仪器故障诊断」")
    d = json.loads(cli("discover", "query", "仪器故障诊断"))
    acs = (d.get("result") or {}).get("acsMap") or {}
    for aic, v in acs.items():
        mark = "  ← 本作品" if "05I1" in aic else ""
        print(f"  {v.get('name', '')}")
        print(f"    AIC={aic}  active={v.get('active')}{mark}")

    # ③ 本作品被调（AIP 直连自测）
    标题(3, "本作品被调 · AIP 直连自测（非叮当）")
    state, task_id, body = asyncio.run(调用(OUR_URL, "CEN-01", insecure=True))
    print(f"  输入：CEN-01")
    print(f"  状态：{state}")
    print(f"  taskId：{task_id}")
    print()
    for line in body.splitlines():
        print("  " + line)

    # ④ 互联 + 访问
    标题(4, "互联 + 访问 · 调用「校园报修调度智能体」")
    state, task_id, body = asyncio.run(调用(REPAIR_URL, "宿舍空调不制冷，三楼 302，比较紧急"))
    print(f"  输入：宿舍空调不制冷，三楼 302，比较紧急")
    print(f"  状态：{state}")
    print(f"  taskId：{task_id}")
    print()
    for line in body.splitlines():
        print("  " + line)

    print()
    print(BAR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
