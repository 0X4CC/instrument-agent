# -*- coding: utf-8 -*-
"""
AIP Partner · 科研仪器故障诊断

把 diagnose.py 的诊断能力包成 AIP 协议的 Partner：
    Leader 发 TaskCommand(start) → 本服务诊断 → 返回 TaskResult(awaiting-completion)

启动：
    cd instrument-agent
    uv run uvicorn partners.main:app --port 8011

自测（不经过 Leader）：
    curl -X POST http://127.0.0.1:8011/rpc \
         -H "Content-Type: application/json" \
         -d '{"jsonrpc":"2.0","id":"1","method":"rpc","params":{"command":{...}}}'
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from pydantic import BaseModel

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
from acps_sdk.amp import (
    AccessBody,
    AccessEmitter,
    AccessParticipant,
    AccessRequest,
    AccessResponse,
    ErrorInfo,
    HeartbeatEmitter,
)

# 让本文件能 import 到项目根目录的 diagnose.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diagnose import 加载规则, 加载仪器, 诊断, 诊断结论  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# AMP 可观测性：Access + Heartbeat
#
# 只写本地 NDJSON，由 Fluent Bit 尾追转发到平台 Kafka。
# 不改 acs.json、不改端点，因此不触发版本变更 / 新 AIC。
# =============================================================================

AIC = os.environ.get("AGENT_AIC", "1.2.156.3088.1.BUPT.AD8RWG.U8VP8D.N65RSB.05I1")
AMP_LOG_DIR = Path(os.environ.get("AMP_LOG_DIR", "./logs"))
amp_access = AccessEmitter(AMP_LOG_DIR / "amp_access_instrument_diagnosis.jsonl", aic=AIC)
amp_heartbeat = HeartbeatEmitter(AMP_LOG_DIR / "amp_heartbeat_instrument_diagnosis.jsonl", aic=AIC)


# =============================================================================
# 启动时加载数据
# =============================================================================

规则 = []
仪器表 = []


def _确保加载() -> None:
    global 规则, 仪器表
    if not 规则:
        规则 = 加载规则()
        仪器表 = 加载仪器()
        logger.info("诊断数据就绪：%d 条规则，%d 台仪器", len(规则), len(仪器表))


# =============================================================================
# 业务：把诊断结论变成给人看的文本
# =============================================================================


def _渲染结论(d: 诊断结论) -> str:
    """把一条诊断结论渲染成多行文本。"""
    行 = [
        f"【{d.conclusion}】{d.instrument_name}（{d.instrument_id}）",
        f"错误码：{d.error_code or '无'}",
    ]
    if d.fault_name:
        行.append(f"故障：{d.fault_name}")
    if d.severity:
        行.append(f"严重度：{d.severity}")
    if d.evidence:
        行.append("依据：")
        行.extend(f"  · {e}" for e in d.evidence)
    if d.cause:
        行.append(f"可能原因：{d.cause}")
    if d.action:
        行.append(f"处置建议：{d.action}")
    if d.manual:
        行.append(f"参考：{d.manual}")
    return "\n".join(行)


def _取输入文本(command: TaskCommand) -> str:
    """从命令的 dataItems 里把文本拼出来。"""
    parts = []
    for item in command.dataItems or []:
        if isinstance(item, TextDataItem) and item.text:
            parts.append(item.text)
    return " ".join(parts).strip()


def _解析目标(文本: str) -> Optional[str]:
    """
    从用户输入里认出要诊断谁。

    - "CEN-01"          -> CEN-01
    - "诊断 CEN-01"      -> CEN-01
    - "巡诊" / "全部"     -> "__ALL__"
    - 空                 -> "__ALL__"
    """
    if not 文本 or any(k in 文本 for k in ("巡诊", "全部", "所有", "all")):
        return "__ALL__"

    上 = 文本.upper()
    for inst in 仪器表:
        if inst.id.upper() in 上 or inst.name in 文本:
            return inst.id
    return None


# =============================================================================
# AIP 命令处理
# =============================================================================


async def on_start(command: TaskCommand, task: Optional[TaskResult]) -> TaskResult:
    """
    收到 start 命令：诊断 → 把结果放进 products 和 dataItems →
    状态置为 awaiting-completion（按 AIP 规范，等 Leader 显式 complete）。
    """
    _确保加载()

    # 先走默认语义：不存在就建任务，已存在就原样返回（幂等）
    task = await DefaultHandlers.start(command, task)

    # 已经处理过的任务不再重复执行
    if task.status.state != TaskState.Accepted:
        return task

    文本 = _取输入文本(command)
    目标 = _解析目标(文本)

    if 目标 is None:
        正文 = f"未识别到仪器：{文本!r}。可用的仪器编号：{', '.join(i.id for i in 仪器表)}"
        结论数 = 0
    elif 目标 == "__ALL__":
        结果 = [诊断(i, 规则) for i in 仪器表]
        异常 = [r for r in 结果 if r.conclusion != "正常"]
        正文 = "\n\n".join(_渲染结论(r) for r in 异常) or "全部仪器正常"
        结论数 = len(异常)
    else:
        inst = next(i for i in 仪器表 if i.id == 目标)
        正文 = _渲染结论(诊断(inst, 规则))
        结论数 = 1

    logger.info("任务 %s 诊断完成：目标=%s，异常 %d 项", task.taskId, 目标, 结论数)

    # 产出物：把诊断报告作为 Product 交回去
    product = Product(
        id=f"diagnosis-{task.taskId}",
        name="仪器诊断报告",
        description=f"共 {结论数} 项异常" if 目标 == "__ALL__" else "单台诊断",
        dataItems=[TextDataItem(text=正文)],
    )
    TaskManager.set_products(task.taskId, [product])

    # 状态推进：accepted → awaiting-completion
    return TaskManager.update_task_status(
        task.taskId,
        TaskState.AwaitingCompletion,
        data_items=[TextDataItem(text=正文)],
    )


handlers = CommandHandlers(
    on_start=on_start,
    # get / cancel / complete / continue 先用默认实现
)


# =============================================================================
# FastAPI 服务
# =============================================================================

app = FastAPI(
    title="科研仪器诊断 Partner",
    description="AIP 协议的 Partner 端：接收 TaskCommand，返回诊断结果 TaskResult。",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)


@app.post("/rpc", response_model=None)
async def rpc(request: Request) -> RpcResponse:
    """
    AIP 规定的 RPC 入口。

    每次请求在 finally 里写一条 AMP access 日志（写失败不影响业务）。
    ⚠️ 身份绑定仍关闭：本服务不要求 mTLS 客户端证书。
    """
    t0 = time.perf_counter()
    raw = await request.body()
    sender: Optional[str] = None
    会话: Optional[str] = None
    try:
        payload = json.loads(raw)
        command = ((payload.get("params") or {}).get("command") or {})
        sender = command.get("senderId") or command.get("sender_id")
        会话 = command.get("sessionId") or command.get("session_id")
    except Exception:
        pass

    响应: Optional[RpcResponse] = None
    状态码 = 200
    错误: Optional[ErrorInfo] = None
    try:
        响应 = await handle_rpc_request(
            request,
            handlers,
            local_aic=None,
            identity_binding_enabled=False,
        )
        return 响应
    except Exception as exc:
        状态码 = 500
        错误 = ErrorInfo(code=500, message=str(exc))
        raise
    finally:
        try:
            响应字节 = len(响应.model_dump_json().encode("utf-8")) if 响应 is not None else 0
            await amp_access.emit(
                AccessBody(
                    duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                    request=AccessRequest(
                        method="POST",
                        url="/rpc",
                        route="/rpc",
                        headers=dict(request.headers),
                        body_size_bytes=len(raw),
                    ),
                    response=AccessResponse(status_code=状态码, body_size_bytes=响应字节),
                    caller=AccessParticipant(aic=sender, service_name="platform"),
                    callee=AccessParticipant(aic=AIC, service_name="instrument-diagnosis"),
                    error=错误,
                ),
                correlation_id=会话,
            )
        except Exception:
            logger.warning("AMP access 写入失败", exc_info=True)


@app.on_event("startup")
async def _启动AMP心跳() -> None:
    """启动后台心跳任务：立即发首条，之后每 15 秒一条。"""
    间隔 = float(os.environ.get("AMP_HEARTBEAT_INTERVAL_SECONDS", "15"))
    app.state.amp_heartbeat_task = asyncio.create_task(
        amp_heartbeat.run_periodic(间隔), name="amp-heartbeat"
    )
    logger.info("AMP heartbeat 已启动：间隔 %.0fs，日志目录 %s", 间隔, AMP_LOG_DIR)


@app.on_event("shutdown")
async def _停止AMP心跳() -> None:
    task = getattr(app.state, "amp_heartbeat_task", None)
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/health", summary="健康检查")
def health() -> dict:
    _确保加载()
    return {
        "status": "ok",
        "role": "partner",
        "rules": len(规则),
        "instruments": len(仪器表),
        "now": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", summary="服务说明")
def index() -> dict:
    return {
        "role": "partner",
        "protocol": "AIP (GB/Z 185.6)",
        "endpoint": "/rpc",
        "capabilities": ["仪器故障诊断"],
        "instruments": [i.id for i in 仪器表] if 仪器表 else [],
    }
