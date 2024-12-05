from PIL import Image
from pyueye import ueye
# import cv2
from PyQt5 import QtGui
from PyQt5.QtGui import QImage, QImageReader
import numpy as np
from pylablib.devices import uc480



class Camera:
    def __init__(self, exposure: float = 1, width: int = 1024, height: int = 1024, AOI: bool = True):
        # set default parameters
        self.hCam = ueye.HIDS(0)  # 0: first available camera;  1-254: The camera with the specified camera ID
        self.pcImageMemory = ueye.c_mem_p()
        self.MemID = ueye.int()  # 定义一个类型，未初始化值，已分配储存空间，未来传入函数后可以接收返回值
        self.rectAOI = ueye.IS_RECT()
        self.pitch = ueye.INT()
        self.nBitsPerPixel = ueye.INT(8)  # 24: bits per pixel for color mode; take 8 bits per pixel for monochrome
        self.nRet_initial = -1
        self.setAOI = AOI
        self.nRet_setAOI = -1
        self.array_size = 1024
        self.array_center_local = [int(width / 2 - 1), int(height / 2 - 1)]
        self.array_center_global = [int(3088 / 2 - 1), int(2076 / 2 - 1)]
        self.mouseposition = [0, 0]
        self.width = ueye.int(width)
        self.height = ueye.int(height)
        self.Exposure = exposure
        self.data = []

    def camera_open(self, m):
        self.hCam = ueye.HIDS(m)
        self.nRet_initial = ueye.is_InitCamera(self.hCam, None)
        return self.nRet_initial

    def set_paramerters(self):
        ueye.is_SetDisplayMode(self.hCam, ueye.IS_SET_DM_DIB)
        self.rectAOI.s32X = ueye.int(int(self.array_center_global[0] - self.array_size / 2 - 1))
        self.rectAOI.s32Y = ueye.int(int(self.array_center_global[1] - self.array_size / 2 - 1))
        self.rectAOI.s32Width = self.width
        self.rectAOI.s32Height = self.height
        if self.setAOI == True:
            self.nRet_setAOI = ueye.is_AOI(self.hCam, ueye.IS_AOI_IMAGE_SET_AOI, self.rectAOI,
                                           ueye.sizeof(self.rectAOI))
        ueye.is_AllocImageMem(self.hCam, self.width, self.height, self.nBitsPerPixel, self.pcImageMemory, self.MemID)
        # Makes the specified image memory the active memory
        ueye.is_SetImageMem(self.hCam, self.pcImageMemory, self.MemID)
        ueye.is_SetColorMode(self.hCam, ueye.IS_CM_SENSOR_RAW8)
        # Set the desired color mode
        # ueye.is_CaptureVideo(self.hCam, ueye.IS_DONT_WAIT)
        ueye.is_InquireImageMem(self.hCam, self.pcImageMemory, self.MemID, self.width, self.height,
                                self.nBitsPerPixel,
                                self.pitch)
        ueye.is_PixelClock(self.hCam, ueye.IS_PIXELCLOCK_CMD_SET, ueye.DOUBLE(400),
                           ueye.sizeof(ueye.DOUBLE(400)))
        ueye.is_Exposure(self.hCam, ueye.IS_EXPOSURE_CMD_SET_EXPOSURE, ueye.DOUBLE(self.Exposure),
                         ueye.sizeof(ueye.DOUBLE(self.Exposure)))
        ueye.is_SetFrameRate(self.hCam, ueye.DOUBLE(20), ueye.DOUBLE(45))

    def generate_thumbnail(self):
        thumbnail = np.zeros((104, 154, 3), np.uint8)
        thumbnail[:] = [201, 201, 205]
        top_left = [self.array_center_global[0] - int(self.array_size / 2 - 1),
                    self.array_center_global[1] - int(self.array_size / 2 - 1)]
        bot_right = [self.array_center_global[0] + int(self.array_size / 2 - 1),
                     self.array_center_global[1] + int(self.array_size / 2 - 1)]
        cv2.rectangle(thumbnail, (int(top_left[0] / 20), int(top_left[1] / 20)),
                      (int(bot_right[0] / 20), int(bot_right[1] / 20)), (255, 0, 0), -1)
        show_1 = QtGui.QImage(thumbnail.data, thumbnail.shape[1], thumbnail.shape[0], thumbnail.shape[1] * 3,
                              QtGui.QImage.Format.Format_BGR888)
        return show_1

    def capture_video(self):
        return ueye.is_CaptureVideo(self.hCam, ueye.IS_DONT_WAIT)

    def stop_video(self):
        return ueye.is_StopLiveVideo(self.hCam, ueye.IS_DONT_WAIT)

    def capture_picture(self):
        return ueye.is_FreezeVideo(self.hCam, ueye.IS_DONT_WAIT)

    def get_data(self):
        array = ueye.get_data(self.pcImageMemory, self.width, self.height, self.nBitsPerPixel, self.pitch, copy=False)
        self.data = np.reshape(array, (self.height.value, self.width.value))
        # return self.data

    def exit(self):
        ueye.is_FreeImageMem(self.hCam, self.pcImageMemory, self.MemID)
        ret = None
        if self.hCam is not None:
            ret = ueye.is_ExitCamera(self.hCam)
        else:
            print("Camera isn't open!")
        if ret == ueye.IS_SUCCESS:
            self.hCam = None
        return ret

class IDS:
    def __init__(self):
        
        # self.cam = uc480.UC480Camera(backend='ueye')
        print((uc480.list_cameras(backend='ueye')))
        # print(uc480.UC480Camera.get_all_color_modes())
        cam_id = uc480.list_cameras(backend='ueye')[0][0]
        self.cam = uc480.UC480Camera(cam_id, backend='ueye')

    def set_pixel_rate(self, pixel_rate):
        self.cam.set_pixel_rate(pixel_rate)

    def get_color_mode(self):
        return self.get_color_mode()

    def set_color_mode(self, color_mode):
        self.cam.set_color_mode(color_mode)

    def set_ex_time(self,ex_time):
        self.cam.set_exposure(ex_time)

    def snap(self):
        image = self.cam.snap()
        return image

    def start_acquisition(self):
        self.cam.start_acquisition()

    def wait_for_frame(self, nframes=10):
        self.cam.wait_for_frame(nframes=nframes)

    def read_newest_image(self):
        image = self.cam.read_newest_image()
        if image is None:
            self.wait_for_frame(1)
            image = self.cam.read_newest_image()

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
            print(f"曝光时间设置为 {exposure_time*1e3} 毫秒")
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
                frame_rate = 1/self.camera.AcquisitionFrameRate.Value
                print(f"当前帧率为 {1/frame_rate} FPS")
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
