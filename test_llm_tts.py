import asyncio
import ollama
import edge_tts
import pygame
import tempfile
import os
import time

# ================== 配置区 ==================
SYSTEM_PROMPT = """
你是一个傲娇的AI主播，性格毒舌但内心关心观众。
要求：
1. 回答必须简短，不超过30个汉字
2. 语气要带点嘲讽，但偶尔流露出温柔
3. 适当使用颜文字或emoji（如 (╯°□°)╯、❤️）
"""

MODEL_NAME = "qwen2.5:7b"  # 如果显存低于4GB，改成 "qwen2.5:3b"
VOICE_NAME = "zh-CN-XiaoxiaoNeural"  # 微软中文女声，可换成 "zh-CN-YunxiNeural"（男声）
# ============================================

def get_ai_response(user_input):
    """调用本地大模型生成回复"""
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            options={
                "temperature": 0.85,  # 越高越随机（毒舌程度）
                "top_p": 0.9,
                "num_predict": 100,   # 限制最大生成长度
            }
        )
        return response['message']['content'].strip()
    except Exception as e:
        print(f"❌ AI 接口报错: {e}")
        return "哼，本小姐现在不想说话！"

async def text_to_speech(text):
    """将文本转为语音并播放（使用 Edge TTS）"""
    try:
        # 生成临时音频文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_path = tmp_file.name
        
        # 调用 Edge TTS 合成语音
        communicate = edge_tts.Communicate(text, VOICE_NAME, rate="+5%")
        await communicate.save(tmp_path)
        
        # 使用 pygame 播放音频
        pygame.mixer.init()
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        
        # 等待播放结束
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        
        # 清理临时文件
        pygame.mixer.quit()
        os.unlink(tmp_path)
        
    except Exception as e:
        print(f"❌ TTS 报错: {e}")

async def main():
    """主循环：键盘输入 -> AI回复 -> 语音播放"""
    print("=" * 50)
    print("🤖 Neuro-lite AI 主播已启动（MVP版）")
    print("输入 'quit' 或 'exit' 退出程序")
    print("=" * 50)
    
    while True:
        # 1. 获取用户输入
        user_input = input("\n👤 观众说: ").strip()
        
        if user_input.lower() in ['quit', 'exit', '退出']:
            print("👋 拜拜！")
            break
        
        if not user_input:
            continue
        
        # 2. 获取 AI 回复
        print("💬 AI 思考中...", end="", flush=True)
        start_time = time.time()
        ai_text = get_ai_response(user_input)
        elapsed = time.time() - start_time
        print(f" (耗时 {elapsed:.2f}秒)")
        print(f"🤖 Neuro: {ai_text}")
        
        # 3. 语音播报
        await text_to_speech(ai_text)

if __name__ == "__main__":
    asyncio.run(main())