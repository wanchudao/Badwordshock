"""
core/matcher.py — 词库匹配

判断一段文本里有没有脏话。
- 中文：整词子串匹配
- 英文：整 token 完全相等
- 白名单优先：命中白名单的词绝对不触发
"""
import re
import sys
import traceback
from pathlib import Path
from core.normalizer import normalize, normalize_word

# PyInstaller 兼容
if getattr(sys, 'frozen', False):
    _PLUGIN_DIR   = Path(sys.executable).parent
else:
    _PLUGIN_DIR   = Path(__file__).resolve().parent.parent
_BADWORDS_DIR = _PLUGIN_DIR / "badwords"


class _WordList:
    """单个词库文件（带热重载）。"""
    def __init__(self, path: Path):
        self._path  = path
        self._words: set[str] = set()
        self._mtime = 0.0

    def get(self) -> set[str]:
        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            return set()
        if mtime != self._mtime:
            self._words = self._load()
            self._mtime = mtime
        return self._words

    def _load(self) -> set[str]:
        words: set[str] = set()
        try:
            for line in self._path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                w = normalize_word(line)
                if w:
                    words.add(w)
        except Exception:
            print(f"[matcher] 加载词库失败: {self._path}")
            traceback.print_exc()
        return words


# ── 模块级词库对象 ──
_wl_zh        = _WordList(_BADWORDS_DIR / "default_zh.txt")
_wl_en        = _WordList(_BADWORDS_DIR / "default_en.txt")
_wl_whitelist = _WordList(_BADWORDS_DIR / "whitelist.txt")


def _zh_chars(text: str) -> str:
    return "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")


def _is_cn(word: str) -> bool:
    n = sum(1 for c in word if "\u4e00" <= c <= "\u9fff")
    return n > len(word) / 2


def match(
    raw_text: str,
    use_default_zh: bool = True,
    use_default_en: bool = True,
    use_default_wl: bool = True,
    custom_words:  str = "",
    exclude_words: str = "",
    use_variant:   bool = True,
    use_alias:     bool = True,
) -> list[str]:
    """返回命中的脏话词列表，空列表 = 未命中。"""
    text = normalize(raw_text, use_variant=use_variant, use_alias=use_alias)
    if not text:
        return []

    # 组装词库
    bad: set[str] = set()
    if use_default_zh:
        bad |= _wl_zh.get()
    if use_default_en:
        bad |= _wl_en.get()
    for w in re.split(r"[,\s，、;；]+", custom_words):
        w = normalize_word(w.strip())
        if w:
            bad.add(w)
    if not bad:
        return []

    # 组装白名单
    wl: set[str] = set()
    if use_default_wl:
        wl |= _wl_whitelist.get()
    for w in re.split(r"[,\s，、;；]+", exclude_words):
        w = normalize_word(w.strip())
        if w:
            wl.add(w)

    # 白名单预检
    for w in wl:
        if w and w in text:
            text = text.replace(w, "")
    if not text:
        return []

    # 匹配
    zh   = _zh_chars(text)
    en_tk = set(re.findall(r"[a-z0-9]+", text))
    hits: list[str] = []
    for w in bad:
        if w in wl:
            continue
        if _is_cn(w):
            if w in zh:
                hits.append(w)
        else:
            if w in en_tk:
                hits.append(w)
    return hits
