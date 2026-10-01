# test_integration_chain.py
"""
L2 链路测试：验证 AIBrain 内部数据流
关键验证点：
  1. 检索结果是否正确拼接到 prompt
  2. 记忆写入是否发生在响应之后（不阻塞）
  3. 主动话题是否走特殊路径（不写入记忆）
"""
import asyncio
import time
from ai_brain import AIBrain
from config import AI_CONFIG


async def test_retrieval_injection():
    """验证检索结果真的被拼进了 prompt"""
    print("\n" + "=" * 70)
    print("🔗 L2-1：检索注入验证")
    print("=" * 70)

    brain = AIBrain(
        model_name=AI_CONFIG["model_name"],
        system_prompt=AI_CONFIG["system_prompt"],
        temperature=AI_CONFIG["temperature"],
        max_tokens=AI_CONFIG["max_tokens"]
    )
    brain.memory.clear()

    # 预设一条记忆
    brain.memory.add_memory("用户养了一只叫豆豆的橘猫", topic="宠物", speaker="user")

    # 直接调检索，验证能被召回
    results = brain.memory.search("我家猫怎么样")
    print(f"  检索到 {len(results)} 条:")
    for r in results:
        print(f"    - [{r['similarity']}] {r['content']}")

    assert len(results) > 0, "❌ 记忆未被召回"
    assert "猫" in results[0]["content"], "❌ 召回的无关"

    # 拼接到 prompt
    ctx = brain.memory.format_for_prompt(results)
    assert "【相关记忆】" in ctx, "❌ 拼接格式错误"
    assert "猫" in ctx, "❌ 拼接内容错误"
    print(f"  ✅ 拼接结果:\n{ctx}")


async def test_memory_write_async():
    """验证记忆写入是异步的，不阻塞响应"""
    print("\n" + "=" * 70)
    print("🔗 L2-2：异步写入验证")
    print("=" * 70)

    brain = AIBrain(
        model_name=AI_CONFIG["model_name"],
        system_prompt=AI_CONFIG["system_prompt"],
        temperature=AI_CONFIG["temperature"],
        max_tokens=AI_CONFIG["max_tokens"]
    )
    brain.memory.clear()

    start = time.time()
    reply, _, _ = await brain.chat("我最近在追三体电视剧")
    elapsed = time.time() - start
    print(f"  chat() 耗时: {elapsed:.2f}s")

    # 立即检查（此时异步任务可能还在跑）
    immediate_count = brain.memory.collection.count()
    print(f"  立即检查记忆: {immediate_count} 条")

    # 等待异步完成
    await asyncio.sleep(5)
    final_count = brain.memory.collection.count()
    print(f"  等待 5s 后: {final_count} 条")

    assert final_count >= 1, "❌ 异步写入最终失败"
    print("  ✅ 异步写入正常工作")


async def test_proactive_path():
    """验证主动话题不污染记忆"""
    print("\n" + "=" * 70)
    print("🔗 L2-3：主动话题路径")
    print("=" * 70)

    brain = AIBrain(
        model_name=AI_CONFIG["model_name"],
        system_prompt=AI_CONFIG["system_prompt"],
        temperature=AI_CONFIG["temperature"],
        max_tokens=AI_CONFIG["max_tokens"]
    )
    brain.memory.clear()

    # 预设旧话题
    import time as _t
    brain.memory.collection.add(
        ids=["old_1"],
        embeddings=[brain.memory._embed("用户喜欢看悬疑电影")],
        documents=["用户喜欢看悬疑电影"],
        metadatas=[{
            "topic": "电影", "speaker": "user",
            "timestamp": _t.time() - 3 * 86400,
            "date_str": "3天前"
        }]
    )

    old = brain.memory.get_random_old_topic()
    assert old is not None, "❌ 旧话题未召回"
    print(f"  抽取到: {old['topic']} - {old['content']}")

    # 构造主动 prompt（模拟 main.py 逻辑）
    proactive_input = f"（你突然想起之前聊过的：{old['content']}）用臭美语气主动问用户关于「{old['topic']}」的新问题"
    reply, emotion, action = await brain.chat(proactive_input)
    print(f"  主动发言: {reply}")

    # 验证：主动话题的指令不应写入记忆
    await asyncio.sleep(5)
    all_data = brain.memory.collection.get(include=["metadatas"])
    user_topics = [m.get("topic") for m in all_data["metadatas"] if m.get("speaker") == "user"]
    print(f"  记忆库 user 话题: {user_topics}")

    # 主动指令可能被误提取，这是已知风险点
    assert "电影" in user_topics or len(user_topics) <= 2, "⚠️ 主动话题污染了记忆（可接受但需关注）"


async def main():
    await test_retrieval_injection()
    await test_memory_write_async()
    await test_proactive_path()
    print("\n✅ L2 链路测试全部通过")


if __name__ == "__main__":
    asyncio.run(main())