#!/usr/bin/env python3
"""
测试脚本 - 演示同步阻塞 vs 异步非阻塞的区别

运行此脚本可以清楚地看到：
1. 同步版本会阻塞主线程
2. 异步版本不会阻塞主线程
"""

import time
import threading
from datetime import datetime


# 模拟一个慢速连接函数
def slow_connect_test(success_after: float = 3.0):
    """
    模拟慢速连接
    
    Args:
        success_after: 多少秒后成功
    """
    start = datetime.now()
    while (datetime.now() - start).total_seconds() < success_after:
        time.sleep(0.1)
    return {
        'success': True,
        'message': f'连接成功（耗时 {success_after} 秒）'
    }


def test_sync_blocking():
    """测试同步阻塞 - 会卡住"""
    print("\n" + "="*60)
    print("测试 1: 同步阻塞版本（会卡住）")
    print("="*60)
    
    start = datetime.now()
    print(f"[{start.strftime('%H:%M:%S')}] 开始测试...")
    print("[在等待连接时，主线程被阻塞，无法执行其他操作...]")
    
    # 同步调用 - 会阻塞
    result = slow_connect_test(success_after=3.0)
    
    end = datetime.now()
    elapsed = (end - start).total_seconds()
    
    print(f"[{end.strftime('%H:%M:%S')}] 测试完成，耗时 {elapsed:.2f} 秒")
    print(f"结果: {result['message']}")


def test_async_nonblocking():
    """测试异步非阻塞 - 不会卡住"""
    print("\n" + "="*60)
    print("测试 2: 异步非阻塞版本（不会卡住）")
    print("="*60)
    
    result_container = [None]
    start = datetime.now()
    print(f"[{start.strftime('%H:%M:%S')}] 开始测试...")
    
    # 在后台线程执行
    def worker():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 后台线程：开始连接...")
        result_container[0] = slow_connect_test(success_after=3.0)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 后台线程：连接完成")
    
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    
    # 主线程继续执行其他任务
    print("[在后台线程连接时，主线程可以继续执行其他操作...]")
    
    for i in range(3):
        time.sleep(1)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 主线程：执行其他任务 {i+1}/3...")
    
    # 等待后台线程完成
    thread.join(timeout=5.0)
    
    end = datetime.now()
    elapsed = (end - start).total_seconds()
    
    print(f"[{end.strftime('%H:%M:%S')}] 测试完成，总耗时 {elapsed:.2f} 秒")
    if result_container[0]:
        print(f"结果: {result_container[0]['message']}")


def test_timeout_protection():
    """测试超时保护"""
    print("\n" + "="*60)
    print("测试 3: 超时保护（防止无限等待）")
    print("="*60)
    
    import concurrent.futures
    
    def very_slow_connect():
        """模拟非常慢的连接（10秒）"""
        time.sleep(10)
        return {'success': True, 'message': '连接成功'}
    
    start = datetime.now()
    print(f"[{start.strftime('%H:%M:%S')}] 开始测试（设置2秒超时）...")
    
    # 使用线程池 + 超时
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(very_slow_connect)
        try:
            result = future.result(timeout=2.0)
            print(f"结果: {result['message']}")
        except concurrent.futures.TimeoutError:
            end = datetime.now()
            elapsed = (end - start).total_seconds()
            print(f"[{end.strftime('%H:%M:%S')}] 操作超时（仅耗时 {elapsed:.2f} 秒）")
            print("√ 超时保护生效，没有无限等待！")


def test_real_connection():
    """测试真实连接场景"""
    print("\n" + "="*60)
    print("测试 4: 真实连接场景对比")
    print("="*60)
    
    from async_connection_manager import AsyncConnectionManager
    
    manager = AsyncConnectionManager()
    
    print("测试 SSH 连接到一个不存在的服务器...")
    print("（这会触发超时保护）")
    
    start = datetime.now()
    
    # 使用异步管理器测试连接
    result = manager.test_connection(
        'ssh',
        ip='192.0.2.1',  # 测试用IP，不可路由
        username='test',
        password='test',
        port=22,
        timeout=3  # 3秒超时
    )
    
    end = datetime.now()
    elapsed = (end - start).total_seconds()
    
    print(f"\n测试完成，耗时 {elapsed:.2f} 秒")
    print(f"成功: {result['success']}")
    print(f"消息: {result['message']}")
    print(f"错误类型: {result.get('error_type', 'N/A')}")
    
    if elapsed <= 5:
        print("\n√ 超时保护生效！没有无限等待。")


def main():
    """主函数"""
    print("\n" + "="*70)
    print(" " * 15 + "阻塞 vs 非阻塞 对比测试")
    print("="*70)
    
    # 测试1：同步阻塞
    test_sync_blocking()
    
    # 测试2：异步非阻塞
    test_async_nonblocking()
    
    # 测试3：超时保护
    test_timeout_protection()
    
    # 测试4：真实连接场景
    try:
        test_real_connection()
    except Exception as e:
        print(f"\n真实连接测试跳过（需要依赖库）: {e}")
    
    # 总结
    print("\n" + "="*70)
    print(" 总结")
    print("="*70)
    print("""
1. 同步版本：
   - 会阻塞主线程
   - 适合命令行工具
   - 不适合 GUI/Web 应用

2. 异步版本：
   - 不会阻塞主线程
   - 适合 GUI/Web 应用
   - 用户体验更好

3. 超时保护：
   - 防止无限等待
   - 使用线程池 + timeout
   - 必须有！

4. 推荐做法：
   - GUI/Web 应用：使用 AsyncConnectionManager
   - 命令行工具：使用增强版客户端
   - 所有场景：都要设置超时
    """)
    
    print("="*70)


if __name__ == "__main__":
    main()
