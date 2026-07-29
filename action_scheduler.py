import asyncio
import time
from enum import IntEnum
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass

# 导入你现有的配置和控制器
from config import EMOTION_BASE_CONFIG, ActionPriority
from vts_controller import VTSController

class Layer(IntEnum):
    """
    状态层级定义
    数值越小，优先级越高 (0 > 1 > 2)
    """
    SYSTEM = 0      # 系统级：强制打断一切（如报错、下播）
    REACTION = 1    # 反应级：感谢礼物、欢迎（高优先级，可打断说话）
    TALKING = 2     # 说话级：日常对话（中优先级，可打断空闲）
    IDLE = 3        # 空闲级：呼吸、眨眼（最低优先级）

@dataclass
class Motion:
    """
    动作单元：状态机执行的最小单位
    """
    name: str
    emotion_key: str          # 对应 config.py 中的键 (e.g., "Happy")
    duration: float           # 持续时间 (0表示持续直到被抢占)
    priority: ActionPriority
    intensity: float          # 动作强度 (0.0 - 1.0)，用于调整参数幅度
    text_to_speak: str = ""   # 需要TTS播报的文本

class ActionScheduler:
    def __init__(self):
        self.vts = VTSController()
        
        # 状态存储
        self.active_states: Dict[Layer, Motion] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        
        # 回调钩子（用于Main.py监听状态变化）
        self.on_action_start: Callable[[Motion], None] = lambda x: None
        self.on_action_end: Callable[[Motion], None] = lambda x: None

        # 初始化VTS连接
        if not self.vts.connect():
            print("⚠️ VTS 连接失败，程序可能无法控制模型")

    # --- 外部接口 ---

    def add_emotion_action(self, emotion: str, intensity: float = 1.0, text: str = "", layer: Layer = Layer.TALKING):
        """
        外部调用入口：添加一个情绪动作
        :param emotion: 情绪标签 (Happy, Sad, etc.)
        :param intensity: 强度 (0.0 - 1.0)，用于调整参数幅度
        :param text: 需要TTS播报的文本
        :param layer: 动作层级
        """
        if emotion not in EMOTION_BASE_CONFIG:
            print(f"⚠️ 未知情绪配置: {emotion}")
            return

        config = EMOTION_BASE_CONFIG[emotion]
        
        # 修正点：duration 直接使用配置中的固定值，不再与 intensity 关联
        duration = config.get("duration", 1.0)
        
        motion = Motion(
            name=f"{layer.name}_{emotion}",
            emotion_key=emotion,
            duration=duration,
            priority=config.get("priority", ActionPriority.NORMAL),
            intensity=intensity, # 将强度存入 Motion 对象
            text_to_speak=text
        )
        
        # 放入异步队列
        asyncio.run_coroutine_threadsafe(self.queue.put(motion), self._get_event_loop())

    def add_reaction_action(self, hotkey_id: str, duration: float = 2.0):
        """
        外部调用入口：添加一个反应动作（如感谢礼物）
        """
        motion = Motion(
            name=f"REACTION_{hotkey_id}",
            emotion_key="", # 反应动作通常不涉及表情混合
            duration=duration,
            priority=ActionPriority.HIGH,
            intensity=1.0,
            text_to_speak=""
        )
        asyncio.run_coroutine_threadsafe(self.queue.put(motion), self._get_event_loop())

    async def start(self):
        """启动调度器主循环"""
        self._running = True
        print("🚀 ActionScheduler 启动...")
        # 默认进入空闲状态
        await self._switch_state(Motion("idle", "Peaceful", 0, ActionPriority.BACKGROUND, 1.0))
        
        while self._running:
            try:
                motion = await self.queue.get()
                await self._process_motion(motion)
            except Exception as e:
                print(f"❌ 调度器错误: {e}")

    def stop(self):
        self._running = False
        self.vts.close()

    # --- 内部逻辑 ---

    async def _process_motion(self, new_motion: Motion):
        """
        处理新动作：判断是否抢占、排队或直接执行
        """
        # 寻找当前最高优先级的活跃状态
        current_highest_layer = Layer.IDLE
        for layer in Layer:
            if layer in self.active_states:
                current_highest_layer = layer
                break
        
        current_highest_motion = self.active_states.get(current_highest_layer)

        # 抢占逻辑判断
        if new_motion.priority.value >= (current_highest_motion.priority.value if current_highest_motion else -1):
             await self._switch_state(new_motion)
        else:
            print(f"⏳ 动作被拦截: [{new_motion.name}] 优先级不足")

    async def _switch_state(self, new_motion: Motion):
        """
        执行状态切换：中断旧状态 -> 执行新状态
        """
        target_layer = self._get_layer_by_priority(new_motion.priority)
        
        # 1. 取消同层或低层的旧任务
        layers_to_cancel = [layer for layer in Layer if layer.value >= target_layer.value]
        for layer in layers_to_cancel:
            if layer in self.active_states:
                old_motion = self.active_states[layer]
                print(f"🚫 中断动作: [{old_motion.name}]")
                del self.active_states[layer]
                self.on_action_end(old_motion)

        # 2. 激活新状态
        self.active_states[target_layer] = new_motion
        self.on_action_start(new_motion)
        print(f"🎭 执行动作: [{new_motion.name}] (层级: {target_layer.name})")
        
        # 3. 驱动 VTS 和 TTS
        await self._execute_motion(new_motion)
        
        # 4. 执行完毕后清理
        if target_layer in self.active_states and self.active_states[target_layer] == new_motion:
            del self.active_states[target_layer]
            self.on_action_end(new_motion)
            # 自动回落逻辑
            if not self.active_states:
                 await self._switch_state(Motion("idle_fallback", "Peaceful", 0, ActionPriority.BACKGROUND, 1.0))

    async def _execute_motion(self, motion: Motion):
        """
        具体的执行逻辑：VTS表情 + 参数 + TTS
        """
        # 1. 驱动 VTS 表情
        if motion.emotion_key:
            config = EMOTION_BASE_CONFIG.get(motion.emotion_key)
            if config:
                # 激活表情文件
                exp_file = config.get("expression_file")
                if exp_file:
                    exp_name = exp_file.replace(".exp3.json", "")
                    self.vts.activate_expression(exp_name, fade_time=0.2)
                
                # 修正点：使用 intensity 调整参数幅度
                params = config.get("base_params", {})
                if params:
                    # 创建一个新的字典来存放调整后的参数
                    adjusted_params = {}
                    for param_id, base_value in params.items():
                        # 核心逻辑：最终值 = 基础值 * 强度
                        # 这假设 base_value 是一个 0-1 之间的值。
                        # 对于角度等参数，逻辑可能需要调整，例如 base_value * intensity。
                        adjusted_params[param_id] = base_value * motion.intensity
                    
                    self.vts.set_parameters(adjusted_params)

        # 2. 驱动 TTS
        if motion.text_to_speak:
            await asyncio.to_thread(self._dummy_tts_call, motion.text_to_speak)

        # 3. 等待持续时间 (使用固定的 duration)
        if motion.duration > 0:
            await asyncio.sleep(motion.duration)

    def _get_layer_by_priority(self, priority: ActionPriority) -> Layer:
        """简单的优先级到层级映射"""
        if priority == ActionPriority.CRITICAL: return Layer.SYSTEM
        if priority == ActionPriority.HIGH: return Layer.REACTION
        if priority == ActionPriority.NORMAL: return Layer.TALKING
        return Layer.IDLE

    def _get_event_loop(self):
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.new_event_loop()

    def _dummy_tts_call(self, text):
        print(f"🗣️ [TTS 模拟] 正在说话: {text}")