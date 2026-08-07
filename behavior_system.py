# ============================================================
# Live2D VTubeStudio 行为/动作决策系统
#┌─────────────────────────────────────────────────┐
#│  Layer 4：AI 语义驱动（最智能，最自然）            
#│  输入：LLM 理解对话内容 → 推断意图和情绪            
#│  输出："现在是吐槽环节，我要做个嫌弃脸+摆手"        
#├─────────────────────────────────────────────────┤    
#│  Layer 3：结构化标记驱动（可控性强）                
#│  输入：LLM 在回复中嵌入 [action:wave] [emotion:tsundere] 
#│  输出：标记 → 预设动画/表情映射                     
#├─────────────────────────────────────────────────┤
#│  Layer 2：文本关键词驱动（最实用）                  
#│  输入：在播报文本中匹配关键词（"比心""挥手""哈哈"）   
#│  输出：匹配到后插入对应动作                          
#├─────────────────────────────────────────────────┤
#│  Layer 1：音频信号驱动（基础层，每句话都有）          
#│  振幅包络	身体上下浮动（呼吸感）	跟随句子节奏的微幅身体 bob
#|  音高（F0）​	眉毛和头部倾斜	高音 → 眉毛微抬 + 头微仰，低音 → 放松
#|  语速	眨眼频率	语速快 → 眨眼少（专注），语速慢 → 眨眼多（放松）                       │
#└─────────────────────────────────────────────────┘
# ============================================================
import time, re, random, math
from collections import deque
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass, field
from live2d_params import Live2DParams
# --- 基础数据结构 ---
@dataclass
class EmotionState:
    """持续的情绪表达状态，用于混合表情参数"""
    valence: float = 0.0    # 正面/负面 -1..1
    arousal: float = 0.0    # 激动/平静 0..1
    dominance: float = 0.5  # 掌控/顺从 0..1

@dataclass
class IntentState:
    """Layer 4 输出的高层意图，驱动行为模型"""
    valence: float = 0.0
    arousal: float = 0.5
    dominance: float = 0.5
    social_mode: str = "neutral"   # banter, storytelling, consoling, moderating, idle...
    energy: float = 0.8

# --- 动作请求结构 ---
@dataclass
class ActionRequest:
    """由各层生成的统一动作请求"""
    action_id: str                  # 唯一标识
    layer: int                     # 来源层 1-4
    priority: int                  # 0=微动作(可叠加), 5=中, 10=独占大动作
    start_time: float              # 请求生成时间
    duration: float                # 持续时间
    params_override: Dict[str, float]  # 直接覆盖的参数
    animation_name: Optional[str] = None  # 预设动画名
    emotion_blend: Optional[EmotionState] = None
    cooldown_group: Optional[str] = None  # 冷却分组

