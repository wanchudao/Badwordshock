"""
core/ai_judge.py — AI 智能判断

词库未命中时用 AI 判断是否脏话。
支持 Detoxify（轻量）和本地 LLM（更准）。

注意：所有 AI 依赖都在方法内部 import，按需加载。
"""
import traceback

MODE_WORDLIST_ONLY    = "wordlist_only"
MODE_WORDLIST_THEN_AI = "wordlist_then_ai"
MODE_AI_ONLY          = "ai_only"


class _DetoxifyBackend:
    def __init__(self):
        self._model = None

    def _ensure(self):
        if self._model is not None:
            return
        try:
            from detoxify import Detoxify
            self._model = Detoxify("multilingual")
            print("[ai_judge] Detoxify multilingual 加载完成")
        except ImportError:
            raise RuntimeError("缺少 detoxify，请运行: pip install detoxify")
        except Exception as e:
            raise RuntimeError(f"Detoxify 加载失败: {e}")

    def judge(self, text: str, threshold: float) -> tuple[bool, float]:
        self._ensure()
        try:
            results = self._model.predict(text)
            score = max(results.values())
            return score >= threshold, score
        except Exception as e:
            print(f"[ai_judge] Detoxify 推理失败: {e}")
            return False, 0.0


class _LocalLLMBackend:
    _PROMPT = (
        "请判断下面这句话是否包含脏话、侮辱性语言或攻击性言论。\n"
        "只回答「是」或「否」，不要解释。\n\n"
        "句子：「{text}」\n\n回答："
    )

    def __init__(self):
        self._tokenizer = None
        self._model     = None
        self._model_id  = None

    def _ensure(self, model_id: str):
        if self._model is not None and self._model_id == model_id:
            return
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            import torch
            print(f"[ai_judge] 加载 LLM: {model_id}（首次需下载，请耐心等待）")
            self._tokenizer = AutoTokenizer.from_pretrained(model_id)
            self._model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto",
            )
            self._model_id = model_id
            print(f"[ai_judge] LLM {model_id} 加载完成")
        except ImportError:
            raise RuntimeError("缺少 transformers/torch，请运行: pip install transformers torch accelerate")
        except Exception as e:
            raise RuntimeError(f"LLM 加载失败: {e}")

    def judge(self, text: str, threshold: float, model_id: str) -> tuple[bool, float]:
        self._ensure(model_id)
        try:
            import torch
            prompt = self._PROMPT.format(text=text)
            inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs, max_new_tokens=5, do_sample=False,
                    temperature=1.0,
                    pad_token_id=self._tokenizer.eos_token_id,
                )
            new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            answer = self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            print(f"[ai_judge] LLM 回答: {answer!r}")
            is_bad = answer.startswith("是")
            return is_bad, 1.0 if is_bad else 0.0
        except Exception as e:
            print(f"[ai_judge] LLM 推理失败: {e}")
            return False, 0.0


class AIJudge:

    def __init__(self):
        self._detoxify = _DetoxifyBackend()
        self._llm      = _LocalLLMBackend()
        self.config: dict = {}

    def should_use_ai(self, wordlist_hit: bool) -> bool:
        mode = self.config.get("judge_mode", MODE_WORDLIST_ONLY)
        if mode == MODE_WORDLIST_ONLY:
            return False
        if mode == MODE_AI_ONLY:
            return True
        return not wordlist_hit  # MODE_WORDLIST_THEN_AI

    def judge(self, text: str) -> tuple[bool, float]:
        backend   = self.config.get("ai_backend", "detoxify")
        threshold = float(self.config.get("ai_threshold", 70)) / 100.0
        try:
            if backend == "detoxify":
                return self._detoxify.judge(text, threshold)
            elif backend == "local_llm":
                model_id = self.config.get("local_llm_model", "Qwen/Qwen2.5-3B-Instruct")
                return self._llm.judge(text, threshold, model_id)
            else:
                print(f"[ai_judge] 未知后端: {backend}")
                return False, 0.0
        except RuntimeError as e:
            print(f"[ai_judge] {e}")
            return False, 0.0
        except Exception:
            traceback.print_exc()
            return False, 0.0
