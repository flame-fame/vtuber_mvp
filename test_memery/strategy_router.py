# strategy_router.py
"""
策略路由器：按权重随机选择响应策略
支持注册新策略、动态权重、连续策略过滤
"""
import random
from typing import Dict, Optional
from strategies import (
    MemoryStrategy, PraiseStrategy, SelfMockStrategy,
    ExtendStrategy, ProbeStrategy
)


class StrategyRouter:
    def __init__(self, brain, persona=None):
        """
        :param brain: AIBrain 实例
        :param persona: PersonaLoader 实例（可选，用于覆盖权重）
        """
        self.brain = brain
        self.strategies: Dict[str, object] = {}
        self.weights: Dict[str, float] = {}
        self.recent_history = []  # 最近 3 轮策略名
        self.ban_consecutive = {"probe"}  # 禁止连续触发的策略

        # 1. 注册所有策略
        self._register_all()

        # 2. 权重优先从 persona 读，否则用默认
        if persona:
            persona_weights = persona.get_strategy_weights()
            for name, w in persona_weights.items():
                if name in self.strategies:
                    self.weights[name] = w

    def _register_all(self):
        """统一注册入口，新增策略在此加一行即可"""
        self.register(MemoryStrategy(self.brain), 0.2)
        self.register(PraiseStrategy(self.brain), 0.2)
        self.register(SelfMockStrategy(self.brain), 0.2)
        self.register(ExtendStrategy(self.brain), 0.2)
        self.register(ProbeStrategy(self.brain), 0.2)

    def register(self, strategy, weight: float):
        """注册一个策略"""
        self.strategies[strategy.name] = strategy
        self.weights[strategy.name] = weight

    def pick(self, user_input: str) -> object:
        """按权重随机选一个策略"""
        # 1. 过滤：should_use 不通过的、连续禁用的
        available = {}
        for name, w in self.weights.items():
            strat = self.strategies[name]
            if not strat.should_use(user_input):
                continue
            # 连续禁用检查
            if name in self.ban_consecutive and self.recent_history:
                if self.recent_history[-1] == name:
                    continue
            available[name] = w

        # 2. 如果全被过滤，退回全量
        if not available:
            available = {k: v for k, v in self.weights.items()}

        # 3. 按权重随机
        names = list(available.keys())
        weights = list(available.values())
        chosen_name = random.choices(names, weights=weights, k=1)[0]  # 按weights权重随机抽取1个
        chosen = self.strategies[chosen_name]

        # 4. 记录历史
        self.recent_history.append(chosen_name)
        if len(self.recent_history) > 3:
            self.recent_history.pop(0)

        chosen.on_selected()
        return chosen

    def get_recent_history(self):
        return self.recent_history.copy()