# --- 全局系统 ---
class BehaviorSystem:
    def __init__(self):
        # 四层模块
        self.audio_layer = AudioDrivenLayer()
        self.keyword_layer = KeywordDrivenLayer()
        self.markup_layer = MarkupDrivenLayer()
        self.intent_layer = IntentDrivenLayer()
        
        # 当前表情/身体状态（持续更新，用于 lerp）
        self.current_params = Live2DParams()
        self.current_emotion = EmotionState()
        self.target_params = Live2DParams()      # 最终混合目标
        
        # 活跃的动作队列（按优先级排序）
        self.active_actions: List[ActionRequest] = []
        
        # 微动作独立循环（永远运行）
        self.micro_actions = MicroActionLoop()
        
        # 能量预算
        self.energy = 1.0
        self.energy_regen_rate = 0.1 / 3.0       # 每3秒恢复0.1
        
        # 冷却记录 {group_name: last_trigger_time}
        self.cooldowns: Dict[str, float] = {}
        
        # 上一帧音频音量（用于口型同步）
        self.last_audio_rms = 0.0
        
        # 帧时间
        self.last_frame_time = time.time()
        self.delta_time = 0.0

    # ==================== 主循环 ====================
    def update(self, audio_rms: float, audio_pitch: float, 
               current_text: str, llm_markup: Optional[dict] = None,
               llm_intent: Optional[IntentState] = None):
        """
        每帧调用（通常 60fps），计算当前帧的模型参数。
        参数是各层需要的实时输入。
        """
        now = time.time()
        self.delta_time = now - self.last_frame_time
        self.last_frame_time = now

        # 1. 收集各层的动作请求
        self._collect_layer_requests(now, audio_rms, audio_pitch, current_text, 
                                     llm_markup, llm_intent)

        # 2. 冲突解决 & 优先级仲裁
        self._arbitrate_actions(now)

        # 3. 混合所有活跃请求，生成目标参数
        self.target_params = self._blend_params(now)

        # 4. 加入微动作独立循环的输出
        micro_params = self.micro_actions.get_params(now, self.delta_time)
        self.target_params = self._merge_micro(micro_params, self.target_params)

        # 5. 平滑过渡到目标参数（永远用 lerp）
        self._smooth_params()

        # 6. 能量自然恢复
        self._update_energy()

        # 7. 清理已完成的动作
        self._cleanup_actions(now)

        return self.current_params   # 发送给 VTubeStudio

    # ==================== 各层收集请求 ====================
    def _collect_layer_requests(self, now, audio_rms, pitch, text, markup, intent):
        # Layer 1: 音频驱动 (基础层，每帧都产生影响)
        reqs_l1 = self.audio_layer.process(now, audio_rms, pitch, text)
        self._add_requests(reqs_l1)
        
        # Layer 2: 关键词驱动 (实时文本扫描，低频触发)
        if text and text != self.keyword_layer.last_processed_text:
            reqs_l2 = self.keyword_layer.scan_text(text, now)
            self._add_requests(reqs_l2)
        
        # Layer 3: LLM 标记驱动 (结构化标记，优先级高于关键词)
        if markup:
            reqs_l3 = self.markup_layer.process_markup(markup, now)
            self._add_requests(reqs_l3)
        
        # Layer 4: 意图驱动 (最高层意图，持续影响)
        if intent:
            reqs_l4 = self.intent_layer.process_intent(intent, now)
            self._add_requests(reqs_l4)

    def _add_requests(self, requests: List[ActionRequest]):
        for req in requests:
            # 冷却检查
            if req.cooldown_group and req.cooldown_group in self.cooldowns:
                if time.time() - self.cooldowns[req.cooldown_group] < self._cooldown_time(req.cooldown_group):
                    continue
            # 能量检查（中、大动作需要能量）
            if req.priority >= 5 and self.energy < 0.3:
                continue
            if req.priority >= 10 and self.energy < 0.5:
                # 大动作能量不足，降级为中动作或忽略
                req.priority = 5
                req.animation_name = None
                req.params_override = {"body_y": 0.1}  # 微小代替
            
            # 扣能量
            self._consume_energy(req)
            
            self.active_actions.append(req)
            # 记录冷却
            if req.cooldown_group:
                self.cooldowns[req.cooldown_group] = time.time()

    # ==================== 优先级仲裁 ====================
    def _arbitrate_actions(self, now):
        """
        面部表情：Layer4 > Layer3 > Layer2 > Layer1
        身体动作：独占大动作(priority>=10)排队执行，中动作可被打断，微动作总是叠加
        口型：始终由 Layer1 驱动，但情绪可微调。
        """
        # 排序：优先级高的在前，同优先级按时间
        self.active_actions.sort(key=lambda a: (-a.priority, a.start_time))
        
        # 找出当前最高优先级的独占动作（如果有）
        dominant_action = None
        for action in self.active_actions:
            if action.priority >= 10 and now < action.start_time + action.duration:
                dominant_action = action
                break
        
        # 如果有独占动作，则中优先级及以下的面部表情请求暂时被抑制
        # 但微动作（priority 0）不受影响（在混合阶段单独处理）
        # 这里实现抑制逻辑：移除被覆盖的动作请求，但保留 duration 内的独占动作
        self.active_actions = [a for a in self.active_actions 
                               if (a.priority >= 10 or 
                                   (dominant_action is None and a.priority >= 5) or 
                                   a.priority == 0 or 
                                   now < a.start_time + a.duration)]

    # ==================== 参数混合 ====================
    def _blend_params(self, now) -> Live2DParams:
        """
        混合所有活跃请求的参数，遵循表情优先和权重规则。
        大动作直接覆盖骨骼参数（身体），表情参数根据 valence 加权。
        """
        target = Live2DParams()  # 空白起点
        
        # 默认基线：idle 状态
        idle_emotion = EmotionState(valence=0.1, arousal=0.2, dominance=0.5)
        target = self._apply_emotion_blend(target, idle_emotion, weight=0.3)  # 始终保持轻微微笑
        
        # 收集各层的 emotion_blend 和 params_override
        for action in self.active_actions:
            if now >= action.start_time + action.duration:
                continue
            # 计算动作进度 (0 到 1)
            elapsed = now - action.start_time
            progress = min(elapsed / action.duration, 1.0) if action.duration > 0 else 1.0
            
            # 动画类动作：直接设置身体参数（混合时权重高）
            if action.animation_name:
                anim_params = self._get_animation_params(action.animation_name, progress)
                target = self._merge_params_override(target, anim_params, action.priority)
            
            # 情绪混合：按优先级加权叠加
            if action.emotion_blend:
                weight = self._layer_weight(action.layer)  # L4>L3>L2>L1
                target = self._apply_emotion_blend(target, action.emotion_blend, weight)
            
            # 直接参数覆盖：口型等
            if action.params_override:
                target = self._merge_params_override(target, action.params_override, action.priority)
        
        # 最后 Layer1 音频驱动口型强制覆盖（口型总是最高优先级）
        target.mouth_open = self.last_audio_rms * 1.5  # 幅度映射
        
        return target

    def _apply_emotion_blend(self, params: Live2DParams, emotion: EmotionState, weight: float) -> Live2DParams:
        """根据 VAD 情绪值混合面部参数"""
        # 简化映射：valence 影响 smile/anger，arousal 影响眉毛和眼睛张开程度
        smile = max(0, emotion.valence) * emotion.arousal * weight
        anger = max(0, -emotion.valence) * emotion.arousal * weight
        params.param_smile = max(params.param_smile, smile)
        params.param_anger = max(params.param_anger, anger)
        # 眉毛随 arousal 抬高
        params.brow_left_y += emotion.arousal * 0.2 * weight
        params.brow_right_y += emotion.arousal * 0.2 * weight
        # 眼睛大小随情绪变化
        eye_factor = 1.0 + (emotion.arousal - 0.5) * 0.3
        params.eye_open_left *= eye_factor
        params.eye_open_right *= eye_factor
        return params

    def _merge_params_override(self, base: Live2DParams, override: Dict[str, float], priority: int) -> Live2DParams:
        """用加权方式合并参数，高优先级完全覆盖低优先级"""
        # 这里简单处理：直接赋值对应字段，因为 arbitration 已经移除了低优先级冲突项
        for key, val in override.items():
            setattr(base, key, val)
        return base

    def _layer_weight(self, layer: int) -> float:
        if layer == 4: return 1.0
        elif layer == 3: return 0.8
        elif layer == 2: return 0.6
        elif layer == 1: return 0.3
        return 0.0

    # ==================== 平滑过渡 ====================
    def _smooth_params(self):
        """对所有参数做 lerp，避免瞬间切换。速度根据参数类型不同。"""
        smooth_speed_face = 8.0   # 表情快速跟随
        smooth_speed_body = 4.0   # 身体动作稍慢
        smooth_speed_mouth = 12.0 # 口型极快
        
        # 利用 delta_time 计算插值因子
        def lerp_attr(attr_name: str, speed: float):
            current = getattr(self.current_params, attr_name)
            target = getattr(self.target_params, attr_name)
            factor = min(1.0, speed * self.delta_time)
            setattr(self.current_params, attr_name, current + (target - current) * factor)
        
        for attr in ['param_smile', 'param_anger', 'brow_left_y', 'brow_right_y',
                     'eye_open_left', 'eye_open_right']:
            lerp_attr(attr, smooth_speed_face)
        for attr in ['head_x', 'head_y', 'body_y', 'body_z']:
            lerp_attr(attr, smooth_speed_body)
        lerp_attr('mouth_open', smooth_speed_mouth)

    # ==================== 微动作独立循环 ====================
    class MicroActionLoop:
        def __init__(self):
            self.blink_timer = random.uniform(2.0, 4.0)
            self.blink_state = 0.0   # 0=睁开, 1=闭眼
            self.breath_phase = 0.0
            self.eye_gaze_timer = 0.0
            self.gaze_x = 0.0
            self.gaze_y = 0.0
        
        def get_params(self, now, dt) -> Dict[str, float]:
            # 呼吸：4-6 秒周期正弦波，映射到身体轻微浮动
            self.breath_phase += dt * 1.0  # ~6.28秒周期
            breath_body_y = math.sin(self.breath_phase) * 0.015  # 微小浮动
            
            # 眨眼：非等速，快速闭合，稍慢睁开
            self.blink_timer -= dt
            if self.blink_timer <= 0:
                self.blink_state = 1.0  # 闭眼
                self.blink_timer = 0.1  # 闭眼持续时间 0.1s
            elif self.blink_state > 0:
                # 睁开过程
                self.blink_state = max(0.0, self.blink_state - dt * 10.0)
            
            # 眼神游移：每 3-8 秒改变注视点
            self.eye_gaze_timer -= dt
            if self.eye_gaze_timer <= 0:
                self.gaze_x = random.uniform(-0.3, 0.3)
                self.gaze_y = random.uniform(-0.2, 0.2)
                self.eye_gaze_timer = random.uniform(3.0, 8.0)
            
            return {
                'body_y': breath_body_y,
                'eye_open_left': 1.0 - self.blink_state * 0.9,
                'eye_open_right': 1.0 - self.blink_state * 0.9,
                'head_x': self.gaze_x * 0.5,   # 头轻微跟随目光
                'head_y': self.gaze_y * 0.3,
            }

    def _merge_micro(self, micro: Dict[str, float], target: Live2DParams) -> Live2DParams:
        """微动作叠加到目标参数上（加法叠加或取最大值）"""
        for key, val in micro.items():
            current = getattr(target, key, 0.0)
            # 身体浮动用加法，眨眼用覆盖（闭眼状态优先）
            if 'eye_open' in key:
                setattr(target, key, min(current, val))  # 取更小的（闭眼）
            else:
                setattr(target, key, current + val)
        return target

    # ==================== 能量预算 ====================
    def _consume_energy(self, action: ActionRequest):
        if action.priority >= 10:   # 大动作
            self.energy -= 0.15
        elif action.priority >= 5:  # 中动作
            self.energy -= 0.05
        else:                       # 微表情
            self.energy -= 0.01
        self.energy = max(0.0, self.energy)

    def _update_energy(self):
        self.energy = min(1.0, self.energy + self.energy_regen_rate * self.delta_time)

    def _cooldown_time(self, group_name: str) -> float:
        if 'big' in group_name:
            return 5.0
        return 2.5

    # ==================== 辅助：动画参数查询 ====================
    def _get_animation_params(self, anim_name: str, progress: float) -> Dict[str, float]:
        """这里模拟从动画库获取参数，实际对接 Live2D 动画系统"""
        if anim_name == 'wave':
            return {'head_x': math.sin(progress * 6.28) * 0.2, 'body_z': 0.1}
        elif anim_name == 'heart':
            return {'param_cheek': 0.8, 'param_smile': 0.9}
        # ... 其他动画
        return {}

    def _cleanup_actions(self, now):
        self.active_actions = [a for a in self.active_actions if now < a.start_time + a.duration]


