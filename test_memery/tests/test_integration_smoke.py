# test_integration_smoke.py
"""
L1 冒烟测试：验证 AIBrain + Memory 的最小闭环
不依赖 VTS / TTS，只测 AI 大脑层
"""
import asyncio
import time
from ai_brain import AIBrain
from config import AI_CONFIG
from memory_manager import MemoryManager


async def test_smoke():
    print("=" * 70)
    print("🔥 L1 冒烟测试：AIBrain + Memory 最小闭环")
    print("=" * 70)

    # 1. 初始化
    brain = AIBrain(
        model_name=AI_CONFIG["model_name"],
        system_prompt=AI_CONFIG["system_prompt"],
        temperature=AI_CONFIG["temperature"],
        max_tokens=AI_CONFIG["max_tokens"]
    )
    brain.memory.clear()
    print(f"✅ AIBrain 初始化完成，记忆库: {brain.memory.collection.count()} 条")

    # 2. 一次正常对话
    print("\n[对话 1]")
    reply, emotion, action = await brain.chat("我喜欢玩王者农药，我后羿玩的贼溜")
    print(f"  回复: {reply}")
    print(f"  情绪: {emotion}, 动作: {action}")

    # 3. 等待异步记忆写入
    await asyncio.sleep(3)
    count_after = brain.memory.collection.count()
    print(f"\n  记忆库数量: {count_after}")

    assert count_after >= 1, "❌ 记忆未写入"
    assert reply and len(reply) > 0, "❌ 回复为空"
    assert emotion in brain.emotions_list, f"❌ 情绪非法: {emotion}"
    assert action in brain.actions_list, f"❌ 动作非法: {action}"

    # 4. 第二次对话，验证检索命中
    print("\n[对话 2：验证检索]")
    reply2, _, _ = await brain.chat("我原神也玩，钟离虐哭你")
    print(f"  回复: {reply2}")

    # 3. 等待异步记忆写入
    await asyncio.sleep(3)
    count_after = brain.memory.collection.count()
    print(f"\n  记忆库数量: {count_after}")

    assert count_after >= 2, "❌ 记忆未写入"
    assert reply and len(reply) > 0, "❌ 回复为空"

    print("\n✅ L1 冒烟测试通过")


if __name__ == "__main__":
    asyncio.run(test_smoke())