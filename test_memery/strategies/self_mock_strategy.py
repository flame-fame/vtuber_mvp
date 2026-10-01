# strategies/self_mock_strategy.py
import random
from strategies import BaseStrategy

class SelfMockStrategy(BaseStrategy):
    name = "self_mock"

    TEMPLATES = [
        "{user_input}\n\n（用自嘲的语气回应，可以调侃自己是人工智障/没文化/数学不好等，但要保持傲娇）",
        "{user_input}\n\n（假装很菜，但结尾一定要反转让自己显得可爱，例如：虽然我菜但我美啊）",
        "{user_input}\n\n（用一个自黑的笑话回应，最好带点表情和动作）",
    ]

    def build_prompt(self, user_input: str) -> str:
        return random.choice(self.TEMPLATES).format(user_input=user_input)