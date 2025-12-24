import sys
import os
import time
import io
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import traceback
import h5py

# PyQt6 导入
from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QVBoxLayout, QFileDialog, QMessageBox, QInputDialog
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
                if self.device_name == "NewPort":
                    from motion_controller import xps
                    device_instance = xps(IP='192.168.0.254')
                    device_instance.init_groups(['Group3', 'Group4'])
                elif self.device_name == "Nators":
                    from motion_controller import nators
                    device_instance = nators(ip_address="192.168.0.254")
                    device_instance.open_system()
                elif self.device_name == "SmartAct":
                    from motion_controller import smartact
                    device_instance = smartact()

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
            
            # 1. 定义垂直线的笔 (红色，宽度2，虚线)
            pen_v = QPen(QColor("red"), 2)
            pen_v.setStyle(Qt.PenStyle.DashLine)

            # 2. 定义水平线的笔 (蓝色，宽度2，虚线)
            pen_h = QPen(QColor("blue"), 2)
            pen_h.setStyle(Qt.PenStyle.DashLine)
            
            if self.v_line is None:
                # 创建线条时分别传入对应的笔
                self.v_line = self.scene.addLine(cx, 0, cx, h, pen_v)
                self.h_line = self.scene.addLine(0, cy, w, cy, pen_h)
                
                # 设置层级，确保显示在图片上方
                self.v_line.setZValue(1)
                self.h_line.setZValue(1)
            else:
                # 更新线条位置
                self.v_line.setLine(cx, 0, cx, h)
                self.h_line.setLine(0, cy, w, cy)
                
                # 【关键】更新笔的样式 (确保颜色和粗细实时生效)
                self.v_line.setPen(pen_v)
                self.h_line.setPen(pen_h)
                
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
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.image_view.mouse_hover_signal.connect(self.on_mouse_moved)
        self.default_save_dir = "please change this to your own path"
        self.save_dir = self.default_save_dir

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
        """全局异常捕获"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(error_msg, file=sys.stderr)
        
        header = f"⛔ 【系统崩溃/错误】 {exc_type.__name__}: {exc_value}"
        self.log_error(header + "\n" + error_msg)

    # =====================================================
    # 【新增】改进的日志函数
    # =====================================================
    def log_info(self, msg):
        """信息日志 - 蓝色"""
        timestamp = time.strftime("%H:%M:%S")
        html = f"<span style='color:#2196F3;'><b>[{timestamp}]</b> ℹ️ {msg}</span>"
        self.txt_log.append(html)
        self._scroll_to_bottom()
    
    def log_success(self, msg):
        """成功日志 - 绿色"""
        timestamp = time.strftime("%H:%M:%S")
        html = f"<span style='color:#4CAF50;'><b>[{timestamp}]</b> ✅ {msg}</span>"
        self.txt_log.append(html)
        self._scroll_to_bottom()
    
    def log_warning(self, msg):
        """警告日志 - 橙色"""
        timestamp = time.strftime("%H:%M:%S")
        html = f"<span style='color:#FF9800;'><b>[{timestamp}]</b> ⚠️ {msg}</span>"
        self.txt_log.append(html)
        self._scroll_to_bottom()
    
    def log_error(self, msg):
        """错误日志 - 红色"""
        timestamp = time.strftime("%H:%M:%S")
        html = f"<span style='color:#F44336;'><b>[{timestamp}]</b> ❌ {msg}</span>"
        self.txt_log.append(html)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """自动滚动到底部"""
        scrollbar = self.txt_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

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

    # --- 异步加载设备 ---
    def start_init_camera(self):
        """步骤1: 仅仅负责启动线程"""
        cam_name = self.combo_camera.currentText()
        self.log_info(f"正在初始化相机: {cam_name}...")
        self.btn_open_cam.setEnabled(False) # 禁用按钮防止重复点击
        
        # 创建并启动线程
        self.loader_thread_cam = DeviceLoader('camera', cam_name)
        # 【关键】将线程结束的信号，连接到下面的回调函数
        self.loader_thread_cam.finished_signal.connect(self.on_camera_loaded)
        self.loader_thread_cam.start()

    def on_camera_loaded(self, success, result):
        """步骤2: 线程跑完后自动运行这里，处理结果"""
        self.btn_open_cam.setEnabled(True) # 恢复按钮
        
        if success:
            self.camera = result
            self.btn_open_cam.setText("已就绪")
            self.btn_open_cam.setStyleSheet("background-color: #4CAF50; color: white;")
            
            # --- 相机参数初始化逻辑 ---
            # 1. 应用曝光
            self.set_exposure_time()

            # 2. 获取位深
            bit_depth = 16 
            try:
                if hasattr(self.camera, 'get_bit_depth'):
                    bit_depth = int(self.camera.get_bit_depth())
                elif hasattr(self.camera, 'bit_depth'):
                    bit_depth = int(self.camera.bit_depth)
                elif hasattr(self.camera, 'BitDepth'):
                    bit_depth = int(self.camera.BitDepth)
            except Exception as e:
                self.log_warning(f"获取位深失败，使用默认值 16: {e}")

            # 3. 计算饱和值
            self.saturation_value = (1 << bit_depth) - 1
            
            self.line_cam_max.setText(f"{self.saturation_value} ({bit_depth}-bit)")
            self.log_success(f"相机就绪 | 位深: {bit_depth} | 饱和阈值: {self.saturation_value}")
            
        else:
            self.log_error(f"相机初始化失败: {result}")

    def start_init_motion(self):
        stage_name = self.combo_stage.currentText()
        self.log_info(f"正在连接位移台: {stage_name}...")
        self.btn_connect_stage.setEnabled(False)
        self.loader_thread_stage = DeviceLoader('stage', stage_name)
        self.loader_thread_stage.finished_signal.connect(self.on_motion_loaded)
        self.loader_thread_stage.start()

    def on_motion_loaded(self, success, result):
        self.btn_connect_stage.setEnabled(True)
        if success:
            self.motion = result
            self.btn_connect_stage.setText("已连接")
            self.log_success("位移台连接成功")
            
            self.sync_hardware_position() 
        else:
            self.log_error(f"位移台错误: {result}")

    def sync_hardware_position(self):
        """标准逻辑：读取硬件当前的绝对位置更新到软件"""
        if not self.motion: return
        
        hw_x, hw_y = 0.0, 0.0
        success = False

        try:     
            # 1. 尝试通用接口 get_position(axis)
            if hasattr(self.motion, 'get_position'):
                hw_x = float(self.motion.get_position(0))
                hw_y = float(self.motion.get_position(1))
                success = True
            
            # 2. 针对特定控制器的特殊处理 (XPS, SmartAct)
            elif hasattr(self.motion, 'xps') and hasattr(self.motion, 'groups'):
                if len(self.motion.groups) >= 2:
                    g0 = self.motion.groups[0]
                    g1 = self.motion.groups[1]
                    hw_x = self.motion.xps.get_stage_position(f'{g0}.Pos')
                    hw_y = self.motion.xps.get_stage_position(f'{g1}.Pos')
                    success = True
                
            if success:
                # [关键] 这里更新显示的 Label，而不是 Target 输入框
                # 显示给用户看的是 lbl_x / lbl_y
                self.stage_widget.lbl_x.setText(f"X: {hw_x:.3f} mm")
                self.stage_widget.lbl_y.setText(f"Y: {hw_y:.3f} mm")
                
                self.stage_widget.target_x.blockSignals(True)
                self.stage_widget.target_y.blockSignals(True)
                
                # 安全地修改文本，此时绝对不会触发 move_stage_absolute
                self.stage_widget.target_x.setText(f"{hw_x:.3f}")
                self.stage_widget.target_y.setText(f"{hw_y:.3f}")
                
                # 修改完后，必须恢复信号，否则用户手动输入回车也没反应了
                self.stage_widget.target_x.blockSignals(False)
                self.stage_widget.target_y.blockSignals(False)
            else:
                self.log_warning("无法同步硬件位置")

        except Exception as e:
            self.stage_widget.target_x.blockSignals(False)
            self.stage_widget.target_y.blockSignals(False)
            self.log_error(f"同步位置异常: {e}")


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
            self.log_info("ROI 大于等于图像尺寸，无需裁剪")
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
                # 1. 获取并裁剪图像
                img = self.camera.read_newest_image()
                if img is None: return
                cropped_img = self.crop_image(img)
                
                # ==========================================
                # 【恢复】 2. 全局最大值监测与饱和报警
                # ==========================================
                max_val = np.max(cropped_img)
                self.line_global_max.setText(f"{max_val}")
                
                # 检查是否过曝 (self.saturation_value 是之前计算好的，如 255 或 4095)
                # 可以在 __init__ 里给个默认值防止报错: self.saturation_value = getattr(self, 'saturation_value', 65535)
                limit = getattr(self, 'saturation_value', 65535)
                
                if max_val >= limit:
                    self.line_global_max.setStyleSheet("color: red; font-weight: bold; background: #ffeeee;")
                else:
                    self.line_global_max.setStyleSheet("color: green; font-weight: bold; background: #f0f0f0;")

                # ==========================================
                # 【恢复】 3. 处理 Log 显示和 Mask
                # ==========================================
                # 获取 Mask 勾选状态
                show_mask = self.chk_mask.isChecked()
                
                # 处理 Log 变换
                if self.chk_log.isChecked():
                    # log(1+x) 变换，拉伸暗部细节
                    img_disp = np.log1p(cropped_img.astype(np.float32))
                    # 归一化回原来的位深范围，以便显示
                    img_disp = (img_disp / img_disp.max() * limit).astype(np.uint16)
                    self.image_view.update_image(img_disp, show_mask)
                else:
                    # 正常线性显示
                    self.image_view.update_image(cropped_img, show_mask)

                # ==========================================
                # 【保留】 4. 鼠标悬停数值更新 (防止 ROI 变化导致越界)
                # ==========================================
                h, w = cropped_img.shape
                if 0 <= self.last_mouse_x < w and 0 <= self.last_mouse_y < h:
                    # 从【原始数据】中取出值 (即使在 Log 模式下，也显示原始光子数)
                    current_val = cropped_img[self.last_mouse_y, self.last_mouse_x]
                    self.update_pixel_display(current_val)
                else:
                    # 越界重置
                    self.last_mouse_x = w // 2
                    self.last_mouse_y = h // 2
            
            except Exception as e:
                pass

    def toggle_live(self):
        if not self.camera:
            self.log_warning("请先连接并初始化相机！")
            return

        if self.is_live:
            # === 如果当前是启动状态，则停止 ===
            self.timer.stop()  # 停止定时器
            self.is_live = False
            
            # 更新按钮样式
            self.btn_live.setText("👁 启动")
            self.btn_live.setStyleSheet("background:#27ae60;color:white;font-weight:bold;")
            self.log_info("实时显示已停止")
            
        else:
            # 根据您相机的曝光时间，这个值可以调整，比如 30 或 100
            exposure_ms = self.exposure_spin.value()
            refresh_interval = max(30, int(exposure_ms)) 
            
            self.timer.start(refresh_interval)
            self.is_live = True
            
            # 更新按钮样式
            self.btn_live.setText("⬛ 停止")
            self.btn_live.setStyleSheet("background:#7f8c8d;color:white;font-weight:bold;")
            self.log_success("实时显示已启动")

    def calculate_center(self):
        if not self.camera:
            self.log_warning("相机未连接")
            return
        img = self.camera.read_newest_image()
        if img is None: 
            self.log_warning("无法获取图像用于计算")
            return
        h_full, w_full = img.shape
        threshold = np.mean(img) + np.std(img) * 2
        mask = img > threshold
        if np.sum(mask) == 0:
            self.log_warning("图像过暗，无法寻找中心")
            return
        y_indices, x_indices = np.indices(img.shape)
        total_mass = np.sum(img[mask])
        center_x = np.sum(x_indices[mask] * img[mask]) / total_mass
        center_y = np.sum(y_indices[mask] * img[mask]) / total_mass
        self.log_success(f"检测到质心: ({center_x:.1f}, {center_y:.1f})")
        
        sensor_cx = w_full / 2
        sensor_cy = h_full / 2
        offset_x = int(center_x - sensor_cx)
        offset_y = int(center_y - sensor_cy)
        
        self.off_x.setValue(offset_x)
        self.off_y.setValue(offset_y)
        self.log_success(f"已更新偏移量: X={offset_x}, Y={offset_y}")
        
    # --- 位移台逻辑 ---
    def update_stage_display(self):
        self.stage_widget.lbl_x.setText(f"X: {self.stage_widget.target_x.text()} mm")
        self.stage_widget.lbl_y.setText(f"Y: {self.stage_widget.target_y.text()} mm")

    def move_stage_manual(self, axis_name, direction):
        if not self.motion:
            self.log_warning("位移台未连接")
            return
        stage_step = self.stage_widget.step_spin.value()
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
            
        dist = stage_step * direction
        try:
            # 1. 执行相对移动
            self.motion.move_by(dist, axis=target_axis)
            self.sync_hardware_position()
            
        except Exception as e:
            self.log_error(f"移动失败: {e}")

    def move_stage_absolute(self):
        if not self.motion: return
        try:
            target_x = float(self.stage_widget.target_x.text())
            target_y = float(self.stage_widget.target_y.text())
        except ValueError:
            self.log_error("坐标输入格式错误，请输入数字")
            return
        
        self.log_success(f"移动至绝对位置: ({target_x}, {target_y})...")
        
        try:
            # 方案 A: 优先使用绝对移动接口 (更准)
            if hasattr(self.motion, 'move_to'):
                # 处理轴交换
                is_swap = self.stage_widget.check_swap.isChecked()
                
                # 简单逻辑：如果不交换，0是X；如果交换，1是X
                ax_x = 1 if is_swap else 0
                ax_y = 0 if is_swap else 1
                
                self.motion.move_to(target_x, axis=ax_x)
                self.motion.move_to(target_y, axis=ax_y)
            
            else:
                # 方案 B: 如果只有 move_by，则需要先读取当前位置算差值
                # (这里保持你原来的逻辑，但加上硬件同步)
                current_x_str = self.stage_widget.lbl_x.text().split(':')[-1].replace('mm','').strip()
                current_y_str = self.stage_widget.lbl_y.text().split(':')[-1].replace('mm','').strip()
                
                cur_x = float(current_x_str) if current_x_str else 0.0
                cur_y = float(current_y_str) if current_y_str else 0.0
                
                dx = target_x - cur_x
                dy = target_y - cur_y
                
                if abs(dx) > 1e-6: self._move_logical_delta(dx, 0)
                if abs(dy) > 1e-6: self._move_logical_delta(dy, 1)

            # 无论哪种方式，移动完最后都要同步显示
            self.sync_hardware_position()
            self.log_success(f"移动完成")
                
        except Exception as e:
            self.log_error(f"绝对移动失败: {e}")

    def _move_logical_delta(self, delta, logical_axis_idx): 
        """
        执行相对移动，并在移动后直接读取硬件位置更新界面。
        不再使用 target_x.text() + delta 这种不靠谱的字符串加减。
        """
        # 1. 获取轴映射设置
        is_swap = self.stage_widget.check_swap.isChecked()
        inv_x = self.stage_widget.check_inv_x.isChecked()
        inv_y = self.stage_widget.check_inv_y.isChecked()
        
        phys_axis = 0
        phys_dist = delta
        
        # 2. 计算物理轴和方向
        if logical_axis_idx == 0: # 逻辑 X 轴
            phys_axis = 1 if is_swap else 0
            if inv_x: phys_dist *= -1
        else: # 逻辑 Y 轴
            phys_axis = 0 if is_swap else 1
            if inv_y: phys_dist *= -1
            
        # 3. 执行物理移动
        if self.motion:
            try:
                # 发送移动指令
                self.motion.move_by(phys_dist, axis=phys_axis)
                
                # 可选：如果电机响应慢，可以加一点微小的延时，确保读回来的是移动后的值
                # time.sleep(0.05) 
                
                self.sync_hardware_position()
                
            except Exception as e:
                self.log_error(f"相对移动失败: {e}")

    def zero_stage(self):
        if not self.motion:
            self.log_warning("位移台未连接")
            return

        self.log_info("正在执行回零操作 (Move to Absolute 0)...")
        try:
            # 尝试调用硬件的绝对移动接口
            # 假设驱动通过 move_to(position, axis) 实现
            # Axis 0 = X, Axis 1 = Y
            self.motion.move_to(0.0, axis=0)
            self.motion.move_to(0.0, axis=1)
            
            # 移动完成后，同步硬件位置显示
            self.sync_hardware_position()
            self.log_success("回零完成")
            
        except AttributeError:
            # 如果驱动没有 move_to，尝试其他常见命名
            self.log_warning("驱动未提供标准 move_to 接口，尝试 set_position 0...")
            try:
                # 某些驱动可能是 set_position
                if hasattr(self.motion, 'move_absolute'):
                    self.motion.move_absolute(0.0, axis=0)
                    self.motion.move_absolute(0.0, axis=1)
                    self.sync_hardware_position()
            except Exception as e:
                self.log_error(f"回零失败: {e}")
        except Exception as e:
            self.log_error(f"回零异常: {e}")

    def preview_scan_path(self):
        try:
            from Scanner import Scanner
            mode_map = {
                "矩形": "rectangle", 
                "圆形": "round", 
                "螺旋": "fermat"
            }
            # 获取当前选中的模式文本，并映射到英文key
            ui_mode_text = self.combo_scan_mode.currentText()
            mode = mode_map.get(ui_mode_text, "round") # 默认 fallback 到 round
            
            # 2. 获取圈数
            try:
                scan_range_x = float(self.scan_range_x.text())
                scan_range_y = float(self.scan_range_y.text())
            except ValueError: scan_range_x = scan_range_y = 1

            try:
                scan_step = float(self.scan_step.text())
            except ValueError: scan_step = 0.1
            
            # 4. 生成 Scanner 对象
            self.scanner = Scanner(step=scan_step, scan_range_x=scan_range_x, scan_range_y=scan_range_y, mode=mode)
            
            # 5. 更新 UI 上的采集点数显示
            total_points = len(self.scanner.x)
            self.scan_points.setText(str(total_points))
            self.log_success(f"生成扫描路径: {ui_mode_text}, 总点数: {total_points}")

            # 6. 绘制预览
            plt.style.use('default')
            fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
            x_pts = np.array(self.scanner.abs_x)
            y_pts = np.array(self.scanner.abs_y)
            
            # 绘制路径连线
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
            self.log_error(f"生成路径失败: {e}")
            traceback.print_exc()

    def confirm_directory(self):
        """
        弹出确认框，询问用户目录是否正确。
        返回: True (用户点Yes), False (用户点No)
        """
        current_dir = self.save_dir_edit.text().strip()
        
        # 1. 检查是否为空
        if not current_dir:
            QMessageBox.warning(self, "路径错误", "保存目录不能为空!")
            return False
        
        # 2. 检查是否还是默认值
        if current_dir == self.default_save_dir:
            reply = QMessageBox.warning(
                self, 
                "⚠️ 目录未更改", 
                "请修改保存目录!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 假设 Yes 意味着 "我要去改"，则返回 False 阻止采集
                return False
            else:
                # No 意味着取消操作
                return False
        
        # 3. 更新并确保目录存在
        self.save_dir = current_dir
        if not os.path.exists(self.save_dir):
            try:
                os.makedirs(self.save_dir)
                self.log_success(f"已创建目录: {self.save_dir}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建目录:\n{e}")
                return False
        
        return True

    def start_scan(self):
        # 扫描前强制重新生成一次，确保参数是最新的
        if not self.confirm_directory():
            return

        self.preview_scan_path()
        
        if not getattr(self, 'scanner', None): 
            self.log_error("扫描器未初始化，请先点击'显示/更新扫描路径'")
            return
        
        if not self.confirm_directory():
            return
        
        self.log_info(f"开始采集 {len(self.scanner.x)} 点...")
        self.scan_idx = 0
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self._scan_step)
        self.scan_timer.start(500) 
        
    def _scan_step(self):
        if self.scan_idx >= len(self.scanner.x):
            self.scan_timer.stop()
            self.log_success("扫描完成")
            final_x = self.scanner.final_pos[0]
            final_y = self.scanner.final_pos[1]
            self._move_logical_delta(-final_x, 0)
            self._move_logical_delta(-final_y, 1)
            return
            
        dx = self.scanner.x[self.scan_idx]
        dy = self.scanner.y[self.scan_idx]
        
        self._move_logical_delta(dx, 0)
        self._move_logical_delta(dy, 1)
        
        # time.sleep(0.5)
        self.save_current_frame(filename=f"scan_{self.scan_idx}.h5")
        self.scan_idx += 1

    def set_exposure_time(self):
        if self.camera:
            val = self.exposure_spin.value()
            self.camera.set_ex_time(val / 1000.0)
            self.log_info(f"曝光: {val} ms")

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.save_dir_edit.setText(path)
            self.save_dir = path

    def on_manual_save(self):
        """响应界面上的'保存'按钮点击"""
        # 1. 检查目录
        if not self.confirm_directory():
            return
        
        default_name = f"image_{time.strftime('%H%M%S')}.h5"
        
        filename, ok = QInputDialog.getText(
            self,
            "保存单帧数据",
            "请输入文件名:",
            text=default_name
        )
        
        if ok and filename.strip():
            final_name = filename.strip()
            # 强制加上 .h5 后缀，如果用户没写
            if not final_name.endswith('.h5') and not final_name.endswith('.png'):
                final_name += '.h5'
                
            self.save_current_frame(filename=final_name)
        else:
            self.log_info("保存已取消")

    def save_current_frame(self, filename=None):
        if self.camera:
            try:
                # 1. 获取最新图像
                full_img = self.camera.read_newest_image()
                if full_img is None: return

                # 2. 【关键】经过 crop_image 处理，应用子图和偏移
                roi_img = self.crop_image(full_img)
                    
                if roi_img is not None:
                    # 准备路径
                    if not filename:
                        filename = f"temp.png"
                    path = os.path.join(self.save_dir, filename)
                    if not os.path.exists(self.save_dir): os.makedirs(self.save_dir)

                    # === 分支 A: 如果是 HDF5 文件 (保存数据+元数据) ===
                    if filename.endswith(".h5") or filename.endswith(".hdf5"):
                        # 1. 获取位移台绝对位置 (从界面显示的 Target/Current 读取)
                        try:
                            cur_x = float(self.stage_widget.target_x.text())
                            cur_y = float(self.stage_widget.target_y.text())
                        except:
                            cur_x, cur_y = 0.0, 0.0

                        # 2. 获取波长 (假设界面上有个 self.wavelength_spin 输入框，如果没有则用默认值)
                        try:
                            wavelength = float(self.wavelength_spin.value())
                        except:
                            wavelength = 633.0  # 默认波长 633 Å
                        
                        # 3. 写入 H5 文件
                        with h5py.File(path, 'w') as f:
                            # 创建数据组
                            entry = f.create_group("entry")
                            data_grp = entry.create_group("data")
                            
                            # 保存图像数据
                            data_grp.create_dataset("data", data=roi_img, compression="gzip")
                            
                            # 保存元数据
                            # (1) 波长
                            beam = entry.create_group("beam")
                            beam.create_dataset("incident_wavelength", data=wavelength)
                            
                            # (2) 绝对位置
                            position = entry.create_group("position")
                            position.create_dataset("x_position", data=cur_x)
                            position.create_dataset("y_position", data=cur_y)
                            
                            # (3) 其他信息
                            f.create_dataset("timestamp", data=time.strftime('%Y-%m-%d %H:%M:%S'))
                        
                        self.log_success(f"已保存 H5 数据: {filename} (Pos: {cur_x:.3f}, {cur_y:.3f})")

                    # === 分支 B: 如果是普通图片 (PNG/JPG) ===
                    else:
                        # 此时只能保存图片，无法保存元数据
                        img_pil = Image.fromarray(roi_img)
                        img_pil.save(path)
                        self.log_success(f"已保存图像: {filename}")
                    
            except Exception as e:
                self.log_error(f"保存失败: {e}")
                import traceback
                traceback.print_exc()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LogicWindow()
    window.show()
    sys.exit(app.exec())