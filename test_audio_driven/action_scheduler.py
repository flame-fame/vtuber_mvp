import asyncio
from enum import Enum
from typing import Optional
from animation_player import AnimationPlayer

class ActionPriority(Enum):
    BACKGROUND = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class ActionScheduler:
    """
    动作调度器，管理动作队列、优先级和打断逻辑。
    """
    
    def __init__(self, player: AnimationPlayer):
        self.player = player
        self.queue = asyncio.Queue()
        self.current_priority = ActionPriority.BACKGROUND.value
        self.current_action_name: Optional[str] = None
        self._running = True
        self._worker_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动调度器工作循环"""
        self._worker_task = asyncio.create_task(self._worker_loop())
    
    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            await self._worker_task
    
    async def request_action(self, action_name: str, priority: int = ActionPriority.NORMAL.value):
        """
        请求播放动作。
        如果新动作优先级高于当前，则打断当前动作并立即播放；
        否则加入队列等待。
        """
        if not action_name:
            return
        # 检查动作是否存在
        if not self.player.mapper.get_action_definition(action_name):
            print(f"⚠️ 动作 {action_name} 不存在，忽略")
            return
        
        if priority > self.current_priority:
            # 打断当前动作
            self.player.stop_current()
            self.current_priority = priority
            self.current_action_name = action_name
            # 立即播放
            asyncio.create_task(self.player.play_action_with_priority(action_name, priority, self))
            print(f"⚡ 打断当前动作，立即播放: {action_name}")
        else:
            # 加入队列（优先级相等或更低）
            await self.queue.put((action_name, priority))
            print(f"📥 动作 {action_name} 加入队列 (优先级 {priority})")
    
    async def _worker_loop(self):
        """队列处理循环"""
        while self._running:
            try:
                action_name, priority = await self.queue.get()
                # 检查是否还可以播放（可能已被更高优先级打断）
                if priority < self.current_priority:
                    # 如果队列中有更高优先级的动作已打断，则跳过本动作
                    print(f"⏭️ 跳过队列中的 {action_name}，因为已被更高优先级打断")
                    continue
                # 等待当前动作结束（如果有）
                if self.player._current_task and not self.player._current_task.done():
                    await self.player._current_task
                # 开始播放
                self.current_priority = priority
                self.current_action_name = action_name
                await self.player.play_action_with_priority(action_name, priority, self)
                # 播放完毕，清空当前优先级（设为背景级）
                self.current_priority = ActionPriority.BACKGROUND.value
                self.current_action_name = None
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ 调度器异常: {e}")