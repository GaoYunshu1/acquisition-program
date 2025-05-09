import math
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


class Scanner:
    def __init__(self, step, scan_num, mode='round', nth=6):
        self.step = step
        self.scan_num = scan_num
        self.mode = mode
        self.nth = nth  # 新增参数nth，控制基础角度数目
        self.x = []
        self.y = []
        self.abs_x = []
        self.abs_y = []
        self.final_pos = (0, 0)
        self.generate_scan_points()

    def generate_scan_points(self):
        if self.mode == 'round':
            # 计算扫描区域的半长
            scan_half_length = self.step * self.scan_num
            # 生成绝对坐标列表，包含原点
            pos_absolute = [(0.0, 0.0)]
            for ir in range(1, self.scan_num + 1):
                rr = ir * self.step
                nth_angles = self.nth * ir
                dth = 2 * math.pi / nth_angles
                for ith in range(nth_angles):
                    theta = ith * dth
                    x = rr * math.sin(theta)  # 对应Matlab的x坐标
                    y = rr * math.cos(theta)  # 对应Matlab的y坐标
                    # 检查是否超出扫描区域
                    if abs(x) > scan_half_length or abs(y) > scan_half_length:
                        break
                    pos_absolute.append((x, y))
            # 转换为相对位移
            self.x = [0]
            self.y = [0]
            for i in range(1, len(pos_absolute)):
                prev_x, prev_y = pos_absolute[i - 1]
                curr_x, curr_y = pos_absolute[i]
                self.x.append(curr_x - prev_x)
                self.y.append(curr_y - prev_y)
            # 计算绝对坐标
            current_x, current_y = 0.0, 0.0
            self.abs_x.append(current_x)
            self.abs_y.append(current_y)
            for dx, dy in zip(self.x, self.y):
                current_x += dx
                current_y += dy
                self.abs_x.append(current_x)
                self.abs_y.append(current_y)
            self.final_pos = (current_x, current_y)

        elif self.mode == 'rectangle':
            # 修改后的矩形扫描代码（示例，需根据需求调整）
            # 生成蛇形路径的相对位移
            self.x = []
            self.y = []
            for i in range(self.scan_num):
                for j in range(self.scan_num):
                    if j == 0 and i != 0:
                        self.x.append(self.step)
                    else:
                        self.x.append(0)
                    if self.x[-1] != 0:
                        self.y.append(0)
                    elif i % 2 == 0:
                        self.y.append(self.step)
                    else:
                        self.y.append(-self.step)
            current_x, current_y = 0, 0
            for dx, dy in zip(self.x, self.y):
                current_x += dx
                current_y += dy
                self.abs_x.append(current_x)
                self.abs_y.append(current_y)
            self.final_pos = (current_x, current_y)


def visualize_scan_path(scanner:Scanner, save_path=None, dpi=100):
    """
    可视化扫描路径

    参数：
    scanner - 包含扫描数据的Scanner对象
    save_path - 图片保存路径（可选）
    dpi - 输出分辨率（默认100）
    """
    # 检查是否有扫描数据
    if not hasattr(scanner, 'abs_x') or not hasattr(scanner, 'abs_y'):
        raise ValueError("Scanner对象缺少坐标数据")

    x = np.array(scanner.abs_x)
    y = np.array(scanner.abs_y)

    if len(x) == 0 or len(y) == 0:
        raise ValueError("坐标数据为空")

    plt.figure(figsize=(10, 10))
    ax = plt.gca()

    # 创建颜色映射（按扫描顺序）
    colors = np.arange(len(x))
    norm = Normalize(vmin=0, vmax=len(x) - 1)
    cmap = plt.get_cmap('viridis')

    # 绘制连接线（带箭头指示方向）
    for i in range(1, len(x)):
        dx = x[i] - x[i - 1]
        dy = y[i] - y[i - 1]
        ax.arrow(x[i - 1], y[i - 1], dx, dy,
                 shape='full', lw=1,
                 color=cmap(norm(i - 1)),
                 length_includes_head=True,
                 head_width=0.3 * scanner.step,
                 head_length=0.5 * scanner.step)

    # 绘制扫描点
    scatter = ax.scatter(x, y, c=colors, cmap=cmap,
                         s=50, zorder=3, edgecolor='w')

    # 标注起点和终点
    ax.scatter(x[0], y[0], s=200, marker='*',
               c='limegreen', edgecolor='k', label='Start')
    ax.scatter(x[-1], y[-1], s=200, marker='X',
               c='orangered', edgecolor='k', label='End')

    # 绘制扫描区域边界
    max_extent = scanner.step * scanner.scan_num
    rect = plt.Rectangle((-max_extent, -max_extent),
                         2 * max_extent, 2 * max_extent,
                         linewidth=2, linestyle='--',
                         edgecolor='gray', facecolor='none')
    ax.add_patch(rect)

    # 设置坐标轴
    buffer = scanner.step * 0.5
    ax.set_xlim(-max_extent - buffer, max_extent + buffer)
    ax.set_ylim(-max_extent - buffer, max_extent + buffer)
    ax.set_aspect('equal')
    ax.grid(True, linestyle=':', alpha=0.7)
    ax.set_xlabel('X Position')
    ax.set_ylabel('Y Position')

    # 添加颜色条
    # cbar = plt.colorbar(scatter, ax=ax)
    # cbar.set_label('Scan Order')

    # 添加图例
    ax.legend(loc='upper right')

    # 设置标题
    title = f"{scanner.mode.capitalize()} Scan Path\n"
    title += f"Step: {scanner.step}, Steps: {scanner.scan_num}"
    if scanner.mode == 'round' and hasattr(scanner, 'nth'):
        title += f", Nth: {scanner.nth}"
    plt.title(title)

    # 保存或显示图像
    if save_path:
        plt.savefig(save_path, dpi=dpi, bbox_inches='tight')
        print(f"图像已保存至：{save_path}")
    else:
        plt.show()

    plt.close()


if __name__ == '__main__':
    scanner = Scanner(0.1, 5, mode='round')
    print(len(scanner.x))
    # print(scanner.y)
    print(f'{scanner.abs_x}')
    print(f'{scanner.abs_y}')
    visualize_scan_path(
        scanner,
        # save_path='scan_path.png',
        dpi=150
    )
