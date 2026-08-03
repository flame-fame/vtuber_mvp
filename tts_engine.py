import asyncio
import edge_tts
import pygame
import tempfile
import os
import time

class TTSEngine:
    """语音合成引擎"""
    
    def __init__(self, voice: str , rate: str):
        self.voice = voice
        self.rate = rate
        self.is_playing = False
        self._loop = None

    def set_loop(self, loop:asyncio.BaseEventLoop):
        """设置事件循环"""
        self._loop = loop
        
    def speak(self, text: str):
        """播放语音（同步）"""
        if not text:
            return
            
        try:
            if self._loop:
                # 使用已有的循环
                self._loop.run_until_complete(self._speak_async(text))
            else:
                # 创建新的循环（兼容旧用法）
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._speak_async(text))
                loop.close()
        except Exception as e:
            print(f"❌ TTS 播放失败: {e}")
    
    async def _speak_async(self, text: str):
        """异步执行TTS"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_path = tmp_file.name
            
            start_time = time.time()

            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
            await communicate.save(tmp_path)

            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"语音合成完毕，耗时: {elapsed_time:.2f} 秒")
            
            # 播放音频（同步操作）
            pygame.mixer.init()
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            
            self.is_playing = True
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            self.is_playing = False
            
            pygame.mixer.quit()
            os.unlink(tmp_path)
            
        except Exception as e:
            print(f"❌ TTS 错误: {e}")