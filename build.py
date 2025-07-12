#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 auto-py-to-exe 配置的单文件编译脚本
使用 releaseConfig.json 的配置项自动生成 PyInstaller 命令
"""

import os
import sys
import json
import subprocess
import site
from pathlib import Path

def get_script_dir():
    """获取脚本所在目录"""
    return Path(__file__).parent.absolute()

def find_tkinterdnd2_path():
    """自动查找 tkinterdnd2 包路径"""
    try:
        import tkinterdnd2
        return Path(tkinterdnd2.__file__).parent
    except ImportError:
        # 在 site-packages 中查找
        for site_dir in site.getsitepackages():
            tkinterdnd2_path = Path(site_dir) / "tkinterdnd2"
            if tkinterdnd2_path.exists():
                return tkinterdnd2_path
        return None

def find_tkdnd_path():
    """自动查找 tkdnd 包路径"""
    for site_dir in site.getsitepackages():
        tkdnd_path = Path(site_dir) / "tkdnd"
        if tkdnd_path.exists():
            return tkdnd_path
    return None

def build_executable():
    """根据 releaseConfig.json 配置构建可执行文件"""
    script_dir = get_script_dir()
    config_file = script_dir / "releaseConfig.json"
    
    if not config_file.exists():
        print(f"错误: 配置文件 {config_file} 不存在")
        return False
    
    # 读取配置
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"错误: 读取配置文件失败 - {e}")
        return False
    
    # 构建 PyInstaller 命令
    cmd = ["pyinstaller"]
    
    # 处理配置选项
    options = config.get("pyinstallerOptions", [])
    py_file = None
    icon_file = None
    data_files = []
    
    for option in options:
        dest = option.get("optionDest")
        value = option.get("value")
        
        if dest == "filenames" and value:
            py_file = Path(value).name  # 使用相对路径
        elif dest == "onefile" and value:
            cmd.append("--onedir")
        elif dest == "console" and not value:
            cmd.append("--noconsole")
        elif dest == "icon_file" and value:
            icon_file = script_dir / "icon.ico"
            if icon_file.exists():
                cmd.extend(["--icon", str(icon_file)])
        elif dest == "noconfirm" and value:
            cmd.append("--noconfirm")
        elif dest == "datas" and value:
            data_files.append(value)
    
    # 处理数据文件 - 自动查找依赖包路径
    tkinterdnd2_path = find_tkinterdnd2_path()
    tkdnd_path = find_tkdnd_path()
    
    if tkinterdnd2_path:
        cmd.extend(["--add-data", f"{tkinterdnd2_path};tkinterdnd2/"])
        print(f"找到 tkinterdnd2 路径: {tkinterdnd2_path}")
    else:
        print("警告: 未找到 tkinterdnd2 包")
    
    if tkdnd_path:
        cmd.extend(["--add-data", f"{tkdnd_path};tkdnd/"])
        print(f"找到 tkdnd 路径: {tkdnd_path}")
    else:
        print("警告: 未找到 tkdnd 包")
    
    # 添加图标文件
    if icon_file and icon_file.exists():
        cmd.extend(["--add-data", f"{icon_file};."])
        print(f"添加图标文件: {icon_file}")
    
    # 添加主 Python 文件
    if py_file:
        main_py = script_dir / py_file
        if main_py.exists():
            cmd.append(str(main_py))
        else:
            print(f"错误: 主文件 {main_py} 不存在")
            return False
    else:
        print("错误: 未找到主 Python 文件")
        return False
    
    # 输出构建命令
    print("执行 PyInstaller 命令:")
    print(" ".join(cmd))
    print()
    
    # 执行构建
    try:
        result = subprocess.run(cmd, cwd=script_dir, check=True)
        print("\n构建成功!")
        
        # 查找生成的可执行文件
        dist_dir = script_dir / "dist"
        if dist_dir.exists():
            exe_files = list(dist_dir.glob("*.exe"))
            if exe_files:
                print(f"可执行文件位置: {exe_files[0]}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n构建失败: {e}")
        return False
    except FileNotFoundError:
        print("错误: 未找到 PyInstaller，请先安装: pip install pyinstaller")
        return False

def main():
    """主函数"""
    print("ResizePic 自动编译脚本")
    print("=" * 40)
    
    # 检查依赖
    try:
        import PyInstaller
        print(f"PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("错误: 未安装 PyInstaller")
        print("请运行: pip install pyinstaller")
        return 1
    
    # 开始构建
    if build_executable():
        print("\n编译完成!")
        return 0
    else:
        print("\n编译失败!")
        return 1

if __name__ == "__main__":
    sys.exit(main())