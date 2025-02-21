import tkinter as tk

root = tk.Tk()
canvas = tk.Canvas(root, width=300, height=200)
canvas.pack()

def round_rectangle(canvas, x1, y1, x2, y2, radius=25, **kwargs):
    points = [
        x1+radius, y1,
        x2-radius, y1,
        x2, y1,
        x2, y1+radius,
        x2, y2-radius,
        x2, y2,
        x2-radius, y2,
        x1+radius, y2,
        x1, y2,
        x1, y2-radius,
        x1, y1+radius,
        x1, y1
    ]
    return canvas.create_polygon(points, **kwargs, smooth=True)


def create_capsule(canvas, x, y, width, height, fill="", outline=""):
    """
    创建一个左右两边为正圆形的圆角矩形（胶囊形）
    参数：
      canvas - 目标 Canvas
      x, y - 左上角坐标
      width, height - 总宽高
      fill, outline - 填充色及边框色
    要求：height 为圆形直径，左右两边即为完整圆。
    """
    r = height / 2
    x1, y1 = x, y
    x2, y2 = x + width, y + height

    # 中间矩形部分
    rect = canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=outline)

    # 左侧圆形
    left_oval = canvas.create_oval(x1, y1, x1 + 2*r, y2, fill=fill, outline=outline)
    # 右侧圆形
    right_oval = canvas.create_oval(x2 - 2*r, y1, x2, y2, fill=fill, outline=outline)
    
    return (rect, left_oval, right_oval)

# 创建一个宽50像素, 高20像素（左右半径10像素）的胶囊形
#create_capsule(canvas, 60, 60, 50, 20, fill="#9bd300", outline="")
# 绘制一个圆角矩形
round_rectangle(canvas, 50, 50, 100, 50, radius=20, fill="#9bd300", outline="")

root.mainloop()

