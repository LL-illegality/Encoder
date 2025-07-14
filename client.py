import socket
import threading
import json
import time
import pygame
import sys
import math
import random

# 导入按键配置模块
from keybindings import load_keybindings, get_key_name

class GameClient:
    def __init__(self, host='localhost', port=5555, username=None, screen_width=800, screen_height=600):
        # 初始化游戏客户端
        self.host = host
        self.port = port
        self.username = username or f"Player_{int(time.time()) % 1000}"
        self.client_socket = None
        self.client_id = None
        self.game_state = None
        self.running = False
        self.connected = False
        self.message_callback = None
        self.receive_thread = None
        
        # 其他玩家位置插值系统
        self.player_positions = {}  # {player_id: {"current": [x, y], "target": [x, y], "last_update": timestamp}}
        
        # 角色字符串颜色
        self.prefix_color = (86, 156, 214)  # 前缀(0x, 0b)的颜色
        self.number_color = (181, 206, 168)  # 数字部分的颜色

        # 当前显示进制状态 (默认为16进制)
        self.display_base = 16  # 可以是2(二进制), 10(十进制), 16(十六进制)
        self.player_value = 0  # 玩家的值(整数)，用于进制转换
        
        # 动画效果相关
        self.animations = []  # 存储进制转换动画
        self.particles = []   # 存储粒子效果
        self.bullets = []  # 存储子弹对象
        self.interpolated_bullets = []  # 存储插值后的子弹状态
        
        # Pygame相关属性
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.screen = None
        self.clock = None
        self.font = None
        self.player_color = (0, 255, 0)  # 玩家颜色为绿色
        
        # 技能长按状态跟踪
        self.skill_key_pressed = None  # 当前按下的技能键
        self.skill_press_time = 0      # 技能键按下的时间
        self.target_player_id = None   # 目标玩家ID
        self.skill_range = 0           # 当前选择技能的范围
        # 加载按键配置
        self.keybindings = load_keybindings()
        
        # 逻辑运算技能按钮
        self.skills = [
            {"name": "AND", "symbol": "&", "description": "按位与运算", "color": (100, 200, 255), "key": self.keybindings["skill_1"]},
            {"name": "OR", "symbol": "|", "description": "按位或运算", "color": (255, 150, 100), "key": self.keybindings["skill_2"]},
            {"name": "NOT", "symbol": "~", "description": "按位非运算", "color": (200, 100, 255), "key": self.keybindings["skill_3"]},
            {"name": "XOR", "symbol": "^", "description": "按位异或运算", "color": (150, 255, 100), "key": self.keybindings["skill_4"]}
        ]
        
        # 十六进制模式的技能将在后面定义

        # 初始化标记位置为None
        self.marked_position = None
        self.skill_button_size = 70  # 技能按钮大小
        self.skill_button_margin = 10  # 技能按钮间距
        self.skill_hover_index = -1  # 当前鼠标悬停的技能索引
        self.other_players_color = (255, 0, 0)  # 其他玩家颜色为红色
        self.bg_color = (31, 31, 31)  # 背景颜色为深灰色
        self.move_speed = 15  # 玩家移动速度
        self.velocity_x = 0  # X轴速度
        self.velocity_y = 0  # Y轴速度
        self.acceleration = 0.3  # 加速度
        self.max_velocity = 15  # 最大速度
        self.friction = 0.95  # 摩擦力（减速）
        
        # 十六进制模式技能相关属性
        self.hex_skills = [
            {"name": "取址", "symbol": "&", "description": "标记当前位置", "color": (100, 150, 255), "key": self.keybindings["skill_1"]},
            {"name": "寻址", "symbol": "*", "description": "传送到标记的位置", "color": (150, 100, 255), "key": self.keybindings["skill_2"]}
        ]
        self.decimal_skills = [
            {"name": "赋值", "symbol": "=", "description": "为自己赋予随机值", "color": (255, 150, 100), "key": self.keybindings["skill_1"]},
            {"name": "开火", "symbol": "fire()", "description": "向前方发射能量", "color": (200, 100, 255), "key": self.keybindings["skill_2"]},
            {"name": "爆炸", "symbol": "*args", "description": "释放爆炸冲击波", "color": (255, 100, 100), "key": self.keybindings["skill_3"]},
            {"name": "内存释放", "symbol": "</>", "description": "释放内存并恢复能量", "color": (150, 255, 100), "key": self.keybindings["skill_4"]}
        ]
        self.memory_usage = 0  # 当前内存占用(0-255)
        self.max_memory = 255  # 最大内存占用
        self.marked_position = None  # 被标记的位置坐标
        self.teleporting = False  # 传送状态锁
        self.teleport_time = 0  # 传送开始时间
        self.teleport_cooldown = 0.5  # 传送后移动锁定时间(秒)
        self.memory_release_active = False  # 内存释放状态标志
        self.memory_release_start_time = 0  # 内存释放开始时间

        # 玩家碰撞箱大小
        self.player_size = 30  # 玩家碰撞箱大小 (正方形边长)

        # 摄像机平滑跟随
        self.camera_target_x = 0
        self.camera_target_y = 0
        self.camera_smoothness = 0.1  # 摄像机跟随平滑度(0-1)，值越小跟随越慢
        
        # 地图设置
        self.map_width = 2000  # 地图总宽度
        self.map_height = 1500  # 地图总高度
        
        # 摄像机设置
        self.camera_offset_x = 0  # 摄像机X偏移
        self.camera_offset_y = 0  # 摄像机Y偏移
        
        # 技能冷却时间管理
        self.cooldowns = {
            # 二进制模式技能冷却时间
            "AND": 0.5,  # 与操作 0.5秒冷却
            "OR": 0.5,   # 或操作 0.5秒冷却
            "NOT": 2.0,  # 非操作 2秒冷却
            "XOR": 0.5,  # 异或操作 0.5秒冷却

            # 十进制模式技能冷却时间
            "赋值": 10.0,   # 赋值技能 10秒冷却
            "开火": 2.0,    # 开火技能 2秒冷却
            "爆炸": 20.0,   # 爆炸技能 20秒冷却
            "内存释放": 10.0, # 内存释放技能 10秒冷却

            # 十六进制模式技能冷却时间
            "取址": 1.0,    # 取址技能 1秒冷却
            "寻址": 30.0    # 寻址技能 30秒冷却
        }

        # 上次使用技能的时间记录
        self.last_skill_use = {
            "AND": 0,
            "OR": 0,
            "NOT": 0,
            "XOR": 0,
            "赋值": 0,
            "开火": 0,
            "爆炸": 0,
            "内存释放": 0,
            "取址": 0,
            "寻址": 0
        }

    def init_pygame(self):
        # 初始化Pygame界面
        pygame.init()
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption(f"Encoder - {self.username}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Microsoft YaHei", 24)  # 默认字体，大小24
        self.char_font = pygame.font.SysFont("Consolas", 40)  # 改为Consolas字体
        self.username_font = pygame.font.SysFont("Microsoft YaHei", 16)  # 用户名字体缩小
        self.value_font = pygame.font.SysFont("Consolas", 28)  # 数值显示字体

    def connect(self):
        # 连接到游戏服务器
        try:
            # 初始化网络连接
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            self.running = True

            # 发送连接消息
            connect_message = {
                "type": "connect",
                "username": self.username
            }
            self._send_message(connect_message)

            # 启动接收消息线程
            self.receive_thread = threading.Thread(target=self._receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            
            # 初始化Pygame
            self.init_pygame()

            return True
        except Exception as e:
            print(f"连接服务器时出错: {e}")
            return False

    def disconnect(self):
        # 断开与服务器的连接
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        self.connected = False
        print("已断开与服务器的连接")
        pygame.quit()
    
    def _check_player_collision(self, x1, y1, x2, y2):
        """
        检查两个玩家位置之间是否发生碰撞
        x1, y1: 第一个玩家的位置
        x2, y2: 第二个玩家的位置
        返回: 如果碰撞返回True，否则返回False
        """
        # 使用玩家的碰撞箱大小计算碰撞
        return (abs(x1 - x2) < self.player_size and 
                abs(y1 - y2) < self.player_size)
                
    def _find_nearest_target_in_range(self, max_range):
        # 查找射程范围内最近的目标
        if not self.game_state or not self.client_id or self.client_id not in self.game_state.get("players", {}):
            return None
        
        # 获取当前玩家位置
        player_pos = self.game_state["players"][self.client_id]["position"]
        
        nearest_player = None
        min_distance = float('inf')
        
        # 查找最近的玩家
        for other_id, other_player in self.game_state["players"].items():
            if other_id != self.client_id:
                other_pos = other_player["position"]
                # 计算距离
                distance = math.sqrt(max(0, (player_pos[0] - other_pos[0]) ** 2 + (player_pos[1] - other_pos[1]) ** 2))
                if distance <= max_range and distance < min_distance:
                    min_distance = distance
                    nearest_player = other_id
        
        return nearest_player

    def _draw_target_frame(self, target_id):
        # 绘制目标红框
        if not self.game_state or "players" not in self.game_state or target_id not in self.game_state["players"]:
            return
        
        # 获取目标玩家位置
        target_pos = self.game_state["players"][target_id]["position"]
        
        # 计算屏幕坐标
        screen_x = target_pos[0] - self.camera_offset_x
        screen_y = target_pos[1] - self.camera_offset_y
        
        # 如果目标在屏幕内才绘制
        if 0 <= screen_x < self.screen_width and 0 <= screen_y < self.screen_height:
            # 设置红框大小和颜色
            frame_size = 60
            frame_color = (255, 0, 0)  # 红色
            frame_width = 3  # 线宽
            
            # 绘制目标框
            frame_rect = pygame.Rect(
                screen_x - frame_size // 2,
                screen_y - frame_size // 2,
                frame_size,
                frame_size
            )
            pygame.draw.rect(self.screen, frame_color, frame_rect, frame_width)
    def _handle_events(self):
        """处理所有输入事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            # 如果内存释放状态活跃，任何按键或鼠标操作都会取消它
            if self.memory_release_active:
                # 检查有没有按键或鼠标操作
                if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN]:
                    # 计算已释放的内存
                    current_time = time.time()
                    elapsed_time = current_time - self.memory_release_start_time
                    # 内存释放技能持续时间（秒）
                    release_duration = 10.0

                    # 如果仍在释放时间内
                    if elapsed_time < release_duration:
                        # 计算基于时间的进度比例
                        progress_ratio = elapsed_time / release_duration
                        # 计算当前应该的内存值 = 初始值 - (初始值 * 进度比例)
                        target_memory = self.initial_memory * (1 - progress_ratio)
                        # 平滑过渡到目标值
                        self.memory_usage = int(max(0, target_memory))
                        update_message = {
                            "type": "player_update",
                            "value": self.player_value,
                            "memory_usage": self.memory_usage,
                            "memory_release_active": False
                        }
                        self._send_message(update_message)
                    self.memory_release_active = False

            # 处理按键事件
            if event.type == pygame.KEYDOWN:
                # 检查是否按下ESC键取消技能
                if event.key == self.keybindings["cancel_skill"]:
                    if self.skill_key_pressed:
                        self.skill_key_pressed = None
                        self.target_player_id = None
                        self.skill_range = 0
                        print("技能释放已取消")
                    continue

                # 使用配置的技能快捷键
                # 二进制模式技能
                if self.display_base == 2:
                    if event.key == self.keybindings["skill_1"]:
                        self.skill_key_pressed = event.key
                        self.skill_range = 200
                        # 初次按下时找最近目标
                        self.target_player_id = self._find_nearest_target_in_range(200)
                    elif event.key == self.keybindings["skill_2"]:
                        self.skill_key_pressed = event.key
                        self.skill_range = 200
                        # 初次按下时找最近目标
                        self.target_player_id = self._find_nearest_target_in_range(200)
                    elif event.key == self.keybindings["skill_3"]:
                        # NOT技能不需要目标直接使用
                        self.use_skill(2)
                    elif event.key == self.keybindings["skill_4"]:
                        self.skill_key_pressed = event.key
                        self.skill_range = 200
                        # 初次按下时找最近目标
                        self.target_player_id = self._find_nearest_target_in_range(200)

                # 十六进制模式技能
                elif self.display_base == 16:
                    if event.key == self.keybindings["skill_1"]:
                        # 取址技能直接使用
                        self.use_hex_skill(0)
                    elif event.key == self.keybindings["skill_2"]:
                        # 寻址技能直接使用
                        self.use_hex_skill(1)

                # 十进制模式技能
                elif self.display_base == 10:
                    if event.key == self.keybindings["skill_1"]:
                        # 赋值技能不需要目标
                        self.use_decimal_skill(0)
                    elif event.key == self.keybindings["skill_2"]:
                        # 开火技能需要目标
                        self.skill_key_pressed = event.key
                        self.skill_range = 600
                        # 初次按下时找最近目标
                        self.target_player_id = self._find_nearest_target_in_range(600)
                    elif event.key == self.keybindings["skill_3"]:
                        # 爆炸技能需要目标
                        self.skill_key_pressed = event.key
                        self.skill_range = 600
                        # 初次按下时找最近目标
                        self.target_player_id = self._find_nearest_target_in_range(600)
                    elif event.key == self.keybindings["skill_4"]:
                        # 内存释放技能不需要目标
                        self.use_decimal_skill(3)

                # 模式切换
                if event.key == self.keybindings["decimal_mode"]:
                    self.display_base = 10
                    self._send_base_change(10)
                elif event.key == self.keybindings["binary_mode"]:
                    self.display_base = 2
                    self._send_base_change(2)
                elif event.key == self.keybindings["hex_mode"]:
                    self.display_base = 16
                    self._send_base_change(16)

            # 处理技能键松开事件
            elif event.type == pygame.KEYUP:
                if self.skill_key_pressed and event.key == self.skill_key_pressed:
                    # 根据当前按下的技能键释放对应技能
                    if self.display_base == 2:
                        if event.key == self.keybindings["skill_1"]:
                            self.use_skill(0)
                        elif event.key == self.keybindings["skill_2"]:
                            self.use_skill(1)
                        elif event.key == self.keybindings["skill_4"]:
                            self.use_skill(3)
                    elif self.display_base == 10:
                        if event.key == self.keybindings["skill_2"]:
                            self.use_decimal_skill(1)
                        elif event.key == self.keybindings["skill_3"]:
                            self.use_decimal_skill(2)

                    # 重置技能状态
                    self.skill_key_pressed = None
                    self.target_player_id = None
                    self.skill_range = 0

            # 处理鼠标点击
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键点击
                    mouse_pos = pygame.mouse.get_pos()
                    # 检查是否点击了技能按钮
                    if self.display_base == 2:
                        button_y = self.screen_height - self.skill_button_size - 10
                        for i, skill in enumerate(self.skills):
                            total_width = (self.skill_button_size + self.skill_button_margin) * len(self.skills) - self.skill_button_margin
                            start_x = (self.screen_width - total_width) // 2
                            button_x = start_x + (self.skill_button_size + self.skill_button_margin) * i
                            button_rect = pygame.Rect(button_x, button_y, self.skill_button_size, self.skill_button_size)

                            if button_rect.collidepoint(mouse_pos):
                                # 针对需要目标的技能先找最近目标
                                if i != 2:  # NOT技能不需要目标
                                    self.target_player_id = self._find_nearest_target_in_range(200)
                                self.use_skill(i)
                                break

                    elif self.display_base == 10:
                        button_y = self.screen_height - self.skill_button_size - 10
                        for i, skill in enumerate(self.decimal_skills):
                            total_width = (self.skill_button_size + self.skill_button_margin) * len(self.decimal_skills) - self.skill_button_margin
                            start_x = (self.screen_width - total_width) // 2
                            button_x = start_x + (self.skill_button_size + self.skill_button_margin) * i
                            button_rect = pygame.Rect(button_x, button_y, self.skill_button_size, self.skill_button_size)

                            if button_rect.collidepoint(mouse_pos):
                                skill_range = 600 if i in [1, 2] else 200
                                # 针对需要目标的技能先找最近目标
                                if i in [1, 2]:  # 只有开火和爆炸技能需要目标
                                    self.target_player_id = self._find_nearest_target_in_range(skill_range)
                                self.use_decimal_skill(i)
                                break
                    # 检查是否点击了十六进制模式的技能按钮
                    elif self.display_base == 16:
                        button_y = self.screen_height - self.skill_button_size - 10
                        for i, skill in enumerate(self.hex_skills):
                            total_width = (self.skill_button_size + self.skill_button_margin) * len(self.hex_skills) - self.skill_button_margin
                            start_x = (self.screen_width - total_width) // 2
                            button_x = start_x + (self.skill_button_size + self.skill_button_margin) * i
                            button_rect = pygame.Rect(button_x, button_y, self.skill_button_size, self.skill_button_size)

                            if button_rect.collidepoint(mouse_pos):
                                self.use_hex_skill(i)
                                break
    def run_game(self):
        # 运行游戏主循环
        if not self.connected:
            print("未连接到服务器，无法运行游戏")
            return
            
        try:
            while self.running:
                # 处理事件
                self._handle_events()
                
                # 处理键盘输入
                keys = pygame.key.get_pressed()
                dx = 0
                dy = 0

                if keys[pygame.K_w] or keys[pygame.K_UP]:
                    dy = -self.move_speed
                if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                    dy = self.move_speed
                if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                    dx = -self.move_speed
                if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                    dx = self.move_speed

                self._move_player(dx, dy)
                
                # 更新目标玩家（如果有正在按下的技能键）
                if self.skill_key_pressed and self.skill_range > 0:
                    self.target_player_id = self._find_nearest_target_in_range(self.skill_range)
                
                # 更新屏幕
                self._draw_game()
                
                # 处理内存释放状态
                if self.memory_release_active and self.memory_usage > 0:
                    current_time = time.time()
                    elapsed_time = current_time - self.memory_release_start_time
                    # 内存释放技能持续时间（秒）
                    release_duration = 10.0  # 5秒完成释放
                    
                    # 如果仍在释放时间内
                    if elapsed_time < release_duration:
                        # 计算基于时间的进度比例
                        progress_ratio = elapsed_time / release_duration
                        # 计算当前应该的内存值 = 初始值 - (初始值 * 进度比例)
                        target_memory = self.initial_memory * (1 - progress_ratio)
                        # 平滑过渡到目标值
                        self.memory_usage = int(max(0, target_memory))

                        # 在玩家周围生成绿色粒子和随机白色数字
                        # if self.game_state and self.client_id in self.game_state.get("players", {}):
                        #     player_pos = self.game_state["players"][self.client_id]["position"]
                        #     # 每帧添加2-3个粒子
                        #     for _ in range(random.randint(2, 3)):
                        #         self._add_memory_release_particle(player_pos[0], player_pos[1])

                        # 每隔一小段时间向服务器发送内存使用量更新
                        # 使用当前时间的小数部分来控制发送频率，大约每0.2秒发送一次
                        if (current_time * 5) % 1 < 0.1:  # 0.1/5 = 0.02秒的窗口，约等于每0.2秒发送一次
                            update_message = {
                                "type": "player_update",
                                "value": self.player_value,  # 保持当前player_value不变
                                "memory_usage": self.memory_usage,
                                "memory_release_active": True
                            }
                            self._send_message(update_message)
                    else:
                        # 释放时间结束，完全释放内存
                        self.memory_usage = 0
                        self.memory_release_active = False
                        print("内存释放完成")
                        
                        # 向服务器发送更新，同步内存释放状态
                        update_message = {
                            "type": "player_update",
                            "value": self.player_value,  # 保持当前player_value不变
                            "memory_usage": self.memory_usage,
                            "memory_release_active": False
                        }
                        self._send_message(update_message)
                
                # 控制帧率
                self.clock.tick(60)
        except Exception as e:
            print(f"游戏运行时出错: {e}")
        finally:
            self.disconnect()
    
    def _move_player(self, dx, dy):
        # 移动玩家位置
        if not self.game_state or not self.client_id:
            return

        # 确保玩家ID在游戏状态中
        if self.client_id not in self.game_state.get("players", {}):
            print(f"玩家ID {self.client_id} 不在游戏状态中")
            return
            
        # 检查是否在传送锁定状态
        if self.teleporting:
            # 检查是否已经过了冷却时间
            if time.time() - self.teleport_time > self.teleport_cooldown:
                self.teleporting = False
                print("传送锁定结束，允许移动")
            else:
                # 在传送锁定期间不允许移动
                return

        # 应用加速度
        if dx != 0:
            self.velocity_x += dx * self.acceleration
        if dy != 0:
            self.velocity_y += dy * self.acceleration

        # 限制最大速度
        if abs(self.velocity_x) > self.max_velocity:
            self.velocity_x = self.max_velocity if self.velocity_x > 0 else -self.max_velocity
        if abs(self.velocity_y) > self.max_velocity:
            self.velocity_y = self.max_velocity if self.velocity_y > 0 else -self.max_velocity

        # 应用摩擦力（当没有输入时）
        if dx == 0:
            self.velocity_x *= self.friction
        else:
            # 当有输入时，设置初始速度以避免累积效应
            self.velocity_x = dx * self.acceleration

        if dy == 0:
            self.velocity_y *= self.friction
        else:
            # 当有输入时，设置初始速度以避免累积效应
            self.velocity_y = dy * self.acceleration

        # 如果速度很小，则设为0（避免微小移动）
        if abs(self.velocity_x) < 0.05:
            self.velocity_x = 0
        if abs(self.velocity_y) < 0.05:
            self.velocity_y = 0

        current_pos = self.game_state["players"][self.client_id]["position"]
        new_x = current_pos[0] + self.velocity_x
        new_y = current_pos[1] + self.velocity_y

        # 检查是否碰到地图边界，如果是则应用反弹效果
        boundary_collision = False
        
        # 保存原始位置用于检测碰撞
        orig_x, orig_y = new_x, new_y
        
        # 边界限制
        new_x = max(30 + self.player_size, min(self.map_width - self.player_size - 30, new_x))
        new_y = max(30 + self.player_size, min(self.map_height - self.player_size - 30, new_y))

        # 检测与其他玩家的碰撞
        collision_detected = False
        for other_id, other_player in self.game_state["players"].items():
            if other_id != self.client_id:
                other_pos = other_player["position"]
                # 检测是否会与其他玩家碰撞
                if self._check_player_collision(new_x, new_y, other_pos[0], other_pos[1]):
                    collision_detected = True
                    # 计算碰撞后的反弹方向
                    dx = new_x - other_pos[0]
                    dy = new_y - other_pos[1]
                    # 避免dx和dy都为0的情况
                    if dx == 0 and dy == 0:
                        dx = random.uniform(-1, 1)
                        dy = random.uniform(-1, 1)
                    # 归一化方向向量
                    length = math.sqrt(max(0, dx * dx + dy * dy))
                    if length > 0:
                        dx /= length
                        dy /= length
                    # 设置碰撞反弹速度
                    bounce_factor = 3.0
                    self.velocity_x = dx * bounce_factor
                    self.velocity_y = dy * bounce_factor
                    # 重新计算位置，稍微远离碰撞点
                    new_x = current_pos[0] + self.velocity_x
                    new_y = current_pos[1] + self.velocity_y
                    break

        # 如果检测到玩家之间的碰撞，再次确保不会移出地图边界
        if collision_detected:
            new_x = max(30, min(self.map_width - self.player_size - 30, new_x))
            new_y = max(30, min(self.map_height - self.player_size - 30, new_y))
        # 只有位置确实改变时才发送更新
        if new_x != current_pos[0] or new_y != current_pos[1]:
            # 更新本地状态
            self.game_state["players"][self.client_id]["position"] = [new_x, new_y]

            # 发送位置更新到服务器
            self.send_move([new_x, new_y])
    
    def _update_player_positions(self):
        # 更新其他玩家的位置插值
        current_time = time.time()
        for player_id, pos_data in self.player_positions.items():
            if player_id in self.game_state.get("players", {}):
                # 计算过渡进度 (根据时间差异和最大过渡时间)
                elapsed = current_time - pos_data["last_update"]
                max_transition_time = 0.2  # 200毫秒内完成过渡
                progress = min(1.0, elapsed / max_transition_time)
                
                # 使用缓动函数使移动更自然
                # 使用easeOutQuad缓动: progress = 1 - (1 - progress) * (1 - progress)
                eased_progress = 1 - (1 - progress) * (1 - progress)
                
                # 使用线性插值平滑移动
                current_x = pos_data["current"][0]
                current_y = pos_data["current"][1]
                target_x = pos_data["target"][0]
                target_y = pos_data["target"][1]
                
                # 计算新的当前位置
                new_x = current_x + (target_x - current_x) * eased_progress
                new_y = current_y + (target_y - current_y) * eased_progress
                
                # 更新当前位置
                pos_data["current"] = [new_x, new_y]
                
                # 如果已经足够接近目标位置，则直接设置为目标位置
                if progress >= 0.98:
                    pos_data["current"] = pos_data["target"].copy()
                
                # 更新游戏状态中的位置以便绘制
                self.game_state["players"][player_id]["position"] = pos_data["current"].copy()
    
    def _update_camera(self):
        # 更新摄像机位置，使当前玩家居中，带有平滑跟随效果
        if not self.game_state or not self.client_id or self.client_id not in self.game_state.get("players", {}):
            return

        # 获取当前玩家位置
        player_pos = self.game_state["players"][self.client_id]["position"]

        # 计算目标摄像机位置，使玩家位于屏幕中央
        self.camera_target_x = player_pos[0] - (self.screen_width // 2)
        self.camera_target_y = player_pos[1] - (self.screen_height // 2)

        # 平滑过渡到目标位置
        self.camera_offset_x += (self.camera_target_x - self.camera_offset_x) * self.camera_smoothness
        self.camera_offset_y += (self.camera_target_y - self.camera_offset_y) * self.camera_smoothness

        # 确保摄像机不会超出地图边界
        self.camera_offset_x = max(0, min(self.map_width - self.screen_width, self.camera_offset_x))
        self.camera_offset_y = max(0, min(self.map_height - self.screen_height, self.camera_offset_y))

        # 转换为整数，避免绘制时的类型错误
        self.camera_offset_x = int(self.camera_offset_x)
        self.camera_offset_y = int(self.camera_offset_y)

    def _draw_map_boundaries(self):
        # 绘制地图边界
        # 计算可见区域的边界
        border_color = (100, 100, 100)  # 灰色边界

        # 左边界
        if self.camera_offset_x == 0:
            pygame.draw.line(self.screen, border_color, (0, 0), (0, self.screen_height), 30)

        # 右边界
        if self.camera_offset_x + self.screen_width >= self.map_width:
            right_edge = self.map_width - self.camera_offset_x
            pygame.draw.line(self.screen, border_color, (right_edge, 0), (right_edge, self.screen_height), 30)

        # 上边界
        if self.camera_offset_y == 0:
            pygame.draw.line(self.screen, border_color, (0, 0), (self.screen_width, 0), 30)

        # 下边界
        if self.camera_offset_y + self.screen_height >= self.map_height:
            bottom_edge = self.map_height - self.camera_offset_y
            pygame.draw.line(self.screen, border_color, (0, bottom_edge), (self.screen_width, bottom_edge), 30)

    def _draw_grid(self):
        # 绘制地图网格线
        grid_color = (111, 118, 128)  # 网格线颜色
        grid_spacing = 50  # 网格线间距

        # 计算起始点和结束点（考虑摄像机偏移）
        start_x = (grid_spacing - (self.camera_offset_x % grid_spacing)) % grid_spacing
        start_y = (grid_spacing - (self.camera_offset_y % grid_spacing)) % grid_spacing

        # 绘制垂直线
        for x in range(start_x, self.screen_width, grid_spacing):
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, self.screen_height), 1)

        # 绘制水平线
        for y in range(start_y, self.screen_height, grid_spacing):
            pygame.draw.line(self.screen, grid_color, (0, y), (self.screen_width, y), 1)

    def _draw_info(self):
        # 绘制坐标信息和游戏状态
        if not self.game_state or not self.client_id or self.client_id not in self.game_state.get("players", {}):
            return

        # 获取当前玩家位置
        player_pos = self.game_state["players"][self.client_id]["position"]

        # 显示坐标信息
        position_text = f"位置: ({player_pos[0]}, {player_pos[1]})"
        pos_surface = self.font.render(position_text, True, (255, 255, 255))
        self.screen.blit(pos_surface, (10, 10))

        # 显示地图信息
        map_text = f"地图: {self.map_width}x{self.map_height}"
        map_surface = self.font.render(map_text, True, (255, 255, 255))
        self.screen.blit(map_surface, (10, 40))
    def _draw_game(self):
            # 绘制游戏画面
            # 清空屏幕
            self.screen.fill(self.bg_color)

            # 如果游戏状态不存在，则不绘制
            if not self.game_state or "players" not in self.game_state:
                pygame.display.flip()
                return
                
            # 更新其他玩家的位置插值
            self._update_player_positions()

            # 更新子弹位置
            self._update_bullets()

            # 更新摄像机位置
            self._update_camera()

            # 绘制网格线
            self._draw_grid()

            # 绘制地图边界
            self._draw_map_boundaries()
            
            # 绘制粒子效果
            self._draw_particles()
            # 渲染子弹
            self._render_bullets()

            # 绘制所有玩家
            for player_id, player_data in self.game_state["players"].items():
                # 获取玩家位置和名称
                position = player_data.get("position", [0, 0])
                username = player_data.get("username", "Unknown")

                # 计算屏幕上的位置（应用摄像机偏移）
                screen_x = position[0] - self.camera_offset_x
                screen_y = position[1] - self.camera_offset_y

                # 如果玩家在视野内才绘制
                if 0 <= screen_x < self.screen_width and 0 <= screen_y < self.screen_height:
                    # 决定使用的颜色 - 自己是绿色，其他玩家是红色
                    color = self.player_color if str(player_id) == str(self.client_id) else self.other_players_color

                    # 使用_draw_player方法绘制玩家
                    self._draw_player(player_id, screen_x, screen_y, player_data.get("value", 0), username, color)

            # 如果长按技能键，检测范围内最近目标
            if self.skill_key_pressed:
                self.target_player_id = self._find_nearest_target_in_range(self.skill_range)
                
            # 如果有目标玩家，绘制红框
            if self.target_player_id:
                self._draw_target_frame(self.target_player_id)

            # 绘制信息
            self._draw_info()
            
            # 在所有进制模式下都绘制内存占用进度条
            self._draw_memory_bar()

            # 根据不同模式绘制对应的技能按钮
            if self.display_base == 2:
                self._draw_skill_buttons()
            elif self.display_base == 16:
                self._draw_hex_skill_buttons()
            elif self.display_base == 10:
                self._draw_decimal_skill_buttons()
                
            # 如果有标记的位置，绘制箭头
            if self.marked_position:
                self._draw_position_arrow()
            
            # 更新显示
            pygame.display.flip()
            
    def _update_bullets(self):
        """更新子弹插值状态"""
        if not self.game_state or "bullets" not in self.game_state:
            return
            
        current_time = time.time()
        # 适应服务器的30FPS更新频率
        server_delta_time = 1/30  # 服务器帧率 
        client_delta_time = 1/60  # 客户端帧率
        
        # 创建子弹ID到子弹对象的映射，以优化查找效率
        bullet_map = {bullet.get("id", id(bullet)): bullet for bullet in self.game_state["bullets"]}
        
        # 以下是原有的插值逻辑，先处理插值，再进行物理更新
        new_bullet_ids = set(bullet_map.keys())
        
        # 更新现有子弹的插值状态
        updated_bullets = []
        for bullet_data in self.interpolated_bullets:
            bullet_id = bullet_data["id"]
            
            if bullet_id in new_bullet_ids:
                # 直接从映射中获取子弹，提高效率
                new_bullet = bullet_map[bullet_id]
                
                # 获取服务器发送的位置和本地当前位置
                server_position = new_bullet.get("position", [0, 0]).copy()
                current_position = bullet_data["current_position"].copy()
                
                # 计算位置偏差
                dx = server_position[0] - current_position[0]
                dy = server_position[1] - current_position[1]
                error_distance = math.sqrt(max(0, dx**2 + dy**2))
                
                # 如果偏差过大，直接使用服务器位置
                if error_distance > 20:
                    bullet_data["current_position"] = server_position.copy()
                    bullet_data["prev_position"] = server_position.copy()
                else:
                    # 保存上一个位置为当前位置
                    bullet_data["prev_position"] = bullet_data["current_position"].copy()
                
                # 设置目标位置为服务器位置
                bullet_data["target_position"] = server_position.copy()
                # 更新最后更新时间
                bullet_data["last_update"] = current_time
                # 更新子弹数据
                bullet_data["bullet_data"] = new_bullet
                # 保留子弹
                updated_bullets.append(bullet_data)
        
        # 添加新的子弹
        for bullet_id, new_bullet in bullet_map.items():
            # 检查是否已存在
            if not any(b["id"] == bullet_id for b in updated_bullets):
                position = new_bullet.get("position", [0, 0])
                # 确保新添加的子弹有created_time属性
                if "created_time" not in new_bullet:
                    new_bullet["created_time"] = current_time
                    
                updated_bullets.append({
                    "id": bullet_id,
                    "prev_position": position.copy(),
                    "current_position": position.copy(),
                    "target_position": position.copy(),
                    "last_update": current_time,
                    "bullet_data": new_bullet
                })
        
        self.interpolated_bullets = updated_bullets
        
        # 物理更新逻辑：更新子弹位置、检查边界和生命周期
        # 注意：服务器已经在更新位置，我们只需要在两次服务器更新之间进行平滑补间
        for bullet_data in self.interpolated_bullets:
            bullet = bullet_data["bullet_data"]
            velocity = bullet.get("velocity", [0, 0])
            
            # 改进的位置预测：使用更精确的速度积分和缓动函数
            elapsed_since_update = current_time - bullet_data["last_update"]
            
            # 只在合理的时间范围内应用预测，避免长时间无更新导致飘逸
            if elapsed_since_update < server_delta_time * 3:
                # 计算积分系数：使用平方根函数作为缓动，使运动更平滑
                # 这种插值方式在更新初期变化较快，接近目标时变化较慢
                time_factor = min(1.0, elapsed_since_update / (server_delta_time * 2))
                smoothed_factor = math.sqrt(max(0, time_factor))  # 平方根缓动
                
                # 根据速度向量长度动态调整预测程度
                speed = math.sqrt(max(0, velocity[0]**2 + velocity[1]**2))
                speed_factor = min(1.2, max(0.8, speed / 150))  # 速度归一化因子
                
                # 计算平滑预测位置
                predicted_x = bullet_data["current_position"][0] + velocity[0] * elapsed_since_update * speed_factor * smoothed_factor
                predicted_y = bullet_data["current_position"][1] + velocity[1] * elapsed_since_update * speed_factor * smoothed_factor
                
                # 设置预测位置为当前位置
                bullet_data["current_position"] = [predicted_x, predicted_y]
                
                # 保存最后预测时间，用于后续插值
                bullet_data["last_prediction_time"] = current_time
            
            # 确保每个子弹有created_time属性
            if "created_time" not in bullet:
                bullet["created_time"] = current_time
            
            # 更新子弹生命周期
            if "lifetime" in bullet:
                bullet["lifetime"] -= client_delta_time
        
        # 移除超出边界或生命周期结束的子弹
        self.interpolated_bullets = [
            bullet_data for bullet_data in self.interpolated_bullets 
            if (0 <= bullet_data["current_position"][0] <= self.map_width and
                0 <= bullet_data["current_position"][1] <= self.map_height and
                current_time - bullet_data["bullet_data"].get("created_time", current_time) <= 5.0)
        ]
    
    def _render_bullets(self):
        """渲染游戏中的所有子弹"""
        # 如果没有插值子弹数据，直接返回
        if not self.interpolated_bullets:
            return
            
        current_time = time.time()
        
        # 在渲染前使用亚帧插值技术平滑更新子弹位置
        if not hasattr(self, "last_render_time"):
            self.last_render_time = current_time
        render_delta = current_time - self.last_render_time
        self.last_render_time = current_time
        
        # 获取实际FPS，用于计算移动量
        fps_factor = min(1.0, max(0.1, render_delta * 60))  # 标准化到60FPS
        
        for bullet_data in self.interpolated_bullets:
            bullet = bullet_data["bullet_data"]
            velocity = bullet.get("velocity", [0, 0])
            
            # 计算插值系数
            elapsed = current_time - bullet_data["last_update"]
            
            # 子弹位置亚帧更新：在每一帧渲染时进行细分插值
            if "velocity" in bullet and (velocity[0] != 0 or velocity[1] != 0):
                # 计算速度大小，用于视觉平滑处理
                speed = math.sqrt(max(0, velocity[0]**2 + velocity[1]**2))
                
                # 使用基于速度的动态插值系数
                interp_factor = min(1.0, max(0.3, speed / 300)) * fps_factor
                
                # 使用当前渲染帧实际时间差计算位移增量
                dx = velocity[0] * render_delta * interp_factor
                dy = velocity[1] * render_delta * interp_factor
                
                # 应用亚帧位移
                current_pos = bullet_data["current_position"]
                current_pos[0] += dx
                current_pos[1] += dy
            
            # 获取子弹位置
            bullet_pos = bullet_data["current_position"]
            
            # 计算屏幕上的位置（应用摄像机偏移）
            screen_x = bullet_pos[0] - self.camera_offset_x
            screen_y = bullet_pos[1] - self.camera_offset_y
            
            # 扩大渲染区域，使进入屏幕的子弹过渡更自然
            render_margin = 50  # 扩大50像素的渲染范围
            if -render_margin <= screen_x < self.screen_width + render_margin and -render_margin <= screen_y < self.screen_height + render_margin:
                # 获取子弹颜色和大小
                bullet = bullet_data["bullet_data"]
                bullet_color = bullet.get("color", (212, 212, 212))  # 默认白色
                bullet_char = bullet.get("char", "*")  # 默认字符
                
                # 根据伤害值确定子弹大小
                bullet_damage = bullet.get("damage", 1)
                bullet_size = min(30, max(10, bullet_damage * 3))  # 大小范围在10-30之间
                
                # 创建子弹字体
                bullet_font = pygame.font.SysFont("Consolas", int(bullet_size), bold=True)
                
                # 渲染子弹
                bullet_surface = bullet_font.render(bullet_char, True, bullet_color)
                
                # 获取渲染后的矩形并居中定位
                bullet_rect = bullet_surface.get_rect(center=(screen_x, screen_y))
                
                # 绘制子弹
                self.screen.blit(bullet_surface, bullet_rect)
                
                # 增强的尾迹效果系统，基于子弹速度和渲染帧率动态调整
                # 获取子弹速度，用于确定尾迹生成概率和特性
                velocity = bullet.get("velocity", [0, 0])
                velocity_mag = math.sqrt(max(0, velocity[0]**2 + velocity[1]**2))
                
                # 动态尾迹生成频率：速度越快，尾迹越多
                trail_chance = min(0.8, max(0.3, velocity_mag / 200))
                
                # 基于实际FPS调整尾迹生成频率，保持视觉一致性
                if not hasattr(self, "frame_time_smoother"):
                    self.frame_time_smoother = 0.016  # 初始化为60FPS
                
                # 平滑帧时间（避免帧率波动导致尾迹突变）
                if hasattr(self, "last_render_time"):
                    actual_delta = current_time - self.last_render_time
                    self.frame_time_smoother = self.frame_time_smoother * 0.9 + actual_delta * 0.1
                
                # 根据实际帧率调整尾迹生成概率
                frame_adjust = min(2.0, max(0.5, 0.016 / max(0.001, self.frame_time_smoother)))
                trail_chance *= frame_adjust
                
                if random.random() < trail_chance:
                    # 速度越快，尾迹越长、越大
                    trail_scale = min(1.5, max(0.5, velocity_mag / 100))
                    trail_size = random.uniform(3, 8) * trail_scale
                    
                    # 计算尾迹偏移，确保尾迹在子弹后方
                    if velocity_mag > 0:
                        norm_x = -velocity[0] / velocity_mag
                        norm_y = -velocity[1] / velocity_mag
                    else:
                        norm_x, norm_y = 0, 0
                    
                    # 尾迹偏移量与速度成正比
                    offset_scale = min(15, max(5, velocity_mag / 20))
                    dx = norm_x * offset_scale * random.uniform(0.8, 1.2)
                    dy = norm_y * offset_scale * random.uniform(0.8, 1.2)
                    
                    # 添加小的随机性使尾迹更自然
                    dx += random.uniform(-2, 2)
                    dy += random.uniform(-2, 2)
                    
                    # 创建尾迹粒子
                    trail_particle = {
                        "x": bullet_pos[0] + dx,
                        "y": bullet_pos[1] + dy,
                        "dx": dx * 0.05,  # 减小尾迹自身的移动速度
                        "dy": dy * 0.05,
                        "size": trail_size,
                        "color": bullet_color,
                        "life": random.uniform(0.05, 0.2) * trail_scale,  # 更短的生命周期
                        "opacity": random.uniform(0.6, 1.0),  # 添加透明度变化
                        "start_time": current_time,
                        "type": "particle"
                    }
                    self.particles.append(trail_particle)

    def _draw_particles(self):
        # 绘制粒子效果
        current_time = time.time()
        active_particles = []
        
        # 处理所有粒子
        for particle in self.particles:
            # 计算粒子的生命周期
            age = current_time - particle["start_time"]
            if age < particle["life"]:
                # 粒子还活着，更新位置
                progress = age / particle["life"]
                alpha = 255 * (1 - progress)  # 逐渐变透明
                
                # 计算屏幕坐标
                screen_x = particle["x"] - self.camera_offset_x
                screen_y = particle["y"] - self.camera_offset_y
                
                # 如果在屏幕内，绘制粒子
                if 0 <= screen_x < self.screen_width and 0 <= screen_y < self.screen_height:
                    # 根据粒子类型绘制不同效果
                    if particle.get("type") == "wave":
                        # 绘制扩散波
                        # 计算当前半径
                        current_radius = particle["radius"] + particle["speed"] * age
                        if current_radius <= particle["max_radius"]:
                            # 波的透明度随半径增大而减小
                            wave_alpha = alpha #int(alpha * (1 - current_radius / particle["max_radius"]))
                            # 从particle["color"]获取RGB值并确保alpha在有效范围内
                            r, g, b = particle["color"]
                            safe_wave_alpha = max(0, min(255, int(wave_alpha)))
                            # 创建带有alpha通道的颜色
                            wave_color = (r, g, b, safe_wave_alpha)
                            pygame.draw.circle(self.screen, wave_color, (screen_x, screen_y), current_radius, 3)  # 3是线宽
                    elif particle.get("type") == "operator":
                        # 绘制运算符特效
                        # 根据生命周期调整大小和透明度
                        current_size = particle["initial_size"] * (1 + progress * 0.5)  # 逐渐变大
                        current_opacity = int(particle["initial_opacity"] * (1 - progress))  # 逐渐变透明

                        # 创建字体并渲染符号
                        symbol_font = pygame.font.SysFont("Microsoft YaHei", int(current_size), bold=True)
                        # 从particle["color"]获取RGB值并确保alpha在有效范围内
                        r, g, b = particle["color"]
                        safe_opacity = max(0, min(255, int(current_opacity)))
                        symbol_text = symbol_font.render(particle["symbol"], True, (r, g, b))
                        # 使用set_alpha单独设置透明度
                        symbol_text.set_alpha(safe_opacity)

                        # 将符号居中显示在粒子位置
                        symbol_rect = symbol_text.get_rect(center=(screen_x, screen_y))
                        self.screen.blit(symbol_text, symbol_rect)
                    elif particle.get("type") == "fire_text":
                        # 绘制开火技能特殊效果 - fire + ()
                        # 渲染"fire"
                        fire_font = pygame.font.SysFont("Consolas", int(particle["text_size"]), bold=True)
                        # 确保alpha在有效范围内并正确处理颜色参数
                        safe_alpha = max(0, min(255, int(alpha)))
                        fire_text = fire_font.render("fire", True, (220, 220, 170))
                        # 如果需要alpha效果，可以使用Surface的set_alpha方法
                        fire_text.set_alpha(safe_alpha)
                        fire_rect = fire_text.get_rect(center=(screen_x, screen_y))
                        self.screen.blit(fire_text, fire_rect)
                        
                        # 渲染括号
                        bracket_font = pygame.font.SysFont("Consolas", int(particle["bracket_size"]), bold=True)
                        # 确保alpha在有效范围内并正确处理括号颜色参数
                        safe_alpha = max(0, min(255, int(alpha)))
                        bracket = bracket_font.render("()", True, (212, 212, 212))
                        # 使用Surface的set_alpha方法应用透明度
                        bracket.set_alpha(safe_alpha)
                        
                        # 计算括号位置
                        bracket_rect = bracket.get_rect(left=fire_rect.right+3, centery=fire_rect.centery)
                        
                        # 绘制括号
                        self.screen.blit(bracket, bracket_rect)
                    elif particle.get("type") == "number":
                        # 绘制数字粒子（内存释放技能的数字）
                        number_font = pygame.font.SysFont("Consolas", int(particle["size"]), bold=True)
                        # 确保alpha在有效范围内
                        safe_alpha = max(0, min(255, int(alpha)))
                        # 渲染数字文本
                        number_text = number_font.render(particle["text"], True, particle["color"])
                        # 应用透明度
                        number_text.set_alpha(safe_alpha)
                        # 获取文本矩形并定位
                        number_rect = number_text.get_rect(center=(screen_x, screen_y))
                        # 绘制数字
                        self.screen.blit(number_text, number_rect)
                    else:
                        # 创建增强的标准粒子（主要用于子弹尾迹）
                        size = particle["size"]
                        # 增加模糊效果使尾迹更平滑
                        blur_size = int(size * 1.2)
                        blur_size = max(4, blur_size)  # 确保最小尺寸
                        
                        particle_surface = pygame.Surface((blur_size, blur_size), pygame.SRCALPHA)
                        
                        # 获取粒子颜色和透明度
                        r, g, b = particle["color"]
                        
                        # 使用粒子自带的透明度属性（如果有）
                        base_opacity = particle.get("opacity", 1.0)
                        # 随着生命周期减少透明度
                        age_factor = 1 - progress
                        # 计算最终透明度
                        final_alpha = int(255 * base_opacity * age_factor)
                        safe_alpha = max(0, min(255, final_alpha))
                        
                        # 创建带有alpha通道的颜色
                        particle_color = (r, g, b, safe_alpha)
                        center = (blur_size/2, blur_size/2)
                        
                        # 绘制带透明度的发光核心
                        pygame.draw.circle(particle_surface, particle_color, center, size/2)
                        
                        # 如果是尾迹粒子且有速度信息，绘制流线型尾迹
                        if "dx" in particle and "dy" in particle:
                            # 确保使用实数进行比较
                            dx_abs = abs(particle["dx"].real) if isinstance(particle["dx"], complex) else abs(particle["dx"])
                            dy_abs = abs(particle["dy"].real) if isinstance(particle["dy"], complex) else abs(particle["dy"])
                            total_movement = dx_abs + dy_abs  # 使用总移动量变量
                            if total_movement > 0.1:
                                # 计算运动方向的单位向量 - 确保使用实数
                                # 检查并转换可能的复数为实数
                                dx = particle["dx"].real if isinstance(particle["dx"], complex) else particle["dx"]
                                dy = particle["dy"].real if isinstance(particle["dy"], complex) else particle["dy"]
                                # 确保平方和为正数，避免复数
                                square_sum = max(0.01, dx**2 + dy**2)  # 保证平方和为正
                                mag = math.sqrt(square_sum)
                                norm_dx = -dx / mag  # 反向，尾迹在运动方向后方
                                norm_dy = -dy / mag
                            
                                # 尾迹长度随速度变化
                                # 确保mag是实数且为正值
                                safe_mag = abs(mag) if isinstance(mag, complex) else mag
                                trail_len = min(size, safe_mag * 2)
                            
                                # 尾迹起点和终点
                                start_x, start_y = center
                                # 确保使用实数计算
                                safe_norm_dx = norm_dx.real if isinstance(norm_dx, complex) else norm_dx
                                safe_norm_dy = norm_dy.real if isinstance(norm_dy, complex) else norm_dy
                                end_x = start_x + safe_norm_dx * trail_len
                                end_y = start_y + safe_norm_dy * trail_len
                            
                                # 尾迹颜色（半透明）
                                trail_alpha = max(0, min(128, int(safe_alpha * 0.7)))
                                trail_color = (r, g, b, trail_alpha)
                            
                                # 绘制渐变尾迹线条
                                # if trail_len > 1:
                                #     pygame.draw.line(particle_surface, trail_color, 
                                #                     (start_x, start_y), 
                                #                     (end_x, end_y), 
                                #                     max(1, int(size/3)))
                        
                        # 渲染到屏幕
                        self.screen.blit(particle_surface, (screen_x - blur_size/2, screen_y - blur_size/2))
                
                # 更新粒子位置 - 排除fire_text类型的粒子
                if particle.get("type") != "fire_text":
                    # 获取当前帧时间差，用于平滑移动
                    frame_time = 1/60
                    if hasattr(self, "frame_time_smoother"):
                        frame_time = self.frame_time_smoother
                    
                    # 计算移动衰减系数 - 确保不会产生负值或复数
                    safe_progress = min(1.0, max(0.0, progress))  # 限制progress在0.0-1.0之间
                    # 使用非线性衰减，但确保指数计算安全
                    power_val = 0.7
                    # 避免对负数进行非整数幂运算
                    decay_factor = safe_progress**power_val if safe_progress >= 0 else 0
                    decay = max(0, (1 - decay_factor))
                    
                    # 平滑运动系数
                    move_factor = frame_time * 60  # 标准化到60FPS
                    
                    # 应用平滑运动 - 确保使用实数值
                    # 检查粒子是否有dx和dy属性
                    if "dx" not in particle or "dy" not in particle:
                        continue  # 跳过没有速度属性的粒子
                    
                    # 检查并转换可能的复数为实数
                    dx = particle["dx"].real if isinstance(particle["dx"], complex) else particle["dx"]
                    dy = particle["dy"].real if isinstance(particle["dy"], complex) else particle["dy"]
                    particle["dx"] = dx  # 更新为实数
                    particle["dy"] = dy  # 更新为实数
                    # 确保所有计算都基于实数
                    movement_x = dx * decay * move_factor
                    movement_y = dy * decay * move_factor
                    # 检查计算结果是否为复数
                    if isinstance(movement_x, complex):
                        movement_x = movement_x.real
                    if isinstance(movement_y, complex):
                        movement_y = movement_y.real
                    particle["x"] += movement_x
                    particle["y"] += movement_y
                    
                    # 随着生命周期缩小粒子尺寸
                    if "size" in particle and particle["size"] > 2:
                        particle["size"] *= (1 - frame_time * 0.5)
                
                # 保持此粒子
                active_particles.append(particle)
        
        # 更新粒子列表
        self.particles = active_particles
    
    def _draw_position_arrow(self):
        if not self.marked_position or not self.client_id or self.client_id not in self.game_state.get("players", {}):
            return

        # 获取当前玩家位置
        current_position = self.game_state["players"][self.client_id]["position"]

        # 计算屏幕上的当前位置和标记位置
        current_screen_x = current_position[0] - self.camera_offset_x
        current_screen_y = current_position[1] - self.camera_offset_y

        marked_screen_x = self.marked_position[0] - self.camera_offset_x
        marked_screen_y = self.marked_position[1] - self.camera_offset_y

        # 计算方向向量
        dx = marked_screen_x - current_screen_x
        dy = marked_screen_y - current_screen_y

        # 计算向量长度
        length = math.sqrt(max(0, dx * dx + dy * dy))

        # 如果标记位置就是当前位置或太近，不需要绘制箭头
        if length < 10:
            return

        # 标准化向量
        dx /= length
        dy /= length

        # 设置箭头长度和宽度
        arrow_length = min(50, length * 0.5)  # 不超过距离的一半，最大50像素
        arrow_width = 10

        # 计算箭头位置（从玩家位置向外偏移一点）
        offset = 30  # 从玩家位置向外偏移的距离
        start_x = current_screen_x + dx * offset
        start_y = current_screen_y + dy * offset

        # 箭头终点
        end_x = start_x + dx * arrow_length
        end_y = start_y + dy * arrow_length

        # 计算箭头的两个翼点
        angle = math.atan2(dy, dx)
        wing_angle1 = angle + math.pi * 0.75  # 135度
        wing_angle2 = angle - math.pi * 0.75  # -135度

        wing_x1 = end_x + math.cos(wing_angle1) * arrow_width
        wing_y1 = end_y + math.sin(wing_angle1) * arrow_width

        wing_x2 = end_x + math.cos(wing_angle2) * arrow_width
        wing_y2 = end_y + math.sin(wing_angle2) * arrow_width

        # 绘制箭头
        arrow_color = (212, 212, 212)  # 黄色箭头
        pygame.draw.line(self.screen, arrow_color, (start_x, start_y), (end_x, end_y), 3)
        pygame.draw.polygon(self.screen, arrow_color, [(end_x, end_y), (wing_x1, wing_y1), (wing_x2, wing_y2)])

        # 绘制箭头上方的距离文本
        distance = int(length)
        distance_text = f"{distance}"
        text_surface = self.font.render(distance_text, True, (181, 206, 168))

        # 文本位置（箭头中点上方）
        text_x = (start_x + end_x) / 2 - text_surface.get_width() / 2
        text_y = (start_y + end_y) / 2 - 20

        # 绘制文本
        self.screen.blit(text_surface, (text_x, text_y))

    def _add_conversion_particles(self, x, y, base):
        # 在指定位置添加进制转换的粒子效果
        num_particles = 20  # 增加粒子数量到60个
        # 确保x和y是数值类型
        try:
            x = float(x)
            y = float(y)
        except (ValueError, TypeError):
            print(f"警告：粒子效果位置坐标转换失败，使用原始值 x={x}, y={y}")
        print(f"创建进制转换粒子效果: 位置=({x}, {y}), 进制={base}, 粒子数量={num_particles}")
        colors = {
            2: [(100, 200, 255), (50, 150, 255), (80, 180, 240), (30, 130, 220), (120, 220, 255)],   # 蓝色系 - 二进制
            10: [(255, 200, 100), (255, 150, 50), (255, 180, 70), (240, 160, 40), (250, 210, 120)],  # 橙色系 - 十进制
            16: [(200, 255, 100), (150, 255, 50), (180, 240, 80), (160, 230, 60), (220, 255, 120)]   # 绿色系 - 十六进制
        }
        
        base_colors = colors.get(base, [(255, 255, 255), (200, 200, 200), (220, 220, 220), (180, 180, 180)])
        print(f"选择颜色方案: {base}进制, {len(base_colors)}种颜色")
        
        # 创建扩散波效果
        wave_radius = 0  # 初始波半径
        wave_speed = 20  # 波扩散速度
        wave_particle = {
            "x": x,
            "y": y,
            "radius": wave_radius,
            "max_radius": 100,  # 最大扩散半径，从100增大到150
            "speed": wave_speed,
            "color": random.choice(base_colors),
            "life": 1,  # 波的生命周期，从3.0延长到4.5
            "start_time": time.time(),
            "type": "wave"  # 标记为波类型粒子
        }
        self.particles.append(wave_particle)
        print(f"创建波效果粒子: 半径={wave_radius}→{wave_particle['max_radius']}, 速度={wave_speed}, 生命={wave_particle['life']}秒")
        
        # 创建标准粒子
        for i in range(num_particles):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2, 5)  # 增加粒子速度，从(5,15)到(7,18)
            size = random.uniform(5, 10)   # 增加粒子大小，从(8,20)到(10,25)
            color = random.choice(base_colors)
            
            particle = {
                "x": x,
                "y": y,
                "dx": math.cos(angle) * speed,
                "dy": math.sin(angle) * speed,
                "size": size,
                "color": color,
                "life": random.uniform(1.5, 3.0),  # 延长粒子生命周期，从(1.5,3.0)到(2.0,4.0)
                "start_time": time.time(),
                "type": "particle"  # 标记为标准粒子类型
            }
            
            self.particles.append(particle)
            
        print(f"粒子效果创建完成: 总计{len(self.particles)}个粒子在系统中")
    
    def _draw_player(self, player_id, x, y, value, name, color):
        # 在屏幕上绘制一个玩家
        # 根据当前显示进制决定前缀和数值格式
        prefix = ""
        value_str = ""
        display_base = self.display_base  # 默认使用当前玩家的显示进制
        # 获取玩家内存数据
        player_memory_usage = 0
        max_memory = 255  # 默认最大内存值
        memory_release_active = False  # 内存释放状态标志
        
        # 如果游戏状态中有此玩家的进制设置，使用它
        if self.game_state and "players" in self.game_state and player_id in self.game_state["players"]:
            player_data = self.game_state["players"][player_id]
            if "base" in player_data:
                display_base = player_data["base"]
            if "memory_usage" in player_data:
                player_memory_usage = player_data["memory_usage"]
            if "memory_release_active" in player_data:
                memory_release_active = player_data["memory_release_active"]
        
        is_self = str(player_id) == str(self.client_id)
        if is_self:
            self.memory_usage = player_memory_usage
        
        # 检查内存释放状态并绘制特效
        if memory_release_active:
            # 绘制"内存释放中"文本
            release_font = pygame.font.SysFont("Microsoft YaHei", 14, bold=True)
            release_text = release_font.render("内存释放中", True, (0, 255, 100))
            text_x = x - release_text.get_width() // 2
            text_y = y - 60  # 在玩家上方显示
            self.screen.blit(release_text, (text_x, text_y))
        
            player_pos = player_data["position"]
            # 每帧添加2-3个粒子
            for _ in range(random.randint(2, 3)):
                self._add_memory_release_particle(player_pos[0], player_pos[1])
        
        # 格式化值显示
        if isinstance(value, (int, float)):
            int_value = int(value)
            if display_base == 2:
                prefix = "0b"
                value_str = bin(int_value)[2:]  # 移除Python的"0b"前缀
            elif display_base == 16:
                prefix = "0x"
                value_str = hex(int_value)[2:]  # 移除Python的"0x"前缀
            else:  # 十进制
                prefix = ""
                value_str = str(int_value)
        else:
            # 如果不是数字，直接显示
            if str(value).startswith("0x"):
                prefix = "0x"
                value_str = str(value)[2:]
            elif str(value).startswith("0b"):
                prefix = "0b"
                value_str = str(value)[2:]
            else:
                prefix = ""
                value_str = str(value)

        # 渲染前缀
        # prefix_color = self.prefix_color if is_self else color
        prefix_text = self.char_font.render(prefix, True, self.prefix_color)

        # 渲染数值
        # number_color = self.number_color if is_self else color
        number_text = self.char_font.render(value_str, True, self.number_color)

        # 计算总宽度和高度
        prefix_width = prefix_text.get_width()
        number_width = number_text.get_width()
        total_width = prefix_width + number_width
        char_height = max(prefix_text.get_height(), number_text.get_height())

        # 计算起始位置，使整体居中
        start_x = x - total_width // 2
        char_y = y - char_height // 2

        # 渲染前缀和数值
        self.screen.blit(prefix_text, (start_x, char_y))
        self.screen.blit(number_text, (start_x + prefix_width, char_y))

        # 渲染用户名（放在角色下方）
        if name:
            name_text = self.username_font.render(name, True, color)
            name_width = name_text.get_width()
            # 计算用户名位置（居中于角色下方）
            name_x = x - name_width // 2
            name_y = y + char_height // 2 + 5  # 角色下方5像素
            self.screen.blit(name_text, (name_x, name_y))

            # 绘制内存条 (在玩家上方)
            if self.game_state and "players" in self.game_state and player_id in self.game_state["players"] and not is_self:
                # 内存条尺寸和位置
                bar_width = 50
                bar_height = 6
                bar_x = x - bar_width // 2
                bar_y = y - char_height // 2 - 15  # 角色上方15像素

                # 绘制边框和背景
                pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))

                # 计算内存占用比例
                memory_ratio = min(1.0, player_memory_usage / max_memory)
                filled_width = int(bar_width * memory_ratio)

                # 根据占用程度和内存释放状态确定颜色
                if memory_release_active:
                    fill_color = (0, 150, 255)  # 蓝色，表示内存释放状态
                elif memory_ratio < 0.5:
                    fill_color = (0, 255, 0)  # 绿色
                elif memory_ratio < 0.8:
                    fill_color = (255, 255, 0)  # 黄色
                else:
                    fill_color = (255, 0, 0)  # 红色

                # 绘制填充部分
                if filled_width > 0:
                    pygame.draw.rect(self.screen, fill_color, (bar_x, bar_y, filled_width, bar_height))

                # 绘制内存使用文字
                memory_text = f"{player_memory_usage}/{max_memory}"
                memory_font = pygame.font.SysFont("Microsoft YaHei", 10)
                memory_surface = memory_font.render(memory_text, True, (200, 200, 200))
                memory_x = x - memory_surface.get_width() // 2
                memory_y = bar_y - memory_surface.get_height() - 2
                self.screen.blit(memory_surface, (memory_x, memory_y))

    def set_message_callback(self, callback):
        # 设置接收消息的回调函数
        self.message_callback = callback

    def send_move(self, position):
        # 发送移动消息
        move_message = {
            "type": "move",
            "position": position
        }
        self._send_message(move_message)


    def _send_base_change(self, base):
        # 发送进制变更请求
        base_message = {
            "type": "base_change",
            "base": base
        }
        self._send_message(base_message)
        
        # 在玩家位置添加粒子效果
        try:
            if self.game_state and "players" in self.game_state and self.client_id in self.game_state["players"]:
                player_data = self.game_state["players"][self.client_id]
                if "position" in player_data:
                    player_pos = player_data["position"]
                    self._add_conversion_particles(player_pos[0], player_pos[1], base)
        except Exception as e:
            print(f"创建进制变更粒子效果时出错: {e}")
        
    def send_action(self, action_type, **kwargs):
        # 发送游戏动作
        action_message = {
            "type": "action",
            "action": action_type,
            **kwargs
        }
        self._send_message(action_message)

    def _send_message(self, message):
        # 发送消息到服务器
        if not self.running or not self.client_socket:
            print("未连接到服务器，无法发送消息")
            return False

        try:
            self.client_socket.send(json.dumps(message).encode('utf-8'))
            return True
        except Exception as e:
            print(f"发送消息时出错: {e}")
            self.disconnect()
            return False

    def _receive_messages(self):
        # 接收服务器消息的线程函数
        buffer = ""
        while self.running:
            try:
                data = self.client_socket.recv(4096)
                if not data:
                    # 服务器关闭连接
                    break

                buffer += data.decode('utf-8')
                
                # 处理缓冲区中可能的多个JSON消息
                while buffer:
                    try:
                        # 尝试寻找完整的JSON对象边界
                        try:
                            # 寻找第一个有效的JSON对象
                            json_obj, index = json.JSONDecoder().raw_decode(buffer)
                            # 处理这个JSON对象
                            self._process_server_message(json_obj)
                            # 从缓冲区中移除已处理的JSON
                            buffer = buffer[index:].lstrip()
                            # 如果缓冲区为空，退出循环
                            if not buffer:
                                break
                        except json.JSONDecodeError:
                            # 如果缓冲区中没有完整的JSON对象，等待更多数据
                            break
                    except Exception as e:
                        print(f"处理JSON消息时出错: {e}, 缓冲区内容: {buffer[:100]}")
                        # 尝试找到下一个可能的JSON对象开始位置
                        try:
                            next_json_start = buffer.find("{", 1)
                            if next_json_start > 0:
                                print(f"尝试跳过无效数据到下一个JSON起始位置: {next_json_start}")
                                buffer = buffer[next_json_start:]
                            else:
                                # 没找到下一个JSON起始，清空缓冲区
                                print("无法找到有效的JSON数据，清空缓冲区")
                                buffer = ""
                                break
                        except:
                            # 出现严重错误，清空缓冲区
                            buffer = ""
                            break

            except ConnectionError:
                print("服务器连接已断开")
                break
            except Exception as e:
                print(f"接收消息时出错: {e}")
                buffer = ""  # 出错时清空缓冲区
                # 不要立即退出循环，尝试继续接收

        # 如果循环退出，确保客户端断开连接
        if self.running:
            self.disconnect()

    def _process_server_message(self, message):
        # 处理从服务器接收到的消息
        message_type = message.get('type')

        if message_type == 'welcome':
            # 处理欢迎消息
            self.client_id = message.get('client_id')
            # 确保客户端ID是字符串格式，以便与玩家列表中的ID匹配
            if self.client_id is not None:
                self.client_id = str(self.client_id)
            self.game_state = message.get('game_state')
            self.connected = True
            
            # 初始化所有玩家的位置插值数据
            if self.game_state and "players" in self.game_state:
                for player_id, player_data in self.game_state["players"].items():
                    if player_id != self.client_id:  # 只为其他玩家设置
                        position = player_data.get("position", [0, 0])
                        self.player_positions[player_id] = {
                            "current": position.copy(),
                            "target": position.copy(),
                            "last_update": time.time()
                        }
            # 设置初始玩家值
            self.player_value = 0
            print(message.get('message'))

        elif message_type == 'player_moved':
            # 处理玩家移动
            player_id = message.get('client_id')
            new_position = message.get('position')
            if self.game_state and 'players' in self.game_state and player_id in self.game_state['players']:
                # 立即更新游戏状态中的玩家位置
                self.game_state['players'][player_id]['position'] = new_position.copy()
                
                # 为其他玩家进行位置插值
                if str(player_id) != str(self.client_id):
                    if player_id not in self.player_positions:
                        self.player_positions[player_id] = {
                            "current": new_position.copy(),
                            "target": new_position.copy(),
                            "last_update": time.time()
                        }
                    else:
                        # 从当前位置开始插值
                        current_pos = self.game_state['players'][player_id]['position'].copy()
                        self.player_positions[player_id]["current"] = current_pos
                        self.player_positions[player_id]["target"] = new_position.copy()
                        self.player_positions[player_id]["last_update"] = time.time()
        elif message_type == 'player_joined':
            # 处理新玩家加入
            print(message.get('message'))
            if self.game_state and 'players' in self.game_state:
                new_player_id = message.get('client_id')
                new_player_username = message.get('username')
                # 更新本地游戏状态...

        elif message_type == 'player_left':
            # 处理玩家离开
            print(message.get('message'))
            if self.game_state and 'players' in self.game_state:
                left_player_id = message.get('client_id')
                # 更新本地游戏状态...

        elif message_type == 'player_value_updated':
            # 处理玩家值更新消息
            updated_client_id = message.get('client_id')
            new_value = message.get('value')
            memory_usage = message.get('memory_usage')
            memory_release_active = message.get('memory_release_active')
            
            print(f"收到player_value_updated消息: player_id={updated_client_id}, value={new_value}, memory={memory_usage}")
            
            # 更新游戏状态
            if self.game_state and "players" in self.game_state and updated_client_id in self.game_state["players"]:
                player_data = self.game_state["players"][updated_client_id]
                
                # 更新值
                if new_value is not None:
                    player_data["value"] = new_value
                    if updated_client_id == self.client_id:
                        self.player_value = new_value
                
                # 更新内存使用
                if memory_usage is not None:
                    player_data["memory_usage"] = memory_usage
                
                # 更新内存释放状态
                if memory_release_active is not None:
                    player_data["memory_release_active"] = memory_release_active
        
        elif message_type == 'chat':
            # 处理聊天消息
            sender_id = message.get('client_id')
            sender_name = message.get('username')
            content = message.get('content')
            print(f"{sender_name}: {content}")

        elif message_type == 'game_update':
            # 获取新的游戏状态
            new_game_state = message.get('game_state')
            
            # 优先处理玩家位置信息
            if new_game_state and "players" in new_game_state:
                for player_id, player_data in new_game_state["players"].items():
                    # 确保游戏状态和玩家ID存在
                    if self.game_state and "players" in self.game_state and player_id in self.game_state["players"]:
                        # 获取新位置
                        if "position" in player_data:
                            new_position = player_data["position"]
                            
                            # 更新游戏状态中的位置
                            self.game_state["players"][player_id]["position"] = new_position.copy()
                            
                            # 更新其他玩家的插值系统
                            if str(player_id) != str(self.client_id) and player_id in self.player_positions:
                                current_pos = new_position.copy()
                                self.player_positions[player_id]["current"] = current_pos
                                self.player_positions[player_id]["target"] = new_position.copy()
                                self.player_positions[player_id]["last_update"] = time.time()
                        
                        # 处理内存释放状态
                        if "memory_release_active" in player_data:
                            self.game_state["players"][player_id]["memory_release_active"] = player_data["memory_release_active"]
            
            # 更新完整游戏状态
            self.game_state = new_game_state
            
            # 更新玩家值
            if self.game_state and "players" in self.game_state and self.client_id in self.game_state["players"]:
                player_data = self.game_state["players"][self.client_id]
                if "value" in player_data:
                    self.player_value = player_data["value"]
        elif message_type == 'base_changed':
            # 处理进制变化
            try:
                changed_player_id = message.get('client_id')
                # 确保ID是字符串类型
                if changed_player_id is not None:
                    changed_player_id = str(changed_player_id)
                
                new_base = message.get('base')
                timestamp = message.get('timestamp', time.time())
                priority = message.get('priority', 0)
                player_position = message.get('player_position')
                
                print(f"收到base_changed消息: player={changed_player_id}, base={new_base}, timestamp={timestamp}, priority={priority}, player_position={player_position}")
                
                # 验证游戏状态
                if not self.game_state:
                    print("错误: 游戏状态为空，无法处理base_changed消息")
                    return
                
                if "players" not in self.game_state:
                    print("错误: 游戏状态中没有players字段，无法处理base_changed消息")
                    return
                
                # 打印玩家ID列表和changed_player_id
                player_ids = list(self.game_state['players'].keys())
                print(f"游戏状态中的玩家ID列表: {player_ids}")
                print(f"changed_player_id: {changed_player_id}, 类型: {type(changed_player_id)}")
                
                # 更新玩家进制
                if changed_player_id in self.game_state["players"]:
                    print(f"匹配成功: 玩家ID {changed_player_id} 在游戏状态中找到")
                    self.game_state["players"][changed_player_id]["base"] = new_base
                    # 如果是当前玩家自己进制变化了，更新本地显示进制
                    if changed_player_id == str(self.client_id):
                        self.display_base = new_base
                    
                    # 添加中文名称显示
                    base_names = {
                        2: "二进制",
                        10: "十进制",
                        16: "十六进制"
                    }
                    base_name = base_names.get(new_base, f"{new_base}进制")
                    
                    # 确定粒子效果的位置 - 优先使用服务器提供的位置
                    world_x = None
                    world_y = None
                    
                    if player_position:
                        try:
                            world_x = player_position[0]
                            world_y = player_position[1]
                            print(f"使用服务器提供的位置({world_x}, {world_y})创建粒子效果")
                        except (IndexError, TypeError) as e:
                            print(f"无法使用服务器提供的位置: {e}")
                            player_position = None
                    
                    if player_position is None or world_x is None or world_y is None:
                        # 回退到使用本地游戏状态中的位置
                        try:
                            player_pos = self.game_state["players"][changed_player_id]["position"]
                            world_x = player_pos[0]
                            world_y = player_pos[1]
                            print(f"使用本地游戏状态中的位置({world_x}, {world_y})创建粒子效果")
                        except (KeyError, IndexError, TypeError) as e:
                            print(f"错误：找不到玩家ID {changed_player_id} 的位置信息: {e}")
                            print(f"完整的游戏状态: {json.dumps(self.game_state, indent=2)}")
                            # 使用默认位置
                            world_x = self.screen_width // 2
                            world_y = self.screen_height // 2
                            print(f"使用默认位置({world_x}, {world_y})创建粒子效果")
                    
                    # 添加世界坐标系中的粒子效果，这样所有玩家都能看到
                    try:
                        self._add_conversion_particles(world_x, world_y, new_base)
                        print(f"在位置({world_x}, {world_y})创建了{base_name}的粒子效果，base={new_base}，粒子效果已添加")
                    except Exception as e:
                        print(f"创建粒子效果时出错: {e}")
                else:
                    print(f"错误：玩家ID {changed_player_id} 在游戏状态中未找到")
                    print(f"可用的玩家ID: {player_ids}")
            except Exception as e:
                print(f"处理base_changed消息时发生错误: {e}")

                # 触发一个特殊的动画效果标记，确保所有客户端显示动画
                print(f"玩家 {self.game_state['players'][changed_player_id]['username']} 切换到{base_name}")
        elif message_type == 'action_result':
            # 处理动作结果
            client_id = message.get('client_id')
            action = message.get('action')
            result = message.get('result')
            
            # 处理内存释放状态
            if action == 'decimal_skill' and message.get('skill_name') == '内存释放':
                if 'memory_release_active' in message:
                    # 更新玩家的内存释放状态
                    player_id = message.get('client_id')
                    if self.game_state and "players" in self.game_state and player_id in self.game_state["players"]:
                        self.game_state["players"][player_id]["memory_release_active"] = message.get('memory_release_active')
            elif action == 'skill':
                skill_name = message.get('skill_name')
                skill_index = message.get('skill_index')
                player_position = message.get('player_position')
                if player_position and skill_name:
                    # 添加基础粒子效果
                    self._add_skill_particles(player_position[0], player_position[1])
                    if 0 <= skill_index < len(self.skills):
                        skill = self.skills[skill_index]

                        # 创建运算符特效
                        operator_effect = {
                            "x": player_position[0],
                            "y": player_position[1] - 50,
                            "symbol": skill["symbol"],  # & 或 *
                            "color": skill["color"],  # 使用技能定义的颜色
                            "initial_size": 80,  # 初始大小
                            "size": 80,  # 当前大小
                            "initial_opacity": 180,  # 初始不透明度 (0-255)
                            "opacity": 180,  # 当前不透明度
                            "life": 2.0,  # 生命周期
                            "start_time": time.time(),
                            "type": "operator",  # 标记为运算符特效
                            "dx": 0,  # 运算符粒子不需要移动
                            "dy": 0   # 运算符粒子不需要移动
                            }
                        self.particles.append(operator_effect)

            elif action == 'hex_skill':  # 不是自己使用的十六进制技能
                skill_name = message.get('skill_name')
                skill_index = message.get('skill_index')
                player_position = message.get('player_position')
                
                if player_position and skill_name:
                    # 添加基础粒子效果
                    self._add_skill_particles(player_position[0], player_position[1])
                    
                    # 找到对应的十六进制技能
                    if 0 <= skill_index < len(self.hex_skills):
                        skill = self.hex_skills[skill_index]
                        
                        # 创建运算符特效
                        operator_effect = {
                            "x": player_position[0],
                            "y": player_position[1] - 50,
                            "symbol": skill["symbol"],  # & 或 *
                            "color": skill["color"],  # 使用技能定义的颜色
                            "initial_size": 80,  # 初始大小
                            "size": 80,  # 当前大小
                            "initial_opacity": 180,  # 初始不透明度 (0-255)
                            "opacity": 180,  # 当前不透明度
                            "life": 2.0,  # 生命周期
                            "start_time": time.time(),
                            "type": "operator",  # 标记为运算符特效
                            "dx": 0,  # 运算符粒子不需要移动
                            "dy": 0   # 运算符粒子不需要移动
                        }
                        self.particles.append(operator_effect)
                        
            # 处理十进制技能使用效果
            if action == 'decimal_skill':
                skill_name = message.get('skill_name')
                skill_index = message.get('skill_index')
                player_position = message.get('player_position')

                if player_position and skill_name:
                    # 为十进制技能添加特效
                    decimal_effect_color = (0, 200, 255)  # 蓝色调
                    if skill_name == "赋值":
                        symbol = "="
                        decimal_effect_color = (255, 150, 100)
                        self._add_skill_particles(player_position[0], player_position[1])
                    elif skill_name == "开火":
                        symbol = "fire"
                        decimal_effect_color = (200, 100, 255)
                        self._add_fire_text_effect(player_position[0], player_position[1])
                        self._add_skill_particles(player_position[0], player_position[1])
                    elif skill_name == "爆炸":
                        symbol = "*args"
                        decimal_effect_color = (255, 100, 100)
                        self._add_explosion_particles(player_position[0], player_position[1])
                    elif skill_name == "内存释放":
                        symbol = "</>"
                        decimal_effect_color = (150, 255, 100)
                        self._add_skill_particles(player_position[0], player_position[1])
                    else:
                        symbol = "#"

                    # 只有非开火技能才添加operator特效
                    if skill_name != "开火":
                        # 创建十进制特效
                        decimal_effect = {
                            "x": player_position[0],
                            "y": player_position[1] - 50,
                            "symbol": symbol,
                            "color": decimal_effect_color,
                            "initial_size": 80,
                            "size": 80,
                            "initial_opacity": 180,
                            "opacity": 180,
                            "life": 2.0,
                            "start_time": time.time(),
                            "type": "operator",
                            "dx": 0,
                            "dy": 0
                        }
                        self.particles.append(decimal_effect)
            
        elif message_type == 'bullets_created':
            # 处理新创建的子弹
            new_bullets = message.get('bullets', [])

            if self.game_state and "bullets" in self.game_state:
                # 将新子弹添加到游戏状态
                self.game_state["bullets"].extend(new_bullets)

                # 立即更新子弹插值状态
                self._update_bullets()

                # 添加创建子弹的效果
                for bullet in new_bullets:
                    # 添加子弹发射特效
                    if "position" in bullet:
                        # 在子弹位置添加粒子效果
                        x, y = bullet["position"]
                        for _ in range(5):  # 添加5个粒子
                            particle = {
                                "x": x,
                                "y": y,
                                "dx": random.uniform(-2, 2),
                                "dy": random.uniform(-2, 2),
                                "size": random.uniform(2, 5),
                                "color": (212, 212, 212),
                                "life": random.uniform(0.2, 0.5),
                                "start_time": time.time(),
                                "type": "particle"
                            }
                            self.particles.append(particle)
                

            
            # 处理十六进制技能使用效果
        # 调用消息回调函数
        if self.message_callback:
            self.message_callback(message)

    def _draw_skill_buttons(self):
        # 绘制底部的技能按钮
        self._draw_skill_buttons_common(self.skills)
            
    def _draw_hex_skill_buttons(self):
        # 绘制底部的十六进制模式技能按钮
        self._draw_skill_buttons_common(self.hex_skills)
        
    def _draw_decimal_skill_buttons(self):
        # 绘制底部的十进制模式技能按钮
        self._draw_skill_buttons_common(self.decimal_skills)
        
    def _draw_memory_bar(self):
        # 在右上角绘制内存占用进度条
        bar_width = 150
        bar_height = 20
        bar_x = self.screen_width - bar_width - 10
        bar_y = 10
        
        # 绘制边框和背景
        pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
        
        # 计算内存占用比例
        memory_ratio = self.memory_usage / self.max_memory
        filled_width = int(bar_width * memory_ratio)
        
        # 根据占用程度确定颜色
        # 根据占用程度和状态确定颜色
        if self.memory_release_active:
            fill_color = (0, 150, 255)  # 蓝色，表示内存释放状态
        elif memory_ratio < 0.5:
            fill_color = (0, 255, 0)  # 绿色
        elif memory_ratio < 0.8:
            fill_color = (255, 255, 0)  # 黄色
        else:
            fill_color = (255, 0, 0)  # 红色
            
        # 绘制填充部分
        pygame.draw.rect(self.screen, fill_color, (bar_x, bar_y, filled_width, bar_height))
        
        # 绘制内存使用文字
        memory_text = f"内存: {self.memory_usage}/{self.max_memory}"
        memory_font = pygame.font.SysFont("Microsoft YaHei", 14)
        text_surface = memory_font.render(memory_text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(bar_x + bar_width/2, bar_y + bar_height/2))
        self.screen.blit(text_surface, text_rect)
        
    def _draw_skill_buttons_common(self, skills_list):
        # 通用的技能按钮绘制函数
        font = pygame.font.SysFont("Microsoft YaHei", 16)
        symbol_font = pygame.font.SysFont("Consolas", 26, bold=True)
        cooldown_font = pygame.font.SysFont("Microsoft YaHei", 16, bold=True)

        # 获取当前时间用于计算冷却
        current_time = time.time()

        # 计算按钮区域的总宽度
        total_width = (self.skill_button_size + self.skill_button_margin) * len(skills_list) - self.skill_button_margin
        start_x = (self.screen_width - total_width) // 2
        button_y = self.screen_height - self.skill_button_size - 10  # 底部边距10像素

        # 绘制每个技能按钮
        for i, skill in enumerate(skills_list):
            # 计算按钮位置
            button_x = start_x + (self.skill_button_size + self.skill_button_margin) * i
            button_rect = pygame.Rect(button_x, button_y, self.skill_button_size, self.skill_button_size)

            # 检测鼠标悬停
            is_hover = button_rect.collidepoint(pygame.mouse.get_pos())
            if is_hover:
                self.skill_hover_index = i

            # 绘制按钮背景
            button_color = skill["color"]
            border_color = (255, 255, 255) if is_hover else (150, 150, 150)
            pygame.draw.rect(self.screen, button_color, button_rect, border_radius=10)
            pygame.draw.rect(self.screen, border_color, button_rect, width=3, border_radius=10)

            # 绘制技能符号
            symbol_text = symbol_font.render(skill["symbol"], True, (255, 255, 255))
            symbol_rect = symbol_text.get_rect(center=(button_x + self.skill_button_size//2, button_y + self.skill_button_size//2 - 5))
            self.screen.blit(symbol_text, symbol_rect)
            
            # 检查并绘制技能冷却遮罩
            skill_name = skill["name"]
            last_use_time = self.last_skill_use.get(skill_name, 0)
            cooldown_time = self.cooldowns.get(skill_name, 0)
            
            # 计算经过的时间和剩余冷却时间
            elapsed = current_time - last_use_time
            if elapsed < cooldown_time:
                # 技能在冷却中，绘制半透明黑色遮罩
                cooldown_ratio = 1 - (elapsed / cooldown_time)  # 冷却剩余比例
                mask_height = int(self.skill_button_size * cooldown_ratio)  # 遮罩高度
                
                # 创建遮罩矩形，保持圆角边框
                mask_rect = pygame.Rect(
                    button_x,
                    button_y + self.skill_button_size - mask_height,
                    self.skill_button_size,
                    mask_height
                )
                
                # 创建遮罩表面
                mask_surface = pygame.Surface((self.skill_button_size, mask_height), pygame.SRCALPHA)
                mask_surface.fill((0, 0, 0, 180))  # 半透明黑色
                
                # 为遮罩设置圆角（如果在底部）
                self.screen.blit(mask_surface, mask_rect.topleft)
                
                # 显示剩余冷却时间（秒）
                remaining = cooldown_time - elapsed
                if remaining > 0.5:  # 只有超过0.5秒才显示
                    time_text = f"{remaining:.1f}s"
                    time_surface = cooldown_font.render(time_text, True, (255, 255, 255))
                    time_rect = time_surface.get_rect(center=(button_x + self.skill_button_size//2, button_y + self.skill_button_size//2 + 10))
                    self.screen.blit(time_surface, time_rect)

            # 绘制技能名称
            name_text = font.render(skill["name"], True, (255, 255, 255))
            name_rect = name_text.get_rect(center=(button_x + self.skill_button_size//2, button_y + self.skill_button_size - 12))
            self.screen.blit(name_text, name_rect)

            # 在按钮上方显示按键提示
            key_name = get_key_name(skill["key"]).upper()
            key_text = font.render(key_name, True, (200, 200, 200))
            key_rect = key_text.get_rect(center=(button_x + self.skill_button_size//2, button_y - 12))
            self.screen.blit(key_text, key_rect)

        # 如果有悬停的按钮，显示技能描述
        if self.skill_hover_index >= 0 and self.skill_hover_index < len(skills_list):
            skill = skills_list[self.skill_hover_index]
            desc_font = pygame.font.SysFont("Microsoft YaHei", 18)
            desc_text = desc_font.render(skill["description"], True, (255, 255, 255))
            desc_rect = desc_text.get_rect(center=(self.screen_width // 2, button_y - 30))
            
            # 绘制描述背景
            bg_rect = desc_rect.inflate(20, 10)
            pygame.draw.rect(self.screen, (50, 50, 50, 180), bg_rect, border_radius=5)
            self.screen.blit(desc_text, desc_rect)
    def use_skill(self, skill_index):
        # 使用技能（仅在二进制模式下可用）
        if self.display_base != 2:
            return
            
        if 0 <= skill_index < len(self.skills):
            skill = self.skills[skill_index]

            # 检查技能冷却
            if not self._check_cooldown(skill["name"]):
                return
            
            # 检查内存需求
            memory_needed = 0
            if skill["name"] == "AND":
                memory_needed = 1
            elif skill["name"] == "OR":
                memory_needed = 1
            elif skill["name"] == "NOT":
                memory_needed = 1
            elif skill["name"] == "XOR":
                memory_needed = 5
                
            # 检查内存是否足够
            if self.memory_usage + memory_needed > self.max_memory:
                print(f"内存不足，无法使用{skill['name']}技能！需要{memory_needed}点内存，当前可用内存：{self.max_memory - self.memory_usage}")
                return
            if skill["name"] != "NOT" and not self._check_target_in_range(200):
                return
                
            print(f"使用技能: {skill['name']}")

            # 根据不同技能增加内存
            if skill["name"] == "AND":
                self.memory_usage += 1
                print(f"使用AND技能，内存增加1点，当前内存：{self.memory_usage}")
            elif skill["name"] == "OR":
                self.memory_usage += 1
                print(f"使用OR技能，内存增加1点，当前内存：{self.memory_usage}")
            elif skill["name"] == "NOT":
                self.memory_usage += 1
                print(f"使用NOT技能，内存增加1点，当前内存：{self.memory_usage}")
            elif skill["name"] == "XOR":
                self.memory_usage += 5
                print(f"使用XOR技能，内存增加5点，当前内存：{self.memory_usage}")

            # 发送技能使用消息到服务器
            action_message = {
                "type": "action",
                "action": "skill",
                "skill_name": skill["name"],
                "skill_index": skill_index,
                "memory_usage": self.memory_usage
            }
            self._send_message(action_message)

            # 更新技能使用时间
            self._update_skill_use_time(skill["name"])

            # 在玩家位置创建技能使用的粒子效果
            # if self.game_state and "players" in self.game_state and self.client_id in self.game_state["players"]:
            #     player_pos = self.game_state["players"][self.client_id]["position"]
            #     # 使用技能颜色创建粒子效果
            #     self._add_skill_particles(player_pos[0], player_pos[1])
            #     # 添加运算符特效
            #     self._add_operator_effect(player_pos, skill)
                
    def use_hex_skill(self, skill_index):
        # 使用十六进制模式下的技能
        if self.display_base != 16:
            return
            
        if 0 <= skill_index < len(self.hex_skills):
            skill = self.hex_skills[skill_index]

            # 检查技能冷却
            if not self._check_cooldown(skill["name"]):
                return
            
            # 检查内存需求
            memory_needed = 0
            if skill_index == 0:  # 取址技能
                memory_needed = 8
            elif skill_index == 1:  # 寻址技能
                memory_needed = 20
                
            # 检查内存是否足够
            if self.memory_usage + memory_needed > self.max_memory:
                print(f"内存不足，无法使用{skill['name']}技能！需要{memory_needed}点内存，当前可用内存：{self.max_memory - self.memory_usage}")
                return
            
            print(f"使用十六进制技能: {skill['name']}")

            # 取址技能
            if skill_index == 0:  # 取址技能
                if self.game_state and "players" in self.game_state and self.client_id in self.game_state["players"]:
                    # 标记当前位置
                    self.marked_position = self.game_state["players"][self.client_id]["position"].copy()
                    print(f"标记当前位置: {self.marked_position}")
                    # 增加内存占用
                    self.memory_usage += 8
                    print(f"使用取址技能，内存增加8点，当前内存：{self.memory_usage}")
            
            # 寻址技能
            elif skill_index == 1:  # 寻址技能
                if self.marked_position:
                    # 记录传送开始时间并设置传送锁定状态
                    self.teleporting = True
                    self.teleport_time = time.time()
                    # 传送到标记位置
                    self.send_move(self.marked_position)
                    # 立即更新本地位置以避免漂移
                    self.player_x, self.player_y = self.marked_position
                    # 重置速度以防止传送后继续移动
                    self.velocity_x = 0
                    self.velocity_y = 0
                    self.marked_position = None
                    print(f"传送到标记位置并锁定移动 {self.teleport_time}")
                    # 增加内存占用
                    self.memory_usage += 20
                    print(f"使用寻址技能，内存增加20点，当前内存：{self.memory_usage}")
                else:
                    print("未设置标记位置，无法使用寻址技能")
                    return

            # 发送技能使用消息到服务器
            action_message = {
                "type": "action",
                "action": "hex_skill",
                "skill_name": skill["name"],
                "skill_index": skill_index,
                "memory_usage": self.memory_usage
            }
            self._send_message(action_message)

            # 更新技能使用时间
            self._update_skill_use_time(skill["name"])

            # 在玩家位置创建技能使用的粒子效果
            if self.game_state and "players" in self.game_state and self.client_id in self.game_state["players"]:
                player_pos = self.game_state["players"][self.client_id]["position"]
                # 创建粒子效果
                self._add_skill_particles(player_pos[0], player_pos[1])
                
    def use_decimal_skill(self, skill_index):
        # 使用十进制模式下的技能
        if self.display_base != 10:
            return

        if 0 <= skill_index < len(self.decimal_skills):
            skill = self.decimal_skills[skill_index]

            # 检查技能冷却
            if not self._check_cooldown(skill["name"]):
                return
            
            # 开火和爆炸技能需要检查射程范围
            if skill_index in [1, 2]:  # 开火或爆炸技能
                # 检查600距离内是否有玩家
                if not self._check_target_in_range(600):
                    print(f"{skill['name']}技能: 射程范围内没有目标!")
                    return
            
            # 检查内存需求
            memory_needed = 0
            if skill_index == 0:  # 赋值技能
                memory_needed = 10
            elif skill_index == 1:  # 打印技能
                memory_needed = 10
            elif skill_index == 2:  # 开火技能
                # 开火技能是消耗内存，不是增加内存，所以这里检查已有内存是否足够
                if self.memory_usage < 20:
                    print(f"开火技能: 内存不足! 需要至少20点内存，当前内存:{self.memory_usage}")
                    return
            # 释放技能不需要检查内存
            
            # 除开火和释放技能外，检查其他技能是否有足够内存
            if skill_index not in [2, 3] and self.memory_usage + memory_needed > self.max_memory:
                print(f"内存不足，无法使用{skill['name']}技能！需要{memory_needed}点内存，当前可用内存：{self.max_memory - self.memory_usage}")
                return
                
            print(f"使用十进制技能: {skill['name']}")

            # 赋值技能
            if skill_index == 0:  # 赋值技能
                # 生成1-100的随机值
                random_value = random.randint(1, 255)
                self.player_value = random_value
                # 使用固定10点内存占用
                self.memory_usage += 10
                print(f"赋值技能: 设置玩家值为{random_value}, 内存占用增加10点，当前内存:{self.memory_usage}")
                
                # 向服务器发送玩家值更新
                self._send_message({
                    'type': 'player_update',
                    'client_id': self.client_id,
                    'value': self.player_value,
                    'memory_usage': self.memory_usage
                })

            # 开火技能
            elif skill_index == 1:  # 开火技能
                print(f"开火技能: 发射能量弹! 消耗20点内存")
                # 消耗内存
                self.memory_usage = max(0, self.memory_usage - 20)

            # 爆炸技能
            elif skill_index == 2:  # 爆炸技能
                print(f"爆炸技能: 释放冲击波! 消耗30点内存")
                # 消耗内存
                self.memory_usage = max(0, self.memory_usage - 30)

            # 释放技能
            elif skill_index == 3:  # 内存释放技能
                print(f"内存释放技能: 开始释放内存")
                # 激活内存释放状态
                self.memory_release_active = True
                self.memory_release_start_time = time.time()
                # 记录激活时的初始内存值
                self.initial_memory = self.memory_usage
                # 内存释放状态下不立即释放内存，而是持续降低
                print(f"内存释放技能已激活")

            # 发送技能使用消息到服务器
            action_message = {
                "type": "action",
                "action": "decimal_skill",
                "skill_name": skill["name"],
                "skill_index": skill_index,
                "memory_usage": self.memory_usage
            }
            self._send_message(action_message)

            # 更新技能使用时间
            self._update_skill_use_time(skill["name"])

            # 在玩家位置创建技能使用的粒子效果
            if self.game_state and "players" in self.game_state and self.client_id in self.game_state["players"]:
                player_pos = self.game_state["players"][self.client_id]["position"]
                # 创建粒子效果
                if skill_index == 1:  # 开火技能使用特殊效果
                    self._add_fire_text_effect(player_pos[0], player_pos[1])
                elif skill_index == 2:  # 爆炸技能使用特殊粒子效果
                    self._add_explosion_particles(player_pos[0], player_pos[1])
                else:  # 其他技能使用通用粒子效果
                    self._add_skill_particles(player_pos[0], player_pos[1])
    def _add_skill_particles(self, x, y):
        # 为技能使用添加粒子效果
        num_particles = 30
        # 创建飞散粒子
        for i in range(num_particles):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(3, 8)
            size = random.uniform(4, 10)

            # 调整粒子颜色，稍微增加随机性
            offset = random.randint(-30, 30)
            r = min(255, 225 + offset)
            g = min(255, 225 + offset)
            b = min(255, 225 + offset)

            particle = {
                "x": x,
                "y": y,
                "dx": math.cos(angle) * speed,
                "dy": math.sin(angle) * speed,
                "size": size,
                "color": (r, g, b),
                "life": random.uniform(1.0, 2.5),
                "start_time": time.time(),
                "type": "particle"
            }
            self.particles.append(particle)
            
    def _add_fire_text_effect(self, x, y):
        # 为开火技能添加特殊文本效果
        # 创建fire文本特效
        fire_effect = {
            "x": x,
            "y": y - 40,  # 在玩家上方显示
            "text_size": 40,  # 文本大小
            "bracket_size": 40,  # 括号大小
            "life": 1.2,  # 缩短生命周期，减少对其他粒子的影响
            "start_time": time.time(),
            "type": "fire_text"  # 标记为fire文本特效（特殊处理，不更新位置）
        }
        self.particles.append(fire_effect)
        
    def _add_explosion_particles(self, x, y):
        # 为爆炸技能添加特殊粒子效果
        num_particles = 60  # 增加粒子数量

        # 添加爆炸波效果 - 3个不同大小的扩散波
        wave_colors = [(255, 100, 0), (255, 50, 0), (255, 0, 0)]
        max_radiuses = [200, 150, 100]

        for i in range(3):
            wave_particle = {
                "x": x,
                "y": y,
                "radius": 10,  # 初始半径
                "max_radius": max_radiuses[i],  # 最大半径
                "speed": 80,  # 扩散速度
                "color": wave_colors[i],  # 波的颜色
                "life": 1.0,  # 生命周期
                "start_time": time.time(),
                "type": "wave"  # 指定为波类型
            }
            self.particles.append(wave_particle)

        # 创建飞散粒子
        for i in range(num_particles):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(5, 15)  # 速度更快
            size = random.uniform(8, 15)  # 尺寸更大

            # 随机选择红色或橙色系
            r = random.randint(200, 255)
            g = random.randint(0, 150)
            b = 0

            particle = {
                "x": x,
                "y": y,
                "dx": math.cos(angle) * speed,
                "dy": math.sin(angle) * speed,
                "size": size,
                "color": (r, g, b),
                "life": random.uniform(0.8, 2.0),
                "start_time": time.time(),
                "type": "particle"
            }
            self.particles.append(particle)
    def _add_operator_effect(self, player_pos, skill):
        nearby_players = []

        # 查找附近的玩家
        if self.game_state and "players" in self.game_state:
            for other_id, other_player in self.game_state["players"].items():
                if other_id != self.client_id:
                    other_pos = other_player["position"]
                    nearby_players.append(other_pos)

        # 特殊处理NOT技能，在玩家自身位置显示运算符
        if skill["name"] == "NOT":
            operator_effect = {
                "x": player_pos[0],
                "y": player_pos[1] - 50,
                "symbol": skill["symbol"],  # 运算符符号(~)
                "color": (212, 212, 212),
                "initial_size": 80,  # 初始大小
                "size": 80,  # 当前大小
                "initial_opacity": 180,  # 初始不透明度 (0-255)
                "opacity": 180,  # 当前不透明度
                "life": 2.0,  # 生命周期
                "start_time": time.time(),
                "type": "operator",  # 标记为运算符特效
                "dx": 0,  # 运算符粒子不需要移动
                "dy": 0   # 运算符粒子不需要移动
            }
            self.particles.append(operator_effect)
        
        else:

        # 为每个附近的玩家创建运算符特效
            for target_pos in nearby_players:
                # 计算中点位置
                mid_x = (player_pos[0] + target_pos[0]) / 2
                mid_y = (player_pos[1] + target_pos[1]) / 2

                # 创建运算符特效
                operator_effect = {
                    "x": mid_x,
                    "y": mid_y,
                    "symbol": skill["symbol"],  # 运算符符号(&, |, ~, ^)
                    "color": (212, 212, 212),
                    "initial_size": 80,  # 初始大小
                    "size": 80,  # 当前大小
                    "initial_opacity": 180,  # 初始不透明度 (0-255)
                    "opacity": 180,  # 当前不透明度
                    "life": 2.0,  # 生命周期
                    "start_time": time.time(),
                    "type": "operator",  # 标记为运算符特效
                    "dx": 0,  # 运算符粒子不需要移动
                    "dy": 0   # 运算符粒子不需要移动
                }
                self.particles.append(operator_effect)

    def _add_memory_release_particle(self, x, y):
        # 为内存释放技能添加特殊粒子效果

        # 随机决定是否生成数字或粒子
        if random.random() < 0.3:  # 30%概率生成数字
            # 生成随机数字粒子
            random_num = random.randint(0, 9)
            particle = {
                "x": x + random.uniform(-50, 50),
                "y": y + random.uniform(-50, 50),
                "dx": random.uniform(-2, 2),
                "dy": random.uniform(-4, -1),  # 向上飘
                "text": str(random_num),
                "size": random.randint(15, 25),
                "color": (255, 255, 255),  # 白色数字
                "life": random.uniform(1.0, 2.0),
                "start_time": time.time(),
                "type": "number"
            }
        else:
            # 生成标准绿色粒子
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1, 3)
            size = random.uniform(4, 8)

            # 绿色粒子，带一点随机色调变化
            g_value = random.randint(200, 255)
            r_value = random.randint(50, 100)

            particle = {
                "x": x + random.uniform(-30, 30),
                "y": y + random.uniform(-30, 30),
                "dx": math.cos(angle) * speed,
                "dy": math.sin(angle) * speed,
                "size": size,
                "color": (r_value, g_value, 50),  # 绿色为主的粒子
                "life": random.uniform(0.8, 1.5),
                "start_time": time.time(),
                "type": "particle"
            }

        self.particles.append(particle)

    def _check_target_in_range(self, max_range):
        # 检查射程范围内是否有其他玩家
        if not self.game_state or not self.client_id or self.client_id not in self.game_state.get("players", {}):
            return False
        
        # 获取当前玩家位置
        player_pos = self.game_state["players"][self.client_id]["position"]
        
        # 检查是否有其他玩家在指定范围内
        for other_id, other_player in self.game_state["players"].items():
            if other_id != self.client_id:
                other_pos = other_player["position"]
                # 计算距离
                distance = math.sqrt(max(0, (player_pos[0] - other_pos[0]) ** 2 + (player_pos[1] - other_pos[1]) ** 2))
                if distance <= max_range:
                    return True
        
        return False
        
    def _check_cooldown(self, skill_name):
        current_time = time.time()
        last_use_time = self.last_skill_use.get(skill_name, 0)
        cooldown_time = self.cooldowns.get(skill_name, 0)

        # 计算经过的时间
        elapsed = current_time - last_use_time

        # 如果经过的时间小于冷却时间，技能仍在冷却中
        if elapsed < cooldown_time:
            remaining = cooldown_time - elapsed
            print(f"{skill_name}技能冷却中，还需等待 {remaining:.1f} 秒")
            return False

        return True

    def _update_skill_use_time(self, skill_name):
        self.last_skill_use[skill_name] = time.time()

# 客户端使用示例
if __name__ == "__main__":
    import random
    import argparse
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(description="游戏客户端")
    parser.add_argument("--host", default="localhost", help="服务器主机名")
    parser.add_argument("--port", type=int, default=5555, help="服务器端口")
    parser.add_argument("--username", default=f"Player_{random.randint(100, 999)}", help="玩家用户名")
    args = parser.parse_args()
    
    # 创建并连接客户端
    client = GameClient(host=args.host, port=args.port, username=args.username)
    
    def handle_message(message):
        message_type = message.get('type')
        if message_type in ['welcome', 'player_joined', 'player_left']:
            print(f"[系统] {message.get('message', '')}")
    
    client.set_message_callback(handle_message)
    
    if client.connect():
        try:
            # 启动游戏主循环
            client.run_game()
        except KeyboardInterrupt:
            print("程序被用户中断")
        finally:
            client.disconnect()
    else:
        print("无法连接到服务器")
