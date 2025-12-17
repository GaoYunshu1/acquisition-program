import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGroupBox, QFormLayout, QLabel, QLineEdit, QPushButton, 
                             QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QTabWidget, QGridLayout, 
                             QFrame, QTextEdit, QSizePolicy, QFileDialog)
from PyQt6.QtCore import Qt

# ==========================================
# 1. 增强版位移台控制 (StageControlWidget)
# ==========================================
class StageControlWidget(QWidget):
    def __init__(self, log_callback=None):
        super().__init__()
        self.log_callback = log_callback 
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # --- A. 实时坐标显示 ---
        pos_layout = QHBoxLayout()
        self.lbl_x = QLabel("X: 0.000 mm")
        self.lbl_x.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        self.lbl_y = QLabel("Y: 0.000 mm")
        self.lbl_y.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        
        # 暴露归零按钮
        self.btn_zero = QPushButton("归零")
        self.btn_zero.setFixedSize(50, 25)
        
        pos_layout.addWidget(self.lbl_x)
        pos_layout.addSpacing(20)
        pos_layout.addWidget(self.lbl_y)
        pos_layout.addStretch()
        pos_layout.addWidget(self.btn_zero)
        layout.addLayout(pos_layout)

        # --- B. 运动控制区 (左边摇杆，右边绝对位置) ---
        move_container = QHBoxLayout()
        
        # B1. 左侧：虚拟摇杆 (步进)
        joystick_frame = QFrame()
        joystick_layout = QGridLayout(joystick_frame)
        joystick_layout.setContentsMargins(0,0,0,0)
        
        # 使用不带空格的字符，配合 setFixedSize 保证正方形
        self.btn_up = self.create_dir_btn("▲", "Y", 1)
        self.btn_down = self.create_dir_btn("▼", "Y", -1)
        self.btn_left = self.create_dir_btn("◀", "X", -1)
        self.btn_right = self.create_dir_btn("▶", "X", 1)
        
        joystick_layout.addWidget(self.btn_up, 0, 1)
        joystick_layout.addWidget(self.btn_left, 1, 0)
        joystick_layout.addWidget(self.btn_right, 1, 2)
        joystick_layout.addWidget(self.btn_down, 2, 1)
        
        move_container.addWidget(joystick_frame)
        move_container.addSpacing(15)

        # B2. 右侧：绝对移动 & 步长设置
        param_layout = QFormLayout()
        
        # 步长设置 (QDoubleSpinBox, 右对齐)
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.001, 100.0)
        self.step_spin.setValue(0.1)
        self.step_spin.setSingleStep(0.01)
        self.step_spin.setSuffix(" mm")
        self.step_spin.setAlignment(Qt.AlignmentFlag.AlignRight) # PyQt6 Enum
        param_layout.addRow("点动步长:", self.step_spin)

        # 绝对移动 X (QDoubleSpinBox, 右对齐)
        self.target_x = QDoubleSpinBox()
        self.target_x.setRange(-1000, 1000)
        self.target_x.setDecimals(3)
        self.target_x.setAlignment(Qt.AlignmentFlag.AlignRight) # PyQt6 Enum
        param_layout.addRow("X:", self.target_x)

        # 绝对移动 Y (QDoubleSpinBox, 右对齐)
        self.target_y = QDoubleSpinBox()
        self.target_y.setRange(-1000, 1000)
        self.target_y.setDecimals(3)
        self.target_y.setAlignment(Qt.AlignmentFlag.AlignRight) # PyQt6 Enum
        param_layout.addRow("Y:", self.target_y)
        
        self.btn_go = QPushButton("移动到坐标 (Go)")
        param_layout.addRow(self.btn_go)
        
        move_container.addLayout(param_layout)
        layout.addLayout(move_container)

        # --- C. 轴向配置 ---
        config_layout = QHBoxLayout()
        self.check_swap = QCheckBox("交换XY轴")
        self.check_inv_x = QCheckBox("X反转")
        self.check_inv_y = QCheckBox("Y反转")
        config_layout.addWidget(QLabel("配置:"))
        config_layout.addWidget(self.check_swap)
        config_layout.addWidget(self.check_inv_x)
        config_layout.addWidget(self.check_inv_y)
        config_layout.addStretch()
        layout.addLayout(config_layout)

    def create_dir_btn(self, text, axis, direction):
        btn = QPushButton(text)
        # 强制正方形，解决左右不对称问题
        btn.setFixedSize(40, 40) 
        btn.setStyleSheet("font-size: 18px; font-family: Arial; padding: 0px;")
        return btn

