"""
main.py — DGHub 插件「说脏话会被电！」

严格遵循 DGHub SDK v1 协议：
  - 从 manifest.json 动态读取完整 manifest 用于 hello 握手
  - 所有重依赖（numpy/sounddevice/faster-whisper）在方法内部按需 import
  - 先连 DGHub、完成握手、接收配置，再加载模型和启动麦克风
"""
import asyncio
import json
import os
import sys
import traceback
import queue

HERE = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ── PyInstaller 打包后：提前设置 DLL 搜索路径（必须在任何 ctranslate2 相关 import 之前）──
if getattr(sys, 'frozen', False):
    _internal = os.path.join(HERE, "_internal")
    if os.path.isdir(_internal):
        os.add_dll_directory(_internal)
        _c2 = os.path.join(_internal, "ctranslate2")
        if os.path.isdir(_c2):
            os.add_dll_directory(_c2)
        _tl = os.path.join(_internal, "torch", "lib")
        if os.path.isdir(_tl):
            os.add_dll_directory(_tl)

# ── 1. 从 manifest.json 读取完整 manifest ──
def _read_manifest():
    path = os.path.join(HERE, "manifest.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

MANIFEST = _read_manifest()

# ── 2. 轻量依赖（必须可用）──
import websockets
from core.trigger    import TriggerEngine
from core.matcher    import match
from core.ai_judge   import AIJudge, MODE_WORDLIST_ONLY


class Plugin:

    def __init__(self):
        self.cfg: dict = {}
        self.ws = None
        self.trigger = TriggerEngine()
        self.judge   = AIJudge()
        # 重依赖延迟加载
        self.asr = None
        self.mic = None
        self.q: queue.Queue = queue.Queue(maxsize=8)
        self.mic_status: queue.Queue = queue.Queue()  # 麦克风线程状态上报
        self._model_ok = False
        self._done = False

    # ── helpers ──

    def _sync(self):
        self.trigger.config = self.cfg
        self.trigger.ws     = self.ws
        self.judge.config   = self.cfg
        if self.asr:
            self.asr.config = self.cfg

    async def _send(self, data: dict):
        if self.ws:
            await self.ws.send(json.dumps(data, ensure_ascii=False))

    async def _log(self, lvl: str, msg: str):
        await self._send({"op": "log", "level": lvl, "message": f"[badwordshock] {msg}"})

    # ── 握手 ──

    async def _handshake(self, token: str) -> bool:
        await self._send({"op": "hello", "token": token, "manifest": MANIFEST})
        ack = json.loads(await self.ws.recv())
        if ack.get("op") != "hello_ack":
            print(f"[main] 握手: 意外 op={ack.get('op')}")
            return False
        if not ack.get("accepted"):
            print(f"[main] 握手被拒: {ack.get('reason')}")
            return False
        print(f"[main] 握手 OK, SDK={ack.get('sdk_version')}")
        return True

    # ── 等待 config ──

    async def _wait_config(self) -> bool:
        while True:
            msg = json.loads(await self.ws.recv())
            op = msg.get("op")
            if op == "config":
                self.cfg = msg.get("data") or {}
                self._sync()
                print(f"[main] 初始配置 {len(self.cfg)} 项")
                return True
            elif op == "ping":
                await self._send({"op": "pong", "t": msg.get("t")})
            elif op == "stop":
                return False

    # ── 懒加载重依赖 ──

    def _load_asr(self) -> bool:
        if self.asr is not None:
            return True
        try:
            from core.asr import ASREngine
            self.asr = ASREngine()
            self.asr.config = self.cfg
            print("[main] ASR 引擎就绪")
            return True
        except ImportError as e:
            print(f"[main] ASR 不可用: {e}")
            return False

    def _load_mic(self) -> bool:
        try:
            from core.mic_capture import MicCapture
            self.mic = MicCapture(utter_q=self.q, get_cfg=lambda: self.cfg,
                                  status_q=self.mic_status)
            self.mic.start()
            return True
        except ImportError as e:
            print(f"[main] 麦克风模块不可用: {e}")
            return False

    # ── 模型预加载 ──

    async def _preload(self):
        if not self.asr:
            return
        loop = asyncio.get_event_loop()
        await self._log("info", "模型加载中…")
        try:
            await loop.run_in_executor(None, self.asr.preload)
            self._model_ok = True
            await self._log("info", "模型就绪，开始监听！")
        except Exception as e:
            await self._log("error", f"模型加载失败: {e}")
            traceback.print_exc()

    # ── ASR 消费 ──

    async def _mic_status_reader(self):
        """转发麦克风线程的状态消息到 DGHub 日志。"""
        loop = asyncio.get_event_loop()
        while not self._done:
            try:
                level, msg = await loop.run_in_executor(None, self.mic_status.get)
            except Exception:
                break
            await self._log(level, msg)

    async def _consumer(self):
        loop = asyncio.get_event_loop()
        while not self._done:
            audio = await loop.run_in_executor(None, self.q.get)
            if audio is None:
                return
            while not self._model_ok and not self._done:
                await asyncio.sleep(0.5)
            if self._done or not self.asr:
                continue

            try:
                text = await loop.run_in_executor(None, self.asr.transcribe, audio)
            except Exception as e:
                await self._log("error", f"ASR 失败: {e}")
                continue
            if not text:
                continue

            if self.cfg.get("log_recognized_text", True):
                await self._log("info", f"识别: {text!r}")

            hits = match(
                text,
                use_default_zh = self.cfg.get("use_default_zh", True),
                use_default_en = self.cfg.get("use_default_en", True),
                use_default_wl = self.cfg.get("use_default_whitelist", True),
                custom_words   = self.cfg.get("custom_words", ""),
                exclude_words  = self.cfg.get("exclude_words", ""),
                use_variant    = self.cfg.get("use_variant_normalize", True),
                use_alias      = self.cfg.get("use_pinyin_alias", True),
            )
            if hits:
                await self.trigger.trigger(hits[0], text, "wordlist")
                continue

            if self.judge.should_use_ai(wordlist_hit=False):
                try:
                    is_bad, score = await loop.run_in_executor(None, self.judge.judge, text)
                except Exception as e:
                    await self._log("error", f"AI 失败: {e}")
                    continue
                if is_bad:
                    label = text[:10] + ("…" if len(text) > 10 else "")
                    await self.trigger.trigger(label, text, "ai", score)

    # ── 消息循环 ──

    async def _messages(self):
        async for raw in self.ws:
            try:
                m = json.loads(raw)
            except json.JSONDecodeError:
                continue
            op = m.get("op")
            if op == "config":
                self.cfg = m.get("data") or {}
                self._sync()
            elif op == "config_changed":
                k, v = m.get("key"), m.get("value")
                self.cfg[k] = v
                self._sync()
                if k == "asr_model" and self.asr:
                    self.asr._model = None
                    self.asr._model_name = None
                    self._model_ok = False
                    asyncio.create_task(self._preload())
            elif op == "ping":
                await self._send({"op": "pong", "t": m.get("t")})
            elif op == "stop":
                await self._log("info", f"停止: {m.get('reason')}")
                return
            elif op == "device_info":
                pass  # 仅日志

    # ── 主入口 ──

    async def run(self):
        host  = os.environ.get("DGHUB_HOST", "127.0.0.1")
        port  = os.environ.get("DGHUB_PORT", "8000")
        token = os.environ.get("DGHUB_TOKEN", "")
        if not token:
            print("[main] 缺少 DGHUB_TOKEN"); sys.exit(1)

        url = f"ws://{host}:{port}/ws/plugin?token={token}"
        print(f"[main] 连接 {host}:{port} …")

        try:
            async with websockets.connect(url, max_size=None) as ws:
                self.ws = ws
                self._sync()

                if not await self._handshake(token):
                    return
                if not await self._wait_config():
                    return

                # 后台加载模型
                self._load_asr()
                asyncio.create_task(self._preload())

                # 启动麦克风
                self._load_mic()

                # 启动 ASR 消费 + 麦克风状态转发
                consumer = asyncio.create_task(self._consumer())
                status_reader = asyncio.create_task(self._mic_status_reader())
                await self._log("info", "插件已就绪")

                try:
                    await self._messages()
                finally:
                    self._done = True
                    if self.mic:
                        self.mic.stop()
                    try:
                        self.q.put_nowait(None)
                    except queue.Full:
                        pass
                    try:
                        self.mic_status.put_nowait(("", ""))
                    except queue.Full:
                        pass
                    consumer.cancel()
                    status_reader.cancel()
                    try:
                        await consumer
                    except asyncio.CancelledError:
                        pass
                    try:
                        await status_reader
                    except asyncio.CancelledError:
                        pass

        except websockets.exceptions.ConnectionClosed as e:
            print(f"[main] 连接断开: {e}")
        except Exception:
            traceback.print_exc()
            sys.exit(1)


def main():
    asyncio.run(Plugin().run())


if __name__ == "__main__":
    main()
