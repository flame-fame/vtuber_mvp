from dataclasses import dataclass, field
# --- 基础数据结构 ---
@dataclass
class Live2DParams:
    """需要发送给 VTubeStudio 的最终模型参数集（每帧更新）"""
    FaceAngleX: float = 0.0        # 人脸角度 X
    FaceAngleY: float = 0.0        # 人脸角度 Y
    FaceAngleZ: float = 0.0        # 人脸角度 Z
    Blush: float = 0.0        # 腮红

    MouthSmile: float = 0.0        # 嘴型 0-1
    MouthOpen: float = 0.0           # 口型 0-1
    MouthPositionX: float = 0.0        # 嘴型位置 X
    MouthPositionY: float = 0.0        # 嘴型位置 Y

    EyeOpenLeft: float = 1.0
    EyeOpenRight: float = 1.0
    EyeSmileLeft: float = 0.0
    EyeSmileRight: float = 0.0

    EyeLeftX: float = 0.0
    EyeLeftY: float = 0.0
    EyeRightX: float = 0.0
    EyeRightY: float = 0.0

    BrowLeftY: float = 0.0
    BrowRightY: float = 0.0
    BrowSmileLeft: float = 0.0
    BrowSmileRight: float = 0.0

    head_x: float = 0.0              # 左右转头
    head_y: float = 0.0              # 上下抬头
    body_y: float = 0.0              # 身体浮动 bob
    body_z: float = 0.0              # 身体前后
    param_cheek: float = 0.0         # 腮红/情绪
    param_smile: float = 0.0
    param_anger: float = 0.0
    # ... 其他 Live2D 自定义参数