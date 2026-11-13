# -*- coding: utf-8 -*-
"""
Partner ① · 状态采集（端口 8011）

职责：按「机组」或「全部」返回仪器当前状态。
这是异构适配层的落点——真实系统里，这一层要把各厂商协议归一化成统一字段。

启动：
    uv run uvicorn partners.status_server:app --port 8011
"""

import logging

from diagnose import 加载仪器

from partners.common import 建AIP应用

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")

仪器表 = 加载仪器()


def 采集(文本: str) -> tuple[str, dict]:
    """按机组名或仪器编号筛选；空 / all 返回全部。"""
    关键词 = 文本.strip()

    if not 关键词 or "全部" in 关键词 or "all" in 关键词.lower() or "巡" in 关键词:
        目标 = 仪器表
        标题 = "全部机组"
    else:
        目标 = [i for i in 仪器表
                if (i.group and 关键词 in i.group)
                or 关键词.upper() in i.id.upper()
                or 关键词 in i.name]
        标题 = 关键词

    if not 目标:
        return f"未找到匹配「{关键词}」的仪器", {"count": 0, "items": []}

    行 = [f"【状态采集】{标题}：{len(目标)} 台仪器", "-" * 48]
    数据 = []
    for i in 目标:
        code = i.status.error_code or "正常"
        行.append(f"  {i.id:8s} {i.name:26s} {code}")
        数据.append({
            "id": i.id, "name": i.name, "device_type": i.device_type,
            "group": i.group, "error_code": i.status.error_code,
            "status": i.status.model_dump(exclude_none=True),
        })

    return "\n".join(行), {"count": len(目标), "items": 数据}


app = 建AIP应用(
    名称="状态采集 Partner",
    描述="按机组采集仪器运行状态，输出归一化后的统一字段（异构适配层）。",
    业务=采集,
    产品名="仪器状态快照",
)
