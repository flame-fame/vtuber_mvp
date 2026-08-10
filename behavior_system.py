"""
Live2D VTubeStudio 行为/动作决策系统（完整可用版）
包含：音频驱动、关键词驱动、标记驱动、意图驱动 四层协同
状态机：idle, banter, storytelling, consoling, moderating, sing, dance
所有参数映射基于 live2d_param_mapping.json
"""
import json
import time
import re
import random
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum, auto

# ========================= 基础数据结构 =========================
@dataclass
class Live2DParams:
    """发送给 VTubeStudio 的最终模型参数集（每帧更新）"""
    ParamFacePositionX: float = 0.0
    ParamFacePositionY: float = 0.0
    ParamFacePositionZ: float = 0.0
    ParamAngleX: float = 0.0
    ParamAngleY: float = 0.0
    ParamAngleZ: float = 0.0
    ParamCheek: float = 0.0
    ParamMouthForm: float = 0.0
    ParamMouthOpenY: float = 0.0
    ParamEyeLOpen: float = 1.0
    ParamEyeROpen: float = 1.0
    ParamEyeLSmile: float = 0.0
    ParamEyeRSmile: float = 0.0
    ParamEyeBallX: float = 0.0
    ParamEyeBallY: float = 0.0
    ParamBrowLForm: float = 0.0
    ParamBrowRForm: float = 0.0
    ParamBodyAngleX: float = 0.0
    ParamBodyAngleY: float = 0.0
    ParamBodyAngleZ: float = 0.0
    ParamArmLA: float = 0.0
    ParamArmRA: float = 0.0

@dataclass
class EmotionState:
    """持续情绪表达（用于混合表情）"""
    valence: float = 0.0     # 正面/负面 -1..1
    arousal: float = 0.0     # 激动/平静 0..1
    dominance: float = 0.5   # 掌控/顺从 0..1

@dataclass
class IntentState:
    """Layer 4 输出的高层意图"""
    valence: float = 0.0
    arousal: float = 0.5
    dominance: float = 0.5
    social_mode: str = "neutral"

@dataclass
class ActionRequest:
    """统一动作请求"""
    action_id: str
    layer: int           # 1-4
    priority: int        # 0=微动作, 5=中, 10=独占大动作
    start_time: float
    duration: float
    params_override: Dict[str, float] = field(default_factory=dict)
    animation_name: Optional[str] = None
    emotion_blend: Optional[EmotionState] = None
    cooldown_group: Optional[str] = None
    # 可用于传递序列动画（如舞蹈、动作）
    sequence: Optional[List[Dict]] = None

# ========================= 状态机定义 =========================
class SystemMode(Enum):
    IDLE = auto()
    BANTER = auto()           # 闲聊
    STORYTELLING = auto()     # 讲故事
    CONSOLING = auto()        # 安慰
    MODERATING = auto()       # 主持/控场
    SING = auto()             # 唱歌（口型同步 + 律动）
    DANCE = auto()            # 跳舞（节拍驱动或时间线）

# ========================= 动作库（加载 JSON 映射） =========================
class ActionLibrary:
    """从 live2d_param_mapping.json 加载所有表情、动作、舞蹈、微动作"""
    def __init__(self, json_path: str = "live2d_param_mapping.json"):
        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.expressions = self.data["expressions"]
        self.actions = self.data["actions"]
        self.dance_moves = self.data["dance_moves"]
        self.micro_actions = self.data["micro_actions"]
        self.combo_presets = self.data["combo_presets"]

    def get_expression_params(self, name: str) -> Dict[str, float]:
        """获取表情的静态参数（用于情绪混合）"""
        expr = self.expressions.get(name)
        if expr:
            # 过滤掉 _comment 等非参数字段
            return {k: v for k, v in expr.items() if k.startswith("Param")}
        return {}

    def get_action_sequence(self, name: str) -> Tuple[float, List[Dict]]:
        """返回动作的总时长和关键帧序列"""
        act = self.actions.get(name)
        if act:
            return act["duration"], act["sequence"]
        return 0.0, []

    def get_dance_move(self, name: str) -> Tuple[float, bool, List[Dict]]:
        """返回舞蹈动作的时长、是否可循环、关键帧序列"""
        move = self.dance_moves.get(name)
        if move:
            return move["duration"], move.get("loopable", False), move["sequence"]
        return 0.0, False, []

    def get_micro_sequence(self, name: str) -> List[Dict]:
        """返回微动作的关键帧序列"""
        micro = self.micro_actions.get(name)
        if micro and "sequence" in micro:
            return micro["sequence"]
        return []

