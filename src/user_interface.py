# -*- coding: utf-8 -*-

from datetime import datetime
from os import remove, rename, listdir, walk, _exit
from os.path import exists, isdir, isfile, abspath, splitext, basename
from shutil import rmtree, move
from threading import Thread
from PyQt5 import QtGui
from PyQt5.QtGui import QTextCursor, QTextDocument, QTextCharFormat
from PyQt5.QtWidgets import QWidget, QMessageBox, QFileDialog, QDesktopWidget, QGridLayout
from ui import UiForm
from PyQt5.QtCore import Qt
from seek_sort import SeekAndSort
from logger import MyLogs
from call_exe import Unlock
import resource_rc


class UserInterface(QWidget, UiForm):

    def __init__(self):
        super(UserInterface, self).__init__()
        self.resize(1920, 980)  # 设置主窗口大小
        self.center()  # 窗口居中显示
        self.setup_ui()  # 初始化UI
        self.input_dir = None  # 源文件目录
        self.output_dir = None  # 文件解锁后保存的目录
        self.sf_total = 0  # 源文件总数
        self.tf_total = 0  # 目标文件夹下所有文件个数
        self.success_total = 0  # 成功文件总数
        self.failed_total = 0  # 失败文件总数
        self.unlock_th = None  # 初始化一个变量后续赋值给解锁线程
        self.remove_th = None  # 初始化一个变量后续赋值给删除文件线程
        self.input_btn.clicked.connect(lambda: self.get_dir())  # 点击源文件目录按钮连接槽函数
        self.output_btn.clicked.connect(lambda: self.get_dir())  # 点击输出文件目录按钮连接槽函数
        self.cancel_btn.clicked.connect(lambda: self.close())  # 点击退出按钮连接槽函数
        self.unlock = Unlock()  # 初始化音乐解锁对象
        self.unlock_btn.clicked.connect(lambda: self.start_unlock())  # 点击解锁按钮连接槽函数
        self.unlock.log_signal.connect(self.show_info)  # 自定义解锁线程发送日志信号连接槽函数
        self.unlock.finished_signal.connect(self.finished_signal)  # 自定义解锁线程异常信号连接槽函数
        self.seek_and_sort = SeekAndSort()  # 初始化查找重复文件对象
        self.seek_and_sort.finished_signal.connect(self.finished_signal)  # 各线程处理完成发送信号
        self.seek_and_sort.log_signal.connect(self.show_seek_info)  # 查找重复文件对象的自定义日志信号连接槽函数
        self.tools_btn.clicked.connect(lambda: self.seek_repeat_file())  # 查找重复文件小工具按钮槽函数
        self.show()  # 显示主窗口
        self.setWindowTitle("音乐解锁")  # 设置主窗口标题
        icon = QtGui.QIcon()  # 初始化图标对象
        icon.addPixmap(QtGui.QPixmap(":/music.ico"), QtGui.QIcon.Normal, QtGui.QIcon.Off)  # 设置图标资源
        self.setWindowIcon(icon)  # 为窗口设置图标
        self.log = MyLogs()  # 初始化日志文件对象
        self.notice()
        self.switch_UI = 0  # 音乐解锁和查找重复文件共用一个窗口,但显示效果需要切换
        self.file_type = [".wave", ".mp4", ".opus", ".mp4", ".flac",
                          ".ape", ".wav", ".mp3", ".aac", ".mgg", ".ac3",
                          ".ogg", ".wma", ".kgm", ".kgma", ".qmc3", ".aiff",
                          ".vpr", ".ncm", ".m4a", ".kwm", ".dsd", ".dsf", ".dff",
                          ".qmcflac", ".mgg1", ".mflac0", ".mgg0", '.ts', '.amr']  # 文件格式

    def closeEvent(self, event):
        """
        重写窗口关闭事件，点击'X'或者'退出'按钮时触发此函数，
        弹窗提示用户是否确认退出
        :param event: pyqt窗口事件
        :return: None
        """
        try:
            # 判断解锁线程是否在执行解锁, 如果正在执行解锁强制退出可能损坏文件弹窗提示用户
            if self.unlock_th and self.unlock_th.is_alive():
                result = QMessageBox.warning(self, "警告!", "正在执行解锁强制退出可能损坏文件, 是否强制退出?",
                                             QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.No)
            # 判断查找重复文件线程是否在执行解锁, 如果正在执行查找强制退出可能损坏文件弹窗提示用户
            elif self.remove_th and self.remove_th.is_alive():
                result = QMessageBox.warning(self, "警告!", "正在执行文件查找强制退出可能损坏文件, 是否强制退出?",
                                             QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.No)
            # 可安全退出，弹窗询问用户是否退出
            else:
                result = QMessageBox.question(self, "询问?", "确认退出程序?",
                                              QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.No)
            if result == QMessageBox.Yes:  # 如果用户确认退出关闭窗口
                event.accept()  # 表示事件已处理，不需要向父窗口传播， 关闭窗口
                _exit(0)  # 界面的关闭时会有一些时候退出不完全或者子进程或线程仍未结束 需要调用 os 的_exit 完全退出
            else:
                event.ignore()  # 表示事件未处理，继续向父窗口传播，不退出继续运行
        except Exception as e:  # 异常捕捉
            self.logger.error(e)  # 将异常写进日志文件

    def notice(self):
        QMessageBox.information(self, "请知悉 !", "目前支持的格式:\t酷狗 (.kgm   .kgma)\n"
                                               "\t\t酷我 (.kwm)\n"
                                               "\t\t网易 (.ncm)\n"
                                               "\t\tVIPER HIFI (.vpr)\n"
                                               "\t\tQQ音乐 (.qmcflac   .qmc3)\n\n"
                                               "暂不支持的格式:\tQQ音乐 (.mflac0   .mgg0   .mgg1)待后续更新\n\n"
                                               "更多格式请自行尝试,或有其他相关格式文件可分享与我,为后期更新提供测试帮助 !\n\n"
                                               "使用之前请记得备份文件并认真阅读当前路径下Readme.md自述文件！")

    def rename_dir(self, base_path):
        """
        启动程序时判断'同名不同艺术家文件,请自行确认删除其中之一' 和‘重复文件’两个目录是否在当前路径中，由于这两个文件夹是
        存储最终查找结果的，如果让这两个文件夹参与查找会导致其他路径的文件和这两个文件夹内的文件重复，如果重复文件已经在这两
        个文件夹里面然而在程序查找的时候可能会把其他路径下的相同文件判定为重复文件，再从其他路径移动重复文件到这两个文件夹就
        会移动失败，会导致查找到的结果和我们实际看到的结果不一样，所以每次程序运行的时候如果这两个文件夹存在的话就给他重命名
        为临时文件夹，然后执行查找，查找完成后删除当前路径下空的文件夹; 如果临时文件夹和保存查找结果的文件夹都同时存在并且文
        件夹内都有文件的情况下，先将临时文件夹下的文件移动到这两个文件夹中，移动完后删除临时文件夹，再将保存结果的文件夹重命
        名为临时文件夹，再执行查找
        :param base_path: 音乐文件根路径
        :return: None
        """
        temp_check = f"{base_path}/temp_check/".replace('\\', '/')  # 临时文件夹用来存放用户自行确认的重复文件
        check_files = f"{base_path}/同名不同艺术家文件,请自行确认删除其中之一/".replace('\\', '/')  # 需要用户自行确认重复文件的目录路径
        temp_dir = f"{base_path}/temp/".replace('\\', '/')  # 存放重复文件的临时文件夹路径
        repeate_files = f"{base_path}/重复文件/".replace('\\', '/')  # 重复文件目录路径
        # 判断临时文件夹和"同名不同艺术家文件,请自行确认删除其中之一"文件夹是否存在
        if exists(temp_check) and exists(check_files):
            files = listdir(temp_check)  # 获取临时文件夹下所有文件
            if not files:  # 如果临时文件夹为空
                rmtree(temp_check, True)  # 删除临时文件夹
            else:  # 否则临时文件夹不为空
                for file in files:  # 遍历获取文件名
                    src_path = f"{temp_check}{file}"  # 拼接源文件的绝对路径
                    des_path = f"{check_files}{file}"  # 拼接文件要移动的目标绝对路径
                    if exists(des_path):  # 如果源文件在目标文件夹中已经存在说明文件重复
                        remove(src_path)  # 删除重复的文件
                        log = f"[{str(datetime.now())[:-3]}] [INFO]:    [已删除多次重复的文件]:  [{src_path}]"  # UI日志
                        self.show_info(log)  # 将日志显示在UI
                        self.log.info(f"[已删除多次重复的文件]: [{src_path}] \n")  # 将日志写进日志文件
                    else:
                        move(src_path, des_path)  # 否则移动文件至目标路径
                rmtree(temp_check)  # 删除临时文件夹
            rename(check_files, temp_check)  # 将需要用户确认重复的文件夹重命名为临时文件夹
        elif exists(check_files):  # 否则如果需要用户确认的重复文件目录存在
            rename(check_files, temp_check)  # 重命名文件夹为临时文件夹
        if exists(temp_dir) and exists(repeate_files):  # 如果存放重复文件的临时文件夹存在并且重复文件夹目录存在
            files = listdir(temp_dir)  # 获取文件夹下所有文件
            if not files:  # 如果临时文件夹为空
                rmtree(temp_dir, True)  # 删除临时文件夹
            else:  # 否则临时文件夹不为空
                for file in files:  # 遍历获取文件名
                    src_path = f"{temp_dir}{file}"  # 拼接源文件绝对路径
                    des_path = f"{repeate_files}{file}"  # 拼接文件要移动的目标绝对路径
                    if isfile(src_path):  # 如果源文件是文件
                        if not exists(des_path):  # 如果源文件在不在目标路径下
                            move(src_path, des_path)  # 移动源文件至目标路径
                        else:  # 否则源文件已在目标路径中存在说明文件重复
                            remove(src_path)  # 删除重复文件
                            log = f"[{str(datetime.now())[:-3]}] [INFO]:    [已删除多次重复的文件]:  [{src_path}]"  # UI日志
                            self.show_info(log)  # 讲日志显示到UI
                            self.log.info(f"[已删除多次重复的文件]: [{src_path}] \n")  # 将日志写进日志文件
                    elif isdir(src_path):  # 否则如果源文件是文件夹
                        file_list = listdir(src_path)  # 获取文件夹下所有文件
                        if not file_list:  # 如果文件夹为空
                            rmtree(src_path, True)  # 删除文件夹
                        else:  # 否则文件夹不为空
                            for f in file_list:  # 遍历文件夹下所有文件获取文件名
                                src = f"{src_path}{'/'}{f}"  # 拼接源文件绝对路径
                                des = f"{repeate_files}{f}"  # 拼接文件要移动的目标绝对路径
                                if not exists(des):  # 如果源文件是文件并且源文件不在目标路径下
                                    move(src, des)  # 移动文件至目标路径
                                else:  # 否则文件已在目标路径下, 说明文件重复
                                    remove(src)  # 删除重复文件
                                    log = f"[{str(datetime.now())[:-3]}] [INFO]:    [已删除多次重复的文件]:  [{src_path}]"  # UI日志
                                    self.show_info(log)  # 将日志显示在UI
                                    self.log.info(f"[已删除多次重复的文件]: [{src_path}] \n")  # 将日志写进日志文件
                        rmtree(src_path, True)  # 删除子文件夹
            rmtree(temp_dir, True)  # 删除临时文件夹
            rename(repeate_files, temp_dir)  # 将重复文件夹目录重命名为临时文件夹
        elif exists(repeate_files):  # 否则如果重复文件夹目录存在
            rename(repeate_files, temp_dir)  # 将重复文件夹目录重命名为临时文件夹

    def seek_repeat_file(self):
        """
        当鼠标点击UI，"查找低质量重复文件 "选择文件夹" 按钮时触发此函数
        :return: None
        """
        try:
            if self.unlock_th and self.unlock_th.is_alive():  # 判断此时的音乐解锁线程是否存在和是否正在活动
                QMessageBox.information(self, "消息", "正在执行文件解锁请稍等!")  # 如果正在执行文件解锁弹窗提示
                return
            elif self.remove_th and self.remove_th.is_alive():  # 判断查找重复文件线程是否存在并且是否在活动
                QMessageBox.warning(self, "警告!", "正在执行查找,请勿重复操作!")  # 如果正在执行删除文件弹窗提示
                return
            self.resetting()  # 重置数据
            base_dir = QFileDialog.getExistingDirectory(self, "选择文件夹", "./")  # 点击"选择文件夹"按钮触发文件对话框，获取音乐文件的根目录
            if not base_dir:
                return
            if abspath(base_dir) == abspath("../../") and not base_dir:  # 判断用户选择的文件夹是否为当前程序所在的目录
                QMessageBox.warning(self, "警告!", "请选择音乐文件根路径!")  # 如果是在程序运行的当前目录弹窗提示
                return
            result = QMessageBox.question(self, "询问", "确定执行查找?")  # 弹窗提示用户是否执行查找
            if result == QMessageBox.No:  # 如果点击弹窗的"Yes"按钮开始执行查找重复文件
                return
            self.seek_and_sort.resetting()  # 重置查找重复文件类的数据
            # 弹窗提示用户是否开启模糊查找功能
            result = QMessageBox.question(self, "询问?", "当前为精确查找, 文件属性一致才会判断重复, 建议开启模糊查找以增加命中率,"
                                                       " 可能会增加误判, 但不会删除文件请放心使用, 是否开启模糊查找?",
                                          QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.Yes)
            if result == QMessageBox.Yes:  # 如果点击Yes按钮开始模糊查找功能
                self.seek_and_sort.fuzzy_query_status = 1  # 修改状态值为1，即开启模糊查找
            else:
                self.seek_and_sort.fuzzy_query_status = 0  # 否则点击No按钮修改状态值为0， 即不开启模糊查找
            if exists(base_dir):  # 判断文件夹是否存在
                self.textEdit.setStyleSheet(
                    "QTextEdit{font-size:16px;border:2px solid rgb(192,192,192);}")  # 设置UI显示日志控件的样式和字体
                self.tools_edit.setStyleSheet("QLineEdit{font-size:25px;color:rgb(0,160,0);\
                                    border:2px solid rgb(192,192,192);}")  # 设置UI 显示音乐根目录控件的样式
                self.tools_edit.setText(base_dir)  # 设置在UI显示用户选择的音乐文件根目录
                # 修改"重复文件、同名不同艺术家文件,请自行确认删除其中之一"等文件夹名称为临时文件夹
                self.rename_dir(base_dir)
                file_total = 0  # 文件总数，初始为零
                wrong_cnt = 0  # 其他文件或者非音乐文件计数
                for root, dirs, files in walk(base_dir):  # 遍历音乐文件根目录下所有资源,获取所有文件
                    for file in files:  # 遍历文件列表得到每一个文件
                        if splitext(file)[1] not in self.seek_and_sort.support_type:  # 切割文件名得到文件后缀判断是否为音乐文件
                            wrong_cnt += 1  # 如果是其他文件计数加一
                            if wrong_cnt >= 20:  # 如果连续出现20个其他文件则弹窗提示用户
                                QMessageBox.critical(self, "错误!", "不符合的文件, 请重新选择音乐根目录")
                                return
                        else:
                            wrong_cnt = 0  # 其他文件计数归零
                        if splitext(file)[1] in self.seek_and_sort.support_type:
                            file_total += 1  # 文件总数加一，得到所有文件总数
                            # self.add_data(self.sf_edit, basename(file))     # 将源文件显示到UI
                            # self.sf_label.setText(f"源文件:  {file_total} 个项目")  # 设置UI源文件数量
                base_dir = f"{base_dir}/"  # 音乐根目录路径拼接“/"
                self.pgb.setMaximum(file_total)  # 设置进度条总进度值为文件总数
                self.seek_and_sort.base_path = base_dir  # 将音乐根目录路径赋值给删除文件对象保存
                self.remove_th = Thread(
                    target=self.seek_and_sort.seek, args=(base_dir,))  # 开启新的线程执行查找和删除文件
                self.remove_th.start()  # 启动线程
                # self.remove_th.join()   # 主线程等待子线程运行结束后主线程再继续运行, 由于主线程运行UI，如果主线程阻塞会影响UI数据延迟更新
                self.tf_label.setText("重复文件:  0 个项目")
                self.success_label.setText("相似或同名文件:  0 个项目")
        except Exception as e:  # 捕获异常
            self.log.error(e)  # 出现异常写进日志文件

    def center(self):
        """
        让窗口居中显示
        :return: None
        """
        # 获取屏幕坐标系
        screen = QDesktopWidget().screenGeometry()
        # 获取窗口坐标系
        size = self.geometry()
        newLeft = (screen.width() - size.width()) / 2
        newTop = (screen.height() - size.height()) / 2 - 50
        self.move(int(newLeft), int(newTop))

    def switch_window(self):
        if self.switch_UI == 0:  # 值为0时显示解锁UI
            self.sf_label.setText("源文件: ")  # 重置源文件数量显示label
            self.success_label.setText("成功项: ")  # 重置显示成功文件数量label
            self.failed_label.setText("失败项: ")  # 重置显示失败文件数量label
            self.tf_label.setText("目标文件: ")  # 重置显示目标文件数量label
            self.tf_edit.clear()  # 清空显示目标文件控件
            self.sf_edit.clear()
            self.cause_edit.clear()  # 清空显示失败原因的控件
            self.success_edit.close()  # 关闭控件显示
            self.failed_label.show()  # 显示控件
            layout = QGridLayout()  # 网格布局
            self.success_edit.resize(self.tf_edit.width(), self.success_edit.height())  # 修改控件大小
            layout.addWidget(self.success_edit, 1, 2, 1, 2)  # 将控件添加到网格布局
            self.setLayout(layout)  # 设置布局
            self.success_edit.show()  # 显示控件
            self.failed_edit.show()  # 显示控件
            layout.update()  # 更新布局
            self.tools_edit.setStyleSheet("QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")

        elif self.switch_UI == 1:  # 值为1时显示查找重复文件UI
            self.sf_label.setText("源文件: ")  # 重置控件文本
            self.sf_edit.clear()  # 清空显示源文件控件
            self.tf_edit.clear()  # 清空显示目标文件控件
            self.cause_edit.clear()  # 清空显示失败原因控件
            self.textEdit.clear()
            self.success_edit.clear()
            self.failed_edit.clear()
            self.input_dir = None  # 将源文件路径置为空
            self.output_dir = None  # 将保存文件路径置为空
            self.src_edit.clear()  # 清空源文件的路径输入控件
            self.out_edit.clear()  # 清空保存到文件夹的路径输入控件
            self.src_edit.setStyleSheet(
                "QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")  # 重置显示源文件路径的控件样式
            self.out_edit.setStyleSheet(
                "QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")  # 重置显示保存文件路径的控件样式
            self.failed_edit.close()  # 关闭控件
            self.failed_label.close()  # 关闭控件
            self.success_label.setText("相似或同名文件: ")  # 修改lable控件文本
            self.tf_label.setText("重复文件: ")  # 修改lable控件文本
            layout = QGridLayout()  # 网格布局
            max_width = self.tf_edit.width() * 2 + 10  # 控件最大宽度
            self.success_edit.setMaximumHeight(max_width)  # 设置控件最大宽度
            self.success_edit.resize(max_width, self.success_edit.height())  # 修改控件显示的大小
            layout.addWidget(self.success_edit, 1, 2, 1, 2)  # 将控件添加到网格布局
            self.setLayout(layout)  # 设置布局
            layout.update()  # 更新布局

    def resetting(self, edit=None):
        """
        重置UI各控件数据
        :param edit: edit文本控件对象
        :return: None
        """
        text = self.sender().text()  # 获取信号源对象的文本属性
        if edit is self.sf_edit:  # 如果正在输入源文件路径
            if self.switch_UI == 1:  # 判断显示的是否为查找重复文件的UI
                self.switch_UI = 0  # 修改为显示解锁的UI
                self.switch_window()  # 重新显示UI
            self.sf_label.setText("源文件: ")  # 重置源文件数量显示label
            self.success_label.setText("成功项: ")  # 重置显示成功文件数量label
            self.failed_label.setText("失败项: ")  # 重置显示失败文件数量label
            self.tools_edit.clear()  # 重置显示查找重复文件路径控件
            self.sf_edit.clear()  # 清空源文件控件的数据
            self.sf_total = 0  # 重置源文件的文件数量为0
            self.src_edit.clear()  # 清空显示源文件路径控件
            self.textEdit.clear()  # 清空日志信息控件
            self.success_edit.clear()  # 清空显示成功文件控件
            self.failed_edit.clear()  # 清空显示失败文件控件
            self.cause_edit.clear()  # 清空显示失败原因控件
            self.pgb.reset()  # 重置进度条
            self.src_edit.setStyleSheet("QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")
        elif edit is self.tf_edit:  # 如果正在输入保存文件的路径
            if self.switch_UI == 1:  # 判断显示的是否为查找重复文件的UI
                self.switch_UI = 0  # 修改为显示解锁的UI
                self.switch_window()  # 重新显示UI
            self.tf_edit.clear()  # 清空目标文件控件的数据
            self.tf_total = 0  # 重置目标文件夹文件数量为0
            self.tf_label.setText("目标文件: ")  # 重置目标文件数量显示lable
            self.success_label.setText("成功项: ")  # 重置显示成功文件数量label
            self.failed_label.setText("失败项: ")  # 重置显示失败文件数量label
            self.textEdit.clear()  # 清空日志信息控件
            self.success_edit.clear()  # 清空显示成功文件控件
            self.failed_edit.clear()  # 清空显示失败文件控件
            self.tools_edit.clear()  # 重置显示查找重复文件路径控件
            self.out_edit.clear()  # 清空显示保存文件路径控件
            self.cause_edit.clear()  # 清空显示失败原因控件
            self.pgb.reset()  # 重置进度条
            self.out_edit.setStyleSheet("QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")
        else:
            if text == "选择文件夹(Ctrl+R)":  # 信号源对象的文本属性
                if self.switch_UI == 0:  # 判断显示的是否为解锁的UI
                    self.switch_UI = 1  # 修改为显示查找重复文件的UI
                    self.switch_window()  # 重新显示UI
                self.sf_label.setText("源文件: ")  # 重置控件文本
                self.success_label.setText("相似或同名文件: ")  # 修改lable控件文本
                self.tf_label.setText("重复文件: ")  # 修改lable控件文本
            elif text == '解锁(Ctrl+N)':  # 信号源对象的文本属性
                if self.switch_UI == 1:  # 判断显示的是否为查找重复文件的UI
                    self.switch_UI = 0  # 修改为显示解锁的UI
                    self.switch_window()  # 重新显示UI
            # 重置tools_edit控件的字体颜色样式
            self.tools_edit.setStyleSheet("QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")
            self.tf_edit.clear()  # 清空UI目标文件控件的数据
            self.tf_total = 0  # 重置目标文件夹下文件总数
            self.sf_edit.clear()  # 清空UI源文件控件数据
            self.sf_total = 0  # 重置源文件数量
            self.unlock.repeat_total = 0  # 重置重复文件总数
            self.success_total = 0  # 重置成功解锁的文件总数
            self.success_edit.clear()  # 清空显示成功文件控件
            self.failed_total = 0  # 重置解锁失败文件总数
            self.failed_edit.clear()  # 清空显示失败文件控件
            self.cause_edit.clear()  # 清空显示失败原因控件
            self.get_files(self.input_dir, self.sf_edit)  # 刷新源文件文件总数并显示文件
            self.get_files(self.output_dir, self.tf_edit)  # 刷新目标文件夹下文件总数并显示文件
            self.unlock.pgb_value = 0  # 重置进度值为0
            self.textEdit.clear()  # 清空日志信息控件
            self.pgb.reset()  # 重置进度条
            self.tools_edit.clear()  # 重置显示查找重复文件路径控件

    def add_data(self, edit, info):
        """
        将日志信息追加显示到edit控件
        :param edit: edit对象
        :param info: 文本信息
        :return: None
        """
        edit.moveCursor(QTextCursor.End)  # 将光标移动到行的结尾
        edit.append(info)  # 追加显示

    def get_files(self, path=None, edit=None):
        """
        根据传入的路劲获取此路径下的所有文件，把符合格式的文件显示到对应的edit控件
        :param path: 路径
        :param edit: edit对象
        :return: None
        """
        try:
            if path and isdir(path):  # 判断path参数是否为空, 是否为文件夹
                file_list = listdir(path)  # 获取文件夹下所有文件存到列表
                for file in file_list:  # 遍历文件列表
                    child_path = f"{path}{'/'}{file}"  # 拼接文件或子文件夹路径
                    if isfile(child_path):
                        if splitext(child_path)[1] in self.file_type:  # 如果文件格式符合列表中任意一项，将文件追加显示到edit控件
                            # 避免多次重复操作解锁会重复显示已经解锁过的文件名到源文件和目标文件控件
                            if self.sender().text() == "解锁(Ctrl+N)" and file not in edit.toPlainText():
                                base_name = basename(child_path)  # 获取不包含路径的文件名
                                self.add_data(edit, base_name)  # 将文件追加到edit控件显示
                                if edit is self.sf_edit:  # 如果此时编辑的是sf_edit，则传入sf_edit对象
                                    self.sf_total += 1  # 源文件总数加1
                                elif edit is self.tf_edit:  # 如果此时编辑的是tf_edit，则传入tf_edit对象
                                    self.tf_total += 1  # 目标文件总数加1
                            else:  # 程序刚启动第一次运行时显示所有源文件和目标文件
                                base_name = basename(child_path)  # 获取不包含路径的文件名
                                self.add_data(edit, base_name)  # 将文件追加到edit控件显示
                                if edit is self.sf_edit:  # 如果此时编辑的是sf_edit，则传入sf_edit对象
                                    self.sf_total += 1  # 源文件总数加1
                                elif edit is self.tf_edit:  # 如果此时编辑的是tf_edit，则传入tf_edit对象
                                    self.tf_total += 1  # 目标文件总数加1
                    elif isdir(child_path):  # 如果是文件夹
                        child_path = f"{child_path}{'/'}"  # 拼接文件路径中的斜杠
                        self.get_files(child_path, edit)  # 递归调用自己
        except Exception as e:  # 异常捕捉
            self.log.error(e)  # 将异常写进日志文件

    def search(self, edit, search_str):
        """
        搜索文本框中特定的字符串并改变字符串颜色
        :param edit: edit对象
        :param search_str: 要搜索的字符串
        :return: None
        """
        document = QTextDocument()
        document = edit.document()
        highlight_cursor = QTextCursor(document)
        cursor = QTextCursor(document)
        cursor.beginEditBlock()
        color_format = QTextCharFormat(highlight_cursor.charFormat())
        if "INFO" in search_str:
            color_format.setForeground(Qt.green)
        elif "WARNING" in search_str:
            color_format.setForeground(Qt.magenta)
        elif "ERROR" in search_str:
            color_format.setForeground(Qt.red)
        else:
            color_format.setForeground(Qt.red)
        while (not highlight_cursor.isNull()) and (not highlight_cursor.atEnd()):
            highlight_cursor = document.find(search_str, highlight_cursor)
            if not highlight_cursor.isNull():
                highlight_cursor.mergeCharFormat(color_format)
        cursor.endEditBlock()

    def show_seek_info(self, log_info=None, pgb_value=None, file_info=None):
        """
        显示查找重复文件线程和音质分类线程的日志信息
        :param log_info: UI显示的日志信息
        :param pgb_value: 线程执行的进度值
        :param file_info: 源文件名称或者重复文件的名称
        :return: None
        """
        if log_info:
            self.add_data(self.textEdit, log_info)  # 追加数据到UI显示日志信息
            self.search(self.textEdit, log_info)  # 调用search()函数，将textEdit控件中的文本修改颜色显示
        if pgb_value:  # 判断值是否为空
            self.pgb.setValue(pgb_value)  # 不为空设置进度值
        if file_info and type(file_info) is str:  # 判断值是否为空并且是否为字符串类型
            self.add_data(self.sf_edit, file_info)  # 追加数据到UI显示日志信息
            self.sf_total += 1  # 源文件总数加一
            self.sf_label.setText(f"源文件:  {self.sf_total} 个项目")  # 设置UI源文件lable显示源文件数量
        if file_info and type(file_info) is tuple:  # 判断值是否为空并且是否为元组类型
            if len(file_info) == 2:  # 如果元组长度等于2，其中值为相似或者同名的文件名
                file_info = f"{file_info[0]}  ------  {file_info[1]}"  # 将两个文件名拼接成日志字符串
                if file_info not in self.success_edit.toPlainText():  # 判断数据是否已经显示在UI, 避免重复显示
                    self.add_data(self.success_edit, file_info)  # 追加数据到UI显示日志信息
            else:
                # if file_info[0] not in self.tf_edit.toPlainText():          # 判断数据是否已经显示在UI, 避免重复显示
                self.add_data(self.tf_edit, file_info[0])  # 追加数据到UI显示日志信息
        # 设置UI控件显示相似或同名文件的数量
        self.success_label.setText(f"相似或同名文件:  {self.seek_and_sort.user_check_result_cnt} 个项目")
        self.tf_label.setText(f"重复文件:  {self.seek_and_sort.result_cnt} 个项目")  # 设置UI控件显示重复文件数量

    # @pyqtSlot(str, int, str, str)
    def show_info(self, log_info=None, pgb_value=None, success_file=None, failed_file=None):
        """
        在UI显示各线程日志信息,采用自定义信号将其他线程的日志信息发送给主线程,由主线程接收数据并显示到UI
        :param log_info: 一行日志信息
        :param pgb_value: 进度条的进度值
        :param success_file: 解锁成功的文件信息
        :param failed_file:  解锁失败的文件信息
        :return: None
        """
        try:
            if log_info:  # 判断日志信息是否为空
                self.add_data(self.textEdit, log_info)  # 追加数据到UI显示日志信息
                self.search(self.textEdit, log_info)  # 调用search()函数，将textEdit控件中的文本修改颜色显示
            if pgb_value:  # 判断进度值是否为空
                self.pgb.setValue(pgb_value)  # 设置进度条进度值
            if success_file:  # 如果成功解锁一个文件将日志信息追加显示到success_edit中
                self.add_data(self.success_edit, success_file)  # 追加显示成功文件
                self.success_total += 1  # 成功计数加1
                if success_file not in self.tf_edit.toPlainText() \
                        or 'successfully' in log_info:  # 避免多次重复操作解锁会重复显示已经解锁过的文件名到目标文件控件
                    self.tf_total += 1  # 目标文件总数加1
                    self.add_data(self.tf_edit, success_file)  # 将解锁成功的文件追加显示到目标文件控件
                self.success_label.setText(f"成功项:  {self.success_total} 个项目")  # 更新成功数量
                self.tf_label.setText(f"目标文件:  {self.tf_total} 个项目")  # 将目标文件总数显示到"目标文件："标签
            elif failed_file:  # 如果出现解锁失败的文件将文件信息显示到 failed_edit
                self.add_data(self.failed_edit, failed_file)  # 追加显示失败文件
                self.failed_total += 1  # 解锁失败文件数量加1
                failed_cause = f"不支持({failed_file})此文件的转换"  # 失败原因: 解锁失败说明不支持该文件格式
                self.failed_label.setText(f"失败项:  {self.failed_total} 个项目")  # 更新失败文件的数量
                self.add_data(self.cause_edit, failed_cause)  # 追加显示失败原因
                self.search(self.cause_edit, failed_file)  # 将解锁失败的文件加颜色显示UI
            if self.pgb.maximum() == pgb_value:  # 判断当前进度值是否为最大进度值
                if pgb_value == self.unlock.pgb_value:  # 判断进度条值如果和解锁的进度值相等说明是在执行解锁功能
                    if self.failed_total:  # 判断失败文件总数是否为0
                        self.pgb.setMaximum(self.failed_total)  # 设置用于移动解锁失败文件功能的总进度值
        except Exception as e:  # 异常捕捉
            self.log.error(e)  # 出现异常写进日志文件

    # @pyqtSlot()
    def finished_signal(self, arg=None):
        """
        解锁线程、查找重复文件线程、音质分类线程处理完成时发送完成信号的槽函数
        :param arg: 不同信号发送了不同的参数值，根据参数值判断触发此函数的信号源
        :return: None
        """
        self.pgb.setValue(self.pgb.maximum())
        if arg == 'unlock_finish':  # 判断是否为解锁完成信号
            QMessageBox.information(self, "OK", "解锁完成!")  # 弹窗提示用户
            if self.failed_total:  # 如果失败文件总数不等于0
                QMessageBox.warning(self, "警告!",
                                    f'{self.failed_total} 个解锁失败的文件已移动至: "{self.input_dir}/解锁失败/"  目录下请确认!')  # 弹窗提示用户有解锁失败的文件
            if self.unlock.repeat_total:  # 如果解锁线程的重复解锁文件总数不等于0
                # 弹窗提示有重复解锁的文件且被覆盖
                QMessageBox.information(self, "消息", f"{self.unlock.repeat_total} 个重复文件已被覆盖!")
        elif arg == 'seek_repeat_finish':  # 判断是否为查找重复文件完成信号
            # 如果重复文件计数等于零说明没有重复文件，不等于零设置移动文件的总进度值并将重复文件移动到统一目录
            if self.seek_and_sort.result_cnt or self.seek_and_sort.user_check_result_cnt:
                # 设置删除重复文件的总进度值
                self.pgb.setMaximum(self.seek_and_sort.result_cnt + self.seek_and_sort.user_check_result_cnt)
                self.seek_and_sort.th_flag = 1  # 修改查找重复文件线程状态值, 表示查找完成,当值为1时线程执行下一步移动重复文件
            else:
                QMessageBox.information(self, "消息", "没有重复文件!")  # 否则没有重复文件弹窗提示用户
                self.exec_sort()  # 下一步执行文件按音质分类
        elif arg == 'move_file_finish':  # 判断是否为移动文件完成信号
            if self.seek_and_sort.user_check_result_cnt:  # 判断需要用户确认的重复文件计数是否为0
                # 如果计数器不为0说明有需要用户确认的重复文件, 弹窗提示用户
                QMessageBox.warning(self, "警告!",
                                    f'{self.seek_and_sort.user_check_result_cnt}  个相同或相似文件已移动至:    "{self.seek_and_sort.base_path}/同名不同艺术家文件,请自行确认删除其中之一/"   目录下,请确认!!!')
            if self.seek_and_sort.result_cnt:
                # 弹窗提示用户重复文件查找完成并询问是否执行一键删除
                result = QMessageBox.question(self, "询问?",
                                              f'查找完成! {self.seek_and_sort.result_cnt} 个重复文件已移动至: "{self.seek_and_sort.base_path}重复文件/"  路径下,删除需谨慎,是否执行一键删除?',
                                              QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.No)
                if result == QMessageBox.Yes:  # 判断用户是否点击"Yes"按钮
                    self.pgb.setMaximum(self.seek_and_sort.result_cnt)  # 设置删除重复文件的总进度值
                    self.seek_and_sort.th_flag = 2  # 修改查找重复文件线程状态值为2, 表示重复文件移动完成,下一步执行删除重复文件
                else:
                    self.exec_sort()  # 否则不删除重复文件,执行文件音质分类
            else:
                self.exec_sort()  # 如果没有重复文件进行下一步按音质分类
        elif arg == 'remove_finish_0' or arg == 'remove_finish_1':  # 判断是否为删除重复文件完成信号, 参数中包含了删除文件函数的返回值
            if arg[-1]:  # 删除文件函数完成后通过信号发送函数执行返回值，通过返回值判断有无异常,无异常返回值为1 说明文件删除成功
                self.tf_edit.clear()
                self.tf_label.setText("重复文件:  0 个项目")
                self.seek_and_sort.result_cnt = 0
                QMessageBox.information(self, "OK!", "删除完成!")  # 删除完成弹窗提示用户
            else:  # 否则有异常发生, 返回值为0, 说明有文件未被删除
                QMessageBox.critical(self, "ERROR!", "有未删除的项目请确认!")  # 说明执行删除时有异常发生，弹窗提示用户有未删除的文件
            self.exec_sort()  # 重复文件删除完成后进行下一步按音质分类
        elif arg == 'file_sort_finish':  # 判断是否为音质分类线程
            QMessageBox.information(self, "OK", "音质分类完成！")  # 弹窗提示用户音质分类完成
        elif arg == "move_sort_failed_finish":  # 如果有分类失败的文件移动完成后将发送信号
            # 弹窗提示用户
            QMessageBox.warning(self, '警告!',
                                f'{self.seek_and_sort.sort_failed_cnt}个分类失败的文件已移至: "{self.seek_and_sort.base_path}/分类失败/"  目录下请确认!')

    def exec_sort(self):
        failed_cnt = 0  # 假设解锁失败文件夹在音乐文件根目录下初始化解锁失败的文件总为0
        if exists(f"{self.seek_and_sort.base_path}解锁失败/"):  # 判断解锁失败文件是否在音乐根目录下
            failed_cnt = len(listdir(f"{self.seek_and_sort.base_path}解锁失败/"))  # 获取解锁失败文件夹下文件总数
        # 用文件总数减去重复文件数量减去解锁失败文件的数量作为音质分类的进度条最大值
        pgb_maxValue = self.seek_and_sort.pgb_value - self.seek_and_sort.result_cnt - \
                       self.seek_and_sort.user_check_result_cnt - failed_cnt
        result = QMessageBox.question(  # 弹窗提示用户是否对音质进行文件夹分类
            self, "询问?", '是否对文件按音质进行分类?',
            QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.No)
        if result == QMessageBox.Yes:  # 判断是否点击Yes按钮
            self.pgb.setMaximum(pgb_maxValue)  # 设置执行文件分类的总进度值
            self.seek_and_sort.th_flag = 3  # 修改查找重复文件线程状态值为3, 表示重复文件查找并移动或删除完成, 下一步执行音质分类
        else:
            self.seek_and_sort.th_flag = 4  # 如果用户不需要执行音质分类将值改为4, 结束重复文件查找线程

    def start_unlock(self):
        """
        当点击解锁按钮, 校验源文件目录和输出文件目录的正确性读取源文件目录的文件总个数作为进度条的最大值
        开启一个新的线程执行文件解锁， 如果单线程会导致UI阻塞每次点击解锁重置各个Edit控件，等待显示新的数据
        :return: None
        """
        if self.remove_th and self.remove_th.is_alive():  # 判断重复文件查找删除线程是否存在，是否活动
            QMessageBox.information(self, "消息", "正在执行重复文件查找请稍等!")  # 如果正在执行查找或删除提示用户稍后再操作
            return
        if self.unlock_th and self.unlock_th.is_alive():  # 判断解锁线程是否存在，是否活动
            QMessageBox.warning(self, "警告！", "正在执行解锁，请勿重复操作！")  # 如果正在执行解锁提示用户不要重复操作
            return
        self.resetting()  # 重置数据及各控件
        if not self.input_dir or not self.output_dir:  # 判断文件路径是否为空
            QMessageBox.warning(self, "警告！", "文件路径不能为空,请重新选择!")  # 如果为空则UI弹窗提示
            return
        if not exists(self.input_dir):  # 判断源文件路径是否存在
            QMessageBox.warning(self, "警告！", "源文件夹不存在，请重新选择!")  # 不存在则弹窗提示
            return
        if not exists(self.output_dir):  # 判断输出文件夹路径是否存在
            QMessageBox.warning(self, "警告！", "目标文件夹不存在，请重新选择!")  # 不存在则弹窗提示
            return
        if self.sf_total == 0:  # 如果源文件中文件个数为0，说明没有可解锁的文件
            QMessageBox.warning(self, "警告！", "未找到文件,请重新选择目录!")  # 弹窗提示
            return
        if self.input_dir and self.output_dir and self.input_dir == self.output_dir:  # 判断源文件路径和目标文件路径是否为空
            QMessageBox.warning(self, "警告！", "保存文件路径不能和源文件路径相同,请重新选择保存路径")
            return
        self.textEdit.setStyleSheet("QTextEdit{font-size:16px;border:2px solid rgb(192,192,192);}")  # 设置日志信息文本框样式
        self.sf_label.setText(f"源文件:  {self.sf_total} 个项目")  # 设置源文件总个数
        self.tf_label.setText(f"目标文件:  {self.tf_total} 个项目")  # 设置目标文件总个数
        self.pgb.setMaximum(self.sf_total)  # 设定进度条的总进度值为可解锁的文件总数
        # 开启一个新的线程执行解锁
        self.unlock_th = Thread(target=self.unlock.execute_cmd, args=(self.input_dir, self.output_dir))
        self.unlock_th.start()  # 启动线程
        # self.unlock_th.join()  # 主线程等待子线程运行结束后主线程再继续运行, 由于主线程运行UI，如果主线程阻塞会影响UI数据延迟更新
        self.failed_label.setText("失败项:  0 个项目")  # 如果所有文件解锁成功更新失败项标签为“0个的项目”
        self.success_label.setText("成功项:  0 个项目")

    def get_dir(self):
        """
        通过UI点击按钮获取源文件夹和输出文件夹路径
        将获取的路径通过QLineEdit控件显示到UI
        :return: None
        """
        text = self.sender().text()  # 获取信号源对象的文本属性
        if text == "选择文件夹(Ctrl+F)":  # 判断如果信号源对象的文本属性和定义的字符串相等，说明点击的是"源文件目录"按钮
            self.resetting(self.sf_edit)  # 是文件夹清空sf_edit，等待显示新的数据
            self.input_dir = QFileDialog.getExistingDirectory(self, "选择文件夹", "./")  # QFileDialog控件获取文件夹路径
            self.src_edit.setText(self.input_dir)  # 将选择的路径显示到UI
            if isdir(self.input_dir):  # 判断是文件夹则QLineEdit控件的字体会变成绿色
                self.src_edit.setStyleSheet("QLineEdit{font-size:25px;color:rgb(0,160,0);\
                border:2px solid rgb(192,192,192);}")
                self.get_files(self.input_dir, self.sf_edit)  # 获取源文件路径下所有文件
                self.sf_label.setText(f"源文件:  {self.sf_total} 个项目")  # 设置源文件总个数
            # 正常输入是不会等于空串的,这种情况为之前输入过值然后给清除了,此时恢复到程序刚启动时最初的样式
            elif self.input_dir == "" or self.input_dir is None:
                self.src_edit.setStyleSheet("QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")
                self.resetting(self.sf_edit)  # 重置显示源文件文本框控件
                self.sf_label.setText("源文件: ")  # 重置源文件数量为初始状态
            else:  # 否则QLineEdit控件的字体变成红色
                self.src_edit.setStyleSheet("QLineEdit{font-size:25px;color:rgb(255,0,0);\
                border:2px solid rgb(192,192,192);}")  # 重置源文件路径输入框样式
                self.sf_label.setText("源文件:  路径不存在!")  # 如果路径错误label显示路径不存在
                self.resetting(self.sf_edit)  # 不是文件夹则重置sf_edit
        elif text == "选择文件夹(Ctrl+S)":  # 判断如果信号源对象的文本属性和定义的字符串相等，说明点击的是"输出到目录"按钮
            self.resetting(self.tf_edit)  # 是文件夹清空tf_edit，等待显示新的数据
            self.output_dir = QFileDialog.getExistingDirectory(self, "选择文件夹", "./")  # QFileDialog控件获取文件夹路径
            self.out_edit.setText(self.output_dir)  # 将选择的路径显示到UI
            if isdir(self.output_dir):  # 判断是文件夹则QLineEdit控件的字体会变成绿色
                self.out_edit.setStyleSheet("QLineEdit{font-size:25px;color:rgb(0,160,0);\
                    border:2px solid rgb(192,192,192);}")  # 重置保存文件的路径输入框
                self.get_files(self.output_dir, self.tf_edit)  # 获取目标文件夹下所有文件
                self.tf_label.setText(f"目标文件:  {self.tf_total} 个项目")  # 设置UI目标文件数量

                # 正常输入是不会等于空串的,这种情况为之前输入过值然后给清除了,此时恢复到程序刚启动时最初的样式
            elif self.output_dir == "" or self.output_dir is None:
                self.out_edit.setStyleSheet("QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")
                self.resetting(self.tf_edit)  # 重置目标路径文本编辑框
                self.tf_label.setText("目标文件: ")  # 重置目标文件label
            else:  # 否则QLineEdit控件的字体变成红色
                self.out_edit.setStyleSheet("QLineEdit{font-size:25px;color:rgb(255,0,0);\
                    border:2px solid rgb(192,192,192);}")  # 重置保存文件路径输入框
                self.tf_label.setText("目标文件:  路径不存在")  # 如果路径错误label显示路径不存在
                self.resetting(self.tf_edit)  # 不是文件夹则重置tf_edit
