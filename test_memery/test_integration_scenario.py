# test_integration_scenario.py
"""
L3 场景测试：模拟真实直播弹幕流
验证：多用户场景、话题延续、长对话记忆衰减
"""
import asyncio
import time
from ai_brain import AIBrain
from danmaku_reader import DanmakuReader, DmType
from config import AI_CONFIG


# 构造模拟弹幕文件
SCENARIO = """
# 场景：多用户直播，话题跳跃
0.0 | 小明 | normal | 主播今天好漂亮
3.0 | 小红 | normal | 我也玩原神，你抽到胡桃了吗
6.0 | 小明 | normal | 我家的猫也叫胡桃
9.0 | 阿强 | enter | 
10.0 | 小红 | normal | 深圳今天下雨了
13.0 | 阿强 | normal | 主播打游戏吗
16.0 | 小明 | normal | 我最近在追三体
19.0 | 小红 | normal | 我觉得叶文洁有点可怜
"""


async def test_scenario():
    print("=" * 70)
    print("🎬 L3 场景测试：模拟直播弹幕流")
    print("=" * 70)

    # 写临时弹幕文件
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                      delete=False, encoding="utf-8") as f:
        f.write(SCENARIO)
        path = f.name

    brain = AIBrain(
        model_name=AI_CONFIG["model_name"],
        system_prompt=AI_CONFIG["system_prompt"],
        temperature=AI_CONFIG["temperature"],
        max_tokens=AI_CONFIG["max_tokens"]
    )
    brain.memory.clear()

    reader = DanmakuReader(path, speed=10.0)  # 加速 10 倍

    print("\n--- 开始处理弹幕流 ---")
    async for dm in reader.stream():
        if dm.dtype == DmType.SYSTEM:
            continue

        if dm.dtype == DmType.ENTER:
            print(f"\n📺 [{dm.offset:.1f}s] {dm.username} 进入")
            continue

        user_input = f"{dm.username}：{dm.content}"
        print(f"\n📺 [{dm.offset:.1f}s] {user_input}")

        reply, emotion, action = await brain.chat(user_input)
        print(f"🤖 {reply} [{emotion}:{action}]")

        # 每轮之间等 1 秒，让异步写入完成
        await asyncio.sleep(1)

    # 等待所有异步写入完成
    print("\n⏳ 等待异步记忆写入...")
    await asyncio.sleep(8)

    # 验证记忆累积
    count = brain.memory.collection.count()
    print(f"\n📊 最终记忆数: {count}")
    assert count >= 3, f"❌ 记忆数过少: {count}"

    # 验证关键记忆
    all_data = brain.memory.collection.get(include=["documents", "metadatas"])
    print("\n📋 记忆库内容:")
    for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
        print(f"  [{meta.get('topic')}] {doc}")

    # 验证：应该能召回原神、猫、三体等
    keywords_to_find = ["原神", "猫", "三体"]
    found = []
    for kw in keywords_to_find:
        results = brain.memory.search(kw)
        if any(kw in r["content"] for r in results):
            found.append(kw)
    print(f"\n🔍 关键词召回验证: {found}/{keywords_to_find}")
    assert len(found) >= 2, f"❌ 召回率过低: {found}"

    os.unlink(path)
    print("\n✅ L3 场景测试通过")


if __name__ == "__main__":
    asyncio.run(test_scenario())