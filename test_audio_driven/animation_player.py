import asyncio
import time
from typing import Dict, Any, Optional, Callable
from parameter_mapper import ParameterMapper
from bio_controller import BioController
from vts_controller import VTSController
class AnimationPlayer:
    """
    负责按时间线播放动作序列，支持线性插值，
    并维护当前表情状态，动作结束后恢复。
    """
    
    def __init__(self, mapper: ParameterMapper, vts_controller: VTSController, update_interval: float = 0.05):
        """
        :param mapper: ParameterMapper 实例
        :param vts_controller: VTSController 实例（需有 set_parameters 方法）
        :param update_interval: 参数更新间隔（秒），默认 20fps
        """
        self.mapper = mapper
        self.vts = vts_controller
        self.bio = BioController()
        self.interval = update_interval
        
        # 当前基础表情（持续状态）
        self.current_expression_name = "neutral"
        self.current_expression_params = mapper.get_expression_params("neutral")
        self.current_actual_params = self.current_expression_params.copy()
        self.bio_params = {}
        self.action_params = {}

        # 高频更新任务
        self._bio_update_task: Optional[asyncio.Task] = None
        # 播放状态
        self._current_task: Optional[asyncio.Task] = None
        self._stop_flag = False

    async def start_bio_loop(self):
        """启动生物控制器的独立高频更新循环"""
        self._bio_update_task = asyncio.create_task(self._bio_loop())
    
    async def _bio_loop(self):
        """高频生物更新循环（10ms/次）"""
        # 眼睛和身体更新频率5:1
        round=0
        while True:
            try:
                # 更新所有生物参数（包括眼球和眨眼）
                round+=1
                current_time = time.time()
                bio_params = {}
                eye_params = {}
                body_params = {}
                eye_params.update(self.bio.update_eyes(current_time))
                eye_params.update(self.bio.update_blink(current_time))
                bio_params=eye_params.copy()
                # 眼睛和身体更新频率5:1
                if round%5==0:
                    body_params.update(self.bio.update_breath(current_time))
                    body_params.update(self.bio.update_micro_movement(current_time))
                    bio_params.update(body_params)
                # 合并到生物参数
                self.bio_params = bio_params.copy()
                # 与其他参数合并发送
                self._send_merged_params()
                # 打印调试信息
                # print(f"👁️ 眼球: {self.bio_params.get('EyeBallX', 0):.3f}, {self.bio_params.get('EyeBallY', 0):.3f}")
                # print(f"😉 眨眼状态: {'闭眼' if self.bio_params.get('EyeLOpen', 1) < 0.5 else '睁眼'}")
                await asyncio.sleep(0.02)  # 50fps 更新频率
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ 生物循环异常: {e}")
        
    async def set_expression_smooth(self, expression_name: str, fade_time: float = 3) -> None:
        """平滑过渡到新表情"""
        target_params = self.mapper.get_expression_params(expression_name)
        if not target_params:
            print(f"⚠️ 未知表情: {expression_name}")
            return
        current_params = self.current_expression_params.copy()
        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= fade_time:
                break
            ratio = elapsed / fade_time
            #缓动：先快后慢
            eased_ratio = 1 - (1 - ratio) ** 2
            # 线性插值
            interpolated = {}
            for param, target_val in target_params.items():
                current_val = current_params.get(param, 0.0)
                interpolated[param] = current_val + (target_val - current_val) * eased_ratio
            # 每帧更新当前表情参数（如果表情提前终结导致目标参数T未达到，以实际参数A作为当前参数，避免以T作为下一个表情切换的起始状态）
            self.current_expression_params = interpolated.copy()
            # 与其他参数合并发送
            self._send_merged_params()
            # 模拟人的表情更新频率：10fps
            await asyncio.sleep(0.1)
        
        # 最终设置(如果表情播放完了未被提前终结)
        self.current_expression_name = expression_name
        self.current_expression_params = target_params.copy()

    def _send_merged_params(self):
        """合并所有参数并发送给 VTS"""
        # 1. 从基础表情复制
        merged = self.current_expression_params.copy()
        
        # 2. 叠加生物参数（不覆盖表情参数）
        for param, value in self.bio_params.items():
            if param not in merged:  # 如果表情里没有这个参数，才添加
                merged[param] = value
            # 如果表情里有，不覆盖（保持表情优先）
        
        # 3. 叠加动作参数（覆盖表情和生物）
        for param, value in self.action_params.items():
            merged[param] = value  # 动作优先级最高
        
        # 4. 发送到 VTS
        vts_params = self.mapper.to_vts_params(merged)
        self.vts.set_parameters(vts_params)