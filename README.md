-# 实验室科研仪器智能运维

> 用 AIP 协议把「仪器故障诊断」做成可被发现、可被调用的多智能体系统。

---

## 一句话

实验室里有各种仪器，故障排查靠老师傅经验、手册翻找、故障码查表。
**本项目把这些经验变成可执行、可复现、可被别人调用的能力。**

---

## 现在能做什么

**一行命令，对全部仪器做一次巡诊：**

```bash
uv run python diagnose.py
```

**输出**：

```
🔴 高速冷冻离心机 A-01（CEN-01）
   结论：确诊
   故障：转子不平衡
   严重度：中
   依据：
     · vibration_mm_s：8.2 > 阈值 5.0 ✅ 佐证
   可能原因：转子配重不均，或离心管放置不对称
   处置建议：停机，检查转子配重块与离心管对称性；重新配平后低速试运行
   参考：§3.2 转子平衡与维护

🟡 紫外可见分光光度计（备用）（UV-02）
   结论：疑似
   依据：
     · baseline_drift_abs：0.003 ≤ 阈值 0.005 ⚠️ 未佐证
     ↑ 报警了，但传感器数据不支撑
```

**只看一台**：

```bash
uv run python diagnose.py CEN-01
```

---

## 诊断逻辑：三级判断

| 结论 | 判定条件 |
| --- | --- |
| 🔴 **确诊** | 错误码匹配 **且** 传感器数据佐证 |
| 🟡 **疑似** | 错误码匹配，**但**传感器不支撑（可能是误报） |
| ⚪ **未知故障** | 错误码不在规则库里，转人工 |
| 🟢 **正常** | 没有上报错误码 |

> **这是"诊断"而不是"查表"**——同一个错误码，传感器数据不支持时结论会降级。

---

## 目录结构

```
instrument-agent/
├── diagnose.py          诊断引擎（核心业务逻辑）
├── data/
│   ├── instruments.json 仪器状态数据
│   └── faults.json      故障规则库
├── app/                 ✅ HTTP 服务（5 接口 + 演示首页）
├── partners/            ✅ AIP Partner（对外提供诊断能力）
│   ├── main.py
│   └── online/instrument_diagnosis/
│       └── acs.json     能力说明书（注册平台用）
├── leader/              ✅ AIP Leader（编排与验收）
│   └── main.py
└── docs/                架构说明、数据格式
```

---

## 三种跑法

### ① 命令行（最快）

```bash
uv run python diagnose.py            # 巡诊全部
uv run python diagnose.py CEN-01     # 指定一台
```

### ② HTTP 服务（网页演示）

```bash
uv run uvicorn app.main:app --port 8012
```

浏览器打开 <http://127.0.0.1:8012/> —— 自带演示首页，不依赖外部 CDN。

### ③ AIP 双进程（协议演示）

**终端 A** —— Partner：

```bash
uv run uvicorn partners.main:app --port 8011
```

**终端 B** —— Leader：

```bash
uv run python -m leader.main 巡诊
uv run python -m leader.main CEN-01
```

**完整走一遍 AIP 状态机**：

```
Leader  start  →  Partner 诊断
                  状态 = awaiting-completion
Leader  complete →  状态 = completed
```

---

## 环境

| 项 | 版本 |
| --- | --- |
| Python | 3.13（`uv` 管理） |
| Pydantic | 2.14 |
| FastAPI | 0.151 |
| acps-sdk | 2.0.0 |

**依赖管理一律走 uv**：

```bash
uv sync          # 按 pyproject.toml 装齐
uv add <包名>     # 加新依赖
uv run python xxx.py
```

> ⚠️ **不要裸敲 `python`**——那可能是全局解释器，看不见 `.venv` 里的包。

---

## 测试

```bash
uv run pytest -q          # 跑全部（约 0.2 秒）
uv run pytest -v          # 看每条用例
```

**共 65 个测试，覆盖两类：**

| 文件 | 测什么 | 数量 |
| --- | --- | --- |
| `tests/test_diagnose.py` | **诊断逻辑**：五种结论、七种操作符、数据缺失、差鉴别 | 24 |
| `tests/test_data.py` | **数据合法性**：字段拼错、重复错误码、`checks` 用了不存在的传感器、acs.json 结构 | 41 |

**最有价值的三条：**

- `test_checks的字段名都是仪器状态里存在的` —— **字段名写错 = 永远匹配不到，且不报错**
- `test_acs不含校名等敏感信息` —— 防止章程违规
- `test_条件部分满足判为疑似且置信度50` —— 锁住核心分级逻辑

> 💡 **改完 `data/*.json` 先跑一遍测试**，比直接跑程序更容易发现拼写错误。

---

## 安全规则

注册到平台时会产生**私钥和证书**。这类文件一旦进过 Git，即使删掉也会留在历史里。

`.gitignore` 已挡住：

| 类型 | 说明 |
| --- | --- |
| `*.pem` / `*.key` | 私钥 |
| `*.crt` / `*.csr` | 证书与证书请求 |
| `eab.json` | 平台注册凭证 |

---

## 下一步

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 诊断引擎 | 规则推理 + 三级判断 | ✅ |
| HTTP 服务 | `/diagnose` 等 5 个接口 + 演示首页 | ✅ |
| AIP 双进程 | Partner + Leader，走完 `start → complete` | ✅ |
| `acs.json` | 能力说明书（字段与官方样例一致） | ✅ |
| **平台注册** | 2026-10-28 审核通过（APPROVED），AIC 已分配 | ✅ |
| **平台四环节** | 注册 / 发现 / 互联 / 访问全部完成并留证（证据材料保留在本地，未随仓库公开） | ✅ |
| **身份证书** | serverAuth + clientAuth 已从平台 CA 领到（`keyfiles/`） | ✅ |
| **云服务器部署** | 阿里云轻量（`YOUR_SERVER_IP`），systemd 常驻 + 开机自启，65 测试在服务器通过 | ✅ |
| **端点迁移** | 版本 0.1.2 审核通过，端点 `https://YOUR_SERVER_IP:8011/rpc`（0.1.1 因 http 被自动审核拒；APPROVED 记录锁定不可改） | ✅ |
| **版本升级** | **版本 0.1.3 审核通过**，当前 AIC `1.2.156.3088.1.BUPT.AD8RWG.M34RS7.TBZ0N8.1DGH`；新证书已签发并部署（旧 0.1.2 的 AIC `…05I1` 保留为历史） | ✅ |
| **AMP 可观测性** | `AccessEmitter` + `HeartbeatEmitter` 写入 `/var/log/wutong-amp`，Fluent Bit 转发到平台 Kafka（`amp.access` / `amp.heartbeat`） | ✅ |
| mTLS 接入 | Partner 服务端启用 HTTPS + 客户端证书校验，开启身份绑定 | ⬜ 待办 |
| 真实数据 | 把 `data/faults.json` 换成实验室实际故障码 | ⬜ 待办 |
