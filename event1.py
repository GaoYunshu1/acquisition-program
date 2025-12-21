import sys
import os
import time
import io
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import traceback

# PyQt6 导入
from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QVBoxLayout, QFileDialog, QMessageBox
from PyQt6.QtGui import QImage, QPixmap, QPen, QColor
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread

# 导入 UI 定义
from gui_generate import ModernUI

# =========================================================
#  硬件加载线程
# =========================================================
class DeviceLoader(QThread):
    finished_signal = pyqtSignal(bool, object)

    def __init__(self, device_type, device_name):
        super().__init__()
        self.device_type = device_type 
        self.device_name = device_name

    def run(self):
        try:
            device_instance = None
            if self.device_type == 'camera':
                if self.device_name == "IDS":
                    from camera import IDS
                    device_instance = IDS()
                    device_instance.start_acquisition()
                    device_instance.set_pixel_rate(7e7)
                elif self.device_name == "Ham":
                    from camera import Ham
                    device_instance = Ham()
                    device_instance.start_acquisition()
                elif self.device_name == "Lucid":
                    from lucid import LucidCamera
                    device_instance = LucidCamera(max_tries=1, wait_time=1)
                    device_instance.start_acquisition()
                elif self.device_name == "PM":
                    from photometrics import PyVCAM
                    device_instance = PyVCAM()
                    device_instance.start_acquisition()
                elif self.device_name == "IDS_Peak":
                    from peak import IDSPeakCamera
                    device_instance = IDSPeakCamera()
                    device_instance.start_acquisition()
                elif self.device_name == "PI-mte3":
                    from pi_camera import PICamera                        
                    device_instance = PICamera()
                    device_instance.start_acquisition()

            elif self.device_type == 'stage':
                if self.device_name == "SmartAct":
                    from motion_controller import smartact
                    device_instance = smartact()
                elif self.device_name == "Nators":
                    from motion_controller import nators
                    device_instance = nators(ip_address="192.168.0.254")
                    device_instance.open_system()
                elif self.device_name == "NewPort":
                    from motion_controller import xps
                    device_instance = xps(IP='192.168.0.254')
                    device_instance.init_groups(['Group3', 'Group4'])

            if device_instance:
                self.finished_signal.emit(True, device_instance)
            else:
                self.finished_signal.emit(False, f"未找到驱动: {self.device_name}")

        except Exception as e:
            self.finished_signal.emit(False, str(e))

