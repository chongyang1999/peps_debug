#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""串口环回诊断工具 - 快速验证TX-RX短接是否正常"""

import serial
import time
import sys

def test_loopback(port='COM3', baudrate=38400):
    """测试串口环回功能"""
    print(f"\n{'='*60}")
    print(f"串口环回诊断工具")
    print(f"{'='*60}")
    print(f"端口: {port}")
    print(f"波特率: {baudrate}")
    print(f"请确保TX和RX已短接！")
    print(f"{'='*60}\n")

    try:
        # 打开串口
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=2,
            rtscts=False,
            dsrdtr=False,
            xonxoff=False
        )

        print(f"✓ 串口已打开")
        print(f"  RTS={ser.rts}, CTS={ser.cts}, DTR={ser.dtr}, DSR={ser.dsr}")

        # 清空缓冲区
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print(f"✓ 缓冲区已清空\n")

        # 测试序列
        test_data = [
            b"A",
            b"ABC",
            b"0123456789",
            b"\x00\x01\x02\x03\x04\x05",
        ]

        success_count = 0
        fail_count = 0

        for i, data in enumerate(test_data, 1):
            print(f"[测试 {i}/{len(test_data)}]")
            print(f"  发送: {data.hex().upper()} ({len(data)} 字节)")

            # 发送
            written = ser.write(data)
            print(f"  write() 返回: {written}")
            print(f"  flush前 out_waiting: {ser.out_waiting}")

            ser.flush()  # 关键！强制刷新缓冲区
            print(f"  flush后 out_waiting: {ser.out_waiting}")

            # 等待数据返回
            time.sleep(0.1)

            print(f"  接收缓冲 in_waiting: {ser.in_waiting}")

            # 接收
            received = ser.read(len(data))
            print(f"  接收: {received.hex().upper()} ({len(received)} 字节)")

            # 验证
            if received == data:
                print(f"  结果: ✓ 成功")
                success_count += 1
            else:
                print(f"  结果: ✗ 失败")
                fail_count += 1

            print()
            time.sleep(0.2)

        # 总结
        print(f"{'='*60}")
        print(f"测试完成: 成功 {success_count}/{len(test_data)}, 失败 {fail_count}/{len(test_data)}")
        print(f"{'='*60}\n")

        ser.close()

        if fail_count == 0:
            print("✓ 结论: 环回测试完全成功，硬件和驱动工作正常")
            print("  → 问题可能在GUI程序的发送方法缺少flush()")
            return 0
        elif success_count > 0:
            print("⚠ 结论: 部分成功，可能存在时序或缓冲问题")
            return 1
        else:
            print("✗ 结论: 完全失败，请检查:")
            print("  1. TX-RX是否真的短接？")
            print("  2. USB芯片驱动是否正常？")
            print("  3. COM13是否被其他程序占用？")
            print("  4. 尝试更换USB转串口线或使用不同的USB口")
            return 2

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 3

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else 'COM3'
    sys.exit(test_loopback(port))
