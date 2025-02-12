# Add these lines at the very beginning of your script, right after the imports:
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
import os.path
import winreg
import configparser
import tkinter as tk
from tkinter import Tk, Label, Entry, Button, filedialog, StringVar, OptionMenu, BooleanVar, Checkbutton
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image
from tkinter import ttk


def read_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    # 设置默认值
    default_config = {
        'DefaultInFolder': os.path.join(get_desktop_path(), "input"),
        'DefaultOutFolder': os.path.join(get_desktop_path(), "output"),
        'DefaulMultiplied': '2',
        'DefaulMode': 'Crop',
        'DefaulPretrimState': '1',
        'ProcessSubfolders': '0' 
    }
    
    if not os.path.exists(config_path):
        config['DEFAULT'] = default_config
        with open(config_path, 'w', encoding='utf-8') as f:
            config.write(f)
    else:
        config.read(config_path, encoding='utf-8')
        # 确保所有键都存在
        for key, value in default_config.items():
            if key not in config['DEFAULT']:
                config['DEFAULT'][key] = value
    
    return config['DEFAULT']

def save_config():
    config = configparser.ConfigParser()
    try:
        config['DEFAULT'] = {
            'DefaultInFolder': input_folder_entry.get().encode('utf-8').decode('utf-8'),
            'DefaultOutFolder': output_folder_entry.get().encode('utf-8').decode('utf-8'),
            'DefaulMultiplied': multiple_entry.get(),
            'DefaulMode': method_var.get(),
            'DefaulPretrimState': '1' if trim_var.get() else '0',
            'ProcessSubfolders': '1' if subfolder_var.get() else '0'  # 添加新选项
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        with open(config_path, 'w', encoding='utf-8') as f:
            config.write(f)
    except Exception as e:
        print(f"Error saving config: {e}")
def open_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    try:
        # Store original modification time
        original_mtime = os.path.getmtime(config_path) if os.path.exists(config_path) else None
        
        # Open config in Notepad
        os.system(f'notepad "{config_path}"')
        
        # Wait for Notepad to close and check if file was modified
        if original_mtime and os.path.exists(config_path):
            new_mtime = os.path.getmtime(config_path)
            if new_mtime > original_mtime:
                # Reload configuration
                config = read_config()
                # Update UI with new values
                input_folder_entry.delete(0, tk.END)
                input_folder_entry.insert(0, config.get('DefaultInFolder'))
                output_folder_entry.delete(0, tk.END)
                output_folder_entry.insert(0, config.get('DefaultOutFolder'))
                multiple_entry.delete(0, tk.END)
                multiple_entry.insert(0, config.get('DefaulMultiplied'))
                method_var.set(config.get('DefaulMode'))
                trim_var.set(config.get('DefaulPretrimState') == '1')
                
    except Exception as e:
        print(f"Error handling config file: {e}")

def handle_drop(entry, event):
    print(f"Handling drop event...")
    
    try:
        data = event.data
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        
        # 清理路径字符串
        data = data.strip('{}').strip('"')
        data = os.path.normpath(data)  # 标准化路径
        print(f"Processed path: {data}")
        
        # 检查并处理路径
        if os.path.exists(data):
            if os.path.isdir(data):
                entry.delete(0, tk.END)
                entry.insert(0, data)
                print(f"Updated entry with directory: {data}")
            elif os.path.isfile(data):
                folder = os.path.dirname(data)
                entry.delete(0, tk.END)
                entry.insert(0, folder)
                print(f"Updated entry with parent directory: {folder}")
            
            # 强制更新Entry和整个窗口
            entry.update()
            root.update_idletasks()
            
            # 保存配置
            save_config()
            print("Configuration saved")
            
        else:
            print(f"Invalid path: {data}")
    
    except Exception as e:
        print(f"Error in handle_drop: {str(e)}")



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
    
def process_folder(input_path, output_path, method, multiple, trim_enabled, process_subfolders=False):
    # 处理当前文件夹中的图片
    for item in os.listdir(input_path):
        item_path = os.path.join(input_path, item)
        if os.path.isfile(item_path) and item.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
            relative_path = os.path.relpath(os.path.dirname(item_path), input_path)
            output_dir = os.path.join(output_path, relative_path)
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, item)
            
            with Image.open(item_path) as img:
                adjust_image_size(img, output_file, method, multiple, trim_enabled)
        
        # 如果是文件夹且启用了子文件夹处理
        elif os.path.isdir(item_path) and process_subfolders:
            new_output_path = os.path.join(output_path, item)
            process_folder(item_path, new_output_path, method, multiple, trim_enabled, process_subfolders)


