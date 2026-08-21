# bio_controller.py - 新建文件
import math
import random
import time
from typing import Dict

class BioController:
    """
    生物节律控制器：独立控制眼球、眨眼、呼吸等生理运动
    更新频率远高于表情更新
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
        
    def update_eyes(self,  dt: float) -> Dict[str, float]:
        """
        更新眼球运动（高频）
        返回：眼球位置参数（EyeBallX, EyeBallY）
        """
        current_time = dt
        params = {}
        
        # 1. 眼球微跳：每 0.2~0.5 秒改变目标位置
        if current_time - self.eye_target_time > self.eye_move_duration:
            # 生成新的随机目标（范围 ±0.3）
            self.eye_target_x = self.rng.uniform(-0.8, 0.8)
            self.eye_target_y = self.rng.uniform(-0.8, 0.8)
            self.eye_target_time = current_time
            
        # 2. 平滑追踪目标（阻尼滤波）
        smooth_factor = 0.15  # 越大跟随越快
        self.eye_current_x += (self.eye_target_x - self.eye_current_x) * smooth_factor
        self.eye_current_y += (self.eye_target_y - self.eye_current_y) * smooth_factor
        
        params["ParamEyeBallX"] = self.eye_current_x
        params["ParamEyeBallY"] = self.eye_current_y
        
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
                self.next_blink_time = current_time + self.rng.uniform(2.0, 5.0)
        else:
            # 眨眼进行中
            elapsed = current_time - self.blink_start_time
            if elapsed < self.blink_duration:
                # 眨眼曲线：快速闭眼，慢速睁开
                progress = elapsed / self.blink_duration
                if progress < 0.3:
                    # 闭眼阶段
                    openness = 1.0 - (progress / 0.3)
                else:
                    # 睁眼阶段（缓动）
                    open_progress = (progress - 0.3) / 0.7
                    openness = 0.0 + open_progress ** 1.5
                params["ParamEyeLOpen"] = min(openness, 1.0)
                params["ParamEyeROpen"] = min(openness, 1.0)
            else:
                self.is_blinking = False
                params["ParamEyeLOpen"] = 1.0
                params["ParamEyeROpen"] = 1.0
        
        return params
    
    def update_breath(self, dt: float) -> Dict[str, float]:
        """
        更新呼吸微动（低频）
        返回：身体和头部微动参数
        """
        self.breath_phase += dt * self.breath_speed
        breath_val = math.sin(self.breath_phase)
        
        params = {
            "ParamBodyAngleY": breath_val * 0.8,      # 身体微前倾
            "ParamFacePositionY": breath_val * 0.2,   # 头部微上下
            "ParamAngleY": breath_val * 0.3,     # 头部微微点头
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
