import websocket
import json
import time
import threading
import os

# 用于生成唯一的请求ID
import uuid

# ================= 配置区 =================
VTS_WS_URL = "ws://localhost:8001"  # 默认WebSocket端口
PLUGIN_NAME = "MyAIVTuber"  # 插件名称
PLUGIN_DEVELOPER = "LXL"  # 开发者名称
TOKEN_FILE = "vts_token.txt"  # 认证令牌文件名
# =========================================


class VTSConnection:
    def __init__(self):
        self.ws = None
        self.authenticated = False
        self.token = None
        # 用于存储异步响应的简易字典
        self.response_store = {}

    def connect(self):
        """建立WebSocket连接"""
        print(f"⏳ 正在连接到 VTube Studio ({VTS_WS_URL})...")
        try:
            # 启用trace可查看详细日志，此处关闭
            self.ws = websocket.WebSocketApp(
                VTS_WS_URL,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
            )
            # 在另一个线程中运行，避免阻塞主程序
            wst = threading.Thread(target=self.ws.run_forever, daemon=True)
            wst.start()
            # 等待连接建立
            time.sleep(10)
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

    def on_open(self, ws):
        print("✅ WebSocket 连接已建立")
        # 连接成功后，首先请求API状态（这是官方推荐的第一个步骤）
        self.send_request("APIStateRequest", {})

    def on_message(self, ws, message):
        """处理所有收到的消息"""
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
                    print("🔑 当前会话未认证，尝试使用本地 Token...")
                    # ✅ 先尝试读取本地保存的 token
                    saved_token = self.load_token()
                    if saved_token:
                        self.token = saved_token
                        print(f"📂 找到本地 Token: {saved_token[:8]}...，直接尝试认证")
                        self.authenticate_session()
                    else:
                        print("❌ 本地 Token 不存在或为空，开始完整认证流程...")
                        self.request_auth_token()

            # 处理认证令牌响应
            elif msg_type == "AuthenticationTokenResponse":
                token = data.get("data", {}).get("authenticationToken")
                if token:
                    self.token = token
                    print(f"✅ 成功获取认证令牌: {token[:8]}...")
                    # 第二步：使用令牌进行会话认证
                    self.authenticate_session()
                else:
                    print("❌ 获取认证令牌失败")

            # 处理会话认证响应
            elif msg_type == "AuthenticationResponse":
                auth_data = data.get("data", {})
                if auth_data.get("authenticated"):
                    self.authenticated = True
                    # ✅ 认证成功后保存 token
                    if self.token:
                        self.save_token(self.token)
                    print("🎉 会话认证成功！可以开始控制模型了。")
                    # 认证成功后，可以执行初始化操作，例如获取当前模型信息
                    self.send_request("CurrentModelRequest", {})
                else:
                    print(f"❌ 会话认证失败: {auth_data.get('reason')}")
                    # 清除失效的本地 token
                    if os.path.exists(TOKEN_FILE):
                        os.remove(TOKEN_FILE)
                    # 回退到完整认证流程（弹窗）
                    self.request_auth_token()

            # 处理当前模型信息响应
            elif msg_type == "CurrentModelResponse":
                model_data = data.get("data", {})
                if model_data.get("modelLoaded"):
                    print(f"📦 当前模型: {model_data.get('modelName')}")
                    # 可以在这里添加初始化的表情或动作
                    # self.trigger_expression("your_expression_name")
                else:
                    print("ℹ️ 当前未加载任何模型")

            # 处理通用错误响应
            elif msg_type == "APIError":
                error_data = data.get("data", {})
                print(
                    f"❌ API错误 [{error_data.get('errorID')}]: {error_data.get('message')}"
                )

            # 将响应存储，供send_request方法使用（如果需要同步等待）
            if request_id and request_id in self.response_store:
                self.response_store[request_id] = data

        except json.JSONDecodeError:
            print(f"⚠️ 收到非JSON消息: {message}")
        except Exception as e:
            print(f"⚠️ 处理消息时出错: {e}")

    def on_error(self, ws, error):
        print(f"⚠️ WebSocket 错误: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("🔌 WebSocket 连接已关闭")
        self.authenticated = False

    def send_request(self, msg_type, data_payload, request_id=None):
        """发送请求到VTS API"""
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
            "data": data_payload,
        }
        try:
            self.ws.send(json.dumps(request))
            return request_id
        except Exception as e:
            print(f"❌ 发送请求失败: {e}")
            return None

    # ============== API 认证流程方法 ==============
    def request_auth_token(self):
        """请求认证令牌（会触发VTS弹窗）"""
        print("⏳ 正在请求认证令牌，请在VTube Studio中允许插件访问...")
        self.send_request(
            "AuthenticationTokenRequest",
            {
                "pluginName": PLUGIN_NAME,
                "pluginDeveloper": PLUGIN_DEVELOPER,
                # 可选: "pluginIcon": "base64_encoded_128x128_png"
            },
        )

    def authenticate_session(self):
        """使用令牌认证当前会话"""
        if not self.token:
            print("❌ 没有可用的令牌，请先请求令牌")
            return
        print("⏳ 正在进行会话认证...")
        self.send_request(
            "AuthenticationRequest",
            {
                "pluginName": PLUGIN_NAME,
                "pluginDeveloper": PLUGIN_DEVELOPER,
                "authenticationToken": self.token,
            },
        )

    # ============== 认证令牌管理方法 ==============
    def save_token(self, token):
        """将 token 保存到本地文件"""
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        print(f"💾 Token 已保存到 {TOKEN_FILE}")

    def load_token(self):
        """从本地文件读取 token"""
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                token = f.read().strip()
                if token:
                    return token
        return None

    # ============== 核心控制方法 ==============
    def set_parameter(self, param_id, value):
        """设置一个Live2D参数（例如口型、表情）"""
        if not self.authenticated:
            print("❌ 未认证，无法控制参数")
            return
        # 注意：这里使用的是"InjectParameterDataRequest"
        # 它用于覆盖面部追踪等输入参数
        self.send_request(
            "InjectParameterDataRequest",
            {
                "faceFound": True,  # 告诉VTS"面部已找到"，避免触发丢失动画
                "parameterValues": [{"id": param_id, "value": value}],
            },
        )

    def trigger_hotkey(self, hotkey_id):
        """触发一个已配置的热键"""
        if not self.authenticated:
            print("❌ 未认证，无法触发热键")
            return
        self.send_request("HotkeyTriggerRequest", {"hotkeyID": hotkey_id})

    def get_model_info(self):
        """获取当前加载的模型信息"""
        return self.send_request("CurrentModelRequest", {})


