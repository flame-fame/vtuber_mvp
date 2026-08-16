import asyncio
import time
from typing import Dict, Any, Optional, Callable
from parameter_mapper import ParameterMapper

class AnimationPlayer:
    """
    负责按时间线播放动作序列，支持线性插值，
    并维护当前表情状态，动作结束后恢复。
    """
    
    def __init__(self, mapper: ParameterMapper, vts_controller, update_interval: float = 0.05):
        """
        :param mapper: ParameterMapper 实例
        :param vts_controller: VTSController 实例（需有 set_parameters 方法）
        :param update_interval: 参数更新间隔（秒），默认 20fps
        """
        self.mapper = mapper
        self.vts = vts_controller
        self.interval = update_interval
        
        # 当前基础表情（持续状态）
        self.current_expression_name = "neutral"
        self.current_expression_params = mapper.get_expression_params("neutral")
        
        # 播放状态
        self._current_task: Optional[asyncio.Task] = None
        self._stop_flag = False
    
    def set_expression(self, expression_name: str) -> None:
        """立即设置表情（持续状态）"""
        params = self.mapper.get_expression_params(expression_name)
        if not params:
            print(f"⚠️ 未知表情: {expression_name}")
            return
        self.current_expression_name = expression_name
        self.current_expression_params = params.copy()
        # 立即注入表情参数
        vts_params = self.mapper.to_vts_params(params)
        self.vts.set_parameters(vts_params)
        print(f"🎭 表情切换到: {expression_name}")
    
    async def play_action(self, action_name: str) -> None:
        """
        异步播放一个动作。
        播放期间会覆盖当前表情参数，播放结束后恢复表情。
        """
        action_def = self.mapper.get_action_definition(action_name)
        if not action_def:
            print(f"⚠️ 未知动作: {action_name}")
            return
        
        duration = action_def.get("duration", 1.0)
        sequence = action_def.get("sequence", [])
        if not sequence:
            print(f"⚠️ 动作 {action_name} 无关键帧")
            return
        
        # 排序关键帧按时间
        keyframes = sorted(sequence, key=lambda kf: kf["time"])
        # 确保开始时间 0 存在，若不存在则插入一个空帧（沿用当前表情）
        if keyframes[0]["time"] != 0:
            keyframes.insert(0, {"time": 0.0})
        
        # 记录开始时间
        start_time = asyncio.get_event_loop().time()
        # 保存当前表情参数以便恢复
        restore_params = self.current_expression_params.copy()
        
        # 播放循环
        while not self._stop_flag:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= duration:
                break
            
            # 计算当前时间的插值参数
            current_params = self._interpolate(keyframes, elapsed)
            # 合并当前表情参数（动作中未定义的参数保留表情值）
            merged = restore_params.copy()
            merged.update(current_params)
            # 注入 VTS
            vts_params = self.mapper.to_vts_params(merged)
            self.vts.set_parameters(vts_params)
            
            await asyncio.sleep(self.interval)
        
        # 恢复表情（如果未被新表情更改）
        if self.current_expression_params == restore_params:
            vts_params = self.mapper.to_vts_params(self.current_expression_params)
            self.vts.set_parameters(vts_params)
        # 否则不恢复，因为表情已经被外部更改
        
        print(f"✅ 动作 {action_name} 播放结束")
    
    def _interpolate(self, keyframes: list, current_time: float) -> Dict[str, float]:
        """
        线性插值计算当前时间的参数值。
        keyframes: 每个元素为 {"time": t, "param": value, ...}
        """
        result = {}
        # 找到当前时间所在的两个关键帧
        i = 0
        while i < len(keyframes) - 1 and keyframes[i+1]["time"] < current_time:
            i += 1
        if i >= len(keyframes) - 1:
            # 超过最后一个关键帧，直接取最后一个
            kf = keyframes[-1]
            for k, v in kf.items():
                if k != "time":
                    result[k] = v
            return result
        
        t0 = keyframes[i]["time"]
        t1 = keyframes[i+1]["time"]
        if t1 - t0 == 0:
            ratio = 0.0
        else:
            ratio = (current_time - t0) / (t1 - t0)
        
        # 对每个参数进行插值
        keys = set(keyframes[i].keys()) | set(keyframes[i+1].keys())
        keys.discard("time")
        for k in keys:
            v0 = keyframes[i].get(k, 0.0)
            v1 = keyframes[i+1].get(k, 0.0)
            result[k] = v0 + (v1 - v0) * ratio
        return result
    
    async def play_action_with_priority(self, action_name: str, priority: int, scheduler) -> None:
        """包装方法，供调度器调用"""
        self._stop_flag = False
        self._current_task = asyncio.create_task(self.play_action(action_name))
        try:
            await self._current_task
        except asyncio.CancelledError:
            print(f"⏹️ 动作 {action_name} 被取消")
            # 取消后立即恢复表情
            vts_params = self.mapper.to_vts_params(self.current_expression_params)
            self.vts.set_parameters(vts_params)
    
    def stop_current(self) -> None:
        """停止当前播放的动作"""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            self._stop_flag = True