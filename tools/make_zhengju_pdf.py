# -*- coding: utf-8 -*-
"""把全部佐证材料合并成一个 PDF。"""
import io
import json
import re

from fpdf import FPDF

BASE = r"D:/Privacy Docs/study/agent/instrument-agent/佐证材料"
OUT = r"D:/Privacy Docs/study/agent/文档/赛事-智能体互联/佐证材料-异构科研仪器智能运维协同体.pdf"
FONT = r"C:/Windows/Fonts/simhei.ttf"

EMOJI = {"✅": "√", "❌": "x", "🟡": "○", "🔴": "●", "⬜": "□", "⭐": "★",
         "⚠️": "[注意]", "🔑": "[要点]", "💡": "[提示]", "🎯": "[目标]",
         "⏰": "[时间]", "❓": "?", "►": ">", "◄": "<", "↔": "<->", "✗": "x", "•": "-"}
def clean(t):
    for k, v in EMOJI.items():
        t = t.replace(k, v)
    return t

def wrap(text, width=42):
    out = []
    for para in text.split("\n"):
        while len(para) > width:
            out.append(para[:width])
            para = "    " + para[width:]
        out.append(para)
    return "\n".join(out)

def json_text(path, width=40):
    try:
        d = json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return clean(io.open(path, encoding="utf-8").read())
    return wrap(json.dumps(d, ensure_ascii=False, indent=2), width)

class P(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("cn", size=8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"第 {self.page_no()} 页", align="C")

pdf = P(format="A4")
pdf.set_auto_page_break(auto=True, margin=16)
pdf.add_font("cn", "", FONT)
pdf.add_font("cn", "B", FONT)
pdf.set_text_color(20, 20, 20)

def heading(text, size=15):
    pdf.set_font("cn", "B", size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 8, text)
    pdf.ln(2)

def body(text, size=9.5):
    pdf.set_font("cn", size=size)
    for line in clean(text).split("\n"):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 4.6, line)
    pdf.ln(3)

def code(text, size=8.5):
    pdf.set_font("cn", size=size)
    pdf.set_text_color(40, 40, 40)
    for line in clean(wrap(text, 46)).split("\n"):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 4.2, line)
    pdf.set_text_color(20, 20, 20)
    pdf.ln(3)

# ── 封面 ──
pdf.add_page()
pdf.set_font("cn", "B", 26)
pdf.ln(60)
pdf.set_x(pdf.l_margin)
pdf.multi_cell(0, 14, "异构科研仪器智能运维协同体", align="C")
pdf.set_font("cn", size=18)
pdf.set_x(pdf.l_margin)
pdf.multi_cell(0, 10, "参赛佐证材料（合并）", align="C")
pdf.set_font("cn", size=12)
pdf.ln(20)
pdf.set_x(pdf.l_margin)
pdf.multi_cell(0, 7, "赛题：AIC · 智能体互联\n整理日期：2026-10-30", align="C")

# ── 目录 ──
pdf.add_page()
heading("目录")
body("一、平台注册佐证（10-28 提交当日审核通过 + 10-29 状态快照）\n"
     "二、平台发现佐证（discover query 原始返回）\n"
     "三、跨智能体互联与访问佐证（调用「校园报修调度智能体」完整 TaskResult）\n"
     "四、单元测试佐证（65 个用例全部通过）\n"
     "五、并发性能佐证（串行 vs 并发实测，加速 5.6×）\n"
     "六、公网端点在线验证与四环节留档（云服务器 HTTPS + 平台 CA 证书）\n"
     "七、平台验证记录（四环节汇总说明）\n"
     "八、平台访问数据说明（查询方法与刷新规律）\n"
     "九、AMP 可观测性接入验证（10-30 部署）\n"
     "十、版本 0.1.3 升级与 AIC 变更（10-30）")

# ── 一、注册 ──
pdf.add_page()
heading("一、平台注册佐证")
body("以下为 2026-10-28 提交当日的平台 Agent 列表原始返回（approval_status = APPROVED，AIC 已分配）：")
code(json_text(BASE + "/注册-2026-10-28.json"))
body("2026-10-29 状态快照（端点迁移至云服务器后，版本 0.1.2 审核通过，新 AIC 生效；"
     "快照拍摄于删除旧版记录之前，观察平台自动审核整个过程）：")
code(json_text(BASE + "/fresh/注册状态-2026-10-29.json"))

