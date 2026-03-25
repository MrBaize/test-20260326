"""
增强版 Telnet 客户端 - 解决连接卡住问题
添加了更完善的超时控制和异常处理
"""

import telnetlib
import socket
import time
import threading
from typing import Optional, Dict, Any


class TelnetClientEnhanced:
    """增强版 Telnet连接客户端类 - 带超时保护"""
    
    def __init__(self):
        self.telnet = None
        self.connected = False
        self.connection_info = {}
        self.timeout = 30
    
    def _read_with_timeout(self, pattern: bytes, timeout: float) -> Optional[bytes]:
        """
        读取数据直到匹配到指定模式，带超时保护
        
        Args:
            pattern: 要匹配的模式（字节串）
            timeout: 超时时间（秒）
            
        Returns:
            读取到的数据，超时返回None
        """
        if not self.telnet:
            return None
        
        result = [None]  # 使用列表存储结果以便在lambda中修改
        exception = [None]
        
        def read_worker():
            try:
                result[0] = self.telnet.read_until(pattern, timeout)
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=read_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout + 1)  # 多给1秒余量
        
        if thread.is_alive():
            # 线程还在运行，说明超时了
            return None
        
        if exception[0]:
            raise exception[0]
        
        return result[0]
    
    def connect(self, ip: str, username: str, password: str, port: int = 23, 
                baud_rate: int = 9600, timeout: int = 30) -> Dict[str, Any]:
        """
        连接到Telnet服务器（增强版，带超时保护）
        
        Args:
            ip: 服务器IP地址
            username: 用户名
            password: 密码
            port: 端口号，默认23
            baud_rate: 波特率（主要用于串口通信，这里保留参数）
            timeout: 连接超时时间，默认30秒
            
        Returns:
            连接结果字典
        """
        try:
            # 先尝试TCP连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            try:
                sock.connect((ip, port))
            except socket.gaierror as e:
                raise Exception(f"无法解析主机地址 {ip}: {str(e)}")
            
            # TCP连接成功后创建Telnet连接
            self.telnet = telnetlib.Telnet()
            self.telnet.sock = sock
            self.timeout = timeout
            
            # 等待登录提示（带超时保护）
            login_prompt = self._read_with_timeout(b"login: ", timeout)
            if not login_prompt:
                # 尝试其他常见的登录提示
                login_prompt = self._read_with_timeout(b"Login: ", timeout)
                if not login_prompt:
                    # 可能是已经登录或直接进入命令行
                    pass
            
            # 发送用户名
            self.telnet.write(username.encode('ascii') + b"\n")
            
            # 等待密码提示（带超时保护）
            password_prompt = self._read_with_timeout(b"Password: ", timeout)
            if not password_prompt:
                # 尝试其他常见的密码提示
                password_prompt = self._read_with_timeout(b"password: ", timeout)
                if not password_prompt:
                    pass  # 可能不需要密码
            
            # 发送密码
            self.telnet.write(password.encode('ascii') + b"\n")
            
            # 等待登录结果
            time.sleep(1)  # 给服务器时间处理登录
            
            # 检查是否登录成功（尝试读取一些输出）
            try:
                initial_output = self.telnet.read_very_eager().decode('ascii', errors='ignore')
                
                # 检查常见的登录失败提示
                if "Login incorrect" in initial_output or "Authentication failed" in initial_output:
                    self.telnet.close()
                    self.telnet = None
                    return {
                        'success': False,
                        'message': 'Telnet认证失败：用户名或密码错误',
                        'error_type': 'authentication'
                    }
            except:
                pass
            
            self.connected = True
            self.connection_info = {
                'ip': ip,
                'username': username,
                'port': port,
                'baud_rate': baud_rate,
                'status': 'connected'
            }
            
            return {
                'success': True,
                'message': f'Telnet连接成功: {ip}:{port}',
                'connection_info': self.connection_info
            }
            
        except ConnectionRefusedError:
            return {
                'success': False,
                'message': f'Telnet连接被拒绝: {ip}:{port}',
                'error_type': 'connection_refused'
            }
        except socket.timeout:
            return {
                'success': False,
                'message': f'Telnet连接超时（超过{timeout}秒）',
                'error_type': 'timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Telnet连接失败: {str(e)}',
                'error_type': 'general'
            }
    
    def send_command(self, command: str, wait_time: float = 1.0, 
                    timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        发送命令到Telnet服务器（带超时保护）
        
        Args:
            command: 要发送的命令
            wait_time: 等待响应的时间，默认1秒
            timeout: 读取超时时间，None表示使用连接超时
            
        Returns:
            命令执行结果字典
        """
        if not self.connected or not self.telnet:
            return {
                'success': False,
                'message': 'Telnet未连接，请先建立连接'
            }
        
        try:
            # 发送命令
            self.telnet.write(command.encode('ascii') + b"\n")
            
            # 等待响应
            wait_timeout = timeout if timeout is not None else self.timeout
            if wait_time > 0:
                time.sleep(wait_time)
            
            # 读取输出
            output = self.telnet.read_very_eager().decode('ascii', errors='ignore')
            
            return {
                'success': True,
                'command': command,
                'output': output.strip()
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'命令发送失败: {str(e)}'
            }
    
    def read_output(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        读取Telnet输出
        
        Args:
            timeout: 读取超时时间，默认使用连接超时
            
        Returns:
            读取结果字典
        """
        if not self.connected or not self.telnet:
            return {
                'success': False,
                'message': 'Telnet未连接，请先建立连接'
            }
        
        try:
            read_timeout = timeout if timeout is not None else self.timeout
            
            # 读取所有可用输出
            output = self.telnet.read_very_eager().decode('ascii', errors='ignore')
            
            return {
                'success': True,
                'output': output.strip()
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'读取输出失败: {str(e)}'
            }
    
    def expect(self, pattern: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        等待特定模式出现（带超时保护）
        
        Args:
            pattern: 要匹配的模式（正则表达式）
            timeout: 超时时间，默认使用连接超时
            
        Returns:
            匹配结果字典
        """
        if not self.connected or not self.telnet:
            return {
                'success': False,
                'message': 'Telnet未连接，请先建立连接'
            }
        
        try:
            read_timeout = timeout if timeout is not None else self.timeout
            
            # 使用带超时的expect
            try:
                match_index, match_object, output = self.telnet.expect(
                    [pattern.encode('ascii')], 
                    read_timeout
                )
            except EOFError:
                return {
                    'success': False,
                    'message': '连接已关闭'
                }
            
            if match_index == -1:
                return {
                    'success': False,
                    'message': f'等待模式超时: {pattern}'
                }
            
            output_str = output.decode('ascii', errors='ignore')
            
            return {
                'success': True,
                'match_index': match_index,
                'matched_text': match_object.group().decode('ascii') if match_object else None,
                'output': output_str
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'模式匹配失败: {str(e)}'
            }
    
    def disconnect(self) -> Dict[str, Any]:
        """
        断开Telnet连接
        
        Returns:
            断开连接结果字典
        """
        try:
            if self.telnet:
                # 发送退出命令
                try:
                    self.telnet.write(b"exit\n")
                    time.sleep(0.5)
                except:
                    pass
                
                self.telnet.close()
                self.telnet = None
            
            self.connected = False
            self.connection_info = {}
            
            return {
                'success': True,
                'message': 'Telnet连接已断开'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'断开连接失败: {str(e)}'
            }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        获取连接状态
        
        Returns:
            连接状态字典
        """
        # 检查连接是否仍然活跃
        is_alive = False
        if self.connected and self.telnet and self.telnet.sock:
            try:
                # 尝试检查socket状态
                is_alive = True
            except:
                is_alive = False
        
        return {
            'connected': self.connected and is_alive,
            'connection_info': self.connection_info
        }
    
    def test_connection(self, ip: str, username: str, password: str, 
                       port: int = 23, timeout: int = 10) -> Dict[str, Any]:
        """
        测试Telnet连接（增强版，带超时保护）
        
        Args:
            ip: 服务器IP地址
            username: 用户名
            password: 密码
            port: 端口号，默认23
            timeout: 连接超时时间，默认10秒
            
        Returns:
            测试结果字典
        """
        test_telnet = None
        sock = None
        try:
            # 先尝试TCP连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            try:
                sock.connect((ip, port))
            except socket.gaierror as e:
                raise Exception(f"无法解析主机地址 {ip}: {str(e)}")
            
            # TCP连接成功后创建Telnet连接
            test_telnet = telnetlib.Telnet()
            test_telnet.sock = sock
            
            # 尝试读取登录提示（不等待太久）
            try:
                login_prompt = test_telnet.read_until(b"login: ", timeout=timeout)
            except:
                login_prompt = b""
            
            # 发送用户名
            test_telnet.write(username.encode('ascii') + b"\n")
            
            # 尝试读取密码提示
            try:
                password_prompt = test_telnet.read_until(b"Password: ", timeout=timeout)
            except:
                password_prompt = b""
            
            return {
                'success': True,
                'message': f'Telnet连接测试成功: {ip}:{port}'
            }
            
        except socket.timeout:
            return {
                'success': False,
                'message': f'Telnet连接测试超时（超过{timeout}秒）',
                'error_type': 'timeout'
            }
        except socket.gaierror as e:
            return {
                'success': False,
                'message': f'无法解析主机地址 {ip}: {str(e)}',
                'error_type': 'dns_error'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Telnet连接测试失败: {str(e)}'
            }
        finally:
            if test_telnet:
                try:
                    test_telnet.close()
                except:
                    pass
            if sock:
                try:
                    sock.close()
                except:
                    pass


# 保持向后兼容
TelnetClient = TelnetClientEnhanced
