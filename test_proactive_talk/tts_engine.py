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
        self.audio_duration = 0.0 # 音频时长（秒）
        self.chunk_ms = 20  # 每 20ms 一个帧
        self.tmp_path = None # 临时音频文件路径
        self.rms_array = None # 音频 RMS 数组
        self._loop = None # 事件循环
        self.is_pygame_inited = False # pygame 是否初始化
        


    def set_loop(self, loop:asyncio.BaseEventLoop):
        """设置事件循环"""
        self._loop = loop

    def get_audio_duration(self, text: str) -> float:
        """获取语音合成时间（秒）"""
        return self.audio_duration

    async def synthesize(self, text: str) -> str:
        """异步合成，返回临时音频文件路径"""
        tmp_path = await asyncio.to_thread(self._synthesize_sync, text)
        self.tmp_path = tmp_path
        return tmp_path

    def _synthesize_sync(self, text: str) -> str:
        """同步合成，返回临时音频文件路径"""
        try:
            # 生成临时音频文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_path = tmp_file.name
            # 创建新的事件循环执行保存文件
            loop=asyncio.new_event_loop()
            start_time = time.time()
            try:
                communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
                loop.run_until_complete(communicate.save(tmp_path)) # 保存文件
            finally:
                loop.close()
                asyncio.set_event_loop(None) #清理

            self.tmp_path = tmp_path
            print(f"语音合成完毕，耗时: {time.time() - start_time:.2f} 秒")

            return self.tmp_path
        except Exception as e:
            print(f"❌ TTS 合成失败: {e}")
            return None

    async def compute_rms(self, tmp_path:str) -> tuple:
        """异步计算音频的 RMS 数组"""
        rms_array, duration = await asyncio.to_thread(self._compute_rms_sync, tmp_path)
        self.rms_array = rms_array
        self.audio_duration = duration
        return rms_array, duration

    def _compute_rms_sync(self, tmp_path:str) -> tuple:
        """
        计算音频的 RMS 数组
        """
        try:
            audio = AudioSegment.from_mp3(tmp_path)
            samples = np.array(audio.get_array_of_samples())
            # 如果为立体声，取平均
            if audio.channels == 2:
                samples = samples.reshape(-1, 2).mean(axis=1)
            sample_rate = audio.frame_rate
            # 将 samples 归一化到 -1~1
            samples = samples / (2 ** (audio.sample_width * 8 - 1))
            # 计算音频时长（用于表情同步时长）
            self.audio_duration = len(samples) / sample_rate
            print(f"音频时长: {self.audio_duration:.2f} 秒")

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
            return self.rms_array, self.audio_duration
        except Exception as e:
            print(f"❌ 计算 RMS 失败: {e}")
            return None, None

   
    async def play_music(self, tmp_path:str):
        """只播放，不做其他"""
        try:
            if not self.is_pygame_inited:
                pygame.mixer.init()
                self.is_pygame_inited = True
            pygame.mixer.music.load(tmp_path)
            self.is_playing = True
            pygame.mixer.music.play()
            start_time = time.time()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.02)
            print(f"音频播放耗时: {time.time() - start_time:.2f} 秒")
        except Exception as e:
            print(f"❌ 播放音频失败: {e}")
        finally:
            if self.is_pygame_inited:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                pygame.mixer.quit()
                self.is_playing = False
                self.is_pygame_inited = False
            