# ================= 主程序入口 =================
def main():
    print("=" * 50)
    print("🚀 VTube Studio MVP 控制器")
    print("=" * 50)

    vts = VTSConnection()
    if not vts.connect():
        print("💡 请确保VTube Studio已启动，并且API端口设置为8001")
        return

    # 等待认证完成（简单起见，等待几秒）
    print("⏳ 等待认证流程完成... (请留意VTS的弹窗)")
    time.sleep(6)  # 给用户留出点击"允许"的时间

    if vts.authenticated:
        print("\n🎮 开始演示控制！")

        # 演示1: 让模型张嘴 (MouthOpen 是常用参数)
        print("👄 张嘴 (参数值 0.8)...")
        vts.set_parameter("MouthOpen", 0.8)
        time.sleep(1.5)

        print("👄 闭嘴 (参数值 0.0)...")
        vts.set_parameter("MouthOpen", 0.0)
        time.sleep(0.5)

        # 演示2: 尝试触发一个名为 "Happy" 的热键（如果你配置了的话）
        # print("😊 尝试触发 'Happy' 热键...")
        # vts.trigger_hotkey("Happy")

        print("\n✅ MVP演示结束。你可以继续在控制台输入命令。")
        print("输入 'param <name> <value>' 控制参数")
        print("输入 'hotkey <id>' 触发热键")
        print("输入 'quit' 退出程序")

        # 简单的交互循环
        while True:
            try:
                cmd = input("> ").strip().split()
                if not cmd:
                    continue
                if cmd[0] == "quit":
                    break
                elif cmd[0] == "param" and len(cmd) == 3:
                    vts.set_parameter(cmd[1], float(cmd[2]))
                elif cmd[0] == "hotkey" and len(cmd) == 2:
                    vts.trigger_hotkey(cmd[1])
                else:
                    print("⚠️ 无效命令")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ 输入错误: {e}")
    else:
        print("❌ 认证失败，请检查VTS设置并重新运行。")

    print("👋 退出程序")


if __name__ == "__main__":
    main()
