import serial
import time
from typing import Optional, Dict, Any


class SerialClient:
    """串口连接客户端类"""
    
    def __init__(self):
        self.serial = None
        self.connected = False
        self.connection_info = {}
    
    def connect(self, com_port: str, baud_rate: int = 9600, 
                bytesize: int = 8, parity: str = 'N', stopbits: float = 1, 
                timeout: float = 1.0) -> Dict[str, Any]:
        """
        连接到串口设备
        
        Args:
            com_port: 串口名称（如 'COM1', '/dev/ttyUSB0'）
            baud_rate: 波特率，默认9600
            bytesize: 数据位，默认8
            parity: 校验位，默认'N'（无校验）
            stopbits: 停止位，默认1
            timeout: 超时时间，默认1秒
            
        Returns:
            连接结果字典
        """
        try:
            # 创建串口连接
            self.serial = serial.Serial(
                port=com_port,
                baudrate=baud_rate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout
            )
            
            # 等待串口稳定
            time.sleep(0.1)
            
            self.connected = True
            self.connection_info = {
                'com_port': com_port,
                'baud_rate': baud_rate,
                'bytesize': bytesize,
                'parity': parity,
                'stopbits': stopbits,
                'timeout': timeout,
                'status': 'connected'
            }
            
            return {
                'success': True,
                'message': f'串口连接成功: {com_port}@{baud_rate}bps',
                'connection_info': self.connection_info
            }
            
        except serial.SerialException as e:
            return {
                'success': False,
                'message': f'串口连接失败: {str(e)}',
                'error_type': 'serial_exception'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'串口连接异常: {str(e)}',
                'error_type': 'general'
            }
    
    def send_data(self, data: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        """
        发送数据到串口
        
        Args:
            data: 要发送的数据
            encoding: 编码格式，默认utf-8
            
        Returns:
            发送结果字典
        """
        if not self.connected or not self.serial:
            return {
                'success': False,
                'message': '串口未连接，请先建立连接'
            }
        
        try:
            # 编码数据并发送
            encoded_data = data.encode(encoding)
            bytes_sent = self.serial.write(encoded_data)
            
            return {
                'success': True,
                'message': f'数据发送成功，发送字节数: {bytes_sent}',
                'bytes_sent': bytes_sent
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'数据发送失败: {str(e)}'
            }
    
    def send_bytes(self, data: bytes) -> Dict[str, Any]:
        """
        发送字节数据到串口
        
        Args:
            data: 要发送的字节数据
            
        Returns:
            发送结果字典
        """
        if not self.connected or not self.serial:
            return {
                'success': False,
                'message': '串口未连接，请先建立连接'
            }
        
        try:
            bytes_sent = self.serial.write(data)
            
            return {
                'success': True,
                'message': f'字节数据发送成功，发送字节数: {bytes_sent}',
                'bytes_sent': bytes_sent
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'字节数据发送失败: {str(e)}'
            }
    
    def read_data(self, size: Optional[int] = None, 
                  timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        从串口读取数据
        
        Args:
            size: 要读取的字节数，None表示读取所有可用数据
            timeout: 读取超时时间，None表示使用默认超时
            
        Returns:
            读取结果字典
        """
        if not self.connected or not self.serial:
            return {
                'success': False,
                'message': '串口未连接，请先建立连接'
            }
        
        try:
            # 设置临时超时
            original_timeout = self.serial.timeout
            if timeout is not None:
                self.serial.timeout = timeout
            
            # 读取数据
            if size is None:
                # 读取所有可用数据
                data = self.serial.read_all()
            else:
                # 读取指定字节数
                data = self.serial.read(size)
            
            # 恢复原始超时设置
            if timeout is not None:
                self.serial.timeout = original_timeout
            
            return {
                'success': True,
                'data': data,
                'data_hex': data.hex(),
                'data_str': data.decode('utf-8', errors='ignore'),
                'bytes_read': len(data)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'数据读取失败: {str(e)}'
            }
    
    def read_line(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        从串口读取一行数据
        
        Args:
            timeout: 读取超时时间，None表示使用默认超时
            
        Returns:
            读取结果字典
        """
        if not self.connected or not self.serial:
            return {
                'success': False,
                'message': '串口未连接，请先建立连接'
            }
        
        try:
            # 设置临时超时
            original_timeout = self.serial.timeout
            if timeout is not None:
                self.serial.timeout = timeout
            
            # 读取一行数据
            line = self.serial.readline()
            
            # 恢复原始超时设置
            if timeout is not None:
                self.serial.timeout = original_timeout
            
            return {
                'success': True,
                'data': line,
                'data_hex': line.hex(),
                'data_str': line.decode('utf-8', errors='ignore').strip(),
                'bytes_read': len(line)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'行读取失败: {str(e)}'
            }
    
    def flush_input(self) -> Dict[str, Any]:
        """
        清空输入缓冲区
        
        Returns:
            清空结果字典
        """
        if not self.connected or not self.serial:
            return {
                'success': False,
                'message': '串口未连接，请先建立连接'
            }
        
        try:
            self.serial.reset_input_buffer()
            return {
                'success': True,
                'message': '输入缓冲区已清空'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'清空输入缓冲区失败: {str(e)}'
            }
    
    def flush_output(self) -> Dict[str, Any]:
        """
        清空输出缓冲区
        
        Returns:
            清空结果字典
        """
        if not self.connected or not self.serial:
            return {
                'success': False,
                'message': '串口未连接，请先建立连接'
            }
        
        try:
            self.serial.reset_output_buffer()
            return {
                'success': True,
                'message': '输出缓冲区已清空'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'清空输出缓冲区失败: {str(e)}'
            }
    
    def disconnect(self) -> Dict[str, Any]:
        """
        断开串口连接
        
        Returns:
            断开连接结果字典
        """
        try:
            if self.serial:
                self.serial.close()
                self.serial = None
            
            self.connected = False
            self.connection_info = {}
            
            return {
                'success': True,
                'message': '串口连接已断开'
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
        status_info = {
            'connected': self.connected,
            'connection_info': self.connection_info
        }
        
        # 如果已连接，添加更多状态信息
        if self.connected and self.serial:
            status_info.update({
                'port': self.serial.port,
                'baudrate': self.serial.baudrate,
                'bytesize': self.serial.bytesize,
                'parity': self.serial.parity,
                'stopbits': self.serial.stopbits,
                'timeout': self.serial.timeout
            })
        
        return status_info
    
    def get_available_ports(self) -> Dict[str, Any]:
        """
        获取可用的串口列表
        
        Returns:
            串口列表字典
        """
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            port_list = []
            
            for port in ports:
                port_info = {
                    'device': port.device,
                    'name': port.name,
                    'description': port.description,
                    'hwid': port.hwid,
                    'vid': port.vid if port.vid else None,
                    'pid': port.pid if port.pid else None
                }
                port_list.append(port_info)
            
            return {
                'success': True,
                'ports': port_list,
                'count': len(port_list)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'获取串口列表失败: {str(e)}'
            }
    
    def test_connection(self, com_port: str, baud_rate: int = 9600, 
                       timeout: float = 2.0) -> Dict[str, Any]:
        """
        测试串口连接
        
        Args:
            com_port: 串口名称
            baud_rate: 波特率，默认9600
            timeout: 连接超时时间，默认2秒
            
        Returns:
            测试结果字典
        """
        test_serial = None
        try:
            test_serial = serial.Serial(
                port=com_port,
                baudrate=baud_rate,
                timeout=timeout
            )
            
            return {
                'success': True,
                'message': f'串口连接测试成功: {com_port}@{baud_rate}bps'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'串口连接测试失败: {str(e)}'
            }
        finally:
            if test_serial:
                test_serial.close()