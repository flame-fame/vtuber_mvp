# strategies/extend_strategy.py
from strategies import BaseStrategy

class ExtendStrategy(BaseStrategy):
    name = "extend"

    def build_prompt(self, user_input: str) -> str:
        return (
            f"{user_input}\n\n"
            f"（顺着用户的话题往下延伸一个相关的小话题，展示你懂很多，"
            f"但别超过 100 字，最后用一个反问句收尾，把话题抛回给用户）"
        )