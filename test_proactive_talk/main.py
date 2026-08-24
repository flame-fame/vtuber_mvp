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
import os
import random

class AIVTuber:
    def __init__(self):
        print("🚀 正在初始化 AI 主播核心...")
        # 主动发言配置
        self.proactive_mode = False  # 是否启用主动发言
        self.proactive_interval = 15.0  # 主动发言间隔（秒）
        self.last_proactive_time = time.time()
        self.active_topic_cooldown = {}  # 话题冷却
        self.max_consecutive_proactive = 10  # 连续主动发言最大次数
        self.current_consecutive_proactive = 0
        # 初始化AI组件
        self.brain = AIBrain(
            model_name=AI_CONFIG["model_name"],
            system_prompt=AI_CONFIG["system_prompt"],
            temperature=AI_CONFIG["temperature"],
            max_tokens=AI_CONFIG["max_tokens"]
        )
        # 初始化其他组件
        self.vts = VTSController()
        self.mapper = ParameterMapper("live2d_param_mapping.json", "face_param_mapping.json")
        self.tts = TTSEngine(voice=TTS_CONFIG["voice"], rate=TTS_CONFIG["rate"])
        self.param_controller = ParamController()
        self.player = AnimationPlayer(self.mapper, self.vts, self.param_controller)
        self.danmaku_reader = DanmakuReader("danmaku_live.txt")
        # 连接 VTS
        if not self.vts.connect():
            print("❌ 无法连接到 VTube Studio，请检查是否开启并配置了API。")
            exit(1)
        # 等待认证完成
        print("⏳ 等待 VTS 认证...")
        time.sleep(3)
        print("✅ AI 主播初始化完成！准备就绪。")

    async def process_tts(self, reply_text, emotion):
        """处理任务"""
         #  1. 合成音频
        tmp_path = await self.tts.synthesize(reply_text)
        rms_array, duration = await self.tts.compute_rms(tmp_path)
        # 2. 激活表情
        if emotion != "neutral":
            expression_task = asyncio.create_task(self.player.toggle_expression(emotion, fade_time=0.5, duration=duration))
        else:
            expression_task = asyncio.create_task(self.player.set_expression_smooth("neutral", fade_time=0.5))
        
        # 4. 播放语音（异步等待完成）
        play_task = asyncio.create_task(self.tts.play_music(tmp_path))
        animation_task = asyncio.create_task(self.player.audio_driven_loop(self.tts, rms_array))

        # 5. 等待三个任务完成
        try:
            await asyncio.wait_for(
                asyncio.gather(expression_task, play_task, animation_task, return_exceptions=True),
                timeout=30.0 # 30秒超时
            )
        except asyncio.TimeoutError:
            print("⚠️ 任务播放超时")
            expression_task.cancel()
            play_task.cancel()
            animation_task.cancel()
        except Exception as e:
            print(f"⚠️ 等待任务完成时出错: {e}")
        # 6. 删除临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    async def process_ai(self, user_input) -> tuple[str, str, str]:
        # 1. AI 思考（同步操作）
        start_time = time.time()
        # 调用 AI 思考
        try:
            reply_text, emotion, action = await self.brain.chat(user_input)
        except Exception as e:
            print(f"⚠️ 思考时出错: {e}")
            return "", "neutral", "think"
        elapsed_time = time.time() - start_time
        print(f"思考耗时: {elapsed_time:.4f} 秒")
        return reply_text, emotion, action

    async def process_danmaku(self, danmaku) -> tuple[str, str]:
        """异步处理单条弹幕"""
        # 生成系统回复消息（不调用AI）
        user_input = ""
        sys_reply_text = ""
        if danmaku.dtype == DmType.SYSTEM:
            return user_input, sys_reply_text
        elif danmaku.dtype == DmType.ENTER:
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
        # 显示系统弹幕
        print(f"\n📺 弹幕 [{danmaku.offset:.1f}s]: {user_input}")
        
        return user_input, sys_reply_text
    
    def _should_proactive(self) -> bool:
        """判断是否应该主动发言"""
        current_time = time.time()
        
        # 检查是否达到间隔时间
        if current_time - self.last_proactive_time < self.proactive_interval:
            return False
        
        # 检查是否超过连续主动发言限制
        if self.current_consecutive_proactive >= self.max_consecutive_proactive:
            return False
        
        # 如果最近有弹幕交互，重置间隔
        if current_time - self.brain.last_interaction_time < 5.0:
            self.last_proactive_time = current_time
            return False
        
        return True
    
    async def _do_proactive_message(self) -> tuple[str, str, str]:
        """执行主动发言"""
        try:
            print("\n💭 主动发言中...")
            user_input = random.choice(TOPIC_POOL)
            # 生成主动消息
            reply_text, emotion, action = await self.brain.chat(user_input)
        except Exception as e:
            print(f"⚠️ 主动发言时出错: {e}")
            return "", "neutral", "think"
            
        print(f"🤖 AI主动说: {reply_text}")
        print(f"🎭 表情: {emotion}, 动作: {action}")
        
        # 更新最后主动发言时间
        self.last_proactive_time = time.time()
        self.current_consecutive_proactive += 1

        return reply_text, emotion, action

    async def run_async(self):
        """异步主循环"""
        print("\n--- 🎬 开始模拟直播弹幕 ---")
        print("输入 'quit' 退出, 'history' 查看历史, 'clear' 清空记忆\n")
        
        # 启动生物参数更新循环
        asyncio.create_task(self.player.bio_loop())
        
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
                if danmaku.dtype == DmType.SYSTEM:
                    continue
                self.proactive_mode = self.danmaku_reader.is_long_wait
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
                try:
                    sys_reply_text = ""
                    user_input = ""
                    # 检查是否需要主动发言
                    if not self.proactive_mode:
                        user_input, sys_reply_text = await self.process_danmaku(danmaku)
                    else:
                        user_input = random.choice(TOPIC_POOL)
                        
                    # 系统生成欢迎和感谢回复    
                    if sys_reply_text:
                        reply_text = sys_reply_text
                        emotion = "neutral"
                        action = "think"
                        sys_reply_text = ""
                    else:
                        # 普通弹幕，调用 AI 思考
                        print("💬 思考中...")
                        reply_text, emotion, action = await self.process_ai(user_input)

                    print(f"🎭 表情: {emotion}")
                    # 处理 TTS 任务和表情动画   
                    await self.process_tts(reply_text, emotion)
                except Exception as e:
                    print(f"⚠️ 处理弹幕时出错: {e}")
                    # 继续处理下一个弹幕
                    continue
                
        except KeyboardInterrupt:
            print("\n👋 程序被用户中断")
            self.brain.close()
        except Exception as e:
            print(f"❌ 运行出错: {e}")
            self.brain.close()

if __name__ == "__main__":
    app = AIVTuber()
    asyncio.run(app.run_async())
