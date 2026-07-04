import requests
import time
import json
import math

class VTubeDriver:
    def __init__(self, port=8001):
        self.base_url = f"http://localhost:{port}/api/v1"
        self.connected = False
        
    def test_connection(self):
        """测试VTube Studio是否在运行"""
        try:
            response = requests.get(f"{self.base_url}/ping", timeout=2)
            if response.status_code == 200:
                self.connected = True
                print("✅ 已连接 VTube Studio")
                return True
        except:
            print("❌ 无法连接 VTube Studio，请确保它已启动并开启API")
            return False
        return False
    
    def set_mouth_open(self, value):
        """
        控制嘴部张开程度
        value: 0.0（闭嘴） ~ 1.0（最大张开）
        """
        if not self.connected:
            return
        
        # VTube Studio的口型参数名通常叫 MouthOpen
        data = {
            "model": {
                "paramValues": [
                    {
                        "id": "MouthOpen",  # 标准参数名
                        "value": value
                    }
                ]
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/parameter",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=1
            )
            return response.status_code == 200
        except:
            return False
    
    def set_emotion(self, emotion):
        """
        切换表情（通过参数组合实现）
        emotion: "happy", "angry", "sad", "surprised", "neutral"
        """
        if not self.connected:
            return
        
        # 不同表情对应的参数值映射
        emotion_params = {
            "happy": {"EyeOpen": 1.0, "MouthForm": 0.8, "EyebrowY": -0.5},
            "angry": {"EyeOpen": 0.7, "MouthForm": -0.6, "EyebrowY": 0.8, "EyebrowAngle": 0.7},
            "sad": {"EyeOpen": 0.5, "MouthForm": -0.3, "EyebrowY": 0.5},
            "surprised": {"EyeOpen": 1.2, "MouthOpen": 0.9, "EyebrowY": -0.8},
            "neutral": {"EyeOpen": 0.8, "MouthOpen": 0.0, "MouthForm": 0.0, "EyebrowY": 0.0}
        }
        
        params = emotion_params.get(emotion, emotion_params["neutral"])
        
        # 构建请求参数
        param_values = [{"id": k, "value": v} for k, v in params.items()]
        data = {"model": {"paramValues": param_values}}
        
        try:
            response = requests.post(
                f"{self.base_url}/parameter",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=1
            )
            return response.status_code == 200
        except:
            return False
    
    def move_head(self, x=0, y=0, z=0):
        """
        控制头部转动
        x: -30 ~ 30（左右）
        y: -20 ~ 20（上下）
        z: -30 ~ 30（倾斜）
        """
        if not self.connected:
            return
        
        data = {
            "model": {
                "paramValues": [
                    {"id": "AngleX", "value": x},
                    {"id": "AngleY", "value": y},
                    {"id": "AngleZ", "value": z}
                ]
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/parameter",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=1
            )
            return response.status_code == 200
        except:
            return False
    
    def set_parameter(self, param_id, value):
        """通用参数设置接口"""
        if not self.connected:
            return
        
        data = {
            "model": {
                "paramValues": [
                    {"id": param_id, "value": value}
                ]
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/parameter",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=1
            )
            return response.status_code == 200
        except:
            return False
    
    def close(self):
        """复位所有参数到中性状态"""
        self.set_emotion("neutral")
        self.set_mouth_open(0)
        self.move_head(0, 0, 0)


# ============ 使用示例 ============
if __name__ == "__main__":
    # 创建驱动实例
    driver = VTubeDriver(port=8001)
    
    # 测试连接
    if not driver.test_connection():
        print("请先打开 VTube Studio 并开启 API")
        exit(1)
    
    # 演示：各种表情切换
    print("😊 切换开心表情...")
    driver.set_emotion("happy")
    time.sleep(1)
    
    print("😡 切换生气表情...")
    driver.set_emotion("angry")
    time.sleep(1)
    
    print("😮 切换惊讶表情...")
    driver.set_emotion("surprised")
    time.sleep(1)
    
    print("😐 回到中性...")
    driver.set_emotion("neutral")
    time.sleep(1)
    
    # 演示：说话（嘴部开合）
    print("🗣️ 模拟说话（嘴部开合）...")
    for i in range(10):
        # 正弦波模拟说话节奏
        mouth_value = (math.sin(i * 0.8) + 1) / 2  # 0~1之间变化
        driver.set_mouth_open(mouth_value)
        time.sleep(0.1)
    
    # 关闭复位
    driver.close()
    print("✅ 演示完成")