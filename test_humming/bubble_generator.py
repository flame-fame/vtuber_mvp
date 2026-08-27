# bubble_generator.py
from PIL import Image, ImageDraw, ImageFont
from vts_controller import VTSController
from config import ITEM_PATH
import os
import time
import hashlib

class BubbleGenerator:
    def __init__(self):
        self.font_size = 16
        self.max_width = 600
        self.base_dir = ITEM_PATH
        self.item_name = None
        self.font_type = "simhei.ttf"
        self.output_path = None

    def generate_bubble(self, text: str, username: str)-> tuple[str, str]:
        # 生成唯一文件名（替换掉固定的 self.output_path）
        content_hash = hashlib.md5(f"{username}:{text}".encode()).hexdigest()[:6]
        timestamp = int(time.time() * 1000)
        unique_filename = f"bubble_{timestamp}_{content_hash}.png"
        # 1. 创建透明画布 (宽度固定600，高度自适应)
        max_width = self.max_width
        font_size = self.font_size
        output_path = os.path.join(self.base_dir, unique_filename)
        self.item_name = unique_filename
        self.output_path = output_path

        try:
            # 找一个支持中文的字体，如果没有则用默认
            font = ImageFont.truetype(self.font_type, font_size)  # Windows黑体
        except:
            font = ImageFont.load_default()

        # 2. 先计算文字尺寸，决定画布高度
        dummy_img = Image.new("RGBA", (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        # 用户名 + 冒号 + 内容
        full_text = f"{username}：{text}"
        # 获取文本边界
        bbox = dummy_draw.textbbox((0, 0), full_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 加上内边距 (左右30，上下20)
        padding_x = 30
        padding_y = 20
        img_width = min(max_width, text_width + padding_x * 2)
        img_height = text_height + padding_y * 2
        
        # 3. 创建最终透明画布并绘制圆角矩形
        img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制半透明白色气泡背景 (圆角矩形)
        radius = 20  # 圆角半径
        draw.rounded_rectangle(
            [(0, 0), (img_width, img_height)],
            radius=radius,
            fill=(255, 255, 255, 220),  # 白色半透明
            outline=(200, 200, 200, 255), # 浅灰边框
            width=2
        )
        
        # 绘制文字 (黑色)
        draw.text(
            (padding_x, padding_y), 
            full_text, 
            font=font, 
            fill=(0, 0, 0, 255)
        )
        
        # 4. 保存为PNG
        img.save(output_path, "PNG")
        return unique_filename, output_path
