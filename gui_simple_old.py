# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'gui_simple.ui'
#
# Created by: PyQt5 UI code generator 5.15.9
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1097, 861)
        MainWindow.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.image = QtWidgets.QGraphicsView(self.centralwidget)
        self.image.setGeometry(QtCore.QRect(20, 20, 640, 640))
        self.image.setObjectName("image")
        self.carmera_init = QtWidgets.QPushButton(self.centralwidget)
        self.carmera_init.setGeometry(QtCore.QRect(740, 170, 141, 71))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.carmera_init.setFont(font)
        self.carmera_init.setIconSize(QtCore.QSize(30, 30))
        self.carmera_init.setObjectName("carmera_init")
        self.line = QtWidgets.QFrame(self.centralwidget)
        self.line.setGeometry(QtCore.QRect(680, 0, 16, 871))
        self.line.setFrameShape(QtWidgets.QFrame.VLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName("line")
        self.init_motion_ctr = QtWidgets.QPushButton(self.centralwidget)
        self.init_motion_ctr.setGeometry(QtCore.QRect(910, 170, 151, 71))
        font = QtGui.QFont()
        font.setPointSize(9)
        self.init_motion_ctr.setFont(font)
        self.init_motion_ctr.setObjectName("init_motion_ctr")
        self.layoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget.setGeometry(QtCore.QRect(20, 710, 211, 91))
        self.layoutWidget.setObjectName("layoutWidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.layoutWidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtWidgets.QLabel(self.layoutWidget)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.photon = QtWidgets.QLineEdit(self.layoutWidget)
        self.photon.setObjectName("photon")
        self.horizontalLayout.addWidget(self.photon)
        self.layoutWidget1 = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget1.setGeometry(QtCore.QRect(290, 710, 351, 91))
        self.layoutWidget1.setObjectName("layoutWidget1")
        self.horizontalLayout_11 = QtWidgets.QHBoxLayout(self.layoutWidget1)
        self.horizontalLayout_11.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_11.setObjectName("horizontalLayout_11")
        self.log = QtWidgets.QPushButton(self.layoutWidget1)
        self.log.setIconSize(QtCore.QSize(30, 30))
        self.log.setObjectName("log")
        self.horizontalLayout_11.addWidget(self.log)
        self.save_raw_data = QtWidgets.QPushButton(self.layoutWidget1)
        self.save_raw_data.setObjectName("save_raw_data")
        self.horizontalLayout_11.addWidget(self.save_raw_data)
        self.save_image = QtWidgets.QPushButton(self.layoutWidget1)
        self.save_image.setIconSize(QtCore.QSize(30, 30))
        self.save_image.setObjectName("save_image")
        self.horizontalLayout_11.addWidget(self.save_image)
        self.layoutWidget2 = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget2.setGeometry(QtCore.QRect(740, 650, 62, 151))
        self.layoutWidget2.setObjectName("layoutWidget2")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.layoutWidget2)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_4 = QtWidgets.QLabel(self.layoutWidget2)
        font = QtGui.QFont()
        font.setPointSize(9)
        self.label_4.setFont(font)
        self.label_4.setObjectName("label_4")
        self.verticalLayout.addWidget(self.label_4)
        self.label_5 = QtWidgets.QLabel(self.layoutWidget2)
        font = QtGui.QFont()
        font.setPointSize(9)
        self.label_5.setFont(font)
        self.label_5.setObjectName("label_5")
        self.verticalLayout.addWidget(self.label_5)
        self.label_8 = QtWidgets.QLabel(self.layoutWidget2)
        font = QtGui.QFont()
        font.setPointSize(9)
        self.label_8.setFont(font)
        self.label_8.setObjectName("label_8")
        self.verticalLayout.addWidget(self.label_8)
        self.label_9 = QtWidgets.QLabel(self.layoutWidget2)
        font = QtGui.QFont()
        font.setPointSize(9)
        self.label_9.setFont(font)
        self.label_9.setObjectName("label_9")
        self.verticalLayout.addWidget(self.label_9)
        self.layoutWidget3 = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget3.setGeometry(QtCore.QRect(820, 740, 241, 61))
        self.layoutWidget3.setObjectName("layoutWidget3")
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.layoutWidget3)
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.ex_time = QtWidgets.QLineEdit(self.layoutWidget3)
        self.ex_time.setObjectName("ex_time")
        self.verticalLayout_4.addWidget(self.ex_time)
        self.save_path = QtWidgets.QLineEdit(self.layoutWidget3)
        self.save_path.setObjectName("save_path")
        self.verticalLayout_4.addWidget(self.save_path)
        self.layoutWidget4 = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget4.setGeometry(QtCore.QRect(820, 650, 241, 91))
        self.layoutWidget4.setObjectName("layoutWidget4")
        self.verticalLayout_10 = QtWidgets.QVBoxLayout(self.layoutWidget4)
        self.verticalLayout_10.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_10.setObjectName("verticalLayout_10")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.label_6 = QtWidgets.QLabel(self.layoutWidget4)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.label_6.setFont(font)
        self.label_6.setObjectName("label_6")
        self.horizontalLayout_3.addWidget(self.label_6)
        self.xbias = QtWidgets.QLineEdit(self.layoutWidget4)
        self.xbias.setObjectName("xbias")
        self.horizontalLayout_3.addWidget(self.xbias)
        self.label_7 = QtWidgets.QLabel(self.layoutWidget4)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.label_7.setFont(font)
        self.label_7.setObjectName("label_7")
        self.horizontalLayout_3.addWidget(self.label_7)
        self.ybias = QtWidgets.QLineEdit(self.layoutWidget4)
        self.ybias.setObjectName("ybias")
        self.horizontalLayout_3.addWidget(self.ybias)
        self.verticalLayout_10.addLayout(self.horizontalLayout_3)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.label_2 = QtWidgets.QLabel(self.layoutWidget4)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.label_2.setFont(font)
        self.label_2.setObjectName("label_2")
        self.horizontalLayout_2.addWidget(self.label_2)
        self.xpixel_num = QtWidgets.QLineEdit(self.layoutWidget4)
        self.xpixel_num.setObjectName("xpixel_num")
        self.horizontalLayout_2.addWidget(self.xpixel_num)
        self.label_3 = QtWidgets.QLabel(self.layoutWidget4)
        font = QtGui.QFont()
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.label_3.setFont(font)
        self.label_3.setObjectName("label_3")
        self.horizontalLayout_2.addWidget(self.label_3)
        self.ypixel_num = QtWidgets.QLineEdit(self.layoutWidget4)
        self.ypixel_num.setObjectName("ypixel_num")
        self.horizontalLayout_2.addWidget(self.ypixel_num)
        self.verticalLayout_10.addLayout(self.horizontalLayout_2)
        self.layoutWidget5 = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget5.setGeometry(QtCore.QRect(900, 290, 101, 51))
        self.layoutWidget5.setObjectName("layoutWidget5")
        self.verticalLayout_11 = QtWidgets.QVBoxLayout(self.layoutWidget5)
        self.verticalLayout_11.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_11.setObjectName("verticalLayout_11")
        self.xmotion = QtWidgets.QLineEdit(self.layoutWidget5)
        self.xmotion.setObjectName("xmotion")
        self.verticalLayout_11.addWidget(self.xmotion)
        self.y_motion = QtWidgets.QLineEdit(self.layoutWidget5)
        self.y_motion.setObjectName("y_motion")
        self.verticalLayout_11.addWidget(self.y_motion)
        self.layoutWidget6 = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget6.setGeometry(QtCore.QRect(790, 290, 91, 51))
        self.layoutWidget6.setObjectName("layoutWidget6")
        self.verticalLayout_12 = QtWidgets.QVBoxLayout(self.layoutWidget6)
        self.verticalLayout_12.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_12.setObjectName("verticalLayout_12")
        self.label_23 = QtWidgets.QLabel(self.layoutWidget6)
        self.label_23.setObjectName("label_23")
        self.verticalLayout_12.addWidget(self.label_23)
        self.label_24 = QtWidgets.QLabel(self.layoutWidget6)
        self.label_24.setObjectName("label_24")
        self.verticalLayout_12.addWidget(self.label_24)
        self.layoutWidget7 = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget7.setGeometry(QtCore.QRect(790, 370, 223, 251))
        self.layoutWidget7.setObjectName("layoutWidget7")
        self.horizontalLayout_12 = QtWidgets.QHBoxLayout(self.layoutWidget7)
        self.horizontalLayout_12.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_12.setObjectName("horizontalLayout_12")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.label_13 = QtWidgets.QLabel(self.layoutWidget7)
        self.label_13.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.label_13.setAlignment(QtCore.Qt.AlignCenter)
        self.label_13.setObjectName("label_13")
        self.verticalLayout_3.addWidget(self.label_13)
        self.label_11 = QtWidgets.QLabel(self.layoutWidget7)
        self.label_11.setAlignment(QtCore.Qt.AlignCenter)
        self.label_11.setObjectName("label_11")
        self.verticalLayout_3.addWidget(self.label_11)
        self.label_12 = QtWidgets.QLabel(self.layoutWidget7)
        self.label_12.setAlignment(QtCore.Qt.AlignCenter)
        self.label_12.setObjectName("label_12")
        self.verticalLayout_3.addWidget(self.label_12)
        self.horizontalLayout_12.addLayout(self.verticalLayout_3)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setSizeConstraint(QtWidgets.QLayout.SetMaximumSize)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.scan_mode = QtWidgets.QComboBox(self.layoutWidget7)
        self.scan_mode.setMinimumSize(QtCore.QSize(0, 35))
        self.scan_mode.setObjectName("scan_mode")
        self.scan_mode.addItem("")
        self.verticalLayout_2.addWidget(self.scan_mode)
        self.step = QtWidgets.QLineEdit(self.layoutWidget7)
        self.step.setMinimumSize(QtCore.QSize(0, 35))
        self.step.setObjectName("step")
        self.verticalLayout_2.addWidget(self.step)
        self.scan_num = QtWidgets.QLineEdit(self.layoutWidget7)
        self.scan_num.setMinimumSize(QtCore.QSize(0, 35))
        self.scan_num.setObjectName("scan_num")
        self.verticalLayout_2.addWidget(self.scan_num)
        self.horizontalLayout_12.addLayout(self.verticalLayout_2)
        self.layoutWidget8 = QtWidgets.QWidget(self.centralwidget)
        self.layoutWidget8.setGeometry(QtCore.QRect(720, 60, 361, 81))
        self.layoutWidget8.setObjectName("layoutWidget8")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout(self.layoutWidget8)
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout()
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.label_15 = QtWidgets.QLabel(self.layoutWidget8)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.label_15.setFont(font)
        self.label_15.setAlignment(QtCore.Qt.AlignCenter)
        self.label_15.setObjectName("label_15")
        self.verticalLayout_5.addWidget(self.label_15)
        self.select_cam = QtWidgets.QComboBox(self.layoutWidget8)
        self.select_cam.setMinimumSize(QtCore.QSize(0, 35))
        self.select_cam.setObjectName("select_cam")
        self.select_cam.addItem("")
        self.verticalLayout_5.addWidget(self.select_cam)
        self.horizontalLayout_4.addLayout(self.verticalLayout_5)
        self.verticalLayout_6 = QtWidgets.QVBoxLayout()
        self.verticalLayout_6.setObjectName("verticalLayout_6")
        self.label_16 = QtWidgets.QLabel(self.layoutWidget8)
        font = QtGui.QFont()
        font.setPointSize(11)
        self.label_16.setFont(font)
        self.label_16.setAlignment(QtCore.Qt.AlignCenter)
        self.label_16.setObjectName("label_16")
        self.verticalLayout_6.addWidget(self.label_16)
        self.select_motion = QtWidgets.QComboBox(self.layoutWidget8)
        self.select_motion.setMinimumSize(QtCore.QSize(0, 35))
        self.select_motion.setObjectName("select_motion")
        self.select_motion.addItem("")
        self.select_motion.addItem("")
        self.verticalLayout_6.addWidget(self.select_motion)
        self.horizontalLayout_4.addLayout(self.verticalLayout_6)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1097, 26))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.carmera_init.setText(_translate("MainWindow", "相机初始化"))
        self.init_motion_ctr.setText(_translate("MainWindow", "位移台初始化"))
        self.label.setText(_translate("MainWindow", "最大光子数"))
        self.photon.setText(_translate("MainWindow", "20"))
        self.log.setText(_translate("MainWindow", "log显示"))
        self.save_raw_data.setText(_translate("MainWindow", "保存原始数据"))
        self.save_image.setText(_translate("MainWindow", "保存图片"))
        self.label_4.setText(_translate("MainWindow", "像素偏移"))
        self.label_5.setText(_translate("MainWindow", "像素数量"))
        self.label_8.setText(_translate("MainWindow", "曝光时间"))
        self.label_9.setText(_translate("MainWindow", "保存名称"))
        self.label_6.setText(_translate("MainWindow", "x"))
        self.label_7.setText(_translate("MainWindow", "Y"))
        self.label_2.setText(_translate("MainWindow", "x"))
        self.xpixel_num.setText(_translate("MainWindow", "2048"))
        self.label_3.setText(_translate("MainWindow", "Y"))
        self.ypixel_num.setText(_translate("MainWindow", "2048"))
        self.label_23.setText(_translate("MainWindow", "X轴位移(mm)"))
        self.label_24.setText(_translate("MainWindow", "Y轴位移(mm)"))
        self.label_13.setText(_translate("MainWindow", "扫描方式"))
        self.label_11.setText(_translate("MainWindow", "步长(mm)"))
        self.label_12.setText(_translate("MainWindow", "扫描次数"))
        self.scan_mode.setItemText(0, _translate("MainWindow", "矩形"))
        self.label_15.setText(_translate("MainWindow", "相机"))
        self.select_cam.setItemText(0, _translate("MainWindow", "IDS"))
    
        self.label_16.setText(_translate("MainWindow", "位移台"))
        self.select_motion.setItemText(0, _translate("MainWindow", "newportxps"))
        self.select_motion.setItemText(1, _translate("MainWindow", "smartact"))