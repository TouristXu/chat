import socket
import threading
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import hashlib
import base64

CHAT_SERVER_HOST = '127.0.0.1'
CHAT_SERVER_PORT = 8888
WEB_SERVER_PORT = 8080

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

class ChatWebSocketHandler:
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    
    def __init__(self, client_socket):
        self.client_socket = client_socket
        self.client_address = client_socket.getpeername()
        self.handshake_done = False
        self.username = f"Web用户_{int(time.time() % 10000)}"
        print(f"[WebSocket] 新建连接: {self.client_address}")
    
    def handle_handshake(self, data):
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
            
            print(f"[WebSocket] Host: {headers.get('Host', '未知')}")
            print(f"[WebSocket] Upgrade: {headers.get('Upgrade', '未知')}")
            print(f"[WebSocket] Connection: {headers.get('Connection', '未知')}")
            print(f"[WebSocket] Sec-WebSocket-Key: {headers.get('Sec-WebSocket-Key', '未知')}")
            print(f"[WebSocket] Sec-WebSocket-Version: {headers.get('Sec-WebSocket-Version', '未知')}")
            
            if 'Upgrade' in headers and headers['Upgrade'].lower() == 'websocket':
                sec_key = headers.get('Sec-WebSocket-Key', '')
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
        if len(data) < 2:
            print(f"[WebSocket] 帧数据不足: {len(data)} bytes")
            return None
        
        fin = (data[0] >> 7) & 1
        opcode = data[0] & 0x0F
        mask = (data[1] >> 7) & 1
        payload_len = data[1] & 0x7F
        
        print(f"[WebSocket] 帧解析 - FIN: {fin}, Opcode: {opcode}, Mask: {mask}, PayloadLen: {payload_len}")
        
        if opcode == 8:
            print(f"[WebSocket] 收到关闭帧")
            return None
        
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
        print(f"[WebSocket] 准备发送消息: {message[:50]}..." if len(message) > 50 else f"[WebSocket] 准备发送消息: {message}")
        
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
        
        try:
            send_len = self.client_socket.send(frame)
            print(f"[WebSocket] 消息发送成功: {send_len} bytes")
            return True
        except Exception as e:
            print(f"[WebSocket] 消息发送失败: {type(e).__name__}: {str(e)}")
            return False

class ChatClient:
    def __init__(self, web_handler):
        self.web_handler = web_handler
        self.chat_socket = None
        self.running = False
        print(f"[ChatClient] 新建实例 - 用户名: {web_handler.username}")
    
    def connect_to_chat_server(self):
        print(f"[ChatClient] 开始连接聊天服务器 - {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}")
        
        try:
            self.chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.chat_socket.settimeout(5)
            print(f"[ChatClient] Socket创建成功")
            
            start_time = time.time()
            self.chat_socket.connect((CHAT_SERVER_HOST, CHAT_SERVER_PORT))
            connect_time = (time.time() - start_time) * 1000
            print(f"[ChatClient] 连接成功 - 耗时: {connect_time:.2f}ms")
            
            self.chat_socket.settimeout(None)
            
            send_len = self.chat_socket.send(self.web_handler.username.encode('utf-8'))
            print(f"[ChatClient] 用户名发送成功: {self.web_handler.username} ({send_len} bytes)")
            
            self.running = True
            
            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
            print(f"[ChatClient] 消息接收线程已启动")
            
            return True
            
        except socket.timeout:
            print(f"[ChatClient] 连接超时 - {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}")
            return False
        except ConnectionRefusedError:
            print(f"[ChatClient] 连接被拒绝 - {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}")
            return False
        except OSError as e:
            print(f"[ChatClient] 网络错误 - {e.errno}: {str(e)}")
            return False
        except Exception as e:
            print(f"[ChatClient] 连接失败: {type(e).__name__}: {str(e)}")
            return False
    
    def receive_messages(self):
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
                        text_message = data.decode('utf-8')
                        print(f"[ChatClient] 纯文本消息: {text_message[:50]}...")
                        self.web_handler.send_frame(text_message)
                else:
                    print(f"[ChatClient] 连接已断开")
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
        if self.chat_socket and self.running:
            try:
                self.chat_socket.send(message.encode('utf-8'))
                return True
            except Exception as e:
                return False
        return False

