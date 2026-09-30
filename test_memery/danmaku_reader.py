# danmaku_reader.py
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DmType(Enum):
    ENTER = "enter"
    NORMAL = "normal"
    GIFT = "gift"
    SC = "sc"
    FOLLOW = "follow"
    SYSTEM = "system"


@dataclass
class Danmaku:
    offset: float
    username: str
    dtype: DmType
    content: str
    amount: str = ""


class DanmakuReader:
    def __init__(self, path: str, speed: float = 1.0):
        self.speed = speed
        self.items: list[Danmaku] = []
        self.long_wait_time = 15.0
        self.is_long_wait = False
        self.current_index = 0
        self._parse(path)
        self.t0 = time.perf_counter()

    def _parse(self, path: str):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                continue
            offset = float(parts[0])
            username = parts[1]
            dtype_str = parts[2].lower()
            content = parts[3] if len(parts) > 3 else ""
            amount = ""
            if dtype_str == "sc" and len(parts) >= 5:
                amount, content = parts[3], parts[4]
            try:
                dtype = DmType(dtype_str)
            except ValueError:
                dtype = DmType.NORMAL
            self.items.append(Danmaku(offset, username, dtype, content, amount))
        self.items.sort(key=lambda d: d.offset)

    async def stream(self):
        """按时间偏移异步逐条产出"""
        t0 = time.perf_counter()
        for dm in self.items:
            target = dm.offset / self.speed
            wait = target - (time.perf_counter() - t0)
            # 等待弹幕时间间隔（超过long_wait_time秒应该主动说话）
            if wait > 0 and wait < self.long_wait_time:
                await asyncio.sleep(wait)
                self.is_long_wait = False
            elif wait >= self.long_wait_time:
                self.is_long_wait = True
                await asyncio.sleep(wait)
            yield dm

    async def get_next_danmaku(self):
        """获取下一条弹幕（如果未到时间则等待，但如果等待时间超过阈值，返回 None 表示需要主动发言）"""
        if self.current_index >= len(self.items):
            return None, True  # 没有更多弹幕，可以主动发言
        dm = self.items[self.current_index]
        target_time = dm.offset / self.speed
        current_time = time.perf_counter() - self.t0
        
        # 如果还没到时间
        if current_time < target_time:
            remaining = target_time - current_time
            
            # 如果剩余时间超过 long_wait_time，立即返回 None 表示可以主动发言
            if remaining > self.long_wait_time:
                return None, True
            
            # 等待剩余时间
            await asyncio.sleep(remaining)
        
        # 时间到了，返回弹幕
        self.current_index += 1
        return dm, False

    async def wait_for_danmaku_or_proactive(self):
        """等待弹幕或主动发言时机"""
        while True:
            # 获取下一条弹幕
            dm, should_proactive = await self.get_next_danmaku()
            
            if dm:
                # 有弹幕，返回
                return dm
            elif should_proactive:
                # 需要主动发言，返回 None
                return None
