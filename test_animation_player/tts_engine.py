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
        self.vts_controller = None
        self.animation_player = None

    def set_vts(self, vts_controller, animation_player):
        """注入 VTS 控制器和动画播放器，用于获取当前表情参数"""
        self.vts_controller = vts_controller
        self.animation_player = animation_player

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

            # 4. 获取当前表情参数（作为基础）
            if self.animation_player:
                base_params = self.animation_player.current_expression_params.copy()
            else:
                base_params = {}

            # 5. 实时循环：每 50ms 读取 RMS 并驱动动作
            CHUNK_MS = 50  # 每 50ms 更新一次
            total_ms = len(audio)
            self.is_playing = True

            while pygame.mixer.music.get_busy():
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
                # 将 RMS 映射到头部角度
                # 不同动作模式有不同的映射方式
                
                # 默认：轻微随音量点头（更自然）
                head_angle_y = -rms * 5.0
                head_angle_x = -rms * 5.0
                head_angle_z = rms * 3.0 * np.sin(time.time() * 2.0)
                
                # 6. 合并参数：基础表情 + 头部动作
                merged_params = base_params.copy()
                merged_params["ParamAngleX"] = head_angle_x
                merged_params["ParamAngleY"] = head_angle_y
                merged_params["ParamAngleZ"] = head_angle_z

                # 7. 通过 VTS 发送（注意参数名映射）
                if self.vts_controller:
                    vts_params = self.vts_controller.mapper.to_vts_params(merged_params)
                    self.vts_controller.set_parameters(vts_params)

                await asyncio.sleep(CHUNK_MS / 1000)
            # 8. 播放结束，恢复表情（不再叠加头部动作）
            if self.animation_player:
                restore_params = self.animation_player.current_expression_params.copy()
                vts_params = self.vts_controller.mapper.to_vts_params(restore_params)
                self.vts_controller.set_parameters(vts_params)

            self.is_playing = False
            pygame.mixer.quit()
            os.unlink(tmp_path)
            
        except Exception as e:
            print(f"❌ TTS 错误: {e}")