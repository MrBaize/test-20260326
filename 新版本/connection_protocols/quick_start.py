#!/usr/bin/env python3
"""
快速开始示例 - 展示如何修复界面卡顿问题

这个示例展示了三种修复方法，选择适合你的场景：
1. 异步连接管理器（推荐用于GUI应用）
2. 快速修复包装器（最小改动）
3. 增强版客户端（推荐用于命令行工具）
"""

import time
import threading


# ============================================
# 方法1: 异步连接管理器（推荐）
# ============================================
print("="*70)
print("方法1: 异步连接管理器（推荐用于GUI应用）")
print("="*70)

from async_connection_manager import AsyncConnectionManager

manager = AsyncConnectionManager()

print("\n示例：测试SSH连接")
print("注意：这会在后台执行，不会阻塞主线程\n")

# 在GUI应用中，应该在后台线程调用
def test_ssh_async():
    def worker():
        print("  [后台线程] 开始连接...")
        start = time.time()
        result = manager.test_connection(
            'ssh',
            ip='192.168.1.100',  # 替换为实际IP
            username='root',
            password='password',
            port=22,
            timeout=5  # 5秒超时
        )
        elapsed = time.time() - start
        print(f"  [后台线程] 连接完成，耗时 {elapsed:.2f} 秒")
        print(f"  [后台线程] 结果: {result['message']}")
        print(f"  [后台线程] 成功: {result['success']}")
        if 'error_type' in result:
            print(f"  [后台线程] 错误类型: {result['error_type']}")
    
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    
    # 主线程可以继续执行其他任务
    print("  [主线程] 等待连接...")
    thread.join(timeout=10)
    print("  [主线程] 继续执行其他任务\n")


test_ssh_async()


# ============================================
# 方法2: 快速修复包装器（最小改动）
# ============================================
print("\n" + "="*70)
print("方法2: 快速修复包装器（最小改动，适合现有项目）")
print("="*70)

from connection_manager import ConnectionManager
from quick_fix import ConnectionManagerWrapper

# 只需包装现有的管理器
original_manager = ConnectionManager()
manager_wrapper = ConnectionManagerWrapper(original_manager)

print("\n示例：使用包装器测试SSH连接")
print("注意：代码基本不变，但自动有了超时保护\n")

def test_with_wrapper():
    print("  开始连接...")
    start = time.time()
    result = manager_wrapper.test_connection(
        'ssh',
        ip='192.168.1.100',  # 替换为实际IP
        username='root',
        password='password',
        port=22,
        timeout=5
    )
    elapsed = time.time() - start
    print(f"  连接完成，耗时 {elapsed:.2f} 秒")
    print(f"  结果: {result['message']}")
    print(f"  成功: {result['success']}\n")


# 在GUI中仍需要在后台线程调用
def test_with_wrapper_async():
    def worker():
        test_with_wrapper()
    
    threading.Thread(target=worker, daemon=True).start()


test_with_wrapper_async()


# ============================================
# 方法3: 增强版客户端（命令行工具）
# ============================================
print("\n" + "="*70)
print("方法3: 增强版客户端（推荐用于命令行工具）")
print("="*70)

from ssh_client_enhanced import SSHClientEnhanced

client = SSHClientEnhanced()

print("\n示例：使用增强版SSH客户端")
print("注意：增强版客户端有完整的超时保护\n")

def test_with_enhanced_client():
    print("  开始连接...")
    start = time.time()
    result = client.test_connection(
        ip='192.168.1.100',  # 替换为实际IP
        username='root',
        password='password',
        port=22,
        timeout=5
    )
    elapsed = time.time() - start
    print(f"  连接完成，耗时 {elapsed:.2f} 秒")
    print(f"  结果: {result['message']}")
    print(f"  成功: {result['success']}")
    if 'error_type' in result:
        print(f"  错误类型: {result['error_type']}\n")


test_with_enhanced_client()


