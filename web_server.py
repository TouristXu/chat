import socket
import threading
import json
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 聊天服务器配置
CHAT_SERVER_HOST = '127.0.0.1'  # 使用本地回环地址连接聊天服务器
CHAT_SERVER_PORT = 8888
WEB_SERVER_PORT = 8080

def get_local_ip():
    """获取本地IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

# 存储Web客户端
web_clients = {}  # {client_socket: client_info}

class ChatWebSocketHandler:
    """处理WebSocket协议"""
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    
    def __init__(self, client_socket):
        self.client_socket = client_socket
        self.client_address = client_socket.getpeername()
        self.handshake_done = False
        self.buffer = ""
        self.username = f"Web用户_{int(time.time() % 10000)}"
        print(f"[WebSocket] 新建连接: {self.client_address}")
    
    def handle_handshake(self, data):
        """处理WebSocket握手"""
        print(f"[WebSocket] 开始握手 - 客户端: {self.client_address}")
        print(f"[WebSocket] 接收到数据长度: {len(data)} bytes")
        
        try:
            lines = data.decode('utf-8').split('\r\n')
            print(f"[WebSocket] 请求行: {lines[0] if lines else '空'}")
            
            headers = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            # 打印关键头部
            print(f"[WebSocket] Host: {headers.get('Host', '未知')}")
            print(f"[WebSocket] Upgrade: {headers.get('Upgrade', '未知')}")
            print(f"[WebSocket] Connection: {headers.get('Connection', '未知')}")
            print(f"[WebSocket] Sec-WebSocket-Key: {headers.get('Sec-WebSocket-Key', '未知')}")
            print(f"[WebSocket] Sec-WebSocket-Version: {headers.get('Sec-WebSocket-Version', '未知')}")
            
            if 'Upgrade' in headers and headers['Upgrade'].lower() == 'websocket':
                sec_key = headers.get('Sec-WebSocket-Key', '')
                import hashlib
                import base64
                accept_key = base64.b64encode(hashlib.sha1((sec_key + self.GUID).encode()).digest()).decode()
                
                print(f"[WebSocket] 生成Accept Key: {accept_key}")
                
                response = (
                    f"HTTP/1.1 101 Switching Protocols\r\n"
                    f"Upgrade: websocket\r\n"
                    f"Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept_key}\r\n"
                    f"\r\n"
                )
                
                send_len = self.client_socket.send(response.encode())
                print(f"[WebSocket] 握手响应已发送: {send_len} bytes")
                
                self.handshake_done = True
                print(f"[WebSocket] 握手成功 - 客户端: {self.client_address}")
                return True
            else:
                print(f"[WebSocket] 握手失败: 不是WebSocket请求")
                return False
        except Exception as e:
            print(f"[WebSocket] 握手异常: {type(e).__name__}: {str(e)}")
            return False
    
    def parse_frame(self, data):
        """解析WebSocket帧"""
        if len(data) < 2:
            print(f"[WebSocket] 帧数据不足: {len(data)} bytes")
            return None
        
        fin = (data[0] >> 7) & 1
        opcode = data[0] & 0x0F
        mask = (data[1] >> 7) & 1
        payload_len = data[1] & 0x7F
        
        print(f"[WebSocket] 帧解析 - FIN: {fin}, Opcode: {opcode}, Mask: {mask}, PayloadLen: {payload_len}")
        
        index = 2
        if payload_len == 126:
            payload_len = int.from_bytes(data[index:index+2], 'big')
            index += 2
        elif payload_len == 127:
            payload_len = int.from_bytes(data[index:index+8], 'big')
            index += 8
        
        if mask:
            mask_key = data[index:index+4]
            index += 4
        
        payload = data[index:index+payload_len]
        
        if mask:
            payload = bytes([payload[i] ^ mask_key[i % 4] for i in range(len(payload))])
        
        message = payload.decode('utf-8')
        print(f"[WebSocket] 解析消息: {message[:50]}..." if len(message) > 50 else f"[WebSocket] 解析消息: {message}")
        
        return message
    
    def send_frame(self, message):
        """发送WebSocket帧"""
        print(f"[WebSocket] 准备发送消息: {message[:50]}..." if len(message) > 50 else f"[WebSocket] 准备发送消息: {message}")
        
        payload = message.encode('utf-8')
        payload_len = len(payload)
        
        frame = bytearray()
        frame.append(0x81)  # FIN + TEXT
        
        if payload_len < 126:
            frame.append(payload_len)
        elif payload_len < 65536:
            frame.append(126)
            frame.extend(payload_len.to_bytes(2, 'big'))
        else:
            frame.append(127)
            frame.extend(payload_len.to_bytes(8, 'big'))
        
        frame.extend(payload)
        
        try:
            send_len = self.client_socket.send(frame)
            print(f"[WebSocket] 消息发送成功: {send_len} bytes")
            return True
        except Exception as e:
            print(f"[WebSocket] 消息发送失败: {type(e).__name__}: {str(e)}")
            return False

class ChatClient:
    """连接到聊天服务器的客户端"""
    def __init__(self, web_handler):
        self.web_handler = web_handler
        self.chat_socket = None
        self.running = False
        print(f"[ChatClient] 新建实例 - 用户名: {web_handler.username}")
    
    def connect_to_chat_server(self):
        """连接到聊天服务器"""
        print(f"[ChatClient] 开始连接聊天服务器 - {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}")
        
        try:
            # 创建socket
            self.chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.chat_socket.settimeout(5)  # 设置超时
            print(f"[ChatClient] Socket创建成功")
            
            # 连接到聊天服务器
            start_time = time.time()
            self.chat_socket.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
            connect_time = (time.time() - start_time) * 1000
            print(f"[ChatClient] 连接成功 - 耗时: {connect_time:.2f}ms")
            
            self.chat_socket.settimeout(None)  # 移除超时
            
            # 发送用户名
            send_len = self.chat_socket.send(self.web_handler.username.encode('utf-8'))
            print(f"[ChatClient] 用户名发送成功: {self.web_handler.username} ({send_len} bytes)")
            
            self.running = True
            
            # 启动接收消息线程
            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
            print(f"[ChatClient] 消息接收线程已启动")
            
            return True
            
        except socket.timeout:
            print(f"[ChatClient] 连接超时 - {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}")
            return False
        except ConnectionRefusedError:
            print(f"[ChatClient] 连接被拒绝 - {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT} (聊天服务器可能未启动)")
            return False
        except OSError as e:
            print(f"[ChatClient] 网络错误 - {e.errno}: {str(e)}")
            return False
        except Exception as e:
            print(f"[ChatClient] 连接失败: {type(e).__name__}: {str(e)}")
            return False
    
    def receive_messages(self):
        """接收聊天服务器消息"""
        print(f"[ChatClient] 开始接收消息循环")
        
        while self.running:
            try:
                data = self.chat_socket.recv(1024)
                if data:
                    print(f"[ChatClient] 接收到数据: {len(data)} bytes")
                    
                    try:
                        message_dict = json.loads(data.decode('utf-8'))
                        print(f"[ChatClient] JSON消息: {message_dict}")
                        self.web_handler.send_frame(json.dumps(message_dict))
                    except json.JSONDecodeError:
                        # 处理纯文本消息
                        text_message = data.decode('utf-8')
                        print(f"[ChatClient] 纯文本消息: {text_message[:50]}...")
                        self.web_handler.send_frame(text_message)
                else:
                    print(f"[ChatClient] 连接已断开 (空数据)")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[ChatClient] 接收消息异常: {type(e).__name__}: {str(e)}")
                break
        
        self.running = False
        print(f"[ChatClient] 消息循环结束")
        
        if self.chat_socket:
            try:
                self.chat_socket.close()
                print(f"[ChatClient] Socket已关闭")
            except:
                pass
    
    def send_message(self, message):
        """发送消息到聊天服务器"""
        if self.chat_socket and self.running:
            try:
                self.chat_socket.send(message.encode('utf-8'))
                return True
            except Exception as e:
                return False
        return False

class WebChatHandler(BaseHTTPRequestHandler):
    """处理HTTP请求"""
    
    def do_GET(self):
        """处理GET请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self.serve_index()
        elif path == '/chat':
            self.handle_websocket()
        elif path == '/api/message':
            self.handle_api_message()
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """处理POST请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/api/send':
            self.handle_api_send()
        else:
            self.send_error(404, "Not Found")
    
    def serve_index(self):
        """返回聊天页面"""
        html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>网页聊天室</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .chat-container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .chat-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .chat-header h1 {
            margin: 0;
            font-size: 24px;
        }
        .chat-messages {
            height: 400px;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
        }
        .message {
            margin-bottom: 15px;
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 70%;
            word-wrap: break-word;
        }
        .message-self {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin-left: auto;
        }
        .message-client {
            background: #e9ecef;
            color: #333;
        }
        .message-server {
            background: #fff3cd;
            color: #856404;
            text-align: center;
            max-width: 100%;
        }
        .message-system {
            background: #d4edda;
            color: #155724;
            text-align: center;
            max-width: 100%;
            font-size: 14px;
        }
        .message-sender {
            font-weight: 600;
            margin-bottom: 4px;
            font-size: 14px;
        }
        .message-content {
            font-size: 15px;
            line-height: 1.4;
        }
        .message-time {
            font-size: 12px;
            opacity: 0.7;
            margin-top: 4px;
        }
        .chat-input {
            padding: 20px;
            border-top: 1px solid #eee;
            display: flex;
            gap: 10px;
        }
        .chat-input input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 16px;
            outline: none;
            transition: border-color 0.3s;
        }
        .chat-input input:focus {
            border-color: #667eea;
        }
        .chat-input button {
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .chat-input button:hover {
            transform: translateY(-2px);
        }
        .chat-input button:active {
            transform: translateY(0);
        }
        .status-bar {
            padding: 10px 20px;
            background: #f8f9fa;
            border-top: 1px solid #eee;
            font-size: 14px;
            color: #666;
            display: flex;
            justify-content: space-between;
        }
        .status-online {
            color: #28a745;
        }
        .status-offline {
            color: #dc3545;
        }
        .username-section {
            padding: 15px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #eee;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .username-section label {
            font-weight: 500;
        }
        .username-section input {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }
        .username-section button {
            padding: 8px 16px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>🌐 网页聊天室</h1>
        </div>
        
        <div class="username-section">
            <label>您的昵称:</label>
            <input type="text" id="usernameInput" placeholder="输入昵称" value="Web用户">
            <button onclick="setUsername()">设置</button>
        </div>
        
        <div class="chat-messages" id="chatMessages">
            <div class="message message-system">
                <div class="message-content">欢迎来到网页聊天室！</div>
            </div>
            <div class="message message-system">
                <div class="message-content">正在连接到服务器...</div>
            </div>
        </div>
        
        <div class="chat-input">
            <input type="text" id="messageInput" placeholder="输入消息..." onkeyup="handleKeyPress(event)">
            <button onclick="sendMessage()">发送</button>
        </div>
        
        <div class="status-bar">
            <span>状态: <span id="status" class="status-offline">离线</span></span>
            <span id="connectionInfo">未连接</span>
        </div>
    </div>

    <script>
        let ws = null;
        let username = 'Web用户_' + Math.floor(Math.random() * 10000);
        
        function setUsername() {
            const input = document.getElementById('usernameInput');
            const newName = input.value.trim();
            if (newName) {
                username = newName;
                if (ws && ws.readyState === WebSocket.OPEN) {
                    // 发送新用户名（需要服务器支持）
                }
            }
        }
        
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.hostname || 'localhost';
            const webServerPort = '8080';  // 网页服务器固定端口
            
            const wsUrl = `${protocol}//${host}:${webServerPort}/chat`;
            console.log(`[WebSocket] 尝试连接: ${wsUrl}`);
            
            addMessage('系统', `正在连接到网页服务器: ${host}:${webServerPort}...`, 'system');
            addMessage('系统', `WebSocket端点: ${wsUrl}`, 'system');
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('[WebSocket] 连接成功');
                document.getElementById('status').textContent = '在线';
                document.getElementById('status').className = 'status-online';
                document.getElementById('connectionInfo').textContent = `已连接到 ${host}:${port}`;
                
                addMessage('系统', 'WebSocket连接成功！', 'system');
                addMessage('系统', '正在连接到聊天服务器...', 'system');
            };
            
            ws.onmessage = function(event) {
                console.log(`[WebSocket] 接收到消息: ${event.data.length} bytes`);
                try {
                    const data = JSON.parse(event.data);
                    console.log('[WebSocket] JSON消息:', data);
                    if (data.type === 'client' || data.type === 'server') {
                        addMessage(data.name, data.message, data.type);
                    } else if (data.type === 'system') {
                        addMessage('系统', data.message, 'system');
                    }
                } catch (e) {
                    // 处理纯文本消息
                    console.log(`[WebSocket] 纯文本消息: ${event.data}`);
                    addMessage('服务器', event.data, 'server');
                }
            };
            
            ws.onerror = function(error) {
                console.error('[WebSocket] 连接错误:', error);
                document.getElementById('status').textContent = '错误';
                document.getElementById('status').className = 'status-offline';
                addMessage('系统', `连接错误: ${error.type || '未知错误'}`, 'system');
            };
            
            ws.onclose = function(event) {
                console.log(`[WebSocket] 连接关闭 - 代码: ${event.code}, 原因: ${event.reason}`);
                document.getElementById('status').textContent = '离线';
                document.getElementById('status').className = 'status-offline';
                document.getElementById('connectionInfo').textContent = `连接已断开 (${event.code})`;
                
                let reason = '未知原因';
                if (event.code === 1000) {
                    reason = '正常关闭';
                } else if (event.code === 1006) {
                    reason = '异常断开';
                }
                addMessage('系统', `连接已断开: ${reason}`, 'system');
                
                // 尝试重新连接
                addMessage('系统', '3秒后尝试重新连接...', 'system');
                setTimeout(connect, 3000);
            };
        }
        
        function addMessage(sender, message, type) {
            const container = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            
            let messageClass = 'message-client';
            if (sender === username) {
                messageClass = 'message-self';
            } else if (sender === '服务器') {
                messageClass = 'message-server';
            } else if (type === 'system') {
                messageClass = 'message-system';
            }
            
            messageDiv.className = 'message ' + messageClass;
            
            const now = new Date();
            const timeStr = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            
            if (type === 'system') {
                messageDiv.innerHTML = `<div class="message-content">${escapeHtml(message)}</div>`;
            } else {
                messageDiv.innerHTML = `
                    <div class="message-sender">${escapeHtml(sender)}</div>
                    <div class="message-content">${escapeHtml(message)}</div>
                    <div class="message-time">${timeStr}</div>
                `;
            }
            
            container.appendChild(messageDiv);
            container.scrollTop = container.scrollHeight;
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (message && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(message);
                addMessage(username, message, 'self');
                input.value = '';
            }
        }
        
        function handleKeyPress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // 页面加载完成后连接
        document.addEventListener('DOMContentLoaded', connect);
    </script>
</body>
</html>
            """
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html_content.encode()))
        self.end_headers()
        self.wfile.write(html_content.encode())
    
    def handle_websocket(self):
        """处理WebSocket连接"""
        # 获取客户端socket
        client_socket = self.connection
        
        # 包装为WebSocket处理器
        ws_handler = ChatWebSocketHandler(client_socket)
        
        # 读取握手数据
        try:
            data = client_socket.recv(4096)
            if ws_handler.handle_handshake(data):
                # 创建聊天客户端
                chat_client = ChatClient(ws_handler)
                if chat_client.connect_to_chat_server():
                    # 处理消息循环
                    while ws_handler.handshake_done:
                        try:
                            data = client_socket.recv(1024)
                            if not data:
                                break
                            
                            message = ws_handler.parse_frame(data)
                            if message:
                                chat_client.send_message(message)
                        except Exception as e:
                            break
            else:
                self.send_error(400, "Bad Request")
        except Exception as e:
            pass
    
    def handle_api_message(self):
        """处理API消息请求"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = json.dumps({'status': 'ok', 'message': 'WebSocket连接已建立'})
        self.wfile.write(response.encode())
    
    def handle_api_send(self):
        """处理API发送消息"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = parse_qs(post_data)
            
            message = data.get('message', [''])[0]
            username = data.get('username', ['Web用户'])[0]
            
            # 发送到聊天服务器
            chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            chat_socket.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
            chat_socket.send(username.encode('utf-8'))
            time.sleep(0.1)
            chat_socket.send(message.encode('utf-8'))
            chat_socket.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode())
        except Exception as e:
            self.send_error(500, str(e))
    
    def log_message(self, format, *args):
        """禁用日志输出"""
        pass

def start_web_server():
    """启动Web服务器"""
    server_address = ('0.0.0.0', WEB_SERVER_PORT)
    httpd = HTTPServer(server_address, WebChatHandler)
    
    local_ip = get_local_ip()
    
    print("="*60)
    print("🌐 Web聊天服务器启动信息")
    print("="*60)
    print(f"监听地址: 0.0.0.0:{WEB_SERVER_PORT}")
    print(f"本地回环地址: http://localhost:{WEB_SERVER_PORT}")
    print(f"局域网地址: http://{local_ip}:{WEB_SERVER_PORT}")
    print(f"聊天服务器地址: {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}")
    print("="*60)
    print("WebSocket端点: ws://localhost:{WEB_SERVER_PORT}/chat")
    print("日志输出已启用，可查看连接状态")
    print("="*60)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    
    httpd.server_close()
    print("Web服务器已关闭")

if __name__ == '__main__':
    start_web_server()