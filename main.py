# -*- coding: utf-8 -*-
from PIL import Image
import os
# 获取当前脚本文件的绝对路径
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
                # 检查并调整图片尺寸
                new_width = width + 1 if width % 2 != 0 else width
                new_height = height + 1 if height % 2 != 0 else height
                # 如果需要调整尺寸，则进行调整
                if (width, height) != (new_width, new_height):
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                # 保存到输出文件夹，保持原格式
                img.save(os.path.join(output_folder, filename))



# 获取当前脚本文件的绝对路径
import os

# 获取当前脚本文件的绝对路径
script_directory = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    input_folder = os.path.join(script_directory, 'input')  # 设置为当前脚本所在目录下的input文件夹
    output_folder = os.path.join(script_directory, 'output')  # 设置为当前脚本所在目录下的output文件夹
    adjust_image_size(input_folder, output_folder)