# ========================= 微动作独立循环 =========================
class MicroActionLoop:
    """永远在后台运行的微动作（眨眼、呼吸、眼神游移等）"""
    def __init__(self):
        self.blink_timer = random.uniform(2.0, 4.0)
        self.blink_state = 0.0          # 0=睁眼, 1=闭眼
        self.blink_phase = 0.0          # 0-1 用于非等速眨眼
        self.breath_phase = 0.0
        self.eye_gaze_timer = 0.0
        self.gaze_x = 0.0
        self.gaze_y = 0.0
        self.lip_lick_timer = random.uniform(10.0, 20.0)
        self.double_blink_timer = random.uniform(8.0, 15.0)
        self._init_double_blink = False

    def get_params(self, dt: float) -> Dict[str, float]:
        """返回当前帧的微动作参数叠加值"""
        params = {}
        # 呼吸（正弦波，4-6秒周期）
        self.breath_phase += dt * 1.2
        breath_body_y = math.sin(self.breath_phase) * 1.2
        breath_head_y = math.sin(self.breath_phase + 0.3) * 0.6
        params["ParamBodyAngleY"] = breath_body_y
        params["ParamAngleY"] = params.get("ParamAngleY", 0.0) + breath_head_y

        # 眨眼逻辑
        self.blink_timer -= dt
        if self.blink_timer <= 0:
            self.blink_state = 1.0   # 开始闭眼
            self.blink_timer = 0.08  # 闭眼持续时间
            self.blink_phase = 0.0
        elif self.blink_state > 0:
            # 睁眼过程（非等速，慢-快-慢 可通过缓动实现，这里简化线性）
            self.blink_phase += dt * 12.0
            self.blink_state = 1.0 - min(1.0, self.blink_phase)
            if self.blink_state <= 0:
                self.blink_state = 0.0
                self.blink_timer = random.uniform(2.0, 4.0)
        params["ParamEyeLOpen"] = 1.0 - self.blink_state * 0.9
        params["ParamEyeROpen"] = 1.0 - self.blink_state * 0.9

        # 双眨眼（偶尔触发）
        self.double_blink_timer -= dt
        if self.double_blink_timer <= 0 and not self._init_double_blink:
            self._init_double_blink = True
            self.double_blink_timer = 0.5
            self.blink_timer = 0.01  # 强制立刻眨眼
        elif self._init_double_blink and self.blink_state <= 0:
            # 第一次眨眼结束后快速再眨一次
            self.blink_timer = 0.01
            self._init_double_blink = False
            self.double_blink_timer = random.uniform(8.0, 15.0)

        # 眼神游移
        self.eye_gaze_timer -= dt
        if self.eye_gaze_timer <= 0:
            self.gaze_x = random.uniform(-0.3, 0.3)
            self.gaze_y = random.uniform(-0.2, 0.2)
            self.eye_gaze_timer = random.uniform(3.0, 8.0)
        params["ParamEyeBallX"] = self.gaze_x
        params["ParamEyeBallY"] = self.gaze_y

        # 舔嘴唇（偶尔触发）
        self.lip_lick_timer -= dt
        if self.lip_lick_timer <= 0:
            params["ParamMouthOpenY"] = 0.12  # 微张
            self.lip_lick_timer = random.uniform(10.0, 20.0)
        return params

# ========================= 各层信号收集器 =========================
class AudioDrivenLayer:
    """Layer 1：音频驱动口型、身体浮动、头部倾斜"""
    def __init__(self):
        self.rms_history = deque(maxlen=5)
        self.speech_active = False
        self.last_rms = 0.0

    def process(self, now: float, audio_rms: float, audio_pitch: float) -> List[ActionRequest]:
        reqs = []
        self.last_rms = audio_rms
        # 口型同步（不生成 ActionRequest，直接在系统里用 audio_rms 驱动）
        # 身体浮动：根据振幅添加微小的动作请求（与呼吸叠加，此处轻量）
        if audio_rms > 0.02:
            bob = min(audio_rms * 0.8, 2.0)
            reqs.append(ActionRequest(
                action_id="audio_bob",
                layer=1, priority=0,
                start_time=now, duration=0.05,
                params_override={"ParamBodyAngleY": bob, "ParamAngleY": bob*0.5}
            ))
        # 音高驱动眉毛
        pitch_norm = (audio_pitch - 150) / 200.0  # 假设范围
        reqs.append(ActionRequest(
            action_id="audio_pitch",
            layer=1, priority=0,
            start_time=now, duration=0.1,
            params_override={
                "ParamBrowLForm": -pitch_norm * 0.2,
                "ParamBrowRForm": -pitch_norm * 0.2
            }
        ))
        return reqs

