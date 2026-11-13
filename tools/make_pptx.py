# -*- coding: utf-8 -*-
"""生成答辩 PPT（16:9，微软雅黑）。"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

OUT = r"D:/Privacy Docs/study/agent/文档/赛事-智能体互联/答辩PPT-异构科研仪器智能运维协同体.pptx"
DARK = RGBColor(0x1F, 0x4E, 0x79)
GRAY = RGBColor(0x55, 0x55, 0x55)
FONT = "微软雅黑"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def set_font(run, size=18, bold=False, color=RGBColor(0x22, 0x22, 0x22)):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def add_title(slide, text, size=30):
    box = slide.shapes.add_textbox(Inches(0.5), Inches(0.35), Inches(12.3), Inches(1.0))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = text
    set_font(r, size=size, bold=True, color=DARK)


def add_bullets(slide, items, top=1.5, size=18, gap=10):
    box = slide.shapes.add_textbox(Inches(0.7), Inches(top), Inches(11.9), Inches(5.6))
    tf = box.text_frame
    tf.word_wrap = True
    first = True
    for text, bold, sz in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(gap)
        r = p.add_run()
        r.text = text
        set_font(r, size=sz if sz else size, bold=bold)


def add_table(slide, headers, rows, top=1.5, col_widths=None, font_size=14):
    n_rows = len(rows) + 1
    n_cols = len(headers)
    tbl_shape = slide.shapes.add_table(n_rows, n_cols, Inches(0.6), Inches(top), Inches(12.1), Inches(0.5 * n_rows))
    tbl = tbl_shape.table
    if col_widths:
        for i, w in enumerate(col_widths):
            tbl.columns[i].width = Inches(w)
    for j, h in enumerate(headers):
        c = tbl.cell(0, j)
        c.text = h
        for p in c.text_frame.paragraphs:
            for r in p.runs:
                set_font(r, size=font_size, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        c.fill.solid()
        c.fill.fore_color.rgb = DARK
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = tbl.cell(i + 1, j)
            c.text = str(v)
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    set_font(r, size=font_size, bold=(j == 0))
    return tbl_shape


# ── 1 封面 ──
s = prs.slides.add_slide(BLANK)
box = s.shapes.add_textbox(Inches(1), Inches(2.3), Inches(11.3), Inches(1.6))
tf = box.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
r = p.add_run(); r.text = "异构科研仪器智能运维协同体"
set_font(r, size=48, bold=True, color=DARK)
p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
r2 = p2.add_run(); r2.text = "AIC · 智能体互联主题赛 答辩"
set_font(r2, size=24, color=GRAY)

# ── 2 背景与痛点 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "背景与痛点")
add_bullets(s, [
    ("实验室仪器“坏在哪、怎么修、找谁修”靠人脑，经验无法复用", True, 20),
    ("状态不透明：仪器跑得好不好，要人到现场看", False, None),
    ("响应慢：故障先报修、再排期、再查手册，小时级起步", False, None),
    ("经验断档：老师傅的判断方法没有沉淀，人一走就断", False, None),
    ("根因：多厂商异构——协议不通、故障码不通、数据格式不通", True, None),
], top=1.6, gap=14)

# ── 3 方案总览 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "方案总览：多智能体协同")
arch = """用户 / 平台
    │
    ▼
运维调度 Leader（意图解析 · 并发分派 · 聚合）
    │  AIP 协议
    ├──────────────┬──────────────┤
    ▼              ▼              ▼
