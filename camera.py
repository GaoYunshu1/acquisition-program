from PIL import Image
from pyueye import ueye
# import cv2
from PyQt5 import QtGui
from PyQt5.QtGui import QImage, QImageReader
import numpy as np
from pylablib.devices import uc480


class IDS:
    def __init__(self):

        # self.cam = uc480.UC480Camera(backend='ueye')
        print((uc480.list_cameras(backend='ueye')))
        # print(uc480.UC480Camera.get_all_color_modes())
        cam_id = uc480.list_cameras(backend='ueye')[0][0]
        self.cam = uc480.UC480Camera(cam_id, backend='ueye')

    def set_pixel_rate(self, pixel_rate):
        try:
            self.cam.set_pixel_rate(pixel_rate)
        except Exception as e:
            print(f'设置pixel rate失败：{e}')

    def get_color_mode(self):
        return self.get_color_mode()

    def set_color_mode(self, color_mode):
        try:
            self.cam.set_color_mode(color_mode)
        except Exception as e:
            print(f'IDS设置颜色模式错误：{e}')

    def set_ex_time(self, ex_time):
        try:
            self.cam.set_exposure(ex_time)
        except Exception as e:
            print(f'IDS曝光时间设置失败：{e}')

    def snap(self):
        image = self.cam.snap()
        return image

    def start_acquisition(self):
        try:
            self.cam.start_acquisition()
        except Exception as e:
            print(f'IDS开始获取图像失败：{e}')

    def wait_for_frame(self, nframes=10):
        self.cam.wait_for_frame(nframes=nframes)

    def read_newest_image(self):
        try:
            image = self.cam.read_newest_image()
            if image is None:
                self.wait_for_frame(1)
                image = self.cam.read_newest_image()
        except Exception as e:
            print(f'IDS获取图像失败：{e}')
        return image

    def get_frame_period(self):
        return self.cam.get_frame_period()


class Basler:
    def __init__(self):
        global pylon
        from pypylon import pylon
        # 创建相机对象并连接到第一个可用的相机
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        self.camera.Open()
        print(self.camera)

    def set_ex_time(self, exposure_time):
        """设置曝光时间，单位为微秒"""
        try:
            # 设置曝光时间
            self.camera.ExposureTime.Value = exposure_time * 1e6
            print(f"曝光时间设置为 {exposure_time * 1e3} 毫秒")
        except Exception as e:
            print(f"设置曝光时间失败: {e}")

    def start_acquisition(self):
        try:
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImages)
        except Exception as e:
            print(f"启动获取图像时发生错误: {e}")

    def read_newest_image(self):
        """获取一幅图像"""

        try:

            if self.camera.IsGrabbing():
                # 获取图像
                grab_result = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

                # 获取图像数据（图像转换为NumPy数组）
                image = grab_result.Array
                # print(image.shape, np.unravel_index(np.argmax(image,keepdims=True),image.shape), np.mean(image),np.sort(np.unique(image))[-2],np.sort(np.unique(image))[-3])

                return image

            else:
                print("相机未准备好获取图像")
                return None

        except Exception as e:
            print(f"获取图像时发生错误: {e}")
            return None

    def set_frame_rate(self, frame_rate: float):
        """设置相机的帧率"""
        if self.camera:
            try:
                self.camera.AcquisitionFrameRate.Value = frame_rate
                print(f"帧率已设置为 {frame_rate} FPS")
            except Exception as e:
                print(f"设置帧率失败: {e}")
        else:
            print("相机未正确初始化，无法设置帧率")

    def get_frame_period(self) -> float:
        """获取当前相机的帧率"""
        if self.camera:
            try:
                frame_rate = 1 / self.camera.AcquisitionFrameRate.Value
                print(f"当前帧率为 {1 / frame_rate} FPS")
                return frame_rate
            except Exception as e:
                print(f"获取帧率失败: {e}")
                return -1
        else:
            print("相机未正确初始化，无法获取帧率")
            return -1

    def set_image_format(self, pixel_format: str):
        """设置相机的图像格式（如 Mono8、RGB8 等）"""
        if self.camera:
            try:
                self.camera.PixelFormat.Value = pixel_format
                print(f"图像格式已设置为 {pixel_format}")
            except Exception as e:
                print(f"设置图像格式失败: {e}")
        else:
            print("相机未正确初始化，无法设置图像格式")

    def get_image_format(self) -> str:
        """获取当前相机的图像格式"""
        if self.camera:
            try:
                pixel_format = self.camera.PixelFormat.Value
                print(f"当前图像格式为 {pixel_format}")
                return pixel_format
            except Exception as e:
                print(f"获取图像格式失败: {e}")
                return ""
        else:
            print("相机未正确初始化，无法获取图像格式")
            return ""

    def close(self):
        """关闭相机连接"""
        self.camera.StopGrabbing()
        self.camera.Close()
        print("相机已关闭")


if __name__ == '__main__':
    # camera = Camera()
    # camera.set_paramerters()
    cam = Basler()
    cam.start_acquisition()
    cam.set_ex_time(405)
    cam.set_image_format('Mono12')
    cam.set_frame_rate(50)
    print(cam.read_newest_image())
    print(cam.get_image_format())
    print(cam.get_frame_period())
    cam.close()
    # cam.cam.set_exposure(0.022)
    # cam.set_pixel_rate(160000000)
    # print(cam.cam.get_pixel_rate())
    # # cam.cam.set_trigger_mode('int')
    # # cam.cam.set_frame_period(0.1)
    # print(cam.cam.get_detector_size())
    # cam.start_acquisition()

    # print(cam.cam.acquisition_in_progress())
    # cam.wait_for_frame(nframes=10)
    # print(cam.cam.get_frame_timings())
    # image = cam.read_newest_image()
    # print(image.dtype)
    # image = Image.fromarray(image)
    # image.show()
    # image.save('./test.png')

    # # print(len(image))
    # cam.cam.close()
