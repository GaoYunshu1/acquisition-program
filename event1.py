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

# 尝试导入硬件驱动
from motion_controller import xps, smartact, nators
from Scanner import Scanner

# =========================================================
#  硬件加载线程 (解决连接慢的问题)
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
                elif self.device_name == "NewPort (XPS)":
                    # 这里的名字要和 UI 里的 addItems 对应
                    from motion_controller import xps
                    device_instance = xps()
                    device_instance.init_groups(['Group3', 'Group4'])
                elif self.device_name == "Nators":
                    from motion_controller import nators
                    device_instance = nators()
                    device_instance.open_system()
                # 兼容 gui_generate.py 中写的 "NewPort" 简写
                elif self.device_name == "NewPort":
                    from motion_controller import xps
                    device_instance = xps()
                    device_instance.init_groups(['Group3', 'Group4'])

            if device_instance:
                self.finished_signal.emit(True, device_instance)
            else:
                self.finished_signal.emit(False, f"未找到驱动: {self.device_name}")

        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def _init_simulated_camera(self):
        class SimCam:
            def read_newest_image(self):
                img = np.random.randint(0, 500, (1024, 1024), dtype=np.uint16)
                img[400:600, 400:600] += 3000 
                return img
            def set_ex_time(self, t): pass
        return SimCam()

    def _init_simulated_stage(self):
        class SimMotion:
            def move_by(self, dist, axis): pass
            def move_to(self, pos, axis): pass
        return SimMotion()


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
        else:
            self.pixmap_item.setPixmap(pix)
        
        # 处理 Mask (十字线)
        if show_mask:
            cx, cy = w / 2, h / 2
            pen = QPen(QColor("lime"), 1)
            
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
        self.image_view.mouse_hover_signal.connect(self.update_mouse_val)

        # --- 2. 内部变量 ---
        self.camera = None
        self.motion = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.is_live = False
        self.save_dir = "data"
        self.scanner = None
        self.loader_thread = None 

        # --- 3. 信号绑定 ---
        self.btn_open_cam.clicked.connect(self.start_init_camera)
        self.btn_connect_stage.clicked.connect(self.start_init_motion)
        
        self.btn_live.clicked.connect(self.toggle_live)
        self.btn_cap.clicked.connect(self.start_scan)
        self.btn_save.clicked.connect(self.save_current_frame)
        self.btn_browse.clicked.connect(self.select_folder)
        self.btn_show_path.clicked.connect(self.preview_scan_path)

        # 位移台
        self.stage_widget.btn_up.clicked.connect(lambda: self.move_stage_manual('Y', 1))
        self.stage_widget.btn_down.clicked.connect(lambda: self.move_stage_manual('Y', -1))
        self.stage_widget.btn_left.clicked.connect(lambda: self.move_stage_manual('X', -1))
        self.stage_widget.btn_right.clicked.connect(lambda: self.move_stage_manual('X', 1))
        self.stage_widget.btn_go.clicked.connect(self.move_stage_absolute)
        self.stage_widget.btn_zero.clicked.connect(self.zero_stage)

        # ROI & Exposure
        self.btn_center.clicked.connect(self.calculate_center)
        self.exposure_spin.valueChanged.connect(self.set_exposure_time)

    def update_mouse_val(self, x, y, val):
        if x >= 0:
            self.line_mouse_val.setText(f"{val}")
        else:
            self.line_mouse_val.setText("-")

    # --- 异步加载 ---
    def start_init_camera(self):
        cam_name = self.combo_camera.currentText()
        self.log(f"正在初始化相机: {cam_name}...")
        self.btn_open_cam.setEnabled(False)
        self.btn_open_cam.setText("连接中...")
        
        self.loader_thread = DeviceLoader('camera', cam_name)
        self.loader_thread.finished_signal.connect(self.on_camera_loaded)
        self.loader_thread.start()

    def on_camera_loaded(self, success, result):
        self.btn_open_cam.setEnabled(True)
        if success:
            self.camera = result
            self.btn_open_cam.setText("已就绪")
            self.btn_open_cam.setStyleSheet("background-color: #a0d468")
            self.log("相机初始化成功")
        else:
            self.btn_open_cam.setText("打开失败")
            self.btn_open_cam.setStyleSheet("background-color: #e74c3c")
            self.log(f"相机错误: {result}")

    def start_init_motion(self):
        stage_name = self.combo_stage.currentText()
        self.log(f"正在连接位移台: {stage_name}...")
        self.btn_connect_stage.setEnabled(False)
        self.btn_connect_stage.setText("连接中...")
        
        self.loader_thread = DeviceLoader('stage', stage_name)
        self.loader_thread.finished_signal.connect(self.on_motion_loaded)
        self.loader_thread.start()

    def on_motion_loaded(self, success, result):
        self.btn_connect_stage.setEnabled(True)
        if success:
            self.motion = result
            self.btn_connect_stage.setText("已连接")
            self.log("位移台连接成功")
        else:
            self.btn_connect_stage.setText("连接失败")
            self.log(f"位移台错误: {result}")

    # --- 实时显示 ---
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

    def update_frame(self):
        if self.camera:
            try:
                img = self.camera.read_newest_image()
                if img is None: return
                
                max_val = np.max(img)
                self.line_global_max.setText(f"{max_val}")
                
                # 传递 mask 状态给 update_image
                show_mask = self.chk_mask.isChecked()
                
                if self.chk_log.isChecked():
                    img_disp = np.log1p(img.astype(np.float32))
                    img_disp = (img_disp / img_disp.max() * 65535).astype(np.uint16)
                    self.image_view.update_image(img_disp, show_mask)
                else:
                    self.image_view.update_image(img, show_mask)
            except Exception as e:
                pass

    def set_exposure_time(self):
        if self.camera:
            val = self.exposure_spin.value()
            self.camera.set_ex_time(val / 1000.0)
            self.log(f"曝光设为: {val} ms")

    # --- 扫描路径 ---
    def preview_scan_path(self):
        """生成路径并在UI下方的 Label 中显示预览图"""
        try:
            from Scanner import Scanner
            
            mode_map = {"矩形": "rectangle", "圆形": "round", "螺旋": "fermat", "fermat": "fermat"}
            mode = mode_map.get(self.combo_scan_mode.currentText(), "round")
            
            # 解析范围
            r_str = self.scan_range.text().split(',')
            r_val = float(r_str[0]) if len(r_str) > 0 else 1.0
            step = float(self.scan_step.text())
            num = self.scan_points.value()
            
            if mode == 'rectangle':
                 scan_num = int(r_val / step)
            else:
                 scan_num = num 
            
            self.log(f"生成扫描路径: {mode}, 步长{step}")
            self.scanner = Scanner(step=step, scan_num=scan_num, mode=mode)
            self.log(f"路径点数: {len(self.scanner.x)}")

            # --- 绘制路径预览图 (Matplotlib -> QPixmap) ---
            # 使用 Agg 后端，不弹窗
            plt.style.use('default')
            fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
            
            # 绘制数据
            x_pts = np.array(self.scanner.abs_x)
            y_pts = np.array(self.scanner.abs_y)
            ax.plot(x_pts, y_pts, 'b.-', markersize=2, linewidth=0.5, alpha=0.6)
            ax.set_title(f"{mode} Path ({len(x_pts)} pts)")
            ax.set_aspect('equal')
            ax.grid(True, linestyle=':', alpha=0.5)
            plt.tight_layout()

            # 保存到内存缓冲区
            buf = io.BytesIO()
            fig.savefig(buf, format='png')
            plt.close(fig)
            buf.seek(0)
            
            # 加载到 QPixmap 并显示
            qimg = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
            self.lbl_scan_preview.setPixmap(pixmap)
            # 缩放以适应标签大小
            self.lbl_scan_preview.setScaledContents(True)

        except Exception as e:
            self.log(f"生成路径失败: {e}")

    def start_scan(self):
        # 自动检测：如果用户没点“显示路径”，这里自动帮忙生成
        if not self.scanner:
            self.log("未检测到路径，正在自动生成...")
            self.preview_scan_path() # 这会生成 self.scanner 并更新UI
            
        if not self.scanner:
            self.log("路径生成失败，无法采集！")
            return
        
        self.log(f"开始采集，总计 {len(self.scanner.x)} 点...")
        self.scan_idx = 0
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self._scan_step)
        self.scan_timer.start(500) 
        
    def _scan_step(self):
        if self.scan_idx >= len(self.scanner.x):
            self.scan_timer.stop()
            self.log("扫描完成")
            # 回归原点
            final_pos = self.scanner.final_pos
            if self.motion:
                self.motion.move_by(-final_pos[0], axis=0)
                self.motion.move_by(-final_pos[1], axis=1)
            return
            
        dx = self.scanner.x[self.scan_idx]
        dy = self.scanner.y[self.scan_idx]
        
        if self.motion:
            self.motion.move_by(dx, axis=0)
            self.motion.move_by(dy, axis=1)
            
        self.save_current_frame(filename=f"scan_{self.scan_idx}.png")
        self.scan_idx += 1

    # --- 辅助功能 ---
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
        self.log(f"移动轴 {target_axis}, 距离 {dist}")
        self.motion.move_by(dist, axis=target_axis)
        
        if axis_name == 'X':
            old_val = float(self.stage_widget.lbl_x.text().split()[1])
            self.stage_widget.lbl_x.setText(f"X: {old_val + dist:.3f} mm")
        else:
            old_val = float(self.stage_widget.lbl_y.text().split()[1])
            self.stage_widget.lbl_y.setText(f"Y: {old_val + dist:.3f} mm")

    def move_stage_absolute(self):
        x = self.stage_widget.target_x.value()
        y = self.stage_widget.target_y.value()
        self.log(f"移动至绝对坐标: ({x}, {y})")
        if self.motion and hasattr(self.motion, 'move_to'):
            self.motion.move_to(x, axis=0) 
            self.motion.move_to(y, axis=1)

    def zero_stage(self):
        self.log("坐标归零")
        self.stage_widget.lbl_x.setText("X: 0.000 mm")
        self.stage_widget.lbl_y.setText("Y: 0.000 mm")

    def calculate_center(self):
        if self.image_view.np_img is None:
            self.log("无图像数据")
            return
        h, w = self.image_view.np_img.shape
        cy, cx = h//2, w//2 
        target_w = self.roi_w.value()
        target_h = self.roi_h.value()
        offset_x = cx - target_w // 2
        offset_y = cy - target_h // 2
        self.off_x.setValue(offset_x)
        self.off_y.setValue(offset_y)
        self.log(f"计算偏移: {offset_x}, {offset_y}")

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
            
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir)
                
            img = Image.fromarray(self.image_view.np_img)
            img.save(path)
            self.log(f"Saved: {filename}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LogicWindow()
    window.show()
    sys.exit(app.exec())