状态采集 Partner  故障诊断 Partner  维护资源 Partner
【异构适配层】                      手册 / 工单 / 备件"""
box = s.shapes.add_textbox(Inches(0.9), Inches(1.5), Inches(11.5), Inches(4.2))
tf = box.text_frame
tf.word_wrap = True
for i, line in enumerate(arch.split("\n")):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    r = p.add_run(); r.text = line
    set_font(r, size=20 if i < 4 else 18, bold=(i in (2, 3)))
add_bullets(s, [("一句话：把异构性隔离在 Partner 内部，AIP 层只看到统一能力。不接大模型也能跑通。", True, 18)], top=5.9)

# ── 4 诊断引擎 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "核心技术 ① 诊断引擎（自主开发）")
add_bullets(s, [
    ("五级结论：正常 / 确诊 / 疑似 / 排除 / 未知故障", True, 20),
    ("置信度 = 满足的佐证条件数 ÷ 总条件数 × 100，按比例分级", False, None),
    ("差鉴别：不仅答“是什么”，还列“为什么不是别的”", False, None),
    ("关键案例：UV-02 报 E-302 但实测数据不支撑 → 判「排除」，提示先查传感器，避免维修白跑", False, None),
    ("数据：12 条规则、16 台仪器 / 4 机组；单台诊断 0.004 ms", False, None),
], top=1.6, gap=14)

# ── 5 并发编排 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "核心技术 ② 并发编排（含实测发现）")
add_bullets(s, [
    ("Leader 三阶段并发编排（asyncio.gather），三个 Partner 各司其职", True, 20),
    ("实测：串行 2826.2 ms → 并发 498.1 ms，加速 5.6 倍", True, 20),
    ("顺带的发现：诊断阶段只加速 1.2×——纯计算任务没有 IO 可并发", False, None),
    ("结论：并发只对“等待型”任务有效（阿姆达尔定律）；盲目加并发只会增加调度开销", False, None),
], top=1.6, gap=14)

# ── 6 开源改造逻辑 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "开源改造逻辑（附件2 点名要求）")
add_table(s,
    ["模块", "来源", "改造程度"],
    [["AIP 通信层 / 数据对象 / 任务状态机", "acps-sdk 原生复用", "未改"],
     ["能力描述 acs.json", "框架复用 + 自主编写", "配置层"],
     ["诊断规则引擎 / 规则库 / Partner 封装 / Leader 编排 / HTTP 服务 / 65 测试", "自主开发", "创新点"],
     ["SDK 源码改动", "仅一处（身份绑定参数）", "报告 §4.2.1"]],
    top=1.6, col_widths=[7.0, 2.6, 2.5], font_size=15)
add_bullets(s, [("自主代码占比约 70%。", True, 18)], top=5.0)

# ── 7 平台接入方案 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "梧桐平台接入方案")
add_bullets(s, [
    ("① 写 acs.json：能力 + 边界（明确拒绝 4 类请求）+ 示例", False, 19),
    ("② acps-cli：auth login → agent save → agent submit", False, None),
    ("③ 公网可达：云服务器（阿里云，固定 IP YOUR_SERVER_IP）+ systemd 常驻", False, None),
    ("④ HTTPS：平台准入要求端点必须 https，用平台 CA 签发的 serverAuth 证书", False, None),
    ("⑤ 审核通过 → 领身份证书（serverAuth + clientAuth）", False, None),
    ("⑥ 平台验证四环节：注册 → 发现 → 互联 → 访问", True, None),
], top=1.6, gap=12)

# ── 8 平台接入效果 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "平台接入效果")
add_table(s,
    ["环节", "结果"],
    [["注册", "10-28 19:37 提交，当日审核通过（APPROVED），AIC 已分配"],
     ["发现", "discover query 返回本作品"],
     ["互联", "调用平台上的「校园报修调度智能体」"],
     ["访问", "返回 completed + 工单号 WO-20261028-8160"],
     ["迁移", "10-29 迁至云服务器固定地址 YOUR_SERVER_IP:8011（HTTPS），版本 0.1.2 审核通过"]],
    top=1.6, col_widths=[1.8, 10.3], font_size=15)

# ── 9 接入踩过的坑 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "接入踩过的 7 个坑（实施深度）")
add_table(s,
    ["#", "问题", "解决"],
    [["1", "CLI 未上 PyPI", "从源码仓库安装"],
     ["2", "依赖版本错配（CLI 要 sdk≥2.2.0，PyPI 只有 2.1.0）", "SDK 也从仓库装"],
     ["3", "平台强制 mTLS 声明", "acs.json 先声明后实现"],
     ["4", "SDK 2.2.0 破坏性变更（身份绑定）", "显式关身份绑定参数"],
     ["5", "中文按 GBK 发送被拒", "请求体统一 UTF-8"],
     ["6", "公网 502", "本地服务未启动"],
     ["7", "http 端点被自动审核拒", "平台证书上 HTTPS，https 端点"]],
    top=1.5, col_widths=[0.7, 5.3, 6.1], font_size=13)
add_bullets(s, [("这些坑本身就是“标准化落地难”的实证。", True, 16)], top=6.7)

# ── 10 量化成效 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "量化成效")
add_table(s,
    ["指标", "实测"],
    [["单台诊断耗时", "0.004 ms（2000 轮平均）"],
     ["AIP 接口响应", "约 10 ms（本地）/ 公网 https 0.2s 内"],
     ["并发协同", "3 Partner，总加速 5.6×（498 vs 2826 ms）"],
     ["测试", "65 个用例全部通过（诊断 24 + 数据 41）"],
     ["平台访问数据", "自 10-28 起积累（排行榜可查，每日凌晨刷新）"]],
    top=1.6, col_widths=[3.2, 8.9], font_size=15)

# ── 11 不足与展望 ──
s = prs.slides.add_slide(BLANK)
add_title(s, "不足与展望（如实）")
add_bullets(s, [
    ("不足：服务端 mTLS 接入中；数据为构造数据（结构参照真实故障码表）；无部署脚本", False, 19),
    ("展望：mTLS + 身份绑定，补验「他方调我方」", False, None),
    ("展望：接入真实实验室数据", False, None),
    ("展望：能力边界“可执行化”——建议 ACS 增加结构化拒绝声明，让拒绝规则可被程序校验", True, None),
], top=1.6, gap=14)

# ── 12 结束 ──
s = prs.slides.add_slide(BLANK)
box = s.shapes.add_textbox(Inches(1), Inches(3.0), Inches(11.3), Inches(1.5))
tf = box.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
r = p.add_run(); r.text = "异构仪器 → 统一能力\n运维经验从“人脑”迁移到“规则库”"
set_font(r, size=30, bold=True, color=DARK)

prs.save(OUT)
print("slides:", len(prs.slides.__iter__.__self__._sldIdLst))
print("written:", OUT)
