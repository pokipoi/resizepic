# -*- coding: utf-8 -*-
from PIL import Image
import os

def adjust_image_size(input_folder, output_folder):
    # 确保输出文件夹存在
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 遍历输入文件夹中的所有文件
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
            file_path = os.path.join(input_folder, filename)
            # 打开图片
            with Image.open(file_path) as img:
                width, height = img.size
                # 计算新的宽度和高度，使其为4的倍数
                new_width = (width + 3) // 4 * 4
                new_height = (height + 3) // 4 * 4
                # 如果需要调整尺寸，则进行调整
                if (width, height) != (new_width, new_height):
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                # 保存到输出文件夹，保持原格式
                img.save(os.path.join(output_folder, filename))

# 获取当前脚本文件的绝对路径
script_directory = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    input_folder = os.path.join(script_directory)  # 设置为当前脚本所在目录
    output_folder = os.path.join(script_directory, 'output')  # 设置为当前脚本所在目录下的output文件夹
    adjust_image_size(input_folder, output_folder)