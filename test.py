import imagingcontrol4 as ic4
import numpy as np
import cv2


class NumpyCaptureListener(ic4.QueueSinkListener):
    def __init__(self):
        self.latest_frame = None  # 存储最新帧的NumPy数组

    def sink_connected(self, sink: ic4.QueueSink, image_type: ic4.ImageType, min_buffers_required: int) -> bool:
        return True  # 接受所有图像格式配置

    def frames_queued(self, sink: ic4.QueueSink):
        buffer = sink.pop_output_buffer()
        # 将图像数据转换为NumPy数组（假设像素格式为BGR8，与OpenCV兼容）
        np_array = buffer.numpy_wrap()
        self.latest_frame = np_array.copy()  # 必须复制数据，确保缓冲区释放后数据有效


def capture_and_display():
    ic4.Library.init()

    try:
        # 枚举并选择第一个可用设备
        device_list = ic4.DeviceEnum.devices()
        if not device_list:
            raise RuntimeError("未找到可用设备")
        dev_info = device_list[0]
        # print(f"正在连接设备: {dev_info.display_name}")

        # 创建设备并配置流
        grabber = ic4.Grabber()
        grabber.device_open(dev_info)
        grabber.device_property_map.get_value_()
        # 创建监听器并配置队列Sink
        listener = NumpyCaptureListener()
        sink = ic4.QueueSink(
            listener,
            [ic4.PixelFormat.Mono8],  # 指定BGR8格式，与OpenCV兼容
            max_output_buffers=1  # 仅保留最新帧
        )
        grabber.stream_setup(sink)

        # 启动采集
        print("开始采集（按 'q' 停止）...")
        while True:
            if listener.latest_frame is not None:
                # 使用OpenCV显示图像
                cv2.imshow("Camera Feed", listener.latest_frame)
                listener.latest_frame = None  # 清除已处理帧

            # 检测按键输入（每1毫秒检查一次）
            key = cv2.waitKey(1)
            if key == ord('q'):  # 按 'q' 退出
                break

    except Exception as e:
        print(f"错误发生: {e}")
    finally:
        # 清理资源
        if 'grabber' in locals():
            grabber.stream_stop()
            grabber.device_close()
        cv2.destroyAllWindows()  # 关闭所有OpenCV窗口
        ic4.Library.exit()


if __name__ == "__main__":
    capture_and_display()