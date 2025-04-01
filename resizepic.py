
import sys
import io
import os
import time
import re
import os.path
import winreg
import configparser
import tkinter as tk
import threading
import queue
from PIL import Image, ImageTk


from tkinter import Tk, Label, Entry, Button, filedialog, StringVar, OptionMenu, BooleanVar, Checkbutton
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image, ImageTk
Image.MAX_IMAGE_PIXELS = None  # 禁用解压炸弹警告

# Cairo错误处理 - 简化图标加载逻辑
try:
    # 尝试直接加载PNG/ICO图标，不使用SVG转换
    pin_on_path = resource_path('pin_on.png')  # 改为直接使用PNG图标
    pin_off_path = resource_path('pin_off.png')
    
    if os.path.exists(pin_on_path) and os.path.exists(pin_off_path):
        pin_on_icon = ImageTk.PhotoImage(Image.open(pin_on_path).resize((24, 24)))
        pin_off_icon = ImageTk.PhotoImage(Image.open(pin_off_path).resize((24, 24)))
    else:
        # 图标文件不存在，使用文本按钮
        raise FileNotFoundError("Icon files not found")
except Exception as e:
    print(f"Using text icon instead: {e}")
    # 使用Unicode字符作为备用图标
    pin_on_icon = None
    pin_off_icon = None

