import asyncio
import time
import sys
from config import *
from ai_brain import AIBrain
from tts import TTSEngine
from action_scheduler import ActionScheduler, Motion


class AIVTuber:
    def __init__(self):
        self.action_scheduler = ActionScheduler()
        self.action_scheduler.on_action_start = self._on_action_start
        self.action_scheduler.on_action_end = self._on_action_end
        self.brain = AIBrain(AI_CONFIG["model_name"], AI_CONFIG["system_prompt"], AI_CONFIG["temperature"], AI_CONFIG["max_tokens"])
        self.tts = TTSEngine(TTS_CONFIG["voice"], TTS_CONFIG["rate"])
        self.running = True

    async def start(self):
        print("="*60)
        print("🤖 AI 主播 v2.0 (集成VTS)")
        print("="*60)

        if not self.action_scheduler:
            print("❌ 调度器初始化失败")
            return

        scheduler_task = asyncio.create_task(self.action_scheduler.start())

        print("\n💡 输入 'quit' 退出，输入 'clear' 清空记忆")
        print("💡 输入 'reset' 重置VTS模型")
        print("-"*60)

        while self.running:
            try:
                user_input = await asyncio.to_thread(input, "\n👤 观众说: ")
                user_input = user_input.strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', '退出']:
                    self.running = False
                    break
                elif user_input.lower() == 'clear':
                    self.brain.clear_history()
                    print("🧹 对话历史已清空")
                    continue
                elif user_input.lower() == 'reset':
                    self._reset_model()
                    continue

                print("💬 AI 思考中...", end="", flush=True)
                start_time = time.time()

                ai_text, emotion, intensity = await asyncio.to_thread(self.brain.chat, user_input)

                elapsed = time.time() - start_time
                print(f" (耗时 {elapsed:.2f}秒)")
                print(f"🤖 AI主播: {ai_text}")
                print(f"😊 情绪: {emotion}，强度：{intensity}")

                self._drive_model(emotion, intensity)

                if ai_text:
                    await asyncio.to_thread(self.tts.speak, ai_text)

            except KeyboardInterrupt:
                self.running = False
                print("\n👋 再见！")
                break
            except Exception as e:
                print(f"⚠️ 发生错误: {e}")

        self._cleanup()
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

    def _reset_model(self):
        self.action_scheduler.add_emotion_action("Peaceful", intensity=1.0, priority=ActionPriority.IDLE)
        print("✅ VTS模型已重置为 'Peaceful'")

    def _drive_model(self, emotion: str, intensity: float = 1.0):
        self.action_scheduler.add_emotion_action(emotion, intensity)
        print(f"✅ VTS模型已驱动为 {emotion}，强度 {intensity}")

    def _cleanup(self):
        self.action_scheduler.stop()
        print("👋 程序已退出")

    def _on_action_start(self, motion: Motion):
        print(f"🎯 皮套动作开始: {motion.name}")

    def _on_action_end(self, motion: Motion):
        print(f"🎯 皮套动作结束: {motion.name}")


if __name__ == "__main__":
    app = AIVTuber()
    asyncio.run(app.start())