# 在 execute() 函数后添加新的快速处理函数
def quick_process(files):
    try:
        method = method_var.get()
        multiple = int(multiple_entry.get())
        trim_enabled = trim_var.get()
        process_subfolders = subfolder_var.get()
        
        processed_any = False  # 添加标志来追踪是否处理了任何文件
        
        for file_path in files:
            if os.path.isfile(file_path) and file_path.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                processed_any = True
                with Image.open(file_path) as img:
                    # 处理图片
                    width, height = img.size
                    new_width = (width + multiple - 1) // multiple * multiple
                    new_height = (height + multiple - 1) // multiple * multiple
                    
                    if method == "Extend":
                        new_img = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
                        new_img.paste(img, ((new_width - width) // 2, (new_height - height) // 2))
                    elif method == "Stretch":
                        new_img = img.resize((new_width, new_height), Image.LANCZOS)
                    elif method == "Crop":
                        left = (width - new_width) // 2
                        top = (height - new_height) // 2
                        right = (width + new_width) // 2
                        bottom = (height + new_height) // 2
                        new_img = img.crop((left, top, right, bottom))

                    # 保存前处理格式
                    if file_path.lower().endswith(('.jpg', '.jpeg')):
                        if new_img.mode == 'RGBA':
                            background = Image.new('RGB', new_img.size, (255, 255, 255))
                            background.paste(new_img, mask=new_img.split()[3])
                            new_img = background
                    
                    new_img.save(file_path)
            
            elif os.path.isdir(file_path):
                if process_subfolders:
                    for root_dir, _, files in os.walk(file_path):
                        for filename in files:
                            if filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                                processed_any = True
                                img_path = os.path.join(root_dir, filename)
                                with Image.open(img_path) as img:
                                    # 处理图片
                                    width, height = img.size
                                    new_width = (width + multiple - 1) // multiple * multiple
                                    new_height = (height + multiple - 1) // multiple * multiple
                                    
                                    if method == "Extend":
                                        new_img = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
                                        new_img.paste(img, ((new_width - width) // 2, (new_height - height) // 2))
                                    elif method == "Stretch":
                                        new_img = img.resize((new_width, new_height), Image.LANCZOS)
                                    elif method == "Crop":
                                        left = (width - new_width) // 2
                                        top = (height - new_height) // 2
                                        right = (width + new_width) // 2
                                        bottom = (height + new_height) // 2
                                        new_img = img.crop((left, top, right, bottom))

                                    # 保存前处理格式
                                    if img_path.lower().endswith(('.jpg', '.jpeg')):
                                        if new_img.mode == 'RGBA':
                                            background = Image.new('RGB', new_img.size, (255, 255, 255))
                                            background.paste(new_img, mask=new_img.split()[3])
                                            new_img = background
                                    
                                    new_img.save(img_path)
                else:
                    # 只处理当前文件夹中的图片
                    for filename in os.listdir(file_path):
                        if filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                            processed_any = True
                            img_path = os.path.join(file_path, filename)
                            with Image.open(img_path) as img:
                                # 处理图片代码与上面相同
                                width, height = img.size
                                new_width = (width + multiple - 1) // multiple * multiple
                                new_height = (height + multiple - 1) // multiple * multiple
                                
                                if method == "Extend":
                                    new_img = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
                                    new_img.paste(img, ((new_width - width) // 2, (new_height - height) // 2))
                                elif method == "Stretch":
                                    new_img = img.resize((new_width, new_height), Image.LANCZOS)
                                elif method == "Crop":
                                    left = (width - new_width) // 2
                                    top = (height - new_height) // 2
                                    right = (width + new_width) // 2
                                    bottom = (height + new_height) // 2
                                    new_img = img.crop((left, top, right, bottom))

                                # 保存前处理格式
                                if img_path.lower().endswith(('.jpg', '.jpeg')):
                                    if new_img.mode == 'RGBA':
                                        background = Image.new('RGB', new_img.size, (255, 255, 255))
                                        background.paste(new_img, mask=new_img.split()[3])
                                        new_img = background
                                
                                new_img.save(img_path)
        
        if processed_any:
            progress_label.config(text="Quick process done!")
        else:
            progress_label.config(text="No images found!")
            
    except Exception as e:
        print(f"Error in quick process: {e}")
        progress_label.config(text="Error!")

def handle_quick_drop(event):
    try:
        data = event.data
        if isinstance(data, str):
            # 处理 Windows 拖放数据格式
            if data.startswith('{') and data.endswith('}'):
                data = data[1:-1]
            
            paths = []
            if '"' in data:
                # 使用 os.path.normpath 标准化路径
                parts = data.split('" "')
                paths = [os.path.normpath(p.strip('"')) for p in parts]
            else:
                paths = [os.path.normpath(data)]
            
            # 使用 os.path.abspath 获取绝对路径
            files = [os.path.abspath(p) for p in paths]
            
            valid_files = []
            for f in files:
                try:
                    # 检查文件是否存在，使用 encode/decode 处理中文路径
                    if os.path.exists(f):
                        valid_files.append(f)
                except UnicodeEncodeError:
                    # 如果出现编码错误，尝试使用 utf-8 编码
                    encoded_path = f.encode('utf-8')
                    if os.path.exists(encoded_path.decode('utf-8')):
                        valid_files.append(encoded_path.decode('utf-8'))
            
            if valid_files:
                quick_process(valid_files)
            else:
                progress_label.config(text="No valid files!")
                
    except Exception as e:
        progress_label.config(text="Error!")
        print(f"Error handling quick drop: {str(e)}")

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
            elif method == "Extend" and img.mode != 'RGBA':
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

            if method == "Stretch":
                # 对宽度和高度分别计算最优尺寸
                new_width = get_optimal_size(width)
                new_height = get_optimal_size(height)
            else:
                # 其他方法保持原来的向上取整逻辑
                new_width = (width + multiple - 1) // multiple * multiple
                new_height = (height + multiple - 1) // multiple * multiple

            if method == "Extend":
                new_img = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
                new_img.paste(img, ((new_width - width) // 2, (new_height - height) // 2))
            elif method == "Stretch":
                new_img = img.resize((new_width, new_height), Image.LANCZOS)
            elif method == "Crop":
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
    
    adjust_image_size(input_folder, output_folder, multiple, method, progress_bar, trim_enabled)
    save_config()  # 保存当前设置到配置文件

    # 任务完成后显示 Done!
    progress_label.config(text="Done!")

# 创建主窗口
root = TkinterDnD.Tk()
root.title("Pixel magnification adjustment")
try:
    icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
except Exception as e:
    print(f"Error loading icon: {e}")

# 读取配置
config = read_config()



# 输入文件夹
Label(root, text="input:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
input_folder_entry = Entry(root, width=40)
input_folder_entry.grid(row=0, column=1, padx=10, pady=5)
input_folder_entry.insert(0, config.get('DefaultInFolder', os.path.join(get_desktop_path(), "input")))
input_folder_entry.drop_target_register(DND_FILES)
input_folder_entry.dnd_bind('<<Drop>>', lambda e: (handle_drop(input_folder_entry, e), root.update()))
Button(root, text="choose", command=select_input_folder).grid(row=0, column=2, padx=10, pady=5, sticky='e')

# 输出文件夹
Label(root, text="output:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
output_folder_entry = Entry(root, width=40)
output_folder_entry.grid(row=1, column=1, padx=10, pady=5)
output_folder_entry.insert(0, config.get('DefaultOutFolder', os.path.join(get_desktop_path(), "output")))
output_folder_entry.drop_target_register(DND_FILES)
output_folder_entry.dnd_bind('<<Drop>>', lambda e: (handle_drop(output_folder_entry, e), root.update()))
Button(root, text="choose", command=select_output_folder).grid(row=1, column=2, padx=10, pady=5, sticky='e')

# 倍率
Label(root, text="multiplier:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
multiple_entry = Entry(root, width=40)
multiple_entry.insert(0, config.get('DefaulMultiplied', "4"))
multiple_entry.grid(row=2, column=1, padx=10, pady=5)

# 处理方式
Label(root, text="method:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
method_var = StringVar(root)
method_combo = ttk.Combobox(root, textvariable=method_var, width=37, state="readonly")
method_combo['values'] = ("Extend", "Stretch", "Crop")
method_combo.set(config.get('DefaulMode', "Extend")) # 设置默认值
method_combo.grid(row=3, column=1, padx=10, pady=5)

# 进度条
Label(root, text="Progress:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
progress_bar = ttk.Progressbar(root, orient='horizontal', length=250, mode='determinate')
progress_bar.grid(row=4, column=1, padx=10, pady=5)

# 在处理方式选择框之后添加 trim 复选框
trim_var = BooleanVar()
trim_checkbox = Checkbutton(root, text="Pretrim", variable=trim_var)
trim_checkbox.grid(row=3, column=2, padx=10, pady=5, sticky='e')
trim_var.set(config.get('DefaulPretrimState'))

# 在创建trim复选框后添加
subfolder_var = BooleanVar()
subfolder_checkbox = Checkbutton(root, text="Process Subfolders", variable=subfolder_var)
subfolder_checkbox.grid(row=2, column=2, padx=10, pady=5, sticky='e')
subfolder_var.set(config.get('ProcessSubfolders') == '1')

# 在文件开头的界面元素定义部分（在创建进度条之后）添加：
progress_label = Label(root, text="")
progress_label.grid(row=4, column=2, padx=10, pady=5, sticky='e')

# 在创建run按钮之前添加快速处理区域
quick_drop_frame = Label(root, text="直接输出", relief="solid", width=10, height=2)
quick_drop_frame.grid(row=5, column=0, padx=10, pady=5, sticky='w')
quick_drop_frame.drop_target_register(DND_FILES)
quick_drop_frame.dnd_bind('<<Drop>>', handle_quick_drop)

# 执行按钮
Button(root, text="run", command=execute, width=35).grid(row=5, column=1, padx=10, pady=5)
Button(root, text="config", command=open_config, width=8).grid(row=5, column=2, padx=10, pady=5)

root.mainloop()