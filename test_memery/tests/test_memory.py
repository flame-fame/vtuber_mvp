# test_memory.py
"""
完整测试套件：覆盖 MemoryManager 和 MemoryExtractor 的所有功能单元

测试分组：
  1. 基础 CRUD（写入、检索、去重、清空）
  2. 语义检索（相似度阈值、top_k、时间衰减、关键词增强）
  3. 冷场抽话题（时间范围过滤、去重、空库处理）
  4. 摘要提取（正常、空输入、JSON 容错、字段缺失）
  5. 异常与边界（空字符串、超长文本、并发送写）
  6. 维护功能（prune 淘汰、clear 清空）
"""
import asyncio
import time
import sys
from memory_manager import MemoryManager
from memory_extractor import MemoryExtractor


# ============================================================
# 测试工具：简单断言框架
# ============================================================
class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def check(self, condition: bool, msg: str):
        if condition:
            self.passed += 1
            print(f"    ✅ {msg}")
        else:
            self.failed += 1
            self.failures.append(msg)
            print(f"    ❌ {msg}")

    def summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 70)
        print(f"📊 测试结果: {self.passed}/{total} 通过")
        if self.failures:
            print("❌ 失败用例:")
            for f in self.failures:
                print(f"   - {f}")
        print("=" * 70)
        return self.failed == 0


runner = TestRunner()


# ============================================================
# 1. 基础 CRUD
# ============================================================
async def test_01_basic_crud():
    print("\n" + "=" * 70)
    print("🧪 测试组 1：基础 CRUD")
    print("=" * 70)

    mm = MemoryManager()
    mm.clear()

    # 1.1 空库状态
    print("\n[1.1] 空库状态")
    runner.check(mm.collection.count() == 0, "清空后 count == 0")
    runner.check(mm.search("任意查询") == [], "空库检索返回 []")
    runner.check(mm.get_random_old_topic() is None, "空库抽话题返回 None")

    # 1.2 写入
    print("\n[1.2] 写入记忆")
    mm.add_memory("用户喜欢玩原神，最爱胡桃", topic="原神", speaker="user")
    mm.add_memory("用户养了一只橘猫", topic="宠物", speaker="user")
    mm.add_memory("AI 自嘲数学不好", topic="自嘲", speaker="ai")
    runner.check(mm.collection.count() == 3, "写入 3 条后 count == 3")

    # 1.3 去重（相同 content）
    print("\n[1.3] 去重（相同 content）")
    before = mm.collection.count()
    mm.add_memory("用户喜欢玩原神，最爱胡桃", topic="原神", speaker="user")
    runner.check(mm.collection.count() == before, "字面完全相同的 content 不重复写入")

    print("\n[1.3b] 去重（语义相近，仅验证不报错）")
    before = mm.collection.count()
    mm.add_memory("用户喜欢玩吃鸡手游，最喜欢玩狙击枪", topic="吃鸡", speaker="user")
    # 语义去重依赖方案B，MVP 阶段允许写入，只验证不崩溃
    runner.check(mm.collection.count() >= before, "语义相近内容不崩溃（允许写入）")
    # 1.4 空内容不写入
    print("\n[1.4] 空内容过滤")
    before = mm.collection.count()
    mm.add_memory("", topic="空", speaker="user")
    mm.add_memory("a", topic="太短", speaker="user")
    runner.check(mm.collection.count() == before, "空/超短内容不写入")

    # 1.5 clear
    print("\n[1.5] clear 清空")
    mm.clear()
    runner.check(mm.collection.count() == 0, "clear 后 count == 0")


