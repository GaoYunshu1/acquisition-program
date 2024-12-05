from newportxps import NewportXPS
import time
from pylablib.devices import SmarAct

class smartact():
    def __init__(self):
        device = SmarAct.list_msc2_devices()
        if len(device) == 0:
            print('没有位移台')
        else:
            print(device[0])
            self.motion = SmarAct.MCS2(device[0])

    def home(self, axis=0):
        self.motion.home(axis=axis)

    def move_by(self, distance, axis=0):
        self.motion.move_by(distance, axis=axis)

    def stop_all(self):
        if self.motion.is_moving(axis=0):
            self.motion.stop(axis=0)
        if self.motion.is_moving(axis=1):
            self.motion.stop(axis=1)

class newport():
    def __init__(self):
        self.motion = NewportXPS('192.168.254.254')

    def home(self, axis=0):
        self.motion.home_group(group=f'group{axis}')

    def move_by(self, distance, axis=0):
        self.motion.move_stage(stage=f'group{axis}.pos', value=distance, relative=True)

if __name__ == "__main__":
    a = smartact()



# class motion_ctr():
#     def __init__(self, IP, username: str = 'Administrator', password: str = 'Administrator', port: int = 5001) -> None:
#         self.xps = NewportXPS(IP, username=username, password=password, port=port)
#         self.groups = []
#
#     def init_groups(self, groups: list = []):
#         if groups:
#             for i in groups:
#                 self.xps.initialize_group(i)
#                 time.sleep(0.5)
#                 self.xps.home_group(i)
#                 time.sleep(0.5)
#                 self.groups.append(i)
#         else:
#             print('No groups specified')
#
#     def init_all_groups(self):
#         self.xps.initialize_allgroups()
#
#     def kill_all_groups(self):
#         for group in self.groups:
#             self.xps.kill_group(group)
#
#     def move_stage(self, stage: str, position: int, relative: bool = False):
#         self.xps.move_stage(stage, position, relative)
#
#     def status_report(self):
#         return self.xps.status_report()
#
#     def set_velocity(self, stage: str = None, velocity: int = 2.5, acceleration: int = None, min_jerktime: int = None,
#                      max_jerktime: int = None):
#         self.xps.set_velocity(stage, velocity, acceleration, min_jerktime, max_jerktime)
