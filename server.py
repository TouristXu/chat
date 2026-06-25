import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
from datetime import datetime
import os
import hashlib
import base64

class ChatServer:
    def __init__(self, root):
        self.root = root
        self.root.title("局域网聊天服务器")
        self.root.geometry("650x750")
        
        # 服务器配置
        self.host = '0.0.0.0'  # 监听所有网络接口
        self.port = 8888
        self.server_socket = None
        self.clients = {}  # {client_socket: client_address}
        self.client_names = {}  # {client_socket: client_name}
        self.client_types = {}  # {client_socket: 'tcp' or 'websocket'}
        self.running = False
        
        # WebSocket配置
        self.websocket_guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        
        # 日志配置
        self.log_file = None
        self.log_file_path = ""
        
        # 系统托盘图标
        self.tray_icon = None
        self.minimized = False
        
        # 创建界面
        self.create_ui()
        
        # 设置关闭事件处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 启动服务器
        self.start_server()
    
    def create_tray_icon(self):
        """创建系统托盘图标"""
        try:
            # 创建一个简单的托盘图标（使用tkinter的iconify功能）
            self.root.iconbitmap(default='')
            # 设置窗口图标
            self.root.iconphoto(True, tk.PhotoImage(data=b'R0lGODlhEAAQAMQAAORHHOVSKudfOulrSOp3WOyDZu6QdvCchPGolfO0o/XBs/fNwfjZ0frl3/zy7////wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH5BAkAABAALAAAAAAQABAAAAVVICSOZGlCQAosJ6mu7fiyZeKqNKToQGDsM8hBADgUXoGAiqhSvp5QAnQKGIgUhwFUYLCVDFCrKUE1lBavAViFIDlTImbKC5Gm2hB0SlBCBMQiB0UjIQA7'))
            
            # 创建右键菜单
            self.tray_menu = tk.Menu(self.root, tearoff=0)
            self.tray_menu.add_command(label="显示窗口", command=self.show_window)
            self.tray_menu.add_command(label="退出", command=self.quit_server)
            
            # 添加一个隐藏的Toplevel窗口用于托盘菜单
            self.tray_popup = tk.Toplevel(self.root)
            self.tray_popup.withdraw()
            self.tray_popup.bind("<Button-3>", self.show_tray_menu)
            
            self.add_message("系统", "服务器已最小化到任务栏，右键点击图标可恢复窗口", 'system')
            
        except Exception as e:
            self.add_message("系统", f"创建托盘图标失败: {str(e)}", 'system')
    
    def show_tray_menu(self, event):
        """显示托盘右键菜单"""
        self.tray_menu.post(event.x_root, event.y_root)
    
    def show_window(self):
        """显示窗口"""
        self.root.deiconify()
        self.root.lift()
        self.minimized = False
    
    def hide_window(self):
        """隐藏窗口到任务栏"""
        self.root.iconify()
        self.minimized = True
    
    def create_ui(self):
        """创建用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 服务器信息框架
        info_frame = ttk.LabelFrame(main_frame, text="服务器信息", padding="10")
        info_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(info_frame, text="状态：未启动", foreground='red')
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.address_label = ttk.Label(info_frame, text=f"监听地址：{self.host}:{self.port}")
        self.address_label.grid(row=1, column=0, sticky=tk.W)
        
        self.client_count_label = ttk.Label(info_frame, text="连接客户端：0")
        self.client_count_label.grid(row=2, column=0, sticky=tk.W)
        
        self.log_file_label = ttk.Label(info_frame, text="日志文件：未创建", foreground='gray')
        self.log_file_label.grid(row=3, column=0, sticky=tk.W)
        
        # 关闭服务器按钮
        self.close_button = ttk.Button(info_frame, text="关闭服务器", command=self.quit_server, state='disabled')
        self.close_button.grid(row=4, column=0, pady=(10, 0))
        
        # 客户端列表框架
        client_frame = ttk.LabelFrame(main_frame, text="连接的客户端", padding="10")
        client_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        self.client_listbox = tk.Listbox(client_frame, width=25, height=15)
        self.client_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        client_scrollbar = ttk.Scrollbar(client_frame, orient=tk.VERTICAL, command=self.client_listbox.yview)
        client_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.client_listbox.config(yscrollcommand=client_scrollbar.set)
        
        # 消息显示框架
        message_frame = ttk.LabelFrame(main_frame, text="消息记录", padding="10")
        message_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        self.message_display = scrolledtext.ScrolledText(message_frame, width=40, height=15, state='disabled')
        self.message_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 消息输入框架
        input_frame = ttk.LabelFrame(main_frame, text="发送消息", padding="10")
        input_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.message_entry = ttk.Entry(input_frame, width=50)
        self.message_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        self.message_entry.bind('<Return>', lambda event: self.send_server_message())
        
        send_button = ttk.Button(input_frame, text="发送", command=self.send_server_message)
        send_button.grid(row=0, column=1)
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(1, weight=1)
        client_frame.columnconfigure(0, weight=1)
        client_frame.rowconfigure(0, weight=1)
        message_frame.columnconfigure(0, weight=1)
        message_frame.rowconfigure(0, weight=1)
        input_frame.columnconfigure(0, weight=1)
        
        # 配置消息显示标签
        self.message_display.tag_config('server', foreground='blue')
        self.message_display.tag_config('client', foreground='green')
        self.message_display.tag_config('system', foreground='gray')
        self.message_display.tag_config('error', foreground='red')
    
    def get_local_ips(self):
        """获取本地所有网络接口的IP地址"""
        ips = []
        try:
            hostname = socket.gethostname()
            ip_addresses = socket.gethostbyname_ex(hostname)[2]
            for ip in ip_addresses:
                # 过滤掉IPv6和回环地址
                if '.' in ip and not ip.startswith('127.'):
                    ips.append(ip)
        except:
            pass
        
        # 如果没有找到有效IP，尝试另一种方法
        if not ips:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                ips.append(ip)
            except:
                ips.append("127.0.0.1")
        
        return ips
    
    def create_log_file(self):
        """创建日志文件"""
        try:
            # 生成日志文件名，包含日期
            log_date = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file_path = f"chat_log_{log_date}.txt"
            self.log_file = open(self.log_file_path, 'w', encoding='utf-8')
            self.log_file.write(f"=== 服务器启动日志 ===\n")
            self.log_file.write(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.log_file.write(f"监听端口: {self.port}\n")
            self.log_file.write("="*50 + "\n\n")
            self.log_file.flush()
            self.log_file_label.config(text=f"日志文件：{self.log_file_path}", foreground='blue')
            self.add_message("系统", f"日志文件已创建：{self.log_file_path}", 'system')
        except Exception as e:
            self.add_message("错误", f"创建日志文件失败：{str(e)}", 'error')
        
    def write_log(self, message_type, sender, message):
        """写入日志到文件"""
        if self.log_file:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_line = f"[{timestamp}] [{message_type}] {sender}: {message}\n"
                self.log_file.write(log_line)
                self.log_file.flush()
            except Exception as e:
                pass
    
    def start_server(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            # 创建日志文件
            self.create_log_file()
            
            self.status_label.config(text="状态：运行中", foreground='green')
            
            # 获取并显示所有本地IP地址
            local_ips = self.get_local_ips()
            ip_list = ", ".join(local_ips)
            self.address_label.config(text=f"监听地址：{ip_list}:{self.port}")
            self.add_message("系统", f"服务器启动成功，监听端口 {self.port}", 'system')
            self.add_message("系统", f"可用连接地址：{ip_list}:{self.port}", 'system')
            
            # 启用关闭服务器按钮
            self.close_button.config(state='normal')
            
            # 启动接受连接的线程
            accept_thread = threading.Thread(target=self.accept_clients, daemon=True)
            accept_thread.start()
            
        except Exception as e:
            self.status_label.config(text=f"状态：启动失败 - {str(e)}", foreground='red')
            self.add_message("错误", f"服务器启动失败：{str(e)}", 'error')
    
    def accept_clients(self):
        """接受客户端连接"""
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                self.add_message("系统", f"新连接来自 {client_address}", 'system')
                
                # 启动处理客户端的线程
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    self.add_message("错误", f"接受连接失败：{str(e)}", 'error')
    
    def handle_client(self, client_socket, client_address):
        """处理客户端消息"""
        try:
            print(f"\n{'='*60}")
            print(f"[客户端连接] 新连接来自: {client_address}")
            print(f"[客户端连接] 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}")
            
            # 检测连接类型（TCP或WebSocket）
            first_data = client_socket.recv(4096)
            if not first_data:
                print(f"[客户端连接] 空数据，连接关闭")
                return
            
            print(f"[连接检测] 接收到初始数据: {len(first_data)} bytes")
            print(f"[连接检测] 数据前100字节: {first_data[:100]}")
            
            is_websocket = self.is_websocket_request(first_data)
            
            if is_websocket:
                print(f"[连接检测] 检测到WebSocket连接请求")
                
                # WebSocket握手
                if not self.websocket_handshake(client_socket, first_data):
                    print(f"[WebSocket] 握手失败")
                    client_socket.close()
                    return
                
                print(f"[WebSocket] 握手成功")
                
                # 等待WebSocket客户端发送用户名（设置超时）
                client_socket.settimeout(10.0)
                print(f"[WebSocket] 等待用户名，超时10秒...")
                name_data = self.websocket_recv(client_socket)
                client_socket.settimeout(None)  # 恢复默认超时
                
                if not name_data:
                    print(f"[WebSocket] 未收到用户名或超时")
                    client_socket.close()
                    return
                
                client_name = name_data
                client_type = 'websocket'
                print(f"[WebSocket] 用户名: {client_name}")
                self.add_message("系统", f"WebSocket客户端 {client_name} ({client_address}) 加入聊天", 'system')
            else:
                # TCP客户端
                client_name = first_data.decode('utf-8')
                client_type = 'tcp'
                print(f"[连接检测] 检测到TCP连接请求")
                print(f"[TCP] 用户名: {client_name}")
                self.add_message("系统", f"TCP客户端 {client_name} ({client_address}) 加入聊天", 'system')
            
            # 注册客户端
            self.clients[client_socket] = client_address
            self.client_names[client_socket] = client_name
            self.client_types[client_socket] = client_type
            
            print(f"[客户端注册] 客户端类型: {client_type}")
            print(f"[客户端注册] 当前连接数: {len(self.clients)}")
            
            # 更新客户端列表
            self.update_client_list()
            
            # 通知所有客户端有新用户加入
            self.broadcast_message({
                'type': 'system',
                'message': f'{client_name} 加入了聊天'
            })
            
            print(f"[消息广播] 通知所有客户端: {client_name} 加入了聊天")
            
            # 接收客户端消息
            while self.running:
                try:
                    if client_type == 'websocket':
                        data = self.websocket_recv(client_socket)
                    else:
                        data = client_socket.recv(1024)
                    
                    if data:
                        message = data
                        self.broadcast_message({
                            'type': 'client',
                            'name': client_name,
                            'message': message
                        })
                        self.add_message(client_name, message, 'client')
                    else:
                        break
                except Exception as e:
                    if self.running:
                        self.add_message("错误", f"接收消息失败：{str(e)}", 'error')
                    break
            
            # 客户端断开
            self.remove_client(client_socket)
            
        except Exception as e:
            if self.running:
                self.add_message("错误", f"处理客户端失败：{str(e)}", 'error')
            try:
                client_socket.close()
            except:
                pass
    
    def is_websocket_request(self, data):
        """检测是否为WebSocket请求"""
        try:
            data_str = data.decode('utf-8')
            return 'upgrade: websocket' in data_str.lower()
        except:
            return False
    
    def websocket_handshake(self, client_socket, data):
        """WebSocket握手"""
        try:
            data_str = data.decode('utf-8')
            print(f"[WebSocket握手] 开始处理握手请求")
            print(f"[WebSocket握手] 请求头前200字节:\n{data_str[:200]}")
            
            headers = {}
            for line in data_str.split('\r\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            if 'Sec-WebSocket-Key' not in headers:
                print(f"[WebSocket握手] 失败 - 缺少Sec-WebSocket-Key")
                return False
            
            sec_key = headers['Sec-WebSocket-Key']
            print(f"[WebSocket握手] Sec-WebSocket-Key: {sec_key}")
            
            accept_key = base64.b64encode(
                hashlib.sha1((sec_key + self.websocket_guid).encode()).digest()
            ).decode()
            print(f"[WebSocket握手] 生成Sec-WebSocket-Accept: {accept_key}")
            
            response = (
                f"HTTP/1.1 101 Switching Protocols\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n"
                f"\r\n"
            )
            
            client_socket.send(response.encode())
            print(f"[WebSocket握手] 发送握手响应成功")
            return True
            
        except Exception as e:
            print(f"[WebSocket握手] 异常 - {type(e).__name__}: {str(e)}")
            self.add_message("错误", f"WebSocket握手失败：{str(e)}", 'error')
            return False
    
    def websocket_recv(self, client_socket):
        """接收WebSocket消息"""
        try:
            data = client_socket.recv(1024)
            if not data:
                print(f"[WebSocket接收] 空数据，连接可能已断开")
                return None
            
            if len(data) < 2:
                print(f"[WebSocket接收] 数据太短 ({len(data)} bytes): {data}")
                return None
            
            fin = (data[0] >> 7) & 1
            opcode = data[0] & 0x0F
            mask = (data[1] >> 7) & 1
            payload_len = data[1] & 0x7F
            
            print(f"[WebSocket接收] 帧信息 - fin: {fin}, opcode: {opcode}, mask: {mask}, payload_len: {payload_len}")
            
            if opcode == 8:
                print(f"[WebSocket接收] 收到关闭帧")
                return None
            
            index = 2
            if payload_len == 126:
                payload_len = int.from_bytes(data[index:index+2], 'big')
                index += 2
                print(f"[WebSocket接收] 扩展长度: {payload_len}")
            elif payload_len == 127:
                payload_len = int.from_bytes(data[index:index+8], 'big')
                index += 8
                print(f"[WebSocket接收] 扩展长度(64位): {payload_len}")
            
            if mask:
                mask_key = data[index:index+4]
                index += 4
                print(f"[WebSocket接收] 掩码: {mask_key.hex()}")
            
            payload = data[index:index+payload_len]
            print(f"[WebSocket接收] 原始payload长度: {len(payload)}, 预期: {payload_len}")
            
            if mask:
                payload = bytes([payload[i] ^ mask_key[i % 4] for i in range(len(payload))])
            
            result = payload.decode('utf-8')
            print(f"[WebSocket接收] 解码结果: '{result}'")
            return result
            
        except socket.timeout:
            print(f"[WebSocket接收] 接收超时")
            return None
        except Exception as e:
            print(f"[WebSocket接收] 异常: {type(e).__name__}: {str(e)}")
            return None
    
    def websocket_send(self, client_socket, message):
        """发送WebSocket消息"""
        try:
            payload = message.encode('utf-8')
            payload_len = len(payload)
            
            frame = bytearray()
            frame.append(0x81)
            
            if payload_len < 126:
                frame.append(payload_len)
            elif payload_len < 65536:
                frame.append(126)
                frame.extend(payload_len.to_bytes(2, 'big'))
            else:
                frame.append(127)
                frame.extend(payload_len.to_bytes(8, 'big'))
            
            frame.extend(payload)
            
            client_socket.send(frame)
            return True
            
        except Exception as e:
            return False
    
    def broadcast_message(self, message_dict):
        """向所有客户端广播消息"""
        message_json = json.dumps(message_dict, ensure_ascii=False)
        
        disconnected_clients = []
        for client_socket in list(self.clients.keys()):
            try:
                client_type = self.client_types.get(client_socket, 'tcp')
                if client_type == 'websocket':
                    # WebSocket客户端发送帧
                    self.websocket_send(client_socket, message_json)
                else:
                    # TCP客户端发送原始数据
                    message_bytes = message_json.encode('utf-8')
                    client_socket.send(message_bytes)
            except:
                disconnected_clients.append(client_socket)
        
        # 移除断开的客户端
        for client_socket in disconnected_clients:
            self.remove_client(client_socket)
    
    def send_server_message(self):
        """服务器发送消息"""
        message = self.message_entry.get().strip()
        if message:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.broadcast_message({
                'type': 'server',
                'name': '服务器',
                'message': message,
                'timestamp': timestamp
            })
            self.add_message("服务器", message, 'server')
            self.message_entry.delete(0, tk.END)
    
    def remove_client(self, client_socket):
        """移除客户端"""
        if client_socket in self.clients:
            client_address = self.clients[client_socket]
            client_name = self.client_names.get(client_socket, str(client_address))
            
            try:
                client_socket.close()
            except:
                pass
            
            del self.clients[client_socket]
            if client_socket in self.client_names:
                del self.client_names[client_socket]
            
            self.update_client_list()
            
            # 通知其他客户端
            self.broadcast_message({
                'type': 'system',
                'message': f'{client_name} 离开了聊天'
            })
            
            self.add_message("系统", f"{client_name} 离开聊天", 'system')
    
    def update_client_list(self):
        """更新客户端列表显示"""
        self.client_listbox.delete(0, tk.END)
        for client_socket, client_name in self.client_names.items():
            client_address = self.clients[client_socket]
            self.client_listbox.insert(tk.END, f"{client_name} ({client_address[0]})")
        
        self.client_count_label.config(text=f"连接客户端：{len(self.clients)}")
    
    def add_message(self, sender, message, message_type='client'):
        """添加消息到显示区域"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {sender}: {message}\n"
        
        self.message_display.config(state='normal')
        self.message_display.insert(tk.END, formatted_message, message_type)
        self.message_display.config(state='disabled')
        self.message_display.see(tk.END)
        
        # 写入日志文件
        self.write_log(message_type.upper(), sender, message)
    
    def on_closing(self):
        """窗口关闭时的处理"""
        if self.running:
            # 如果服务器正在运行，提示确认
            if messagebox.askyesno("确认关闭", "服务器正在运行中，确定要关闭吗？所有连接的客户端将被断开。"):
                self.quit_server()
        else:
            self.root.destroy()
    
    def quit_server(self):
        """真正退出服务器"""
        if messagebox.askyesno("确认退出", "确定要退出服务器吗？所有连接的客户端将被断开。"):
            self.running = False
            
            # 先关闭服务器socket，打破 accept 的阻塞
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            
            # 通知所有客户端服务器关闭
            self.broadcast_message({
                'type': 'system',
                'message': '服务器即将关闭'
            })
            
            # 关闭所有客户端连接
            for client_socket in list(self.clients.keys()):
                try:
                    client_socket.close()
                except:
                    pass
            
            # 关闭日志文件
            if self.log_file:
                try:
                    self.log_file.write("\n" + "="*50 + "\n")
                    self.log_file.write(f"服务器关闭时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    self.log_file.write("=== 服务器关闭 ===")
                    self.log_file.close()
                except:
                    pass
            
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    server = ChatServer(root)
    root.protocol("WM_DELETE_WINDOW", server.on_closing)
    root.mainloop()