# ============================================================
# 各层具体实现（伪代码）
# ============================================================

class AudioDrivenLayer:
    """Layer 1: 音频信号驱动"""
    def __init__(self):
        self.rms_history = deque(maxlen=10)
        self.speech_start_time = None
        self.in_speech = False

    def process(self, now: float, rms: float, pitch: float, text: str) -> List[ActionRequest]:
        reqs = []
        # 口型同步参数（实时驱动，不生成请求，直接由 system 读取 rms）
        # 但身体 bob 和头部倾斜需要转换为请求
        if rms > 0.02:
            if not self.in_speech:
                self.in_speech = True
                self.speech_start_time = now
                # 句子开始，身体微微前倾
                reqs.append(ActionRequest(
                    action_id="audio_lean_in",
                    layer=1, priority=3,
                    start_time=now - 0.08,  # 提前80ms
                    duration=0.2,
                    params_override={"body_z": 0.05}
                ))
            # 跟随振幅的身体 bob (用呼吸叠加实现)
            bob_amount = min(rms * 0.5, 0.03)  # 微小
            reqs.append(ActionRequest(
                action_id="audio_bob",
                layer=1, priority=0,  # 微动作级别，叠加
                start_time=now,
                duration=0.05,  # 短请求，下一帧会再生成
                params_override={"body_y": bob_amount}
            ))
        else:
            if self.in_speech:
                self.in_speech = False
                # 句末身体回退
                reqs.append(ActionRequest(
                    action_id="audio_lean_back",
                    layer=1, priority=3,
                    start_time=now,
                    duration=0.3,
                    params_override={"body_z": 0.0, "body_y": 0.0}
                ))
        
        # 音高影响眉毛（高音抬眉）
        pitch_factor = (pitch - 150) / 200.0  # 假设 pitch 范围
        reqs.append(ActionRequest(
            action_id="audio_pitch_brow",
            layer=1, priority=0,
            start_time=now,
            duration=0.1,
            params_override={"brow_left_y": pitch_factor * 0.15, "brow_right_y": pitch_factor * 0.15}
        ))
        
        return reqs