from tkinter import ttk
from gpu_processor_opencl import process_image_opencl 
if getattr(sys.stdout, 'buffer', None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

task_files = []
thumbnail_images = {}
# 全局队列用于在线程间传递数据
thumbnail_queue = queue.Queue()
thumbnail_loading = False  # 标记是否正在加载缩略图
thumbnail_status_label = None
def resource_path(relative_path):
    """
    获取资源文件的绝对路径，打包后返回 exe 所在的目录（而非临时解压目录）
    """
    if getattr(sys, 'frozen', False):  # 如果是打包后运行
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
def read_config():
    config = configparser.ConfigParser()
    config_path = resource_path('config.ini') 
    
    # 设置默认值
    default_config = {
        'DefaultInFolder': os.path.join(get_desktop_path(), "input"),
        'DefaultOutFolder': os.path.join(get_desktop_path(), "output"),
        'DefaulMultiplied': '2',
        'DefaulMode': 'Extend',
        'DefaulPretrimState': '0',
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
        
        config_path = resource_path('config.ini') 
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
    """将新文件加入全局待处理任务列表，并更新显示。
       如果项目已存在且状态为 done，则恢复为 pending（无论是列表或缩略图视图均相同）"""
    global task_files
    for f in new_files:
        indices = [i for i, item in enumerate(task_files) if item[0] == f]
        if indices:
            index = indices[0]
            if task_files[index][1] == "done":
                task_files[index] = (f, "pending")
        else:
            task_files.append((f, "pending"))
    update_task_display()

def update_task_done(index):
    """更新指定任务状态为 done，并刷新显示，
       缩略图视图中会显示处理完成后的缩略图以及绿色 done 字样"""
    task_files[index] = (task_files[index][0], "done")
    update_task_display()
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

def handle_output_drop(entry, event):
    try:
        data = event.data
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        # 提取所有拖入路径
        matches = re.findall(r'{([^}]+)}|(\S+)', data)
        paths = [grp[0] if grp[0] else grp[1] for grp in matches]
        # 仅保留文件夹
        valid_paths = [os.path.normpath(p) for p in paths if os.path.isdir(p)]
        if valid_paths:
            entry.delete(0, tk.END)
            entry.insert(0, valid_paths[0])
        else:
            print("No valid directory dropped!")
    except Exception as e:
        print(f"Error in handle_output_drop: {e}")
# 修改选择输入文件夹的函数，也加入任务列表
def select_input_folder():
    folder = filedialog.askdirectory()
    if folder:
        input_folder_entry.delete(0, 'end')
        input_folder_entry.insert(0, folder)
        files = add_tasks_from_path(folder)
        if files:
            add_to_task_list(files)

def _process_image_cpu(img, multiple, method, trim_enabled):
    """
    原始 CPU 处理图像的函数
    """
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
        left = (width - new_width) // 2
        top = (height - new_height) // 2
        right = (width + new_width) // 2
        bottom = (height + new_height) // 2
        new_img = img.crop((left, top, right, bottom))
    return new_img

def process_image(img, multiple, method, trim_enabled):
    """
    根据 GPU 处理开关（gpu_var）决定是否调用 GPU 算法。
    如果 gpu_var 为 True，则调用 gpu_processor.process_image_gpu，否则调用 CPU 算法。
    调用其他地方使用 process_image 的代码无需修改。
    """
    try:
        use_gpu = gpu_var.get()
    except Exception as e:
        use_gpu = False
    if use_gpu:
        return process_image_opencl(img, multiple, method, trim_enabled)
    else:
        return _process_image_cpu(img, multiple, method, trim_enabled)
    
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
            progress_label.config(text="Quick process done!",fg="#9bd300")
        else:
            progress_label.config(text="No images found!")
            
    except Exception as e:
        print(f"Error in quick process: {e}")
        progress_label.config(text="Error!")
   
def select_input_folder():
    folder = filedialog.askdirectory()
    if folder:
        clear_all_tasks()  
        input_folder_entry.delete(0, 'end')
        input_folder_entry.insert(0, folder)
        # 刷新待处理任务列表
        files = add_tasks_from_path(folder)
        if files:
            add_to_task_list(files)

def select_output_folder():
    folder = filedialog.askdirectory()
    if folder:
        output_folder_entry.delete(0, 'end')
        output_folder_entry.insert(0, folder)

def remove_selected_task():
    global task_files
    if view_mode.get() == "list":
        # 列表视图模式 (Treeview)
        selected_items = task_listbox.selection()
        if selected_items:
            # 获取每个项目对应的索引
            selected_indices = []
            for item in selected_items:
                # 找出该项在原始任务列表中的位置
                item_idx = task_listbox.index(item)
                selected_indices.append(item_idx)
                
            # 从大到小排序，确保删除时索引正确
            for index in sorted(selected_indices, reverse=True):
                del task_files[index]
            
            # 更新显示
            update_task_display()
    else:
        # 缩略图模式
        selected_indices = []
        for widget in thumbnail_frame.winfo_children():
            if hasattr(widget, "selected") and widget.selected:
                selected_indices.append(widget.thumb_index)
        
        # 去除重复，倒序删除确保索引正确
        for index in sorted(set(selected_indices), reverse=True):
            del task_files[index]
        
        # 更新显示
        update_task_display()

# 添加清空所有任务按钮
def clear_all_tasks():
    global task_files
    # 清空 Treeview 控件
    for item in task_listbox.get_children():
        task_listbox.delete(item)
    # 清空任务列表
    task_files.clear()
    # 更新显示
    update_task_display()
def execute():
    global task_files

    # 刷新任务列表：将状态为 "done" 的任务重置为 "pending"
    for index, (file_path, status) in enumerate(task_files):
        if status == "done":
            task_files[index] = (file_path, "pending")
    update_task_display()

    progress_bar['value'] = 0
    progress_label.config(text="")  # 清除之前的完成提示
    root.update_idletasks()
    
    multiple = int(multiple_entry.get())
    method = method_var.get()
    trim_enabled = trim_var.get()
    process_subfolders = subfolder_var.get()
    output_folder = output_folder_entry.get()
    
    # 重新计算待处理图片总数，用于设置进度条
    def count_images(files_list):
        count = 0
        for file_path, _ in files_list:
            if os.path.isfile(file_path) and file_path.lower().endswith(
                    ('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                count += 1
            elif os.path.isdir(file_path):
                if process_subfolders:
                    for root_dir, _, filenames in os.walk(file_path):
                        for filename in filenames:
                            if filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                                count += 1
                else:
                    for filename in os.listdir(file_path):
                        if filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                            count += 1
        return count

    total = count_images(task_files)
    progress_bar.config(maximum=total)
    current_progress = 0

    for index, (file_path, status) in enumerate(task_files):
        # 只处理未处理项
        if status != "done":
            print(f"Processing: {file_path}")
            try:
                if os.path.isfile(file_path) and file_path.lower().endswith(
                        ('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                    # 如果文件在输入文件夹内，则保留相对路径，否则仅取文件名
                    input_folder = input_folder_entry.get()
                    abs_file = os.path.abspath(file_path)
                    abs_input = os.path.abspath(input_folder)
                    if abs_file.startswith(abs_input):
                        relative = os.path.relpath(file_path, input_folder)
                    else:
                        relative = os.path.basename(file_path)
                    out_file = os.path.join(output_folder, relative)
                    os.makedirs(os.path.dirname(out_file), exist_ok=True)
                    
                    with Image.open(file_path) as img:
                        new_img = process_image(img, multiple, method, trim_enabled)
                        # 针对 JPEG 格式转换（JPEG 不支持透明通道）
                        if file_path.lower().endswith(('.jpg', '.jpeg')) and new_img.mode == 'RGBA':
                            background = Image.new('RGB', new_img.size, (255, 255, 255))
                            background.paste(new_img, mask=new_img.split()[3])
                            new_img = background
                        print(f"Saving processed image to: {out_file}")
                        new_img.save(out_file)
                    current_progress += 1
                    progress_bar['value'] = current_progress
                    root.update_idletasks()
                    
                elif os.path.isdir(file_path):
                    # 对文件夹调用 process_folder 函数，并将输出目录设为 output_folder
                    print(f"Processing directory: {file_path}")
                    process_folder(file_path, output_folder, method, multiple, trim_enabled, process_subfolders)
                    # 此处对于文件夹内的进度更新较难精确计数，可按实际情况调节
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
            # 标记当前任务已完成
            task_files[index] = (file_path, "done")
            update_task_display()
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

def toggle_thumbnail_select(event):
    """切换缩略图标签的选中状态，选中时改变背景色"""
    label = event.widget
    if not hasattr(label, "selected") or not label.selected:
        label.selected = True
        # 改变背景以表示选中，颜色可根据需要调整
        label.config(bg="lightblue")
    else:
        label.selected = False
        # 恢复为容器背景色
        label.config(bg=thumbnail_frame.cget("bg"))


def load_thumbnails_thread(files, multiple, method, trim_enabled, items_per_row):
    """在后台线程中加载缩略图"""
    global thumbnail_loading
    thumbnail_loading = True
    
    # 限制显示数量
    MAX_THUMBNAILS = 50
    display_count = min(len(files), MAX_THUMBNAILS)
    
    for idx in range(display_count):
        if idx >= len(files):
            break
            
        f, status = files[idx]
        try:
            img = Image.open(f)
            img.thumbnail((64, 64))

            # 如果图像有透明通道，则绘制描边
            if 'A' in img.getbands():
                from PIL import ImageDraw
                draw = ImageDraw.Draw(img)
                draw.rectangle((0, 0, img.width - 1, img.height - 1), outline="#9dd500")
            
            # 计算行列位置
            row = idx // items_per_row
            col = idx % items_per_row
            
            # 添加尺寸信息
            orig_dims, new_dims = calculate_new_dimensions(f, multiple, method, trim_enabled)
            text = f"{os.path.basename(f)}\n{orig_dims[0]}x{orig_dims[1]} → {new_dims[0]}x{new_dims[1]}"
            
            fg_color = "black"
            if status == "done":
                text += "\n--- done!"
                fg_color = "green"
                
            # 将加载的原始PIL图像和相关信息放入队列
            # 注意：不在线程中创建 ImageTk 对象
            thumbnail_queue.put((idx, img, text, status, fg_color, row, col))
        except Exception as e:
            print(f"Error loading thumbnail for {f}: {e}")
    
    # 所有图片处理完毕
    thumbnail_loading = False
    
    # 如果有更多图片，发送一个特殊信号以显示提示信息
    if len(files) > MAX_THUMBNAILS:
        thumbnail_queue.put(('more_info', len(files) - MAX_THUMBNAILS, 
                           display_count // items_per_row + 1, items_per_row))

def update_thumbnail_display():
    """定期检查队列并更新UI的函数"""
    global thumbnail_images
    
    try:
        # 处理队列中的项目，每次最多处理5个以保持UI响应
        processed = 0
        while not thumbnail_queue.empty() and processed < 5:
            item = thumbnail_queue.get_nowait()
            processed += 1
            
            # 处理常规缩略图
            if isinstance(item[0], int):
                idx, img, text, status, fg_color, row, col = item
                
                # 创建PhotoImage并保存引用
                photo = ImageTk.PhotoImage(img)
                thumbnail_images[idx] = photo
                
                # 创建并配置标签
                lbl = tk.Label(thumbnail_frame,
                              image=photo,
                              text=text,
                              compound="top",
                              fg=fg_color,
                              bd=0)
                lbl.thumb_index = idx
                lbl.selected = False
                lbl.bind("<Button-1>", toggle_thumbnail_select)
                
                # 放置标签
                lbl.grid(row=row, column=col, padx=5, pady=5)
                thumbnail_frame.grid_columnconfigure(col, weight=1)
                
            # 处理"更多项目"提示
            elif item[0] == 'more_info':
                _, count, row, colspan = item
                more_label = tk.Label(thumbnail_frame, 
                                     text=f"+ {count} more items...",
                                     fg="gray")
                more_label.grid(row=row, column=0, columnspan=colspan, pady=10)
    
    except Exception as e:
        print(f"Error updating thumbnail display: {e}")
    
    # 如果仍在加载或队列非空，继续调度更新
    if thumbnail_loading or not thumbnail_queue.empty():
        thumbnail_status_label.config(text=f"Loading thumbnails... ({len(thumbnail_images)}/{min(len(task_files), 50)})")
        root.after(50, update_thumbnail_display)  # 50毫秒后再次检查
    else:
        # 加载完成，更新滚动区域
        thumbnail_frame.update_idletasks()
        thumbnail_canvas.configure(scrollregion=thumbnail_canvas.bbox("all"))
        thumbnail_status_label.config(text="All thumbnails loaded")
        thumbnail_status_label.after(2000, lambda: thumbnail_status_label.config(text=""))

def update_task_display():
    global thumbnail_images
    if view_mode.get() == "list":
        # 列表视图代码保持不变...
        list_frame.grid()
        thumbnail_container.grid_remove()
        
        # 清空当前列表
        for item in task_listbox.get_children():
            task_listbox.delete(item)
            
        # 填充列表视图数据...
        for idx, (f, status) in enumerate(task_files):
            try:
                orig_dims, new_dims = calculate_new_dimensions(f, int(multiple_entry.get()), method_var.get(), trim_var.get())
                
                item_id = task_listbox.insert("", "end", 
                                            values=(os.path.basename(f), 
                                                    f"{orig_dims[0]}x{orig_dims[1]}",
                                                    f"{new_dims[0]}x{new_dims[1]}",
                                                    "Done" if status == "done" else "Pending"))
                
                if status == "done":
                    task_listbox.item(item_id, tags=("done",))
            except Exception as e:
                print(f"Error processing list item {f}: {e}")
        
        task_listbox.tag_configure("done", foreground="green")
    else:
        # 缩略图视图 - 使用线程加载
        list_frame.grid_remove()
        thumbnail_container.grid()
        
        # 清除现有缩略图
        for widget in thumbnail_frame.winfo_children():
            widget.destroy()
        thumbnail_images = {}
        
        # 设置每行显示的项目数
        items_per_row = 5
        
        # 显示加载状态
        global thumbnail_status_label
        thumbnail_status_label = tk.Label(thumbnail_frame, text="Loading thumbnails...", fg="blue")
        thumbnail_status_label.grid(row=0, column=0, columnspan=items_per_row)
        
        # 启动缩略图加载线程
        threading.Thread(
            target=load_thumbnails_thread,
            args=(task_files, int(multiple_entry.get()), method_var.get(), trim_var.get(), items_per_row),
            daemon=True
        ).start()
        
        # 开始定时更新UI
        root.after(100, update_thumbnail_display)
def remove_selected_task():
    global task_files
    if view_mode.get() == "list":
        # 列表模式，使用 Listbox 的多选
        selected_items = task_listbox.selection()
        selected_indices = []
        if selected_items:
            # Get each selected item's index in the task_files list
            for item in selected_items:
                item_index = task_listbox.index(item)
                selected_indices.append(item_index)
            
            # Delete items in reverse order to avoid index shifting
            for index in sorted(selected_indices, reverse=True):
                del task_files[index]
            
            # Remove the selected items from the Treeview
            for item in selected_items:
                task_listbox.delete(item)
    else:
        # 缩略图模式，根据每个标签的 selected 属性
        selected_indices = []
        for widget in thumbnail_frame.winfo_children():
            if hasattr(widget, "selected") and widget.selected:
                selected_indices.append(widget.thumb_index)
        # 去除重复，倒序删除确保索引正确
        for index in sorted(set(selected_indices), reverse=True):
            del task_files[index]
    update_task_display()
def switch_view_mode():
    if view_mode.get() == "list":
        view_mode.set("thumbnail")
    else:
        view_mode.set("list")
    update_task_display()

def calculate_new_dimensions(img_path, multiple, method, trim_enabled):
    """根据用户设置计算图片处理后的预期尺寸"""
    try:
        with Image.open(img_path) as img:
            width, height = img.size
            
            # 如果启用了裁剪，先计算裁剪后的尺寸
            if trim_enabled and 'A' in img.getbands():
                try:
                    alpha = img.getchannel('A')
                    bbox = alpha.getbbox()
                    if bbox:
                        width = bbox[2] - bbox[0]
                        height = bbox[3] - bbox[1]
                except Exception:
                    pass
            
            # 根据不同方法计算新尺寸
            if method == "Stretch":
                def get_optimal_size(dimension):
                    lower = (dimension // multiple) * multiple
                    upper = lower + multiple
                    return lower if abs(dimension - lower) <= abs(dimension - upper) else upper
                new_width = get_optimal_size(width)
                new_height = get_optimal_size(height)
            else:  # Extend 或 Crop 方法
                new_width = (width + multiple - 1) // multiple * multiple
                new_height = (height + multiple - 1) // multiple * multiple
                
            return (width, height), (new_width, new_height)
    except Exception as e:
        print(f"Error calculating dimensions: {e}")
        return (0, 0), (0, 0)

# 2. 添加窗口置顶功能 (在主窗口创建后添加)
def toggle_always_on_top():
    global always_on_top, pin_button
    always_on_top = not always_on_top
    root.attributes("-topmost", always_on_top)
    
    # 更新按钮图标
    if always_on_top:
        pin_button.config(image=pin_on_icon)
        pin_button.config(background="#9bd300")  # 置顶时按钮背景变色
    else:
        pin_button.config(image=pin_off_icon)
        pin_button.config(background=root.cget('bg'))  # 恢复默认背景色

def update_target_sizes(*args):
    """当用户修改倍数、方法或预裁剪设置时，更新所有任务的目标尺寸"""
    if view_mode.get() == "list" and task_files:
        try:
            multiple = int(multiple_entry.get())
            method = method_var.get()
            trim = trim_var.get()
            
            # 更新 Treeview 中的目标尺寸列
            for idx, (f, status) in enumerate(task_files):
                item_id = task_listbox.get_children()[idx]
                orig_dims, new_dims = calculate_new_dimensions(f, multiple, method, trim)
                task_listbox.set(item_id, "new_size", f"{new_dims[0]}x{new_dims[1]}")
        except Exception as e:
            print(f"Error updating target sizes: {e}")

# 绑定参数变更事件



# 创建主窗口
root = TkinterDnD.Tk()
# 添加在 root 创建后，设置窗口属性之前

# 添加置顶功能和图标
always_on_top = False

# 加载 SVG 图标 (需要先在同目录下准备这两个 SVG 文件)
try:
    from PIL import Image, ImageTk
    # 尝试加载 SVG 图标，如果没有或出错则使用文字按钮
    pin_on_path = resource_path('ic_fluent_pin_48_regular.svg')
    pin_off_path = resource_path('ic_fluent_pin_off_48_regular.svg')
    
    # 如果是 SVG，需要先转换为 PNG
    import cairosvg  # 你可能需要安装这个库: pip install cairosvg
    
    if os.path.exists(pin_on_path) and os.path.exists(pin_off_path):
        # 转换 SVG 到 PNG，然后加载
        temp_on = os.path.join(os.path.dirname(pin_on_path), 'temp_pin_on.png')
        temp_off = os.path.join(os.path.dirname(pin_off_path), 'temp_pin_off.png')
        
        cairosvg.svg2png(url=pin_on_path, write_to=temp_on, output_width=24, output_height=24)
        cairosvg.svg2png(url=pin_off_path, write_to=temp_off, output_width=24, output_height=24)
        
        pin_on_icon = ImageTk.PhotoImage(Image.open(temp_on))
        pin_off_icon = ImageTk.PhotoImage(Image.open(temp_off))
        
        # 删除临时文件
        os.remove(temp_on)
        os.remove(temp_off)
    else:
        # 如果找不到图标文件，使用简单文本按钮
        raise FileNotFoundError("Icon files not found")
except Exception as e:
    print(f"Error loading pin icons: {e}")
    # 使用 Unicode 字符作为备用图标
    pin_on_icon = None
    pin_off_icon = None
root.title("Pixel magnification adjustment")
try:
    icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
except Exception as e:
    print(f"Error loading icon: {e}")

# 添加在标题栏设置后，其他窗口元素之前

# 添加置顶按钮
if pin_on_icon and pin_off_icon:
    pin_button = tk.Button(root, image=pin_off_icon, command=toggle_always_on_top, 
                          bd=0, highlightthickness=0, relief="flat")
else:
    # 如果图标加载失败，使用文字按钮
    pin_button = tk.Button(root, text="📌", command=toggle_always_on_top,
                          bd=0, highlightthickness=0, relief="flat")

pin_button.grid(row=21, column=2, padx=10, pady=5, sticky='se')

root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)

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
output_folder_entry.dnd_bind('<<Drop>>', lambda e: (handle_output_drop(output_folder_entry, e), root.update()))
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
style = ttk.Style(root)
style.theme_use('default')
style.configure("green.Horizontal.TProgressbar", troughcolor='#eff2c7', background='#9bd300')
progress_bar = ttk.Progressbar(root, orient='horizontal', length=250, mode='determinate', style="green.Horizontal.TProgressbar")
progress_bar.grid(row=4, column=1, padx=10, pady=5)

# 在处理方式选择框之后添加 trim 复选框
trim_var = BooleanVar()
trim_checkbox = Checkbutton(root, text="Pretrim", variable=trim_var)
trim_checkbox.grid(row=3, column=2, padx=10, pady=5, sticky='e')
trim_var.set(config.get('DefaulPretrimState'))

# 在界面控件部分，添加 GPU 处理开关
gpu_var = BooleanVar()
gpu_checkbox = Checkbutton(root, text="GPU Processing", variable=gpu_var)
gpu_checkbox.grid(row=4, column=2, padx=10, pady=5, sticky='e')
gpu_var.set(False)

# 添加Process Subfolders 复选框
subfolder_var = BooleanVar()
subfolder_checkbox = Checkbutton(root, text="Process Subfolders", variable=subfolder_var)
subfolder_checkbox.grid(row=2, column=2, padx=10, pady=5, sticky='e')
subfolder_var.set(config.get('ProcessSubfolders') == '1')

# 在文件开头的界面元素定义部分（在创建进度条之后）添加：
progress_label = Label(root, text="")
progress_label.grid(row=21, column=1, padx=10, pady=5, sticky='wes')

# 在创建run按钮之前添加快速处理区域
border_frame = tk.Frame(root, bg="#9bd300", padx=2, pady=2)
border_frame.grid(row=5, column=0, padx=10, pady=5, sticky='w')

quick_drop_frame = Label(border_frame, text="Quick Drop", relief="solid", width=10, height=2, bd=0)
quick_drop_frame.pack()
quick_drop_frame.drop_target_register(DND_FILES)
quick_drop_frame.dnd_bind('<<Drop>>', handle_quick_drop)

# task_frame 跨 3 列，并在水平方向扩展
task_frame = tk.Frame(root)
task_frame.grid(row=8, column=0, rowspan=6, columnspan=3, padx=10, pady=5, sticky="ew")

# 使 task_frame 内部第 0 列具有伸缩性
task_frame.grid_columnconfigure(0, weight=1)
task_frame.grid_rowconfigure(0, weight=1)

list_frame = tk.Frame(task_frame)
list_frame.grid(row=0, column=0, sticky="nsew")
list_frame.grid_columnconfigure(0, weight=1)
list_frame.grid_rowconfigure(0, weight=1)
# 替换原有的 task_listbox 定义
task_listbox = ttk.Treeview(list_frame, columns=("name", "orig_size", "new_size", "status"), 
                           selectmode="extended", show="headings", height=10)

# 设置列标题
task_listbox.heading("name", text="File Name")
task_listbox.heading("orig_size", text="Original Size")
task_listbox.heading("new_size", text="Target Size")
task_listbox.heading("status", text="Status")

# 添加垂直滚动条
scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=task_listbox.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
task_listbox.configure(yscrollcommand=scrollbar.set)
task_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# 修改缩略图容器配置
thumbnail_container = tk.Frame(task_frame)
thumbnail_container.grid(row=0, column=0, sticky="nsew")
thumbnail_container.grid_remove()  # 默认隐藏
thumbnail_container.grid_columnconfigure(0, weight=1)
thumbnail_container.grid_rowconfigure(0, weight=1)

# 创建缩略图视图的滚动区域
thumbnail_canvas = tk.Canvas(thumbnail_container, bg="white")
thumbnail_scrollbar = ttk.Scrollbar(thumbnail_container, orient="vertical", command=thumbnail_canvas.yview)
thumbnail_scrollbar_h = ttk.Scrollbar(thumbnail_container, orient="horizontal", command=thumbnail_canvas.xview)
thumbnail_frame = tk.Frame(thumbnail_canvas, bg="white")

# 配置横向和纵向滚动条
thumbnail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
thumbnail_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)
thumbnail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# 设置 canvas 可同时水平和垂直滚动
thumbnail_canvas.configure(yscrollcommand=thumbnail_scrollbar.set, 
                          xscrollcommand=thumbnail_scrollbar_h.set)

# 将 frame 放入 canvas 中并配置
thumbnail_canvas.create_window((0, 0), window=thumbnail_frame, anchor=tk.NW)

# 配置 thumbnail_frame 以支持正确的网格布局
def configure_thumbnail_layout(event=None):
    # 设置内部frame的最小宽度为canvas宽度，确保网格布局正确显示
    thumbnail_canvas.configure(scrollregion=thumbnail_canvas.bbox("all"))
    thumbnail_frame.config(width=max(thumbnail_canvas.winfo_width(), 
                                    len(task_files) * 150))  # 根据缩略图宽度调整

thumbnail_frame.bind("<Configure>", configure_thumbnail_layout)
thumbnail_canvas.bind("<Configure>", lambda e: thumbnail_frame.config(width=max(thumbnail_canvas.winfo_width(), 200)))



# 切换视图
view_mode = tk.StringVar(value="list")

#切换视图按钮
toggle_view_btn = Button(root, text="Toggle View", command=switch_view_mode)
toggle_view_btn.grid(row=7, column=2, padx=10, pady=5, sticky='ew')

# 添加移除选中按钮
remove_selected_btn = Button(root, text="Remove Selected", command=remove_selected_task)
remove_selected_btn.grid(row=7, column=0, padx=1, pady=1, sticky='ew')
clear_all_btn = Button(root, text="Clear All Tasks", command=clear_all_tasks)
clear_all_btn.grid(row=7, column=1, padx=1, pady=1, sticky='ew')

# 执行按钮
Button(root, text="run", command=execute, width=35).grid(row=5, column=1, padx=10, pady=5)
Button(root, text="config", command=open_config, width=8).grid(row=5, column=2, padx=10, pady=5,sticky='e')

root.protocol("WM_DELETE_WINDOW", save_config)

default_input_folder = input_folder_entry.get()
if os.path.exists(default_input_folder):
    new_files = add_tasks_from_path(default_input_folder)
    if new_files:
        add_to_task_list(new_files)
else:
    print(f"Input folder not found: {default_input_folder}")

multiple_entry.bind("<KeyRelease>", update_target_sizes)
method_var.trace("w", update_target_sizes)
trim_var.trace("w", update_target_sizes)

root.mainloop()