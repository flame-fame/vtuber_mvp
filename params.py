# --- 基础数据结构 ---
@dataclass
class Live2DParams:
    """需要发送给 VTubeStudio 的最终模型参数集（每帧更新）"""
    ParamAngleX: float = 0.0        # 人脸角度 X
    ParamAngleY: float = 0.0        # 人脸角度 Y
    ParamAngleZ: float = 0.0        # 人脸角度 Z
    ParamCheek: float = 0.0        # 腮红

    ParamMouthForm: float = 0.0        # 嘴型 0-1
    ParamMouthOpenY: float = 0.0           # 口型 0-1
    MouthPositionX: float = 0.0        # 嘴型位置 X
    MouthPositionY: float = 0.0        # 嘴型位置 Y

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

    # ... 其他 Live2D 自定义参数