HTML_CONTENT = """
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
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .chat-header {
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
        }
        .chat-header h1 {
            margin: 0;
            font-size: 24px;
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
        .server-config {
            padding: 12px 20px;
            background: #e9ecef;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .server-config label {
            font-weight: 500;
            color: #495057;
        }
        .server-config input {
            padding: 8px 12px;
            border: 1px solid #ced4da;
            border-radius: 8px;
            font-size: 14px;
            width: 120px;
        }
        .server-config button {
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .server-config button:first-of-type {
            background: #28a745;
            color: white;
        }
        .server-config button:first-of-type:hover {
            background: #218838;
        }
        .server-config button:last-of-type {
            background: #dc3545;
            color: white;
        }
        .server-config button:last-of-type:hover {
            background: #c82333;
        }
        .chat-messages {
            height: 400px;
            overflow-y: auto;
            padding: 20px;
        }
        .message {
            margin-bottom: 15px;
            max-width: 80%;
        }
        .message-content {
            padding: 10px 15px;
            border-radius: 12px;
            font-size: 14px;
            line-height: 1.5;
        }
        .message-self {
            text-align: right;
        }
        .message-self .message-content {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px 12px 0 12px;
            display: inline-block;
        }
        .message-other {
            text-align: left;
        }
        .message-other .message-content {
            background: #f1f3f4;
            color: #333;
            border-radius: 12px 12px 12px 0;
            display: inline-block;
        }
        .message-system {
            text-align: center;
        }
        .message-system .message-content {
            background: #e3f2fd;
            color: #1976d2;
            font-size: 12px;
            padding: 5px 10px;
            border-radius: 4px;
        }
        .chat-input {
            padding: 15px 20px;
            background: #f8f9fa;
            border-top: 1px solid #eee;
            display: flex;
            gap: 10px;
        }
        .chat-input input {
            flex: 1;
            padding: 12px 15px;
            border: 1px solid #ddd;
            border-radius: 12px;
            font-size: 16px;
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
        
        <div class="server-config">
            <label>服务器地址:</label>
            <input type="text" id="serverHost" placeholder="输入服务器IP" value="127.0.0.1">
            <label>端口:</label>
            <input type="text" id="serverPort" placeholder="输入端口" value="8080">
            <button onclick="connect()">连接</button>
            <button onclick="disconnect()">断开</button>
        </div>
        
        <div class="chat-messages" id="chatMessages">
            <div class="message message-system">
                <div class="message-content">欢迎来到网页聊天室！</div>
            </div>
            <div class="message message-system">
                <div class="message-content">请输入服务器地址并点击连接按钮</div>
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
                addMessage('系统', `用户名已更改为: ${username}`, 'system');
            }
        }
        
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = document.getElementById('serverHost').value.trim() || '127.0.0.1';
            const port = document.getElementById('serverPort').value.trim() || '8080';
            
            const wsUrl = `${protocol}//${host}:${port}/chat`;
            console.log(`[WebSocket] 尝试连接: ${wsUrl}`);
            
            addMessage('系统', `正在连接到服务器: ${host}:${port}...`, 'system');
            addMessage('系统', `WebSocket端点: ${wsUrl}`, 'system');
            
            if (ws) {
                ws.close();
            }
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('[WebSocket] 连接成功');
                document.getElementById('status').textContent = '在线';
                document.getElementById('status').className = 'status-online';
                document.getElementById('connectionInfo').textContent = `已连接到 ${host}:${port}`;
                
                addMessage('系统', 'WebSocket连接成功！', 'system');
                addMessage('系统', '正在发送用户名...', 'system');
                
                setTimeout(function() {
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(username);
                        console.log(`[WebSocket] 发送用户名: ${username}`);
                        addMessage('系统', `已发送用户名: ${username}`, 'system');
                    }
                }, 100);
            };
            
            ws.onmessage = function(event) {
                console.log(`[WebSocket] 接收到消息: ${event.data.length} bytes`);
                try {
                    const data = JSON.parse(event.data);
                    console.log('[WebSocket] JSON消息:', data);
                    if (data.type === 'client') {
                        addMessage(data.name, data.message, 'other');
                    } else if (data.type === 'server') {
                        addMessage(data.name, data.message, 'other');
                    } else if (data.type === 'system') {
                        addMessage('系统', data.message, 'system');
                    }
                } catch (e) {
                    console.log(`[WebSocket] 纯文本消息: ${event.data}`);
                    addMessage('服务器', event.data, 'other');
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
            };
        }
        
        function disconnect() {
            if (ws) {
                console.log('[WebSocket] 手动断开连接');
                addMessage('系统', '正在断开连接...', 'system');
                ws.close(1000, '手动断开');
                ws = null;
            } else {
                addMessage('系统', '当前没有连接', 'system');
            }
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(message);
                addMessage('我', message, 'self');
                input.value = '';
            } else {
                addMessage('系统', '请先连接到服务器', 'system');
            }
        }
        
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
        
        function addMessage(sender, message, type) {
            const container = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message message-${type}`;
            
            let content = '';
            if (type === 'system') {
                content = `<div class="message-content">${message}</div>`;
            } else {
                content = `<div class="message-content"><strong>${sender}:</strong> ${message}</div>`;
            }
            
            messageDiv.innerHTML = content;
            container.appendChild(messageDiv);
            container.scrollTop = container.scrollHeight;
        }
    </script>
</body>
</html>
"""

class WebRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(HTML_CONTENT.encode()))
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode())
        elif path == '/chat':
            self.handle_websocket()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        self.send_response(404)
        self.end_headers()
    
    def handle_websocket(self):
        client_socket = self.connection
        
        ws_handler = ChatWebSocketHandler(client_socket)
        
        try:
            data = client_socket.recv(4096)
            if ws_handler.handle_handshake(data):
                print(f"[WebSocket] 握手成功，等待用户名...")
                ws_handler.send_frame(json.dumps({'type': 'system', 'message': '请输入用户名'}))
                
                chat_client = None
                
                while ws_handler.handshake_done:
                    try:
                        data = client_socket.recv(1024)
                        if not data:
                            print(f"[WebSocket] 客户端断开连接")
                            break
                        
                        message = ws_handler.parse_frame(data)
                        if message:
                            if not chat_client:
                                ws_handler.username = message
                                print(f"[WebSocket] 收到用户名: {ws_handler.username}")
                                ws_handler.send_frame(json.dumps({'type': 'system', 'message': f'用户名已设置: {ws_handler.username}'}))
                                
                                print(f"[WebSocket] 正在连接到聊天服务器...")
                                chat_client = ChatClient(ws_handler)
                                if chat_client.connect_to_chat_server():
                                    print(f"[WebSocket] Web客户端已连接到聊天服务器")
                                    ws_handler.send_frame(json.dumps({'type': 'system', 'message': '已连接到聊天服务器'}))
                                else:
                                    print(f"[WebSocket] 无法连接到聊天服务器")
                                    ws_handler.send_frame(json.dumps({'type': 'system', 'message': '无法连接到聊天服务器，请确保聊天服务器已启动'}))
                                    time.sleep(2)
                                    break
                            else:
                                chat_client.send_message(message)
                    except Exception as e:
                        print(f"[WebSocket] 消息循环异常: {type(e).__name__}: {str(e)}")
                        break
            else:
                print(f"[WebSocket] 握手失败")
        except Exception as e:
            print(f"[WebSocket] 处理异常: {type(e).__name__}: {str(e)}")
    
    def log_message(self, format, *args):
        pass

def start_web_server():
    from socketserver import ThreadingMixIn
    
    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        pass
    
    server_address = ('0.0.0.0', WEB_SERVER_PORT)
    httpd = ThreadedHTTPServer(server_address, WebRequestHandler)
    
    local_ip = get_local_ip()
    
    print("="*60)
    print("🌐 Web聊天服务器启动信息")
    print("="*60)
    print(f"监听地址: 0.0.0.0:{WEB_SERVER_PORT}")
    print(f"本地回环地址: http://localhost:{WEB_SERVER_PORT}")
    print(f"局域网地址: http://{local_ip}:{WEB_SERVER_PORT}")
    print(f"聊天服务器地址: {CHAT_SERVER_HOST}:{CHAT_SERVER_PORT}")
    print("="*60)
    print("WebSocket端点: ws://localhost:8080/chat")
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
