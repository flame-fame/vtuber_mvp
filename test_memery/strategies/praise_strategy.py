# strategies/praise_strategy.py
import random
from strategies import BaseStrategy

class PraiseStrategy(BaseStrategy):
    name = "praise"

    TEMPLATES = [
        "{user_input}\n\n（用夸张的臭美语气夸赞用户或自己，或者把某个普通事物夸上天，要有反差感）",
        "{user_input}\n\n（先夸用户，然后顺势自夸一句，最后用 [happy:body_bounce] 收尾）",
        "{user_input}\n\n（假装很不屑，但暗地里夸自己一句，典型的傲娇式夸赞）",
    ]

    def build_prompt(self, user_input: str) -> str:
        return random.choice(self.TEMPLATES).format(user_input=user_input)