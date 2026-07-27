import asyncio
import time
from typing import Callable, Dict, Any
from dataclasses import dataclass

from config import EMOTION_BASE_CONFIG, ActionPriority
from vts_controller import VTSController


@dataclass
class Motion:
    name: str
    emotion_key: str
    duration: float
    priority: ActionPriority
    intensity: float
    text_to_speak: str = ""


class ActionScheduler:
    def __init__(self):
        self.vts = VTSController()
        
        self.active_states: Dict[ActionPriority, Motion] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        
        self.on_action_start: Callable[[Motion], None] = lambda x: None
        self.on_action_end: Callable[[Motion], None] = lambda x: None

        if not self.vts.connect():
            print("⚠️ VTS 连接失败，程序可能无法控制模型")

    def add_emotion_action(self, emotion: str, intensity: float = 1.0, text: str = "", priority: ActionPriority = ActionPriority.TALKING):
        if emotion not in EMOTION_BASE_CONFIG:
            print(f"⚠️ 未知情绪配置: {emotion}")
            return

        config = EMOTION_BASE_CONFIG[emotion]
        
        duration = config.get("duration", 1.0)
        
        motion = Motion(
            name=f"{priority.name}_{emotion}",
            emotion_key=emotion,
            duration=duration,
            priority=config.get("priority", ActionPriority.TALKING),
            intensity=intensity,
            text_to_speak=text
        )
        
        asyncio.run_coroutine_threadsafe(self.queue.put(motion), self._get_event_loop())

    def add_reaction_action(self, hotkey_id: str, duration: float = 2.0):
        motion = Motion(
            name=f"REACTION_{hotkey_id}",
            emotion_key="",
            duration=duration,
            priority=ActionPriority.REACTION,
            intensity=1.0,
            text_to_speak=""
        )
        asyncio.run_coroutine_threadsafe(self.queue.put(motion), self._get_event_loop())

    async def start(self):
        self._running = True
        print("🚀 ActionScheduler 启动...")
        await self._switch_state(Motion("idle", "Peaceful", 0, ActionPriority.IDLE, 1.0))
        
        while self._running:
            try:
                motion = await self.queue.get()
                await self._process_motion(motion)
            except Exception as e:
                print(f"❌ 调度器错误: {e}")

    def stop(self):
        self._running = False
        self.vts.close()

    async def _process_motion(self, new_motion: Motion):
        current_highest_priority = ActionPriority.IDLE
        for priority in ActionPriority:
            if priority in self.active_states:
                current_highest_priority = priority
                break
        
        current_highest_motion = self.active_states.get(current_highest_priority)

        if new_motion.priority.value <= (current_highest_motion.priority.value if current_highest_motion else 999):
             await self._switch_state(new_motion)
        else:
            print(f"⏳ 动作被拦截: [{new_motion.name}] 优先级不足")

    async def _switch_state(self, new_motion: Motion):
        target_priority = new_motion.priority
        
        priorities_to_cancel = [p for p in ActionPriority if p.value >= target_priority.value]
        for priority in priorities_to_cancel:
            if priority in self.active_states:
                old_motion = self.active_states[priority]
                print(f"🚫 中断动作: [{old_motion.name}]")
                del self.active_states[priority]
                self.on_action_end(old_motion)

        self.active_states[target_priority] = new_motion
        self.on_action_start(new_motion)
        print(f"🎭 执行动作: [{new_motion.name}] (优先级: {target_priority.name})")
        
        await self._execute_motion(new_motion)
        
        if target_priority in self.active_states and self.active_states[target_priority] == new_motion:
            del self.active_states[target_priority]
            self.on_action_end(new_motion)
            if not self.active_states:
                 await self._switch_state(Motion("idle_fallback", "Peaceful", 0, ActionPriority.IDLE, 1.0))

    async def _execute_motion(self, motion: Motion):
        if motion.emotion_key:
            config = EMOTION_BASE_CONFIG.get(motion.emotion_key)
            if config:
                exp_file = config.get("expression_file")
                if exp_file:
                    exp_name = exp_file.replace(".exp3.json", "")
                    self.vts.activate_expression(exp_name, fade_time=0.2)
                
                params = config.get("base_params", {})
                if params:
                    adjusted_params = {}
                    for param_id, base_value in params.items():
                        adjusted_params[param_id] = base_value * motion.intensity
                    
                    self.vts.set_parameters(adjusted_params)

        if motion.text_to_speak:
            await asyncio.to_thread(self._dummy_tts_call, motion.text_to_speak)

        if motion.duration > 0:
            await asyncio.sleep(motion.duration)

    def _get_event_loop(self):
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.new_event_loop()

    def _dummy_tts_call(self, text):
        print(f"🗣️ [TTS 模拟] 正在说话: {text}")