class KeywordDrivenLayer:
    """Layer 2：文本关键词触发预设动作"""
    def __init__(self, library: ActionLibrary):
        self.library = library
        self.last_text = ""
        self.rules = [
            (r"比心|爱心", "heart", 6, "mid_gesture", True),
            (r"拜拜|再见", "wave", 7, "big_gesture", True),
            (r"哈哈{2,}", "clap", 5, "mid_gesture", True),  # 大笑可用鼓掌代替
            (r"啊这|草|我靠", "facepalm", 5, "mid_gesture", True),
            (r"吓死我了", "shrug", 6, "big_gesture", True),
            (r"好厉害|太强了|牛批", "thumbs_up", 6, "mid_gesture", True),
            (r"嗯？|什么？|哈？", "tilt_head", 4, "mid_gesture", True),
            (r"呜呜|哭|好伤心", "cry", 6, "mid_gesture", True),
            (r"不好意思|对不起|抱歉", "bow", 8, "big_gesture", True),
            (r"谢谢", "heart", 7, "mid_gesture", True),
        ]

    def scan_text(self, text: str, now: float) -> List[ActionRequest]:
        self.last_text = text
        matched = []
        for pattern, anim, pri, cd, check_neg in self.rules:
            if self._is_negated(text, pattern):
                continue
            if re.search(pattern, text):
                matched.append((pri, anim, cd))
        if not matched:
            return []
        matched.sort(key=lambda x: x[0], reverse=True)
        anim_name = matched[0][1]
        cd_group = matched[0][2]
        duration, seq = self.library.get_action_sequence(anim_name)
        if duration == 0:
            return []
        return [ActionRequest(
            action_id=f"kw_{anim_name}",
            layer=2, priority=matched[0][0],
            start_time=now - 0.1,  # 领先音频
            duration=duration,
            animation_name=anim_name,
            sequence=seq,
            cooldown_group=cd_group,
            emotion_blend=self._get_emotion_for_keyword(anim_name)
        )]

    def _is_negated(self, text, pattern):
        neg_words = ['不', '别', '没', '不要']
        match = re.search(pattern, text)
        if match:
            start = match.start()
            if start >= 2 and any(w in text[start-2:start] for w in neg_words):
                return True
        return False

    def _get_emotion_for_keyword(self, anim):
        if anim == 'heart': return EmotionState(0.8, 0.6, 0.6)
        if anim == 'laugh': return EmotionState(0.9, 0.9, 0.5)
        if anim == 'scared': return EmotionState(-0.5, 1.0, 0.3)
        return EmotionState()

class MarkupDrivenLayer:
    """Layer 3：LLM 结构化标记驱动"""
    def __init__(self, library: ActionLibrary):
        self.library = library
        self.emotion_map = {
            "happy": EmotionState(0.8,0.7,0.6),
            "angry": EmotionState(-0.8,0.9,0.8),
            "sad": EmotionState(-0.7,0.2,0.3),
            "surprised": EmotionState(0.3,1.0,0.5),
            "teasing": EmotionState(0.5,0.6,0.7),
            "shy": EmotionState(0.3,0.4,0.2),
            "serious": EmotionState(0.1,0.3,0.8),
            "bored": EmotionState(-0.2,0.1,0.3),
            "confused": EmotionState(0.0,0.5,0.2),
            "disgusted": EmotionState(-0.7,0.6,0.7),
            "excited": EmotionState(0.9,1.0,0.7),
            "tsundere": EmotionState(0.4,0.6,0.5),
        }

    def process(self, markup: dict, now: float) -> List[ActionRequest]:
        reqs = []
        if "emotion" in markup:
            em = self.emotion_map.get(markup["emotion"], EmotionState())
            # 表情持续 5 秒
            reqs.append(ActionRequest(
                action_id="markup_emotion",
                layer=3, priority=8,
                start_time=now - 0.15,
                duration=5.0,
                emotion_blend=em
            ))
        if "action" in markup:
            action_name = markup["action"]
            intensity = float(markup.get("intensity", 0.7))
            duration, seq = self.library.get_action_sequence(action_name)
            if duration > 0:
                # 根据 intensity 缩放时长
                duration *= intensity
                reqs.append(ActionRequest(
                    action_id=f"markup_{action_name}",
                    layer=3, priority=9,
                    start_time=now - 0.15,
                    duration=duration,
                    animation_name=action_name,
                    sequence=seq,
                    cooldown_group="markup_action"
                ))
        return reqs