class KeywordDrivenLayer:
    """Layer 2: 文本关键词驱动"""
    def __init__(self):
        self.last_processed_text = ""
        # 关键词规则库 (正则，动作名，优先级，冷却组，否定检测)
        self.rules = [
            (r"比心|爱心", "heart", 6, "mid_gesture", True),
            (r"拜拜|再见|byebye", "wave", 7, "big_gesture", True),
            (r"哈哈{2,}", "laugh", 5, "mid_gesture", True),
            (r"啊这|草|我靠", "facepalm", 5, "mid_gesture", True),
            (r"吓死我了", "scared", 6, "big_gesture", True),
            (r"好厉害|太强了|牛批", "clap", 6, "mid_gesture", True),
            (r"嗯？|什么？|哈？", "tilt_head", 4, "mid_gesture", True),
            (r"呜呜|哭|好伤心", "cry", 6, "mid_gesture", True),
            (r"不好意思|对不起|抱歉", "bow", 8, "big_gesture", True),
            (r"谢谢", "heart_thanks", 7, "mid_gesture", True),
        ]
    
    def scan_text(self, text: str, now: float) -> List[ActionRequest]:
        self.last_processed_text = text
        reqs = []
        matched = []
        for pattern, anim, priority, cd_group, check_neg in self.rules:
            if self._is_negated(text, pattern):  # 否定检测
                continue
            if re.search(pattern, text):
                matched.append((priority, anim, cd_group))
        
        if not matched:
            return []
        
        # 取优先级最高的一个
        matched.sort(key=lambda x: x[0], reverse=True)
        top_anim = matched[0][1]
        cd_group = matched[0][2]
        
        reqs.append(ActionRequest(
            action_id=f"kw_{top_anim}",
            layer=2,
            priority=matched[0][0],
            start_time=now - 0.1,  # 领先音频
            duration=2.0,          # 动作时长
            animation_name=top_anim,
            cooldown_group=cd_group,
            emotion_blend=self._emotion_for_anim(top_anim)
        ))
        return reqs

    def _is_negated(self, text, pattern):
        """检查关键词前两个词内是否有否定词"""
        neg_words = ['不', '别', '没', '不要']
        idx = text.find(re.search(pattern, text).group())
        if idx > 1:
            before = text[idx-2:idx]
            if any(w in before for w in neg_words):
                return True
        return False

    def _emotion_for_anim(self, anim: str) -> EmotionState:
        if anim == 'heart':
            return EmotionState(valence=0.8, arousal=0.6)
        if anim == 'laugh':
            return EmotionState(valence=0.9, arousal=0.9)
        if anim == 'scared':
            return EmotionState(valence=-0.5, arousal=1.0)
        # ...
        return EmotionState()


