import os
from tkinter import Tk, Label, Entry, Button, filedialog
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image
from tkinter import ttk

def adjust_image_size(input_folder, output_folder, multiple, progress_bar):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    files = [f for f in os.listdir(input_folder) if f.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp'))]
    total_files = len(files)
    progress_bar['maximum'] = total_files

    for i, filename in enumerate(files):
        file_path = os.path.join(input_folder, filename)
        with Image.open(file_path) as img:
            width, height = img.size
            new_width = (width + multiple - 1) // multiple * multiple
            new_height = (height + multiple - 1) // multiple * multiple
            if (width, height) != (new_width, new_height):
                img = img.resize((new_width, new_height), Image.LANCZOS)
            output_path = os.path.join(output_folder, filename)
            img.save(output_path)
        
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
    input_folder = input_folder_entry.get()
    output_folder = output_folder_entry.get()
    multiple = int(multiple_entry.get())
    adjust_image_size(input_folder, output_folder, multiple, progress_bar)

# 创建主窗口
root = TkinterDnD.Tk()
root.title("Pixel magnification adjustment")

# 输入文件夹
Label(root, text="input:").grid(row=0, column=0, padx=10, pady=5)
input_folder_entry = Entry(root, width=40)
input_folder_entry.grid(row=0, column=1, padx=10, pady=5)
input_folder_entry.drop_target_register(DND_FILES)
input_folder_entry.dnd_bind('<<Drop>>', lambda e: input_folder_entry.insert(0, e.data))
Button(root, text="choose", command=select_input_folder).grid(row=0, column=2, padx=10, pady=5)

# 输出文件夹
Label(root, text="output:").grid(row=1, column=0, padx=10, pady=5)
output_folder_entry = Entry(root, width=40)
output_folder_entry.grid(row=1, column=1, padx=10, pady=5)
output_folder_entry.drop_target_register(DND_FILES)
output_folder_entry.dnd_bind('<<Drop>>', lambda e: output_folder_entry.insert(0, e.data))
Button(root, text="choose", command=select_output_folder).grid(row=1, column=2, padx=10, pady=5)

# 倍率
Label(root, text="multiplier:").grid(row=2, column=0, padx=10, pady=5)
multiple_entry = Entry(root, width=40)
multiple_entry.grid(row=2, column=1, padx=10, pady=5)

# 进度条
Label(root, text="Progress:").grid(row=3, column=0, padx=10, pady=5) 
progress_bar = ttk.Progressbar(root, orient='horizontal', length=285, mode='determinate')
progress_bar.grid(row=3, column=1, padx=10, pady=5)

# 执行按钮
Button(root, text="run", command=execute, width=40).grid(row=4, column=1, padx=10, pady=5)

root.mainloop()