# ============================================================
# 2. 语义检索
# ============================================================
async def test_02_search():
    print("\n" + "=" * 70)
    print("🧪 测试组 2：语义检索")
    print("=" * 70)

    mm = MemoryManager()
    mm.clear()
    mm.add_memory("用户喜欢玩原神这款二次元游戏，最爱胡桃", topic="原神", speaker="user")
    mm.add_memory("用户养了一只橘猫叫豆豆，很调皮", topic="宠物", speaker="user")
    mm.add_memory("用户在深圳做程序员，经常加班", topic="职业", speaker="user")
    mm.add_memory("用户喜欢周杰伦的音乐", topic="音乐", speaker="user")

    # 2.1 语义相关性
    print("\n[2.1] 语义相关性")
    r1 = mm.search("有什么游戏推荐", top_k=3)
    runner.check(len(r1) > 0, "检索'游戏'有结果")
    if r1:
        runner.check("原神" in r1[0]["content"], f"最相关的是原神 (实际: {r1[0]['topic']})")

    r2 = mm.search("我家小猫", top_k=3)
    if r2:
        runner.check("猫" in r2[0]["content"], f"检索'小猫'命中宠物 (实际: {r2[0]['topic']})")

    # 2.2 top_k 限制
    print("\n[2.2] top_k 限制")
    r3 = mm.search("随便", top_k=2)
    runner.check(len(r3) <= 2, f"top_k=2 返回 <=2 条 (实际 {len(r3)})")

    # 2.3 相似度阈值
    print("\n[2.3] 相似度阈值过滤")
    r4 = mm.search("量子力学弦理论暗物质", top_k=5)
    runner.check(all(m["similarity"] >= mm.similarity_threshold for m in r4),
                 f"所有结果相似度 >= {mm.similarity_threshold}")

    # 2.4 返回字段完整性
    print("\n[2.4] 返回字段完整性")
    if r1:
        required = {"content", "topic", "speaker", "date_str", "similarity", "age_days"}
        runner.check(required.issubset(r1[0].keys()),
                     f"返回字段包含 {required}")

    # 2.5 format_for_prompt
    print("\n[2.5] format_for_prompt 格式化")
    fmt = mm.format_for_prompt(r1)
    runner.check("【相关记忆】" in fmt, "包含标题'【相关记忆】'")
    runner.check("user曾提到" in fmt, "包含 speaker 前缀")
    runner.check(mm.format_for_prompt([]) == "", "空列表返回空字符串")


# ============================================================
# 3. 冷场抽话题
# ============================================================
async def test_03_proactive_topic():
    print("\n" + "=" * 70)
    print("🧪 测试组 3：冷场抽话题")
    print("=" * 70)

    mm = MemoryManager()
    mm.clear()

    # 3.1 空库
    print("\n[3.1] 空库处理")
    runner.check(mm.get_random_old_topic() is None, "空库返回 None")

    # 3.2 写入 5 条 3 天前的旧记忆
    print("\n[3.2] 时间范围过滤")
    old_ts = time.time() - 3 * 86400
    for i, (topic, content) in enumerate([
        ("电影", "用户喜欢悬疑电影"),
        ("音乐", "用户喜欢周杰伦"),
        ("旅行", "用户想去日本"),
        ("美食", "用户爱吃火锅"),
        ("运动", "用户打羽毛球"),
    ]):
        mm.collection.add(
            ids=[f"old_{i}"],
            embeddings=[mm._embed(content)],
            documents=[content],
            metadatas=[{
                "topic": topic, "speaker": "user",
                "timestamp": old_ts, "date_str": "3天前"
            }]
        )

    # 3.3 太新的记忆不抽（0.5 天内）
    print("\n[3.3] 太新的记忆排除")
    mm.add_memory("刚刚聊过的新鲜事", topic="新话题", speaker="user")
    # 抽 20 次，验证从不出现在结果里
    got_new = False
    for _ in range(20):
        mm.recent_topics = []  # 每次重置，允许重复抽
        t = mm.get_random_old_topic()
        if t and t["topic"] == "新话题":
            got_new = True
            break
    runner.check(not got_new, "0.5 天内的新记忆不被抽取")

    # 3.4 去重机制
    print("\n[3.4] 话题去重")
    mm.recent_topics = []
    seen = []
    for _ in range(5):
        t = mm.get_random_old_topic()
        if t:
            seen.append(t["topic"])
    runner.check(len(seen) == len(set(seen)), f"5 次抽取无重复 (实际: {seen})")
    runner.check(len(mm.recent_topics) <= 5, "recent_topics 上限 5")

    # 3.5 recent_topics 满后抽不出
    print("\n[3.5] recent_topics 满后")
    t = mm.get_random_old_topic()
    runner.check(t is None, "所有旧话题都在 recent 里时返回 None")


