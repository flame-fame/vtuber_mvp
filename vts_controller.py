import websocket
import json
import time
import threading
import os
from typing import Dict, Callable,Optional
from config import *
# 用于生成唯一的请求ID
import uuid


class VTSController:
    def __init__(self):
        self.ws_url = VTS_CONFIG["ws_url"]
        self.plugin_name = VTS_CONFIG["plugin_name"]
        self.plugin_developer = VTS_CONFIG["plugin_developer"]
        self.token_file = VTS_CONFIG["token_file"]

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

    def connect(self):
        """建立WebSocket连接"""
        print(f"⏳ 正在连接到 VTube Studio ({self.ws_url})...")
        try:
            # 启用trace可查看详细日志，此处关闭
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            # 在另一个线程中运行，避免阻塞主程序
            wst = threading.Thread(target=self.ws.run_forever, daemon=True)
            wst.start()

            self.connected = False
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
                return False

        except Exception as e:
            print(f"❌ VTS 连接失败: {e}")
            return False

    # ============== 内部方法 - WebSocket 回调方法 ==============
    def _on_open(self, ws):
        print("✅ VTS WebSocket 连接已建立")
        self.connected = True
        # 连接成功后，首先请求API状态
        self._send_request("APIStateRequest", {})

    def _on_message(self, ws, message):
        """处理所有收到的消息"""
        try:
            data = json.loads(message)

            msg_type = data.get("messageType")
            request_id = data.get("requestID")

            # 处理API状态响应
            if msg_type == "APIStateResponse":
                is_auth = data.get("data", {}).get("currentSessionAuthenticated", False)
                if is_auth:
                    print("ℹ️ VTS 当前会话已认证")
                    self.authenticated = True
                else:
                    print("🔑 VTS 当前会话未认证，尝试使用本地 Token...")
                    # ✅ 先尝试读取本地保存的 token
                    saved_token = self._load_token()
                    if saved_token:
                        self.token = saved_token
                        print(
                            f"📂 VTS - 找到本地 Token: {saved_token[:8]}...，直接尝试认证"
                        )
                        self._authenticate_session()
                    else:
                        print("❌ VTS - 本地 Token 不存在或为空，开始完整认证流程...")
                        self._request_auth_token()

            # 处理认证令牌响应
            elif msg_type == "AuthenticationTokenResponse":
                token = data.get("data", {}).get("authenticationToken")
                if token:
                    self.token = token
                    print(f"✅ VTS - 成功获取认证令牌: {token}")
                    # 使用令牌进行会话认证
                    self._authenticate_session()
                else:
                    print("❌ VTS - 获取认证令牌失败")

            # 处理会话认证响应
            elif msg_type == "AuthenticationResponse":
                auth_data = data.get("data", {})
                if auth_data.get("authenticated"):
                    self.authenticated = True
                    # ✅ 认证成功后保存 token
                    if self.token:
                        self._save_token(self.token)
                    print("🎉 VTS - 会话认证成功！可以开始控制模型了。")
                    # 认证成功后，可以执行初始化操作，例如获取当前模型信息
                    self._send_request("CurrentModelRequest", {})
                else:
                    print(f"❌ VTS - 会话认证失败: {auth_data.get('reason')}")
                    # 清除失效的本地 token
                    if os.path.exists(self.token_file):
                        os.remove(self.token_file)
                    # 回退到完整认证流程（弹窗）
                    self._request_auth_token()

            # 处理当前模型信息响应
            elif msg_type == "CurrentModelResponse":
                model_data = data.get("data", {})
                if model_data.get("modelLoaded"):
                    print(f"📦 VTS - 当前模型: {model_data.get('modelName')}")
                    # 可以在这里添加初始化的表情或动作
                    # self.trigger_expression("your_expression_name")
                else:
                    print("ℹ️ VTS - 当前未加载任何模型")

            # 处理通用错误响应
            elif msg_type == "APIError":
                error_data = data.get("data", {})
                print(
                    f"❌ API错误 [{error_data.get('errorID')}]: {error_data.get('message')}"
                )

            # 将响应存储，供send_request方法使用（如果需要同步等待）
            if request_id:
                self.response_store[request_id] = data
                print(f"✅ VTS - 成功存储响应: {request_id}:{data}")

            # 调用注册的回调函数
            with self.lock:
                for callback in self.message_callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        print(f"⚠️ VTS - 回调{callback.__name__}执行失败: {e}")

        except json.JSONDecodeError:
            print(f"⚠️ VTS - 收到非JSON消息: {message}")
        except Exception as e:
            print(f"⚠️ VTS - 处理消息时出错: {e}")

    def _on_error(self, ws, error):
        self.connected = False
        print(f"⚠️ VTS - WebSocket 错误 : {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        self.authenticated = False
        self.token = None

        print(f"🔌 VTS - WebSocket 连接已关闭: {close_status_code} {close_msg}")    

    # ============== 内部方法 - 发送请求和注册回调 ==============

    def _send_request(self, msg_type: str, data_payload: Dict, request_id=None):
        """发送请求到VTS API"""
        if not self.ws:
            print("❌ VTS - WebSocket未连接, 无法发送请求")
            return None

        if request_id is None:
            request_id = str(uuid.uuid4())[:8]
            print(f"✅ VTS - 生成新请求ID: {request_id}")

        request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": request_id,
            "messageType": msg_type,
            "data": data_payload,
        }
        try:
            self.ws.send(json.dumps(request))
            print(f"✅ VTS - 发送请求成功: {request_id}:{data_payload}")
            return request_id
        except Exception as e:
            print(f"❌ VTS - 发送请求失败: {e}")
            return None
        
    def _register_callback(self, callback: Callable):
        """注册消息回调"""
        with self.lock:
            self.message_callbacks.append(callback)
            print(f"✅ VTS - 注册回调: {callback.__name__}")
    
    # ============== API 认证流程方法 ==============
    def _request_auth_token(self):
        """请求认证令牌（会触发VTS弹窗）"""
        print("⏳ VTS - 正在请求认证令牌，请在VTube Studio中允许插件访问...")
        self._send_request(
            "AuthenticationTokenRequest",
            {
                "pluginName": self.plugin_name,
                "pluginDeveloper": self.plugin_developer,
                # 可选: "pluginIcon": "base64_encoded_128x128_png"
            },
        )

    def _authenticate_session(self):
        """使用令牌认证当前会话"""
        if not self.token:
            print("❌ VTS - 没有可用的令牌，请先请求令牌")
            return
        print("⏳ VTS - 正在进行会话认证...")
        self._send_request(
            "AuthenticationRequest",
            {
                "pluginName": self.plugin_name,
                "pluginDeveloper": self.plugin_developer,
                "authenticationToken": self.token,
            },
        )

    # ============== 认证令牌管理方法 ==============
    def _save_token(self, token):
        """将 token 保存到本地文件"""
        with open(self.token_file, "w") as f:
            f.write(token)
        print(f"💾 Token 已保存到 {self.token_file}")

    def _load_token(self):
        """从本地文件读取 token"""
        if os.path.exists(self.token_file):
            print(f"✅ VTS - 本地文件存在: {self.token_file}")
            with open(self.token_file, "r") as f:
                token = f.read().strip()
                if token:
                    return token
                else:
                    print("⚠️ VTS - 本地文件存在但为空")
        return None

    # ============== 公开API方法 ==============
    def set_parameter(self, param_id, value):
        """设置一个Live2D参数（例如口型、表情）"""
        # 注意：这里使用的是"InjectParameterDataRequest"
        # 它用于覆盖面部追踪等输入参数
        self._send_request(
            "InjectParameterDataRequest",
            {
                "faceFound": True,  # 告诉VTS"面部已找到"，避免触发丢失动画
                "parameterValues": [{"id": param_id, "value": value}],
            },
        )
        print(f"✅ VTS - 发送设置参数请求 {param_id} : {value}")

    def set_parameters(self, parameters: Dict[str, float]):
        """
        设置多个Live2D参数，支持平滑淡出/渐变
        Args:
                parameters: 参数字典，如 {"MouthOpen": 0.5, "EyeOpenLeft": 0.8, "EyeOpenRight": 0.8}
        """
        param_list = [{"id": k, "value": v} for k, v in parameters.items()]

        req_body = {
            "faceFound": True,
            "parameterValues": param_list
        }
       
        self._send_request("InjectParameterDataRequest", req_body)
        print(f"✅ VTS - 发送设置参数请求 {parameters}")

    def activate_expression(
        self, expression_name: str, fade_time: float = 0.25, active: bool = True
    ):
        """激活/取消表情"""
        if not self.authenticated:
            print("❌ 未认证")
            return
        self._send_request(
            "ExpressionActivationRequest",
            {
                "expressionFile": f"{expression_name}.exp3.json",
                "fadeTime": fade_time,
                "active": active,
            },
        )
        print(f"✅ VTS - 发送激活/取消表情请求 {expression_name} {fade_time} {active}")

    # 获取当前加载的模型信息
    def get_model_info(self):
        """获取当前加载的模型信息"""
        print(f"✅ VTS - 发送获取当前模型信息请求")
        return self._send_request("CurrentModelRequest", {})

    def trigger_hotkey(self, hotkey_id):
        """触发一个已配置的热键"""
        self._send_request("HotkeyTriggerRequest", {"hotkeyID": hotkey_id})
        print(f"✅ VTS - 发送触发热键请求 {hotkey_id}")

    def close(self):
        """关闭与websocket的连接"""
        self.ws.close()
        self.ws = None
        self.response_store.clear()
        self.message_callbacks.clear()
        print("✅ VTS - 已关闭websocket连接")

    def get_callback(self):
        return self.message_callbacks
    def get_response(self):
        return self.response_store