class MarkupDrivenLayer:
    """Layer 3: LLM 结构化标记驱动"""
    def process_markup(self, markup: dict, now: float) -> List[ActionRequest]:
        reqs = []
        # markup 结构: {"emotion": "teasing", "action": "shrug", "intensity": 0.8}
        if "emotion" in markup:
            emotion_map = {
                "happy": EmotionState(0.8,0.7,0.6), "angry": EmotionState(-0.8,0.9,0.8),
                "sad": EmotionState(-0.7,0.2,0.3), "surprised": EmotionState(0.3,1.0,0.5),
                "teasing": EmotionState(0.5,0.6,0.7), "shy": EmotionState(0.3,0.4,0.2),
                "serious": EmotionState(0.1,0.3,0.8),
            }
            em = emotion_map.get(markup["emotion"], EmotionState())
            reqs.append(ActionRequest(
                action_id="markup_emotion",
                layer=3, priority=8,  # 高于关键词
                start_time=now - 0.15,  # 提前触发
                duration=5.0,           # 持续表情
                emotion_blend=em,
                cooldown_group=None
            ))
        if "action" in markup:
            intensity = markup.get("intensity", 0.7)
            reqs.append(ActionRequest(
                action_id=f"markup_{markup['action']}",
                layer=3, priority=9,
                start_time=now - 0.15,
                duration=2.0 * intensity,
                animation_name=markup["action"],
                params_override={"intensity": intensity},
                cooldown_group="markup_action"
            ))
        return reqs


