# bio_controller.py - 新建文件
import math
import random
import time
from typing import Dict
import numpy as np

class ParamController:
    """
    参数控制器：
    1.独立控制眼球、眨眼、呼吸、微动作等生理运动
    2.音频驱动参数
    """
    
    def __init__(self, random_seed: int = None):
        self.rng = random.Random(random_seed if random_seed else int(time.time()))
        
        # 眼球状态
        self.eye_target_x = 0.0
        self.eye_target_y = 0.0
        self.eye_current_x = 0.0
        self.eye_current_y = 0.0
        self.eye_target_time = time.time()
        self.eye_move_duration = 0.2  # 每次微动持续200ms
        # 眼球扫视状态
        self._saccade_timer = 0
        self._saccade_target_x = 0
        self._saccade_target_y = 0
        self._saccade_phase = 0  # 0=漂移, 1=扫视中
        # 眨眼状态
        self.next_blink_time = self.rng.uniform(2.0, 5.0)
        self.blink_start_time = 0.0
        self.blink_duration = 0.15  # 眨眼持续时间 150ms
        self.is_blinking = False
        
        # 呼吸状态
        self.breath_phase = 0.0
        self.breath_speed = 0.6  # 呼吸频率 0.6Hz
        
        # 头部微动（极微小）
        self.micro_angle_phase = 0.0
        self.micro_angle_amplitude = 0.5  # 微动幅度（度）
        
    def update_eyes(self, dt: float) -> Dict[str, float]:
        current_time = time.time()
        params = {}
        
        # 1. 慢速漂移（默认状态）：始终有一个微小的速度
        # 使用 Perlin 噪声近似（多频率正弦叠加），产生连续、缓慢变化
        drift_speed_x = math.sin(current_time * 0.3) * 0.02 + math.sin(current_time * 0.7) * 0.01
        drift_speed_y = math.cos(current_time * 0.4) * 0.02 + math.cos(current_time * 0.9) * 0.01
        
        # 2. 累加漂移（限制范围）
        self.eye_current_x += drift_speed_x * dt * 2.0
        self.eye_current_y += drift_speed_y * dt * 2.0
        self.eye_current_x = max(-0.6, min(0.6, self.eye_current_x))
        self.eye_current_y = max(-0.6, min(0.6, self.eye_current_y))
        
        # 3. 偶尔的扫视
        self._saccade_timer += dt
        # 触发扫视（随机间隔 2~5 秒）
        if self._saccade_phase == 0 and self._saccade_timer > self.rng.uniform(2.0, 5.0):
            self._saccade_phase = 1
            self._saccade_target_x = self.rng.uniform(-0.9, 0.9)
            self._saccade_target_y = self.rng.uniform(-0.9, 0.9)
            self._saccade_start_time = current_time
            self._saccade_duration = 0.15  # 扫视持续 150ms（非常快）
        
        # 执行扫视（快速移动）
        if self._saccade_phase == 1:
            # 联动眨眼
            self.trigger_blink()
            elapsed = current_time - self._saccade_start_time
            if elapsed < self._saccade_duration:
                # 快速跳向目标（缓动，先快后慢）
                progress = elapsed / self._saccade_duration
                eased = 1 - (1 - progress) ** 3  # 三次缓出
                self.eye_current_x += (self._saccade_target_x - self.eye_current_x) * eased * 0.8
                self.eye_current_y += (self._saccade_target_y - self.eye_current_y) * eased * 0.8
            else:
                # 扫视结束，回到漂移模式
                self._saccade_phase = 0
                self._saccade_timer = 0
        
        # 4. 添加微小震颤（人眼永不静止）
        tremor_x = self.rng.gauss(0, 0.005)  # 振幅更小
        tremor_y = self.rng.gauss(0, 0.005)
        
        params["ParamEyeBallX"] = self.eye_current_x + tremor_x
        params["ParamEyeBallY"] = self.eye_current_y + tremor_y
    
        return params
    
    def update_blink(self, dt: float) -> Dict[str, float]:
        """
        更新眨眼（独立频率）
        返回：眼睛开闭参数（EyeLOpen, EyeROpen）
        """
        current_time = dt
        params = {}
        
        if not self.is_blinking:
            # 检查是否该眨眼了
            if current_time >= self.next_blink_time:
                self.is_blinking = True
                self.blink_start_time = current_time
                self.next_blink_time = current_time + self.rng.uniform(2.5, 6.0)
        else:
            # 眨眼进行中
            elapsed = current_time - self.blink_start_time
            if elapsed < self.blink_duration:
                # 眨眼曲线：快速闭眼，慢速睁开
                progress = elapsed / self.blink_duration
                if progress < 0.25:
                    # 闭眼阶段
                    openness = 1.0 - (progress / 0.25)
                else:
                    # 睁眼阶段（缓动）
                    open_progress = (progress - 0.25) / 0.75
                    openness = 0.0 + open_progress ** 1.5
                params["ParamEyeLOpen"] = min(max(openness, 0.0), 1.0)
                params["ParamEyeROpen"] = min(max(openness, 0.0), 1.0)       
            else:
                self.is_blinking = False
                params["ParamEyeLOpen"] = 1.0
                params["ParamEyeROpen"] = 1.0
        
        return params

    def trigger_blink(self):
        """强制触发一次眨眼（用于眼动联动）"""
        self.is_blinking = True
        self.blink_start_time = time.time()
        self.next_blink_time = self.blink_start_time + self.rng.uniform(2.5, 6.0)

    def update_breath(self, dt: float) -> Dict[str, float]:
        """
        更新呼吸微动（低频）
        返回：身体和头部微动参数
        """
        self.breath_phase += dt * self.breath_speed
        breath_val = math.sin(self.breath_phase)
        
        params = {
            "ParamBodyAngleY": breath_val * 0.1,      # 身体微前倾
            "ParamFacePositionY": breath_val * 0.1,   # 头部微上下
            "ParamAngleY": breath_val * 0.1,     # 头部微微点头
        }
        return params
    
    def update_micro_movement(self, dt: float) -> Dict[str, float]:
        """
        更新头部极细微颤动（模拟真实人体微颤）
        """
        self.micro_angle_phase += dt * 2.0
        # 使用 Perlin 噪声近似（多频率正弦叠加）
        noise_x = math.sin(self.micro_angle_phase * 1.3) * 0.3
        noise_y = math.sin(self.micro_angle_phase * 1.7) * 0.2
        noise_z = math.cos(self.micro_angle_phase * 0.9) * 0.4
        
        return {
            "ParamAngleX": noise_x,
            "ParamAngleY": noise_y,
            "ParamAngleZ": noise_z,
        }

    def update_audio_driven_movement(self, rms_array: np.ndarray, chunk_ms: float = 20.0) -> Dict[str, float]:
        """根据音频驱动参数"""
        rms_array = rms_array
        chunk_ms = chunk_ms
        # 用于平滑的参数
        smooth_angle_y = 0.0
        smooth_angle_x = 0.0
        smooth_angle_z = 0.0
        smooth_factor = 0.1  # 平滑因子，越小越平滑

        chunk_index = 0
        start_ms = time.time()

        
        # 时间索引获取rms值
        elapsed_ms = (time.time() - start_ms) * 1000
        chunk_index = int(elapsed_ms / chunk_ms)
        rms = rms_array[chunk_index]
        # 将 RMS 映射到头部角度
        # 1. 头部随音量上下摆动（点头），音量越大，头越低
        phase = (elapsed_ms / 1000) * 5  # 5Hz 摆动频率
        target_angle_y = min(rms * 200.0 * math.sin(phase * 2), 10.0)  # 最大 10 度
        
        # 2. 头部随音量左右微摇（摇头），音量越大，摆动幅度越大
        # 用一个缓慢的相位产生自然摆动，幅度随 RMS 变化
        
        target_angle_x = rms * 100.0 * math.sin(phase)
        
        # 3. 头部侧倾（歪头），音量越大，微微倾斜
        target_angle_z = rms * 100.0 * math.cos(phase * 0.2)

        # ---- 平滑滤波（关键！） ----
        smooth_angle_y += (target_angle_y - smooth_angle_y) * smooth_factor
        smooth_angle_x += (target_angle_x - smooth_angle_x) * smooth_factor
        smooth_angle_z += (target_angle_z - smooth_angle_z) * smooth_factor
        
        # 6. 合并参数
        merged_params = {}
        merged_params["ParamAngleX"] = smooth_angle_x
        merged_params["ParamAngleY"] = smooth_angle_y
        merged_params["ParamAngleZ"] = smooth_angle_z
        
        merged_params["ParamBodyAngleX"] = smooth_angle_x/5.0
        merged_params["ParamBodyAngleY"] = smooth_angle_y/5.0
        merged_params["ParamBodyAngleZ"] = smooth_angle_z/5.0

        merged_params["ParamArmLA"] = smooth_angle_x * 10
        merged_params["ParamArmRA"] = smooth_angle_x * 10

        return merged_params