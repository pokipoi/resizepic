import pyopencl as cl
import numpy as np
from PIL import Image

# 初始化 OpenCL 环境，选择第一个可用设备
platform = cl.get_platforms()[0]
device = platform.get_devices()[0]
ctx = cl.Context([device])
queue = cl.CommandQueue(ctx)

# 内核代码：extend 模式：将源图像复制到目标图像中指定偏移位置，其它区域置 0
extend_kernel_source = """
__kernel void extend_image(__global uchar *source, const int src_width, const int src_height,
                             __global uchar *dest, const int dest_width, const int dest_height,
                             const int channels, const int offset_x, const int offset_y) {
    int x = get_global_id(0);
    int y = get_global_id(1);
    int dest_index = (y * dest_width + x) * channels;
    if (x >= offset_x && x < offset_x + src_width && y >= offset_y && y < offset_y + src_height) {
        int src_x = x - offset_x;
        int src_y = y - offset_y;
        int src_index = (src_y * src_width + src_x) * channels;
        for (int c = 0; c < channels; c++){
            dest[dest_index + c] = source[src_index + c];
        }
    } else {
        for (int c = 0; c < channels; c++){
            dest[dest_index + c] = 0;
        }
    }
}
"""

# 内核代码：stretch 模式（使用最近邻插值）
stretch_kernel_source = """
__kernel void stretch_image(__global uchar *source, const int src_width, const int src_height,
                              __global uchar *dest, const int dest_width, const int dest_height,
                              const int channels, const float scale_x, const float scale_y) {
    int x = get_global_id(0);
    int y = get_global_id(1);
    int dest_index = (y * dest_width + x) * channels;
    int src_x = min((int)(x / scale_x), src_width - 1);
    int src_y = min((int)(y / scale_y), src_height - 1);
    int src_index = (src_y * src_width + src_x) * channels;
    for (int c = 0; c < channels; c++){
        dest[dest_index + c] = source[src_index + c];
    }
}
"""

# 编译内核
extend_program = cl.Program(ctx, extend_kernel_source).build()
stretch_program = cl.Program(ctx, stretch_kernel_source).build()

def process_image_opencl(img, multiple, method, trim_enabled):
    """
    OpenCL版本的图像处理函数
      - trim 部分仍在CPU上执行
      - Extend 和 Stretch 模式使用 OpenCL 内核加速
      - Crop 模式使用 host 端 numpy 切片
    """
    # trim处理（CPU执行）
    if trim_enabled:
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        try:
            alpha = np.array(img.getchannel('A'))
            coords = np.argwhere(alpha)
            if coords.size:
                y0, x0 = coords.min(axis=0)
                y1, x1 = coords.max(axis=0) + 1
                img = img.crop((x0, y0, x1, y1))
        except Exception as e:
            print(f"Warning: Could not trim image: {e}")
    
    width, height = img.size
    # 计算目标尺寸
    if method == "Stretch":
        def get_optimal_size(dimension):
            lower = (dimension // multiple) * multiple
            upper = lower + multiple
            return lower if abs(dimension - lower) <= abs(dimension - upper) else upper
        new_width = get_optimal_size(width)
        new_height = get_optimal_size(height)
    else:
        new_width = ((width + multiple - 1) // multiple) * multiple
        new_height = ((height + multiple - 1) // multiple) * multiple

    # 转换图像为 numpy 数组（假设为uint8）
    img_arr = np.array(img)
    if img_arr.ndim == 2:
        # 单通道扩展到二维有1个通道
        img_arr = img_arr[..., np.newaxis]
    src_height, src_width, channels = img_arr.shape

    # 建立目标数组
    if method in ["Extend", "Stretch"]:
        dest_arr = np.empty((new_height, new_width, channels), dtype=np.uint8)
    elif method == "Crop":
        # 对Crop模式，直接裁剪原图
        left = (width - new_width) // 2
        top = (height - new_height) // 2
        cropped = img_arr[top:top+new_height, left:left+new_width, :]
        return Image.fromarray(cropped)
    else:
        dest_arr = img_arr.copy()

    mf = cl.mem_flags
    # 将源数据复制到 device 内存
    src_buf = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=img_arr)
    dest_buf = cl.Buffer(ctx, mf.WRITE_ONLY, dest_arr.nbytes)

    if method == "Extend":
        # 计算粘贴偏移量（居中）
        offset_x = (new_width - src_width) // 2
        offset_y = (new_height - src_height) // 2
        # 全局工作项大小：目标图像尺寸
        global_size = (new_width, new_height)
        extend_program.extend_image(queue, global_size, None,
                                      src_buf, np.int32(src_width), np.int32(src_height),
                                      dest_buf, np.int32(new_width), np.int32(new_height),
                                      np.int32(channels), np.int32(offset_x), np.int32(offset_y))
    elif method == "Stretch":
        scale_x = new_width / src_width
        scale_y = new_height / src_height
        global_size = (new_width, new_height)
        stretch_program.stretch_image(queue, global_size, None,
                                      src_buf, np.int32(src_width), np.int32(src_height),
                                      dest_buf, np.int32(new_width), np.int32(new_height),
                                      np.int32(channels), np.float32(scale_x), np.float32(scale_y))
    # 读回结果
    cl.enqueue_copy(queue, dest_arr, dest_buf)
    queue.finish()
    return Image.fromarray(dest_arr)