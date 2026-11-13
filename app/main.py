# -*- coding: utf-8 -*-
"""
科研仪器智能运维 · HTTP 服务

启动：
    cd research-agent/instrument-agent
    uv run uvicorn app.main:app --reload --port 8011

打开：
    http://127.0.0.1:8011/docs      ← 可交互的接口文档（演示用这个）
    http://127.0.0.1:8011/health    ← 健康检查
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from diagnose import (
    加载规则,
    加载仪器,
    诊断,
    数据读不了,
    诊断结论,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="科研仪器智能运维 API",
    description=(
        "基于 ACS 能力描述与规则推理的仪器故障诊断服务。\n\n"
        "**诊断三级判断**：确诊（错误码 + 传感器佐证）/ 疑似（数据不支撑）/ 未知故障（规则库未收录）"
    ),
    version="0.1.0",
    # 关掉默认的 /docs 和 /redoc —— 它们从 jsdelivr 加载资源，国内打不开会白屏
    docs_url=None,
    redoc_url=None,
)

# 国内可访问的 CDN（staticfile 与 bootcdn 都实测可用）
_SWAGGER_JS = "https://cdn.staticfile.org/swagger-ui/5.17.14/swagger-ui-bundle.min.js"
_SWAGGER_CSS = "https://cdn.staticfile.org/swagger-ui/5.17.14/swagger-ui.css"


# =============================================================================
# 启动时加载数据（加载一次，常驻内存）
# =============================================================================

规则 = []
仪器表 = []


@app.on_event("startup")
def _启动加载() -> None:
    global 规则, 仪器表
    try:
        规则 = 加载规则()
        仪器表 = 加载仪器()
    except 数据读不了 as e:
        logger.error("数据加载失败：%s", e)
        raise
    logger.info("服务就绪：%d 条规则，%d 台仪器", len(规则), len(仪器表))


# =============================================================================
# 页面：演示首页（不依赖任何 CDN，断网也能用）
# =============================================================================

首页HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>科研仪器智能运维</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 32px 20px;
    font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
    background: #f5f6f8; color: #1a1a1a;
  }
  .wrap { max-width: 900px; margin: 0 auto; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: #666; font-size: 14px; margin-bottom: 24px; }
  .card {
    background: #fff; border-radius: 10px; padding: 20px 22px;
    box-shadow: 0 1px 3px rgba(0,0,0,.08); margin-bottom: 18px;
  }
  label { font-size: 14px; color: #444; margin-right: 8px; }
  select, button {
    font-size: 14px; padding: 8px 14px; border-radius: 6px;
    border: 1px solid #ccc; background: #fff; cursor: pointer;
  }
  button.primary { background: #2563eb; border-color: #2563eb; color: #fff; }
  button.primary:hover { background: #1d4ed8; }
  .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  #out { margin-top: 18px; }
  .badge {
    display: inline-block; padding: 2px 10px; border-radius: 99px;
    font-size: 13px; font-weight: 600;
  }
  .b-确诊 { background: #fee2e2; color: #b91c1c; }
  .b-疑似 { background: #fef3c7; color: #b45309; }
  .b-正常 { background: #dcfce7; color: #15803d; }
  .b-排除 { background: #dbeafe; color: #1d4ed8; }
  .b-未知故障 { background: #e5e7eb; color: #374151; }
  .kv { margin: 8px 0; font-size: 14px; line-height: 1.7; }
  .kv b { color: #374151; }
  .ev { color: #666; font-size: 13px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; }
  th { color: #666; font-weight: 500; }
  .muted { color: #999; font-size: 13px; margin-top: 16px; }
  a { color: #2563eb; }
</style>
</head>
<body>
<div class="wrap">
  <h1>科研仪器智能运维</h1>
  <div class="sub">规则推理 + 传感器佐证 · 诊断结果分「确诊 / 疑似 / 未知」三级</div>

  <div class="card">
    <div class="row">
      <label for="sel">选择仪器</label>
      <select id="sel"></select>
      <button class="primary" onclick="diagOne()">诊断</button>
      <button onclick="diagAll()">巡诊全部</button>
    </div>
    <div id="out"><div class="muted">点「诊断」开始。</div></div>
  </div>

  <div class="muted">
    接口文档：<a href="/docs">/docs</a> ·
    规则库：<a href="/rules">/rules</a> ·
    健康检查：<a href="/health">/health</a>
  </div>
</div>

<script>
async function 初始化() {
  const r = await fetch('/instruments');
  const list = await r.json();
  const sel = document.getElementById('sel');
  sel.innerHTML = list.map(i =>
    `<option value="${i.id}">${i.name}（${i.id}）</option>`
  ).join('');
}

function 渲染(d) {
  const ev = (d.evidence || []).map(e => `<div class="ev">· ${e}</div>`).join('');
  const alt = (d.alternatives || []).map(c =>
    `<div class="ev">✗ ${c.故障}（${c.错误码}）：${c.理由}</div>`
  ).join('');
  const 置信 = d.confidence ? `　置信度 ${d.confidence}` : '';
  return `
    <div class="badge b-${d.conclusion}">${d.conclusion}</div>${置信}
    <div class="kv"><b>仪器：</b>${d.instrument_name}（${d.instrument_id}）</div>
    <div class="kv"><b>错误码：</b>${d.error_code || '无'}</div>
    ${d.fault_name ? `<div class="kv"><b>故障：</b>${d.fault_name}</div>` : ''}
    ${d.severity ? `<div class="kv"><b>严重度：</b>${d.severity}</div>` : ''}
    <div class="kv"><b>依据：</b></div>${ev}
    ${d.cause ? `<div class="kv"><b>可能原因：</b>${d.cause}</div>` : ''}
    ${d.action ? `<div class="kv"><b>处置建议：</b>${d.action}</div>` : ''}
    ${d.manual ? `<div class="kv"><b>参考：</b>${d.manual}</div>` : ''}
    ${alt ? `<div class="kv"><b>差鉴别（为什么不是别的）：</b></div>${alt}` : ''}
  `;
}

async function diagOne() {
  const id = document.getElementById('sel').value;
  const out = document.getElementById('out');
  out.innerHTML = '<div class="muted">诊断中…</div>';
  const r = await fetch('/diagnose?instrument_id=' + encodeURIComponent(id));
  if (!r.ok) { out.innerHTML = '<div class="kv">请求失败：' + r.status + '</div>'; return; }
  out.innerHTML = 渲染(await r.json());
}

async function diagAll() {
  const out = document.getElementById('out');
  out.innerHTML = '<div class="muted">巡诊中…</div>';
  const r = await fetch('/diagnose/all?only_abnormal=true');
  const d = await r.json();
  const rows = d.results.map(x => `
    <tr>
      <td><span class="badge b-${x.conclusion}">${x.conclusion}</span></td>
      <td>${x.instrument_name}</td>
      <td>${x.error_code || '—'}</td>
      <td>${x.fault_name || '—'}</td>
    </tr>`).join('');
  const s = Object.entries(d.summary).map(([k,v]) => `${k} ${v}`).join(' · ');
  out.innerHTML = `
    <div class="kv"><b>共 ${d.total} 台异常</b>　${s}</div>
    <table><thead><tr><th>结论</th><th>仪器</th><th>错误码</th><th>故障</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

初始化();
</script>
</body>
</html>"""