class IntentDrivenLayer:
    """Layer 4: AI 语义意图驱动"""
    def process_intent(self, intent: IntentState, now: float) -> List[ActionRequest]:
        reqs = []
        # 意图直接转为持续情绪状态，最高优先级
        em = EmotionState(intent.valence, intent.arousal, intent.dominance)
        reqs.append(ActionRequest(
            action_id="intent_emotion",
            layer=4, priority=10,   # 最高
            start_time=now,
            duration=10.0,          # 意图持续较长
            emotion_blend=em,
            cooldown_group=None
        ))
        
        # 根据社交模式触发行为集合
        if intent.social_mode == "banter":
            # 允许更多随机的头部晃动，激活吐槽手势池
            reqs.append(ActionRequest(
                action_id="mode_banter",
                layer=4, priority=4,
                start_time=now,
                duration=9999,  # 模式持续
                params_override={"head_x_jitter": 0.2}  # 自定义参数
            ))
        elif intent.social_mode == "storytelling":
            reqs.append(ActionRequest(
                action_id="mode_story",
                layer=4, priority=4,
                start_time=now,
                duration=9999,
                params_override={"gesture_smooth": 0.1, "body_sway": 0.3}
            ))
        # 能量管理由系统的能量预算负责，这里不再重复
        return reqs