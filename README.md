# 说脏话会被电！🫨⚡

**DGHub 外部插件** — 麦克风实时监听，说脏话立刻被电一下。

[![SDK](https://img.shields.io/badge/DGHub_SDK-v1-blue)](PLUGIN_DEVELOPMENT.md)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.1.0-orange)](https://github.com)

---

## 功能

- **实时语音识别** — 基于 faster-whisper，支持 GPU 加速
- **多语言脏话库** — 中英文词库 + 拼音缩写映射（sb→傻逼、nmsl→你妈死了）+ 同音字变体归一化
- **AI 智能兜底** — 词库未命中时可启用 Detoxify 或本地 LLM 二次判断
- **白名单防误伤** — 内置「我去/操作/干嘛/草莓」等日常词汇白名单
- **可配置电击** — 强度增量、持续时间、冷却间隔、波形预设均可调
- **21 个波形预设** — CS2 内置 5 个 + 郊狼原生 16 个

---

## 快速开始

### 1. 安装

将插件解压到 `DGHub/plugins/badwordshock/`，然后安装依赖：

```bash
# 双击运行（Windows）
install_deps.bat

# 或手动安装
pip install -r requirements.txt
```

> 依赖必须装到 DGHub 使用的 Python 环境。国内用户可加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`

### 2. 启用

重启 DGHub → 插件中心 → 外部插件 → 启用「说脏话会被电！」

首次启动时 Whisper 模型会自动下载（约 1.5GB），请耐心等待「模型就绪」日志。

### 3. 配置

在 DGHub 配置面板中调整：

| 设置项 | 说明 |
|---|---|
| 波形预设 | 命中脏话时播放的波形（21 种可选） |
| 单次电击强度增量 | 在 baseline 基础上 +X% |
| 电击持续秒数 | 每次电击持续时长 |
| 触发冷却 | 两次电击最小间隔，防止连电 |
| 触发动作 | both（强度+波形）/ strength（仅强度）/ waveform（仅波形） |

---

## 系统要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows |
| Python | 3.10+ |
| 麦克风 | 可用输入设备 |
| GPU | 可选（有 NVIDIA 显卡可加速识别） |
| 网络 | 首次启动需下载 Whisper 模型 |

---

## 依赖

| 包 | 重要性 |
|---|---|
| `websockets` | 必需 |
| `numpy` | 必需 |
| `sounddevice` | 必需 |
| `faster-whisper` | 必需 |
| `detoxify` | 可选（AI 判断） |
| `transformers` + `torch` + `accelerate` | 可选（本地 LLM） |

---

## 项目结构

```
badwordshock/
├── manifest.json          # 插件元信息 + 配置 UI schema
├── main.py                # 主入口
├── start.bat              # 启动脚本
├── requirements.txt       # 依赖清单
├── install_deps.bat       # 一键安装脚本
├── core/                  # 核心模块
│   ├── asr.py             # 语音识别引擎
│   ├── ai_judge.py        # AI 智能判断
│   ├── matcher.py         # 词库匹配引擎
│   ├── mic_capture.py     # 麦克风采集 + VAD
│   ├── normalizer.py      # 文本归一化管道
│   └── trigger.py         # 电击触发 + 冷却
└── badwords/              # 词库数据
    ├── default_zh.txt     # 中文脏话词库
    ├── default_en.txt     # 英文脏话词库
    ├── pinyin_alias.txt   # 拼音/缩写映射表
    └── whitelist.txt      # 白名单
```

---

## 许可

Just for fun. Use at your own risk.
