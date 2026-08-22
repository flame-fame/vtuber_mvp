import asyncio
import edge_tts
import pygame
import tempfile
import os
import time
import numpy as np
from pydub import AudioSegment
import math
import random


class TTSEngine:
    """语音合成引擎"""
    
    def __init__(self, voice: str , rate: str):
        self.voice = voice
        self.rate = rate
        self.is_playing = False
        self.audio_duration = 0.0
        self.mixer = pygame.mixer.init()
        self.chunk_ms = 20  # 每 20ms 一个帧
        

    def set_loop(self, loop:asyncio.BaseEventLoop):
        """设置事件循环"""
        self._loop = loop

    def get_audio_duration(self, text: str) -> float:
        """获取语音合成时间（秒）"""
        return self.audio_duration

    async def speak(self, text: str):
        """播放语音（异步执行）"""
        if not text:
            return
        try:
            await self._speak_async(text)
        except Exception as e:
            print(f"❌ TTS 播放失败: {e}")
    
    async def _speak_async(self, text: str):
        """异步执行TTS"""
        try:
            # 1. 生成临时音频文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_path = tmp_file.name
            
            start_time = time.time()

            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)

            await communicate.save(tmp_path)

            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"语音合成完毕，耗时: {elapsed_time:.2f} 秒")

            # 2. 计算音频时长（用于表情同步时长）
            

            # 3. 加载音频数据（用于计算 RMS）
            audio = AudioSegment.from_mp3(tmp_path)
            samples = np.array(audio.get_array_of_samples())
            # 如果为立体声，取平均
            if audio.channels == 2:
                samples = samples.reshape(-1, 2).mean(axis=1)
            sample_rate = audio.frame_rate
            # 将 samples 归一化到 -1~1
            samples = samples / (2 ** (audio.sample_width * 8 - 1))
            print(samples.size)

            #  **预计算 RMS 数组**（关键优化）
            CHUNK_MS = self.chunk_ms  # 每 20ms 一个帧
            chunk_samples = int(CHUNK_MS * sample_rate / 1000)
            total_chunks = len(samples) // chunk_samples + 1
            rms_array = []
            for i in range(total_chunks):
                start = i * chunk_samples
                end = min(start + chunk_samples, len(samples))
                chunk = samples[start:end]
                if len(chunk) > 0:
                    rms = np.sqrt(np.mean(chunk ** 2))
                    rms_array.append(min(rms, 0.3))  # 限制最大幅度
                else:
                    rms_array.append(0.0)
            self.rms_array = rms_array

            # 4. 播放音频
            self.mixer.music.load(tmp_path)
            self.mixer.music.play()
            self.is_playing = True

            # # 5. 实时循环
            # # 用于平滑的参数
            # smooth_angle_y = 0.0
            # smooth_angle_x = 0.0
            # smooth_angle_z = 0.0
            # smooth_factor = 0.1  # 平滑因子，越小越平滑

            # chunk_index = 0
           
            # start_ms = time.time()

            # while self.mixer.music.get_busy() and chunk_index <= len(rms_array):
            #     # 时间索引获取rms值
            #     elapsed_ms = (time.time() - start_ms) * 1000
            #     chunk_index = int(elapsed_ms / CHUNK_MS)
            #     if chunk_index >= len(rms_array):
            #         break
            #     rms = rms_array[chunk_index]
            #     # 将 RMS 映射到头部角度
            #     # 1. 头部随音量上下摆动（点头），音量越大，头越低
            #     phase = (elapsed_ms / 1000) * 5  # 5Hz 摆动频率
            #     target_angle_y = min(rms * 200.0 * math.sin(phase * 2), 10.0)  # 最大 10 度
                
            #     # 2. 头部随音量左右微摇（摇头），音量越大，摆动幅度越大
            #     # 用一个缓慢的相位产生自然摆动，幅度随 RMS 变化
                
            #     target_angle_x = rms * 100.0 * math.sin(phase)
                
            #     # 3. 头部侧倾（歪头），音量越大，微微倾斜
            #     target_angle_z = rms * 100.0 * math.cos(phase * 0.2)

            #     # ---- 平滑滤波（关键！） ----
            #     smooth_angle_y += (target_angle_y - smooth_angle_y) * smooth_factor
            #     smooth_angle_x += (target_angle_x - smooth_angle_x) * smooth_factor
            #     smooth_angle_z += (target_angle_z - smooth_angle_z) * smooth_factor
                
            #     # 6. 合并参数：基础表情 + 头部动作
            #     merged_params = {}
            #     merged_params["ParamAngleX"] = smooth_angle_x
            #     merged_params["ParamAngleY"] = smooth_angle_y
            #     merged_params["ParamAngleZ"] = smooth_angle_z
            #     # 如果音频长度较长，模拟讲话思考时眼珠四处转动
            #     #merged_params["ParamEyeBallX"] = smooth_angle_x * 0.1 if samples.size>100000 else smooth_angle_y*0.05
            #     #erged_params["ParamEyeBallY"] = smooth_angle_y * 0.1 if samples.size>100000 else smooth_angle_x*0.05
            #     merged_params["ParamBodyAngleX"] = smooth_angle_x/5.0
            #     merged_params["ParamBodyAngleY"] = smooth_angle_y/5.0
            #     merged_params["ParamBodyAngleZ"] = smooth_angle_z/5.0
            #     merged_params["ParamArmLA"] = smooth_angle_x * 10
            #     merged_params["ParamArmRA"] = smooth_angle_x * 10

            #     # 7. 通过 VTS 发送（注意参数名映射）
            #     if self.vts_controller:
            #         vts_params = self.vts_controller.mapper.to_vts_params(merged_params)
            #         #print(f"发送参数: {vts_params}")
            #         self.vts_controller.set_parameters(vts_params)
                
            #     #控制更新频率
            #     await asyncio.sleep(CHUNK_MS / 1000)

            print(f"语音播放完成,耗时: {time.time() - start_ms:.2f} 秒")
            self.is_playing = False
            self.mixer.quit()
            os.unlink(tmp_path)
            
        except Exception as e:
            print(f"❌ TTS 错误: {e}")