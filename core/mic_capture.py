"""
core/mic_capture.py — 麦克风采集 + 简易 VAD

注意：numpy / sounddevice 只在 run() 方法内部 import，
确保插件缺少这些依赖时也能先连上 DGHub。
"""
import threading
import queue
import time
import traceback

SAMPLE_RATE   = 16000
BLOCK_MS      = 30
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000  # 480

SILENCE_TAIL_MS = 600
MAX_UTTER_MS    = 8000
MIN_UTTER_MS    = 250


class MicCapture(threading.Thread):

    def __init__(self, utter_q: queue.Queue, get_cfg, status_q: queue.Queue | None = None):
        super().__init__(daemon=True, name="MicCapture")
        self.utter_q  = utter_q
        self.status_q = status_q
        self.get_cfg  = get_cfg
        self._stop    = threading.Event()

    def _status(self, level: str, msg: str):
        if self.status_q is not None:
            try:
                self.status_q.put_nowait((level, msg))
            except queue.Full:
                pass

    def stop(self):
        self._stop.set()

    # ── 设备选择 ──

    def _pick_device(self, sd) -> int | None:
        name = (self.get_cfg().get("mic_device") or "").strip()
        if not name:
            return None
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0 and name.lower() in dev["name"].lower():
                    print(f"[mic] 找到设备 #{i}: {dev['name']}")
                    return i
            print(f"[mic] 未找到含 '{name}' 的设备，使用默认")
        except Exception as e:
            print(f"[mic] 查询设备失败: {e}")
        return None

    # ── 主循环 ──

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError as e:
            self._status("error", f"麦克风缺少依赖: {e}")
            return

        device = self._pick_device(sd)
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                dtype="float32", blocksize=BLOCK_SAMPLES,
                                device=device) as stream:
                self._status("ok", f"麦克风已启动, {SAMPLE_RATE}Hz")
                self._loop(stream, np)
        except Exception as e:
            self._status("error", f"麦克风采集异常: {e}")
            traceback.print_exc()

    def _loop(self, stream, np):
        buf: list = []
        voiced_ms = silence_ms = 0
        in_speech = False

        while not self._stop.is_set():
            cfg       = self.get_cfg()
            enabled   = cfg.get("enabled", True)
            threshold = float(cfg.get("vad_threshold", 0.012))

            if not enabled:
                buf.clear()
                voiced_ms = silence_ms = 0
                in_speech = False
                time.sleep(0.1)
                continue

            try:
                data, overflowed = stream.read(BLOCK_SAMPLES)
            except Exception as e:
                print(f"[mic] 读帧失败: {e}")
                time.sleep(0.01)
                continue
            if overflowed:
                print("[mic] 缓冲区溢出")

            pcm = data[:, 0] if data.ndim > 1 else data.flatten()
            rms = float(np.sqrt(np.mean(pcm * pcm) + 1e-12))

            if rms >= threshold:
                in_speech = True
                voiced_ms += BLOCK_MS
                silence_ms = 0
                buf.append(pcm.copy())
            elif in_speech:
                silence_ms += BLOCK_MS
                buf.append(pcm.copy())

            if in_speech and (silence_ms >= SILENCE_TAIL_MS or voiced_ms >= MAX_UTTER_MS):
                if voiced_ms >= MIN_UTTER_MS and buf:
                    audio = np.concatenate(buf, axis=0)
                    try:
                        self.utter_q.put_nowait(audio)
                    except queue.Full:
                        try:
                            self.utter_q.get_nowait()
                            self.utter_q.put_nowait(audio)
                        except Exception:
                            pass
                buf.clear()
                voiced_ms = silence_ms = 0
                in_speech = False
