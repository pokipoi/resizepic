# Add these lines at the very beginning of your script, right after the imports:
import sys
import io
import os
import time
import re
import os.path
import winreg
import configparser
import tkinter as tk
from tkinter import Tk, Label, Entry, Button, filedialog, StringVar, OptionMenu, BooleanVar, Checkbutton
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image
from tkinter import ttk
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

task_files = []
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
    try:
        # Save current settings to config
        config = configparser.ConfigParser()
        config['DEFAULT'] = {
            'DefaultInFolder': input_folder_entry.get(),
            'DefaultOutFolder': output_folder_entry.get(),
            'DefaulMultiplied': multiple_entry.get(),
            'DefaulMode': method_var.get(),
            'DefaulPretrimState': '1' if trim_var.get() else '0',
            'ProcessSubfolders': '1' if subfolder_var.get() else '0'
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        with open(config_path, 'w', encoding='utf-8') as f:
            config.write(f)
            
        # Destroy the window
        root.destroy()
    except Exception as e:
        print(f"Error saving config on exit: {e}")
        root.destroy()

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

def add_tasks_from_path(path):
    """根据路径返回图片文件列表，按照Process Subfolders复选框过滤"""
    files = []
    img_ext = ('png', 'jpg', 'jpeg', 'gif', 'bmp')
    if os.path.isfile(path) and path.lower().endswith(img_ext):
        files.append(path)
    elif os.path.isdir(path):
        if subfolder_var.get():
            # 遍历所有子目录
            for root_dir, _, filenames in os.walk(path):
                for filename in filenames:
                    if filename.lower().endswith(img_ext):
                        files.append(os.path.join(root_dir, filename))
        else:
            # 仅收集目录根下的文件
            for filename in os.listdir(path):
                if filename.lower().endswith(img_ext):
                    files.append(os.path.join(path, filename))
    return files

def add_to_task_list(new_files):
    """将新文件加入全局待处理任务列表，并更新列表框显示。如果项目已存在且状态为 done，恢复为 pending"""
    global task_files
    for f in new_files:
        indices = [i for i, item in enumerate(task_files) if item[0] == f]
        if indices:
            index = indices[0]
            if task_files[index][1] == "done":
                # 恢复该任务的 pending 状态
                task_files[index] = (f, "pending")
                task_listbox.delete(index)
                task_listbox.insert(index, f)  # 移除 "done!" 标记
                task_listbox.itemconfig(index, {'fg': 'black'})
        else:
            task_files.append((f, "pending"))
            task_listbox.insert(tk.END, f)
            
def update_task_done(index):
    """更新列表中指定项为 done!，字体显示绿色"""
    task_listbox.delete(index)
    # 运用标签颜色，需要用 Tkinter 的 itemconfig 方法，
    # 这里简单地在字符串后加上 done! 标记
    task_listbox.insert(index, f"{task_files[index][0]}  ---  done!")
    task_listbox.itemconfig(index, {'fg': 'green'})
    # 同时更新全局列表状态
    task_files[index] = (task_files[index][0], "done")

#
# 修改用于 input_folder_entry 拖入的处理函数（也适用于 choose按钮）
def handle_drop(entry, event):
    print("Handling drop event...")
    try:
        data = event.data
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        # 清理路径字符串，支持多个拖入
        matches = re.findall(r'{([^}]+)}|(\S+)', data)
        paths = [grp[0] if grp[0] else grp[1] for grp in matches]
        paths = [os.path.normpath(p) for p in paths if os.path.exists(p)]
        if not paths:
            print("No valid paths found!")
            return
        # 更新输入框显示第一个路径
        entry.delete(0, tk.END)
        entry.insert(0, paths[0])
        # 对每个路径，收集图片文件并加入待处理任务列表
        all_new_files = []
        for p in paths:
            all_new_files.extend(add_tasks_from_path(p))
        if all_new_files:
            add_to_task_list(all_new_files)
        root.update_idletasks()
    except Exception as e:
        print(f"Error in handle_drop: {e}")

#
# 修改选择输入文件夹的函数，也加入任务列表
def select_input_folder():
    folder = filedialog.askdirectory()
    if folder:
        input_folder_entry.delete(0, 'end')
        input_folder_entry.insert(0, folder)
        files = add_tasks_from_path(folder)
        if files:
            add_to_task_list(files)
def process_image(img, multiple, method, trim_enabled):
    """
    对单个 PIL.Image 对象进行处理，返回处理后的图像。
    """
    # 如果启用 pretrim，则转换为 RGBA 并裁剪透明区域
    if trim_enabled:
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        try:
            alpha = img.getchannel('A')
            bbox = alpha.getbbox()
            if bbox:
                img = img.crop(bbox)
        except Exception as e:
            print(f"Warning: Could not trim image: {e}")
    
    width, height = img.size
    if method == "Stretch":
        # 支持宽高分别调整到最优尺寸（或简单调用 resize）
        def get_optimal_size(dimension):
            lower = (dimension // multiple) * multiple
            upper = lower + multiple
            return lower if abs(dimension - lower) <= abs(dimension - upper) else upper
        new_width = get_optimal_size(width)
        new_height = get_optimal_size(height)
    else:
        new_width = (width + multiple - 1) // multiple * multiple
        new_height = (height + multiple - 1) // multiple * multiple

    if method == "Extend":
        new_img = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
        new_img.paste(img, ((new_width - width) // 2, (new_height - height) // 2))
    elif method == "Stretch":
        new_img = img.resize((new_width, new_height), Image.LANCZOS)
    elif method == "Crop":
        # Crop: 裁剪中心区域
        left = (width - new_width) // 2
        top = (height - new_height) // 2
        right = (width + new_width) // 2
        bottom = (height + new_height) // 2
        new_img = img.crop((left, top, right, bottom))
    
    # 如果输出 JPEG，而图像是RGBA，则转换为RGB（可在保存时再转换）
    return new_img

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
    # 遍历当前文件夹中的所有项
    for item in os.listdir(input_path):
        item_path = os.path.join(input_path, item)
        # 如果是图片文件
        if os.path.isfile(item_path) and item.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
            relative_path = os.path.relpath(os.path.dirname(item_path), input_path)
            output_dir = os.path.join(output_path, relative_path)
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, item)
            
            with Image.open(item_path) as img:
                # 调用通用图像处理函数生成处理后的图像
                new_img = process_image(img, multiple, method, trim_enabled)
                
                # 如果输出JPEG格式，而图像为RGBA，则转换为RGB
                if output_file.lower().endswith(('.jpg', '.jpeg')) and new_img.mode == 'RGBA':
                    background = Image.new('RGB', new_img.size, (255, 255, 255))
                    background.paste(new_img, mask=new_img.split()[3])
                    new_img = background
                    
                new_img.save(output_file)
        
        # 如果是子文件夹且启用了处理子文件夹，则递归调用 process_folder
        elif os.path.isdir(item_path) and process_subfolders:
            new_output_path = os.path.join(output_path, item)
            process_folder(item_path, new_output_path, method, multiple, trim_enabled, process_subfolders)


def quick_process(files):
    try:
        method = method_var.get()
        multiple = int(multiple_entry.get())
        trim_enabled = trim_var.get()   # 获取是否启用 pretrim
        process_subfolders = subfolder_var.get()
        
        # 预计算待处理图片总数，用于设置进度条
        def count_images(files_list):
            count = 0
            for file_path in files_list:
                if os.path.isfile(file_path) and file_path.lower().endswith(
                        ('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                    count += 1
                elif os.path.isdir(file_path):
                    if process_subfolders:
                        for root_dir, _, filenames in os.walk(file_path):
                            for filename in filenames:
                                if filename.lower().endswith(
                                        ('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                                    count += 1
                    else:
                        for filename in os.listdir(file_path):
                            if filename.lower().endswith(
                                    ('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                                count += 1
            return count
        
        total_files = count_images(files)
        progress_bar.config(maximum=total_files)
        progress_bar['value'] = 0
        progress_label.config(text="")
        root.update_idletasks()

        current_progress = 0
        processed_any = False
        
        for file_path in files:
            print(f"Debug: Processing file: {file_path}")
            # 如果是图片文件
            if os.path.isfile(file_path) and file_path.lower().endswith(
                    ('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                processed_any = True
                with Image.open(file_path) as img:
                    new_img = process_image(img, multiple, method, trim_enabled)
                    # 针对 JPEG 格式转换（JPEG 不支持透明通道）
                    if file_path.lower().endswith(('.jpg', '.jpeg')) and new_img.mode == 'RGBA':
                        background = Image.new('RGB', new_img.size, (255, 255, 255))
                        background.paste(new_img, mask=new_img.split()[3])
                        new_img = background
                    print(f"Debug: Saving image: {file_path}")
                    new_img.save(file_path)
                current_progress += 1
                progress_bar['value'] = current_progress
                root.update_idletasks()
            
            # 如果是文件夹
            elif os.path.isdir(file_path):
                print(f"Debug: Directory found: {file_path}")
                if process_subfolders:
                    for root_dir, _, filenames in os.walk(file_path):
                        for filename in filenames:
                            if filename.lower().endswith(
                                    ('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                                processed_any = True
                                img_path = os.path.join(root_dir, filename)
                                with Image.open(img_path) as img:
                                    new_img = process_image(img, multiple, method, trim_enabled)
                                    if img_path.lower().endswith(('.jpg', '.jpeg')) and new_img.mode == 'RGBA':
                                        background = Image.new('RGB', new_img.size, (255, 255, 255))
                                        background.paste(new_img, mask=new_img.split()[3])
                                        new_img = background
                                    new_img.save(img_path)
                                current_progress += 1
                                progress_bar['value'] = current_progress
                                root.update_idletasks()
                else:
                    # 仅处理目录根下的图片
                    for filename in os.listdir(file_path):
                        if filename.lower().endswith(
                                ('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                            processed_any = True
                            img_path = os.path.join(file_path, filename)
                            with Image.open(img_path) as img:
                                new_img = process_image(img, multiple, method, trim_enabled)
                                if img_path.lower().endswith(('.jpg', '.jpeg')) and new_img.mode == 'RGBA':
                                    background = Image.new('RGB', new_img.size, (255, 255, 255))
                                    background.paste(new_img, mask=new_img.split()[3])
                                    new_img = background
                                new_img.save(img_path)
                            current_progress += 1
                            progress_bar['value'] = current_progress
                            root.update_idletasks()
        if processed_any:
            progress_label.config(text="Quick process done!")
        else:
            progress_label.config(text="No images found!")
            
    except Exception as e:
        print(f"Error in quick process: {e}")
        progress_label.config(text="Error!")
   
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

def remove_selected_task():
    global task_files
    # 获取所有选中项的索引（返回元组）
    selected_indices = task_listbox.curselection()
    if selected_indices:
        # 从大到小排序，确保删除时索引正确
        for index in sorted(selected_indices, reverse=True):
            task_listbox.delete(index)
            del task_files[index]

# 添加清空所有任务按钮
def clear_all_tasks():
    global task_files
    task_listbox.delete(0, tk.END)
    task_files.clear()
def execute():
    global task_files
    progress_bar['value'] = 0
    progress_label.config(text="")  # 清除之前的完成提示
    root.update_idletasks()
    
    # 获取加工参数
    multiple = int(multiple_entry.get())
    method = method_var.get()
    trim_enabled = trim_var.get()
    
    total = len(task_files)
    progress_bar.config(maximum=total)
    
    for index, (file_path, status) in enumerate(task_files):
        # 只处理未处理项
        if status != "done":
            print(f"Processing: {file_path}")
            try:
                with Image.open(file_path) as img:
                    new_img = process_image(img, multiple, method, trim_enabled)
                    # 针对 JPEG 格式转换
                    if file_path.lower().endswith(('.jpg', '.jpeg')) and new_img.mode == 'RGBA':
                        background = Image.new('RGB', new_img.size, (255, 255, 255))
                        background.paste(new_img, mask=new_img.split()[3])
                        new_img = background
                    new_img.save(file_path)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
            # 更新进度与列表显示
            update_task_done(index)
            progress_bar['value'] = index + 1
            root.update_idletasks()
    progress_label.config(text="Done!")

def handle_quick_drop(event):
    try:
        data = event.data
        if isinstance(data, str):
            matches = re.findall(r'{([^}]+)}|(\S+)', data)
            paths = [grp[0] if grp[0] else grp[1] for grp in matches]
            paths = [os.path.normpath(p) for p in paths if os.path.exists(p)]
            if not paths:
                progress_label.config(text="No valid files!")
                return
            # 对每个路径，收集图片文件
            quick_files = []
            for p in paths:
                quick_files.extend(add_tasks_from_path(p))
            if quick_files:
                quick_process(quick_files)
            else:
                progress_label.config(text="No images found!")
    except Exception as e:
        progress_label.config(text=f"Error handling quick drop: {str(e)}")
        print(f"Error handling quick drop: {e}")

def handle_task_list_drop(event):
    try:
        data = event.data
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        # 清理路径字符串，支持多个拖入
        matches = re.findall(r'{([^}]+)}|(\S+)', data)
        paths = [grp[0] if grp[0] else grp[1] for grp in matches]
        paths = [os.path.normpath(p) for p in paths if os.path.exists(p)]
        if not paths:
            print("No valid paths found!")
            return
        # 对每个路径，收集图片文件，并加入任务列表
        all_new_files = []
        for p in paths:
            all_new_files.extend(add_tasks_from_path(p))
        if all_new_files:
            add_to_task_list(all_new_files)
        root.update_idletasks()
    except Exception as e:
        print(f"Error in handle_task_list_drop: {e}")

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

# 添加Process Subfolders 复选框
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

task_listbox = tk.Listbox(root, width=50, height=20, selectmode=tk.EXTENDED)
task_listbox.grid(row=0, column=3, rowspan=6, padx=10, pady=5)
task_listbox.drop_target_register(DND_FILES)
task_listbox.dnd_bind('<<Drop>>', handle_task_list_drop)

# 添加移除选中按钮
remove_selected_btn = Button(root, text="Remove Selected", command=remove_selected_task)
remove_selected_btn.grid(row=6, column=3, padx=10, pady=5, sticky='ew')
clear_all_btn = Button(root, text="Clear All Tasks", command=clear_all_tasks)
clear_all_btn.grid(row=7, column=3, padx=10, pady=5, sticky='ew')

# 执行按钮
Button(root, text="run", command=execute, width=35).grid(row=5, column=1, padx=10, pady=5)
Button(root, text="config", command=open_config, width=8).grid(row=5, column=2, padx=10, pady=5)

root.protocol("WM_DELETE_WINDOW", save_config)

root.mainloop()