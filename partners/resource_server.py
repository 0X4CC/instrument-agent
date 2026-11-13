# -*- coding: utf-8 -*-
"""
Partner ③ · 维护资源（端口 8013）

职责：按故障码 / 故障名检索手册章节、备件库存、历史工单。

启动：
    uv run uvicorn partners.resource_server:app --port 8013
"""

import json
import logging
from pathlib import Path

from partners.common import 建AIP应用

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")

数据目录 = Path(__file__).resolve().parent.parent / "data"
资源表 = json.loads((数据目录 / "resources.json").read_text(encoding="utf-8"))


def 检索(文本: str) -> tuple[str, dict]:
    """按错误码或故障名查维护资源。"""
    关键词 = 文本.strip()

    命中 = [
        r for r in 资源表
        if 关键词 and (关键词.upper() in r["code"].upper() or 关键词 in r["fault_name"])
    ]

    if not 命中:
        # 没指定就返回全部概览
        行 = [f"【维护资源】共 {len(资源表)} 条故障档案", "-" * 48]
        for r in 资源表:
            行.append(
                f"  {r['code']:8s} {r['fault_name']:12s} "
                f"预计 {r['expected_hours']}h  备件 {len(r['spares'])} 项  工单 {len(r['tickets'])} 条"
            )
        return "\n".join(行), {"count": len(资源表), "items": []}

    r = 命中[0]
    行 = [
        f"【维护资源】{r['code']} · {r['fault_name']}",
        "-" * 48,
        f"  手册参考   ：{r['manual']}",
        f"  预计工时   ：{r['expected_hours']} 小时",
    ]

    if r["spares"]:
        行.append("  备件库存   ：")
        for s in r["spares"]:
            状态 = "✅ 有货" if s["stock"] > 0 else "❌ 缺货"
            行.append(f"    · {s['name']:20s} 库存 {s['stock']:2d} 件  "
                      f"到货 {s['lead_days']} 天  {状态}")
    else:
        行.append("  备件库存   ：无需更换备件")

    if r["tickets"]:
        行.append("  历史工单   ：")
        for t in r["tickets"]:
            行.append(f"    · {t['id']}（{t['days_ago']} 天前）：{t['resolution']}")

    return "\n".join(行), {"count": 1, "item": r}


app = 建AIP应用(
    名称="维护资源 Partner",
    描述="按故障码检索手册章节、备件库存与历史工单，输出处置参考。",
    业务=检索,
    产品名="维护资源档案",
)
