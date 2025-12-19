import sys
import os
import time
import io
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

# PyQt6 导入
from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QVBoxLayout, QFileDialog
from PyQt6.QtGui import QImage, QPixmap, QPen, QColor
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread

# 导入 UI 定义
from gui_generate import ModernUI

# =========================================================
#  硬件加载线程 (修改：增加了模拟相机的位深接口)
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
                if self.device_name == "Simulated":
                    device_instance = self._init_simulated_camera()
                elif self.device_name == "IDS":
                    from camera import IDS
                    device_instance = IDS()
                    device_instance.start_acquisition()
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
                if self.device_name == "Simulated":
                    device_instance = self._init_simulated_stage()
                elif self.device_name == "SmartAct":
                    from motion_controller import smartact
                    device_instance = smartact()
                elif self.device_name == "NewPort":
                    from motion_controller import xps
                    device_instance = xps(ip_address="192.168.0.254")
                    device_instance.init_groups(['Group3', 'Group4'])
                elif self.device_name == "Nators":
                    from motion_controller import nators
                    device_instance = nators(ip_address="192.168.0.254")
                    device_instance.open_system()

            if device_instance:
                self.finished_signal.emit(True, device_instance)
            else:
                self.finished_signal.emit(False, f"未找到驱动: {self.device_name}")

        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def _init_simulated_camera(self):
        class SimCam:
            def read_newest_image(self):
                # 模拟 2048x2048 传感器, 12-bit
                img = np.random.randint(0, 100, (2048, 2048), dtype=np.uint16)
                # 在偏离中心的位置加一个亮斑
                img[800:1000, 1200:1400] += 3000 
                return img
            def set_ex_time(self, t): pass
            
            # 【新增】模拟获取位深
            def get_bit_depth(self):
                return 12 
        return SimCam()

    def _init_simulated_stage(self):
        class SimMotion:
            def move_by(self, dist, axis): pass
            def move_to(self, pos, axis): pass
        return SimMotion()


