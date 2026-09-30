# test_pitch_shift_humming.py
"""
验证 librosa.effects.pitch_shift 方案：
"用 TTS 生成基准'啦' → 变调到不同音高 → 拼接成旋律"

运行后会：
1. 生成 C 大调音阶（C4-D4-E4-F4-G4-A4-B4-C5）
2. 生成小星星开头
3. 生成琶音
4. 对每个结果做音高分析（验证是否真的变调成功）
5. 绘制频谱对比图
6. 播放试听
"""

import asyncio
import tempfile
import os
import numpy as np
import librosa
import librosa.display
import soundfile as sf
import edge_tts
import matplotlib.pyplot as plt
import matplotlib
import pygame

# 中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False


class HummingGenerator:
    """哼唱生成器：TTS 变调方案"""

    MELODY_NOTES = {
        "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23,
        "G4": 392.00, "A4": 440.00, "B4": 493.88,
        "C5": 523.25, "D5": 587.33, "E5": 659.25,
    }

    def __init__(self, voice: str = "zh-CN-XiaoyiNeural"):
        self.voice = voice
        self.sr = 44100

    # ---------- 基础：生成单个基准音 ----------
    async def _generate_base_note(self, text: str, duration: float) -> str:
        """用 edge-tts 生成一个基准音（如 '啦'）"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            tmp_path = f.name

        # 语速放慢一点，让每个音符更"唱"得出来
        rate = "-10%"
        communicate = edge_tts.Communicate(text, self.voice, rate=rate)

        # 用独立事件循环保存
        await asyncio.to_thread(self._save_sync, communicate, tmp_path)

        # 用 pydub 裁剪到目标时长（如果 TTS 生成太长）
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(tmp_path)
        target_ms = int(duration * 1000)
        if len(audio) > target_ms:
            audio = audio[:target_ms]
        # 保存回 mp3（保留原格式，方便 librosa 读取）
        audio.export(tmp_path, format="mp3")

        return tmp_path

    def _save_sync(self, communicate, tmp_path: str):
        """在线程中同步保存（避免和主循环冲突）"""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(communicate.save(tmp_path))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    # ---------- 核心：变调生成旋律 ----------
    async def generate_humming_with_pitch(
        self, melody: list, duration_per_note: float = 0.5
    ) -> str:
        """
        生成带旋律的哼唱（变调方案）
        :param melody: 音名列表，如 ["C4", "E4", "G4", "C5"]
        :param duration_per_note: 每个音符时长（秒）
        """
        try:
            # 1. 生成基准音（用 "啦" 作为原始音色）
            # 为了得到足够长的音频，一次生成一个"啦"，时长 = duration_per_note
            base_audio = await self._generate_base_note("啦", duration_per_note)

            # 2. 加载基准音频
            y_base, sr = librosa.load(base_audio, sr=self.sr, mono=True)
            print(f"  基准音样本数: {len(y_base)}, 采样率: {sr}")

            # 3. 计算基准音的实际基频（用 yin 算法）
            f0_array = librosa.yin(y_base, fmin=80, fmax=1000, sr=sr)
            # 只取有声段（去掉静音/尾音）
            rms = librosa.feature.rms(y=y_base)[0]
            if len(rms) > 0:
                # 生成一个布尔掩码，把 RMS 能量大于最大能量 10% 的帧标记为有声帧（voiced），其余当成静音 / 噪声帧
                voiced_mask = rms > rms.max() * 0.1
                if voiced_mask.sum() > 0 and len(f0_array) >= len(voiced_mask):
                    voiced_f0 = f0_array[:len(voiced_mask)][voiced_mask]
                    base_f0 = np.median(voiced_f0)
                else:
                    base_f0 = np.median(f0_array)
            else:
                base_f0 = np.median(f0_array)

            print(f"  基准音实际基频: {base_f0:.1f} Hz")
            if base_f0 < 50:
                print("  ⚠️ 基准音太弱或检测失败，使用默认值 200 Hz")
                base_f0 = 200.0

            # 4. 对每个音符做变调
            all_audio = []
            for note_name in melody:
                target_freq = self.MELODY_NOTES[note_name]
                # 计算半音变调量
                pitch_shift_semitones = 12 * np.log2(target_freq / base_f0)

                # librosa 变调（保持时长）
                y_shifted = librosa.effects.pitch_shift(
                    y_base, sr=sr, n_steps=pitch_shift_semitones
                )
                all_audio.append(y_shifted)

            # 5. 拼接
            final_audio = np.concatenate(all_audio)

            # 6. 整体淡入淡出
            fade_len = int(sr * 0.05)
            if len(final_audio) > 2 * fade_len:
                final_audio[:fade_len] *= np.linspace(0, 1, fade_len)
                final_audio[-fade_len:] *= np.linspace(1, 0, fade_len)

            # 7. 归一化（避免削波）
            max_amp = np.max(np.abs(final_audio))
            if max_amp > 1e-6:
                final_audio = final_audio / max_amp * 0.9

            # 8. 保存
            output_path = tempfile.mktemp(suffix=".wav")
            sf.write(output_path, final_audio, sr)

            # 清理临时基准音文件
            if os.path.exists(base_audio):
                os.unlink(base_audio)

            # 保存验证数据
            self._last_data = {
                "y_base": y_base,
                "final_audio": final_audio,
                "sr": sr,
                "base_f0": base_f0,
            }

            return output_path

        except Exception as e:
            print(f"❌ 生成旋律哼唱失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ---------- 验证工具 ----------
    def analyze_pitch(self, audio_path: str, melody: list, duration_per_note: float):
        """分析每个音符段的实际基频，验证变调是否成功"""
        y, sr = librosa.load(audio_path, sr=self.sr, mono=True)

        print("\n  📊 音高验证：")
        print("  " + "-" * 60)
        print(f"  {'音符':<6}{'目标频率':<12}{'实际基频':<12}{'误差':<10}{'误差%':<8}")
        print("  " + "-" * 60)

        samples_per_note = int(sr * duration_per_note)
        all_errors = []

        for i, note_name in enumerate(melody):
            target = self.MELODY_NOTES[note_name]
            start = i * samples_per_note
            end = min(start + samples_per_note, len(y))
            if start >= len(y):
                break

            segment = y[start:end]
            # 提取这一段的基频
            f0 = librosa.yin(segment, fmin=80, fmax=1200, sr=sr)

            # 只取有声段（去头去尾）
            rms = librosa.feature.rms(y=segment)[0]
            if len(rms) > 0:
                mask = rms > rms.max() * 0.2
                if mask.sum() > 0 and len(f0) >= len(mask):
                    voiced_f0 = f0[:len(mask)][mask]
                    actual = np.median(voiced_f0)
                else:
                    actual = np.median(f0)
            else:
                actual = np.median(f0)

            error = actual - target
            error_pct = abs(error) / target * 100
            all_errors.append(error_pct)

            print(f"  {note_name:<6}{target:<12.1f}{actual:<12.1f}{error:<+10.1f}{error_pct:<8.1f}")

        print("  " + "-" * 60)
        if all_errors:
            avg_err = np.mean(all_errors)
            print(f"  平均误差: {avg_err:.2f}%")
            if avg_err < 5:
                print("  ✅ 变调准确（误差 < 5%）")
            elif avg_err < 10:
                print("  ⚠️ 变调有偏差（5% < 误差 < 10%）")
            else:
                print("  ❌ 变调误差较大（> 10%），检查基准音提取")

    def plot_comparison(self, save_path: str = "pitch_shift_verify.png"):
        """绘制基准音 vs 最终旋律的频谱对比"""
        if not hasattr(self, "_last_data"):
            print("❌ 请先调用 generate_humming_with_pitch()")
            return

        d = self._last_data
        y_base = d["y_base"]
        final = d["final_audio"]
        sr = d["sr"]
        base_f0 = d["base_f0"]

        fig, axes = plt.subplots(3, 1, figsize=(14, 10))

        # 子图1：基准音波形
        t_base = np.arange(len(y_base)) / sr
        axes[0].plot(t_base, y_base, color="steelblue", linewidth=0.6)
        axes[0].set_title(f"① 基准音波形（'啦'，实际基频 ≈ {base_f0:.1f} Hz）", fontsize=12)
        axes[0].set_ylabel("振幅")
        axes[0].grid(alpha=0.3)

        # 子图2：最终旋律波形
        t_final = np.arange(len(final)) / sr
        axes[1].plot(t_final, final, color="darkorange", linewidth=0.6)
        axes[1].set_title("② 变调后的旋律波形（多音符拼接）", fontsize=12)
        axes[1].set_ylabel("振幅")
        axes[1].grid(alpha=0.3)

        # 子图3：频谱对比
        n_fft = 4096
        spec_base = np.abs(librosa.stft(y_base, n_fft=n_fft)).mean(axis=1)
        spec_final = np.abs(librosa.stft(final, n_fft=n_fft)).mean(axis=1)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        # 只显示 0-1000Hz
        mask = freqs < 1000
        axes[2].plot(freqs[mask], spec_base[mask], label="基准音频谱", alpha=0.7, color="steelblue")
        axes[2].plot(freqs[mask], spec_final[mask], label="最终旋律频谱", alpha=0.7, color="darkorange")
        axes[2].set_title("③ 频谱对比（0-1000 Hz）", fontsize=12)
        axes[2].set_xlabel("频率 (Hz)")
        axes[2].set_ylabel("幅度")
        axes[2].legend()
        axes[2].grid(alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=120)
        print(f"\n  📊 验证图已保存: {save_path}")
        plt.show()


# ==================== 测试 ====================

async def play_audio(path: str):
    """播放音频"""
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        print("  🔊 播放中...")
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        print("  ✅ 播放完成")
    except Exception as e:
        print(f"  ⚠️ 播放失败（可能无音频设备）: {e}")


async def main():
    print("=" * 70)
    print("🎵 验证：librosa 变调方案（TTS基准音 → 变调 → 旋律）")
    print("=" * 70)

    hum = HummingGenerator(voice="zh-CN-XiaoyiNeural")

    # ============ 测试 1：C 大调音阶 ============
    print("\n【测试1】C 大调音阶（上行）")
    melody1 = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
    print(f"  旋律: {melody1}")
    path1 = await hum.generate_humming_with_pitch(melody1, duration_per_note=0.5)
    if path1:
        print(f"  ✅ 生成成功: {path1}")
        hum.analyze_pitch(path1, melody1, 0.5)
        hum.plot_comparison("verify_scale.png")
        await play_audio(path1)
        os.unlink(path1)
    else:
        print("  ❌ 生成失败")

    # ============ 测试 2：小星星开头 ============
    print("\n【测试2】小星星开头")
    melody2 = ["C4", "C4", "G4", "G4", "A4", "A4", "G4"]
    print(f"  旋律: {melody2}")
    path2 = await hum.generate_humming_with_pitch(melody2, duration_per_note=0.5)
    if path2:
        print(f"  ✅ 生成成功: {path2}")
        hum.analyze_pitch(path2, melody2, 0.5)
        hum.plot_comparison("verify_star.png")
        await play_audio(path2)
        os.unlink(path2)
    else:
        print("  ❌ 生成失败")

    # ============ 测试 3：琶音 ============
    print("\n【测试3】C 大调琶音（上行+下行）")
    melody3 = ["C4", "E4", "G4", "C5", "G4", "E4", "C4"]
    print(f"  旋律: {melody3}")
    path3 = await hum.generate_humming_with_pitch(melody3, duration_per_note=0.45)
    if path3:
        print(f"  ✅ 生成成功: {path3}")
        hum.analyze_pitch(path3, melody3, 0.45)
        hum.plot_comparison("verify_arpeggio.png")
        await play_audio(path3)
        os.unlink(path3)
    else:
        print("  ❌ 生成失败")

    print("\n" + "=" * 70)
    print("✅ 所有测试完成！请查看 verify_*.png 验证图")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())