# UART-TCP 代理调试指南 (PC 与树莓派)

本文档提供在 PC (Windows/Linux/macOS) 上运行客户端 (`pc_client`)，在树莓派 (Raspberry Pi) 上运行服务端 (`server`) 的详细调试步骤。

## 1. 环境准备

### 1.1 通用准备 (PC 和树莓派)

*   **Python 3**: 确保两台设备都安装了 Python 3.8 或更高版本。
    *   检查方法: `python3 --version`
*   **pip**: Python 包管理器，通常随 Python 3 一起安装。
    *   检查方法: `python3 -m pip --version`
*   **git**: 版本控制系统，用于获取代码。
    *   检查方法: `git --version`
*   **(可选但推荐) Python 虚拟环境**:
    *   在 PC 和树莓派上，建议使用虚拟环境隔离项目依赖。
    *   安装 `venv` (如果尚未安装): `sudo apt install python3-venv` (Debian/Ubuntu/Raspberry Pi OS) 或系统对应的包管理器。

### 1.2 网络准备

*   确保 PC 和树莓派连接到**同一个局域网**。
*   **获取树莓派的 IP 地址**:
    *   在树莓派的终端中运行: `hostname -I` 或 `ip addr show`
    *   记下这个 IP 地址 (例如 `192.168.1.100`)，后续 PC 客户端连接时需要用到。

## 2. 代码获取与依赖安装

### 2.1 克隆仓库 (PC 和树莓派)

在 PC 和树莓派上分别执行以下命令，将代码克隆到本地：

```bash
git clone <your_repository_url> # 将 <your_repository_url> 替换为实际的仓库地址
cd <repository_name> # 进入项目目录，例如 cd uart-tcp-proxy
```

*注意*: 以下步骤假设你已经提交了 `requirements.txt` 文件到仓库。

### 2.2 创建并激活虚拟环境 (PC 和树莓派 - 推荐)

在项目根目录下执行：

```bash
python3 -m venv venv
```

*   激活虚拟环境：
    *   Linux/macOS/Raspberry Pi: `source venv/bin/activate`
    *   Windows (Git Bash or WSL): `source venv/Scripts/activate`
    *   Windows (Command Prompt): `venv\Scripts\activate.bat`
    *   Windows (PowerShell): `venv\Scripts\Activate.ps1` (可能需要先执行 `Set-ExecutionPolicy Unrestricted -Scope Process`)

激活后，命令行提示符前应出现 `(venv)`。

### 2.3 安装依赖 (PC 和树莓派)

在激活虚拟环境后，在项目根目录下执行：

```bash
pip install -r requirements.txt
```
这将安装 `common/protocol.py` 所需的 `crcmod` 库。

## 3. 运行服务端 (树莓派)

1.  **导航到项目目录**: `cd <repository_name>`
2.  **激活虚拟环境** (如果使用)。
3.  **运行服务端脚本**:
    ```bash
    python server/main.py
    ```
4.  **预期输出**:
    *   服务器启动后，会监听在 `0.0.0.0:65432`。 `0.0.0.0` 表示监听所有可用的网络接口。
    *   日志中应显示类似信息 (具体格式可能因日志配置而略有不同)：
        ```
        ... - INFO - Server listening on ('0.0.0.0', 65432)
        ```
    *   此时，服务器已准备好接收来自 PC 客户端的连接。

## 4. 配置并运行 PC 客户端

1.  **导航到项目目录**: `cd <repository_name>`
2.  **激活虚拟环境** (如果使用)。
3.  **配置服务器 IP 地址**:
    *   打开 `pc_client/main.py` 文件。
    *   找到以下行：
        ```python
        SERVER_HOST = "127.0.0.1" # 默认指向本机
        ```
    *   将其中的 `"127.0.0.1"` 修改为你在步骤 1.2 中获取到的**树莓派的 IP 地址**。例如：
        ```python
        SERVER_HOST = "192.168.1.100"
        ```
    *   保存文件。

4.  **配置串口 (SERIAL_PORT)**:
    *   `pc_client/main.py` 中的 `UARTManager` 当前是**占位符实现**，它不实际操作物理串口。
    *   `SERIAL_PORT` 的值 (默认为 `"COM_PLACEHOLDER"`) 在当前占位符版本中主要用于日志输出，不会导致连接错误。
    *   **对于当前测试**: 你可以暂时保留 `SERIAL_PORT = "COM_PLACEHOLDER"`。程序会模拟 UART 活动。
    *   **未来扩展**: 当 `UARTManager` 被替换为使用 `pyserial` 的真实串口实现时，你需要将 `SERIAL_PORT` 设置为 PC 上连接到目标电路板的实际串口号 (例如 Windows 上的 `"COM3"`，Linux 上的 `"/dev/ttyUSB0"`)。

5.  **运行 PC 客户端脚本**:
    ```bash
    python pc_client/main.py
    ```

