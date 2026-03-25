#!/usr/bin/env python3
"""
快速修复脚本 - 为现有代码添加超时保护

使用方法：
1. 在你的 GUI/Web 应用中
2. 导入此文件
3. 使用 ConnectionManagerWrapper 替换原来的 ConnectionManager
"""

import socket
import threading
import concurrent.futures
from functools import wraps
from typing import Dict, Any, Optional, Callable

# 设置全局 socket 超时，防止 DNS 解析卡住
socket.setdefaulttimeout(30)


def async_execute(timeout: int = 30):
    """
    装饰器：在后台线程执行函数，防止阻塞
    
    Args:
        timeout: 超时时间（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    return {
                        'success': False,
                        'message': f'操作超时（超过{timeout}秒），请检查网络或服务器状态',
                        'error_type': 'timeout'
                    }
        return wrapper
    return decorator


class ConnectionManagerWrapper:
    """
    连接管理器包装器 - 为现有代码添加超时保护
    
    使用方法：
    from connection_manager import ConnectionManager
    from quick_fix import ConnectionManagerWrapper
    
    # 使用包装后的管理器
    manager = ConnectionManagerWrapper(ConnectionManager())
    """
    
    def __init__(self, original_manager):
        """
        Args:
            original_manager: 原始的 ConnectionManager 实例
        """
        self.manager = original_manager
        self._lock = threading.Lock()
    
    @async_execute(timeout=35)
    def connect(self, protocol: str, **kwargs) -> Dict[str, Any]:
        """建立连接（带超时）"""
        return self.manager.connect(protocol, **kwargs)
    
    @async_execute(timeout=10)
    def disconnect(self, protocol: str) -> Dict[str, Any]:
        """断开连接（带超时）"""
        return self.manager.disconnect(protocol)
    
    @async_execute(timeout=15)
    def disconnect_all(self) -> Dict[str, Any]:
        """断开所有连接（带超时）"""
        return self.manager.disconnect_all()
    
    @async_execute(timeout=60)
    def execute_command(self, protocol: str, command: str, **kwargs) -> Dict[str, Any]:
        """执行命令（带超时）"""
        return self.manager.execute_command(protocol, command, **kwargs)
    
    @async_execute(timeout=300)
    def upload_file(self, protocol: str, local_path: str, remote_path: str, **kwargs) -> Dict[str, Any]:
        """上传文件（带超时）"""
        return self.manager.upload_file(protocol, local_path, remote_path, **kwargs)
    
    @async_execute(timeout=300)
    def download_file(self, protocol: str, remote_path: str, local_path: str, **kwargs) -> Dict[str, Any]:
        """下载文件（带超时）"""
        return self.manager.download_file(protocol, remote_path, local_path, **kwargs)
    
    @async_execute(timeout=30)
    def list_files(self, protocol: str, remote_path: str = '.') -> Dict[str, Any]:
        """列出文件（带超时）"""
        return self.manager.list_files(protocol, remote_path)
    
    def get_connection_status(self, protocol: Optional[str] = None) -> Dict[str, Any]:
        """获取连接状态（同步，只读操作）"""
        return self.manager.get_connection_status(protocol)
    
    @async_execute(timeout=15)
    def test_connection(self, protocol: str, **kwargs) -> Dict[str, Any]:
        """测试连接（带超时）"""
        return self.manager.test_connection(protocol, **kwargs)
    
    @async_execute(timeout=10)
    def get_available_ports(self) -> Dict[str, Any]:
        """获取可用串口列表（带超时）"""
        return self.manager.get_available_ports()
    
    def get_supported_protocols(self) -> Dict[str, Any]:
        """获取支持的协议列表（同步）"""
        return self.manager.get_supported_protocols()


# 便捷函数：快速创建带超时的管理器
def create_async_manager():
    """
    快速创建异步连接管理器
    
    返回:
        ConnectionManagerWrapper 实例
    """
    from connection_manager import ConnectionManager
    return ConnectionManagerWrapper(ConnectionManager())


# 示例代码
if __name__ == "__main__":
    print("=== 快速修复示例 ===\n")
    
    # 方式1：包装现有管理器
    from connection_manager import ConnectionManager
    original_manager = ConnectionManager()
    manager = ConnectionManagerWrapper(original_manager)
    
    print("1. 测试连接（带超时保护）:")
    result = manager.test_connection(
        'ssh',
        ip='192.168.1.100',
        username='test',
        password='test',
        port=22,
        timeout=5
    )
    print(f"   结果: {result['message']}")
    print(f"   成功: {result['success']}")
    print(f"   错误类型: {result.get('error_type', 'N/A')}\n")
    
    # 方式2：使用便捷函数
    manager2 = create_async_manager()
    print("2. 使用便捷函数创建管理器:")
    print(f"   管理器类型: {type(manager2).__name__}\n")
    
    print("=== 使用建议 ===")
    print("在你的 GUI 应用中:")
    print("""
    # 导入
    from connection_manager import ConnectionManager
    from quick_fix import ConnectionManagerWrapper
    
    # 创建包装后的管理器
    manager = ConnectionManagerWrapper(ConnectionManager())
    
    # 使用方式不变，但自动带超时保护
    result = manager.test_connection('ssh', ip='...', username='...', password='...')
    
    # 在 GUI 中使用时，仍需要在后台线程调用（因为线程池也会等待超时）
    import threading
    
    def on_test_button_click():
        def worker():
            result = manager.test_connection(...)
            update_ui(result)
        
        threading.Thread(target=worker, daemon=True).start()
    """)
