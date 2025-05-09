import os
import time
from audioop import error
from time import sleep
from PyQt5.QtWidgets import QMainWindow, QApplication, QGraphicsScene
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QTimer, Qt
import sys

from gui_simple import Ui_MainWindow
from camera import IDS, Ham
from VSY import VSyCamera as vsy
from VSY import VsyGvspPixelType
from motion_controller import xps, smartact, nators
import numpy as np
from PIL import Image
from Scanner import Scanner
from copy import copy, deepcopy
from typing import Union, List, Tuple


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.camera = None
        self.motion_controller = None
        self.photon = 20
        self.x_offset = 0
        self.y_offset = 0
        self.xpixel_num = 1024
        self.ypixel_num = 1024
        self.ex_time = 0.36
        self.save_path = None
        self.step = None
        self.scan_num = None
        self.subimage_num = None
        self.xmotion = None
        self.y_motion = None
        self.motion = None
        self.pixel_type = None
        self.scene = QGraphicsScene()  # 创建画布
        self.ui.image.setScene(self.scene)  # 把画布添加到窗口
        self.image_timer = None
        self.photon_timer = None
        self.frame_period = 0
        self.cur_point = 0
        self.x = []
        self.y = []
        self.abs_x = []
        self.abs_y = []
        self.final_pos = None
        self.center = None

        # 这里添加事件响应
        self.ui.carmera_init.clicked.connect(self.init_camera)
        self.ui.init_motion_ctr.clicked.connect(self.init_mtn_ctr)
        self.ui.photon.returnPressed.connect(self.set_photon)
        self.ui.xbias.returnPressed.connect(self.set_xbias)
        self.ui.ybias.returnPressed.connect(self.set_ybias)
        self.ui.xpixel_num.returnPressed.connect(self.set_xpixel_num)
        self.ui.ypixel_num.returnPressed.connect(self.set_ypixel_num)
        self.ui.ex_time.returnPressed.connect(self.set_ex_time)
        self.ui.save_path.returnPressed.connect(self.set_save_path)
        self.ui.step.returnPressed.connect(self.set_step)
        self.ui.scan_num.returnPressed.connect(self.set_scan_num)
        self.ui.xmotion.returnPressed.connect(self.set_xmotion)
        self.ui.y_motion.returnPressed.connect(self.set_ymotion)
        self.ui.log.clicked.connect(self.set_log)
        self.ui.save_image.clicked.connect(self.save_dark)

    def init_camera(self):

        if self.ui.carmera_init.text() == '相机初始化':

            camera_flag = False
            if self.ui.select_cam.currentText() == 'IDS':
                # IDS
                try:
                    self.camera = IDS()
                    self.camera.set_pixel_rate(16e7)
                    self.camera.set_color_mode('mono12')
                    self.camera.start_acquisition()
                    self.camera.wait_for_frame(2)
                    self.pixel_type = 'mono12'
                    camera_flag = True
                except Exception as e:
                    print(f'启动IDS失败:{e}')
            # print(4)
            # elif self.ui.select_cam.currentText() == 'Basler':
            #     try:
            #         self.camera = Basler()
            #         self.camera.set_image_format('Mono12p')
            #         self.pixel_type = 'mono12'
            #         camera_flag = True
            #     except Exception as e:
            #         print(f'启动Basler失败:{e}')

            elif self.ui.select_cam.currentText() == 'VSY':
                try:
                    self.camera = vsy()
                    self.camera.set_pixel_format(VsyGvspPixelType.PixelType_Gvsp_Mono16)
                    self.pixel_type = 'mono16'
                    camera_flag = True
                except Exception as e:
                    print(f'启动VSY失败:{e}')

            # elif self.ui.select_cam.currentText() == 'ImagingSource':
            #     try:
            #         self.camera = IC4Camera(1024, 1024)
            #         self.pixel_type = 'mono16'
            #         camera_flag = True
            #     except Exception as e:
            #         print(f'启动IC4失败:{e}')
            elif self.ui.select_cam.currentText() == 'Ham':
                try:
                    self.camera = Ham()
                    camera_flag = True  # 此项必须
                    self.pixel_type = 'mono16'  # 此项必须
                except Exception as e:
                    print(f'启动Ham失败:{e}')

            if camera_flag:
                self.camera.start_acquisition()
                sleep(1)  # 部分相机启动需要时间，不能立刻获取图像
                # self.camera.set_frame_rate()
                self.frame_period = self.camera.get_frame_period()
                self.frame_period = int(self.frame_period * 2000)  # VSY有问题，只能读最旧图像，必须同步刷新
                print(self.frame_period)
                self.image_timer = QTimer(self)
                self.image_timer.timeout.connect(self.image_show)
                self.image_timer.start(self.frame_period)
                self.photon_timer = QTimer(self)
                self.photon_timer.timeout.connect(self.set_photon)
                self.photon_timer.start(1000)
                self.ui.carmera_init.setText('终止显示')
        else:
            self.image_timer.stop()
        # self.image_show()

    def init_mtn_ctr(self):
        if self.ui.init_motion_ctr.text() == '位移台初始化':
            # self.motion_controller = motion_ctr('192.168.254.254')
            motion = self.ui.select_motion.currentText()
            if motion == 'smartact':
                self.motion = smartact()

            elif motion == 'newportxps':
                self.motion = xps()
                self.motion.init_groups(['Group3', 'Group4'])

            elif motion == 'nators':
                self.motion = nators()
                self.motion.open_system()
            self.ui.init_motion_ctr.setText('开始扫描')
        elif self.ui.init_motion_ctr.text() == '开始扫描':
            self.check_path()
            self.generate_scan_point()
            self.scan()
            self.ui.init_motion_ctr.setText('终止位移台移动')
        else:
            self.ui.init_motion_ctr.setText('开始扫描')
            # self.motion.stop_all()

    def check_path(self):
        try:
            if self.save_path is None:
                self.save_path = 'data'
            if not os.path.exists(self.save_path):
                os.makedirs(self.save_path)
        except Exception as e:
            print(f'保存路径错误:{e}')

    def generate_scan_point(self):
        mode = self.ui.scan_mode.currentText()
        mode_mapping = {
            '矩形': 'rectangle',
            '圆形': 'round',
        }
        normalized_mode = mode_mapping.get(mode)
        scanner = Scanner(
            step=self.step,
            scan_num=self.scan_num,
            mode=normalized_mode
        )

        attributes = ['x', 'y', 'abs_x', 'abs_y', 'final_pos']

        def _smart_copy(value: Union[list, tuple]) -> Union[list, tuple]:
            """智能复制：list深拷贝，tuple直接引用（因其不可变）"""
            return deepcopy(value) if isinstance(value, list) else value

        for attr in attributes:
            original_value = getattr(scanner, attr)
            setattr(self, attr, _smart_copy(original_value))


        #     for i in range(self.scan_num):
        #         for j in range(self.scan_num):
        #             if j == 0 and i != 0:
        #                 self.x.append(self.step)
        #             else:
        #                 self.x.append(0)
        #             if self.x[-1] != 0:
        #                 self.y.append(0)
        #             elif i % 2 == 0:
        #                 self.y.append(self.step)
        #             else:
        #                 self.y.append(-self.step)
        # # print(self.x, self.y)
        # current_x, current_y = 0, 0
        # for dx, dy in zip(self.x, self.y):
        #     current_x += dx
        #     current_y += dy
        #     self.abs_x.append(current_x)
        #     self.abs_y.append(current_y)
        # self.final_pos = (current_x, current_y)
        # print(self.abs_x, self.abs_y)

    def scan(self):

        self.motion.move_by(self.x[self.cur_point], axis=0)
        sleep(0.2)
        self.motion.move_by(self.y[self.cur_point], axis=1)
        self.cur_point = self.cur_point + 1
        if self.camera:
            self.save_image(self.cur_point)
        if self.image_timer:
            QTimer.singleShot(100, self.start_display_next_scan)

    def start_display_next_scan(self):
        self.image_timer.start(self.frame_period)

        if self.cur_point < len(self.x):
            # print(2)
            QTimer.singleShot(300, self.scan)
        else:
            self.motion.move_by(-self.final_pos[0], axis=0)
            sleep(5)
            self.motion.move_by(-self.final_pos[1], axis=1)
        #     self.save_image()

    def image_show(self):
        # while time.time() - a < 20:
        self.scene.clear()
        # print(self.camera.data)
        image = self.camera.read_newest_image()
        # if self.center is None:
        #     self.center = self.find_center(image)
        image = self.crop_image(image)
        self.photon = np.max(image)
        # print(image.shape)
        if self.ui.log.text() == '正常显示':
            image = (4095 * np.log10(9 * image / 4095 + 1)).astype(np.uint16)
        # image = image.transpose((2, 0, 1))
        # print(np.max(image), image.shape)

        if self.pixel_type == 'mono12':
            frame = QImage(image << 4, image.shape[0], image.shape[1], QImage.Format_Grayscale16)
        elif self.pixel_type == 'mono16':
            frame = QImage(image, image.shape[0], image.shape[1], QImage.Format_Grayscale16)
        elif image.dtype == np.uint8:
            frame = QImage(image, image.shape[0], image.shape[1], QImage.Format_RGB888)
        # frame = frame.scaled(640, 640, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pix = QPixmap.fromImage(frame)

        # print(2)
        self.scene.addPixmap(pix)
        # print(3)
        # time.sleep(2)
        # print(time.time())

    def save_image(self, name=0):
        image_ = self.camera.read_newest_image()
        image_ = self.crop_image(image_)
        image_ = Image.fromarray(image_)
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

        save_path = os.path.join(self.save_path, f'{name}.png')
        print(save_path)
        image_.save(save_path)

    def save_dark(self):
        try:
            self.check_path()
            self.save_image(0)
        except Exception as e:
            print(e)

    def find_center(self, image):
        image = image - np.mean(image)
        image[image < 0] = 0
        image = image / np.max(image)

        total_intensity = np.sum(image)

        # 生成坐标网格
        y_indices, x_indices = np.indices(image.shape)

        # 计算加权质心坐标
        print(np.sum(x_indices * image))
        x_center = np.sum(x_indices * image) / total_intensity
        y_center = np.sum(y_indices * image) / total_intensity

        # 确保坐标在图像范围内
        x_center = np.clip(x_center, 0, image.shape[1] - 1)
        y_center = np.clip(y_center, 0, image.shape[0] - 1)

        return (int(round(x_center)), int(round(y_center)))

    def crop_image(self, image):
        if image.ndim == 2:
            width, height = image.shape
        else:
            width, height, _ = image.shape

        # x1 = self.center[0] - self.xpixel_num // 2  # + self.x_offset
        # y1 = self.center[1] - self.ypixel_num // 2  # + self.y_offset
        x1 = width // 2 - self.xpixel_num // 2
        y1 = height // 2 - self.ypixel_num // 2
        # print(x1, y1)
        x2 = x1 + self.xpixel_num
        y2 = y1 + self.ypixel_num

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(width, x2)
        y2 = min(height, y2)
        if image.ndim == 2:
            new_image = image[x1:x2, y1:y2]
        else:
            new_image = image[x1:x2, y1:y2, :]
        return new_image.astype(image.dtype)

    def set_xmotion(self):
        distance = self.ui.xmotion.text()
        distance = float(distance)
        # print(type(distance))
        self.motion.move_by(distance, axis=0)

    def set_ymotion(self):
        distance = self.ui.y_motion.text()
        distance = float(distance)
        # print(type(distance))
        self.motion.move_by(distance, axis=1)

    def set_photon(self):
        self.ui.photon.setText(str(self.photon))

    def set_xbias(self):
        self.x_offset = int(self.ui.xbias.text())
        print(self.x_offset)

    def set_ybias(self):
        self.y_offset = int(self.ui.ybias.text())

    def set_xpixel_num(self):
        self.xpixel_num = int(self.ui.xpixel_num.text())

    def set_ypixel_num(self):
        self.ypixel_num = int(self.ui.ypixel_num.text())

    def set_ex_time(self):
        # 文本框输入为：ms，传参为：S 
        self.ex_time = float(self.ui.ex_time.text()) / 1000
        self.camera.set_ex_time(self.ex_time)

    def set_save_path(self):
        self.save_path = self.ui.save_path.text()

    def set_step(self):
        self.step = float(self.ui.step.text())

    def set_scan_num(self):
        self.scan_num = int(self.ui.scan_num.text())

    def set_log(self):
        if self.ui.log.text() == 'log显示':
            self.ui.log.setText('正常显示')
            self.image_timer.stop()
            self.frame_period += 10
            self.image_timer.start(self.frame_period)
        else:
            self.ui.log.setText('log显示')
            self.image_timer.stop()
            self.frame_period -= 10
            self.image_timer.start(self.frame_period)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
