# idle_manager.py
import asyncio
import random
from dataclasses import dataclass, field
from config import IDLE_TIMEOUT


@dataclass
class IdlePhase:
    """一个空闲阶段"""
    expression: str
    action: str | None
    duration: float          # 持续秒数（-1 = 直到被打断）
    intensity: float = 0.5
    weight: float = 1.0      # 随机选择权重


# 空闲动画序列（按顺序循环，或随机）
IDLE_SEQUENCE: list[IdlePhase] = [
    IdlePhase("平静", "发呆",       duration=5.0,  intensity=0.4, weight=3),
    IdlePhase("微笑", "哼歌",       duration=6.0,  intensity=0.5, weight=2),
    IdlePhase("平静", "左右摇晃",   duration=3.5,  intensity=0.3, weight=2),
    IdlePhase("微笑", "听音乐",     duration=7.0,  intensity=0.4, weight=1),
    IdlePhase("平静", None,         duration=3.0,  intensity=0.3, weight=2),  # 纯静止
    IdlePhase("无辜", "左右摇晃",   duration=3.0,  intensity=0.4, weight=1),  # 歪头看弹幕
]

IDLE_MODE = "random"  # "sequence" | "random"


class IdleManager:
    def __init__(self, orchestrator):
        self.orch = orchestrator
        self.timeout = IDLE_TIMEOUT
        self._task: asyncio.Task | None = None
        self._active = False
        self._seq_index = 0

    def start(self):
        """启动空闲检测（在 main 中调用一次）"""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._idle_loop())

    def notify_activity(self):
        """有弹幕/回复活动时调用 → 重置计时器"""
        self._active = False  # 标记：当前不在空闲

    async def _idle_loop(self):
        """主循环：等待超时 → 播放空闲动画 → 等待 → 循环"""
        while True:
            # ① 等待空闲超时
            await asyncio.sleep(self.timeout)

            # ② 检查是否真的空闲（orchestrator 不在说话）
            if self.orch.is_busy:
                continue

            # ③ 进入空闲状态
            self._active = True
            await self._play_idle_cycle()

    async def _play_idle_cycle(self):
        """播放一轮空闲动画（直到被 notify_activity 打断）"""
        while self._active and not self.orch.is_busy:
            phase = self._pick_phase()

            # 执行表情 + 动作
            await self.orch.action.perform(
                expression=phase.expression,
                action=phase.action,
                intensity=phase.intensity,
            )

            # 等待持续时间（可被打断）
            if phase.duration > 0:
                try:
                    await asyncio.wait_for(
                        self._wait_for_interrupt(),
                        timeout=phase.duration,
                    )
                    # 如果被唤醒（新弹幕来了），立即退出
                    break
                except asyncio.TimeoutError:
                    # 正常超时，继续下一个阶段
                    pass
            else:
                # duration=-1：等到被打断
                await self._wait_for_interrupt()
                break

        # 退出空闲，恢复平静
        await self.orch.action.stop_action()
        await self.orch.action.set_expression("平静", 1.0)

    def _pick_phase(self) -> IdlePhase:
        if IDLE_MODE == "sequence":
            phase = IDLE_SEQUENCE[self._seq_index % len(IDLE_SEQUENCE)]
            self._seq_index += 1
            return phase
        else:
            # 加权随机
            weights = [p.weight for p in IDLE_SEQUENCE]
            return random.choices(IDLE_SEQUENCE, weights=weights, k=1)[0]

    async def _wait_for_interrupt(self):
        """等待被唤醒（新弹幕到达时 notify_activity 会设置标志）"""
        while self._active:
            await asyncio.sleep(0.1)
            if not self._active:
                return

    def stop(self):
        """完全停止空闲管理"""
        self._active = False
        if self._task and not self._task.done():
            self._task.cancel()