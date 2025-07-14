import argparse
import threading
import time
import random
from server import GameServer
from client import GameClient
def start_server(host='localhost', port=5555):
    # 启动游戏服务器
    server = GameServer(host=host, port=port)
    try:
        print(f"启动服务器 {host}:{port}")
        server.start()
    except KeyboardInterrupt:
        print("服务器被用户中断")
    finally:
        server.stop()

def start_client(host='localhost', port=5555, username=None, screen_width=800, screen_height=600):
    # 启动游戏客户端
    client = GameClient(host=host, port=port, username=username, screen_width=screen_width, screen_height=screen_height)

    def handle_message(message):
        # 处理从服务器接收到的消息
        message_type = message.get('type')
        if message_type in ['welcome', 'player_joined', 'player_left']:
            print(f"[系统] {message.get('message', '')}")

    client.set_message_callback(handle_message)

    if client.connect():
        print(f"已连接到服务器 {host}:{port}")
        try:
            client.run_game()
        except KeyboardInterrupt:
            print("客户端被用户中断")
        finally:
            client.disconnect()
    else:
        print("无法连接到服务器")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="游戏服务器和客户端")
    parser.add_argument('--mode', choices=['server', 'client', 'both'], default='both',
                        help='运行模式: server, client, 或 both')
    parser.add_argument('--host', default='localhost', help='服务器主机名')
    parser.add_argument('--port', type=int, default=5555, help='服务器端口')
    parser.add_argument('--username', help='客户端用户名')
    parser.add_argument('--width', type=int, default=800, help='游戏窗口宽度')
    parser.add_argument('--height', type=int, default=600, help='游戏窗口高度')
    args = parser.parse_args()

    if args.mode == 'server':
        # 只启动服务器
        start_server(args.host, args.port)
    elif args.mode == 'client':
        # 只启动客户端
        start_client(args.host, args.port, args.username, args.width, args.height)
    elif args.mode == 'both':
        # 在单独的线程中启动服务器
        server_thread = threading.Thread(target=start_server, args=(args.host, args.port))
        server_thread.daemon = True
        server_thread.start()

        # 等待服务器启动
        time.sleep(1)

        # 在主线程中启动客户端
        start_client(args.host, args.port, args.username, args.width, args.height)