# ==========================================
# 2. 主界面
# ==========================================
class ModernUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("采集控制系统 v6 (PyQt6)")
        self.resize(1280, 950)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # --- 左侧：图像显示区 ---
        self.image_area = QFrame()
        self.image_area.setFrameShape(QFrame.Shape.StyledPanel) # PyQt6 Enum
        self.image_area.setStyleSheet("background-color: #202020; border: 1px solid #555;")
        self.image_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) # PyQt6 Enum
        
        # 这里的 Label 只是占位符，event.py 会用 InteractiveImageView 替换它
        lbl_img = QLabel("Initializing Camera...", self.image_area)
        lbl_img.setStyleSheet("color: #666; font-size: 20px;")
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter) # PyQt6 Enum
        img_layout = QVBoxLayout(self.image_area)
        img_layout.addWidget(lbl_img)
        
        # --- 右侧：控制面板 ---
        self.right_panel = QWidget()
        self.right_panel.setFixedWidth(400)
        
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(5, 0, 5, 0)
        right_layout.setSpacing(8)

        # 1. 核心控制区 (Tab Widget)
        self.tabs = QTabWidget()
        self.setup_hardware_tab() 
        self.setup_scan_tab()     
        self.tabs.addTab(self.tab_hardware, "硬件控制 (Hardware)")
        self.tabs.addTab(self.tab_scan, "自动扫描 (Scan)")
        right_layout.addWidget(self.tabs)
        
        right_layout.addStretch() 

        # 2. 状态面板、按钮、日志
        right_layout.addWidget(self.create_photon_panel())
        right_layout.addWidget(self.create_big_action_buttons())
        right_layout.addWidget(self.create_log_panel())

        main_layout.addWidget(self.image_area)   
        main_layout.addWidget(self.right_panel)  

    # 辅助函数：设置 ComboBox 居中 (PyQt6)
    def setup_combo_centered(self, combo):
        combo.setEditable(True)
        combo.lineEdit().setReadOnly(True)
        combo.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter) # PyQt6 Enum
        for i in range(combo.count()):
            # PyQt6 ItemDataRole
            combo.setItemData(i, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)

    def setup_hardware_tab(self):
        self.tab_hardware = QWidget()
        layout = QVBoxLayout(self.tab_hardware)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # --- A. 设备连接 ---
        device_group = QGroupBox("1. 设备连接")
        device_layout = QGridLayout()
        device_layout.setContentsMargins(5, 10, 5, 10)
        
        device_layout.addWidget(QLabel("相机:"), 0, 0)
        self.combo_camera = QComboBox()
        self.combo_camera.addItems(["IDS", "Ham", "Lucid", "PM", "Simulated"])
        self.setup_combo_centered(self.combo_camera)
        device_layout.addWidget(self.combo_camera, 0, 1)
        
        self.btn_open_cam = QPushButton("打开")
        device_layout.addWidget(self.btn_open_cam, 0, 2)
        
        device_layout.addWidget(QLabel("平台:"), 1, 0)
        self.combo_stage = QComboBox()
        self.combo_stage.addItems(["SmartAct", "NewPort", "Nators", "Simulated"])
        self.setup_combo_centered(self.combo_stage)
        device_layout.addWidget(self.combo_stage, 1, 1)
        
        self.btn_connect_stage = QPushButton("连接")
        device_layout.addWidget(self.btn_connect_stage, 1, 2)
        
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # --- B. 位移台控制 ---
        stage_group = QGroupBox("2. 位移台控制")
        stage_layout = QVBoxLayout()
        self.stage_widget = StageControlWidget() # 实例化
        stage_layout.addWidget(self.stage_widget)
        stage_group.setLayout(stage_layout)
        layout.addWidget(stage_group)

        # --- C. 相机参数 ---
        cam_group = QGroupBox("3. 相机参数")
        cam_layout = QGridLayout()
        
        cam_layout.addWidget(QLabel("曝光 (ms):"), 0, 0)
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setRange(0.001, 10000); self.exposure_spin.setValue(0.1); self.exposure_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        cam_layout.addWidget(self.exposure_spin, 0, 1)
        
        cam_layout.addWidget(QLabel("波长 (nm):"), 1, 0)
        self.wavelength_spin = QDoubleSpinBox()
        self.wavelength_spin.setRange(200, 2000); self.wavelength_spin.setValue(632.8); self.wavelength_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        cam_layout.addWidget(self.wavelength_spin, 1, 1)    
        
        cam_layout.addWidget(QLabel("采样:"), 2, 0)
        self.combo_sampling = QComboBox()
        self.combo_sampling.addItems(["1x1", "2x2", "4x4", "8X8"])
        self.setup_combo_centered(self.combo_sampling)
        cam_layout.addWidget(self.combo_sampling, 2, 1)
        
        cam_group.setLayout(cam_layout)
        layout.addWidget(cam_group)

        # --- D. 阵列与偏移 ---
        roi_group = QGroupBox("4. 阵列与偏移 (ROI)")
        roi_layout = QGridLayout()
        
        roi_layout.addWidget(QLabel("阵列 W/H:"), 0, 0)
        roi_size = QHBoxLayout()
        self.roi_w = QSpinBox(); self.roi_w.setRange(1, 4096); self.roi_w.setValue(1024); self.roi_w.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.roi_h = QSpinBox(); self.roi_h.setRange(1, 4096); self.roi_h.setValue(1024); self.roi_h.setAlignment(Qt.AlignmentFlag.AlignRight)
        roi_size.addWidget(self.roi_w); roi_size.addWidget(QLabel("x")); roi_size.addWidget(self.roi_h)
        roi_layout.addLayout(roi_size, 0, 1)

        roi_layout.addWidget(QLabel("偏移 X/Y:"), 1, 0)
        offset_layout = QHBoxLayout()
        self.off_x = QSpinBox(); self.off_x.setRange(-2000, 2000); self.off_x.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.off_y = QSpinBox(); self.off_y.setRange(-2000, 2000); self.off_y.setAlignment(Qt.AlignmentFlag.AlignRight)
        offset_layout.addWidget(self.off_x); offset_layout.addWidget(self.off_y)
        roi_layout.addLayout(offset_layout, 1, 1)
        
        self.btn_center = QPushButton("获取中心并计算偏移")
        roi_layout.addWidget(self.btn_center, 2, 0, 1, 2)
        
        roi_group.setLayout(roi_layout)
        layout.addWidget(roi_group)

        layout.addStretch()

    def setup_scan_tab(self):
        self.tab_scan = QWidget()
        layout = QVBoxLayout(self.tab_scan)
        group = QGroupBox("自动扫描设置")
        form = QFormLayout()
        
        # 保存路径
        h_path = QHBoxLayout()
        self.save_dir_edit = QLineEdit("data")
        self.btn_browse = QPushButton("...")
        h_path.addWidget(self.save_dir_edit); h_path.addWidget(self.btn_browse)
        form.addRow("目录:", h_path)
        
        # 模式
        self.combo_scan_mode = QComboBox()
        self.combo_scan_mode.addItems(["矩形", "圆形", "螺旋"])
        self.setup_combo_centered(self.combo_scan_mode)
        form.addRow("模式:", self.combo_scan_mode)

        # 参数 (右对齐)
        self.scan_range = QLineEdit("0.2, 0.2"); self.scan_range.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("范围(mm):", self.scan_range)
        
        self.scan_step = QLineEdit("0.1"); self.scan_step.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("步长(mm):", self.scan_step)
        
        self.scan_points = QSpinBox(); self.scan_points.setRange(1, 10000); self.scan_points.setValue(100); self.scan_points.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("点数:", self.scan_points)
        
        self.btn_show_path = QPushButton("显示路径")
        form.addRow(self.btn_show_path) 
        
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()

    def create_photon_panel(self):
        group = QGroupBox("光子数监测")
        layout = QFormLayout()
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.line_cam_max = QLineEdit("65535") 
        self.line_cam_max.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addRow("相机饱和:", self.line_cam_max)

        self.line_global_max = QLineEdit("0")
        self.line_global_max.setReadOnly(True)
        self.line_global_max.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.line_global_max.setStyleSheet("color: red; font-weight: bold; background: #f0f0f0;")
        layout.addRow("全图Max:", self.line_global_max)

        self.line_mouse_val = QLineEdit("0")
        self.line_mouse_val.setReadOnly(True)
        self.line_mouse_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.line_mouse_val.setStyleSheet("color: blue; font-weight: bold; background: #f0f0f0;")
        layout.addRow("鼠标Val:", self.line_mouse_val)

        group.setLayout(layout)
        return group

    def create_big_action_buttons(self):
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(0, 5, 0, 5)
        
        self.btn_live = QPushButton("👁 观察")
        self.btn_live.setMinimumHeight(45)
        self.btn_live.setStyleSheet("background-color: #27ae60; color: white; border-radius: 5px; font-weight: bold;")

        self.btn_cap = QPushButton("🔴 采集")
        self.btn_cap.setMinimumHeight(45)
        self.btn_cap.setStyleSheet("background-color: #c0392b; color: white; border-radius: 5px; font-weight: bold;")

        self.btn_save = QPushButton("💾 保存")
        self.btn_save.setMinimumHeight(45)
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; border-radius: 5px; font-weight: bold;")

        layout.addWidget(self.btn_live, 0, 0)
        layout.addWidget(self.btn_cap, 0, 1)
        layout.addWidget(self.btn_save, 0, 2)
        
        aux = QHBoxLayout()
        self.chk_log = QCheckBox("Log")
        self.chk_mask = QCheckBox("Mask")
        aux.addWidget(self.chk_log)
        aux.addWidget(self.chk_mask)
        layout.addLayout(aux, 1, 0, 1, 3)
        return container

    def create_log_panel(self):
        w = QWidget()
        l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
        l.addWidget(QLabel("系统日志:"))
        self.txt_log = QTextEdit(); self.txt_log.setReadOnly(True); self.txt_log.setFixedHeight(100)
        l.addWidget(self.txt_log)
        return w

    def log(self, msg):
        self.txt_log.append(f">> {msg}")
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernUI()
    window.show()
    sys.exit(app.exec())
