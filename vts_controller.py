import websocket
import json
import time
import threading
import uuid
from typing import Optional, Dict, Callable
from config import *

class VTSController:
    """VTube Studio WebSocket API 控制器"""
    
    def __init__(self):
        self.ws_url = VTS_CONFIG["ws_url"]
        self.plugin_name = VTS_CONFIG["plugin_name"]
        self.plugin_developer = VTS_CONFIG["plugin_developer"]
        
        self.ws = None
        self.authenticated = False
        self.token = None
        self.connected = False
        
        # 存储响应
        self.response_store = {}
        # 消息回调
        self.message_callbacks = []
        # 线程锁
        self.lock = threading.Lock()
        
    def connect(self) -> bool:
        """建立连接"""
        print(f"⏳ 正在连接到 VTube Studio ({self.ws_url})...")
        
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # 在后台线程运行
            wst = threading.Thread(target=self.ws.run_forever, daemon=True)
            wst.start()
            
            # 等待连接建立（最多10秒）
            for _ in range(20):
                if self.connected:
                    break
                time.sleep(0.5)
            
            if not self.connected:
                print("❌ VTS - 连接超时")
                return False
                
            # 等待认证（最多10秒）
            for _ in range(20):
                if self.authenticated:
                    break
                time.sleep(0.5)
            
            if self.authenticated:
                print("✅ VTS - 连接和认证成功！")
                return True
            else:
                print("⚠️ VTS - 连接成功但未认证，请检查是否允许插件")
                return True  # 仍然返回True，让用户通过交互完成认证
                
        except Exception as e:
            print(f"❌ VTS - 连接失败: {e}")
            return False
    
    #=====================WebSocket 回调函数 ======================
    def _on_open(self, ws):
        """连接打开回调"""
        print("✅ WebSocket 连接已建立")
        self.connected = True
        # 请求API状态
        self._send_request("APIStateRequest", {})
    
    def _on_message(self, ws, message):
        """消息接收回调"""
        try:
            data = json.loads(message)
            msg_type = data.get("messageType")
            request_id = data.get("requestID")
            
            # 处理API状态响应
            if msg_type == "APIStateResponse":
                is_auth = data.get("data", {}).get("currentSessionAuthenticated", False)
                if is_auth:
                    print("ℹ️ 当前会话已认证")
                    self.authenticated = True
                else:
                    print("🔑 开始认证流程...")
                    self._request_auth_token()
            
            # 处理认证令牌响应
            elif msg_type == "AuthenticationTokenResponse":
                token = data.get("data", {}).get("authenticationToken")
                if token:
                    self.token = token
                    print(f"✅ 获取认证令牌成功")
                    self._authenticate_session()
                else:
                    print("❌ 获取认证令牌失败")
            
            # 处理会话认证响应
            elif msg_type == "AuthenticationResponse":
                auth_data = data.get("data", {})
                if auth_data.get("authenticated"):
                    self.authenticated = True
                    print("🎉 会话认证成功！")
                    # 获取模型信息
                    self._send_request("CurrentModelRequest", {})
                else:
                    print(f"❌ 会话认证失败: {auth_data.get('reason')}")
            
            # 处理当前模型信息
            elif msg_type == "CurrentModelResponse":
                model_data = data.get("data", {})
                if model_data.get("modelLoaded"):
                    print(f"📦 当前模型: {model_data.get('modelName')}")
            
            # 处理错误
            elif msg_type == "APIError":
                error_data = data.get("data", {})
                error_id = error_data.get("errorID")
                message = error_data.get("message")
                print(f"❌ API错误 [{error_id}]: {message}")
                
                # 如果错误码是50，表示用户拒绝访问，需要重新认证
                if error_id == 50:
                    print("🔑 用户拒绝访问，尝试重新认证...")
                    self.token = None
                    self.authenticated = False
                    self._request_auth_token()
            
            # 存储响应
            if request_id and request_id in self.response_store:
                self.response_store[request_id] = data
                
            # 调用注册的回调
            with self.lock:
                for callback in self.message_callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        print(f"⚠️ 回调执行失败: {e}")
                        
        except json.JSONDecodeError:
            print(f"⚠️ 收到非JSON消息: {message[:100]}...")
        except Exception as e:
            print(f"⚠️ 处理消息时出错: {e}")
    
    def _on_error(self, ws, error):
        print(f"⚠️ WebSocket 错误: {error}")
        self.connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        print("🔌 WebSocket 连接已关闭")
        self.connected = False
        self.authenticated = False
    
    def register_callback(self, callback: Callable):
        """注册消息回调"""
        with self.lock:
            self.message_callbacks.append(callback)
    
    def _send_request(self, msg_type: str, data_payload: Dict, request_id: Optional[str] = None) -> Optional[str]:
        """发送请求"""
        if not self.ws:
            print("❌ WebSocket未连接")
            return None
            
        if request_id is None:
            request_id = str(uuid.uuid4())[:8]
            
        request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": request_id,
            "messageType": msg_type,
            "data": data_payload
        }
        
        try:
            self.ws.send(json.dumps(request))
            return request_id
        except Exception as e:
            print(f"❌ 发送请求失败: {e}")
            return None
    
    def _request_auth_token(self):
        """请求认证令牌"""
        print("⏳ 请求认证令牌，请在VTube Studio中点击'允许'...")
        self._send_request("AuthenticationTokenRequest", {
            "pluginName": self.plugin_name,
            "pluginDeveloper": self.plugin_developer
        })
    
    def _authenticate_session(self):
        """使用令牌认证会话"""
        if not self.token:
            print("❌ 没有可用的令牌")
            return
        self._send_request("AuthenticationRequest", {
            "pluginName": self.plugin_name,
            "pluginDeveloper": self.plugin_developer,
            "authenticationToken": self.token
        })
    
    # ========== 公开API方法 ==========
    
    def set_parameters(self, parameters: Dict[str, float], face_found: bool = True, fade_time: float | None = None):
        """
        设置多个Live2D参数，支持平滑淡出/渐变
        Args:
                parameters: 参数字典，如 {"MouthOpen": 0.5, "EyeOpenLeft": 0.8, "EyeOpenRight": 0.8}
                face_found: 是否告诉VTS"面部已找到"
                fade_time: 渐变过渡时长(秒)，None/0=瞬间切换，大于0平滑插值
        """
        if not self.authenticated:
            print("❌ 未认证，无法控制参数")
            return

        # 参数校验：淡出时间不能为负数
        if fade_time is not None and fade_time < 0:
            print("⚠️ fade_time 不能为负数，已自动置0")
            fade_time = 0.0

        param_list = [{"id": k, "value": v} for k, v in parameters.items()]

        req_body = {
            "faceFound": face_found,
            "parameterValues": param_list
        }
        # 仅当传入有效淡出时间时，追加fadeTime字段
        if fade_time is not None and fade_time > 0:
            req_body["fadeTime"] = fade_time

        self._send_request("InjectParameterDataRequest", req_body)
    
    def set_parameter(self, param_id: str, value: float):
        """设置单个参数"""
        self.set_parameters({param_id: value})
    
    def trigger_hotkey(self, hotkey_id: str):
        """触发快捷键"""
        if not self.authenticated:
            print("❌ 未认证，无法触发热键")
            return
        self._send_request("HotkeyTriggerRequest", {
            "hotkeyID": hotkey_id
        })
    
    def load_model(self, model_id: str):
        """加载模型"""
        if not self.authenticated:
            print("❌ 未认证，无法加载模型")
            return
        self._send_request("ModelLoadRequest", {
            "modelID": model_id
        })
    
    def get_available_models(self):
        """获取可用模型列表"""
        if not self.authenticated:
            print("❌ VTS 未认证")
            return
        return self._send_request("AvailableModelsRequest", {})
    
    def move_model(self, x: float = 0, y: float = 0, rotation: float = 0, size: float = 0, 
                   duration: float = 0.5, relative: bool = False):
        """移动模型"""
        if not self.authenticated:
            print("❌ 未认证")
            return
            
        data = {
            "timeInSeconds": duration,
            "valuesAreRelativeToModel": relative
        }
        if x != 0:
            data["positionX"] = x
        if y != 0:
            data["positionY"] = y
        if rotation != 0:
            data["rotation"] = rotation
        if size != 0:
            data["size"] = size
            
        self._send_request("MoveModelRequest", data)
    
    def activate_expression(self, expression_file: str, fade_time: float = 0.25, active: bool = True):
        """激活/取消表情"""
        if not self.authenticated:
            print("❌ 未认证")
            return
        self._send_request("ExpressionActivationRequest", {
            "expressionFile": expression_file,
            "fadeTime": fade_time,
            "active": active
        })
    
    def close(self):
        """关闭连接"""
        if self.ws:
            self.ws.close()
        print("✅ VTS连接已关闭")