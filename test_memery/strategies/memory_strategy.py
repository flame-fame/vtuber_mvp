# strategies/memory_strategy.py
"""
记忆检索策略：从自身信念库/经历库召回相关记忆
"""
from strategies import BaseStrategy

class MemoryStrategy(BaseStrategy):
    name = "memory"

    def build_prompt(self, user_input: str) -> str:
        # 优先召回自身信念
        memories = self.brain.memory.search(user_input, prefer_self=True)
        if memories:
            ctx = self.brain.memory.format_for_prompt(memories)
            return (
                f"【你的既有信念】\n{ctx}\n\n"
                f"【当前用户说】{user_input}\n\n"
                f"请保持与上述信念一致，用臭美语气回应。"
            )
        # 没命中降级为普通回应
        return user_input