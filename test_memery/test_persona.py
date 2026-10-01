# test_persona_system.py
"""
验证：人格外置 + 策略路由系统
"""
import asyncio
from persona import PersonaLoader
from ai_brain import AIBrain
from config import PERSONA_CONFIG


async def test_persona_loading():
    print("=" * 70)
    print("🧪 测试 1：人格加载")
    print("=" * 70)

    persona = PersonaLoader(PERSONA_CONFIG["path"])
    prompt = persona.build_system_prompt()
    print(f"  system_prompt 长度: {len(prompt)} 字符")
    print(f"  信念数: {len(persona.get_beliefs())}")
    print(f"  策略权重: {persona.get_strategy_weights()}")
    assert "神经喵" in prompt, "❌ system_prompt 缺少名字"
    assert "猫比狗优雅" in prompt, "❌ system_prompt 缺少信念"
    print("  ✅ 人格加载正常")


async def test_strategy_router():
    print("\n" + "=" * 70)
    print("🧪 测试 2：策略路由")
    print("=" * 70)

    brain = AIBrain()
    brain.memory.clear()
    brain._preload_beliefs()

    # 连续抽 20 次，统计分布
    from collections import Counter
    counter = Counter()
    for _ in range(20):
        s = brain.router.pick("测试输入")
        counter[s.name] += 1

    print(f"  20 次抽样分布: {dict(counter)}")
    assert len(counter) >= 3, "❌ 策略多样性不足"
    assert "probe" not in [brain.router.recent_history[i]
                            for i in range(len(brain.router.recent_history) - 1)
                            if brain.router.recent_history[i] == "probe"
                            and brain.router.recent_history[i + 1] == "probe"], \
        "❌ probe 连续触发"
    print("  ✅ 策略路由正常")


async def test_chat_flow():
    print("\n" + "=" * 70)
    print("🧪 测试 3：对话流程")
    print("=" * 70)

    brain = AIBrain()
    brain.memory.clear()
    brain._preload_beliefs()

    test_inputs = [
        "你好呀",
        "你觉得猫和狗哪个好？",
        "我数学考砸了",
        "讲个笑话吧",
    ]

    for inp in test_inputs:
        print(f"\n  👤 用户: {inp}")
        reply, emotion, action = await brain.chat(inp)
        print(f"  🤖 AI: {reply}")
        print(f"  🎭 情绪: {emotion}, 动作: {action}")
        assert reply, "❌ 回复为空"
        assert emotion in brain.emotions_list, f"❌ 情绪非法: {emotion}"
        assert action in brain.actions_list, f"❌ 动作非法: {action}"

    print("\n  ✅ 对话流程正常")


async def test_belief_consistency():
    print("\n" + "=" * 70)
    print("🧪 测试 4：信念一致性")
    print("=" * 70)

    brain = AIBrain()
    brain.memory.clear()
    brain._preload_beliefs()

    # 强制使用 memory 策略
    for _ in range(3):
        reply, _, _ = await brain.chat("你觉得猫和狗哪个好？")
        print(f"  回复: {reply}")

    # 检索信念
    memories = brain.memory.search("猫狗", prefer_self=True)
    print(f"\n  检索到 {len(memories)} 条:")
    for m in memories:
        print(f"    [is_self={m['is_self']}] {m['content']}")

    assert any("猫" in m["content"] for m in memories), "❌ 未检索到猫相关信念"
    print("  ✅ 信念一致性正常")


async def main():
    try:
        await test_persona_loading()
        await test_strategy_router()
        await test_chat_flow()
        await test_belief_consistency()
        print("\n" + "=" * 70)
        print("✅ 全部测试通过")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
    except Exception as e:
        import traceback
        print(f"\n💥 崩溃: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())