import pyvts
import asyncio

# 1. 准备插件信息（首次连接时会向用户请求授权）
plugin_info = {
    "plugin_name": "我的AI主播",  # 你的插件名称
    "developer": "你的名字",  # 开发者名称
    "authentication_token_path": "./token.txt",  # 用于存储认证令牌的文件路径
}


async def main():
    # 2. 创建 vts 实例并连接
    vts = pyvts.vts(plugin_info=plugin_info)
    await vts.connect()
    # 3. 请求令牌（首次运行会触发 VTS 弹窗）
    await vts.request_authenticate_token()
    # 使用令牌进行认证
    authenticated = await vts.request_authenticate()
    print("🔑 认证成功！")
    # 4. 在这里添加你的控制代码

    if authenticated:
        print("你可以继续在控制台输入命令。")
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
                    await vts.request(vts.vts_request.requestSetParameterValue(cmd[1], float(cmd[2])))
                elif cmd[0] == "hotkey" and len(cmd) == 2:
                    await vts.request(vts.vts_request.requestTriggerHotKey(cmd[1]))
                else:
                    print("⚠️ 无效命令")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ 输入错误: {e}")
    else:
        print("❌ 认证失败，请检查VTS设置并重新运行。")

    print("👋 退出程序")
    # 5. 关闭连接
    await vts.close()

if __name__ == "__main__":
    asyncio.run(main())
