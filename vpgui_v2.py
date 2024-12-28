import os
import os.path
import winreg
from tkinter import Tk, Label, Entry, Button, filedialog, StringVar, OptionMenu, BooleanVar, Checkbutton
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image
from tkinter import ttk

def get_desktop_path():
    try:
        # 打开注册表键
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        )
        # 获取桌面路径
        desktop_path = winreg.QueryValueEx(key, "Desktop")[0]
        winreg.CloseKey(key)
        return desktop_path
    except Exception as e:
        print(f"Error getting desktop path: {e}")
        # 如果获取失败，返回默认桌面路径
        return os.path.join(os.path.expanduser("~"), "Desktop")

def handle_drop(entry, event):
    # 处理拖拽的文件或文件夹
    data = event.data
    # 移除可能的大括号和引号
    data = data.strip('{}').strip('"')
    # 如果是文件夹路径，直接使用
    if os.path.isdir(data):
        entry.delete(0, 'end')
        entry.insert(0, data)
    # 如果是文件路径，使用其所在文件夹
    elif os.path.isfile(data):
        folder = os.path.dirname(data)
        entry.delete(0, 'end')
        entry.insert(0, folder)

def adjust_image_size(input_folder, output_folder, multiple, method, progress_bar, trim_enabled):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    files = [f for f in os.listdir(input_folder) if f.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp'))]
    total_files = len(files)
    progress_bar['maximum'] = total_files

    for i, filename in enumerate(files):
        file_path = os.path.join(input_folder, filename)
        with Image.open(file_path) as img:
            # 如果启用了 trim，确保图片是 RGBA 模式
            if trim_enabled:
                # 强制转换为 RGBA 模式
                img = img.convert('RGBA')
                try:
                    # 获取 alpha 通道
                    alpha = img.getchannel('A')
                    # 获取非透明区域的边界框
                    bbox = alpha.getbbox()
                    if bbox:
                        # 裁剪掉透明区域
                        img = img.crop(bbox)
                except Exception as e:
                    print(f"Warning: Could not trim image {filename}: {e}")
            
            # 如果是扩展模式但还不是 RGBA，转换为 RGBA
            elif method == "扩展" and img.mode != 'RGBA':
                img = img.convert('RGBA')

            width, height = img.size
            
            # 优化后的尺寸计算
            def get_optimal_size(dimension):
                # 计算向上和向下取整的倍数值
                lower = (dimension // multiple) * multiple
                upper = lower + multiple
                
                # 选择最接近原始尺寸的值
                if abs(dimension - lower) <= abs(dimension - upper):
                    return lower
                return upper

            if method == "拉伸":
                # 对宽度和高度分别计算最优尺寸
                new_width = get_optimal_size(width)
                new_height = get_optimal_size(height)
            else:
                # 其他方法保持原来的向上取整逻辑
                new_width = (width + multiple - 1) // multiple * multiple
                new_height = (height + multiple - 1) // multiple * multiple

            if method == "扩展":
                new_img = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
                new_img.paste(img, ((new_width - width) // 2, (new_height - height) // 2))
            elif method == "拉伸":
                new_img = img.resize((new_width, new_height), Image.LANCZOS)
            elif method == "裁切":
                left = (width - new_width) // 2
                top = (height - new_height) // 2
                right = (width + new_width) // 2
                bottom = (height + new_height) // 2
                new_img = img.crop((left, top, right, bottom))

            output_path = os.path.join(output_folder, filename)
            # 在保存之前根据文件格式进行适当的模式转换
            if output_path.lower().endswith(('.jpg', '.jpeg')):
                # JPEG 不支持透明通道，转换回 RGB
                if new_img.mode == 'RGBA':
                    # 创建白色背景
                    background = Image.new('RGB', new_img.size, (255, 255, 255))
                    # 将 RGBA 图片粘贴到白色背景上
                    background.paste(new_img, mask=new_img.split()[3])
                    new_img = background
            
            new_img.save(output_path)
        
        progress_bar['value'] = i + 1
        root.update_idletasks()

def select_input_folder():
    folder = filedialog.askdirectory()
    if folder:
        input_folder_entry.delete(0, 'end')
        input_folder_entry.insert(0, folder)

def select_output_folder():
    folder = filedialog.askdirectory()
    if folder:
        output_folder_entry.delete(0, 'end')
        output_folder_entry.insert(0, folder)

def execute():
    # 重置进度条
    progress_bar['value'] = 0
    progress_label.config(text="")  # 清除之前的完成提示
    root.update_idletasks()
    
    input_folder = input_folder_entry.get()
    output_folder = output_folder_entry.get()
    multiple = int(multiple_entry.get())
    method = method_var.get()
    trim_enabled = trim_var.get()
    adjust_image_size(input_folder, output_folder, multiple, method, progress_bar, trim_enabled)
    
    # 任务完成后显示 Done!
    progress_label.config(text="Done!")

# 创建主窗口
root = TkinterDnD.Tk()
root.title("Pixel magnification adjustment")

# 输入文件夹
Label(root, text="input:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
input_folder_entry = Entry(root, width=40)
input_folder_entry.grid(row=0, column=1, padx=10, pady=5)
input_folder_entry.drop_target_register(DND_FILES)
input_folder_entry.dnd_bind('<<Drop>>', lambda e: handle_drop(input_folder_entry, e))
Button(root, text="choose", command=select_input_folder).grid(row=0, column=2, padx=10, pady=5, sticky='e')

# 输出文件夹
Label(root, text="output:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
output_folder_entry = Entry(root, width=40)
output_folder_entry.grid(row=1, column=1, padx=10, pady=5)

# 设置默认输出路径为桌面的 output 文件夹
default_output = os.path.join(get_desktop_path(), "output")
output_folder_entry.insert(0, default_output)

output_folder_entry.drop_target_register(DND_FILES)
output_folder_entry.dnd_bind('<<Drop>>', lambda e: handle_drop(output_folder_entry, e))
Button(root, text="choose", command=select_output_folder).grid(row=1, column=2, padx=10, pady=5, sticky='e')

# 倍率
Label(root, text="multiplier:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
multiple_entry = Entry(root, width=40)
multiple_entry.insert(0, "4")  # 使用 insert 方法设置默认值
multiple_entry.grid(row=2, column=1, padx=10, pady=5)

# 处理方式
Label(root, text="method:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
method_var = StringVar(root)
method_combo = ttk.Combobox(root, textvariable=method_var, width=37, state="readonly")
method_combo['values'] = ("扩展", "拉伸", "裁切")
method_combo.set("扩展")  # 设置默认值
method_combo.grid(row=3, column=1, padx=10, pady=5)

# 进度条
Label(root, text="Progress:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
progress_bar = ttk.Progressbar(root, orient='horizontal', length=250, mode='determinate')
progress_bar.grid(row=4, column=1, padx=10, pady=5)

# 在处理方式选择框之后添加 trim 复选框
trim_var = BooleanVar()
trim_checkbox = Checkbutton(root, text="Pretrim", variable=trim_var)
trim_checkbox.grid(row=3, column=2, padx=10, pady=5, sticky='e')

# 在文件开头的界面元素定义部分（在创建进度条之后）添加：
progress_label = Label(root, text="")
progress_label.grid(row=4, column=2, padx=10, pady=5, sticky='e')

# 执行按钮
Button(root, text="run", command=execute, width=40).grid(row=5, column=1, padx=10, pady=5)

root.mainloop()