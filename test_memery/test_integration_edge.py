# test_integration_edge.py
"""
L4 边界与污染测试
验证：
  1. 长时间对话记忆不爆炸
  2. 主动话题不污染记忆
  3. 记忆检索不过度干扰人格
  4. prune 淘汰机制在真实场景生效
"""
import asyncio
import time
from ai_brain import AIBrain
from config import AI_CONFIG


async def test_memory_pollution():
    """验证主动指令不污染记忆"""
    print("\n" + "=" * 70)
    print("🧪 L4-1：记忆污染检测")
    print("=" * 70)

    brain = AIBrain(
        model_name=AI_CONFIG["model_name"],
        system_prompt=AI_CONFIG["system_prompt"],
        temperature=AI_CONFIG["temperature"],
        max_tokens=AI_CONFIG["max_tokens"]
    )
    brain.memory.clear()

    # 模拟 3 次主动发言（用指令型 prompt）
    for i in range(3):
        prompt = f"（你突然想起之前聊过的话题）用臭美语气主动问用户关于「测试{i}」的问题"
        await brain.chat(prompt)
        await asyncio.sleep(0.5)

    # 等待写入
    await asyncio.sleep(8)

    all_data = brain.memory.collection.get(include=["documents"])
    docs = all_data["documents"]
    print(f"  记忆库数量: {len(docs)}")
    for d in docs:
        print(f"    - {d[:50]}")

    # 污染检测：不应出现"用臭美语气"这样的指令残留
    polluted = [d for d in docs if "臭美" in d or "主动问" in d]
    assert len(polluted) == 0, f"❌ 检测到污染: {polluted}"
    print("  ✅ 无记忆污染")


async def test_long_run():
    """模拟 30 轮对话，验证记忆增长与检索"""
    print("\n" + "=" * 70)
    print("🧪 L4-2：长对话压力测试（30 轮）")
    print("=" * 70)

    brain = AIBrain(
        model_name=AI_CONFIG["model_name"],
        system_prompt=AI_CONFIG["system_prompt"],
        temperature=AI_CONFIG["temperature"],
        max_tokens=AI_CONFIG["max_tokens"]
    )
    brain.memory.clear()

    inputs = [
        f"我想聊聊话题{i}：{['猫', '狗', '游戏', '电影', '音乐'][i % 5]}相关的事"
        for i in range(30)
    ]

    start = time.time()
    for i, inp in enumerate(inputs):
        await brain.chat(inp)
        if i % 5 == 0:
            print(f"  进度: {i+1}/30")
        await asyncio.sleep(0.1)

    total = time.time() - start
    print(f"  30 轮总耗时: {total:.1f}s，平均 {total/30:.2f}s/轮")

    # 等待记忆写入
    await asyncio.sleep(10)
    count = brain.memory.collection.count()
    print(f"  最终记忆数: {count}")

    # 验证：不应超过 30（因为每轮最多一条）
    assert count <= 30, f"❌ 记忆数异常: {count}"
    # 验证：至少一半被提取
    assert count >= 10, f"❌ 提取率过低: {count}/30"

    # 验证检索仍正常
    results = brain.memory.search("猫")
    print(f"  检索'猫'命中: {len(results)} 条")


async def test_prune_in_action():
    """验证 prune 在真实场景生效"""
    print("\n" + "=" * 70)
    print("🧪 L4-3：prune 淘汰机制")
    print("=" * 70)

    brain = AIBrain(
        model_name=AI_CONFIG["model_name"],
        system_prompt=AI_CONFIG["system_prompt"],
        temperature=AI_CONFIG["temperature"],
        max_tokens=AI_CONFIG["max_tokens"]
    )
    brain.memory.clear()

    # 手动注入 100 条
    for i in range(100):
        brain.memory.collection.add(
            ids=[f"stress_{i}"],
            embeddings=[brain.memory._embed(f"压力测试记忆{i}")],
            documents=[f"压力测试记忆{i}"],
            metadatas=[{
                "topic": f"t{i}", "speaker": "user",
                "timestamp": time.time() - (100 - i) * 3600,
                "date_str": "test"
            }]
        )

    print(f"  注入后: {brain.memory.collection.count()} 条")
    brain.memory.prune(max_count=50)
    print(f"  prune 后: {brain.memory.collection.count()} 条")
    assert brain.memory.collection.count() == 50, "❌ prune 未生效"


async def main():
    await test_memory_pollution()
    await test_long_run()
    await test_prune_in_action()
    print("\n✅ L4 边界测试全部通过")


if __name__ == "__main__":
    asyncio.run(main())
    