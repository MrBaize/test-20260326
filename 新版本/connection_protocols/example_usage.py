#!/usr/bin/env python3
"""
连接协议使用示例
"""

from connection_manager import ConnectionManager


def main():
    """主函数 - 演示各种连接协议的使用"""
    
    # 创建连接管理器
    manager = ConnectionManager()
    
    print("=== 连接协议管理器示例 ===\n")
    
    # 1. 显示支持的协议
    protocols_info = manager.get_supported_protocols()
    print("支持的协议:")
    for protocol, info in protocols_info['protocols'].items():
        print(f"  - {protocol.upper()}: {info['description']}")
        print(f"    功能: {', '.join(info['capabilities'])}")
    print()
    
    # 2. 测试SSH连接（需要真实服务器信息）
    print("=== SSH连接测试 ===")
    # 注意：需要替换为真实的服务器信息
    ssh_test = manager.test_connection('ssh', 
                                      ip='192.168.1.100',
                                      username='testuser',
                                      password='testpass',
                                      port=22)
    print(f"SSH测试结果: {ssh_test['message']}")
    print()
    
    # 3. 测试Telnet连接
    print("=== Telnet连接测试 ===")
    telnet_test = manager.test_connection('telnet',
                                         ip='192.168.1.101',
                                         username='testuser',
                                         password='testpass',
                                         port=23)
    print(f"Telnet测试结果: {telnet_test['message']}")
    print()
    
    # 4. 获取可用的串口列表
    print("=== 串口列表 ===")
    ports_info = manager.get_available_ports()
    if ports_info['success']:
        print(f"找到 {ports_info['count']} 个串口:")
        for port in ports_info['ports']:
            print(f"  - {port['device']}: {port['description']}")
    else:
        print(f"获取串口列表失败: {ports_info['message']}")
    print()
    
    # 5. 测试串口连接
    print("=== 串口连接测试 ===")
    serial_test = manager.test_connection('serial',
                                         com_port='COM1',
                                         baud_rate=9600)
    print(f"串口测试结果: {serial_test['message']}")
    print()
    
    # 6. 测试FTP连接
    print("=== FTP连接测试 ===")
    ftp_test = manager.test_connection('ftp',
                                      ip='192.168.1.102',
                                      username='testuser',
                                      password='testpass',
                                      port=21)
    print(f"FTP测试结果: {ftp_test['message']}")
    print()
    
    # 7. 测试SFTP连接
    print("=== SFTP连接测试 ===")
    sftp_test = manager.test_connection('sftp',
                                       ip='192.168.1.103',
                                       username='testuser',
                                       password='testpass',
                                       port=22)
    print(f"SFTP测试结果: {sftp_test['message']}")
    print()
    
    # 8. 显示当前连接状态
    print("=== 当前连接状态 ===")
    status = manager.get_connection_status()
    print(f"活跃连接: {status['active_connections']}")
    
    print("\n=== 示例完成 ===")


if __name__ == "__main__":
    main()