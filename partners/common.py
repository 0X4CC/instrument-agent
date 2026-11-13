# -*- coding: utf-8 -*-
"""
三个 Partner 共用的 AIP 服务壳。

把「怎么把业务函数接成 AIP Partner」这一步抽出来，
每个 Partner 只关心自己的 `on_start` 业务逻辑。
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from fastapi import FastAPI, Request

from acps_sdk.aip.aip_base_model import (
    Product,
    TaskCommand,
    TaskResult,
    TaskState,
    TextDataItem,
)
from acps_sdk.aip.aip_rpc_model import RpcResponse
from acps_sdk.aip.aip_rpc_server import (
    CommandHandlers,
    DefaultHandlers,
    TaskManager,
    handle_rpc_request,
)

logger = logging.getLogger(__name__)

# 让 Partner 能 import 到项目根目录的 diagnose.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

业务函数 = Callable[[str], tuple[str, dict[str, Any]]]
"""业务函数签名：输入文本 -> (给人看的正文, 给机器看的数据)"""


def 取输入文本(command: TaskCommand) -> str:
    """从 TaskCommand 的 dataItems 里把文本拼出来。"""
    parts = []
    for item in command.dataItems or []:
        if isinstance(item, TextDataItem) and item.text:
            parts.append(item.text)
    return " ".join(parts).strip()


def 建AIP应用(
    名称: str,
    描述: str,
    业务: 业务函数,
    产品名: str,
) -> FastAPI:
    """
    用一行调用，把一个「文本 -> (正文, 数据)」的业务函数变成 AIP Partner。

    - 自动处理 start 语义（幂等）
    - 自动把结果塞进 products 和 status.dataItems
    - 自动把状态推进到 awaiting-completion（等 Leader 显式 complete）
    """

    async def on_start(command: TaskCommand, task: Optional[TaskResult]) -> TaskResult:
        task = await DefaultHandlers.start(command, task)
        if task.status.state != TaskState.Accepted:
            return task

        文本 = 取输入文本(command)

        # 模拟「与仪器通信」的耗时（串口 / Modbus / 厂商 SDK 通常 100–500 ms）。
        # 默认 0，开启方式：PARTNER_LATENCY_MS=200
        # ⚠️ 这是【模拟】延迟，不是真实仪器耗时，报告里要如实标注。
        延迟ms = int(os.getenv("PARTNER_LATENCY_MS", "0") or 0)
        if 延迟ms > 0:
            await asyncio.sleep(延迟ms / 1000)

        try:
            正文, 数据 = 业务(文本)
        except Exception as e:                      # 业务出错不让服务崩
            logger.exception("%s 业务处理失败", 名称)
            正文 = f"处理失败：{e}"
            数据 = {"error": str(e)}

        logger.info("[%s] 处理完成：%r -> %d 字", 名称, 文本[:20], len(正文))

        product = Product(
            id=f"{名称}-{task.taskId}",
            name=产品名,
            description=正文.split("\n")[0][:60],
            dataItems=[TextDataItem(text=正文)],
        )
        TaskManager.set_products(task.taskId, [product])

        return TaskManager.update_task_status(
            task.taskId,
            TaskState.AwaitingCompletion,
            data_items=[TextDataItem(text=正文)],
        )

    handlers = CommandHandlers(on_start=on_start)

    app = FastAPI(title=名称, description=描述, version="0.1.0",
                  docs_url=None, redoc_url=None)

    @app.post("/rpc", response_model=None)
    async def rpc(request: Request) -> RpcResponse:
        # SDK 2.2.0 起默认要求 mTLS 身份绑定；尚未领证，先关闭
        return await handle_rpc_request(
            request, handlers, local_aic=None, identity_binding_enabled=False
        )

    @app.get("/health", summary="健康检查")
    def health() -> dict:
        return {"status": "ok", "role": "partner", "service": 名称}

    return app
