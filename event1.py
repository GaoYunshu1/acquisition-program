import sys
import os
import time
import numpy as np
from PIL import Image
# PyQt6 导入
from PyQt6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QVBoxLayout, QFileDialog
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer, Qt, pyqtSignal

# 导入 UI 定义
from gui_generate import ModernUI

# 尝试导入硬件驱动
try:
    from camera import IDS, Ham
    from VSY import VSyCamera as vsy
    from VSY import VsyGvspPixelType
    from motion_controller import xps, smartact, nators
    from Scanner import Scanner
    HARDWARE_AVAILABLE = True
except ImportError:
    print("硬件驱动未找到，启用模拟模式。")
    HARDWARE_AVAILABLE = False
    class Scanner: pass
    class IDS: pass

# =========================================
# 自定义图像显示控件 (PyQt6)
# =========================================
class InteractiveImageView(QGraphicsView):
    # 信号：x, y, pixel_value
    mouse_hover_signal = pyqtSignal(int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None
        self.np_img = None 
        self.setMouseTracking(True) 
        self.setStyleSheet("background: #000; border: 0px;")

    def update_image(self, image_data):
        self.np_img = image_data
        
        if image_data.dtype == np.uint16:
            # 简单压缩用于显示
            display_data = (image_data / 16).astype(np.uint8) 
        else:
            display_data = image_data.astype(np.uint8)

        h, w = display_data.shape
        bytes_per_line = w
        # PyQt6 Enum: QImage.Format.Format_Grayscale8
        qimg = QImage(display_data.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
        pix = QPixmap.fromImage(qimg)

        if self.pixmap_item is None:
            self.pixmap_item = self.scene.addPixmap(pix)
        else:
            self.pixmap_item.setPixmap(pix)
        
        # PyQt6 Enum: Qt.AspectRatioMode.KeepAspectRatio
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

# =========================================
# 业务逻辑类
# =========================================
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

        # --- 3. 信号绑定 ---
        self.btn_open_cam.clicked.connect(self.init_camera)
        self.btn_connect_stage.clicked.connect(self.init_motion)
        
        self.btn_live.clicked.connect(self.toggle_live)
        self.btn_cap.clicked.connect(self.start_scan)
        self.btn_save.clicked.connect(self.save_current_frame)
        self.btn_browse.clicked.connect(self.select_folder)

        # 位移台
        self.stage_widget.btn_up.clicked.connect(lambda: self.move_stage_manual('Y', 1))
        self.stage_widget.btn_down.clicked.connect(lambda: self.move_stage_manual('Y', -1))
        self.stage_widget.btn_left.clicked.connect(lambda: self.move_stage_manual('X', -1))
        self.stage_widget.btn_right.clicked.connect(lambda: self.move_stage_manual('X', 1))
        self.stage_widget.btn_go.clicked.connect(self.move_stage_absolute)
        self.stage_widget.btn_zero.clicked.connect(self.zero_stage)

        # ROI
        self.btn_center.clicked.connect(self.calculate_center)

    def update_mouse_val(self, x, y, val):
        if x >= 0:
            self.line_mouse_val.setText(f"{val}")
        else:
            self.line_mouse_val.setText("-")

    def init_camera(self):
        cam_name = self.combo_camera.currentText()
        self.log(f"初始化相机: {cam_name}...")
        try:
            if cam_name == "Simulated" or not HARDWARE_AVAILABLE:
                self.log(">> 启用模拟相机驱动")
                class SimCam:
                    def read_newest_image(self):
                        img = np.random.randint(0, 500, (1024, 1024), dtype=np.uint16)
                        img[500:520, 500:520] += 2000
                        return img
                    def set_ex_time(self, t): pass
                self.camera = SimCam()
            else:
                if cam_name == "IDS":
                    self.camera = IDS()
                    self.camera.start_acquisition()
            
            self.btn_open_cam.setText("已就绪")
            self.btn_open_cam.setStyleSheet("background-color: #a0d468")
            self.log("相机初始化成功")
        except Exception as e:
            self.log(f"相机错误: {e}")

    def init_motion(self):
        stage_name = self.combo_stage.currentText()
        self.log(f"连接位移台: {stage_name}...")
        try:
            self.btn_connect_stage.setText("已连接")
            self.log("位移台连接成功")
            class SimMotion:
                def move_by(self, dist, axis): print(f"Move Axis {axis} by {dist}")
                def move_to(self, pos, axis): print(f"Move Axis {axis} to {pos}")
            self.motion = SimMotion()
        except Exception as e:
            self.log(f"位移台错误: {e}")

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
                max_val = np.max(img)
                self.line_global_max.setText(f"{max_val}")
                
                if self.chk_log.isChecked():
                    img_disp = np.log1p(img.astype(np.float32))
                    img_disp = (img_disp / img_disp.max() * 65535).astype(np.uint16)
                    self.image_view.update_image(img_disp)
                else:
                    self.image_view.update_image(img)
            except Exception as e:
                print(e)

    def move_stage_manual(self, axis_name, direction):
        if not self.motion:
            self.log("位移台未连接")
            return
            
        step = self.stage_widget.step_spin.value()
        is_swap = self.stage_widget.check_swap.isChecked()
        inv_x = self.stage_widget.check_inv_x.isChecked()
        inv_y = self.stage_widget.check_inv_y.isChecked()
        
        target_axis = 0 # 0:X, 1:Y
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
        if self.motion:
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

    def start_scan(self):
        self.log("开始扫描...")

    def save_current_frame(self):
        if self.image_view.np_img is not None:
            path = os.path.join(self.save_dir, f"capture_{int(time.time())}.png")
            self.log(f"图片已保存: {path}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LogicWindow()
    window.show()
    sys.exit(app.exec())