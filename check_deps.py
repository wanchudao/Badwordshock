"""
check_deps.py — badwordshock 环境检测工具

用法：python check_deps.py

功能：
  - 检测 Python 版本、必需/可选依赖、文件完整性、麦克风、网络、GPU
  - 所有检测仅使用 Python 标准库，无需安装任何第三方包
  - 结果用 [OK] / [FAIL] / [WARN] / [INFO] 标记，兼容 Windows cmd

设计依据：逐一对照项目源码中每个 import 语句和文件访问路径。
"""

import importlib
import os
import sys
import urllib.request
import urllib.error

# ── Windows 控制台编码兼容（避免中文显示为乱码）──
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── 配置 ──

REQUIRED_PYTHON = (3, 10)

# 必需包：{包名: import 路径（用于 importlib 验证）}
REQUIRED_PACKAGES = {
    "websockets":    "websockets",
    "numpy":         "numpy",
    "sounddevice":   "sounddevice",
    "faster_whisper": "faster_whisper",
}

# 可选包（AI 判断）
OPTIONAL_PACKAGES = {
    "detoxify":     "detoxify",
    "transformers": "transformers",
    "torch":        "torch",
    "accelerate":   "accelerate",
}

# 必须存在的文件（相对脚本所在目录 = 插件根目录）
REQUIRED_FILES = [
    "manifest.json",
    "start.bat",
    "requirements.txt",
    os.path.join("core", "__init__.py"),
    os.path.join("core", "asr.py"),
    os.path.join("core", "matcher.py"),
    os.path.join("core", "normalizer.py"),
    os.path.join("core", "mic_capture.py"),
    os.path.join("core", "trigger.py"),
    os.path.join("core", "ai_judge.py"),
    os.path.join("badwords", "default_zh.txt"),
    os.path.join("badwords", "default_en.txt"),
    os.path.join("badwords", "pinyin_alias.txt"),
    os.path.join("badwords", "whitelist.txt"),
]

# 网络检查
HF_TIMEOUT = 5  # 秒

# ── 工具函数 ──

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

_pass = 0
_fail = 0
_warn = 0


def ok(msg: str):
    global _pass
    _pass += 1
    print(f"  [OK]   {msg}")


def fail(msg: str):
    global _fail
    _fail += 1
    print(f"  [FAIL] {msg}")


def warn(msg: str):
    global _warn
    _warn += 1
    print(f"  [WARN] {msg}")


def info(msg: str):
    print(f"  [INFO] {msg}")


def section(title: str):
    print()
    print(f"--- {title} ---")


# ── 各项检测 ──

def check_python():
    v = sys.version_info[:2]
    ver_str = f"{v[0]}.{v[1]}.{sys.version_info[2]}"
    if v >= REQUIRED_PYTHON:
        ok(f"Python {ver_str} (>= {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]})")
    else:
        fail(f"Python {ver_str} — 需要 >= {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}（faster-whisper 要求）")
    info(f"解释器路径: {sys.executable}")


def check_package(name: str, import_path: str, required: bool = True) -> bool:
    """检测单个包是否可 import。返回 True 表示已安装。"""
    try:
        importlib.import_module(import_path)
        if required:
            ok(f"包: {name}")
        else:
            ok(f"包: {name} (可选)")
        return True
    except ImportError:
        msg = f"包: {name} — 未安装"
        if required:
            fail(msg)
        else:
            warn(msg)
        return False


def check_required_packages():
    for name, path in REQUIRED_PACKAGES.items():
        check_package(name, path, required=True)


def check_optional_packages():
    for name, path in OPTIONAL_PACKAGES.items():
        check_package(name, path, required=False)


def check_files():
    for rel in REQUIRED_FILES:
        full = os.path.join(SCRIPT_DIR, rel)
        if os.path.isfile(full):
            ok(f"文件: {rel}")
        else:
            fail(f"文件: {rel} — 缺失")


def check_microphone():
    """检测是否有可用的麦克风输入设备（需要 sounddevice 已安装）。"""
    try:
        importlib.import_module("sounddevice")
    except ImportError:
        warn("麦克风检测跳过（sounddevice 未安装）")
        return

    try:
        import sounddevice as sd
        devices = sd.query_devices()
        inputs = [(i, d) for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]
        if inputs:
            ok(f"麦克风: 找到 {len(inputs)} 个输入设备")
            for idx, dev in inputs:
                info(f"  #{idx}: {dev['name']} (通道: {dev['max_input_channels']}, 采样率: {dev.get('default_samplerate', '?')} Hz)")
        else:
            fail("麦克风: 未找到任何输入设备 — 插件将无法采集语音")
    except Exception as e:
        fail(f"麦克风: 查询失败 — {e}")