# =========================================================
#  自定义图像显示控件 (修改：移除实时信号，改为被动查询)
# =========================================================
class InteractiveImageView(QGraphicsView):
    # 移除了 mouse_hover_signal，改为由外部定时器查询

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None
        self.np_img = None 
        self.setMouseTracking(True) 
        self.setStyleSheet("background: #000; border: 0px;")
        
        # 内部记录当前鼠标在 Image 坐标系下的位置
        self.curr_img_x = -1
        self.curr_img_y = -1
        
        # Mask 线条对象
        self.v_line = None
        self.h_line = None

    def update_image(self, image_data, show_mask=False):
        self.np_img = image_data
        
        # 1. 格式转换
        if image_data.dtype == np.uint16:
            # 简单可视化压缩
            display_data = (image_data / 16).astype(np.uint8) 
        else:
            display_data = image_data.astype(np.uint8)

        h, w = display_data.shape
        bytes_per_line = w
        qimg = QImage(display_data.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
        pix = QPixmap.fromImage(qimg)

        # 2. 更新 Pixmap
        if self.pixmap_item is None:
            self.pixmap_item = self.scene.addPixmap(pix)
        else:
            self.pixmap_item.setPixmap(pix)
        
        # 3. 绘制/更新 Mask 十字线
        if show_mask:
            cx, cy = w / 2, h / 2
            pen = QPen(QColor("#00FF00"), 1)
            pen.setStyle(Qt.PenStyle.DashLine) 
            
            if self.v_line is None:
                self.v_line = self.scene.addLine(cx, 0, cx, h, pen)
                self.h_line = self.scene.addLine(0, cy, w, cy, pen)
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
        """
        仅更新坐标缓存，不发射信号，极大降低 CPU 占用
        """
        if self.np_img is not None and self.pixmap_item is not None:
            scene_pos = self.mapToScene(event.pos())
            item_pos = self.pixmap_item.mapFromScene(scene_pos)
            x, y = int(item_pos.x()), int(item_pos.y())

            h, w = self.np_img.shape
            if 0 <= x < w and 0 <= y < h:
                self.curr_img_x = x
                self.curr_img_y = y
            else:
                self.curr_img_x = -1
                self.curr_img_y = -1
        super().mouseMoveEvent(event)

    def get_current_pixel_info(self):
        """供外部定时器调用的接口"""
        if self.np_img is None: return -1, -1, 0
        
        x, y = self.curr_img_x, self.curr_img_y
        if x >= 0:
            val = self.np_img[y, x]
            return x, y, val
        return -1, -1, 0


# =========================================================
#  主逻辑窗口
# =========================================================
class LogicWindow(ModernUI):
    def __init__(self):
        super().__init__()
        
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
        # 注意：这里不再连接 mouse_hover_signal

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
        self.scanner = None
        
        # 相机参数
        self.saturation_value = 65535 # 默认 16bit，后续会自动读取

        # 软件维护的绝对坐标
        self.stage_pos = {'x': 0.0, 'y': 0.0}

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
            self.btn_open_cam.setStyleSheet("background-color: #a0d468")
            
            # 【新增】读取位深并计算饱和值
            bit_depth = 16 # 默认防守值
            if hasattr(self.camera, "get_bit_depth"):
                try:
                    bit_depth = self.camera.get_bit_depth()
                except:
                    pass
            elif hasattr(self.camera, "BitDepth"): # 兼容部分属性直接访问
                 bit_depth = self.camera.BitDepth
            
            self.saturation_value = (1 << bit_depth) - 1
            self.line_cam_max.setText(f"{self.saturation_value} ({bit_depth}-bit)")
            self.log(f"相机初始化成功，位深: {bit_depth}, 饱和值: {self.saturation_value}")
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
            self.zero_stage()
        else:
            self.log(f"位移台错误: {result}")

    # --- 图像处理核心逻辑 ---
    def crop_image(self, full_image):
        if full_image is None: return None
        h_full, w_full = full_image.shape
        
        target_w = self.roi_w.value()
        target_h = self.roi_h.value()
        off_x = self.off_x.value()
        off_y = self.off_y.value()
        
        center_x = w_full // 2 + off_x
        center_y = h_full // 2 + off_y
        
        x1 = int(center_x - target_w // 2)
        y1 = int(center_y - target_h // 2)
        x2 = x1 + target_w
        y2 = y1 + target_h
        
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
        self.log("坐标已归零 (软件原点)")

    # --- 扫描相关 (修改：计算点数逻辑) ---
    def preview_scan_path(self):
        try:
            from Scanner import Scanner
            
            mode_map = {"矩形": "rectangle", "圆形": "round", "螺旋": "fermat"}
            mode = mode_map.get(self.combo_scan_mode.currentText(), "round")
            
            # 1. 获取范围 (半径 或 边长)
            r_str = self.scan_range_x.text()
            r_val = float(r_str) if r_str else 1.0
            step = float(self.scan_step.text())
            
            # 2. 【核心逻辑修改】计算 scan_num
            # Scanner.py 中:
            # - round: radius = step * scan_num
            # - rectangle: width approx step * scan_num
            # - fermat: radius = step * scan_num (Scanner.py line 125)
            # 因此，我们统一反推 scan_num = range / step
            if step <= 0: step = 0.1
            calc_scan_num = int(r_val / step)
            if calc_scan_num < 1: calc_scan_num = 1
            
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

    # ... (其他辅助函数) ...
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
        if self.image_view.np_img is not None:
            if not filename:
                filename = f"capture_{int(time.time())}.png"
            path = os.path.join(self.save_dir, filename)
            if not os.path.exists(self.save_dir): os.makedirs(self.save_dir)
            
            img = Image.fromarray(self.crop_image(self.camera.read_newest_image()))
            img.save(path)
            self.log(f"Saved: {filename}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LogicWindow()
    window.show()
    sys.exit(app.exec())