6.  **预期输出与行为**:

    *   **PC 客户端日志**:
        *   尝试连接 UART (模拟):
            ```
            ... - INFO - UARTManager initialized for port COM_PLACEHOLDER (placeholder).
            ... - INFO - Attempting to connect to UART COM_PLACEHOLDER...
            ... - INFO - UART COM_PLACEHOLDER connected (placeholder).
            ```
        *   尝试连接网络 (到树莓派服务器):
            ```
            ... - INFO - Attempting to connect to network 192.168.1.100:65432 (Attempt 1/5)...
            ... - INFO - Network connection established to 192.168.1.100:65432.
            ```
        *   客户端启动成功:
            ```
            ... - INFO - PC Client started. Initial connections successful.
            ... - INFO - Starting UART <-> Network data forwarding tasks...
            ```
    *   **树莓派服务端日志**:
        *   当 PC 客户端成功连接时，服务器应显示：
            ```
            ... - INFO - Accepted connection from ('<PC_IP_ADDRESS>', <PC_PORT>)
            ```
            其中 `<PC_IP_ADDRESS>` 是你 PC 的 IP 地址。

    *   **数据双向流动 (模拟 UART)**:
        *   **PC 客户端**:
            *   会模拟从 UART 读取数据 (例如 `UART_DATA_...`) 并通过网络发送。日志：
                ```
                ... - INFO - UART RX: 55 41 52 54 5f 44 41 54 41 5f ... (模拟数据)
                ... - INFO - NET TX (payload): 55 41 52 54 5f 44 41 54 41 5f ...
                ... - DEBUG - NET TX (packed frame): aa 55 00 19 55 41 52 ... (打包后的数据)
                ```
        *   **树莓派服务端**:
            *   会接收到来自 PC 的数据，解包，然后（当前逻辑是）将相同数据打包回传。日志：
                ```
                ... - DEBUG - SERVER RX (chunk) from ('<PC_IP_ADDRESS>', <PC_PORT>): aa 55 ...
                ... - INFO - SERVER RX (unpacked payload ...) from ('<PC_IP_ADDRESS>', <PC_PORT>): 55 41 52 54 5f ...
                ... - INFO - SERVER TX (payload) to ('<PC_IP_ADDRESS>', <PC_PORT>): 55 41 52 54 5f ...
                ... - DEBUG - SERVER TX (packed frame) to ('<PC_IP_ADDRESS>', <PC_PORT>): aa 55 ...
                ```
        *   **PC 客户端**:
            *   会接收到从服务器回传的数据，解包，然后模拟写入 UART。日志：
                ```
                ... - DEBUG - NET RX (chunk): aa 55 ...
                ... - INFO - NET RX (unpacked payload ...): 55 41 52 54 5f ...
                ... - INFO - UART TX: 55 41 52 54 5f ...
                ```
        *   这个过程会持续进行，模拟数据在 UART (PC) -> 网络 (PC->树莓派) -> 网络 (树莓派->PC) -> UART (PC) 的路径中循环。

## 5. 日志级别调整

*   `pc_client/main.py` 和 `server/main.py` 的日志级别已默认为 `DEBUG`，这对于调试非常有用。
*   `common/protocol.py` 中的调试日志也会在 `DEBUG` 级别下显示，例如打包/解包过程、CRC 校验失败等。
*   如果日志过多，可以将 `logging.basicConfig(level=logging.DEBUG, ...)` 修改为 `logging.basicConfig(level=logging.INFO, ...)` 来减少输出。

## 6. 基本故障排除

*   **无法连接到服务器 (ConnectionRefusedError)**:
    *   检查树莓派的 IP 地址是否正确配置在 `pc_client/main.py` 中。
    *   确保树莓派上的 `server/main.py` 正在运行并且没有报错。
    *   检查防火墙设置：PC 和树莓派上的防火墙可能需要允许端口 `65432` 的 TCP 通信。
    *   确保 PC 和树莓派在同一局域网内，并且网络通畅 (例如，PC 可以 `ping` 通树莓派的 IP 地址)。
*   **客户端或服务端启动时报错 `ModuleNotFoundError`**:
    *   确保已在正确的虚拟环境中 (如果使用)。
    *   确保已运行 `pip install -r requirements.txt` 安装了所有依赖。
*   **数据没有按预期回传**:
    *   仔细检查 PC 客户端和服务端的日志。
    *   查看 `DEBUG` 级别的日志，特别是 `common/protocol.py` 的解包日志和 CRC 校验相关的警告。
    *   确认 `pack_data` 和 `unpack_data` 的逻辑是否符合预期。
*   **CRC 错误**:
    *   如果在 `common/protocol.py` 或客户端/服务端日志中看到 "CRC mismatch"，这表明数据在传输过程中可能已损坏，或者打包/解包逻辑存在问题。
    *   这在真实的不稳定网络或串口通信中可能发生，但在本地 TCP 测试中通常不应频繁出现。

## 7. 停止程序

*   在运行客户端或服务端的终端中，按 `Ctrl+C` 可以停止程序。

---

此指南基于当前代码的占位符 UART 实现。当 `UARTManager` 更新为实际与硬件串口交互时，PC 端的串口配置和测试步骤将需要相应调整。
