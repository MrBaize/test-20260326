# 终端模拟器升级说明

## 更新日期
2026-03-16

## 核心改进

### 从"猜测式"到"标准式"的升级

#### 之前的问题
- ❌ 使用 `strip_ansi()` 丢弃 ANSI 转义序列，丢失光标位置信息
- ❌ 通过时间差和文本匹配猜测 shell 的意图
- ❌ 对于 zsh/fish 的实时命令重绘处理不稳定
- ❌ 不支持光标移动、清屏等标准终端特性

#### 新方案的优势
- ✅ 使用 **Pyte** 库（Python 最成熟的终端模拟库）
- ✅ 维护**虚拟屏幕缓冲区**（120x40 二维字符数组）
- ✅ 完整解析并执行所有 ANSI 转义序列
- ✅ 支持光标移动、清屏、颜色等标准终端特性
- ✅ 符合 VT100 终端标准

## 技术架构对比

```
旧架构:
SSH数据 → strip_ansi() → QTextDocument → 显示
              ↓
         丢失位置信息

新架构:
SSH数据 → Pyte Stream → 虚拟屏幕 → QTextEdit → 显示
             ↓          ↓
         解析ANSI   二维缓冲区
```

## 核心修改

### 1. 导入 Pyte 库
```python
from pyte import Screen, Stream
```

### 2. 初始化虚拟屏幕
```python
# 创建虚拟屏幕（120列 x 40行）
self.pyte_screen = Screen(120, 40)
self.pyte_stream = Stream(self.pyte_screen)
```

### 3. 重写 append_raw 方法
```python
def append_raw(self, text):
    # Pyte 自动处理所有 ANSI 序列
    self.pyte_stream.feed(text)
    # 从虚拟屏幕渲染到 UI
    self._render_from_pyte_screen()
```

### 4. 新增屏幕管理方法
- `_render_full()`: 全量渲染整个屏幕
- `_render_incremental()`: 增量渲染（性能优化）
- `clear_screen()`: 清空虚拟屏幕
- `_get_clean_text_from_screen()`: 获取纯文本

## ANSI 序列支持

Pyte 自动处理所有标准 ANSI 序列：

| 序列类型 | 示例 | 功能 |
|---------|------|------|
| 光标移动 | `\r`, `\n`, `\x1b[A/B/C/D` | 光标定位 |
| 清除屏幕 | `\x1b[J`, `\x1b[K` | 清屏/清行 |
| 颜色设置 | `\x1b[31m`, `\x1b[0m` | 颜色和样式 |
| 滚动 | 自动处理 | 终端滚动 |

## 测试验证

### 推荐测试场景

1. **基本命令输入**
   - 输入 `ifconfig` - 应正常显示
   - 使用退格键删除字符 - 应正确显示
   - 使用方向键浏览历史 - 应正确显示

2. **zsh/fish Shell**
   - 输入长命令并修改 - 不应出现重复
   - 使用 Tab 自动补全 - 应正确显示
   - 命令提示符 - 应正确显示

3. **不同协议**
   - SSH 连接测试
   - 串口连接测试
   - Telnet 连接测试（如支持）

## 性能优化

### 增量渲染
- 只更新变化的行，减少 UI 刷新
- 使用 `_use_incremental_render = True` 开启

### 屏幕尺寸
- 默认 120x40
- 可通过 `resize_terminal(cols, rows)` 动态调整

## 兼容性

- ✅ Windows (PyQt6)
- ✅ macOS (PyQt6)
- ✅ Linux (PyQt6)
- ✅ Python 3.7+

## 依赖安装

```bash
pip install pyte
```

## 回退方案

如果遇到问题，可以临时回退到旧方案：

1. 将 `append_raw` 重命名为 `_append_raw_old`
2. 恢复旧的 `append_raw` 实现
3. 恢复 `strip_ansi` 方法

## 后续优化建议

1. **颜色支持扩展**
   - 利用 Pyte 的颜色信息
   - 为不同的输出类型设置不同颜色

2. **更智能的增量渲染**
   - 实现行级别的精确更新
   - 减少闪烁

3. **终端尺寸自适应**
   - 根据窗口大小动态调整
   - 响应式设计

## 参考资料

- Pyte 官方文档: https://github.com/selectel/pyte
- VT100 终端标准
- ANSI 转义序列规范
