import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox
import json
import time
from datetime import datetime

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("局域网聊天客户端")
        self.root.geometry("500x600")
        
        # 客户端配置
        self.server_port = 8888
        self.client_socket = None
        self.connected = False
        self.client_name = ""
        self.running = False
        
        # 创建界面
        self.create_ui()
        
        # 询问用户名
        self.ask_username()
        
        # 搜索并连接服务器
        self.search_and_connect()
    
    def create_ui(self):
        """创建用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 连接状态框架
        status_frame = ttk.LabelFrame(main_frame, text="连接状态", padding="10")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="状态：未连接", foreground='red')
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.server_label = ttk.Label(status_frame, text="服务器：未连接")
        self.server_label.grid(row=1, column=0, sticky=tk.W)
        
        self.user_label = ttk.Label(status_frame, text="用户名：未设置")
        self.user_label.grid(row=2, column=0, sticky=tk.W)
        
        # 重新连接按钮
        reconnect_button = ttk.Button(status_frame, text="重新连接", command=self.reconnect)
        reconnect_button.grid(row=0, column=1, padx=(10, 0))
        
        # 消息显示框架
        message_frame = ttk.LabelFrame(main_frame, text="聊天消息", padding="10")
        message_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.message_display = scrolledtext.ScrolledText(message_frame, width=50, height=20, state='disabled')
        self.message_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 消息输入框架
        input_frame = ttk.LabelFrame(main_frame, text="发送消息", padding="10")
        input_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.message_entry = ttk.Entry(input_frame, width=40)
        self.message_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        self.message_entry.bind('<Return>', lambda event: self.send_message())
        self.message_entry.config(state='disabled')
        
        send_button = ttk.Button(input_frame, text="发送", command=self.send_message)
        send_button.grid(row=0, column=1)
        send_button.config(state='disabled')
        self.send_button = send_button
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        message_frame.columnconfigure(0, weight=1)
        message_frame.rowconfigure(0, weight=1)
        input_frame.columnconfigure(0, weight=1)
        
        # 配置消息显示标签
        self.message_display.tag_config('server', foreground='blue')
        self.message_display.tag_config('client', foreground='green')
        self.message_display.tag_config('self', foreground='purple')
        self.message_display.tag_config('system', foreground='gray')
        self.message_display.tag_config('error', foreground='red')
    
    def ask_username(self):
        """询问用户名"""
        while True:
            name = simpledialog.askstring("用户名", "请输入您的用户名:", parent=self.root)
            if name:
                name = name.strip()
                if name:
                    self.client_name = name
                    self.user_label.config(text=f"用户名：{self.client_name}")
                    break
                else:
                    messagebox.showerror("错误", "用户名不能为空！")
            else:
                # 用户取消输入，使用默认名称
                self.client_name = f"用户{int(time.time()) % 1000}"
                self.user_label.config(text=f"用户名：{self.client_name}")
                break
    
    def get_local_ip(self):
        """获取本地IP地址"""
        try:
            # 创建一个UDP socket来获取本地IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    def get_network_range(self, local_ip):
        """获取网络IP范围"""
        try:
            parts = local_ip.split('.')
            if len(parts) == 4:
                network_base = f"{parts[0]}.{parts[1]}.{parts[2]}"
                return [f"{network_base}.{i}" for i in range(1, 255)]
        except:
            pass
        return []
    
    def search_server(self):
        """搜索局域网内的服务器"""
        local_ip = self.get_local_ip()
        self.add_message("系统", f"正在搜索服务器... 本地IP: {local_ip}", 'system')
        
        # 获取网络范围
        ip_range = self.get_network_range(local_ip)
        
        if not ip_range:
            self.add_message("系统", "无法确定网络范围，尝试常见IP...", 'system')
            ip_range = ["127.0.0.1", "192.168.1.1", "192.168.0.1", "10.0.0.1"]
        
        # 限制搜索的IP数量，避免搜索太多
        search_ips = ip_range[:50]  # 最多搜索50个IP
        
        found_servers = []
        
        # 创建socket用于检测
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(0.1)  # 设置超时时间
        
        for ip in search_ips:
            try:
                result = test_socket.connect_ex((ip, self.server_port))
                if result == 0:
                    found_servers.append(ip)
                    self.add_message("系统", f"发现服务器: {ip}:{self.server_port}", 'system')
            except:
                pass
            except KeyboardInterrupt:
                break
        
        test_socket.close()
        
        return found_servers
    
    def connect_to_server(self, server_ip):
        """连接到指定服务器"""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)  # 设置连接超时
            self.client_socket.connect((server_ip, self.server_port))
            self.client_socket.settimeout(None)  # 移除超时
            
            # 发送用户名
            self.client_socket.send(self.client_name.encode('utf-8'))
            
            self.connected = True
            self.running = True
            
            # 更新UI状态
            self.status_label.config(text="状态：已连接", foreground='green')
            self.server_label.config(text=f"服务器：{server_ip}:{self.server_port}")
            self.message_entry.config(state='normal')
            self.send_button.config(state='normal')
            
            self.add_message("系统", f"成功连接到服务器 {server_ip}:{self.server_port}", 'system')
            
            # 启动接收消息的线程
            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
            
            return True
            
        except Exception as e:
            self.add_message("错误", f"连接服务器失败：{str(e)}", 'error')
            return False
    
    def search_and_connect(self):
        """搜索并连接到服务器"""
        # 在后台线程中搜索服务器
        search_thread = threading.Thread(target=self._search_and_connect_thread, daemon=True)
        search_thread.start()
    
    def _search_and_connect_thread(self):
        """在后台线程中搜索并连接"""
        found_servers = self.search_server()
        
        if found_servers:
            # 连接到第一个找到的服务器
            server_ip = found_servers[0]
            if not self.connect_to_server(server_ip):
                # 如果连接失败，尝试其他服务器
                for ip in found_servers[1:]:
                    if self.connect_to_server(ip):
                        break
        else:
            self.add_message("系统", "未找到可用的服务器", 'system')
            self.status_label.config(text="状态：未找到服务器", foreground='orange')
    
    def reconnect(self):
        """重新连接服务器"""
        if self.connected:
            self.disconnect()
        
        self.add_message("系统", "正在重新连接服务器...", 'system')
        self.search_and_connect()
    
    def disconnect(self):
        """断开连接"""
        self.running = False
        self.connected = False
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        # 更新UI状态
        self.status_label.config(text="状态：未连接", foreground='red')
        self.server_label.config(text="服务器：未连接")
        self.message_entry.config(state='disabled')
        self.send_button.config(state='disabled')
    
    def receive_messages(self):
        """接收服务器消息"""
        while self.running and self.connected:
            try:
                data = self.client_socket.recv(1024)
                if data:
                    try:
                        message_dict = json.loads(data.decode('utf-8'))
                        self.process_message(message_dict)
                    except json.JSONDecodeError:
                        # 处理旧格式的纯文本消息
                        message = data.decode('utf-8')
                        self.add_message("服务器", message, 'server')
                else:
                    # 服务器关闭连接
                    self.add_message("系统", "服务器已关闭连接", 'system')
                    break
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.add_message("错误", f"接收消息时出错：{str(e)}", 'error')
                break
        
        # 连接断开后的处理
        self.disconnect()
    
    def process_message(self, message_dict):
        """处理收到的消息"""
        message_type = message_dict.get('type', 'client')
        
        if message_type == 'client':
            name = message_dict.get('name', '未知用户')
            message = message_dict.get('message', '')
            if name == self.client_name:
                self.add_message(name, message, 'self')
            else:
                self.add_message(name, message, 'client')
        elif message_type == 'server':
            name = message_dict.get('name', '服务器')
            message = message_dict.get('message', '')
            self.add_message(name, message, 'server')
        elif message_type == 'system':
            message = message_dict.get('message', '')
            self.add_message("系统", message, 'system')
    
    def send_message(self):
        """发送消息到服务器"""
        if not self.connected or not self.client_socket:
            messagebox.showerror("错误", "未连接到服务器！")
            return
        
        message = self.message_entry.get().strip()
        if message:
            try:
                self.client_socket.send(message.encode('utf-8'))
                self.message_entry.delete(0, tk.END)
            except Exception as e:
                self.add_message("错误", f"发送消息失败：{str(e)}", 'error')
                self.disconnect()
    
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
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    client = ChatClient(root)
    root.protocol("WM_DELETE_WINDOW", client.on_closing)
    root.mainloop()