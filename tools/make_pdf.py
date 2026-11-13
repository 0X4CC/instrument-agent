# -*- coding: utf-8 -*-
"""把技术报告成稿 md 转成 PDF（fpdf2，中文字体 simhei）。"""
import io
import re
import sys

import markdown as md

from fpdf import FPDF

SRC = r"D:/Privacy Docs/study/agent/文档/赛事-智能体互联/技术报告-设备运维-成稿.md"
OUT = r"D:/Privacy Docs/study/agent/文档/赛事-智能体互联/技术方案-异构科研仪器智能运维协同体.pdf"
FONT = r"C:/Windows/Fonts/simhei.ttf"

text = io.open(SRC, encoding="utf-8").read()

# ── PDF 环境里 simhei 没有 emoji 字形，替换成同义符号 ──
emoji_map = {
    "✅": "√", "❌": "×", "🟡": "○", "🔴": "●", "⬜": "□",
    "⭐": "★", "⚠️": "[注意]", "🔑": "[要点]", "💡": "[提示]",
    "🎯": "[目标]", "🔥": "[重点]", "⏰": "[时间]", "❓": "?",
}
for k, v in emoji_map.items():
    text = text.replace(k, v)

# simhei 缺这些符号字形（代码块时序图/差鉴别里用到），换成同义字符
for k, v in {
    "►": ">", "▶": ">", "◄": "<", "◀": "<",
    "↔": "<->", "✗": "x", "•": "-",
}.items():
    text = text.replace(k, v)

# ── 代码块长行折行（防止超出版面） ──
def wrap_code_block(match):
    code = match.group(1)
    lines = []
    for line in code.split("\n"):
        while len(line) > 86:
            lines.append(line[:86])
            line = "    " + line[86:]
        lines.append(line)
    return "```\n" + "\n".join(lines) + "\n```"

text = re.sub(r"```(.*?)```", wrap_code_block, text, flags=re.S)

html = md.markdown(
    text,
    extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
)

# fpdf2 不认识的块级标签转成 <p>，避免报错
for tag in ("div", "section", "article", "details", "summary"):
    html = html.replace(f"<{tag}>", "").replace(f"</{tag}>", "")

# 表格单元格里不允许嵌套格式标签（<strong> 等会报 NotImplementedError），剥掉只留文字
def strip_inner_tags(match):
    tag = match.group(1)
    inner = re.sub(r"<[^>]+>", "", match.group(2))
    return f"<{tag}>{inner}</{tag}>"

html = re.sub(r"<(td|th)(?: [^>]*)?>(.*?)</\1>", strip_inner_tags, html, flags=re.S)

pdf = FPDF(format="A4")
pdf.set_auto_page_break(auto=True, margin=18)
pdf.add_font("cn", "", FONT)
pdf.set_font("cn", size=10.5)

# 页面 + 页脚页码
class P(FPDF):
    def footer(self):
        self.set_y(-13)
        self.set_font("cn", size=8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"第 {self.page_no()} 页", align="C")

pdf = P(format="A4")
pdf.set_auto_page_break(auto=True, margin=18)
pdf.add_font("cn", "", FONT)
pdf.add_font("cn", "B", FONT)   # 粗体变体：simhei 本身已够粗，复用同一文件
pdf.add_font("cn", "I", FONT)   # 斜体变体：同上（fpdf2 的 HTML 解析会要）
pdf.set_font("cn", size=10.5)
pdf.set_text_color(20, 20, 20)

pdf.add_page()
# 标题字号映射
pdf.set_font_size(10.5)
try:
    pdf.write_html(html, table_line_separators=True, font_family="cn", pre_code_font="cn", ul_bullet_char="-")
except Exception as e:
    # 兜底：去掉 table 边框属性重试
    html2 = re.sub(r'<table[^>]*>', "<table>", html)
    pdf.write_html(html2, table_line_separators=True, font_family="cn", pre_code_font="cn", ul_bullet_char="-")

pdf.output(OUT)
print("written:", OUT, "pages:", pdf.page_no())
