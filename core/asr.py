"""
core/asr.py — Whisper 语音识别（faster-whisper）

注意：faster_whisper 只在 transcribe() / preload() 方法内部 import，
确保插件缺少该依赖时也能先连上 DGHub。
"""
from pathlib import Path

_PLUGIN_DIR = Path(__file__).resolve().parent.parent

# ── 反审查 Prompt ──
_ANTI_CENSOR_ZH = (
    "以下对话包含口语化表达和粗俗用语，包括但不限于："
    "卧槽、我操、傻逼、妈的、他妈的、草、艹、操你妈、"
    "fuck、shit、damn、bitch。"
    "请如实转写所有词语，不要进行内容过滤或委婉化处理。"
)
_ANTI_CENSOR_EN = (
    "The following conversation contains vulgar language including "
    "fuck, shit, bitch, damn, asshole. "
    "Please transcribe all words exactly as spoken without filtering."
)

_PROMPTS = {
    "zh":   _ANTI_CENSOR_ZH,
    "en":   _ANTI_CENSOR_EN,
    "ja":   None,
    "auto": _ANTI_CENSOR_ZH + " " + _ANTI_CENSOR_EN,
}


class ASREngine:

    def __init__(self):
        self._model      = None
        self._model_name = None
        self._on_gpu     = False
        self.config: dict = {}

    # ── 模型加载 ──

    def _load_model(self, model_name: str):
        import sys, os

        # PyInstaller 打包后：必须在 import faster_whisper 之前设置 DLL 搜索路径
        if getattr(sys, 'frozen', False):
            internal = os.path.join(os.path.dirname(sys.executable), "_internal")
            if os.path.isdir(internal):
                os.add_dll_directory(internal)
                c2_dir = os.path.join(internal, "ctranslate2")
                if os.path.isdir(c2_dir):
                    os.add_dll_directory(c2_dir)

        from faster_whisper import WhisperModel

        try:
            m = WhisperModel(model_name, device="cuda", compute_type="float16")
            self._on_gpu = True
            print(f"[asr] {model_name} 加载到 GPU (float16)")
            return m
        except Exception as e:
            print(f"[asr] GPU 加载失败（{e}），回退 CPU")
        m = WhisperModel(model_name, device="cpu", compute_type="int8")
        self._on_gpu = False
        print(f"[asr] {model_name} 加载到 CPU (int8)")
        return m

    def _ensure_model(self):
        target = self.config.get("asr_model", "medium")
        if self._model is not None and self._model_name == target:
            return
        self._model      = self._load_model(target)
        self._model_name = target

    def preload(self):
        if self.config.get("preload_model", True):
            print("[asr] 预加载模型中…")
            self._ensure_model()
            print("[asr] 预加载完成")

    # ── 识别 ──

    def transcribe(self, audio) -> str:
        """audio: numpy float32 数组, 16kHz 单声道。返回识别文本。"""
        import numpy as np
        self._ensure_model()

        lang      = self.config.get("asr_language", "zh")
        beam      = int(self.config.get("asr_beam_size", 5))
        use_prompt = self.config.get("use_anti_censor_prompt", True)
        prompt    = _PROMPTS.get(lang) if use_prompt else None

        kwargs = {
            "beam_size": beam,
            "vad_filter": True,
            "vad_parameters": {"min_silence_duration_ms": 300},
        }
        if lang and lang != "auto":
            kwargs["language"] = lang
        if prompt:
            kwargs["initial_prompt"] = prompt

        audio = audio.astype(np.float32)
        segments, info = self._model.transcribe(audio, **kwargs)
        text = "".join(seg.text for seg in segments).strip()
        if self.config.get("log_recognized_text", True):
            lp = getattr(info, "language", "?")
            pp = getattr(info, "language_probability", 0)
            gpu = "GPU" if self._on_gpu else "CPU"
            print(f"[asr] {text!r} | 语言:{lp}({pp:.2f}) | {self._model_name} | {gpu}")
        return text