def check_network():
    """检测能否访问 Hugging Face（下载 Whisper 模型需要）。"""
    urls = [
        ("https://huggingface.co", "Hugging Face Hub"),
        ("https://pypi.org", "PyPI"),
    ]
    for url, label in urls:
        try:
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=HF_TIMEOUT)
            ok(f"网络: {label} ({url}) 可达")
        except Exception:
            warn(f"网络: {label} ({url}) 不可达 — 首次启动下载模型可能失败")


def check_gpu():
    """检测 CUDA GPU（需要 torch 已安装）。"""
    try:
        importlib.import_module("torch")
    except ImportError:
        info("GPU 检测跳过（torch 未安装）")
        return

    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            try:
                props = torch.cuda.get_device_properties(0)
                vram = props.total_mem / (1024 ** 3)
                vram_str = f"{vram:.1f} GB VRAM, "
            except Exception:
                vram_str = ""
            ok(f"GPU: {gpu_name} ({vram_str}ASR 将使用 GPU 加速)")
        else:
            info("GPU: 无可用 CUDA 设备 — ASR 将回退 CPU 模式（也可用，稍慢）")
    except Exception as e:
        info(f"GPU: 检测异常 — {e}")


def check_env():
    """检查 DGHub 运行时环境变量。"""
    token = os.environ.get("DGHUB_TOKEN", "")
    host = os.environ.get("DGHUB_HOST", "127.0.0.1")
    port = os.environ.get("DGHUB_PORT", "8000")

    if token:
        ok(f"环境变量: DGHUB_TOKEN 已设置")
    else:
        info(f"环境变量: DGHUB_TOKEN 未设置 — 由 DGHub 启动时自动注入，独立运行测试可忽略")

    info(f"  DGHUB_HOST = {host}")
    info(f"  DGHUB_PORT = {port}")


def check_core_imports():
    """尝试 import 项目的 core 模块（验证模块语法和互相引用无误）。"""
    # 把项目根目录加入 sys.path
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)
    modules = [
        "core.normalizer",
        "core.matcher",
        "core.trigger",
        "core.ai_judge",
    ]
    for mod in modules:
        try:
            importlib.import_module(mod)
            ok(f"模块: {mod} 加载成功")
        except Exception as e:
            fail(f"模块: {mod} 加载失败 — {e}")

    # asr.py 和 mic_capture.py 内部延迟 import 重依赖，先确认它们语法没问题
    for mod in ("core.asr", "core.mic_capture"):
        try:
            importlib.import_module(mod)
            ok(f"模块: {mod} 加载成功")
        except ImportError as e:
            # asr.py 有 from pathlib import Path 等轻量导入，不应报 ImportError
            # 如果报错说明依赖缺失
            warn(f"模块: {mod} 加载失败（可能缺依赖） — {e}")
        except Exception as e:
            fail(f"模块: {mod} 加载失败 — {e}")


# ── 主流程 ──

def main():
    print("=" * 60)
    print("  badwordshock 环境检测")
    print("=" * 60)

    section("1. Python 版本")
    check_python()

    section("2. 必需依赖 (pip install)")
    check_required_packages()

    section("3. 可选依赖 — AI 判断 (pip install)")
    check_optional_packages()

    section("4. 文件完整性")
    check_files()

    section("5. 模块加载")
    check_core_imports()

    section("6. 麦克风")
    check_microphone()

    section("7. 网络连通性")
    check_network()

    section("8. GPU / CUDA")
    check_gpu()

    section("9. 环境变量")
    check_env()

    # ── 总结 ──
    print()
    print("=" * 60)
    print(f"  结果:  {_pass} 通过,  {_fail} 失败,  {_warn} 警告")
    if _fail == 0:
        print("  环境就绪，可以启动插件！")
        print()
        print("  下一步:")
        print("    1. 确保插件解压在 DGHub/plugins/badwordshock/")
        print("    2. 重启 DGHub → 插件中心 → 启用「说脏话会被电！」")
        print("    3. 等待日志输出「模型就绪，开始监听！」（首次需下载 Whisper 模型 ~1.5GB）")
    else:
        print("  请先修复上面的 [FAIL] 项，然后重新运行本脚本。")
        print()
        print("  常见修复命令:")
        print("    pip install websockets numpy sounddevice faster-whisper")
        print("    (如需 AI 判断) pip install detoxify")
        print("    (如需本地 LLM) pip install transformers torch accelerate")
    print("=" * 60)


if __name__ == "__main__":
    main()
    # 双击运行时防止窗口一闪而过，方便截图/复制文字发给对方
    input("\n按 Enter 键退出...")