# ============================================================
# 4. 摘要提取
# ============================================================
async def test_04_extractor():
    print("\n" + "=" * 70)
    print("🧪 测试组 4：摘要提取器")
    print("=" * 70)

    ex = MemoryExtractor()

    # 4.1 空输入直接返回
    print("\n[4.1] 空/无意义输入")
    for bad in ["", "嗯", "哦", "哈哈", "?", "？", "a"]:
        r = ex.extract(bad, "嗯嗯")
        runner.check(r["content"] == "" and r["topic"] == "",
                     f"'{bad}' 返回空 ({r})")

    # 4.2 正常提取
    print("\n[4.2] 正常提取")
    r = ex.extract("我今天在原神里抽到胡桃了！", "恭喜！")
    runner.check(r["topic"] != "", f"topic 非空: {r['topic']}")
    runner.check(r["content"] != "", f"content 非空: {r['content']}")
    runner.check(isinstance(r["keywords"], list), "keywords 是 list")

    # 4.3 返回结构完整性
    print("\n[4.3] 返回结构")
    runner.check(set(r.keys()) == {"topic", "content", "keywords"},
                 f"字段完整: {list(r.keys())}")

    # 4.4 异步版本
    print("\n[4.4] 异步版本")
    r_async = await ex.extract_async("我家猫把键盘踩坏了", "哈哈")
    runner.check(r_async["content"] != "", f"异步提取: {r_async['content']}")

    # 4.5 极短 AI 回复不报错
    print("\n[4.5] 边界：AI 回复极短")
    r = ex.extract("我喜欢深圳的海边", "嗯")
    runner.check(isinstance(r, dict), "极短 AI 回复不崩溃")


# ============================================================
# 5. 异常与并发
# ============================================================
async def test_05_exception_concurrency():
    print("\n" + "=" * 70)
    print("🧪 测试组 5：异常与并发")
    print("=" * 70)

    mm = MemoryManager()
    mm.clear()

    # 5.1 超长文本
    print("\n[5.1] 超长文本")
    long_text = "用户喜欢" + "猫" * 500
    try:
        mm.add_memory(long_text, topic="压力测试", speaker="user")
        runner.check(True, "超长文本不崩溃")
    except Exception as e:
        runner.check(False, f"超长文本崩溃: {e}")

    # 5.2 并发写入（异步）
    print("\n[5.2] 并发写入（10 条）")
    before = mm.collection.count()
    tasks = [
        mm.add_memory_async(f"并发测试内容_{i}的详细描述", topic=f"并发{i}", speaker="user")
        for i in range(10)
    ]
    await asyncio.gather(*tasks)
    after = mm.collection.count()
    runner.check(after - before == 10, f"10 条并发写入全部成功 (增加 {after - before})")

    # 5.3 特殊字符
    print("\n[5.3] 特殊字符")
    try:
        mm.add_memory("用户说：'你好' \"世界\" \n\t 换行", topic="特殊", speaker="user")
        runner.check(True, "特殊字符不崩溃")
    except Exception as e:
        runner.check(False, f"特殊字符崩溃: {e}")

    # 5.4 中文标点/emoji
    print("\n[5.4] Emoji 和中文标点")
    try:
        mm.add_memory("用户说：好开心啊😄！真是太棒了～", topic="情绪", speaker="user")
        runner.check(True, "Emoji 不崩溃")
    except Exception as e:
        runner.check(False, f"Emoji 崩溃: {e}")

    # 5.5 检索空字符串
    print("\n[5.5] 检索边界")
    r = mm.search("")
    runner.check(isinstance(r, list), "检索空字符串返回 list")


