import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import json
from datetime import datetime

class ChatServer:
    def __init__(self, root):
        self.root = root
        self.root.title("局域网聊天服务器")
        self.root.geometry("600x700")
        
        # 服务器配置
        self.host = '0.0.0.0'  # 监听所有网络接口
        self.port = 8888
        self.server_socket = None
        self.clients = {}  # {client_socket: client_address}
        self.client_names = {}  # {client_socket: client_name}
        self.running = False
        
        # 创建界面
        self.create_ui()
        
        # 启动服务器
        self.start_server()
    
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
    
    def start_server(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            self.status_label.config(text="状态：运行中", foreground='green')
            self.add_message("系统", f"服务器启动成功，监听 {self.host}:{self.port}", 'system')
            
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
            # 接收客户端名称
            name_data = client_socket.recv(1024).decode('utf-8')
            if name_data:
                client_name = name_data
                self.clients[client_socket] = client_address
                self.client_names[client_socket] = client_name
                
                # 更新客户端列表
                self.update_client_list()
                
                # 通知所有客户端有新用户加入
                self.broadcast_message({
                    'type': 'system',
                    'message': f'{client_name} 加入了聊天'
                })
                
                self.add_message("系统", f"{client_name} ({client_address}) 加入聊天", 'system')
                
                # 接收客户端消息
                while self.running:
                    try:
                        data = client_socket.recv(1024)
                        if data:
                            message = data.decode('utf-8')
                            self.broadcast_message({
                                'type': 'client',
                                'name': client_name,
                                'message': message
                            })
                            self.add_message(client_name, message, 'client')
                        else:
                            break
                    except:
                        break
                
        except Exception as e:
            self.add_message("错误", f"处理客户端 {client_address} 时出错：{str(e)}", 'error')
        finally:
            self.remove_client(client_socket)
    
    def broadcast_message(self, message_dict):
        """向所有客户端广播消息"""
        message_json = json.dumps(message_dict, ensure_ascii=False)
        message_bytes = message_json.encode('utf-8')
        
        disconnected_clients = []
        for client_socket in list(self.clients.keys()):
            try:
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
    
    def on_closing(self):
        """窗口关闭时的处理"""
        self.running = False
        
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
        
        # 关闭服务器socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    server = ChatServer(root)
    root.protocol("WM_DELETE_WINDOW", server.on_closing)
    root.mainloop()