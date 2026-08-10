# main.py
import threading
import time
import asyncio
import sys
from config import *
from ai_brain import AIBrain
from tts_engine import TTSEngine
from vts_controller import VTSController
from behavior_system import BehaviorSystem, ActionLibrary, IntentState

def map_emotion_to_intent(emotion: str) -> IntentState:
    """将 AI 表情标签映射为 VAD 意图（简化映射）"""
    # 根据 emotion 标签设定粗略的 VAD
    mapping = {
        "Happy": IntentState(0.8, 0.6, 0.6),
        "Blush": IntentState(0.7, 0.5, 0.3),
        "Smile": IntentState(0.6, 0.4, 0.5),
        "Stunned": IntentState(0.0, 0.8, 0.3),
        "BadSmile": IntentState(0.2, 0.7, 0.8),
        "Woosh": IntentState(-0.1, 0.6, 0.4),
        "Dislike": IntentState(-0.5, 0.5, 0.6),
        "Sad": IntentState(-0.7, 0.2, 0.2),
        "Normal": IntentState(0.0, 0.5, 0.5),
        "UnHappy": IntentState(-0.6, 0.6, 0.4),
    }
    return mapping.get(emotion, IntentState(0.0, 0.5, 0.5))

def main():
    # 1. 初始化 VTS
    vts = VTSController()
    if not vts.connect():
        print("❌ 无法连接 VTube Studio，程序退出")
        return

    # 2. 初始化 AI
    ai = AIBrain(
        model_name=AI_CONFIG["model_name"],
        system_prompt=AI_CONFIG["system_prompt"],
        temperature=AI_CONFIG["temperature"],
        max_tokens=AI_CONFIG["max_tokens"]
    )

    # 3. 初始化 TTS
    tts = TTSEngine(voice=TTS_CONFIG["voice"], rate=TTS_CONFIG["rate"])

    # 4. 初始化行为系统
    lib = ActionLibrary("live2d_param_mapping.json")
    behavior = BehaviorSystem(lib)

    # 5. 主循环
    print("🎤 数字人已启动！输入 'quit' 退出")
    try:
        while True:
            user_input = input("\n👤 你说: ")
            if user_input.lower() in ('quit', 'exit', 'q'):
                break

            # 5.1 AI 回复
            ai_response, emotion, action = asyncio.run(ai.chat(user_input))
            print(f"🤖 AI: {ai_response}")
            print(f"💬 表情: {emotion}, 动作: {action}")

            # 5.2 构建 markup（标记层输入）
            markup = {
                "emotion": emotion,   # 直接使用 emotion 标签（MarkupDrivenLayer 中已映射）
                "action": action,     # 动作名称，需确保在 live2d_param_mapping 中存在
                "intensity": 0.7
            }

            # 5.3 构建意图（IntentDrivenLayer）
            intent = map_emotion_to_intent(emotion)

            # 5.4 更新行为系统的标记/意图
            behavior.set_markup_and_intent(markup, intent)

            # 5.5 异步播放 TTS（在子线程中执行，避免阻塞主循环）
            tts_thread = threading.Thread(target=tts.speak, args=(ai_response,))
            tts_thread.start()

            # 5.6 持续更新行为参数并发送到 VTS，直到 TTS 播放结束
            # 每秒约 30 帧更新（可根据需要调整）
            frame_interval = 1.0 / 30.0
            last_update = time.time()

            while tts_thread.is_alive() or behavior.active_actions:
                now = time.time()
                if now - last_update >= frame_interval:
                    # 模拟音频 RMS（若正在播放则设为一个固定值，否则 0）
                    audio_rms = 0.3 if tts.is_playing else 0.0
                    # 音高暂用固定值
                    audio_pitch = 180.0
                    # 节拍强度，暂未使用
                    beat = 0.0

                    # 更新行为系统
                    params = behavior.update(
                        audio_rms=audio_rms,
                        audio_pitch=audio_pitch,
                        current_text=ai_response,    # 用于关键词驱动
                        llm_markup=markup,
                        llm_intent=intent,
                        beat_strength=beat
                    )

                    # 转换为参数字典并发送到 VTS
                    param_dict = {
                        "ParamFacePositionX": params.ParamFacePositionX,
                        "ParamFacePositionY": params.ParamFacePositionY,
                        # ... 将所有 Param 字段列入（可用反射或手动列全）
                        "ParamAngleX": params.ParamAngleX,
                        "ParamAngleY": params.ParamAngleY,
                        "ParamAngleZ": params.ParamAngleZ,
                        "ParamCheek": params.ParamCheek,
                        "ParamMouthForm": params.ParamMouthForm,
                        "ParamMouthOpenY": params.ParamMouthOpenY,
                        "ParamEyeLOpen": params.ParamEyeLOpen,
                        "ParamEyeROpen": params.ParamEyeROpen,
                        "ParamEyeLSmile": params.ParamEyeLSmile,
                        "ParamEyeRSmile": params.ParamEyeRSmile,
                        "ParamEyeBallX": params.ParamEyeBallX,
                        "ParamEyeBallY": params.ParamEyeBallY,
                        "ParamBrowLForm": params.ParamBrowLForm,
                        "ParamBrowRForm": params.ParamBrowRForm,
                        "ParamBodyAngleX": params.ParamBodyAngleX,
                        "ParamBodyAngleY": params.ParamBodyAngleY,
                        "ParamBodyAngleZ": params.ParamBodyAngleZ,
                        "ParamArmLA": params.ParamArmLA,
                        "ParamArmRA": params.ParamArmRA,
                    }
                    vts.set_parameters(param_dict)

                    last_update = now

                # 短暂休眠，避免 CPU 占用过高
                time.sleep(0.01)

            # 5.7 等待 TTS 线程结束（此时行为更新循环已退出，但 TTS 可能还在播放）
            tts_thread.join()

    except KeyboardInterrupt:
        print("\n👋 程序终止")
    finally:
        ai.close()
        vts.close()
        print("✅ 已清理资源")

if __name__ == "__main__":
    main()