# 文件名：test_llm_action.py
# 功能：测试弹幕读取和作为输入
# 流程：1.先读取用户输入 2.再读取弹幕输入
import time
import threading
import asyncio
from config import *
from ai_brain import AIBrain
from tts_engine import TTSEngine
from vts_controller import VTSController
from danmaku_reader import DanmakuReader, DmType
from animation_player import AnimationPlayer
from param_controller import ParamController
from parameter_mapper import ParameterMapper

class AIVTuber:
    def __init__(self):
        print("🚀 正在初始化 AI 主播核心...")
        # 1. 初始化组件
        self.brain = AIBrain(
            model_name=AI_CONFIG["model_name"],
            system_prompt=AI_CONFIG["system_prompt"],
            temperature=AI_CONFIG["temperature"],
            max_tokens=AI_CONFIG["max_tokens"]
        )
        self.vts = VTSController()
        self.mapper = ParameterMapper("live2d_param_mapping.json", "face_param_mapping.json")
        self.tts = TTSEngine(voice=TTS_CONFIG["voice"], rate=TTS_CONFIG["rate"])
        self.bio = ParamController()
        self.player = AnimationPlayer(self.mapper, self.vts, self.bio, self.tts)
        self.danmaku_reader = DanmakuReader("danmaku_live.txt")
        self.is_speaking = False
        self._loop = None
        # 2. 连接 VTS
        if not self.vts.connect():
            print("❌ 无法连接到 VTube Studio，请检查是否开启并配置了API。")
            exit(1)
        
        # 等待认证完成
        print("⏳ 等待 VTS 认证...")
        time.sleep(3)
        
        print("✅ AI 主播初始化完成！准备就绪。")

    async def _play_audio_async(self, text):
        """异步播放语音（等待播放完成）"""
        if not text:
            return
        
        self.is_speaking = True
        try:
            # 直接调用异步方法
            await self.tts._speak_async(text)
        finally:
            self.is_speaking = False
            print("🔈 语音播放完成")

    async def _process_danmaku_async(self, danmaku):
        """异步处理单条弹幕"""
        # 跳过系统消息
        if danmaku.dtype == DmType.SYSTEM:
            return
        
        # 构建用户输入
        sys_reply_text = ""
        if danmaku.dtype == DmType.ENTER:
            user_input = f"{danmaku.username} 进入直播间"
            sys_reply_text = f"欢迎 {danmaku.username}！"
        elif danmaku.dtype == DmType.FOLLOW:
            user_input = f"{danmaku.username} 关注了主播"
            sys_reply_text = f"谢谢 {danmaku.username} 关注主播"
        elif danmaku.dtype == DmType.GIFT:
            user_input = f"{danmaku.username} 送了 {danmaku.content}"
            sys_reply_text = f"谢谢 {danmaku.username}宝宝的礼物，主播爱你哦！"
        elif danmaku.dtype == DmType.SC:
            user_input = f"{danmaku.username} 发送SC：{danmaku.content}"
        else:
            user_input = f"{danmaku.username}：{danmaku.content}"

        # 显示弹幕
        print(f"\n📺 弹幕 [{danmaku.offset:.1f}s]: {user_input}")

        # 1. AI 思考（同步操作）
        print("💬 思考中...")
        start_time = time.time()
        # 系统生成欢迎和感谢回复
        if sys_reply_text:
            reply_text = sys_reply_text
            emotion = "neutral"
            action = "think"
            sys_reply_text = ""
        else:
            # 普通弹幕，调用 AI 思考
            reply_text, emotion, action = await self.brain.chat(user_input)
        
        elapsed_time = time.time() - start_time
        print(f"思考耗时: {elapsed_time:.4f} 秒")
        #print(f"🤖 AI: {reply_text}")
        print(f"🎭 表情: {emotion}")
        print(f"🎬 动作: {action}")

        # 2. 激活表情
        if emotion != "neutral":
            asyncio.create_task(self.player.set_expression_smooth(emotion, 1.0))
        else:
            await self.player.set_expression_smooth("neutral", 1.0)

        # 4. 播放语音（异步等待完成）
        print("🔈 语音合成中...")
        await self._play_audio_async(reply_text)

    async def run_async(self):
        """异步主循环"""
        print("\n--- 🎬 开始模拟直播弹幕 ---")
        print("输入 'quit' 退出, 'history' 查看历史, 'clear' 清空记忆\n")
        
        # 启动生物参数更新循环
        await self.player.start_bio_loop()
        # 确保 TTS 引擎使用当前事件循环
        self.tts.set_loop(asyncio.get_running_loop())
        
        # 创建用户输入监听任务
        input_queue = asyncio.Queue()
        
        def input_listener():
            while True:
                try:
                    cmd = input().strip().lower()
                    input_queue.put_nowait(cmd)
                except:
                    break
        
        input_thread = threading.Thread(target=input_listener, daemon=True)
        input_thread.start()
        
        # 获取弹幕流迭代器
        danmaku_iter = self.danmaku_reader.stream()
        
        try:
            async for danmaku in danmaku_iter:
                # 检查用户输入
                while not input_queue.empty():
                    cmd = await input_queue.get()
                    if cmd == 'quit':
                        self.brain.close()
                        print("👋 再见！")
                        return
                    elif cmd == 'history':
                        for item in self.brain.conversation_history:
                            print(item)
                    elif cmd == 'clear':
                        self.brain.clear_history()
                        print("🧠 记忆已清空。")
                
                # 处理弹幕（异步等待语音完成）
                await self._process_danmaku_async(danmaku)
                
        except KeyboardInterrupt:
            print("\n👋 程序被用户中断")
            self.brain.close()
        except Exception as e:
            print(f"❌ 运行出错: {e}")
            self.brain.close()

if __name__ == "__main__":
    app = AIVTuber()
    asyncio.run(app.run_async())
