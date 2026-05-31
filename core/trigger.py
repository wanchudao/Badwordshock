"""
core/trigger.py — 电击触发

职责：冷却管理 + 组装 DGHub trigger 消息 + 发送 + 日志。
"""
import time
import json


class TriggerEngine:

    def __init__(self):
        self.config: dict = {}
        self.ws = None
        self._last_ts = 0.0

    async def trigger(self, hit_word: str, full_text: str,
                      source: str = "wordlist", ai_score: float | None = None):
        """执行一次电击触发（含冷却检查）。"""
        cd = float(self.config.get("cooldown_s", 1.0))
        now = time.time()
        if now - self._last_ts < cd:
            return
        if self.ws is None:
            return
        self._last_ts = now

        action = self.config.get("trigger_action", "both")

        # 组装 trigger 消息体
        trigger_msg = {
            "op": "trigger",
            "action": action,
            "delta_pct": int(self.config.get("delta_pct", 40)),
            "strength_mode": "rollback",
            "duration_s": float(self.config.get("duration_s", 2.0)),
            "channel": self.config.get("channel", "both"),
            "label": f"[{'词库' if source == 'wordlist' else 'AI判断'}] 脏话命中：{hit_word}",
        }
        # 只有 action 包含 waveform 时才需要 preset
        if action in ("both", "waveform"):
            trigger_msg["preset"] = self.config.get("preset", "CS2-受伤")

        msgs = [
            trigger_msg,
            {
                "op": "log", "level": "info",
                "message": (
                    f"[badwordshock] 命中『{hit_word}』"
                    f" | 来源: {source}"
                    f" | 原文: {full_text!r}"
                    + (f" | AI分数: {ai_score:.2f}" if ai_score is not None else "")
                ),
            },
            {
                "op": "status", "fields": {
                    "display_status": f"最近命中：{hit_word}",
                    "last_text": full_text,
                },
            },
        ]
        for m in msgs:
            try:
                await self.ws.send(json.dumps(m, ensure_ascii=False))
            except Exception as e:
                print(f"[trigger] 发送失败: {e}")
