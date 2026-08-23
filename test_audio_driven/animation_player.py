import asyncio
import time
from typing import Dict, Any, Optional, Callable
from parameter_mapper import ParameterMapper
from param_controller import ParamController
from vts_controller import VTSController
from tts_engine import TTSEngine


class AnimationPlayer:
    """
    动画播放器：统一更新动画参数
    """
    
    def __init__(self, mapper: ParameterMapper, vts_controller: VTSController, param_controller: ParamController):
        """
        :param mapper: ParameterMapper 实例
        :param vts_controller: VTSController 实例（需有 set_parameters 方法）
        """
        self.mapper = mapper
        self.vts = vts_controller
        self.param_controller = param_controller
        
        # 当前基础表情（持续状态）
        self.current_expression_name = "neutral"
        self.current_expression_params = mapper.get_expression_params("neutral")

        self.bio_params = {}
        self.tts_params = {}
        self.last_sent_params = {}

    async def bio_loop(self):
        """高频生物更新循环（10ms/次）"""
        # 眼睛和身体更新频率5:1
        round = 0
        last_time = time.time()
        while True:
            try:
                # 更新所有生物参数（包括眼球和眨眼）
                round += 1
                current_time = time.time()
                delta = current_time - last_time
                last_time = current_time

                bio_params = {}
                eye_params = {}
                body_params = {}
                eye_params.update(self.param_controller.update_eyes(delta))
                eye_params.update(self.param_controller.update_blink(current_time))
                bio_params=eye_params.copy()
                # if round % 5 == 0:
                #      body_params.update(self.bio.update_breath(current_time))
                #      body_params.update(self.bio.update_micro_movement(current_time))
                #      bio_params.update(body_params)
                # 合并到生物参数
                self.bio_params = bio_params.copy()
                # 与其他参数合并发送
                self._send_merged_params()
    
                await asyncio.sleep(0.02)  # 50fps 更新频率
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ 生物循环异常: {e}")
        
    def active_expression_by_file(self, expression_name: str):
        """激活新表情"""
        self.vts.activate_expression(expression_name, fade_time=0.5, active=True)
        self.current_expression_name = expression_name

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

    async def audio_driven_loop(self, tts_engine: TTSEngine, rms_array: list):
        """根据音频驱动微动作"""
        tts = tts_engine
        chunk_ms = tts.chunk_ms
        chunk_index = 0
        start_ms = time.time()
        rms_array = rms_array.copy()
        duration = tts.audio_duration
        try:
            while time.time() - start_ms < duration+1:   # 加一秒缓冲
           
                # 时间索引获取rms值
                elapsed_ms = (time.time() - start_ms) * 1000
                chunk_index = int(elapsed_ms / chunk_ms)
                if chunk_index >= len(rms_array):
                    break
                rms = rms_array[chunk_index]
                # 更新TTS参数(由param_controller处理)
                self.tts_params = self.param_controller.update_audio_driven_movement(rms, elapsed_ms)
                self._send_merged_params()
                #控制更新频率
                await asyncio.sleep(chunk_ms / 1000)
        except asyncio.CancelledError:
            print("音频驱动循环被取消")
        except Exception as e:
            print(f"⚠️ 音频驱动参数更新异常: {e}")
        finally:
            # 音频播放结束后，清理 TTS 参数
            self.tts_params = {}
            self._send_merged_params()


    def _send_merged_params(self):
        """合并所有参数并发送给 VTS"""
        # 1. 从基础表情复制
        merged = self.current_expression_params.copy()
        
        # 2. 叠加生物参数（不覆盖表情参数）
        for param, value in self.bio_params.items():
            if param not in merged:  # 如果表情里没有这个参数，才添加
                merged[param] = value
            # 如果表情里有，不覆盖（保持表情优先）
        
        # 3. 叠加 TTS 动作参数（覆盖表情和生物）
        for param, value in self.tts_params.items():
            merged[param] = value  # TTS 动作优先级最高
        
        # 4. 发送到 VTS
        if merged != self.last_sent_params:
            vts_params = self.mapper.to_vts_params(merged)
            self.vts.set_parameters(vts_params)
            self.last_sent_params = merged.copy()