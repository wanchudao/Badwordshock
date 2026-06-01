"""
core/normalizer.py — 文本归一化

把 Whisper 识别的原始文本处理成标准形态，交给 matcher 做词库匹配。

处理顺序：小写 → 去噪 → 去重 → 同音字映射 → 拼音/缩写映射
"""
import re
import sys
from pathlib import Path

# PyInstaller 兼容
if getattr(sys, 'frozen', False):
    _PLUGIN_DIR = Path(sys.executable).parent
else:
    _PLUGIN_DIR = Path(__file__).resolve().parent.parent

# ── 同音字映射表 ──
_HOMOPHONE_MAP = {
    # 操/草 系列
    "槽": "操", "草": "操", "艹": "操", "肏": "操", "曹": "操", "糙": "操",
    # 逼/比 系列
    "笔": "逼", "币": "逼", "必": "逼", "毕": "逼", "壁": "逼", "碧": "逼", "闭": "逼",
    # 妈/马 系列
    "嬷": "妈", "麻": "妈", "马": "妈", "骂": "妈", "玛": "妈", "码": "妈",
    # 傻/沙 系列
    "沙": "傻", "啥": "傻", "杀": "傻", "纱": "傻", "砂": "傻",
    # 屌/吊 系列
    "叼": "屌", "刁": "屌", "雕": "屌", "吊": "屌",
    # 鸡/机 系列
    "机": "鸡", "激": "鸡", "基": "鸡", "几": "鸡", "叽": "鸡", "饥": "鸡",
    # 贱/见 系列
    "见": "贱", "剑": "贱", "建": "贱", "件": "贱", "健": "贱", "践": "贱",
    # 婊/表 系列
    "表": "婊",
    # 骚/搔 系列
    "搔": "骚",
    # 日 系列（Whisper 可能识别成别的）
    "入": "日",
    # 干 系列
    "甘": "干", "杆": "干", "赶": "干",
    # 尼/你 系列（注意：故意不含"拟"——避免 草拟→操你 误伤）
    "尼": "你", "泥": "你",
    # 滚 系列
    "棍": "滚",
    # 死 系列
    "四": "死",
    # 蛋 系列
    "弹": "蛋", "淡": "蛋", "旦": "蛋",
}
_HOMOPHONE_RE = re.compile("[" + "".join(re.escape(k) for k in _HOMOPHONE_MAP) + "]")

# ── 拼音缩写表（热重载）──
_ALIAS_PATH  = _PLUGIN_DIR / "badwords" / "pinyin_alias.txt"
_alias_cache: dict[str, str] | None = None
_alias_mtime: float = 0.0


def _load_aliases() -> dict[str, str]:
    global _alias_cache, _alias_mtime
    try:
        mtime = _ALIAS_PATH.stat().st_mtime
    except FileNotFoundError:
        return {}
    if _alias_cache is not None and mtime == _alias_mtime:
        return _alias_cache
    result = {}
    try:
        for line in _ALIAS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip().lower(), v.strip().lower()
            if k and v:
                result[k] = v
    except Exception:
        pass
    _alias_cache = result
    _alias_mtime = mtime
    return result


def normalize(text: str, use_variant: bool = True, use_alias: bool = True) -> str:
    """主归一化函数。"""
    text = text.lower()
    text = re.sub(r"[^\u4e00-\u9fff\u3400-\u4dbfa-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(.)\1{2,}", r"\1", text)          # 去重：操操操→操
    if use_variant:
        text = _HOMOPHONE_RE.sub(lambda m: _HOMOPHONE_MAP[m.group()], text)
    if use_alias:
        aliases = _load_aliases()
        stripped = text.strip()
        if stripped in aliases:
            text = aliases[stripped]
        else:
            for k in sorted(aliases, key=len, reverse=True):
                if k in text:
                    text = text.replace(k, aliases[k])
    return text


def normalize_word(word: str) -> str:
    """对词库里的单个词做全量归一化。"""
    return normalize(word, use_variant=True, use_alias=True)
