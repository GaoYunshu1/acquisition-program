import sys
import os
import time
import io
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import traceback

# PyQt6 导入
from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QVBoxLayout, QFileDialog
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
                # 兼容 gui_generate.py 中写的 "NewPort" 简写
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
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.is_live = False
        
        # 【新增】鼠标信息更新定时器 (0.1s = 100ms)
        self.mouse_info_timer = QTimer()
        self.mouse_info_timer.setInterval(100) 
        self.mouse_info_timer.timeout.connect(self.update_mouse_display_throttled)
        self.mouse_info_timer.start()

        self.save_dir = "data"

        # --- 3. 信号绑定 ---
        self.btn_open_cam.clicked.connect(self.start_init_camera)
        self.btn_connect_stage.clicked.connect(self.start_init_motion)
        
        self.btn_live.clicked.connect(self.toggle_live)
        self.btn_cap.clicked.connect(self.start_scan)
        self.btn_save.clicked.connect(self.save_current_frame)
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

    def update_mouse_display_throttled(self):
        """【新增】每0.1秒调用一次，从 View 获取数据更新 UI"""
        x, y, val = self.image_view.get_current_pixel_info()
        
        if x >= 0:
            self.line_mouse_val.setText(f"{val}")
            # 简单的过曝警示
            if val >= self.saturation_value:
                self.line_mouse_val.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")
            else:
                self.line_mouse_val.setStyleSheet("color: blue; font-weight: bold; background: #f0f0f0;")
        else:
            self.line_mouse_val.setText("-")
            self.line_mouse_val.setStyleSheet("color: blue; font-weight: bold; background: #f0f0f0;")

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
            
            # [修改点]：在这里插入读取位深的逻辑
            # [标准逻辑]：初始化成功后，立即查询设备属性
            
            bit_depth = 16 # 默认值，作为防守编程
            
            # 1. 尝试通过标准接口获取
            if hasattr(self.camera, "get_bit_depth"):
                try:
                    bit_depth = self.camera.get_bit_depth()
                except:
                    pass
            # 2. 或者尝试直接读取属性 (很多SDK如 IDS, Hamamatsu 可能是属性)
            elif hasattr(self.camera, "BitDepth"):
                bit_depth = self.camera.BitDepth
                
            # 3. 计算饱和值 (2的n次方 - 1)
            self.saturation_value = (1 << bit_depth) - 1
            
            # 更新界面显示
            self.line_cam_max.setText(f"{self.saturation_value} ({bit_depth}-bit)")
            self.log(f"相机就绪，位深: {bit_depth}, 饱和阈值: {self.saturation_value}")
            
        else:
            self.log(f"相机错误: {result}")

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
            
            # [修改点]：原本这里可能写的是 self.zero_stage()
            # [标准逻辑]：连接后第一件事是“同步硬件状态”
            self.sync_hardware_position() 
        else:
            self.log(f"位移台错误: {result}")

    def sync_hardware_position(self):
        """标准逻辑：读取硬件当前的绝对位置更新到软件"""
        if not self.motion: return
        try:
            # 假设 XPS 驱动有一个获取位置的方法，通常是 GroupPositionCurrentGet
            # 或者是通用的 get_position(axis_index)
            # 这里演示通用写法，具体取决于你的 xps.py 封装
            
            # 0 代表 X轴, 1 代表 Y轴
            hw_x = self.motion.get_position(0) 
            hw_y = self.motion.get_position(1)
            
            # 更新软件内的“绝对坐标缓存”
            self.stage_pos['x'] = float(hw_x)
            self.stage_pos['y'] = float(hw_y)
            
            # 刷新 UI 显示
            self.update_stage_display()
            self.log(f"已同步硬件位置: X={hw_x}, Y={hw_y}")
        except Exception as e:
            self.log(f"读取硬件位置失败，回退到软件零点: {e}")
            self.zero_stage()

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
            self.btn_live.setText("👁 观察")
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
        self.stage_widget.lbl_x.setText(f"X: {self.stage_pos['x']:.3f} mm")
        self.stage_widget.lbl_y.setText(f"Y: {self.stage_pos['y']:.3f} mm")

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
                self.stage_pos['x'] += step * direction 
            else:
                self.stage_pos['y'] += step * direction
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
        
        dx = target_x - self.stage_pos['x']
        dy = target_y - self.stage_pos['y']
        
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
            self.stage_pos['x'] += delta
        else: # Y
            phys_axis = 0 if is_swap else 1
            if inv_y: phys_dist *= -1
            self.stage_pos['y'] += delta
            
        self.motion.move_by(phys_dist, axis=phys_axis)
        self.update_stage_display()

    def zero_stage(self):
        self.stage_pos['x'] = 0.0
        self.stage_pos['y'] = 0.0
        self.update_stage_display()
        self.log("坐标已归零")

    # --- 扫描相关 (修改：计算点数逻辑) ---
    def preview_scan_path(self):
        try:
            from Scanner import Scanner
            
            mode_map = {"矩形", "圆形", "螺旋"}
            mode = mode_map.get(self.combo_scan_mode.currentText(), "round")
            
            # 1. 获取范围 (半径 或 边长)
            r_str = self.scan_range_x.text()
            r_val = float(r_str) if r_str else 1.0
            step = float(self.scan_step.text())
            
            self.log(f"计算扫描参数: 范围={r_val}, 步长={step} -> 级数={calc_scan_num}")

            # 3. 生成 Scanner 对象
            self.scanner = Scanner(step=step, scan_num=calc_scan_num, mode=mode)
            
            # 4. 更新 UI 上的采集点数显示 (设为只读或更新值)
            total_points = len(self.scanner.x)
            self.scan_points.setText(str(total_points))
            self.log(f"生成扫描路径: {mode}, 总点数: {total_points}")

            # 5. 绘制预览
            plt.style.use('default')
            fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
            x_pts = np.array(self.scanner.abs_x)
            y_pts = np.array(self.scanner.abs_y)
            ax.plot(x_pts, y_pts, 'b.-', markersize=2, linewidth=0.5, alpha=0.6)
            ax.set_aspect('equal')
            ax.grid(True, linestyle=':', alpha=0.5)
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

    def start_scan(self):
        # 扫描前强制重新生成一次，确保参数是最新的
        self.preview_scan_path()
            
        if not self.scanner: return
        
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

    def save_current_frame(self, filename=None):
        if self.camera:
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LogicWindow()
    window.show()
    sys.exit(app.exec())