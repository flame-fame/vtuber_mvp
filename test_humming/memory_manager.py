# 在 ai_brain.py 顶部新增导入
import chromadb
from chromadb.utils import embedding_functions
import uuid
import random

class MemoryManager:
    def __init__(self, model_name: str , system_prompt: str, temperature: float, max_tokens: int):
        # ... 你原有的初始化代码保持不变 ...
        
        # ========== 新增：ChromaDB 记忆系统初始化 ==========
        # 使用轻量级本地嵌入模型（无需联网，自动下载）
        self.embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"  # 仅 80MB，速度快
        )
        # 持久化存储到本地 ./chroma_db 目录
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        
        # 创建或获取记忆集合
        self.memory_collection = self.chroma_client.get_or_create_collection(
            name="neuro_memories",
            embedding_function=self.embedding_func,
            metadata={"hnsw:space": "cosine"}  # 余弦相似度
        )
        print(f"🧠 记忆系统已加载，现有记忆条数: {self.memory_collection.count()}")
        
        # 冷场阈值（秒）
        self.idle_threshold = 60  # 1分钟无互动触发主动回忆

    # ========== 核心记忆操作方法 ==========
    def add_memory(self, user_input: str, ai_response: str, emotion: str = "neutral"):
        """将一次对话存入向量库（只存精华，避免冗余）"""
        # 1. 生成简洁的文本描述（用于向量化和展示）
        # 截取关键内容，避免记忆污染
        memory_text = f"User asked: {user_input[:60]} | AI replied: {ai_response[:60]}"
        
        # 2. 提取关键词作为元数据（方便按类型检索）
        keywords = self._extract_keywords(user_input + " " + ai_response)
        
        # 3. 生成唯一 ID（用时间戳+随机数）
        memory_id = f"mem_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        
        # 4. 存入 ChromaDB
        self.memory_collection.add(
            documents=[memory_text],
            metadatas=[{
                "timestamp": time.time(),
                "emotion": emotion,
                "keywords": keywords,
                "user_msg": user_input[:100],
                "ai_msg": ai_response[:100]
            }],
            ids=[memory_id]
        )
        # 控制总记忆量（防止过老数据占用资源，可保留最近 1000 条）
        self._trim_memories(max_count=1000)
        print(f"💾 新记忆已存储: {memory_text[:30]}...")

    def retrieve_memories(self, query: str, n_results: int = 3) -> list:
        """根据当前话题检索最相关的历史记忆"""
        if self.memory_collection.count() == 0:
            return []
        
        try:
            results = self.memory_collection.query(
                query_texts=[query],
                n_results=min(n_results, self.memory_collection.count())
            )
            # 格式化返回
            memories = []
            if results and results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]
                    memories.append({
                        "text": doc,
                        "timestamp": meta.get("timestamp"),
                        "emotion": meta.get("emotion", "neutral"),
                        "user_msg": meta.get("user_msg", ""),
                        "ai_msg": meta.get("ai_msg", "")
                    })
            return memories
        except Exception as e:
            print(f"⚠️ 记忆检索失败: {e}")
            return []

    def get_random_memory_topic(self) -> str:
        """随机捞取一条历史记忆，用于主动发起话题（破冰/自嘲）"""
        count = self.memory_collection.count()
        if count == 0:
            return None
        
        # 随机偏移量取一条
        random_offset = random.randint(0, count - 1)
        # 用 peek 或 随机 query 获取
        all_ids = self.memory_collection.get()['ids']
        if not all_ids:
            return None
        
        random_id = random.choice(all_ids)
        result = self.memory_collection.get(ids=[random_id])
        
        if result and result['documents']:
            doc = result['documents'][0]
            meta = result['metadatas'][0]
            # 构造一个俏皮的“挖坟”话题
            topic = f"我突然想起之前聊过 {meta.get('user_msg', '某个话题')}，那时候我说了句「{meta.get('ai_msg', '...')}」，现在想想好羞耻啊！"
            return topic
        return None

    def get_similar_memory_for_context(self, current_input: str) -> str:
        """根据当前用户输入，检索相似历史，给 AI 提供自嘲素材"""
        memories = self.retrieve_memories(current_input, n_results=1)
        if memories:
            m = memories[0]
            # 返回格式化的上下文提示，告诉 AI 它以前也犯过类似错误或聊过类似内容
            return f"（提示：用户现在说的内容，和你之前聊过的「{m['user_msg']}」很像，你当时的回答是「{m['ai_msg']}」，你可以借此自嘲或玩梗）"
        return ""

    def _extract_keywords(self, text: str) -> str:
        """简易关键词提取（按空格和标点切分取前 5 个实词）"""
        # 仅作简单过滤，不引入额外 NLP 库
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z]+', text)
        # 过滤掉常见无意义词（停用词简化版）
        stopwords = {'的', '了', '在', '是', '我', '你', '他', '她', '它', '们', 'and', 'the', 'to', 'for'}
        keywords = [w for w in words if w not in stopwords and len(w) > 1]
        return ','.join(keywords[:5]) if keywords else "general"

    def _trim_memories(self, max_count: int):
        """限制记忆总数，按时间戳删除最老的"""
        count = self.memory_collection.count()
        if count > max_count:
            # 获取所有数据按时间戳排序（通过 get 拿到全部）
            all_data = self.memory_collection.get()
            if all_data and all_data['ids']:
                # 按元数据中的 timestamp 排序
                ids_with_ts = sorted(
                    zip(all_data['ids'], [m.get('timestamp', 0) for m in all_data['metadatas']]),
                    key=lambda x: x[1]
                )
                # 删除最老的一半（保留较新的）
                ids_to_delete = [item[0] for item in ids_with_ts[:-(max_count // 2)]]
                if ids_to_delete:
                    self.memory_collection.delete(ids=ids_to_delete)
                    print(f"🧹 清理了 {len(ids_to_delete)} 条过时记忆")