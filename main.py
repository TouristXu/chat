import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import sys

class ChatAppLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("局域网聊天应用")
        self.root.geometry("400x300")
        
        # 设置窗口居中
        self.center_window()
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 标题
        title_label = ttk.Label(main_frame, text="局域网聊天应用", font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 30))
        
        # 启动服务端按钮
        server_button = ttk.Button(main_frame, text="启动服务端", command=self.start_server, width=20)
        server_button.grid(row=1, column=0, columnspan=2, pady=10)
        
        # 启动客户端按钮
        client_button = ttk.Button(main_frame, text="启动客户端", command=self.start_client, width=20)
        client_button.grid(row=2, column=0, columnspan=2, pady=10)
        
        # 说明标签
        info_label = ttk.Label(main_frame, text="说明：\n服务端：启动聊天服务器\n客户端：自动搜索并连接到局域网服务器", 
                              justify=tk.CENTER, foreground='gray')
        info_label.grid(row=3, column=0, columnspan=2, pady=(30, 0))
        
        # 配置网格权重
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def center_window(self):
        """将窗口居中显示"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def start_server(self):
        """启动服务端"""
        try:
            subprocess.Popen([sys.executable, 'server.py'])
            self.show_info("服务端已启动！")
        except Exception as e:
            self.show_error(f"启动服务端失败：{str(e)}")
    
    def start_client(self):
        """启动客户端"""
        try:
            subprocess.Popen([sys.executable, 'client.py'])
            self.show_info("客户端已启动！")
        except Exception as e:
            self.show_error(f"启动客户端失败：{str(e)}")
    
    def show_info(self, message):
        """显示信息对话框"""
        info_window = tk.Toplevel(self.root)
        info_window.title("信息")
        info_window.geometry("300x100")
        
        # 居中显示
        info_window.update_idletasks()
        x = (self.root.winfo_rootx() + self.root.winfo_width() // 2) - (info_window.winfo_width() // 2)
        y = (self.root.winfo_rooty() + self.root.winfo_height() // 2) - (info_window.winfo_height() // 2)
        info_window.geometry(f'+{x}+{y}')
        
        label = ttk.Label(info_window, text=message, padding=20)
        label.pack()
        
        ok_button = ttk.Button(info_window, text="确定", command=info_window.destroy)
        ok_button.pack(pady=10)
    
    def show_error(self, message):
        """显示错误对话框"""
        error_window = tk.Toplevel(self.root)
        error_window.title("错误")
        error_window.geometry("300x100")
        
        # 居中显示
        error_window.update_idletasks()
        x = (self.root.winfo_rootx() + self.root.winfo_width() // 2) - (error_window.winfo_width() // 2)
        y = (self.root.winfo_rooty() + self.root.winfo_height() // 2) - (error_window.winfo_height() // 2)
        error_window.geometry(f'+{x}+{y}')
        
        label = ttk.Label(error_window, text=message, padding=20, foreground='red')
        label.pack()
        
        ok_button = ttk.Button(error_window, text="确定", command=error_window.destroy)
        ok_button.pack(pady=10)

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatAppLauncher(root)
    root.mainloop()