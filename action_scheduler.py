import time
import threading
import random
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import deque
from config import *
from vts_controller import VTSController

# ==================== 数据结构定义 ====================
@dataclass
class Action:
    """单个动作定义"""
    action_id: str
    action_type: ActionType
    priority: ActionPriority
    data: Dict[str, Any]
    duration: float = 2.0          # 动作持续时间（秒）
    cooldown: float = 3.0          # 冷却时间（秒）
    fade_in: float = 0.3           # 淡入时间
    fade_out: float = 0.3          # 淡出时间
    interruptible: bool = True     # 是否可被中断
    tags: List[str] = field(default_factory=list)  # 标签，用于分组管理

@dataclass
class ActionGroup:
    """动作组 - 一组动作的集合"""
    group_id: str
    name: str
    actions: List[Action]
    priority: ActionPriority
    cooldown: float = 3.0

# ==================== 动作调度器 ====================

class ActionScheduler:
    """
    动作调度器 - 管理VTS动作的优先级、冷却和队列
    
    功能：
    1. 优先级队列：高优先级动作可打断低优先级
    2. 冷却管理：同一动作在冷却期内不重复触发
    3. 平滑过渡：支持淡入淡出
    4. 复合动作：一组动作组合执行
    5. 空闲状态：没有动作时回到默认状态
    """

    def __init__(self):
        # 初始化VTS控制器
        self.vts = VTSController()
        # 初始化空闲状态参数
        self.idle_config = EMOTION_BASE_CONFIG.get("Peaceful", {}).get("base_params", {})

        # 动作队列
        self.action_queue = deque()
        self.current_action = None
        self.current_action_start_time = 0

        # 冷却管理
        self.cooldowns: Dict[str, float] = {}  # action_id -> 最后触发时间

        # 状态
        self.is_running = False
        self.is_paused = False
        self.lock = threading.Lock()
        self.scheduler_thread = None

        # 回调
        self.on_action_start = None  # Callable[[Action], None]
        self.on_action_end = None    # Callable[[Action], None]
        self.on_action_error = None  # Callable[[Action, Exception], None]

        # 预定义的表情映射
        self.expression_map: Dict[str, Dict] = {}

    # ========== 启动/停止 ==========

    def start(self):
        """启动调度器"""
        # 检查VTS是否建立
        if not self.vts:
            print("新建VTS实例失败")
            return
        # 检查是否已启动
        if self.is_running:
            return
        # 启动调度线程
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.scheduler_thread.start()
        print("🎬 动作调度器已启动")

    def stop(self):
        """停止调度器"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=2)
        self.vts.close()
        print("🛑 动作调度器已停止")

    def pause(self):
        self.is_paused = True
        print("⏸ 动作调度器已暂停")
    
    def resume(self):
        self.is_paused = False
        print("▶️ 动作调度器已恢复")
    
    # ========== 核心调度循环 ==========

    def _run_loop(self):
        """调度主循环"""
        while self.is_running:
            try:
                if not self.is_paused:
                    self._tick()
                time.sleep(0.05)  # 20fps
            except Exception as e:
                if self.on_action_error:
                    self.on_action_error(self.current_action, e)
                print(f"⚠️ 调度循环错误: {e}")

    def _tick(self):
        """每帧执行"""
        current_time = time.time()

        # 1. 检查当前动作是否结束
        if self.current_action:
            elapsed = current_time - self.current_action_start_time
            if elapsed >= self.current_action.duration:
                self._end_current_action()

        # 2. 处理队列
        if not self.action_queue and not self.current_action:
            # 没有动作时执行空闲状态
            self._apply_idle()
            return

        # 3. 从队列取出下一个动作
        if not self.current_action:
            self._start_next_action()
            return

        # 4. 检查是否有更高优先级的动作
        if self.action_queue:
            next_action = self.action_queue[0]
            if next_action.priority.value > self.current_action.priority.value:
                if self.current_action.interruptible:
                    self._interrupt_current_action(next_action)
                else:
                    # 不可中断，但高优先级动作入队等待
                    pass

    # ========== 动作管理 ==========

    def add_action(self, action: Action, immediate: bool = False):
        """
        添加动作到队列
        
        Args:
            action: 动作对象
            immediate: 是否立即执行（插入队首）
        """
        with self.lock:
            # 检查冷却
            if not self._check_cooldown(action):
                return

            # 更新冷却时间
            self.cooldowns[action.action_id] = time.time()

            if immediate:
                self.action_queue.appendleft(action)
            else:
                self.action_queue.append(action)

            # 如果队列太长，丢弃低优先级动作
            if len(self.action_queue) > 50:
                self._trim_queue()

    def add_actions(self, actions: List[Action], immediate: bool = False):
        """批量添加动作"""
        for action in actions:
            self.add_action(action, immediate)

    def add_emotion_action(self, emotion: str, intensity: float = 0.5, immediate: bool = False):
        """
        根据情绪添加动作（便捷方法）
        
        Args:
            emotion: 情绪名称 (Happy/Angry/Sad/Surprised/Idle)
            intensity: 强度 0.0-1.0
        """
        action = self._create_emotion_action(emotion, intensity)
        if action:
            self.add_action(action, immediate)

    def clear_queue(self):
        """清空队列"""
        with self.lock:
            self.action_queue.clear()

    def interrupt_all(self):
        """中断所有动作"""
        with self.lock:
            self.action_queue.clear()
            if self.current_action:
                self._end_current_action()

    # ========== 内部方法 ==========

    def _start_next_action(self):
        """开始下一个动作"""
        if not self.action_queue:
            return

        with self.lock:
            self.current_action = self.action_queue.popleft()
            self.current_action_start_time = time.time()

        self._execute_action(self.current_action)

        if self.on_action_start:
            self.on_action_start(self.current_action)

    def _execute_action(self, action: Action):
        """执行具体动作"""
        try:
            if action.action_type == ActionType.EXPRESSION:
                self._execute_expression(action)
            elif action.action_type == ActionType.PARAMETER:
                self._execute_parameter(action)
            elif action.action_type == ActionType.HOTKEY:
                self._execute_hotkey(action)
            elif action.action_type == ActionType.MOVE:
                self._execute_move(action)
            elif action.action_type == ActionType.COMPOSITE:
                self._execute_composite(action)
        except Exception as e:
            if self.on_action_error:
                self.on_action_error(action, e)
            print(f"❌ 执行动作失败 [{action.action_id}]: {e}")

    def _execute_expression(self, action: Action):
        """执行表情动作"""
        expression_file = action.data.get("expression_file")
        active = action.data.get("active", True)
        fade_time = action.data.get("fade_time", action.fade_in)

        self.vts.activate_expression(expression_file, fade_time, active)

        # 同时应用参数（如果有）
        if "parameters" in action.data:
            self.vts.set_parameters(action.data["parameters"], fade_time=fade_time)

    def _execute_parameter(self, action: Action):
        """执行参数动作"""
        parameters = action.data.get("parameters", {})
        self.vts.set_parameters(parameters, fade_time=action.fade_in)

    def _execute_hotkey(self, action: Action):
        """执行热键动作"""
        hotkey_id = action.data.get("hotkey_id")
        self.vts.trigger_hotkey(hotkey_id)

    def _execute_move(self, action: Action):
        """执行移动动作"""
        self.vts.move_model(
            x=action.data.get("x", 0),
            y=action.data.get("y", 0),
            rotation=action.data.get("rotation", 0),
            size=action.data.get("size", 0),
            duration=action.data.get("duration", 0.5),
            relative=action.data.get("relative", False)
        )

    def _execute_composite(self, action: Action):
        """执行复合动作（按顺序执行多个子动作）"""
        sub_actions = action.data.get("sub_actions", [])
        for sub_action in sub_actions:
            self._execute_action(sub_action)
            # 简单延迟
            time.sleep(sub_action.duration * 0.1)

    def _end_current_action(self):
        """结束当前动作"""
        if self.current_action:
            # 淡出效果
            if self.current_action.fade_out > 0:
                self._apply_fade_out(self.current_action)

            old_action = self.current_action
            self.current_action = None

            if self.on_action_end:
                self.on_action_end(old_action)

    def _interrupt_current_action(self, next_action: Action = None):
        """中断当前动作"""
        # 快速淡出
        if self.current_action and self.current_action.fade_out > 0:
            self._apply_fade_out(self.current_action, fast=True)

        self.current_action = None
        # 立即执行高优先级动作
        if next_action:
            with self.lock:
                self.current_action = next_action
                self.current_action_start_time = time.time()

        self._execute_action(self.current_action)

    def _apply_idle(self):
        """应用空闲状态"""
        self.vts.set_parameters(self.idle_config)

    def _apply_fade_out(self, action: Action, fast: bool = False):
        """应用淡出效果"""
        fade_time = 0.1 if fast else action.fade_out

        # 如果是表情，停用
        if action.action_type == ActionType.EXPRESSION:
            expression_file = action.data.get("expression_file")
            if expression_file:
                self.vts.activate_expression(expression_file, fade_time, False)

        # 参数逐渐归零
        if action.action_type == ActionType.PARAMETER:
            params = action.data.get("parameters", {})
            zero_params = {k: 0.0 for k in params.keys()}
            self.vts.set_parameters(zero_params, fade_time)

    def _check_cooldown(self, action: Action) -> bool:
        """检查动作是否在冷却中"""
        if action.action_id in self.cooldowns:
            last_time = self.cooldowns[action.action_id]
            if time.time() - last_time < action.cooldown:
                # 仍然在冷却中，可以随机延迟重试或丢弃
                return False
        return True

    def _trim_queue(self):
        """修剪队列，保留高优先级动作"""
        with self.lock:
            # 按优先级排序，保留前50个
            sorted_actions = sorted(self.action_queue, 
                                  key=lambda a: a.priority.value, 
                                  reverse=True)
            self.action_queue = deque(sorted_actions[:50])

    def _create_emotion_action(self, emotion: str, intensity: float) -> Optional[Action]:
        """根据情绪名+强度，生成最终动作配置"""
        base_cfg = EMOTION_BASE_CONFIG[emotion]
        if not base_cfg:
            return None
        
        final_params = {}

        # 遍历基础参数，区分固定值 / 基础+强度系数计算值
        for key, val in base_cfg["base_params"].items():
            if key.endswith("_base"):
                param_name = key.replace("_base", "")
                coeff_key = f"{param_name}_coeff"
                base_val = val
                coeff = base_cfg["base_params"][coeff_key]
                final_params[param_name] = base_val + coeff * intensity
            elif not key.endswith("_coeff"):
                # 无强度系数的固定参数直接赋值
                final_params[key] = val

        config = {
            "expression": base_cfg["expression_file"],
            "parameters": final_params,
            "duration": base_cfg["duration"],
            "priority": base_cfg["priority"],
        }

        # 构建复合动作
        action = Action(
            action_id=f"emotion_{emotion}_{int(time.time())}",
            action_type=ActionType.COMPOSITE,
            priority=config["priority"],
            data={
                "sub_actions": [
                    Action(
                        action_id=f"emotion_{emotion}_expr",
                        action_type=ActionType.EXPRESSION,
                        priority=config["priority"],
                        data={
                            "expression_file": config["expression"],
                            "active": True,
                            "fade_time": 0.3,
                        },
                        duration=config["duration"],
                        cooldown=config["duration"] + 0.5,
                    ),
                    Action(
                        action_id=f"emotion_{emotion}_params",
                        action_type=ActionType.PARAMETER,
                        priority=config["priority"],
                        data={"parameters": config["parameters"]},
                        duration=config["duration"],
                        cooldown=config["duration"] + 0.5,
                    ),
                ]
            },
            duration=config["duration"],
            cooldown=config["duration"] + 0.5,
            interruptible=True,
        )

        return action

    # ========== 创建动作 ==========

    def create_expression_action(self, expression_file: str, 
                                  duration: float = 2.0,
                                  priority: ActionPriority = ActionPriority.NORMAL) -> Action:
        """创建表情动作"""
        return Action(
            action_id=f"expr_{expression_file}_{int(time.time())}",
            action_type=ActionType.EXPRESSION,
            priority=priority,
            data={
                "expression_file": expression_file,
                "active": True,
                "fade_time": 0.3
            },
            duration=duration,
            cooldown=duration + 1.0,
            interruptible=True
        )

    def create_parameter_action(self, parameters: Dict[str, float],
                                 duration: float = 1.0,
                                 priority: ActionPriority = ActionPriority.NORMAL) -> Action:
        """创建参数动作"""
        return Action(
            action_id=f"param_{int(time.time())}",
            action_type=ActionType.PARAMETER,
            priority=priority,
            data={"parameters": parameters},
            duration=duration,
            cooldown=0.5,
            interruptible=True
        )

    def create_hotkey_action(self, hotkey_id: str,
                              priority: ActionPriority = ActionPriority.HIGH) -> Action:
        """创建热键动作"""
        return Action(
            action_id=f"hotkey_{hotkey_id}_{int(time.time())}",
            action_type=ActionType.HOTKEY,
            priority=priority,
            data={"hotkey_id": hotkey_id},
            duration=0.5,
            cooldown=2.0,
            interruptible=False  # 热键执行通常不可中断
        )

    def create_move_action(self, x: float = 0, y: float = 0, rotation: float = 0,
                           duration: float = 0.5,
                           priority: ActionPriority = ActionPriority.LOW) -> Action:
        """创建移动动作"""
        return Action(
            action_id=f"move_{int(time.time())}",
            action_type=ActionType.MOVE,
            priority=priority,
            data={
                "x": x,
                "y": y,
                "rotation": rotation,
                "duration": duration,
                "relative": True
            },
            duration=duration + 0.5,
            cooldown=1.0,
            interruptible=True
        )