# ============================================
# 对比：原始版本 vs 改进版本
# ============================================
print("\n" + "="*70)
print("对比：原始版本 vs 改进版本")
print("="*70)

print("\n场景：连接到一个不存在的服务器（192.0.2.1）")
print("预期：原始版本可能卡住，改进版本会超时\n")

# 原始版本（使用快速修复包装器模拟）
print("1. 原始版本（模拟）：")
print("   开始连接...")
start = time.time()
result_original = manager.test_connection(
    'ssh',
    ip='192.0.2.1',  # 不可路由的IP
    username='test',
    password='test',
    port=22,
    timeout=5  # 虽然设置了，但可能不完整
)
elapsed_original = time.time() - start
print(f"   连接完成，耗时 {elapsed_original:.2f} 秒")
print(f"   结果: {result_original['message'][:50]}...\n")

# 改进版本（使用增强版客户端）
print("2. 改进版本（增强版客户端）：")
print("   开始连接...")
start = time.time()
result_enhanced = client.test_connection(
    ip='192.0.2.1',
    username='test',
    password='test',
    port=22,
    timeout=5  # 完整的超时控制
)
elapsed_enhanced = time.time() - start
print(f"   连接完成，耗时 {elapsed_enhanced:.2f} 秒")
print(f"   结果: {result_enhanced['message'][:50]}...")
print(f"   错误类型: {result_enhanced.get('error_type', 'N/A')}\n")


# ============================================
# 总结
# ============================================
print("\n" + "="*70)
print(" 总结")
print("="*70)

print("""
根据你的应用场景选择合适的方法：

【GUI应用（Tkinter/PyQt/PySide）】
推荐使用：AsyncConnectionManager
原因：
  - 不会阻塞界面
  - 自动在后台线程执行
  - 用户体验好

使用方法：
  from async_connection_manager import AsyncConnectionManager
  manager = AsyncConnectionManager()
  
  def on_button_click():
      def worker():
          result = manager.test_connection(...)
          root.after(0, lambda: update_ui(result))
      threading.Thread(target=worker, daemon=True).start()


【Web应用（Flask/Django）】
推荐使用：AsyncConnectionManager
原因：
  - 不阻塞请求处理
  - 支持并发连接
  - 可以配合后台任务队列

使用方法：
  from async_connection_manager import AsyncConnectionManager
  manager = AsyncConnectionManager()
  
  @app.route('/test')
  def test():
      def worker():
          result = manager.test_connection(...)
          save_to_db(result)
      threading.Thread(target=worker, daemon=True).start()
      return {'status': 'pending'}


【命令行工具】
推荐使用：增强版客户端（SSHClientEnhanced/TelnetClientEnhanced）
原因：
  - 代码简洁
  - 完整的超时控制
  - 适合单线程场景

使用方法：
  from ssh_client_enhanced import SSHClientEnhanced
  client = SSHClientEnhanced()
  result = client.connect(ip='...', username='...', password='...', timeout=10)


【现有项目快速修复】
推荐使用：ConnectionManagerWrapper
原因：
  - 最小改动
  - 只需一行代码
  - 保持原有逻辑

使用方法：
  from connection_manager import ConnectionManager
  from quick_fix import ConnectionManagerWrapper
  
  manager = ConnectionManagerWrapper(ConnectionManager())
  # 其他代码不变


【超时时间建议】
- TCP连接：10-30秒
- SSH测试：15秒
- SSH连接：30秒
- 文件传输：300秒（5分钟）
- 命令执行：60秒

【重要提示】
1. GUI应用中，所有网络操作都必须在后台线程
2. 必须设置合理的超时时间
3. 提供清晰的错误提示
4. 使用进度反馈提升用户体验
""")

print("="*70)
print(" 更多信息请参考：")
print(" - README_修复说明.md：完整的修复说明")
print(" - 解决界面卡顿问题.md：详细的技术文档")
print(" - example_async_usage.py：完整的GUI示例")
print(" - test_blocking_vs_async.py：对比测试")
print("="*70)
