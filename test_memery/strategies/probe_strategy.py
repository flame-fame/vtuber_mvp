# strategies/probe_strategy.py
from strategies import BaseStrategy

class ProbeStrategy(BaseStrategy):
    name = "probe"

    def build_prompt(self, user_input: str) -> str:
        return (
            f"{user_input}\n\n"
            f"（用好奇的语气追问用户一个细节，让对话继续下去。"
            f"问题要具体，不要泛泛而问，例如问『你今天吃了什么』而不是『你今天怎么样』）"
        )