# ============================================================
# 6. 维护功能
# ============================================================
async def test_06_maintenance():
    print("\n" + "=" * 70)
    print("🧪 测试组 6：维护功能")
    print("=" * 70)

    mm = MemoryManager()
    mm.clear()

    # 6.1 prune 淘汰
    print("\n[6.1] prune 淘汰旧记忆")
    for i in range(20):
        # 手动构造递增时间戳，确保有新旧顺序
        mm.collection.add(
            ids=[f"p_{i}"],
            embeddings=[mm._embed(f"测试记忆{i}")],
            documents=[f"测试记忆{i}"],
            metadatas=[{
                "topic": f"t{i}", "speaker": "user",
                "timestamp": time.time() - (20 - i) * 3600,
                "date_str": "test"
            }]
        )
    runner.check(mm.collection.count() == 20, "写入 20 条")
    mm.prune(max_count=10)
    runner.check(mm.collection.count() == 10, f"prune 后剩 10 条 (实际 {mm.collection.count()})")

    # 6.2 prune 不超上限时不动
    print("\n[6.2] prune 未超限")
    before = mm.collection.count()
    mm.prune(max_count=100)
    runner.check(mm.collection.count() == before, "未超限不删除")

    # 6.3 clear
    print("\n[6.3] clear")
    mm.clear()
    runner.check(mm.collection.count() == 0, "clear 后 0 条")


# ============================================================
# 7. 端到端流程
# ============================================================
async def test_07_e2e():
    print("\n" + "=" * 70)
    print("🧪 测试组 7：端到端流程")
    print("=" * 70)

    mm = MemoryManager()
    ex = MemoryExtractor()
    mm.clear()

    # 7.1 模拟多轮对话 → 记忆累积
    print("\n[7.1] 多轮对话累积记忆")
    dialogs = [
        ("我家猫今天又淘气了", "哈哈，猫咪都这样"),
        ("我最近在玩原神，抽到胡桃了", "恭喜！胡桃很强"),
        ("深圳的天气真热", "是呀，注意防暑"),
    ]
    for user_in, ai_reply in dialogs:
        extracted = await ex.extract_async(user_in, ai_reply)
        if extracted["content"]:
            await mm.add_memory_async(
                extracted["content"],
                extracted["topic"] or "闲聊",
                speaker="user",
                keywords=extracted.get("keywords", [])
            )
    count = mm.collection.count()
    runner.check(count >= 2, f"多轮对话后累积 >=2 条记忆 (实际 {count})")

    # 7.2 后续检索命中
    print("\n[7.2] 后续检索命中")
    r = mm.search("我家小猫咪")
    hit = any("猫" in m["content"] for m in r)
    runner.check(hit, f"检索'小猫咪'命中猫相关记忆")

    # 7.3 关键词增强检索
    print("\n[7.3] 关键词拼接增强")
    all_data = mm.collection.get(include=["documents"])
    has_keywords = any("（" in doc for doc in all_data["documents"])
    runner.check(has_keywords, "关键词已拼接到 content")


# ============================================================
# 主入口
# ============================================================
async def main():
    print("=" * 70)
    print("🚀 开始完整测试套件")
    print("=" * 70)

    try:
        await test_01_basic_crud()
        await test_02_search()
        await test_03_proactive_topic()
        await test_04_extractor()
        await test_05_exception_concurrency()
        await test_06_maintenance()
        await test_07_e2e()
    except Exception as e:
        import traceback
        print(f"\n💥 测试执行崩溃: {e}")
        traceback.print_exc()

    ok = runner.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())