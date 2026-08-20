import asyncio
import edge_tts
import pygame
import tempfile
import os
import time
import numpy as np
from pydub import AudioSegment
import math
from vts_controller import VTSController



class TTSEngine:
    """语音合成引擎"""
    
    def __init__(self, voice: str , rate: str, vts: VTSController):
        self.voice = voice
        self.rate = rate
        self.is_playing = False
        self.vts_controller = vts
        

    def set_loop(self, loop:asyncio.BaseEventLoop):
        """设置事件循环"""
        self._loop = loop
        
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

            # 2. 加载音频数据（用于计算 RMS）
            audio = AudioSegment.from_mp3(tmp_path)
            samples = np.array(audio.get_array_of_samples())
            # 如果为立体声，取平均
            if audio.channels == 2:
                samples = samples.reshape(-1, 2).mean(axis=1)
            sample_rate = audio.frame_rate
            # 将 samples 归一化到 -1~1
            samples = samples / (2 ** (audio.sample_width * 8 - 1))

            # 3. 初始化 pygame 播放器
            pygame.mixer.init()
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()

            # 5. 实时循环：每 20ms 读取 RMS 并驱动动作
            CHUNK_MS = 20  # 每 20ms 更新一次
            self.is_playing = True

            # 用于平滑的参数
            smooth_angle_y = 0.0
            smooth_angle_x = 0.0
            smooth_angle_z = 0.0
            smooth_factor = 0.15  # 平滑因子，越小越平滑
            loop_count = 0
            
            while pygame.mixer.music.get_busy():
                loop_count +=1
                if loop_count % 20 == 0:
                    print(f"当前播放位置: {pos_ms} ms")
                # 获取当前播放位置（毫秒）
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms == -1:
                    pos_ms = 0
                # 计算当前帧索引
                start_sample = int(pos_ms * sample_rate / 1000)
                end_sample = int((pos_ms + CHUNK_MS) * sample_rate / 1000)
                if start_sample >= len(samples):
                    break
                chunk = samples[start_sample:end_sample]
                if len(chunk) == 0:
                    await asyncio.sleep(CHUNK_MS / 1000)
                    continue
                # 计算 RMS（音量）
                rms = np.sqrt(np.mean(chunk ** 2))
                rms = min(rms, 0.3)
                # 将 RMS 映射到头部角度
                # 1. 头部随音量上下摆动（点头），音量越大，头越低
                target_angle_y = -rms * 200.0  # 最大 20 度
                
                # 2. 头部随音量左右微摇（摇头），音量越大，摆动幅度越大
                # 用一个缓慢的相位产生自然摆动，幅度随 RMS 变化
                phase = (pos_ms / 1000) * 3.5  # 3.5Hz 摆动频率
                target_angle_z = rms * 100.0 * math.sin(phase)
                
                # 3. 头部侧倾（歪头），音量越大，微微倾斜
                target_angle_x = rms * 100.0 * math.cos(phase * 0.7)

                # ---- 平滑滤波（关键！） ----
                smooth_angle_y += (target_angle_y - smooth_angle_y) * smooth_factor
                smooth_angle_x += (target_angle_x - smooth_angle_x) * smooth_factor
                smooth_angle_z += (target_angle_z - smooth_angle_z) * smooth_factor
                
                # 6. 合并参数：基础表情 + 头部动作
                merged_params = {}
                merged_params["ParamAngleX"] = smooth_angle_x
                merged_params["ParamAngleY"] = smooth_angle_y
                merged_params["ParamAngleZ"] = smooth_angle_z
                merged_params["ParamEyeBallX"] = -smooth_angle_x/20.0
                merged_params["ParamEyeBallY"] = -smooth_angle_y/20.0
                merged_params["ParamBodyAngleX"] = smooth_angle_x/10.0
                merged_params["ParamBodyAngleY"] = smooth_angle_y/10.0
                merged_params["ParamBodyAngleZ"] = smooth_angle_z/10.0

                # 7. 通过 VTS 发送（注意参数名映射）
                if self.vts_controller:
                    vts_params = self.vts_controller.mapper.to_vts_params(merged_params)
                    #print(f"发送参数: {vts_params}")
                    self.vts_controller.set_parameters(vts_params)

                await asyncio.sleep(CHUNK_MS / 1000)

            self.is_playing = False
            pygame.mixer.quit()
            os.unlink(tmp_path)
            
        except Exception as e:
            print(f"❌ TTS 错误: {e}")