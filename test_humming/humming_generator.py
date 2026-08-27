import asyncio
import edge_tts
import numpy as np
from pydub import AudioSegment
from pydub.generators import Sine
import random
import os
import tempfile
from tts_engine import TTSEngine
from scipy.io import wavfile

class HummingGenerator:
    """哼歌/轻音乐生成器"""
    
    def __init__(self, voice: str = "zh-CN-XiaoyiNeural"):
        self.voice = voice
        
        # 可以哼的歌曲/旋律片段
        self.humming_templates = [
            "啦啦啦～啦啦啦～啦啦啦啦啦～",
            "嗯嗯嗯～哼哼哼～嗯嗯嗯嗯～",
            "嘟嘟嘟～嘟嘟嘟～嘟嘟嘟嘟～",
            "滴滴答～滴滴答～滴滴答答～",
            "呜呜呜～呜呜呜～呜呜呜呜～",
            "嘿嘿嘿～嘿嘿嘿～嘿嘿嘿嘿～",
            "咪咪咪～嘛嘛嘛～咪咪嘛嘛～",
        ]
        
        # 旋律音符（确保在人耳可听范围 200-1000Hz）
        self.melody_notes = {
            "C4": 261.63,   # Do
            "D4": 293.66,   # Re
            "E4": 329.63,   # Mi
            "F4": 349.23,   # Fa
            "G4": 392.00,   # Sol
            "A4": 440.00,   # La
            "B4": 493.88,   # Si
            "C5": 523.25,   # Do(高八度)
            "D5": 587.33,   # Re(高八度)
            "E5": 659.25,   # Mi(高八度)
        }
        
        # 常用旋律
        self.melody_patterns = [
            ["C4", "D4", "E4", "C4"],           # 简单上行
            ["E4", "F4", "G4", "G4"],           # 经典开头
            ["C4", "E4", "G4", "C5"],           # 琶音
            ["A4", "G4", "E4", "C4"],           # 下行
            ["C4", "C4", "G4", "G4", "A4", "A4", "G4"],  # 小星星开头
            ["E4", "E4", "F4", "G4", "G4", "F4", "E4", "D4", "C4"],  # 音阶练习
        ]
        
    async def generate_humming(self, duration: float = 3.0) -> str:
        """生成哼唱音频（使用 edge-tts）"""
        try:
            # 随机选择哼唱内容
            template = random.choice(self.humming_templates)
            
            # 生成临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_path = tmp_file.name
            
            # 使用 edge-tts 生成哼唱
            communicate = edge_tts.Communicate(
                template, 
                self.voice,
                rate="-20%"  # 放慢速度
            )
            
            # 异步保存
            await asyncio.to_thread(self._save_sync, communicate, tmp_path)
            
            # 检查生成的音频
            audio = AudioSegment.from_mp3(tmp_path)
            if len(audio) < duration * 1000:
                times = int(duration * 1000 / len(audio)) + 1
                audio = audio * times
                audio = audio[:int(duration * 1000)]
            
            # 保存
            audio.export(tmp_path, format="mp3")
            
            return tmp_path
            
        except Exception as e:
            print(f"❌ 生成哼唱失败: {e}")
            return None
    
    async def generate_melody(self, duration: float = 3.0) -> str:
        """生成旋律（确保可听）"""
        try:
            sample_rate = 44100
            
            # 随机选择旋律模式
            melody_pattern = random.choice(self.melody_patterns)
            
            # 生成音频数据
            all_samples = []
            note_duration = 0.4  # 每个音符 0.4 秒
            
            for note_name in melody_pattern:
                freq = self.melody_notes[note_name]
                n_samples = int(sample_rate * note_duration)
                
                # 生成正弦波
                t = np.linspace(0, note_duration, n_samples, endpoint=False)
                # 振幅 0.8，确保可听
                tone = np.sin(2 * np.pi * freq * t) * 0.8
                
                # 添加淡入淡出
                fade_samples = int(sample_rate * 0.02)
                tone[:fade_samples] *= np.linspace(0, 1, fade_samples)
                tone[-fade_samples:] *= np.linspace(1, 0, fade_samples)
                
                all_samples.extend(tone)
            
            # 添加泛音（让声音更丰富）
            for i in range(len(all_samples)):
                # 添加二次谐波
                t_i = i / sample_rate
                all_samples[i] += np.sin(2 * np.pi * freq * 2 * t_i) * 0.2
                # 添加三次谐波
                all_samples[i] += np.sin(2 * np.pi * freq * 3 * t_i) * 0.1
            
            # 转换为 numpy 数组
            samples = np.array(all_samples)
            
            # 整体限制范围
            samples = np.clip(samples, -1.0, 1.0)
            
            # 整体淡入淡出
            total_fade = int(sample_rate * 0.1)
            samples[:total_fade] *= np.linspace(0, 1, total_fade)
            samples[-total_fade:] *= np.linspace(1, 0, total_fade)
            
            # 截断到指定时长
            target_samples = int(sample_rate * duration)
            if len(samples) > target_samples:
                samples = samples[:target_samples]
            
            # 生成临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_path = tmp_file.name
            
            # 正确的数据转换（关键！）
            samples_clipped = np.clip(samples, -1.0, 1.0)
            samples_16bit = (samples_clipped * 32767).astype(np.int16)
            
            # 保存 WAV
            wavfile.write(tmp_path, sample_rate, samples_16bit)
            
            # 验证音频是否可播放
            audio = AudioSegment.from_file(tmp_path, format="wav")
            print(f"✅ 旋律生成成功，时长: {len(audio)/1000:.2f} 秒")
            print(f"   采样率: {audio.frame_rate} Hz")
            print(f"   声道: {audio.channels}")
            print(f"   最大振幅: {np.max(np.abs(samples)):.2f}")
            
            return tmp_path
            
        except Exception as e:
            print(f"❌ 生成旋律失败: {e}")
            return None
    
    async def generate_variation_melody(self, duration: float = 3.0) -> str:
        """生成变化旋律（添加随机性）"""
        try:
            sample_rate = 44100
            
            # 随机生成旋律（确保频率在可听范围）
            all_notes = list(self.melody_notes.values())
            melody_sequence = []
            
            # 生成随机旋律
            for _ in range(random.randint(6, 12)):
                freq = random.choice(all_notes)
                duration_note = random.choice([0.3, 0.4, 0.5])
                melody_sequence.append((freq, duration_note))
            
            # 生成音频数据
            all_samples = []
            for freq, note_duration in melody_sequence:
                n_samples = int(sample_rate * note_duration)
                
                # 生成正弦波
                t = np.linspace(0, note_duration, n_samples, endpoint=False)
                tone = np.sin(2 * np.pi * freq * t) * 0.8  # 振幅 0.8
                
                # 添加淡入淡出
                fade_samples = int(sample_rate * 0.02)
                tone[:fade_samples] *= np.linspace(0, 1, fade_samples)
                tone[-fade_samples:] *= np.linspace(1, 0, fade_samples)
                
                all_samples.extend(tone)
            
            # 转换为 numpy 数组
            samples = np.array(all_samples)
            samples = np.clip(samples, -1.0, 1.0)
            
            # 整体淡入淡出
            total_fade = int(sample_rate * 0.1)
            samples[:total_fade] *= np.linspace(0, 1, total_fade)
            samples[-total_fade:] *= np.linspace(1, 0, total_fade)
            
            # 截断
            target_samples = int(sample_rate * duration)
            if len(samples) > target_samples:
                samples = samples[:target_samples]
            
            # 保存
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_path = tmp_file.name
            
            samples_16bit = (samples * 32767).astype(np.int16)
            wavfile.write(tmp_path, sample_rate, samples_16bit)
            
            return tmp_path
            
        except Exception as e:
            print(f"❌ 生成变化旋律失败: {e}")
            return None
    
    def _save_sync(self, communicate, tmp_path: str):
        """同步保存音频"""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(communicate.save(tmp_path))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

async def main():
    """测试哼歌生成和播放"""
    tts = TTSEngine(voice="zh-CN-XiaoxiaoNeural", rate="-20%")
    humming = HummingGenerator()
    
    print("🎵 测试1: 生成哼唱音频...")
    humming_path = await humming.generate_humming(3.0)
    if humming_path:
        print(f"✅ 哼唱音频生成成功")
        # 验证音频
        audio = AudioSegment.from_mp3(humming_path)
        print(f"   时长: {len(audio)/1000:.2f} 秒")
        print(f"   采样率: {audio.frame_rate} Hz")
        await tts.play_music(humming_path)
        os.unlink(humming_path)
    
    print("\n🎵 测试2: 生成旋律音频...")
    melody_path = await humming.generate_melody(3.0)
    if melody_path:
        print(f"✅ 旋律音频生成成功")
        await tts.play_music(melody_path)
        os.unlink(melody_path)
    
    print("\n🎵 测试3: 生成变化旋律...")
    variation_path = await humming.generate_variation_melody(3.0)
    if variation_path:
        print(f"✅ 变化旋律生成成功")
        await tts.play_music(variation_path)
        os.unlink(variation_path)

if __name__ == "__main__":
    asyncio.run(main())