class IntentDrivenLayer:
    """Layer 4：AI 语义意图驱动（高层）"""
    def __init__(self):
        pass

    def process(self, intent: IntentState, now: float) -> List[ActionRequest]:
        reqs = []
        em = EmotionState(intent.valence, intent.arousal, intent.dominance)
        reqs.append(ActionRequest(
            action_id="intent_emotion",
            layer=4, priority=10,
            start_time=now,
            duration=10.0,
            emotion_blend=em
        ))
        # 根据社交模式微调（可被行为系统状态机覆盖，这里做基础）
        return reqs

# ========================= 主行为系统 =========================
class BehaviorSystem:
    def __init__(self, action_library: ActionLibrary):
        self.lib = action_library
        self.audio_layer = AudioDrivenLayer()
        self.keyword_layer = KeywordDrivenLayer(self.lib)
        self.markup_layer = MarkupDrivenLayer(self.lib)
        self.intent_layer = IntentDrivenLayer()

        self.current_params = Live2DParams()
        self.target_params = Live2DParams()
        self.micro_loop = MicroActionLoop()

        # 动作队列与状态
        self.active_actions: List[ActionRequest] = []
        self.cooldowns: Dict[str, float] = {}
        self.energy = 1.0
        self.energy_regen = 0.1 / 3.0
        self.last_time = time.time()
        self.delta_time = 0.0

        # 模式状态机
        self.mode: SystemMode = SystemMode.IDLE
        self.mode_start_time = 0.0
        self.mode_data = {}            # 携带额外数据（如舞蹈时间线）

        # 用于唱歌/跳舞的额外计时器
        self.sing_beat_timer = 0.0
        self.dance_current_move = None
        self.dance_move_progress = 0.0

        # 缓存最后一次标记和意图 ----
        self._last_markup: Optional[dict] = None
        self._last_intent: Optional[IntentState] = None

    def set_markup_and_intent(self, markup: Optional[dict], intent: Optional[IntentState]):
        """从 AI 标签更新当前标记和意图"""
        if markup is not None:
            self._last_markup = markup
        if intent is not None:
            self._last_intent = intent

    def get_current_params(self) -> Live2DParams:
        """返回当前平滑后的参数，供 VTS 发送"""
        return self.current_params

    def set_mode(self, mode: SystemMode, data: dict = None):
        """切换行为模式"""
        self.mode = mode
        self.mode_start_time = time.time()
        self.mode_data = data if data else {}
        # 清理队列中不适合新模式的动作（简单处理：清空所有非微动作）
        self.active_actions = [a for a in self.active_actions if a.priority == 0]

    # ===================== 主更新入口 =====================
    def update(self,
               audio_rms: float = 0.0,
               audio_pitch: float = 150.0,
               current_text: str = "",
               llm_markup: Optional[dict] = None,
               llm_intent: Optional[IntentState] = None,
               beat_strength: float = 0.0) -> Live2DParams:
        """每帧调用，返回当前模型参数"""
        # 如果传入 None，则使用缓存值
        if llm_markup is None:
            llm_markup = self._last_markup
        if llm_intent is None:
            llm_intent = self._last_intent
        
        now = time.time()
        self.delta_time = now - self.last_time
        self.last_time = now

        # 根据当前模式收集动作请求
        if self.mode == SystemMode.DANCE:
            self._update_dance(now, beat_strength)
        elif self.mode == SystemMode.SING:
            self._update_sing(now, audio_rms, audio_pitch, beat_strength)
        else:
            # 通用社交模式，调用四层收集
            self._collect_requests(now, audio_rms, audio_pitch, current_text,
                                   llm_markup, llm_intent)

        # 优先级仲裁
        self._arbitrate(now)

        # 混合参数生成目标
        self.target_params = self._blend_params(now)

        # 叠加微动作（权重可能受模式影响）
        micro_weight = 1.0
        if self.mode == SystemMode.DANCE:
            micro_weight = 0.3  # 跳舞时微动作降低，避免眨眼太频繁
        micro_params = self.micro_loop.get_params(self.delta_time)
        self.target_params = self._merge_micro(micro_params, self.target_params, micro_weight)

        # 口型同步：始终由音频驱动（优先级最高）
        self.target_params.ParamMouthOpenY = min(audio_rms * 1.5, 1.0)

        # 平滑过渡
        self._smooth_params()

        # 能量恢复
        self._update_energy()

        # 清理完成动作
        self._cleanup(now)

        return self.current_params

    # ===================== 四层请求收集（非表演模式） =====================
    def _collect_requests(self, now, rms, pitch, text, markup, intent):
        # Layer 1
        self._add_requests(self.audio_layer.process(now, rms, pitch))
        # Layer 2
        if text and text != self.keyword_layer.last_text:
            self._add_requests(self.keyword_layer.scan_text(text, now))
        # Layer 3
        if markup:
            self._add_requests(self.markup_layer.process(markup, now))
        # Layer 4
        if intent:
            self._add_requests(self.intent_layer.process(intent, now))

        # 状态机附加微调（例如 banter 时允许更多头部晃动）
        if self.mode == SystemMode.BANTER:
            self._add_requests([ActionRequest(
                action_id="mode_banter_jitter",
                layer=4, priority=4, start_time=now, duration=0.1,
                params_override={"ParamAngleX": random.uniform(-2.0, 2.0),
                                 "ParamAngleZ": random.uniform(-2.0, 2.0)}
            )])
        elif self.mode == SystemMode.STORYTELLING:
            # 讲故事时身体轻微左右摇摆，节奏放慢
            sway = math.sin(now * 0.5) * 1.5
            self._add_requests([ActionRequest(
                action_id="story_sway",
                layer=4, priority=3, start_time=now, duration=0.5,
                params_override={"ParamBodyAngleZ": sway}
            )])

    # ===================== 表演模式：舞蹈 =====================
    def _update_dance(self, now, beat_strength):
        """节拍驱动或时间线舞蹈"""
        # 清除大部分旧请求，只保留舞蹈相关
        self.active_actions = [a for a in self.active_actions if a.layer == 0]
        dance_data = self.mode_data.get("choreography")  # 预编排时间线
        if dance_data:
            elapsed = now - self.mode_start_time
            params = self._sample_choreography(dance_data, elapsed)
            if params:
                self._add_requests([ActionRequest(
                    action_id="dance_choreo",
                    layer=5, priority=10, start_time=now, duration=0.1,
                    params_override=params
                )])
        else:
            # 节拍即兴舞蹈：每次强拍切换姿势
            if beat_strength > 0.7 and self.dance_move_progress <= 0:
                move_name = random.choice(["body_bounce", "body_sway", "arm_wave_both",
                                           "arm_raise_single", "hip_sway"])
                dur, loopable, seq = self.lib.get_dance_move(move_name)
                if dur > 0:
                    self.dance_current_move = {"name": move_name, "seq": seq, "dur": dur, "start": now}
                    self.dance_move_progress = dur
            if self.dance_move_progress > 0:
                self.dance_move_progress -= self.delta_time
                if self.dance_current_move:
                    elapsed = now - self.dance_current_move["start"]
                    params = self._sample_sequence(self.dance_current_move["seq"],
                                                   elapsed, self.dance_current_move["dur"])
                    self._add_requests([ActionRequest(
                        action_id="dance_beat",
                        layer=5, priority=10, start_time=now, duration=0.1,
                        params_override=params
                    )])

    # ===================== 表演模式：唱歌 =====================
    def _update_sing(self, now, rms, pitch, beat):
        """唱歌：口型完全由音频驱动，身体随节拍律动，面部情绪由当前情绪决定"""
        # 保留当前情绪（可能来自标记或意图）
        # 身体律动跟随节拍
        if beat > 0.6:
            self._add_requests([ActionRequest(
                action_id="sing_beat_sway",
                layer=4, priority=6, start_time=now, duration=0.3,
                params_override={
                    "ParamBodyAngleZ": random.uniform(-3.0, 3.0),
                    "ParamBodyAngleY": random.uniform(-2.0, 2.0)
                }
            )])
        # 口型同步已在主循环中强制设置

    # ===================== 优先级仲裁 =====================
    def _arbitrate(self, now):
        """面部表情：L4>L3>L2>L1；身体动作：独占大动作优先；微动作永远不参与仲裁"""
        self.active_actions.sort(key=lambda a: (-a.priority, a.start_time))
        # 查找当前独占动作
        dominant = None
        for a in self.active_actions:
            if a.priority >= 10 and now < a.start_time + a.duration:
                dominant = a
                break
        if dominant:
            # 移除被压制的身体/表情请求（priority 5-9），但保留 priority 0 微动作和口型
            self.active_actions = [a for a in self.active_actions
                                   if a.priority == 0 or a.priority >= 10 or
                                   (a.layer == 1 and a.action_id == "audio_bob")]  # 保留呼吸感
        # 同组冷却：移除过期的低优先级动作
        filtered = []
        groups_seen = set()
        for a in self.active_actions:
            if a.cooldown_group:
                if a.cooldown_group in groups_seen:
                    continue
                groups_seen.add(a.cooldown_group)
            filtered.append(a)
        self.active_actions = filtered

    # ===================== 参数混合 =====================
    def _blend_params(self, now) -> Live2DParams:
        target = Live2DParams()
        # 基础 idle 微表情
        base_expr = self.lib.get_expression_params("neutral")
        target = self._apply_static_params(target, base_expr)

        # 按优先级叠加表情权重
        emotion_weights = {4: 1.0, 3: 0.8, 2: 0.6, 1: 0.3}
        collected_emotion = EmotionState()
        for action in self.active_actions:
            if now >= action.start_time + action.duration:
                continue
            # 如果有动画序列，根据时间采样并覆盖参数
            if action.sequence:
                elapsed = now - action.start_time
                seq_params = self._sample_sequence(action.sequence, elapsed, action.duration)
                target = self._merge_params(target, seq_params)
            elif action.params_override:
                target = self._merge_params(target, action.params_override)
            if action.emotion_blend:
                w = emotion_weights.get(action.layer, 0.5)
                # 简单加权叠加（取最大值方向）
                collected_emotion.valence += action.emotion_blend.valence * w
                collected_emotion.arousal += action.emotion_blend.arousal * w
                collected_emotion.dominance += action.emotion_blend.dominance * w

        # 归一化情绪并映射为具体参数
        if any([collected_emotion.valence, collected_emotion.arousal]):
            target = self._apply_emotion_to_params(target, collected_emotion)

        return target

    def _apply_emotion_to_params(self, target: Live2DParams, em: EmotionState) -> Live2DParams:
        """将 VAD 情绪转化为具体参数调整（简化映射）"""
        # 嘴角：valence 正向微笑，负向愤怒
        if em.valence > 0:
            target.ParamMouthForm = max(target.ParamMouthForm, em.valence * em.arousal)
        else:
            target.ParamMouthForm = min(target.ParamMouthForm, em.valence * em.arousal * 0.8)
        # 脸颊：高 arousal + 正 valence 会脸红
        target.ParamCheek = min(target.ParamCheek, -abs(em.valence) * em.arousal * 0.8)
        # 眉毛：高 arousal 抬高，负 valence 压低
        target.ParamBrowLForm += (em.arousal - 0.5) * 0.5 - max(0, -em.valence) * 0.4
        target.ParamBrowRForm += (em.arousal - 0.5) * 0.5 - max(0, -em.valence) * 0.4
        # 眼睛微笑：高 valence + arousal
        target.ParamEyeLSmile = max(target.ParamEyeLSmile, max(0, em.valence) * em.arousal * 0.7)
        target.ParamEyeRSmile = max(target.ParamEyeRSmile, max(0, em.valence) * em.arousal * 0.7)
        return target

    def _merge_params(self, base: Live2DParams, override: Dict[str, float]) -> Live2DParams:
        for k, v in override.items():
            if hasattr(base, k):
                setattr(base, k, v)
        return base

    def _apply_static_params(self, base: Live2DParams, params: Dict[str, float]) -> Live2DParams:
        for k, v in params.items():
            if hasattr(base, k):
                setattr(base, k, v)
        return base

    def _sample_sequence(self, sequence: List[Dict], elapsed: float, total_duration: float) -> Dict[str, float]:
        """从关键帧序列中插值获取当前时间点的参数"""
        if not sequence or total_duration <= 0:
            return {}
        # 假设序列已排序，且最后一个 time = total_duration
        # 找到前后两个关键帧
        prev_frame = sequence[0]
        next_frame = sequence[-1]
        for i, frame in enumerate(sequence):
            if frame["time"] >= elapsed:
                next_frame = frame
                prev_frame = sequence[max(i-1, 0)]
                break
        # 计算插值因子
        t0 = prev_frame["time"]
        t1 = next_frame["time"]
        if t1 - t0 == 0:
            alpha = 0.0
        else:
            alpha = (elapsed - t0) / (t1 - t0)
        alpha = max(0.0, min(1.0, alpha))
        # 线性插值
        result = {}
        for key in prev_frame:
            if key == "time": continue
            v0 = prev_frame.get(key, 0.0)
            v1 = next_frame.get(key, 0.0)
            result[key] = v0 + (v1 - v0) * alpha
        return result

    def _sample_choreography(self, timeline: List[Dict], elapsed: float) -> Dict[str, float]:
        """预编排舞蹈时间线插值（与 _sample_sequence 类似）"""
        return self._sample_sequence(timeline, elapsed, timeline[-1]["time"])

    # ===================== 微动作叠加 =====================
    def _merge_micro(self, micro: Dict[str, float], target: Live2DParams, weight: float) -> Live2DParams:
        for k, v in micro.items():
            if hasattr(target, k):
                current = getattr(target, k)
                # 眼睛开闭取更小值（闭眼优先），其他用加法叠加
                if "Eye" in k and "Open" in k:
                    setattr(target, k, min(current, v))
                else:
                    setattr(target, k, current + v * weight)
        return target

    # ===================== 平滑过渡 =====================
    def _smooth_params(self):
        speed_face = 10.0
        speed_body = 5.0
        speed_mouth = 15.0
        dt = self.delta_time
        def lerp_attr(attr, speed):
            cur = getattr(self.current_params, attr)
            tgt = getattr(self.target_params, attr)
            setattr(self.current_params, attr, cur + (tgt - cur) * min(1.0, speed * dt))
        for a in ['ParamMouthForm','ParamCheek','ParamEyeLSmile','ParamEyeRSmile',
                  'ParamBrowLForm','ParamBrowRForm','ParamEyeLOpen','ParamEyeROpen']:
            lerp_attr(a, speed_face)
        for a in ['ParamAngleX','ParamAngleY','ParamAngleZ','ParamBodyAngleX',
                  'ParamBodyAngleY','ParamBodyAngleZ','ParamArmLA','ParamArmRA']:
            lerp_attr(a, speed_body)
        lerp_attr('ParamMouthOpenY', speed_mouth)
        # 眼球通常直接赋值，也可平滑
        lerp_attr('ParamEyeBallX', 8.0)
        lerp_attr('ParamEyeBallY', 8.0)

    # ===================== 能量预算 =====================
    def _update_energy(self):
        self.energy = min(1.0, self.energy + self.energy_regen * self.delta_time)

    def _add_requests(self, requests: List[ActionRequest]):
        for req in requests:
            # 冷却检查
            if req.cooldown_group and req.cooldown_group in self.cooldowns:
                if time.time() - self.cooldowns[req.cooldown_group] < self._cooldown_time(req.cooldown_group):
                    continue
            # 能量检查
            if req.priority >= 5 and self.energy < 0.3:
                continue
            if req.priority >= 10 and self.energy < 0.5:
                req.priority = 5  # 降级
            # 能量消耗
            if req.priority >= 10:
                self.energy -= 0.15
            elif req.priority >= 5:
                self.energy -= 0.05
            else:
                self.energy -= 0.01
            self.energy = max(0.0, self.energy)
            self.active_actions.append(req)
            if req.cooldown_group:
                self.cooldowns[req.cooldown_group] = time.time()

    def _cooldown_time(self, group: str) -> float:
        if 'big' in group: return 5.0
        return 2.5

    def _cleanup(self, now):
        self.active_actions = [a for a in self.active_actions
                               if now < a.start_time + a.duration + 0.2]  # 小缓冲

# ========================= 使用示例 =========================
if __name__ == "__main__":
    # 初始化
    lib = ActionLibrary("live2d_param_mapping.json")  # 确保路径正确
    system = BehaviorSystem(lib)

    # 模拟音频数据、文本等
    # 每帧调用 update，获取参数发送给 VTubeStudio
    params = system.update(audio_rms=0.3, audio_pitch=200, current_text="哈哈哈你好厉害！")
    print(params)