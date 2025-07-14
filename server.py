import socket
import threading
import json
import time
import random
import math
from math import sin, cos

class GameServer:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}  # {client_id: (client_socket, client_address, username)}
        self.client_id_counter = 0
        self.game_state = {
            "players": {},  # {client_id: {"position": [x, y], "score": 0, "username": "name", "value": 0, "target_value": 0, "memory_release_active": False, "memory_release_time": 0}}
            "game_objects": [],
            "base_conversions": [],  # 保存进制转换的动画信息
            "bullets": []  # 存储子弹对象 {"id": bullet_id, "owner": client_id, "position": [x, y], "velocity": [dx, dy], "damage": damage, "created_time": time_created, "char": "*", "color": (212, 212, 212)}
        }
        self.running = False
        self.lock = threading.Lock()  # 用于同步对共享资源的访问
        self.bullet_id_counter = 0  # 用于分配唯一的子弹ID

    def start(self):
        # 启动服务器
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        print(f"服务器已启动，监听 {self.host}:{self.port}")

        # 启动游戏逻辑循环
        game_thread = threading.Thread(target=self.game_loop)
        game_thread.daemon = True
        game_thread.start()

        # 接受客户端连接
        try:
            while self.running:
                client_socket, client_address = self.server_socket.accept()
                client_thread = threading.Thread(target=self.handle_client, 
                                               args=(client_socket, client_address))
                client_thread.daemon = True
                client_thread.start()
        except Exception as e:
            print(f"服务器错误: {e}")
        finally:
            self.stop()

    def stop(self):
        # 停止服务器
        self.running = False
        # 关闭所有客户端连接
        for client_id, (client_socket, _, _) in self.clients.items():
            try:
                client_socket.close()
            except:
                pass
        # 关闭服务器socket
        try:
            self.server_socket.close()
        except:
            pass
        print("服务器已关闭")

    def handle_client(self, client_socket, client_address):
        # 处理客户端连接和消息
        client_id = None

        try:
            # 接收客户端的初始化消息
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                return

            message = json.loads(data)
            if message.get('type') == 'connect':
                username = message.get('username', f"Player_{self.client_id_counter}")

                # 分配客户端ID并添加到客户端列表
                with self.lock:
                    client_id = self.client_id_counter
                    self.client_id_counter += 1
                    self.clients[client_id] = (client_socket, client_address, username)

                    # 初始化玩家游戏状态
                    # 为新玩家随机分配一个值
                    random_value = random.randint(1, 255)
                    self.game_state["players"][client_id] = {
                        "position": [0, 0],  # 起始位置
                        "score": 0,
                        "username": username,
                        "value": random_value,
                        "target_value": random_value,
                        "base": 16,  # 默认十六进制
                        "memory_usage": 0,  # 内存使用量
                        "max_memory": 100,  # 最大内存容量
                        "memory_release_active": False,  # 内存释放状态
                        "memory_release_time": 0  # 内存释放状态变化时间
                    }

                # 发送欢迎消息和当前游戏状态
                welcome_msg = {
                    "type": "welcome",
                    "client_id": client_id,
                    "message": f"欢迎 {username} 加入游戏!",
                    "game_state": self.game_state
                }
                self.send_to_client(client_id, welcome_msg)

                # 广播新玩家加入的消息
                broadcast_msg = {
                    "type": "player_joined",
                    "client_id": client_id,
                    "username": username,
                    "message": f"玩家 {username} 已加入游戏!"
                }
                self.broadcast(broadcast_msg, exclude=client_id)

                print(f"客户端 {client_id} ({username}) 已连接: {client_address}")

                # 处理客户端消息
                while self.running:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break

                    try:
                        # 尝试处理可能连在一起的多个JSON消息
                        remaining_data = data
                        while remaining_data.strip():
                            try:
                                # 尝试解析一个完整的JSON对象
                                message = json.loads(remaining_data)
                                self.process_message(client_id, message)
                                break  # 成功解析整个字符串，退出循环
                            except json.JSONDecodeError as e:
                                # 如果错误位置信息可用，尝试分割数据
                                if hasattr(e, 'pos'):
                                    # 尝试在错误位置找到JSON对象的结束位置
                                    pos = e.pos
                                    # 尝试解析第一部分
                                    try:
                                        first_part = remaining_data[:pos]
                                        message = json.loads(first_part)
                                        self.process_message(client_id, message)
                                        # 处理剩余部分
                                        remaining_data = remaining_data[pos:]
                                    except:
                                        # 如果无法处理，终止循环
                                        print(f"无法解析部分JSON数据: {remaining_data}")
                                        break
                                else:
                                    # 无法确定错误位置，放弃处理
                                    print(f"收到无效的JSON数据: {remaining_data}")
                                    break
                    except Exception as e:
                        print(f"处理JSON数据时出错: {e}\n数据: {data}")

        except Exception as e:
            print(f"处理客户端 {client_id} 时出错: {e}")
        finally:
            # 客户端断开连接，从游戏中移除
            if client_id is not None:
                with self.lock:
                    if client_id in self.clients:
                        del self.clients[client_id]
                    if client_id in self.game_state["players"]:
                        username = self.game_state["players"][client_id]["username"]
                        del self.game_state["players"][client_id]

                        # 广播玩家离开的消息
                        leave_msg = {
                            "type": "player_left",
                            "client_id": client_id,
                            "username": username,
                            "message": f"玩家 {username} 已离开游戏!"
                        }
                        self.broadcast(leave_msg)
                        print(f"客户端 {client_id} ({username}) 已断开连接")

            try:
                client_socket.close()
            except:
                pass

    def process_message(self, client_id, message):
        # 处理从客户端接收到的消息
        message_type = message.get('type')

        if message_type == 'base_change':
            # 处理进制变换请求
            new_base = message.get('base', 16)
            with self.lock:
                if client_id in self.game_state["players"]:
                    self.game_state["players"][client_id]["base"] = new_base
                    # 发送更新消息给所有客户端
                    self._send_base_change_notification(client_id, new_base)

        elif message_type == 'move':
            # 处理玩家移动
            new_position = message.get('position', [0, 0])
            with self.lock:
                if client_id in self.game_state["players"]:
                    self.game_state["players"][client_id]["position"] = new_position

            # 广播玩家位置更新 - 这是一个高优先级消息，立即发送给所有客户端
            update_msg = {
                "type": "player_moved",
                "client_id": client_id,
                "position": new_position
            }
            self.broadcast(update_msg)
            
            # 同时触发一次游戏状态更新，确保所有客户端都能接收到最新状态
            self._send_game_state_update()

        elif message_type == 'player_update':
            # 处理玩家值更新
            new_value = message.get('value', 0)
            memory_usage = message.get('memory_usage', 0)
            memory_release_active = message.get('memory_release_active', None)
            with self.lock:
                if client_id in self.game_state["players"]:
                    self.game_state["players"][client_id]["value"] = new_value
                    # 更新内存使用量
                    self.game_state["players"][client_id]["memory_usage"] = memory_usage
                    # 更新内存释放状态(如果提供了)
                    if memory_release_active is not None:
                        self.game_state["players"][client_id]["memory_release_active"] = memory_release_active
                    print(f"更新玩家 {client_id} 的值为 {new_value}，内存使用量为 {memory_usage}")
            
            # 广播玩家值更新
            update_msg = {
                "type": "player_value_updated",
                "client_id": client_id,
                "value": new_value,
                "memory_usage": memory_usage,
                "memory_release_active": self.game_state["players"][client_id]["memory_release_active"] if client_id in self.game_state["players"] else False
            }
            self.broadcast(update_msg)
            
            # 同时触发一次游戏状态更新
            self._send_game_state_update()
            
        elif message_type == 'chat':
            # 处理聊天消息
            chat_content = message.get('content', '')
            username = self.game_state["players"][client_id]["username"]

            chat_msg = {
                "type": "chat",
                "client_id": client_id,
                "username": username,
                "content": chat_content,
                "timestamp": time.time()
            }
            self.broadcast(chat_msg)

        elif message_type == 'action':
            # 处理玩家动作
            action = message.get('action', '')

            if action == 'skill' or action == 'hex_skill' or action == 'decimal_skill':
                # 处理技能使用
                skill_name = message.get('skill_name', '')
                skill_index = message.get('skill_index', -1)  # 对于十六进制技能
                
                # 检查是否是内存释放技能
                if action == 'decimal_skill' and skill_index == 3:
                    # 激活内存释放状态
                    if client_id in self.game_state["players"]:
                        self.game_state["players"][client_id]["memory_release_active"] = True
                        self.game_state["players"][client_id]["memory_release_time"] = time.time()
                
                # 获取玩家位置
                player_position = self.game_state["players"][client_id]["position"] if client_id in self.game_state["players"] else [0, 0]
                
                # 对于需要检查射程的技能，验证目标是否在范围内
                can_use_skill = True
                if skill_name in ["AND", "OR", "XOR", "开火", "爆炸"]:
                    # 检查是否有目标在射程内
                    targets_in_range = False
                    for other_id, other_player in self.game_state["players"].items():
                        if other_id != client_id:
                            other_pos = other_player["position"]
                            if self._check_skill_range(player_position, other_pos, skill_name):
                                targets_in_range = True
                                break
                    
                    if not targets_in_range:
                        # 没有目标在射程内
                        result = f"没有目标在{skill_name}技能射程内"
                        can_use_skill = False
                
                if can_use_skill:
                    result = self._process_skill(client_id, skill_name)
                
                # 获取运算符效果信息
                operator_effect = {
                    "symbol": self._get_operator_symbol(skill_name),
                    "targets": []
                }
                
                # 对于需要附近玩家的技能，添加目标玩家位置
                if skill_name in ["AND", "OR", "XOR"]:
                    # 获取附近玩家位置
                    nearby_players = []
                    for other_id, other_player in self.game_state["players"].items():
                        if other_id != client_id:
                            other_pos = other_player["position"]
                            distance = math.sqrt(max(0, (player_position[0] - other_pos[0]) ** 2 + (player_position[1] - other_pos[1]) ** 2))
                            if distance < 100:  # 与处理技能相同的距离阈值
                                nearby_players.append(other_pos)
                    operator_effect["targets"] = nearby_players
                
                # 获取内存使用量
                memory_usage = message.get('memory_usage', 0)
                if client_id in self.game_state["players"]:
                    # 更新玩家内存使用量
                    self.game_state["players"][client_id]["memory_usage"] = memory_usage
                
                # 广播动作结果
                action_result = {
                    "type": "action_result",
                    "client_id": client_id,
                    "action": action,
                    "skill_name": skill_name,
                    "player_position": player_position,
                    "operator_effect": operator_effect,
                    "result": result,
                    "memory_usage": memory_usage
                }
                
                # 如果是十六进制技能或十进制技能，添加技能索引
                if skill_index >= 0:
                    action_result["skill_index"] = skill_index
                    
                self.broadcast(action_result)
            else:
                # 处理其他类型的动作
                # 广播动作结果
                action_result = {
                    "type": "action_result",
                    "client_id": client_id,
                    "action": action,
                    "result": "unknown_action"
                }
                self.broadcast(action_result)

    def send_to_client(self, client_id, message):
        # 向特定客户端发送消息
        if client_id in self.clients:
            client_socket = self.clients[client_id][0]
            try:
                client_socket.send(json.dumps(message).encode('utf-8'))
            except Exception as e:
                print(f"向客户端 {client_id} 发送消息时出错: {e}")

    def broadcast(self, message, exclude=None):
        # 向所有客户端广播消息，可选择排除特定客户端
        for client_id, (client_socket, _, _) in list(self.clients.items()):
            if exclude is not None and client_id == exclude:
                continue

            try:
                client_socket.send(json.dumps(message).encode('utf-8'))
            except Exception as e:
                print(f"向客户端 {client_id} 广播消息时出错: {e}")

    def _send_base_change_notification(self, client_id, new_base):
        # 向所有客户端发送进制变更通知
        player_position = self.game_state["players"][client_id]["position"] if client_id in self.game_state["players"] else [0, 0]
        base_change_msg = {
            "type": "base_changed",
            "client_id": client_id,
            "base": new_base,
            "timestamp": time.time(),
            "priority": "high",  # 添加高优先级标记
            "player_position": player_position  # 添加玩家位置信息
        }
        # 广播进制变更消息
        self.broadcast(base_change_msg)
        print(f"广播进制变更消息: 玩家 {client_id} 切换到 {new_base} 进制，位置: {player_position}")

        # 延迟一小段时间后发送一次完整游戏状态更新，确保所有客户端同步
        time.sleep(0.05)  # 50毫秒延迟
        self._send_game_state_update()

    def _update_animations(self):
        # 更新所有动画效果
        current_time = time.time()
        # 更新转换动画
        active_conversions = []
        for conv in self.game_state["base_conversions"]:
            elapsed = current_time - conv["start_time"]
            if elapsed < conv["duration"]:
                # 动画还在进行中
                progress = elapsed / conv["duration"]  # 0到1之间的进度值
                
                # 平滑更新玩家的值
                client_id = conv["client_id"]
                if client_id in self.game_state["players"]:
                    # 使用线性插值计算当前值
                    start = conv["start_value"]
                    end = conv["end_value"]
                    current = start + (end - start) * progress
                    self.game_state["players"][client_id]["value"] = int(current)
                    
                # 保留此动画继续处理
                active_conversions.append(conv)
            else:
                # 动画结束，确保最终值正确设置
                client_id = conv["client_id"]
                if client_id in self.game_state["players"]:
                    self.game_state["players"][client_id]["value"] = conv["end_value"]
        
        # 更新动画列表，只保留活跃的动画
        self.game_state["base_conversions"] = active_conversions
        
        # 定期向所有客户端发送游戏状态更新
        # 增加发送频率，确保游戏状态更及时地同步
        if len(self.clients) > 0 and (len(active_conversions) > 0 or random.random() < 0.6):
            self._send_game_state_update()

    def _send_game_state_update(self):
        # 发送游戏状态更新到所有客户端
        # 确保每个客户端都收到最新的游戏状态，包括所有玩家的位置和内存释放状态
        
        # 创建包含内存释放状态的游戏状态
        game_state_with_memory_release = self.game_state.copy()
        
        # 确保每个玩家的内存释放状态都包含在游戏状态中
        for player_id, player_data in self.game_state["players"].items():
            memory_release_active = player_data.get("memory_release_active", False)
            if "players" not in game_state_with_memory_release:
                game_state_with_memory_release["players"] = {}
            if player_id not in game_state_with_memory_release["players"]:
                game_state_with_memory_release["players"][player_id] = {}
            game_state_with_memory_release["players"][player_id]["memory_release_active"] = memory_release_active
        
        update_msg = {
            "type": "game_update",
            "game_state": game_state_with_memory_release,
            "timestamp": time.time()  # 添加时间戳以帮助客户端判断最新状态
        }
        self.broadcast(update_msg)

    def game_loop(self):
        # 游戏主循环，处理游戏逻辑、碰撞检测、NPC行为等
        fps = 30
        frame_time = 1.0 / fps


        while self.running:
            start_time = time.time()

            # 在这里更新游戏状态、处理游戏逻辑等
            with self.lock:
                # 更新动画效果
                self._update_animations()
                # 更新子弹
                self._update_bullets(frame_time)
                
                # 监控内存释放状态
                current_time = time.time()
                for player_id, player_data in self.game_state["players"].items():
                    if player_data.get("memory_release_active", False):
                        release_time = player_data.get("memory_release_time", 0)
                        # 如果内存释放状态持续超过10秒，重置状态
                        if current_time - release_time > 10:
                            player_data["memory_release_active"] = False
                            player_data["memory_release_time"] = current_time
                    
                    # 如果玩家内存使用量为0，也重置内存释放状态
                    if player_data.get("memory_usage", 0) == 0 and player_data.get("memory_release_active", False):
                        player_data["memory_release_active"] = False
                        player_data["memory_release_time"] = current_time

            # 计算等待时间以维持稳定的帧率
            elapsed = time.time() - start_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)
    def _check_skill_range(self, player_pos, target_pos, skill_name):
        """检查玩家与目标的距离是否在射程内"""
        distance = math.sqrt(max(0, (player_pos[0] - target_pos[0]) ** 2 + (player_pos[1] - target_pos[1]) ** 2))
        
        # 定义不同技能的射程限制
        if skill_name in ["开火", "爆炸"]:
            return distance <= 600
        elif skill_name in ["AND", "OR", "XOR"]:
            return distance <= 200
        else:
            # 其他技能无射程限制
            return True
            
    def _process_skill(self, client_id, skill_name):
        """处理玩家使用的技能，并应用相应的逻辑运算"""
        if client_id not in self.game_state["players"]:
            return "player_not_found"

        player = self.game_state["players"][client_id]
        current_value = player["value"]
        username = player["username"]

        # 获取玩家位置
        player_pos = player["position"]
        nearby_players = []

        for other_id, other_player in self.game_state["players"].items():
            if other_id != client_id:
                other_pos = other_player["position"]
                # 检查射程
                if self._check_skill_range(player_pos, other_pos, skill_name):
                    nearby_players.append(other_player)

        # 按位非运算不需要附近玩家
        if skill_name == "NOT":
            # 按位非运算
            # 对自己的值进行按位非运算
            result_value = ~current_value & 0xFF  # 限制为8位
            old_value = player["value"]
            player["value"] = result_value
            player["target_value"] = result_value
            # 广播值变化
            return "成功执行NOT运算"
            
        # 需要附近玩家的运算(AND, OR, XOR)
        operations = {
            "AND": lambda x, y: x & y,
            "OR": lambda x, y: x | y,
            "XOR": lambda x, y: x ^ y
        }
        distances = []
        for other_player in nearby_players:
            distance = math.sqrt(max(0, (player_pos[0] - other_player["position"][0]) ** 2 + (player_pos[1] - other_player["position"][1]) ** 2))
            distances.append(distance)
        # 创建元组列表(距离, 玩家ID, 玩家对象)
        player_tuples = []
        for i, other_player in enumerate(nearby_players):
            # 为每个附近玩家找到对应的ID
            for other_id, game_player in self.game_state["players"].items():
                if other_player is game_player:  # 通过对象引用比较
                    player_tuples.append((distances[i], other_id, other_player))
                    break
        
        # 按距离排序
        player_tuples.sort()  # 按第一个元素(距离)排序
        
        # 执行对应的位运算
        if skill_name in operations:
            if player_tuples:  # 使用新的玩家元组列表
                # 将最近的玩家作为目标
                _, target_id, target_player = player_tuples[0]  # 获取目标玩家ID和对象
                target_value = target_player["value"]
                current_value = operations[skill_name](current_value, target_value)
                # 设置新值
                old_value = player["value"]
                target_player["value"] = current_value
                target_player["memory_usage"] = target_player["memory_usage"] + current_value % 8
                # 广播值变化
                # self._broadcast_value_change(client_id, old_value, current_value)
                update_msg = {
                    "type": "player_value_updated",
                    "client_id": target_id,  # 使用从元组中获取的ID
                    "value": target_player["value"],
                    "memory_usage": target_player["memory_usage"],
                    "memory_release_active": self.game_state["players"][target_id]["memory_release_active"] if target_id in self.game_state["players"] else False
                }
                self.broadcast(update_msg)
                return f"成功对{len(nearby_players)}个玩家执行{skill_name}运算"
            else:
                return f"射程内没有玩家，无法执行{skill_name}运算"

        # 处理开火技能 - 发射子弹
        if skill_name == "开火":
            # 找到射程内最近的玩家作为目标
            if nearby_players:
                # 计算所有玩家的距离
                distances = []
                for other_player in nearby_players:
                    other_pos = other_player["position"]
                    distance = math.sqrt(max(0, (player_pos[0] - other_pos[0]) ** 2 + (player_pos[1] - other_pos[1]) ** 2))
                    distances.append(distance)

                # 按距离排序找到最近的玩家
                target_player = [x for _, x in sorted(zip(distances, nearby_players))][0]
                target_pos = target_player["position"]

                # 计算子弹发射方向（从玩家指向目标）
                dx = target_pos[0] - player_pos[0]
                dy = target_pos[1] - player_pos[1]
                # 标准化方向向量
                magnitude = math.sqrt(max(0, dx**2 + dy**2))
                if magnitude > 0:
                    dx /= magnitude
                    dy /= magnitude
                else:
                    # 如果玩家和目标位置重合，设置一个默认方向（向右）
                    dx, dy = 1, 0

                # 根据玩家值计算子弹数量（最多28个，最少1个，确保能构成倒等腰三角形）
                # 计算子弹伤害值（1-32，随玩家值增加而增加）
                # 计算子弹速度（随玩家值增加而增加）

                player_value = max(1, min(255, player["value"]))

                # 计算子弹数量，确保能形成倒等腰三角形
                # 倒等腰三角形的行数需要是1, 3, 6, 10, 15, 21, 28...
                triangle_rows = [1, 3, 6, 10, 15, 21, 28]
                # 根据玩家值选择行数，值越大行数越少
                num_bullets = 1
                row_index = min(len(triangle_rows) - 1, 6 - (player_value // 40))
                for i in range(row_index):
                    num_bullets = triangle_rows[row_index - i]

                # 计算子弹伤害（1-32）
                bullet_damage = max(1, min(32, 32 // num_bullets))

                # 计算子弹速度（基础速度 + 根据玩家值增加）
                bullet_speed_base = 100
                bullet_speed_factor = player_value / 255 * 300  # 最多增加7的速度
                bullet_speed = bullet_speed_base + bullet_speed_factor

                # 创建子弹阵列（倒等腰三角形）
                bullets_created = []
                current_row = 1
                total_bullets = 0
                spread_angle = 0.2  # 子弹扩散角度

                # 创建倒等腰三角形的子弹阵列
                while total_bullets < num_bullets:
                    for i in range(current_row):
                        if total_bullets >= num_bullets:
                            break

                        # 计算扩散角度，使子弹形成三角形
                        angle_offset = (i - (current_row - 1) / 2) * spread_angle

                        # 计算旋转后的方向
                        try:
                            rotated_dx = dx * math.cos(angle_offset) - dy * math.sin(angle_offset)
                            rotated_dy = dx * math.sin(angle_offset) + dy * math.cos(angle_offset)
                            # 确保没有复数产生
                            if isinstance(rotated_dx, complex) or isinstance(rotated_dy, complex):
                                rotated_dx = 1.0 if rotated_dx == 0 else float(rotated_dx.real)
                                rotated_dy = 0.0 if rotated_dy == 0 else float(rotated_dy.real)
                        except Exception:
                            # 出现任何错误时使用默认方向
                            rotated_dx, rotated_dy = 1.0, 0.0

                        # 创建子弹对象
                        bullet = {
                            "id": self.bullet_id_counter,
                            "owner": client_id,
                            "position": player_pos.copy(),  # 从玩家位置发射
                            "velocity": [rotated_dx * bullet_speed, rotated_dy * bullet_speed],
                            "damage": bullet_damage,
                            "created_time": time.time(),
                            "char": "*",  # 子弹字符
                            "color": (212, 212, 212)  # 子弹颜色
                        }

                        self.bullet_id_counter += 1
                        self.game_state["bullets"].append(bullet)
                        bullets_created.append(bullet)
                        total_bullets += 1

                    current_row += 1

                # 广播子弹创建消息
                bullet_msg = {
                    "type": "bullets_created",
                    "bullets": bullets_created,
                    "owner_id": client_id
                }
                self.broadcast(bullet_msg)

                # 开火技能使用者增加10点内存
                player["memory_usage"] += 10

                # 更新玩家状态
                update_msg = {
                    "type": "player_value_updated",
                    "client_id": client_id,
                    "value": player["value"],
                    "memory_usage": player["memory_usage"],
                    "memory_release_active": player.get("memory_release_active", False)
                }
                self.broadcast(update_msg)

                return f"成功发射{len(bullets_created)}个子弹，目标为玩家{target_player['username']}"
            else:
                return "射程内没有可攻击的目标"

        return "未知技能"
        
    def _get_operator_symbol(self, skill_name):
        symbols = {
            "AND": "&",
            "OR": "|",
            "NOT": "~",
            "XOR": "^"
        }
        return symbols.get(skill_name, "")
    def _update_bullets(self, delta_time):
        """更新所有子弹位置并检测碰撞"""
        bullets_to_remove = []

        for bullet in self.game_state["bullets"]:
            # 更新子弹位置
            try:
                # 处理可能的复数
                vx = float(bullet["velocity"][0].real) if isinstance(bullet["velocity"][0], complex) else float(bullet["velocity"][0])
                vy = float(bullet["velocity"][1].real) if isinstance(bullet["velocity"][1], complex) else float(bullet["velocity"][1])
                
                # 确保位置也是实数
                px = float(bullet["position"][0].real) if isinstance(bullet["position"][0], complex) else float(bullet["position"][0])
                py = float(bullet["position"][1].real) if isinstance(bullet["position"][1], complex) else float(bullet["position"][1])
                
                # 更新位置
                bullet["position"][0] = px + vx * delta_time
                bullet["position"][1] = py + vy * delta_time
            except Exception:
                # 如果出现任何问题，标记子弹移除
                bullets_to_remove.append(bullet)

            # 检查子弹寿命
            if time.time() - bullet["created_time"] > 5.0:  # 5秒后子弹消失
                bullets_to_remove.append(bullet)
                continue

            # 检测与玩家的碰撞
            bullet_pos = bullet["position"]
            bullet_owner_id = bullet["owner"]

            for player_id, player in self.game_state["players"].items():
                # 不与自己碰撞
                if player_id == bullet_owner_id:
                    continue

                player_pos = player["position"]
                # 简单的圆形碰撞检测
                try:
                    # 确保位置值都是实数
                    bx = float(bullet_pos[0].real) if isinstance(bullet_pos[0], complex) else float(bullet_pos[0])
                    by = float(bullet_pos[1].real) if isinstance(bullet_pos[1], complex) else float(bullet_pos[1])
                    px = float(player_pos[0].real) if isinstance(player_pos[0], complex) else float(player_pos[0])
                    py = float(player_pos[1].real) if isinstance(player_pos[1], complex) else float(player_pos[1])
                    distance = math.sqrt(max(0, (bx - px) ** 2 + (by - py) ** 2))
                except Exception:
                    # 出现任何错误时使用一个大于碰撞距离的值
                    distance = 100

                if distance < 20:  # 碰撞距离，可以根据需要调整
                    # 处理碰撞
                    damage = bullet["damage"]

                    # 增加被击中玩家的内存使用
                    player["memory_usage"] += damage

                    # 广播子弹击中消息
                    hit_msg = {
                        "type": "bullet_hit",
                        "bullet_id": bullet["id"],
                        "target_id": player_id,
                        "damage": damage,
                        "position": bullet_pos.copy()
                    }
                    self.broadcast(hit_msg)

                    # 更新被击中玩家状态
                    update_msg = {
                        "type": "player_value_updated",
                        "client_id": player_id,
                        "value": player["value"],
                        "memory_usage": player["memory_usage"],
                        "memory_release_active": player.get("memory_release_active", False)
                    }
                    self.broadcast(update_msg)

                    # 子弹击中后移除
                    bullets_to_remove.append(bullet)
                    break

        # 移除需要删除的子弹
        for bullet in bullets_to_remove:
            if bullet in self.game_state["bullets"]:
                self.game_state["bullets"].remove(bullet)

if __name__ == "__main__":
    server = GameServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("接收到中断信号，正在关闭服务器...")
    finally:
        server.stop()