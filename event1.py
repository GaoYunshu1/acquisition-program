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
from camera import IDS, Ham
from VSY import VSyCamera as vsy
from motion_controller import xps, smartact, nators
from Scanner import Scanner, visualize_scan_path 
# from lucid import LucidCamera
# from photometrics import PyVCAM
# from peak import IDSPeakCamera

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
        self.scanner = None

        # --- 3. 信号绑定 ---
        self.btn_open_cam.clicked.connect(self.init_camera)
        self.btn_connect_stage.clicked.connect(self.init_motion)
        
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

        # ROI
        self.btn_center.clicked.connect(self.calculate_center)
        self.exposure_spin.valueChanged.connect(self.set_exposure_time)

    def update_mouse_val(self, x, y, val):
        if x >= 0:
            self.line_mouse_val.setText(f"{val}")
        else:
            self.line_mouse_val.setText("-")

    def init_camera(self):
        cam_name = self.combo_camera.currentText()
        self.log(f"初始化相机: {cam_name}...")
        try:
            if cam_name == "Simulated":
                self._init_simulated_camera()
            elif cam_name == "IDS":
                self.camera = IDS()
                self.camera.start_acquisition()
                self.camera.set_pixel_rate(7e7)
            elif cam_name == "Ham":
                self.camera = Ham()
                self.camera.start_acquisition()
            elif cam_name == "Lucid":
                if 'LucidCamera' in globals() and LucidCamera:
                    self.camera = LucidCamera()
                    self.camera.start_acquisition()
                else:
                    self.log("Lucid 驱动未加载")
                    return
            elif cam_name == "PM":
                if 'PyVCAM' in globals() and PyVCAM:
                    self.camera = PyVCAM()
                    self.camera.start_acquisition()
                else:
                    self.log("Photometrics 驱动未加载")
                    return
            elif cam_name == "IDS_Peak":
                 if 'IDSPeakCamera' in globals() and IDSPeakCamera:
                    self.camera = IDSPeakCamera()
                    self.camera.start_acquisition()
                 else:
                    self.log("IDS Peak 驱动未加载")
                    return
            
            self.btn_open_cam.setText("已就绪")
            self.btn_open_cam.setStyleSheet("background-color: #a0d468")
            self.log("相机初始化成功")
        except Exception as e:
            self.log(f"相机错误: {e}")
            # 出错时启用模拟相机防止崩溃
            self._init_simulated_camera()
            
    def _init_simulated_camera(self):
        self.log(">> 启用模拟相机驱动")
        class SimCam:
            def read_newest_image(self):
                img = np.random.randint(0, 500, (1024, 1024), dtype=np.uint16)
                img[500:520, 500:520] += 2000
                return img
            def set_ex_time(self, t): pass
        self.camera = SimCam()

    def init_motion(self):
        stage_name = self.combo_stage.currentText()
        self.log(f"连接位移台: {stage_name}...")
        try:
            if stage_name == "SmartAct":
                self.motion = smartact()
            elif stage_name == "NewPort (XPS)":
                self.motion = xps(IP='192.168.0.254')
                self.motion.init_groups(['Group3', 'Group4']) # 根据实际情况调整
            elif stage_name == "Nators":
                self.motion = nators()
                self.motion.open_system()
            elif stage_name == "Simulated":
                class SimMotion:
                    def move_by(self, dist, axis): print(f"Move Axis {axis} by {dist}")
                    def move_to(self, pos, axis): print(f"Move Axis {axis} to {pos}")
                self.motion = SimMotion()

            self.btn_connect_stage.setText("已连接")
            self.log("位移台连接成功")
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
                if img is None: return
                
                max_val = np.max(img)
                self.line_global_max.setText(f"{max_val}")
                
                if self.chk_log.isChecked():
                    img_disp = np.log1p(img.astype(np.float32))
                    img_disp = (img_disp / img_disp.max() * 65535).astype(np.uint16)
                    self.image_view.update_image(img_disp)
                else:
                    self.image_view.update_image(img)
            except Exception as e:
                pass

    def set_exposure_time(self):
        if self.camera:
            val = self.exposure_spin.value()
            # 大部分相机驱动接收秒为单位
            self.camera.set_ex_time(val / 1000.0)
            self.log(f"曝光设为: {val} ms")

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
        
        # 简单更新UI坐标显示
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
        # 需要位移台支持 move_to 接口，如果只有 move_by 需要改逻辑
        if self.motion and hasattr(self.motion, 'move_to'):
            self.motion.move_to(x, axis=0) 
            self.motion.move_to(y, axis=1)
        else:
            self.log("当前位移台驱动不支持绝对定位指令")

    def zero_stage(self):
        self.log("坐标归零")
        self.stage_widget.lbl_x.setText("X: 0.000 mm")
        self.stage_widget.lbl_y.setText("Y: 0.000 mm")
        # 如果硬件支持硬件归零，可在此调用 self.motion.home()

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

    def preview_scan_path(self):
        """生成并预览扫描路径"""
        try:
            mode_map = {"矩形": "rectangle", "圆形": "round", "螺旋": "fermat", "fermat": "fermat"}
            mode = mode_map.get(self.combo_scan_mode.currentText(), "round")
            
            # 解析范围
            r_str = self.scan_range.text().split(',')
            if len(r_str) == 1: 
                r_val = float(r_str[0])
            else:
                r_val = float(r_str[0]) # 简单起见取第一个数作为范围基准
                
            step = float(self.scan_step.text())
            num = self.scan_points.value()
            
            # 如果是矩形/圆形，通常 num 指的是边长点数或者半径点数，而不是总点数
            # 这里简单适配 Scanner 类的参数
            if mode == 'rectangle':
                 # 假设范围是边长，计算点数
                 scan_num = int(r_val / step)
            else:
                 scan_num = num # 对于螺旋线，直接用点数
            
            self.log(f"生成扫描路径: {mode}, 步长{step}")
            self.scanner = Scanner(step=step, scan_num=scan_num, mode=mode)
            
            # 调用可视化
            visualize_scan_path(self.scanner)
            self.log(f"路径生成完毕，总点数: {len(self.scanner.x)}")
            
        except Exception as e:
            self.log(f"生成路径失败: {e}")

    def start_scan(self):
        if not self.scanner:
            self.log("请先生成扫描路径！")
            return
        
        self.log(f"开始采集，总计 {len(self.scanner.x)} 点...")
        # 这里需要实现一个非阻塞的扫描循环
        # 简单演示：使用 QTimer 逐点移动
        self.scan_idx = 0
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self._scan_step)
        self.scan_timer.start(500) # 500ms 一点
        
    def _scan_step(self):
        if self.scan_idx >= len(self.scanner.x):
            self.scan_timer.stop()
            self.log("扫描完成")
            # 回到原点
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
            
        # 拍照保存
        self.save_current_frame(filename=f"scan_{self.scan_idx}.png")
        self.scan_idx += 1

    def save_current_frame(self, filename=None):
        if self.image_view.np_img is not None:
            if not filename:
                filename = f"capture_{int(time.time())}.png"
            path = os.path.join(self.save_dir, filename)
            
            # 确保目录存在
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir)
                
            # 保存
            img = Image.fromarray(self.image_view.np_img)
            img.save(path)
            self.log(f"Saved: {filename}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LogicWindow()
    window.show()
    sys.exit(app.exec())