# -*- coding: utf-8 -*-

from datetime import datetime
from os import walk, kill, mkdir, listdir
from os.path import basename, exists
from shutil import move
from subprocess import Popen, PIPE, STDOUT
from time import sleep
from logger import MyLogs
from PyQt5.QtCore import QObject, pyqtSignal


class Unlock(QObject):
    log_signal = pyqtSignal(str, int, str, str)  # 自定义信号,接收解锁线程日志信息
    finished_signal = pyqtSignal(str)  # 解锁自定义异常信息信号

    def __init__(self):
        super(Unlock, self).__init__()
        self.log = MyLogs()  # 初始化日志文件对象
        self.pgb_value = 0  # 进度条的进度值
        self.repeat_total = 0  # 重复解锁文件计数

    def execute_cmd(self, input_dir, output_dir):
        """
        :param input_dir: 源文件目录
        :param output_dir: 保存到目标文件夹目录
        :return: None
        um-windows-amd64.exe可执行程序是在命令行运行的，这个可执行程序才是解锁的核心，输出的日志信息会从命令行打印出来，
        在这里不需要命令行黑窗口,并且需要拿到这个可执行程序在命令行输出的日志信息在我们的UI显示
        从python2.4版本开始,可以用subprocess这个模块来产子生进程,并连接到子进程的标准输入/输出/错误中去，还可以得到子进程的返回值。
        subprocess意在替代其他几个老的模块或者函数，比如：os.system os.spawn* os.popen* popen2.* commands.*
        命令行的结果返回是一次性的，所以我们用read方法读取数据是没有问题的，我们在Python中如果需要获取打印结果，
        如果还是用read方法的话，等待结果的返回时间会非常长，这里需要换一种方法读取结果，实时的打印出日志信息。
        这里就用到了readline方法和iter()函数，其实这种写法类似我们读取文件，单行读取和全部内容读取。
        关于subprocess.Popen()函数的使用和应用pyinstaller打包成可执行文件运行报错可参考链接：
        https://blog.csdn.net/qq_26373925/article/details/105521118
        """
        try:
            failed_flist = []  # 初始化列表存放解锁失败文件名
            input_dir = input_dir.replace('/', '\\')  # 替换路径中顺斜杠为反斜杠
            output_dir = output_dir.replace("/", '\\')  # 替换路径中顺斜杠为反斜杠
            dir_list = [input_dir]  # 初始化列表存放解锁根路径下的文件夹路径
            for root, dirs, files in walk(input_dir):  # 遍历获取解锁根路径下所有文件夹路径
                for dir in dirs:  # 遍历获取解锁根路径下每一个文件夹路径
                    dir = f"{root}\\{dir}"  # 拼接文件夹绝对路径
                    dir_list.append(dir)  # 将文件夹路径追加到列表存放
            exists_file = listdir(output_dir)  # 列表存放目标路径下的文件名信息，用来后续判断是否重复解锁
            self.log.info("  [开始解锁]: ...\n")
            for dir in dir_list:  # 遍历获取需要解锁的文件夹路径
                cmd = f"um-windows-amd64.exe -i {dir} -o {output_dir}"  # 循环创建进程调用解锁可执行程序进行文件解锁的cmd指令
                proc = Popen(
                    cmd,
                    shell=True,
                    stdin=PIPE,
                    stdout=PIPE,
                    stderr=STDOUT
                )
                proc.stdin.close()  # 不需要命令行窗口输入直接关闭
                for line in iter(proc.stdout.readline, 'b'):  # 循环遍历数据
                    line = line.decode("utf-8")  # 读取cmd执行的输出结果为byte类型，需要转码
                    line = line.replace("\\\\", "\\")  # 替换数据中的反斜杠‘\\’
                    if line:
                        # 判断subprocess产生的子进程解锁是否成功，获取数据发送到主线程显示
                        if "successfully converted	" in line:  # 判断文件是否解锁成功
                            self.pgb_value += 1  # 成功解锁一个文件后输出一行日志，进度加1
                            line = line.split("successfully converted	")[1].rstrip('\n')  # 按照指定字符串切割并去除字符串右边的换行符
                            success_file = line.split(f"{output_dir}\\")[1].rstrip('"}\n')  # 解锁成功的文件信息
                            if success_file in exists_file:  # 判断解锁成功的文件在目标路径下是否已经存在
                                self.repeat_total += 1  # 重复解锁文件计数加一
                                log_info = f'[{str(datetime.now())[:-3]}] [WARNING]:  [已覆盖重复文件: "{output_dir}\\{success_file}"]'  # 解锁重复文件的日志信息
                                self.log_signal.emit(log_info, self.pgb_value, success_file, None)  # 发送日志信息到主线程并UI显示
                                self.log.warning(f'[已覆盖重复文件: "{output_dir}\\{success_file}" ] \n')  # 将日志写进日志文件
                            else:
                                # 拼接解锁成功的日志信息
                                log_info = f'[{str(datetime.now())[:-3]}] [INFO]:    successfully converted  {line}'
                                self.log.info(f" successfully converted  {line} \n")  # 将日志写进日志文件
                                self.log_signal.emit(log_info, self.pgb_value, success_file, None)  # 自定义信号发送日志信息
                        elif "conversion failed" in line:  # 判断文件是否解锁失败
                            line = line.split("conversion failed	")[1].rstrip('\n')  # 按照指定字符串切割并去除字符串右边的换行符
                            self.pgb_value += 1  # 进度值加一
                            failed_file = line.split(': "')[1].strip('"}\n')  # 按照指定字符串切割并去除字符串右边的换行符
                            log_error = f"[{str(datetime.now())[:-3]}] [ERROR]:    conversion failed  {line}"
                            self.log.error("conversion failed  {line} \n")  # 解锁失败日志写进日志文件
                            self.log_signal.emit(log_error, self.pgb_value, None, failed_file)  # 自定义信号发送日志信息
                            failed_flist.append(f"{dir}/{failed_file}")  # 将解锁失败的文件添加进列表
                        elif 'skipping while no suitable decoder' in line:  # 解锁失败, 不支持解锁的文件
                            line = line.split('skipping while no suitable decoder	')[1].rstrip('\n')
                            self.pgb_value += 1  # 进度值加一
                            failed_file = line.split(': "')[1].strip('"}\n')  # 截取解锁失败的文件名
                            log_error = f"[{str(datetime.now())[:-3]}] [ERROR]:   skipping while no suitable decoder  {line}"
                            self.log.error(f"skipping while no suitable decoder  {line} \n")  # 不支持解锁的日志信息写进日志文件
                            self.log_signal.emit(log_error, self.pgb_value, None, failed_file)  # 自定义信号发送日志信息
                            failed_flist.append(f"{dir}/{failed_file}")  # 将解锁失败的文件添加进列表
                    else:
                        proc.stdout.close()  # 文件解锁完成后subprocess产生的进程并没有结束，还会持续运行，当没有数据输出时关闭输出
                        # os.system("taskkill /t /f /pid {}".format(pid))  # 解锁完成杀掉进程
                        try:
                            sleep(0.5)
                            proc.terminate()  # 杀进程
                        except Exception:
                            pass
                        break
            self.log.info(" [解锁结束]: ...\n")
            if failed_flist:  # 判断解锁失败列表是否为空
                sleep(0.5)
                pgb_value = 0  # 初始化进度值
                for file in failed_flist:  # 遍历解锁失败的文件列表，将文件移动至保存解锁文件的文件夹下
                    pgb_value += 1  # 进度值加一
                    base_name = basename(file)  # 截取不带路径的文件名
                    des_dir = f"{input_dir}/解锁失败/"  # 拼接文件夹路径
                    des_path = f"{des_dir}{base_name}".replace('\\', '/')  # 拼接文件路径
                    if not exists(des_dir):  # 判断文件夹是否存在
                        mkdir(des_dir)  # 文件夹不存在创建文件夹
                    move(file, des_path)  # 移动文件
                    log = f'[{str(datetime.now())[:-3]}] [INFO]:    [移动成功]:  [原路径: "{file}" ------ 目标路径: "{des_path}"]'
                    self.log.info(f' [移动成功]: [原路径: "{file}" ------ 目标路径: "{des_path}"] \n')  # 将日志写进日志文件
                    self.log_signal.emit(log, pgb_value, None, None)  # 发送进度值
            self.finished_signal.emit('unlock_finish')  # 解锁完成发送完成信号
            # sys.exit()
        except Exception as e:
            self.log.error(f"{str(e)} \n")  # 将异常写进日志文件
