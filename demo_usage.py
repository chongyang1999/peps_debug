#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
串口通信GUI程序演示脚本

这个脚本展示了如何使用GUI程序的两个版本
"""

import os
import sys

def print_menu():
    print("\n" + "="*60)
    print("串口通信可视化GUI程序 - 演示菜单")
    print("="*60)
    print("\n可用的GUI版本：")
    print("\n1. 基础版 (radio_gui.py)")
    print("   - 适合快速开始使用")
    print("   - 内置12个常用命令按钮")
    print("   - 简洁明了的界面")
    print("   - 实时显示接收数据")
    print("\n2. 高级版 (radio_gui_advanced.py)")
    print("   - 支持从JSON配置文件加载命令")
    print("   - 可滚动的命令按钮区域（支持更多命令）")
    print("   - 保存日志功能")
    print("   - 命令按钮工具提示")
    print("   - 显示/隐藏原始数据开关")
    print("\n3. 查看配置文件示例")
    print("   - 打开 commands_config.json")
    print("\n4. 查看完整文档")
    print("   - 打开 GUI_README.md")
    print("\n5. 退出")
    print("\n" + "="*60)

def launch_basic_gui():
    print("\n正在启动基础版GUI...")
    print("提示：关闭GUI窗口即可返回此菜单\n")
    try:
        import radio_gui
        radio_gui.main()
    except Exception as e:
        print(f"错误：无法启动GUI - {e}")
        print("请确保已安装 pyserial 库：pip install pyserial")

def launch_advanced_gui():
    print("\n正在启动高级版GUI...")
    print("提示：关闭GUI窗口即可返回此菜单")
    print("提示：可以点击「加载配置」按钮加载 commands_config.json\n")
    try:
        import radio_gui_advanced
        radio_gui_advanced.main()
    except Exception as e:
        print(f"错误：无法启动GUI - {e}")
        print("请确保已安装 pyserial 库：pip install pyserial")

def show_config_example():
    print("\n" + "="*60)
    print("配置文件示例 (commands_config.json)")
    print("="*60)
    try:
        with open('commands_config.json', 'r', encoding='utf-8') as f:
            content = f.read()
        print(content)
    except FileNotFoundError:
        print("错误：找不到 commands_config.json 文件")
    except Exception as e:
        print(f"错误：{e}")
    print("\n按Enter键返回...")
    input()

def show_documentation():
    print("\n正在打开文档...")
    try:
        # Windows
        if sys.platform == 'win32':
            os.startfile('GUI_README.md')
        # macOS
        elif sys.platform == 'darwin':
            os.system('open GUI_README.md')
        # Linux
        else:
            os.system('xdg-open GUI_README.md')
        print("文档已在默认程序中打开")
    except Exception as e:
        print(f"无法打开文档：{e}")
        print("请手动打开 GUI_README.md 文件")

def check_dependencies():
    """检查依赖库"""
    print("\n检查依赖库...")

    dependencies = {
        'tkinter': 'Python内置，无需安装',
        'serial': 'pip install pyserial',
        'queue': 'Python内置，无需安装',
        'threading': 'Python内置，无需安装',
        'json': 'Python内置，无需安装'
    }

    all_ok = True

    for module, install_cmd in dependencies.items():
        try:
            if module == 'serial':
                import serial
            elif module == 'tkinter':
                import tkinter
            elif module == 'queue':
                import queue
            elif module == 'threading':
                import threading
            elif module == 'json':
                import json

            print(f"  ✓ {module:15} - 已安装")
        except ImportError:
            print(f"  ✗ {module:15} - 未安装 ({install_cmd})")
            all_ok = False

    if all_ok:
        print("\n所有依赖库已就绪！")
    else:
        print("\n警告：部分依赖库未安装，请先安装")

    return all_ok

def main():
    print("\n欢迎使用串口通信可视化GUI程序！")

    # 检查依赖
    if not check_dependencies():
        print("\n请先安装缺失的依赖库")
        return

    while True:
        print_menu()

        try:
            choice = input("请选择 (1-5): ").strip()

            if choice == '1':
                launch_basic_gui()
            elif choice == '2':
                launch_advanced_gui()
            elif choice == '3':
                show_config_example()
            elif choice == '4':
                show_documentation()
            elif choice == '5':
                print("\n感谢使用，再见！")
                break
            else:
                print("\n无效的选择，请输入 1-5")

        except KeyboardInterrupt:
            print("\n\n用户中断，退出程序")
            break
        except Exception as e:
            print(f"\n错误：{e}")

if __name__ == "__main__":
    main()
