# -*- coding: utf-8 -*-
"""演示用：以 AIP 协议调用平台上的另一个智能体（视频第 4 段）。

用法：
    uv run python tools/demo_call_agent.py <rpc 地址> <输入文本>

例：
    uv run python tools/demo_call_agent.py http://47.106.182.157:9031/rpc "宿舍空调不制冷，三楼 302，比较紧急"
"""
import asyncio
import ssl
import sys

from acps_sdk.aip.aip_base_model import TaskState, TextDataItem
from acps_sdk.aip.aip_rpc_client import AipRpcClient


async def 调用(url: str, 文本: str, 跳过证书校验: bool = False) -> None:
    会话 = "s-demo-call"
    ctx = None
    if 跳过证书校验:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    客户端 = AipRpcClient(
        url, leader_id="ops-leader", ssl_context=ctx, identity_binding_enabled=False
    )
    try:
        print(f"→ 调用 {url}")
        print(f"  输入：{文本}")
        任务 = await 客户端.start_task(session_id=会话, user_input=文本)
        状态 = 任务.status.state.value if hasattr(任务.status.state, "value") else 任务.status.state
        print(f"← state = {状态}　taskId = {任务.taskId}")
        for 产品 in 任务.products or []:
            for 条目 in 产品.dataItems or []:
                if isinstance(条目, TextDataItem) and 条目.text:
                    print()
                    print(条目.text)
        if 任务.status.state == TaskState.AwaitingCompletion:
            await 客户端.complete_task(任务.taskId, 会话)
            print("\n（已发送 complete 验收）")
    finally:
        await 客户端.close()


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2
    跳过证书校验 = "--insecure" in args
    url = args[0]
    文本 = " ".join(a for a in args[1:] if a != "--insecure")
    asyncio.run(调用(url, 文本, 跳过证书校验))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
