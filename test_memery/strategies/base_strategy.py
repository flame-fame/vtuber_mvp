# strategies/base_strategy.py
"""
策略基类：所有响应策略的父类
新增策略只需继承 BaseStrategy 并实现 build_prompt
"""


class BaseStrategy:
    name = "base"

    def __init__(self, brain):
        """
        :param brain: AIBrain 实例，策略通过它访问记忆、模型等资源
        """
        self.brain = brain

    def build_prompt(self, user_input: str) -> str:
        """
        返回增强后的 user_input（可包含记忆上下文、指令等）
        子类必须实现
        """
        raise NotImplementedError

    def should_use(self, user_input: str) -> bool:
        """
        可选：某些策略在特定输入下才启用
        默认总是可用
        """
        return True

    def on_selected(self):
        """被选中时的回调（可用于记录状态）"""
        pass