# =========================================================
#  自定义图像显示控件
# =========================================================
class InteractiveImageView(QGraphicsView):
    mouse_hover_signal = pyqtSignal(int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None
        self.np_img = None 
        self.setMouseTracking(True) 
        self.setStyleSheet("background: #000; border: 0px;")
        
        self.curr_img_x = -1
        self.curr_img_y = -1

        self.v_line = None
        self.h_line = None

    def update_image(self, image_data, show_mask=False):
        self.np_img = image_data
        
        if image_data.dtype == np.uint16:
            # 简单压缩用于显示
            display_data = (image_data / 16).astype(np.uint8) 
        else:
            display_data = image_data.astype(np.uint8)

        h, w = display_data.shape
        bytes_per_line = w
        qimg = QImage(display_data.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
        pix = QPixmap.fromImage(qimg)

        if self.pixmap_item is None:
            self.pixmap_item = self.scene.addPixmap(pix)
            self.pixmap_item.setZValue(0)
        else:
            self.pixmap_item.setPixmap(pix)
        
        # 处理 Mask (十字线)
        if show_mask:
            cx, cy = w / 2, h / 2
            pen = QPen(QColor("lime"), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            
            if self.v_line is None:
                self.v_line = self.scene.addLine(cx, 0, cx, h, pen)
                self.h_line = self.scene.addLine(0, cy, w, cy, pen)
                self.v_line.setZValue(1)
                self.h_line.setZValue(1)
            else:
                self.v_line.setLine(cx, 0, cx, h)
                self.h_line.setLine(0, cy, w, cy)
                self.v_line.setVisible(True)
                self.h_line.setVisible(True)
        else:
            if self.v_line:
                self.v_line.setVisible(False)
                self.h_line.setVisible(False)

        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def mouseMoveEvent(self, event):
        if self.np_img is not None and self.pixmap_item is not None:
            scene_pos = self.mapToScene(event.pos())
            item_pos = self.pixmap_item.mapFromScene(scene_pos)
            x, y = int(item_pos.x()), int(item_pos.y())

            h, w = self.np_img.shape
            if 0 <= x < w and 0 <= y < h:
                val = self.np_img[y, x]
                self.mouse_hover_signal.emit(x, y, val)
            else:
                self.mouse_hover_signal.emit(-1, -1, 0)
        super().mouseMoveEvent(event)

# =========================================================
#  主逻辑窗口
# =========================================================
class LogicWindow(ModernUI):
    def __init__(self):
        super().__init__()
        sys.excepthook = self.handle_exception
        
        # --- 1. 替换图像控件 ---
        old_layout = self.image_area.layout()
        if old_layout:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
        else:
            old_layout = QVBoxLayout(self.image_area)
            
        self.image_view = InteractiveImageView()
        old_layout.addWidget(self.image_view)

        # --- 2. 内部变量 ---
        self.camera = None
        self.motion = None
        
        # 实时流定时器
        self.timer.timeout.connect(self.update_frame)
        self.is_live = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.image_view.mouse_hover_signal.connect(self.on_mouse_moved)
        self.save_dir = "please change this to your own path"

        # --- 3. 信号绑定 ---
        self.btn_open_cam.clicked.connect(self.start_init_camera)
        self.btn_connect_stage.clicked.connect(self.start_init_motion)
        
        self.btn_live.clicked.connect(self.toggle_live)
        self.btn_cap.clicked.connect(self.start_scan)
        self.btn_save.clicked.connect(self.on_manual_save)
        self.btn_browse.clicked.connect(self.select_folder)
        self.btn_show_path.clicked.connect(self.preview_scan_path)

        # 位移台控制
        self.stage_widget.btn_up.clicked.connect(lambda: self.move_stage_manual('Y', 1))
        self.stage_widget.btn_down.clicked.connect(lambda: self.move_stage_manual('Y', -1))
        self.stage_widget.btn_left.clicked.connect(lambda: self.move_stage_manual('X', -1))
        self.stage_widget.btn_right.clicked.connect(lambda: self.move_stage_manual('X', 1))
        self.stage_widget.btn_go.clicked.connect(self.move_stage_absolute)
        self.stage_widget.btn_zero.clicked.connect(self.zero_stage)

        # 辅助功能
        self.btn_center.clicked.connect(self.calculate_center)
        self.exposure_spin.valueChanged.connect(self.set_exposure_time)

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """
        全局异常捕获函数：
        当发生未捕获的异常时，自动触发此函数
        """
        # 如果是键盘中断 (Ctrl+C)，则交给系统默认处理，方便开发时强制结束
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # 1. 获取完整的错误堆栈字符串
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # 2. 依然打印到控制台 (方便开发者在 IDE 调试)
        print(error_msg, file=sys.stderr)
        
        # 3. 显示到界面日志 (使用红色高亮)
        # 使用 HTML 格式让报错更显眼
        header = f"⛔ 【系统崩溃/错误】 {exc_type.__name__}: {exc_value}"
        self.log_html(f"<font color='#FF4444'><b>{header}</b><br><pre>{error_msg}</pre></font>")

    def log_html(self, html_msg):
        """辅助函数：支持 HTML 格式的日志插入"""
        self.txt_log.append(html_msg)
        # 自动滚动到底部
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def on_mouse_moved(self, x, y, val):
        if x >= 0 and y >= 0:
            self.last_mouse_x = x
            self.last_mouse_y = y
            self.update_pixel_display(val)

    def update_pixel_display(self, val):
        if val is None: return 
        
        self.line_mouse_val.setText(f"{val}")
        
        if val >= self.saturation_value:
            self.line_mouse_val.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")
        else:
            self.line_mouse_val.setStyleSheet("color: blue; font-weight: bold; background: #f0f0f0;")

    def update_frame(self):
        if self.camera:
            try:
                # 1. 获取并裁剪图像
                img = self.camera.read_newest_image()
                if img is None: return
                cropped_img = self.crop_image(img)
                
                # 2. 更新 View 显示
                self.image_view.update_image(cropped_img, show_mask)

                # ==========================================
                # 【新增逻辑】: 图像更新时，刷新鼠标位置的数值
                # ==========================================
                h, w = cropped_img.shape
                
                # 检查缓存坐标是否还在当前图像范围内 (防止ROI改变导致越界)
                if 0 <= self.last_mouse_x < w and 0 <= self.last_mouse_y < h:
                    # 从【新图像】中取出【旧位置】的值
                    current_val = cropped_img[self.last_mouse_y, self.last_mouse_x]
                    self.update_pixel_display(current_val)
                else:
                    # 如果ROI变小导致坐标失效，重置回中心或0
                    self.last_mouse_x = w // 2
                    self.last_mouse_y = h // 2
            
            except Exception as e:
                # self.log(f"Frame Update Error: {e}")
                pass

    # --- 异步加载设备 ---
    def start_init_camera(self):
        cam_name = self.combo_camera.currentText()
        self.log(f"正在初始化相机: {cam_name}...")
        self.btn_open_cam.setEnabled(False)
        self.loader_thread_cam = DeviceLoader('camera', cam_name)
        self.loader_thread_cam.finished_signal.connect(self.on_camera_loaded)
        self.loader_thread_cam.start()

    def on_camera_loaded(self, success, result):
        self.btn_open_cam.setEnabled(True)
        if success:
            self.camera = result
            self.btn_open_cam.setText("已就绪")
            self.btn_open_cam.setStyleSheet("background-color: #4CAF50; color: white;")

            bit_depth = self.get_current_bit_depth()
            # 3. 计算饱和值 (2^n - 1)
            # 此时 bit_depth 一定有值 (要么是读取到的，要么是默认的16)
            self.saturation_value = (1 << bit_depth) - 1
            
            # 4. 更新界面
            self.line_cam_max.setText(f"{self.saturation_value} ({bit_depth}-bit)")
            self.log(f"相机就绪，位深: {bit_depth}, 饱和阈值: {self.saturation_value}")
            
        else:
            self.log(f"相机错误: {result}")

    import re

    def get_current_bit_depth(self):
        """
        获取当前相机的位深（通过解析 color_mode 字符串）
        返回: int (例如 8, 10, 12, 16)
        """
        # 1. 获取模式 (例如 'mono12', 'raw8', 'rgb8p')
        mode = self.get_color_mode() 

        # 2. 如果返回的是字符串，直接正则提取数字
        if isinstance(mode, str):
            match = re.search(r'(\d+)', mode)
            if match:
                return int(match.group(1))
        
        # 3. (备用逻辑) 如果返回的是 int 枚举值，尝试反查你的字典
        elif isinstance(mode, int):
            # 假设 self._color_modes 是你之前定义的字典
            for name, val in self._color_modes.items():
                if val == mode:
                    # 找到对应名字后，递归调用自己处理字符串
                    match = re.search(r'(\d+)', name)
                    if match:
                        return int(match.group(1))
        
        # 4. 默认回退值 (如果解析失败)
        return 16

    def start_init_motion(self):
        stage_name = self.combo_stage.currentText()
        self.log(f"正在连接位移台: {stage_name}...")
        self.btn_connect_stage.setEnabled(False)
        self.loader_thread_stage = DeviceLoader('stage', stage_name)
        self.loader_thread_stage.finished_signal.connect(self.on_motion_loaded)
        self.loader_thread_stage.start()

    def on_motion_loaded(self, success, result):
        self.btn_connect_stage.setEnabled(True)
        if success:
            self.motion = result
            self.btn_connect_stage.setText("已连接")
            self.log("位移台连接成功")
            
            self.sync_hardware_position() 
        else:
            self.log(f"位移台错误: {result}")

    def sync_hardware_position(self):
        """标准逻辑：读取硬件当前的绝对位置更新到软件"""
        if not self.motion: return
        # 默认回退值
        hw_x, hw_y = 0.0, 0.0
        success = False

        try:     
            if hasattr(self.motion, 'get_position'):
                try:
                    hw_x = float(self.motion.get_position(0))
                    hw_y = float(self.motion.get_position(1))
                    success = True
                except Exception:
                    pass
            
            if not success:
                # 1. 针对 XPS (Newport)
                if hasattr(self.motion, 'xps') and hasattr(self.motion, 'groups'):
                    # 确保 Group 已经初始化
                    if len(self.motion.groups) >= 2:
                        g0 = self.motion.groups[0] # 对应 Axis 0
                        g1 = self.motion.groups[1] # 对应 Axis 1
                        hw_x = self.motion.xps.get_stage_position(f'{g0}.Pos')
                        hw_y = self.motion.xps.get_stage_position(f'{g1}.Pos')
                        success = True
                
                # 2. 针对 SmartAct (pylablib)
                elif hasattr(self.motion, 'motion') and hasattr(self.motion.motion, 'get_position'):
                    # SmartAct MCS2 原生返回单位通常是 米(m)，需转为 mm
                    hw_x = self.motion.motion.get_position(0) * 1000.0
                    hw_y = self.motion.motion.get_position(1) * 1000.0
                    success = True

            if success:
                self.stage_widget.lbl_x.setText(f"X: {hw_x:.3f} mm")
                self.stage_widget.lbl_y.setText(f"Y: {hw_y:.3f} mm")
                self.log(f"已同步硬件位置: X={hw_x:.4f}, Y={hw_y:.4f}")
            else:
                # 如果完全无法读取（比如 Nators 且未修复驱动），则不强制归零，
                # 而是保留当前软件坐标或提示警告
                self.log("警告: 当前位移台驱动不支持读取绝对位置，保持软件坐标不变。")

        except Exception as e:
            self.log(f"同步位置异常: {e}")
            # 只有在真的出错时才建议重置
            # self.zero_stage()


    # --- 图像处理核心逻辑 ---
    def crop_image(self, full_image):
        if full_image is None: return None
        h_full, w_full = full_image.shape
        
        try:
            target_w = int(self.roi_w.text()) # 假设这是 QLineEdit，如果是 SpinBox 用 .value()
            target_h = int(self.roi_h.text())
        except:
            target_w = 1024
            target_h = 1024

        if target_w >= w_full and target_h >= h_full:
            self.log("ROI 大于等于图像尺寸，无需裁剪")
            return full_image

        try:
            off_x = int(self.off_x.text())
            off_y = int(self.off_y.text())
        except:
            off_x = 0
            off_y = 0
        
        center_x = w_full // 2 + off_x
        center_y = h_full // 2 + off_y
        
        x1 = int(center_x - target_w // 2)
        y1 = int(center_y - target_h // 2)
        x2 = x1 + target_w
        y2 = y1 + target_h
        
        if x1 < 0: 
            x1 = 0
            x2 = target_w
        if y1 < 0:
            y1 = 0
            y2 = target_h
        if x2 > w_full:
            x2 = w_full
            x1 = w_full - target_w
        if y2 > h_full:
            y2 = h_full
            y1 = h_full - target_h
            
        # 最后的安全检查
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w_full, x2); y2 = min(h_full, y2)
        
        return full_image[y1:y2, x1:x2]

    def update_frame(self):
        if self.camera:
            try:
                img = self.camera.read_newest_image()
                if img is None: return
                
                cropped_img = self.crop_image(img)
                
                max_val = np.max(cropped_img)
                self.line_global_max.setText(f"{max_val}")
                
                # 饱和报警
                if max_val >= self.saturation_value:
                    self.line_global_max.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")
                else:
                    self.line_global_max.setStyleSheet("color: green; font-weight: bold; background: #f0f0f0;")
                
                show_mask = self.chk_mask.isChecked()
                
                if self.chk_log.isChecked():
                    img_disp = np.log1p(cropped_img.astype(np.float32))
                    img_disp = (img_disp / img_disp.max() * 65535).astype(np.uint16)
                    self.image_view.update_image(img_disp, show_mask)
                else:
                    self.image_view.update_image(cropped_img, show_mask)
            except Exception as e:
                pass

    def toggle_live(self):
        if not self.camera:
            self.log("请先打开相机！")
            return
        if self.is_live:
            self.timer.stop()
            self.btn_live.setText("👁 启动")
            self.btn_live.setStyleSheet("background:#27ae60;color:white;font-weight:bold;")
            self.is_live = False
        else:
            self.timer.start(50) 
            self.btn_live.setText("⬛ 停止")
            self.btn_live.setStyleSheet("background:#7f8c8d;color:white;font-weight:bold;")
            self.is_live = True

    def calculate_center(self):
        if not self.camera:
            self.log("相机未连接")
            return
        img = self.camera.read_newest_image()
        if img is None: 
            self.log("无法获取图像用于计算")
            return
        h_full, w_full = img.shape
        threshold = np.mean(img) + np.std(img) * 2
        mask = img > threshold
        if np.sum(mask) == 0:
            self.log("图像过暗，无法寻找中心")
            return
        y_indices, x_indices = np.indices(img.shape)
        total_mass = np.sum(img[mask])
        center_x = np.sum(x_indices[mask] * img[mask]) / total_mass
        center_y = np.sum(y_indices[mask] * img[mask]) / total_mass
        self.log(f"检测到质心: ({center_x:.1f}, {center_y:.1f})")
        
        sensor_cx = w_full / 2
        sensor_cy = h_full / 2
        offset_x = int(center_x - sensor_cx)
        offset_y = int(center_y - sensor_cy)
        
        self.off_x.setValue(offset_x)
        self.off_y.setValue(offset_y)
        self.log(f"已更新偏移量: X={offset_x}, Y={offset_y}")

    # --- 位移台逻辑 ---
    def update_stage_display(self):
        self.stage_widget.lbl_x.setText(f"X: {self.stage_widget.target_x.text()} mm")
        self.stage_widget.lbl_y.setText(f"Y: {self.stage_widget.target_y.text()} mm")

    def move_stage_manual(self, axis_name, direction):
        if not self.motion:
            self.log("位移台未连接")
            return
        step = self.stage_widget.step_spin.value()
        is_swap = self.stage_widget.check_swap.isChecked()
        inv_x = self.stage_widget.check_inv_x.isChecked()
        inv_y = self.stage_widget.check_inv_y.isChecked()
        
        target_axis = 0 
        if axis_name == 'X':
            target_axis = 1 if is_swap else 0
            if inv_x: direction *= -1
        else: 
            target_axis = 0 if is_swap else 1
            if inv_y: direction *= -1
            
        dist = step * direction
        try:
            self.motion.move_by(dist, axis=target_axis)
            if axis_name == 'X':
                self.stage_widget.target_x.setText(f"{self.stage_widget.target_x.text()}{step * direction:.3f}")
            else:
                self.stage_widget.target_y.setText(f"{self.stage_widget.target_y.text()}{step * direction:.3f}")
            self.update_stage_display()
        except Exception as e:
            self.log(f"移动失败: {e}")

    def move_stage_absolute(self):
        if not self.motion: return
        try:
            target_x = float(self.stage_widget.target_x.text())
            target_y = float(self.stage_widget.target_y.text())
        except ValueError:
            self.log("坐标输入格式错误")
            return
        
        dx = target_x - float(self.stage_widget.target_x.text())
        dy = target_y - float(self.stage_widget.target_y.text())
        
        if abs(dx) > 1e-6: self._move_logical_delta(dx, 0)
        if abs(dy) > 1e-6: self._move_logical_delta(dy, 1)
        self.log(f"移动至: ({target_x}, {target_y})")

    def _move_logical_delta(self, delta, logical_axis_idx):
        is_swap = self.stage_widget.check_swap.isChecked()
        inv_x = self.stage_widget.check_inv_x.isChecked()
        inv_y = self.stage_widget.check_inv_y.isChecked()
        
        phys_axis = 0
        phys_dist = delta
        
        if logical_axis_idx == 0: # X
            phys_axis = 1 if is_swap else 0
            if inv_x: phys_dist *= -1
            self.stage_widget.target_x.setText(f"{self.stage_widget.target_x.text()}{delta:.3f}")
        else: # Y
            phys_axis = 0 if is_swap else 1
            if inv_y: phys_dist *= -1
            self.stage_widget.target_y.setText(f"{self.stage_widget.target_y.text()}{delta:.3f}")
            
        self.motion.move_by(phys_dist, axis=phys_axis)
        self.update_stage_display()

    def zero_stage(self):
        self.stage_widget.target_x.setText("0.000")
        self.stage_widget.target_y.setText("0.000")
        self.update_stage_display()
        self.log("坐标已归零")

    def preview_scan_path(self):
        try:
            from Scanner import Scanner
            import math # 需要引入math库进行向上取整

            # 1. 修正映射字典 (原代码是集合{}，无法使用.get，必须改为字典映射)
            mode_map = {
                "矩形": "rectangle", 
                "圆形": "round", 
                "螺旋": "fermat"
            }
            # 获取当前选中的模式文本，并映射到英文key
            ui_mode_text = self.combo_scan_mode.currentText()
            mode = mode_map.get(ui_mode_text, "round") # 默认 fallback 到 round
            
            # 2. 获取范围 (同时获取 X 和 Y)
            try:
                rx = float(self.scan_range_x.text())
            except ValueError: rx = 1.0
            
            try:
                ry = float(self.scan_range_y.text())
            except ValueError: ry = rx # 如果Y没填或格式错误，默认等于X，保持正方形/正圆
                
            try:
                step = float(self.scan_step.text())
                if step <= 1e-6: step = 0.1 # 防止步长为0导致除法报错
            except ValueError:
                step = 0.1

            # 3. 计算 scan_num
            calc_scan_num = 10 # 默认值
            
            if mode == 'rectangle':
                # 矩形模式：Scanner 生成的是 scan_num * scan_num 的正方形网格
                # 为了保证覆盖用户输入的范围，我们取 X 和 Y 中的最大值
                max_side = max(rx, ry)
                calc_scan_num = int(math.ceil(max_side / step))
                self.log(f"参数计算(矩形): Max边长={max_side:.3f}, 步长={step} -> 级数={calc_scan_num}")
                
            else:
                diameter = min(rx, ry) 
                radius = diameter / 2.0
                calc_scan_num = int(math.ceil(radius / step))
                self.log(f"参数计算({ui_mode_text}): 直径={diameter:.3f}, 半径={radius:.3f} -> 级数={calc_scan_num}")

            # 4. 生成 Scanner 对象
            self.scanner = Scanner(step=step, scan_num=calc_scan_num, mode=mode)
            
            # 5. 更新 UI 上的采集点数显示
            total_points = len(self.scanner.x)
            self.scan_points.setText(str(total_points))
            self.log(f"生成扫描路径: {ui_mode_text}, 总点数: {total_points}")

            # 6. 绘制预览
            plt.style.use('default')
            fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
            x_pts = np.array(self.scanner.abs_x)
            y_pts = np.array(self.scanner.abs_y)
            
            # 绘制路径连线
            ax.plot(x_pts, y_pts, 'b.-', markersize=2, linewidth=0.5, alpha=0.6)
            
            # 绘制用户期望的范围框 (红色虚线)，方便对比实际扫描覆盖情况
            ax.add_patch(plt.Rectangle((-rx/2, -ry/2), rx, ry, 
                                     fill=False, edgecolor='r', linestyle='--', label='Set Range'))
            
            ax.set_aspect('equal')
            ax.grid(True, linestyle=':', alpha=0.5)
            # 稍微扩大一点视野以便看清边界
            max_limit = max(rx, ry) / 2.0 * 1.1
            ax.set_xlim(-max_limit, max_limit)
            ax.set_ylim(-max_limit, max_limit)
            
            plt.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format='png')
            plt.close(fig)
            buf.seek(0)
            
            qimg = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
            self.lbl_scan_preview.setPixmap(pixmap)
            self.lbl_scan_preview.setScaledContents(True)

        except Exception as e:
            self.log(f"生成路径失败: {e}")
            import traceback
            traceback.print_exc()

    def confirm_directory(self):
        """
        弹出确认框，询问用户目录是否正确。
        返回: True (用户点Yes), False (用户点No)
        """
        current_dir = self.save_dir_edit.text()
        
        # 1. 如果目录为空，提示错误
        if not current_dir.strip():
            QMessageBox.warning(self, "路径错误", "保存目录不能为空！")
            return False

        # 2. 构造提示文本
        msg_text = (f"即将保存数据！\n\n"
                    f"当前保存目录为：\n"
                    f"【 {current_dir} 】\n\n"
                    f"请确认目录名称是否正确？")
        
        # 3. 弹出对话框
        reply = QMessageBox.question(
            self, 
            "目录检查", 
            msg_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No  # 默认选中 No，防止手滑
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 确认后，同步更新内部变量，并确保目录存在
            self.save_dir = current_dir
            if not os.path.exists(self.save_dir):
                try:
                    os.makedirs(self.save_dir)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"无法创建目录：\n{e}")
                    return False
            return True
        else:
            self.log("操作已取消。")
            return False

    def start_scan(self):
        # 扫描前强制重新生成一次，确保参数是最新的
        self.preview_scan_path()
        
        if not getattr(self, 'scanner', None): 
            self.log("扫描器未初始化，请先点击'显示/更新扫描路径'")
            return
        
        if not self.confirm_directory():
            return
        
        self.log(f"开始采集 {len(self.scanner.x)} 点...")
        self.scan_idx = 0
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self._scan_step)
        self.scan_timer.start(500) 
        
    def _scan_step(self):
        if self.scan_idx >= len(self.scanner.x):
            self.scan_timer.stop()
            self.log("扫描完成")
            final_x = self.scanner.final_pos[0]
            final_y = self.scanner.final_pos[1]
            self._move_logical_delta(-final_x, 0)
            self._move_logical_delta(-final_y, 1)
            return
            
        dx = self.scanner.x[self.scan_idx]
        dy = self.scanner.y[self.scan_idx]
        
        self._move_logical_delta(dx, 0)
        self._move_logical_delta(dy, 1)
            
        self.save_current_frame(filename=f"scan_{self.scan_idx}.png")
        self.scan_idx += 1

    def set_exposure_time(self):
        if self.camera:
            val = self.exposure_spin.value()
            self.camera.set_ex_time(val / 1000.0)
            self.log(f"曝光: {val} ms")

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.save_dir_edit.setText(path)
            self.save_dir = path

    def on_manual_save(self):
        """响应界面上的'保存'按钮点击"""
        # 1. 先弹窗确认
        if self.confirm_directory():
            # 2. 确认通过后，才执行保存
            self.save_current_frame()

    def save_current_frame(self, filename=None):
        if self.camera:
            try:
                # 1. 获取最新图像
                full_img = self.camera.read_newest_image()
                if full_img is None: return

                # 2. 【关键】经过 crop_image 处理，应用子图和偏移
                roi_img = self.crop_image(full_img)
                    
                if roi_img is not None:
                    if not filename:
                        filename = f"capture_{int(time.time())}.png"
                        path = os.path.join(self.save_dir, filename)
                    if not os.path.exists(self.save_dir): os.makedirs(self.save_dir)
                            
                    # 保存
                    img_pil = Image.fromarray(roi_img)
                    img_pil.save(path)
                    self.log(f"Saved ROI: {filename} ({roi_img.shape})")
                    
            except Exception as e:
                self.log(f"保存当前帧失败: {e}")
                import traceback
                traceback.print_exc()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LogicWindow()
    window.show()
    sys.exit(app.exec())