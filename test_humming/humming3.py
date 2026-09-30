# test_humming_improved.py
"""
验证：变调哼唱 + 裁静音 + 交叉淡化拼接
对比：直接拼接 vs 裁静音+交叉淡化

运行后会：
1. 生成同一段旋律（小星星）
2. 用"直接拼接"生成一个版本
3. 用"裁静音+交叉淡化"生成另一个版本
4. 音高验证 + 波形对比图
5. 依次播放两个版本，方便对比
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
    """哼唱生成器：TTS 变调方案 + 裁静音 + 交叉淡化"""

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

        rate = "-10%"
        communicate = edge_tts.Communicate(text, self.voice, rate=rate)
        await asyncio.to_thread(self._save_sync, communicate, tmp_path)

        # 裁剪到目标时长
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(tmp_path)
        target_ms = int(duration * 1000)
        if len(audio) > target_ms:
            audio = audio[:target_ms]
        audio.export(tmp_path, format="mp3")

        return tmp_path

    def _save_sync(self, communicate, tmp_path: str):
        """在线程中同步保存"""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(communicate.save(tmp_path))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    # ---------- 新增：裁掉首尾静音 ----------
    def _trim_silence(self, y: np.ndarray, sr: int, top_db: int = 30) -> np.ndarray:
        """裁掉首尾静音"""
        intervals = librosa.effects.split(y, top_db=top_db)
        if len(intervals) == 0:
            return y
        # 取第一个到最后一个有声段
        start = intervals[0][0]
        end = intervals[-1][1]
        return y[start:end]

    # ---------- 新增：交叉淡化拼接 ----------
    def _crossfade_concat(self, segments: list, sr: int, fade_ms: int = 40) -> np.ndarray:
        """交叉淡化拼接：让相邻音符重叠，消除静音缝"""
        if not segments:
            return np.array([])

        fade_samples = int(sr * fade_ms / 1000)
        result = segments[0]

        for seg in segments[1:]:
            if len(result) < fade_samples or len(seg) < fade_samples:
                # 段太短，直接拼接
                result = np.concatenate([result, seg])
                continue

            tail = result[-fade_samples:]
            head = seg[:fade_samples]

            # 等功率交叉淡化（比线性更自然）
            fade_out = np.cos(np.linspace(0, np.pi / 2, fade_samples))
            fade_in = np.sin(np.linspace(0, np.pi / 2, fade_samples))

            mixed = tail * fade_out + head * fade_in

            # 拼接：去掉原尾部，接上混合段，再接剩余部分
            result = np.concatenate([result[:-fade_samples], mixed, seg[fade_samples:]])

        return result

    # ---------- 核心：变调生成旋律（带开关，方便对比） ----------
    async def generate_humming_with_pitch(
        self,
        melody: list,
        duration_per_note: float = 0.5,
        use_trim_and_crossfade: bool = True,
        fade_ms: int = 40,
        top_db: int = 30,
    ) -> str:
        """
        生成带旋律的哼唱
        :param melody: 音名列表，如 ["C4", "E4", "G4", "C5"]
        :param duration_per_note: 每个音符时长（秒）
        :param use_trim_and_crossfade: 是否使用裁静音+交叉淡化
        :param fade_ms: 交叉淡化时长（毫秒）
        :param top_db: 静音检测阈值（dB）
        """
        try:
            # 1. 生成基准音（用 "啦"）
            base_audio = await self._generate_base_note("啦", duration_per_note)

            # 2. 加载
            y_base, sr = librosa.load(base_audio, sr=self.sr, mono=True)
            print(f"  基准音样本数: {len(y_base)}, 采样率: {sr}")

            # 3. 计算基准音实际基频
            f0_array = librosa.yin(y_base, fmin=80, fmax=1000, sr=sr)
            rms = librosa.feature.rms(y=y_base)[0]
            if len(rms) > 0:
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
                print("  ⚠️ 基准音太弱，使用默认值 200 Hz")
                base_f0 = 200.0

            # 4. 对每个音符变调
            all_audio = []
            for note_name in melody:
                target_freq = self.MELODY_NOTES[note_name]
                pitch_shift_semitones = 12 * np.log2(target_freq / base_f0)
                y_shifted = librosa.effects.pitch_shift(
                    y_base, sr=sr, n_steps=pitch_shift_semitones
                )

                if use_trim_and_crossfade:
                    # 裁掉首尾静音
                    y_shifted = self._trim_silence(y_shifted, sr, top_db=top_db)

                all_audio.append(y_shifted)

            # 5. 拼接
            if use_trim_and_crossfade:
                final_audio = self._crossfade_concat(all_audio, sr, fade_ms=fade_ms)
            else:
                final_audio = np.concatenate(all_audio)

            # 6. 整体淡入淡出
            fade_len = int(sr * 0.05)
            if len(final_audio) > 2 * fade_len:
                final_audio[:fade_len] *= np.linspace(0, 1, fade_len)
                final_audio[-fade_len:] *= np.linspace(1, 0, fade_len)

            # 7. 归一化
            max_amp = np.max(np.abs(final_audio))
            if max_amp > 1e-6:
                final_audio = final_audio / max_amp * 0.9

            # 8. 保存
            output_path = tempfile.mktemp(suffix=".wav")
            sf.write(output_path, final_audio, sr)

            # 清理临时基准音
            if os.path.exists(base_audio):
                os.unlink(base_audio)

            # 保存验证数据
            self._last_data = {
                "y_base": y_base,
                "final_audio": final_audio,
                "sr": sr,
                "base_f0": base_f0,
                "melody": melody,
                "duration_per_note": duration_per_note,
            }

            return output_path

        except Exception as e:
            print(f"❌ 生成旋律哼唱失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ---------- 验证工具 ----------
    def analyze_pitch(self, audio_path: str, melody: list, duration_per_note: float):
        """分析每个音符段的实际基频"""
        y, sr = librosa.load(audio_path, sr=self.sr, mono=True)

        print("\n  📊 音高验证：")
        print("  " + "-" * 60)
        print(f"  {'音符':<6}{'目标频率':<12}{'实际基频':<12}{'误差':<10}{'误差%':<8}")
        print("  " + "-" * 60)

        # 注意：用了 crossfade 后，每个音符实际长度会短于 duration_per_note
        # 这里按 melody 数量均分总时长来估算
        samples_per_note = len(y) // len(melody)
        all_errors = []

        for i, note_name in enumerate(melody):
            target = self.MELODY_NOTES[note_name]
            start = i * samples_per_note
            end = min(start + samples_per_note, len(y))
            if start >= len(y):
                break

            segment = y[start:end]
            f0 = librosa.yin(segment, fmin=80, fmax=1200, sr=sr)
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

    def plot_comparison(self, audio_a: np.ndarray, audio_b: np.ndarray,
                        sr: int, save_path: str = "humming_compare.png"):
        """绘制两个版本的波形对比"""
        fig, axes = plt.subplots(2, 1, figsize=(14, 7))

        t_a = np.arange(len(audio_a)) / sr
        axes[0].plot(t_a, audio_a, color="steelblue", linewidth=0.6)
        axes[0].set_title(f"① 直接拼接（总长 {len(audio_a)/sr:.2f}s）", fontsize=12)
        axes[0].set_ylabel("振幅")
        axes[0].grid(alpha=0.3)

        t_b = np.arange(len(audio_b)) / sr
        axes[1].plot(t_b, audio_b, color="darkorange", linewidth=0.6)
        axes[1].set_title(f"② 裁静音+交叉淡化（总长 {len(audio_b)/sr:.2f}s）", fontsize=12)
        axes[1].set_xlabel("时间 (s)")
        axes[1].set_ylabel("振幅")
        axes[1].grid(alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=120)
        print(f"\n  📊 对比图已保存: {save_path}")
        plt.show()


# ==================== 播放工具 ====================

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
        print(f"  ⚠️ 播放失败: {e}")


# ==================== 测试 ====================

async def main():
    print("=" * 70)
    print("🎵 哼唱对比测试：直接拼接 vs 裁静音+交叉淡化")
    print("=" * 70)

    hum = HummingGenerator(voice="zh-CN-XiaoyiNeural")

    # 使用"小星星"旋律，最容易听出断续问题
    melody = ["C4", "C4", "G4", "G4", "A4", "A4", "G4"]
    duration_per_note = 0.5

    print(f"\n旋律: {melody}")
    print(f"每音符时长: {duration_per_note}s\n")

    # ============ 版本 A：直接拼接（原始方案）============
    print("【版本 A】直接拼接（np.concatenate）")
    path_a = await hum.generate_humming_with_pitch(
        melody,
        duration_per_note=duration_per_note,
        use_trim_and_crossfade=False,
    )
    if path_a:
        print(f"  ✅ 生成成功: {path_a}")
        hum.analyze_pitch(path_a, melody, duration_per_note)
        # 读取波形用于对比
        y_a, sr = librosa.load(path_a, sr=hum.sr, mono=True)

    # ============ 版本 B：裁静音+交叉淡化 ============
    print("\n【版本 B】裁静音 + 交叉淡化（fade_ms=50, top_db=30）")
    path_b = await hum.generate_humming_with_pitch(
        melody,
        duration_per_note=duration_per_note,
        use_trim_and_crossfade=True,
        fade_ms=50,
        top_db=30,
    )
    if path_b:
        print(f"  ✅ 生成成功: {path_b}")
        hum.analyze_pitch(path_b, melody, duration_per_note)
        y_b, sr = librosa.load(path_b, sr=hum.sr, mono=True)

    # ============ 波形对比图 ============
    if path_a and path_b:
        hum.plot_comparison(y_a, y_b, sr, save_path="humming_compare.png")

    # ============ 播放对比 ============
    if path_a:
        print("\n🎧 播放【版本 A】直接拼接...")
        await play_audio(path_a)
        os.unlink(path_a)

    if path_b:
        print("\n🎧 播放【版本 B】裁静音+交叉淡化...")
        await play_audio(path_b)
        os.unlink(path_b)

    # ============ 额外：试试不同 fade_ms ============
    print("\n" + "=" * 70)
    print("🎵 额外测试：不同交叉淡化时长")
    print("=" * 70)

    for fade_ms in [20, 50, 80, 120]:
        print(f"\n【fade_ms = {fade_ms}ms】")
        path = await hum.generate_humming_with_pitch(
            melody,
            duration_per_note=duration_per_note,
            use_trim_and_crossfade=True,
            fade_ms=fade_ms,
            top_db=30,
        )
        if path:
            y, sr = librosa.load(path, sr=hum.sr, mono=True)
            print(f"  总时长: {len(y)/sr:.2f}s")
            await play_audio(path)
            os.unlink(path)

    print("\n" + "=" * 70)
    print("✅ 测试完成！请听哪个 fade_ms 效果最自然")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())