# ── 二、发现 ──
pdf.add_page()
heading("二、平台发现佐证")
body("2026-10-28 discover query 原始返回（返回本作品及平台其它智能体）：")
code(json_text(BASE + "/发现-2026-10-28.json"))
body("2026-10-29 再次查询返回（本作品仍可被发现，active = true）：")
code(json_text(BASE + "/fresh/发现-2026-10-29.json"))

# ── 三、互联与访问 ──
pdf.add_page()
heading("三、跨智能体互联与访问佐证")
body("通过 AIP TaskCommand(start) 调用平台上的「校园报修调度智能体」，"
     "返回 state = completed，产出工单号 WO-20261028-8160。以下为完整 TaskResult 原始返回：")
code(json_text(BASE + "/互联-调用校园报修调度-2026-10-28.json"))

# ── 四、测试 ──
pdf.add_page()
heading("四、单元测试佐证")
body("2026-10-29 在本地与云服务器（YOUR_SERVER_IP）各跑一遍，均为 65 个用例全部通过：")
code(io.open(BASE + "/fresh/测试-65用例.txt", encoding="utf-8").read())

# ── 五、并发 ──
pdf.add_page()
heading("五、并发性能佐证")
body("测试条件：状态采集与维护资源 Partner 开启 200 ms 模拟仪器通信延迟"
     "（真实串口 / Modbus / 厂商 SDK 通常 100–500 ms；此延迟为模拟值，非实测仪器耗时）。"
     "同一套数据分别串行、并发各跑一遍：")
code(io.open(BASE + "/fresh/并发对比.txt", encoding="utf-8").read())

# ── 六、公网验证与四环节留档 ──
pdf.add_page()
heading("六、公网端点在线验证与四环节留档")
code(io.open(BASE + "/fresh/公网端点验证.txt", encoding="utf-8").read())
body("2026-10-29 23:46 对四环节做了一次完整复验，原始输出如下（第 3 块为本作品端点的 AIP 直连自测，非叮当）：")
code(io.open(BASE + "/fresh/留档-2026-10-29晚.txt", encoding="utf-8").read())

# ── 七、平台验证记录 ──
pdf.add_page()
heading("七、平台验证记录")
body(clean(io.open(BASE + "/平台验证记录.md", encoding="utf-8").read()))

# ── 八、访问数据说明 ──
pdf.add_page()
heading("八、平台访问数据说明")
body("1. 平台「智能体调用排行榜」API 可公开查询（无需登录）：\n"
     "   GET https://wt.ioa.pub/api/rankings/top?startAt=…&endAt=…&n=200\n"
     "   时间格式 YYYY-MM-DDTHH:MM:SS+08:00（URL 编码）。\n"
     "2. 榜单每天约北京时间凌晨 02:00 刷新，meta.accessComputedAt 为最近计算时间。\n"
     "3. AIP 直连调用不经平台、不产生访问记录；平台内调用（如「叮当」）会计入榜单。\n"
     "4. 本作品 2026-10-28 19:37 注册，访问数据自 10-29 起积累，每日截图存证。")

# ── 九、AMP 可观测性 ──
pdf.add_page()
heading("九、AMP 可观测性接入验证（2026-10-30）")
body(clean(io.open(BASE + "/fresh/amp-部署记录-2026-10-30.md", encoding="utf-8").read()))
body("AMP access 原始日志（最近一条）：")
code(io.open(BASE + "/fresh/amp-access-2026-10-30.jsonl", encoding="utf-8").read())
body("AMP heartbeat 原始日志（最近一条）：")
code(io.open(BASE + "/fresh/amp-heartbeat-2026-10-30.jsonl", encoding="utf-8").read())
body("Fluent Bit 转发指标（Kafka 输出 errors=0 / retries=0 / dropped=0）：")
code(io.open(BASE + "/fresh/amp-fluent-bit-metrics-2026-10-30.json", encoding="utf-8").read())

# ── 十、0.1.3 升级 ──
pdf.add_page()
heading("十、版本 0.1.3 升级与 AIC 变更（2026-10-30）")
body("10-30 主动升级版本至 0.1.3，重新提交审核并通过；按新 AIC 重签证书并部署。"
     "旧 0.1.2 记录保留为历史，演示视频中出现的旧 AIC 仍可在平台查询。")
code(io.open(BASE + "/fresh/0.1.3-升级与证书-2026-10-30.txt", encoding="utf-8").read())

pdf.output(OUT)
print("written:", OUT, "pages:", pdf.page_no())
