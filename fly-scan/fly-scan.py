from threading import Thread, Event
from queue import Queue
import time
from time import sleep
from copy import deepcopy
from motion_controller import xps
from camera import PCOCamera
from threading import Thread
from PIL import Image
import os 
import numpy as np
import h5py
import sys


class SoftTriggerFlyScan:
    def __init__(self, motion, camera, scan_params=None):
        self.motion = motion       # 运动控制器
        self.camera = camera       # 相机对象
        if scan_params is not None:
            self.scan_params = scan_params
        else:
            self.scan_params = {
            'xrange': (14, 16),      # (mm)
            'y_ori': 0.5,             # y轴起始位置
            'ystep': 0.1,           # 步长 (mm)
            'sampling_interval': 0.3,  # 采样间隔 (秒)
            'scan_num': 20
        }
        print(self.scan_params)
        self._generate_path()

    def _generate_path(self):
        """生成连续蛇形路径"""
        self.x_pos = [self.scan_params['xrange'][0]]
        offset = self.scan_params['y_ori']
        self.y_pos = [offset]
        for i in range(self.scan_params['scan_num']):
            if i % 2 == 0:
                self.x_pos.append(self.scan_params['xrange'][1])
                self.y_pos.append((i+1) * self.scan_params['ystep'] + offset)
            else:
                self.x_pos.append(self.scan_params['xrange'][0])
                self.y_pos.append((i+1) * self.scan_params['ystep'] + offset)

    def _move_and_wait(self, pos, axis):
        """异步移动并在后台等待完成"""
        try:
            move_thread = Thread(target=self.motion.move_by, args=(pos, axis, False))
            move_thread.start()
        except Exception as e:
            print(e)
        return move_thread
    

    def run_scan(self):
        images = []
        try:
        # 初始化位置，异步移动并等待完成
            self._move_and_wait(self.y_pos[0], 1).join()
            sleep(1)
            self._move_and_wait(self.x_pos[0], 0).join()
        except Exception as e:
            print(e)
            sys.exit(1)


        for i in range(1, len(self.y_pos)):
            # 异步移动X轴
            x_thread = self._move_and_wait(self.x_pos[i], 0)
            print('Fly-scan!')
            
            # 在X轴移动过程中采集图像
            while x_thread.is_alive():
                start = time.time()
                image = deepcopy(self.camera.read_newest_image())
                # print(image)
                if image is not None:
                    images.append(image)
                # print('image')

                time.sleep(max(self.scan_params['sampling_interval'] + start - time.time(), 0.001))
            
            # 确保X轴线程完成
            x_thread.join()
            
            # 移动Y轴并等待完成（可根据需要改为异步）
            y_thread = self._move_and_wait(self.y_pos[i], 1)
            y_thread.join()

        return images

def auto_exposure(cam, lower_bound, upper_bound, 
                 max_iter=20, step_scale=1.2, 
                 min_exposure=1e-6, max_exposure=10.0):
    """
    自动调节相机曝光时间，使图像最大强度值落入指定区间
    
    参数：
        cam: 相机对象（需实现 get_exposure/set_exposure/read_newest_image）
        lower_bound: 目标强度下限（像素值）
        upper_bound: 目标强度上限（像素值）
        max_iter: 最大迭代次数（默认20）
        step_scale: 动态调整比例（默认1.5倍）
        min_exposure: 硬件最小曝光时间（秒，默认1μs）
        max_exposure: 硬件最大曝光时间（秒，默认10秒）
        
    返回：
        (success, final_exposure, final_max)
        success: 是否成功调节
        final_exposure: 最终使用的曝光时间
        final_max: 最终图像的最大强度值
    """
    current_exposure = cam.get_ex_time()

    
    for _ in range(max_iter):
        # 设置并获取当前曝光时间
        current_exposure = max(min(current_exposure, max_exposure), min_exposure)
        cam.cam.stop_acquisition()
        cam.set_ex_time(current_exposure)
        cam.start_acquisition()
        print(current_exposure)
        
        # 采集图像并获取最大值
        img = cam.read_newest_image()
        if img is None:
            raise RuntimeError("无法从相机获取图像")
        current_max = img.max()
        
        # 检查是否满足条件
        if lower_bound <= current_max <= upper_bound:
            return (True, current_exposure, current_max)
            
        # 动态调整策略
        if current_max < lower_bound:  # 曝光不足
            new_exposure = current_exposure * step_scale
            # 当接近上限时降低调整幅度
            if new_exposure > 0.8 * max_exposure:
                new_exposure = (current_exposure + max_exposure) / 2
        else:  # 曝光过度
            new_exposure = current_exposure / step_scale
            # 当接近下限时降低调整幅度
            if new_exposure < 2 * min_exposure:
                new_exposure = (current_exposure + min_exposure) / 2
                
        # 应用调整后的曝光时间
        current_exposure = new_exposure
        
    # 超过最大迭代次数仍未满足条件
    return (False, current_exposure, current_max)

def save_as_compound_dataset(filename, data_list):
    with h5py.File(filename, 'w') as f:
        f.create_dataset('dps', data=data_list)
    

if __name__ == '__main__':
    save_path = 'data'
    motion = xps()
    motion.init_groups(['Group2', 'Group1'])
    motion.set_velocity('Group2.Pos', 0.5)

    camera = PCOCamera()
    camera.start_acquisition()

    # print(camera.cam.get_frame_period())
    # auto_exposure(camera, 3100, 3850)
    # # camera.cam.set_frame_period()

    camera.cam.stop_acquisition()
    camera.set_ex_time(0.0045)
    camera.start_acquisition()
    image = camera.read_newest_image()
    print(np.max(image))
    scan_params={
            'xrange': (10.5, 12.5),      # (mm)
            'y_ori': 11.2,             # y轴起始位置
            'ystep': 0.1,           # 步长 (mm)
            'sampling_interval': 0.3,  # 采样间隔 (秒)
            'scan_num': 3
        }
    fc = SoftTriggerFlyScan(motion, camera, scan_params)

    # print(fc.x_pos)
    # print(fc.y_pos)
    images = fc.run_scan()
    print('start saving')

    # a = [np.random.randint(0, 4095,(5120,5120)).astype(np.uint16) for i in range(102)]
    # print(len(a))
    # aa = np.array(images, dtype=np.uint16)
    # print(aa.shape, aa.dtype)

    save_as_compound_dataset('chip_ph_4.5_0.5.h5_s', images)


    # for i, image in enumerate(images):
    #     image_ = Image.fromarray(image)
    #     if not os.path.exists(save_path):
    #         os.makedirs(save_path)

    #     save_path_in = os.path.join(save_path, f'{i}.png')
    #     print(save_path_in)
    #     image_.save(save_path_in)
        
    print('finish')
    # print(images)