@app.get("/docs", include_in_schema=False)
def 自定义接口文档() -> HTMLResponse:
    """用国内 CDN 的 Swagger UI 替换默认版本（默认版从 jsdelivr 加载，国内会白屏）。"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " · 接口文档",
        swagger_js_url=_SWAGGER_JS,
        swagger_css_url=_SWAGGER_CSS,
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def 演示首页() -> str:
    """演示用的首页，纯 HTML + 原生 JS，不依赖任何外部资源。"""
    return 首页HTML


# =============================================================================
# 接口
# =============================================================================


@app.get("/health", summary="健康检查")
def health() -> dict:
    """确认服务活着，并返回加载了多少数据。"""
    return {
        "status": "ok",
        "rules": len(规则),
        "instruments": len(仪器表),
    }


@app.get("/instruments", summary="列出所有仪器")
def list_instruments() -> list[dict]:
    """返回当前纳管的仪器清单。"""
    return [
        {
            "id": i.id,
            "name": i.name,
            "device_type": i.device_type,
            "model": i.model,
            "vendor": i.vendor,
            "error_code": i.status.error_code,
        }
        for i in 仪器表
    ]


@app.get("/diagnose", summary="诊断单台仪器")
def diagnose_one(
    instrument_id: str = Query(..., description="仪器编号，如 CEN-01"),
) -> 诊断结论:
    """
    给一台仪器做诊断。

    - 错误码匹配 + 传感器数据佐证 → **确诊**
    - 错误码匹配但数据不支撑 → **疑似**
    - 错误码不在规则库 → **未知故障**
    """
    if not 仪器表:
        raise HTTPException(status_code=503, detail="仪器数据尚未加载")

    for inst in 仪器表:
        if inst.id == instrument_id:
            return 诊断(inst, 规则)

    raise HTTPException(status_code=404, detail=f"找不到仪器：{instrument_id}")


@app.get("/diagnose/all", summary="巡诊全部仪器")
def diagnose_all(
    only_abnormal: bool = Query(False, description="只看有问题的（跳过正常）"),
) -> dict:
    """
    对全部仪器做一次巡诊，返回逐台结论 + 汇总统计。
    """
    if not 仪器表:
        raise HTTPException(status_code=503, detail="仪器数据尚未加载")

    结果 = [诊断(inst, 规则) for inst in 仪器表]

    if only_abnormal:
        结果 = [r for r in 结果 if r.conclusion != "正常"]

    统计: dict[str, int] = {}
    for r in 结果:
        统计[r.conclusion] = 统计.get(r.conclusion, 0) + 1

    return {
        "total": len(结果),
        "summary": 统计,
        "results": 结果,
    }


@app.get("/rules", summary="查看故障规则库")
def list_rules(
    device_type: Optional[str] = Query(None, description="按设备类型过滤"),
) -> list[dict]:
    """把规则库暴露出来，方便调试和演示时说明"它凭什么这么判断"。"""
    目标 = [r for r in 规则 if device_type is None or r.device_type == device_type]
    return [r.model_dump() for r in 目标]
