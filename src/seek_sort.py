# -*- coding: utf-8 -*-

from difflib import SequenceMatcher
from datetime import datetime
from os.path import exists, isdir, isfile, splitext, basename, getsize, join, dirname
from os import listdir, remove, rename, mkdir, walk
from re import search, S, findall, compile as re_compile
from shutil import rmtree, move
from time import sleep
from typing import List, Any
from eyed3 import load
from PyQt5.QtCore import pyqtSignal, QObject
from mediafile import MediaFile
from mutagen.aac import AAC
from mutagen.ac3 import AC3
from mutagen.aiff import AIFF
from mutagen.dsdiff import DSDIFF
from mutagen.flac import FLAC
from mutagen.id3 import TIT2, ID3, TPE1
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis, OggVorbisInfo
from mutagen.wave import WAVE
from tinytag import TinyTag
from soundfile import SoundFile
from logger import MyLogs


class SeekAndSort(QObject):
    log_signal = pyqtSignal(str, int, object)  # 自定义信号,发送查找重复文件日志信息
    finished_signal = pyqtSignal(str)  # 自定义信号,发送查找重复文件线程各函数执行完成信号

    def __init__(self):
        super(SeekAndSort, self).__init__()
        self.logger = MyLogs()  # 初始化日志文件对象
        self.file_title_dict = {}  # 存储文件title、文件路径、文件出现的次数计数
        self.result_list = []  # 查找到的重复文件
        self.user_check_result = []  # 查找到文件相同不同艺术家的文件
        # 目前支持查找重复、获取文件元数据、编辑文件元数据的所有类型
        self.support_type = ['.aac', '.mp3', '.ogg', '.opus', '.mp4', '.m4a', '.dff',
                             '.dsf', '.flac', '.wma', '.wave', '.wav', '.ac3', '.aiff']
        self.tinytag_type = ['.aac', '.mp3', '.ogg', '.opus', '.mp4',
                             '.m4a', '.flac', '.wma', '.wave', '.wav']  # TinyTag目前支持的文件类型
        self.id3_type = ['.mp3', '.wma', '.aac']  # 支持ID3并且能被TinyTag获取到文件属性的文件类型 '.ac3',
        self.mutagen_type = ['.aac', '.ogg', '.flac', '.wav', '.aiff', '.dff', '.ac3', '.wma', '.mp3']
        self.pgb_value = 0  # 进度值
        self.result_cnt = 0  # 重复文件计数
        self.user_check_result_cnt = 0  # 相同文件不同艺术家文件计数
        self.base_path = None  # 音乐文件的根目录路径
        self.sort_failed = []  # 音质分类失败文件列表
        self.sort_failed_cnt = 0  # 音质分类失败文件计数
        # MediaFile 模块目前支持的类型
        self.media_file_type = ['.wav', '.opus', '.mp4', '.m4a', '.aiff', '.mp3', '.flac', '.ogg', '.dsf']
        self.th_flag = 0  # 查找重复文件线程执行状态，不同的值调用不同的函数
        self.fuzzy_query_status = 0  # 模糊查找重复文件状态值, 默认为0即不开启模糊查找,程序运行时弹窗提示用户由用户决定是否开启

    def resetting(self):
        """
        重置对象的数据
        :return: None
        """
        self.pgb_value = 0  # 重置进度值
        self.result_cnt = 0  # 重置重复文件计数
        self.file_title_dict.clear()  # 清空 file_title_dict
        self.result_list.clear()  # 清空 result_list
        self.user_check_result_cnt = 0  # 重置相同文件不同艺术家的文件计数
        self.user_check_result.clear()  # 清空相同文件不同艺术家的文件列表
        self.sort_failed.clear()  # 清空分类失败文件列表
        self.th_flag = 0  # 查找重复文件,移动重复文件,删除文件, 音质分类在同一线程下执行, 通过修改线程状态值执行不同的功能
        self.fuzzy_query_status = 0  # 模糊查找重复文件状态值
        self.sort_failed_cnt = 0  # 重置音质分类失败文件计数

    def send_result(self, repeat_name=None, similar_name=None, old_name=None):
        """
        发送查找结果
        :param repeat_name: str 重复的文件名信息
        :param similar_name: str 相似文件的文件名信息
        :param old_name: str 与重复文件对应的文件名信息
        :return: None
        """
        repeat_base = basename(repeat_name)  # 获取不包含路径的文件名
        if repeat_name and similar_name:  # 判断文件名是否为空，都不为空说明是相似或者同名文件
            similar_base = basename(similar_name)  # 获取不包含路径的文件名
            # 将相似文件拼接在日志信息中发送至UI
            log = f'[{str(datetime.now())[:-3]}] [WARNING]:  [相似或同名文件]:  [{repeat_name} ------ {similar_base}]'
            self.log_signal.emit(log, self.pgb_value, (repeat_base, similar_base))  # 发送日志到UI显示
            self.logger.warning(f'[相似或同名文件]: [{repeat_name} ------ {similar_name}] \n')  # 将日志写入文件
        elif repeat_name and not similar_name:  # 如果repeat_name不为空并且check_name为空说明是repeat_name为重复文件
            # 将重复文件拼接到日志信息中发送至UI
            log = f'[{str(datetime.now())[:-3]}] [WARNING]:  [重复文件]:  [{repeat_name} ------ {old_name}]'
            self.log_signal.emit(log, self.pgb_value, (repeat_base,))  # 发送日志到UI显示
            self.logger.warning(f'[重复文件]: [{repeat_name} ------ {old_name}] \n')  # 将日志写入文件

    def get_result(self, filename):
        """
        文件的处理, 获取文件的元数据title利用dict的key值不能重复的特性,将文件title作为key,
        文件的绝对路径作为value,判断key是否在dict中,如果key不存在将key和value存入字典,
        如果key已存在说明文件重复, 根据key取出value值和当前文件进行比对所占空间大小,将低质量的重复文件
        名存入result_list列表中, 将文件名相同但艺术家不同的文件名存入user_check_result列表中，由用户自行确认，
        并将重复的文件生成日志信息通过qt自定义信号发送至UI显示,同时将日志写入文件
        :param filename: str 绝对路径文件名
        :return: None
        """
        try:
            ext_name = splitext(filename)[1].lower()  # 切割文件名获取文件扩展名
            if ext_name not in self.support_type:  # 判断文件是否为本类支持的类型
                return
            self.pgb_value += 1  # 进度值加一
            if "铃声" in filename:  # 如果文件是铃声不做处理
                self.log_signal.emit(None, self.pgb_value, None)  # 发送进度值
                return
            filename = filename.replace("\\", "/")  # 替换路径中的反斜杠
            filename = self.change_name(filename, ext_name)  # 修改文件夹中文件的名称
            if not exists(filename):  # 判断文件是否存在
                return
            meta_data = self.get_meta_data(filename, ext_name)  # 获取文件元数据
            # 部分文件元数据title和artist为空，将文件名切片后作为title和artist存入文件元数据中
            meta_data = self.change_mate_data(meta_data, filename, ext_name)
            title = meta_data['title']  # 从元数据字典中取出文件title

            # -----------------------------------------------------------------------------------------
            # 精确查找, 判断title如果不为空, 文件名作为key, 判断key是否在file_title_dict字典中
            if title and title in self.file_title_dict.keys():
                # 获取字典中同一title对应的多个相似文件列表,二维列表中每个列表存放了文件的绝对路径文件名称和artist信息
                file_list = self.file_title_dict[title]
                for i in file_list:  # 遍历相似文件列表, 取出每一个文件和当前文件比较
                    old_file = i[0]  # 取出之前出现过的文件名
                    old_artist = i[1]  # 取出文件artist
                    file_artist: object = meta_data['artist']  # 取出当前文件的artist
                    if not file_artist:  # 如果当前文件艺术家信息为空
                        file_artist = " "  # 赋值为空格
                    if not old_artist:  # 如果之前已出现过的文件艺术家信息为空
                        old_artist = " "  # 赋值为空格
                    if filename != old_file:  # 判断当前文件和重复文件的文件名是否不相等
                        # 根据文件大小或者相同文件不同艺术家等做处理
                        self.estimate_repeat(filename, file_artist, old_file, old_artist, title)
            else:
                # 如果key不在file_title_dict字典中，将key和value存入file_title_dict
                self.file_title_dict.update({title: [[filename, meta_data['artist']]]})
                self.log_signal.emit(None, self.pgb_value, None)  # 可能没有重复文件, 发送进度值

            # ----------------------------------------------------------------------------------------
            # 模糊查找, 拿当前文件title和每一个文件title匹配相似度
            if title and meta_data['artist'] and self.fuzzy_query_status:  # 判断title和artist是否为空, 并且是否开启模糊查找
                for key in self.file_title_dict.keys():  # 遍历获取每一个文件title
                    file = self.file_title_dict[key][0][0]  # 取出文件名
                    file_artist = self.file_title_dict[key][0][1]  # 取出文件artist
                    title_eq_rate = self.get_equal_rate(title, key)  # 比较两个文件title相似度
                    if title_eq_rate >= 0.76 and filename != file:  # 如果相似度大于等于0.76并且两个文件名不相等
                        if title == key:  # 如果两个文件title相等
                            artist = meta_data['artist']  # 取出当前文件artist
                            self.estimate_repeat(filename, artist, file, file_artist, title)  # 判断文件是否重复或相似
                        else:
                            # 判断当前文件名是否不在相似文件列表和重复文件列表中
                            if filename not in self.user_check_result and filename not in self.result_list:
                                self.user_check_result.append(filename)  # 条件成立将文件追加到相似文件列表中
                                self.user_check_result_cnt += 1  # 相似文件计数加一
                            # 判断与当前文件文件名相似的文件是否不在相似文件列表和重复文件列表中
                            if file not in self.user_check_result and file not in self.result_list:
                                self.user_check_result.append(file)  # 条件成立将文件追加到相似文件列表中
                                self.user_check_result_cnt += 1  # 相似文件计数加一
                            self.send_result(filename, file)  # 将相似文件的文件名发送至UI显示
        except Exception as e:
            self.log_signal.emit(None, self.pgb_value, None)  # 出现异常发送进度值
            self.logger.error(f"[{filename} --------- {e}] \n")  # 出现异常写进日志文件

    def estimate_repeat(self, filename, file_artist, old_file, old_artist, title):
        """
        判断文件是重复文件还是相似文件
        :param filename: str 当前文件绝对路径文件名
        :param file_artist: str 当前文件artist
        :param old_file: str 与当前文件名相似的文件名
        :param old_artist: str 与当前文件名相似的文件artist
        :param title: str 当前文件title
        :return: tuple
        """
        if file_artist == old_artist or file_artist in \
                old_artist or old_artist in file_artist:  # 判断艺术家是否相等或相互包含
            size_a = getsize(old_file)  # 获取重复文件占用空间大小
            size_b = getsize(filename)  # 获取当前文件占用空间大小
            if size_a >= size_b:  # 比对文件占用空间大小
                if filename in self.user_check_result:  # 如果当前文件在相似文件列表中
                    self.user_check_result_cnt -= 1  # 相似文件计数减一
                    ind = self.user_check_result.index(filename)  # 查找当前重复文件在相似文件列表中的索引
                    self.user_check_result.pop(ind)  # 将当前重复文件移除相似文案金列表中
                if filename not in self.result_list:  # 判断当前重复文件是否在重复文件列表中
                    self.result_cnt += 1  # 重复文件计数加一
                    self.result_list.append(filename)  # 将占用空间小的或者质量低的文件存入重复文件列表中
                    self.send_result(repeat_name=filename, old_name=old_file)  # 发送比对结果至UI显示
            else:
                if old_file in self.user_check_result:  # 判断文件是否在相似文件列表中
                    self.user_check_result_cnt -= 1  # 相似文件计数减一
                    ind = self.user_check_result.index(old_file)  # 查找当前重复文件在相似文件列表中的索引
                    self.user_check_result.pop(ind)  # 将当前重复文件移除相似文案金列表中
                if old_file not in self.result_list:
                    self.result_cnt += 1  # 重复文件计数加一
                    self.result_list.append(old_file)  # 将占用空间小的或者质量低的并且歌手相同的文件存入重复文件列表中
                    self.file_title_dict[title][0][0] = filename  # 将高质量的文件名把file_title_dict中原来低质量的文件名替换掉
                    self.file_title_dict[title][0][1] = file_artist  # 将高质量的文件artist存入列表中
                    self.send_result(repeat_name=old_file, old_name=filename)  # 发送比对结果至UI显示
        else:  # 如果艺术家不相等的情况
            # 如果两个文件同时在相似文件列表中说明有重复比对的情况，直接返回
            if old_file in self.user_check_result and filename in self.user_check_result:
                return
            # 如果相似文件不在相似文件列表和重复文件列表中
            if old_file not in self.user_check_result and old_file not in self.result_list:
                self.user_check_result.append(old_file)  # 将文件追加到相似文件列表中
                self.user_check_result_cnt += 1  # 相似文件计数加一
            # 如果当前文件不在相似文件列表和重复文件列表中
            if filename not in self.user_check_result and filename not in self.result_list:
                self.user_check_result.append(filename)  # 将文件追加到相似文件列表中
                self.user_check_result_cnt += 1  # 相似文件计数加一
                self.file_title_dict[title].append([filename, file_artist])  # 将当前文件名和艺术家追加到字典title对应的列表中
            self.send_result(filename, old_file)  # 发送结果至UI显示

    def again_check(self, title: object) -> object:
        """
        再次确认文件title中是否有无意义的字符
        :rtype: object
        :param title: str 文件title
        :return: str title
        """
        title = title.strip()  # 去除title头尾空格
        if 'feat' in title:  # 判断'feat'是否在title中
            title = str.split(title, 'feat')[0].strip()  # 按'feat'切割取索引为0的元素
        if 'Feat' in title:  # 判断'Feat'是否在title中
            title = str.split(title, 'Feat')[0].strip()  # 按'Feat'切割取索引为0的元素
        if 'DJ慢摇嗨曲' in title:  # 判断'DJ慢摇嗨曲'是否在title中
            title = str.replace(title, 'DJ慢摇嗨曲', '')  # 替换'DJ慢摇嗨曲'为空
        if 'DJ' in title and '版' in title:  # 判断类似如"DJ何鹏版"是否在title中
            end_ind = str.index(title, 'D')  # 获取"D"字符的索引作为截取字符串的结束索引
            if str.index(title, 'J') - end_ind != 1:  # 如果"J"的索引减去"D"的索引不等于一说明title中还有"D"字符在其中
                sub_title = title.replace(title[end_ind], '', 1)  # 替换别的"D"字符为空
                end_ind = sub_title.index('D') + 1  # 再重新查找"D"字符的索引作为截取字符串的结束索引
            title = title[:end_ind].strip()  # 截取字符串从索引0开始到"D"的索引结束并去除前后空格
        my_re2 = re_compile(r"[\u4e00-\u9fa5]", S)  # 将字符串形式编译为正则表达式对象，匹配汉字的正则表达式
        my_re3 = re_compile(r"[a-zA-Z]", S)  # 匹配英文字母的正则表达式
        res2 = findall(my_re2, title)  # 搜索字符串，以列表类型返回全部能匹配的子串
        res3 = findall(my_re3, title)  # 搜索字符串，以列表类型返回全部能匹配的子串
        my_re5 = re_compile(r"[\d.]", S)  # 将字符串形式编译为正则表达式对象， 匹配数字和.的正则表达式
        res5 = findall(my_re5, title)  # 搜索字符串，以列表类型返回全部能匹配的子串
        # 如果title为中文并且title中没有英文字符, 如果有英文长度小于中文长度,并且空格在title中
        if res2 and (not res3 or len(res3) < len(res2)) and ' ' in title:
            titles = title.split(' ')  # 按空格切割
            max_len = len(titles[0])  # 假设数组索引0的元素在数组所有元素中长度最大
            for i in titles:  # 遍历数组获取每一个元素
                if len(i) >= max_len:  # 用数组索引0的元素和每个元素比较
                    title = i  # 取长度最长的字符串为title
        if '3D' in title and res5:  # 判断"3D"是否在title中
            ind = res5.index('3')  # 查找"3"在匹配数字正则表达式的结果列表中的索引
            res5.pop(ind)  # 匹配数字正则表达式返回的结果列表将"3"移除
        res5_len = len(res5)  # 获取列表长度
        if res5_len <= 2 and res2:  # 判断长度大于等于2并且title为中文
            for i in res5:  # 遍历数字正则表达式返回的列表
                title = str.strip(title, i)  # 如果title的前后为数字将数字去除
        elif res5_len == 3 and '.' in res5 and res2:  # 如果长度为3并且.在title中并且title为中文
            for i in res5:  # 遍历数字正则表达式返回的列表
                title = str.strip(title, i)  # 去除title前后的.或者数字
        if res2 and res3:  # 如果title中有中文和英文
            res2_len = len(res2)  # 获取中文的长度
            res3_len = len(res3)  # 获取英文的长度
            if res2_len > res3_len and (' ' in title or '.' in title):  # 判断中文的长度是否大于英文的长度并且title中有空格符或者.
                for i in res3:  # 遍历英文字符正则表达式返回的列表
                    if '3D' in title and i == 'D':  # 如果"3D"在title中
                        continue  # 跳过循环不做处理
                    title = str.replace(title, i, '')  # 将英文字符替换为空
            elif res3_len > res2_len and (' ' in title or '.' in title):  # 判断英文的长度是否大于中文的长度并且title中有空格符或者.
                for i in res2:  # 遍历中文正则表达式返回的列表
                    title = str.replace(title, i, '')  # 将title中的中文替换为空
            # 判断如果title中的中文长度等于英文长度并且title中有数字并且空格府和.在title中
            elif res3_len == res2_len and bool(search(r'\d', title)) and (' ' in title or '.' in title):
                for i in title:  # 遍历title
                    if str.isdigit(i):  # 判断i是否为数字
                        title = str.replace(title, i, '')  # 将title中数字替换为空
        return title  # 将处理后的title返回

    def check_char(self, title=None, artist=None):
        """
        符号校验, 处理title中部分无意义的字符
        :param title: str 文件title
        :param artist: str 文件artist
        :param cnt: int 递归调用自己的次数
        :return: str title
        """
        try:
            # 处理title中类似 "01-冻结这份爱-罗羽辰+萌萌音" 字符串去除开头的数字
            # 如果字符串第一个元素和第二个元素为数字,并第三个元素不为数字
            if str.isdigit(title[0]) and str.isdigit(title[1]) and not str.isdigit(title[2]):
                if title[2] == '.' or title[2] == '-':  # 如果title第三个元素为'.' 或者'-'
                    title = title[3:]  # 从第四个元素开始截取到结束替换title
            elif str.isdigit(title[0]) and not str.isdigit(title[1]):  # 如果第一个元素为数字并且第二个元素不为数字
                if title[1] == '.' or title[1] == '-':  # 如果第二个元素为'-' 或者'.'
                    title = title[2:]  # 从第三个元素开始截取到结束替换title
            if '《' in title and '》' in title:  # 如果'《》'在title中, 类似 "威仔、阿夏-《怕爱你太明显》"
                start_ind = str.index(title, '《')  # 查找'《'在title中的索引,作为截取字符串的开始索引
                end_ind = str.index(title, '》')  # 查找'》'在title中的索引， 作为截取字符串的结束索引
                title = title[start_ind + 1: end_ind]  # 从查找到的开始和结束索引截取字符串替换title
            if '-' in title:  # 如果'-'在title中, 类似 "你从不知道-刘增瞳&箱子君"
                titles = str.split(title, '-')  # 按'-' 切割字符串
                if artist and titles[0][0] in artist and len(titles) == 2:  # 如果艺术家信息不为空并且title的第一个字符在艺术家信息中
                    title = titles[1]  # 取'-' 后面的元素替换title
                else:
                    title = titles[0]  # 否则取'-'前面的元素作为title
                # 如果title中是否有多个'-', 类似"Smile.DK - Doo-Be-Di-Boy.flac", 并且艺术家信息不为空并且title第一个元素在艺术家信息中
                if len(titles) >= 4 and artist and titles[0][0] in artist:
                    titles.pop(0)  # 移除数组第一个为艺术家信息的元素
                    title = '-'.join(titles).strip('-')  # 拼接数组中所有元素替换title
                # 如果title中是否有多个'-', 并且艺术家信息不为空, 并且title中一个元素不在艺术家信息中
                elif len(titles) >= 4 and artist and titles[0][0] not in artist:
                    title = '-'.join(titles).strip('-')  # 拼接数组中所有元素替换title
            my_re = re_compile(r'[♡+=*&^@!#$%_—<>?《。？！|…:（）、~【】·「」/{}》\[\]()]', S)  # 将字符串形式返回正则表达式对象
            res: List[Any] = findall(my_re, title)  # 将匹配到的结果以列表返回
            if res:  # 判断列表是否为空
                start_ind = str.index(title, res[0])  # 获取匹配结果索引0的元素在title中的索引位置作为截取字符串的开始索引
                end_ind = str.index(title, res[-1])  # 获取匹配结果索引-1的元素在title中的索引位置作为截取字符串的结束索引
                if start_ind == 0 and end_ind == len(title) - 1:  # 判断如果开始索引等于0并且结束索引为-1，
                    title = title[1:-1]  # 类似 "(花间醉DJ名龙版)" 取符号中间的元素替换现有title
                elif start_ind == 0:  # 如果索引为0
                    title = title[end_ind + 1:]  # 类似"(Stephan F Remix)Play That Game"从最后一个符号开始截取替换title
                elif title[end_ind] == title[-1]:  # 如果结束索引为-1
                    title = title[:start_ind]  # 类似 "孟婆的碗（抖音版）" 从头截取到有符号的位置替换title
                elif title[start_ind] == title[end_ind]:  # 如果开始索引等于结束索引
                    if len(title) >= 2 and start_ind < len(title) // 2:  # 判断如果符号在title中靠左边位置
                        title = title[start_ind + 1:]  # 类似"feat.颖宝儿）爱若专一"取符号右边子串替换title
                    elif len(title) >= 2 and start_ind > len(title) // 2:  # 判断如果符号在title中靠右边位置
                        title = title[:start_ind]  # 类似 "雁声晚》" 取符号右边子串替换title
                    else:  # 如果符号刚好在title中间位置
                        title = title.replace(title[start_ind], '')  # 替换符号为空
                elif f"{title[:start_ind]}{title[end_ind + 1:]}" and f"{title[:start_ind]}{title[end_ind + 1:]}" != " ":
                    sub_str = title[0:start_ind].strip()
                    if artist and sub_str in artist or artist in sub_str:
                        title = title[start_ind + 1: end_ind]
                    else:
                        title = f"{title[0:start_ind]}{title[end_ind + 1:]}"
                else:
                    for i in res:  # 如果以上条件都不成立替换所有符号为空
                        title = str.replace(title, i, '')
                title = self.again_check(title)  # 再次确认title中有无其他无意义字符
            else:
                title = self.again_check(title)  # 如果title中没有无意义的符号再次确认有没有其他无用字符
            return title.strip()  # 去除title前后空格返回
        except Exception:
            return title
        # 汉字表达式：[\u4e00-\u9fa5]
        # 拼音表达式：[Aa-zZāáǎàōóǒòēéěèīíǐìūúǔùüǖǘǚǜńňǹḿmɡ]*
        # 字符表达式：[a-zA-Z0-9_]
        # 包含中英文标点符号和其他特殊符号的表达式：[\W]

    def get_equal_rate(self, str1, str2):
        """
        判断两个字符串的相似率
        :param str1: str 字符串1
        :param str2: str 字符串2
        :return: float
        """
        if str1 and str2:  # 判断字符串是否为空
            return SequenceMatcher(None, str1, str2).quick_ratio()  # 比较字符串相似度
        else:
            return 0.0  # 字符串为空返回0.0

    def change_artist(self, artist):
        """
        修改艺术家信息中的无意义字符
        :param artist: str 修改之前的artist
        :return: str 修改后的aritst
        """
        if not artist:  # 如果字符串为空
            return ' '  # 返回空格
        artist = artist.strip()  # 去除字符串前后空格
        # 无意义的字符, 前12个元素优先成对判断, 如果没有成对出现按单个判断, 后7个元素出现替换为'、'
        unvalued_char = ['(', ')', '（', '）', '[', ']', '【', '】', '<', '>', '《', '》',
                         '/', '&', '+', ',', '_', 'VS', 'Live']
        i = 0
        while i in range(len(unvalued_char)):  # 遍历数组
            if i >= len(unvalued_char):
                break
            # 前12个元素判断是否成对出现在artist中
            if i <= 11 and unvalued_char[i] in artist and unvalued_char[i + 1] in artist:
                start_ind = str.index(artist, unvalued_char[i])  # 查找符号在artist中的索引位置
                end_ind = str.index(artist, unvalued_char[i + 1])  # 查找符号在artist中的索引位置
                if start_ind == 0 and end_ind == -1:  # 如果符号位于artist第一个元素和末尾的元素
                    artist = artist[start_ind + 1: end_ind]  # 取符号中间的字串替换artist
                elif start_ind == 0:  # 如果第一个符号位于artist第一个元素
                    artist = artist[end_ind + 1:]  # 从第二个符号出现的下一个元素截取到末尾
                elif end_ind == len(artist) - 1:  # 如果第二个符号位于artist末位元素
                    artist = artist[: start_ind]  # 从开始截取到第二个符号出现的前一个元素
                i += 2  # 数组遍历的索引值加2
            elif i <= 11 and unvalued_char[i] in artist:  # 如果符号没有成对出现判断单个符号是否在artist中
                artist = str.replace(artist, unvalued_char[i], '')  # 如果单个符号出现直接替换为空
                i += 1
            if 11 < i < len(unvalued_char) and unvalued_char[i] in artist:  # 数组中后7个元素出现在artist中替换为'、'
                artist = str.replace(artist, unvalued_char[i], '、')
                i += 1
            else:
                i += 1
        return artist.strip('、').strip()  # 将处理后的artist返回

    def change_mate_data(self, meta_data=None, filename=None, ext_name=None):
        """
        修改文件的元数据，通过TinyTag获取文件元数据后部分文件title和artist为空，或者有些其他字符在title中
        调用filename_to_meta函数处理,返回文件名和艺术家再调用edit_mate_data函数将数据写进文件元数据中，
        同时更新文件元数据字典，将字典返回
        :param meta_data: dict 文件元数据
        :param filename: str 绝对路径的文件名
        :param ext_name: str 文件扩展名
        :return: dict 文件元数据字典
        """
        try:
            old_title = meta_data['title']  # 取出文件title
            old_artist = meta_data['artist']  # 取出文件artist
            old_album = meta_data['album']  # 取出文件album
            if old_title and self.is_ascii(old_title):  # 判断title是否有ascii字符
                new_title = self.ascii_to_utf8(old_title)  # 将ascii字符转换为'utf-8'编码
            else:
                new_title = old_title
            if old_artist and self.is_ascii(old_artist):  # 判断artist是否有ascii字符
                new_artist = self.ascii_to_utf8(old_artist)  # 将ascii字符转换为'utf-8'编码
            else:
                new_artist = old_artist
            if old_album and self.is_ascii(old_album):  # 判断album是否有ascii字符
                old_album = self.ascii_to_utf8(old_album)  # 将ascii字符转换为'utf-8'编码
                meta_data['album'] = old_album  # 更新文件元数据字典album
            if new_title and new_title != ' ':  # 判断title是否为空
                new_title = self.check_char(old_title, old_artist)  # 处理title中无意义字符
            if new_artist and new_artist != ' ':  # 判断artist是否为空
                new_artist = self.change_artist(old_artist)  # 处理artist中无意义字符
            # 判断title是否为空或者title字符串不在文件名中,或者artist是否为空或者artist是否在文件中
            if not new_title or new_title not in filename or not new_artist or new_artist not in filename:
                title, artist = self.filename_to_meta(filename)  # 通过截取文件名来获得title、artist
                if not new_title:  # 判断元数据字典中的title是否为空
                    if old_album and old_album in filename and old_album != ' ':  # 判断专辑名是否为空，是否在文件名中,如果在文件名中说明为同名专辑
                        new_title = old_album.strip()  # 是同名专辑用专辑名替换title
                    else:
                        new_title = title  # 否则将通过截取文件名得到的title替换元数据中字典中的title
                elif new_title not in filename:  # 判断元数据字典中的artist是否在文件名中
                    new_title = title  # 将通过截取文件名获得的title替换元数据字典中的title
                if not new_artist:  # 判断元数据字典中的artist是否为空
                    new_artist = artist  # 如果为空将通过截取文件名获得的artist替换元数据字典中的artist
                elif new_artist not in filename:  # 如果元数据字典中的artist不在文件名中
                    artist = self.change_artist(artist)  # 通过截取文件名获得的artist处理其中的无意义字符
                    if new_artist != artist:  # 如果元数据字典中的artist不等于通过截取文件名获得的artist
                        new_artist = artist  # 将通过截取文件名获得的artist替换元数据字典中的artist
            if new_title and old_title != new_title:  # 判断通过截取文件名获得title是否为空并且元数据字典中title不等与通过截取文件名获得title
                meta_data['title'] = new_title.strip()  # 将通过截取文件名获得title更新到元数据字典中
            if new_artist and old_artist != new_artist:  # 判断通过截取文件名获得artist是否为空并且元数据字典中artist不等与通过截取文件名获得artist
                meta_data['artist'] = new_artist.strip('、').strip()  # 将通过截取文件名获得artist更新到元数据字典中
            # 判断通过截取文件名获得title是否为空并且元数据字典中title不等与通过截取文件名获得title
            # 或者通过截取文件名获得artist是否为空并且元数据字典中artist不等与通过截取文件名获得artist
            if (new_title and old_title != new_title) or (new_artist and old_artist != new_artist):
                self.edit_mate_data(filename, ext_name, meta_data)  # 将文件元数据写入文件
            return meta_data  # 将更新后的元数据字典返回
        except Exception as e:  # 捕捉异常
            self.logger.error(e)  # 出现异常写进日志文件
            title, artist = self.filename_to_meta(filename)  # 出现异常通过截取文件名获取title和artist
            meta_data['title'] = title.strip()  # 将取到的title更新到元数据字典
            meta_data['artist'] = artist.strip()  # 将取到的艺术家更新到元数据字典中
            return meta_data  # 将元数据字典返回

    def edit_mate_data(self, filename, ext_name, info_dict):
        """
        判断文件类型，将元数据写入文件
        :param filename: str 绝对路径文件名
        :param ext_name: str 文件扩展名
        :param info_dict: dict 文件元数据字典
        :return: None
        """
        try:
            if ext_name not in self.id3_type or ext_name not in self.media_file_type:  # 判断文件是否为本类支持写入元数据的类型
                return
            res = None  # 初始化res用来保存各函数返回值
            if ext_name in self.id3_type:  # 判断文件是否支持ID3
                res = self.modified_id3(filename, info_dict)  # 将元数据写入文件ID3对象
            if ext_name in self.media_file_type:  # 判断文件是否为MediaFile支持的类型
                res = self.edit_media_metadata(filename, info_dict)  # 将元数据写入文件
            if res:  # 判断返回值是否为True，为True文件元数据写入成功
                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [编辑文件元数据成功]:  [{filename}]'  # 日志信息
                self.logger.info(f' [编辑文件元数据成功]:  [{filename}] \n')  # 将日志写入文件
                self.log_signal.emit(log, None, None)  # 发送日志到UI
            else:  # 否则返回值为False,元数据写入失败
                log = f'[{str(datetime.now())[:-3]}] [ERROR]:    [文件元数据编辑失败]:  [{filename}]'  # 异常日志
                self.log_signal.emit(log, None, None)  # 发送日志到UI
                self.logger.error(f'[文件元数据编辑失败]:  [{filename} \n')  # 将异常写进日志文件
        except Exception as e:  # 异常捕捉
            if ext_name == '.mp3':  # 对于部分mp3文件修改元数据会出现异常的换一种方式修改
                res = self.edit_mp3_meta(filename, info_dict)  # 修改mp3元数据
            elif ext_name == '.mp4' or ext_name == '.m4a':  # 如果是mp4或m4a文件
                res = self.embed_mp4_metadata(filename, info_dict)  # 调用embed_mp4_metadata函数写入元数据
            elif ext_name == '.ogg':  # 如果是ogg文件
                res = self.add_ogg_metadata(filename, info_dict)  # 调用add_ogg_metadata函数写入元数据
            elif ext_name == '.flac':  # 如果是falc文件
                self.edit_flac_metadata(filename, info_dict)  # 调用edit_flac_metadata函数写入元数据
            if res:  # 判断返回值是否为True，为True写入元数据成功
                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [编辑文件元数据成功]:  [{filename}]'  # 日志信息
                self.logger.info(f' [编辑文件元数据成功]:  [{filename}] \n')  # 将日志写入文件
                self.log_signal.emit(log, None, None)  # 发送日志到UI
            else:  # 否则返回值为False，元数据写入失败
                log = f'[{str(datetime.now())[:-3]}] [ERROR]:    [编辑文件元数据失败]:  [{e}]'  # 异常日志
                self.log_signal.emit(log, None, None)  # 发送日志到UI
                self.logger.error(f'[编辑文件元数据失败]:  [{e} \n')  # 将异常写进日志文件

    def edit_mp3_meta(self, filename, info_dict):
        """
        处理部分mp3文件修改元数据出现异常时重新修改mp3文件元数据
        :param filename: str 绝对路径文件名
        :param info_dict: dict 文件元数据信息字典
        :return: bool
        """
        try:
            audiofile = load(filename)  # 加载文件
            if audiofile:  # 判断是否为空
                audiofile.initTag()  # 初始化文件的Tag
            if info_dict['artist']:  # 判断字典中artist是否为空
                audiofile.tag.artist = u'{}'.format(info_dict['artist'])  # 歌手或艺术家
            if info_dict['title']:  # 判断字典中title是否为空
                audiofile.tag.title = u'{}'.format(info_dict['title'])  # 文件标题
            audiofile.tag.save()  # 修改后保存
            return True  # 写入成功无异常返回True
        except Exception:  # 异常捕捉
            return False  # 写入失败出现异常返回False

    def filename_to_meta(self, filename):
        """
        通过TinyTag类获取不到文件元数据,或出现异常的文件调用此函数得到title和artist
        :param filename: str 绝对路径的文件名
        :return: str 文件名
        """
        try:
            name = basename(filename)[::-1]  # 去除文件路径，只要完整的文件名,并翻转文件名字符串
            name = '.'.join(name.split('.')[1:])  # 通过’.'切割字符串并分片，获取从索引1到结束的所有元素
            name = name[::-1]  # 再翻转字符串
            if '(DJ版)' in name or '- DJ版' in name or 'DJ版' in name:  # 文件名中无意义的字符
                for i in ['(DJ版)', '- DJ版', 'DJ版']:  # 遍历无意义字符数组
                    if i in name:  # 判断无意义字符是否在name中
                        name = str.replace(name, i, '').strip()  # 出现无意义字符替换为空
                    elif i in name.lower():  # 将大写无意义字母转换为小写字符并判断是否在name中
                        name = str.replace(name, i.lower(), '')  # 将小写无意义字母和字符替换为空
            names = name.split('-')  # 按'-'切割, 得到字符串数组
            if names[0]:  # 如果长度大于等于2
                artist = names[0].strip()  # 获取第一个元素作为文件歌手信息
            else:
                artist = ' '  # 否则文件歌手信息为空串
            # 如果长度大于等于3并且'Dj'或者'Remix'在数组最后一个元素中
            if len(names) >= 3 and ('Dj' in names[-1] or 'Remix' in names[-1]):
                title = names[-2]  # 取数组倒数第二个元素为title
            elif len(names) >= 1:  # 如果数组长度大于等于1
                title = names[-1]  # 取数组最后一个元素为title
            else:
                title = ' '  # 否则title为空串
            if artist:  # 判断artist是否为空
                artist = artist.strip().strip('.').strip('-').strip()  # 去除artist前后'.'和'-'和空格
            if title:  # 判断title是否为空
                title = title.strip()  # 去除title前后空格
            title = self.check_char(title, artist)  # 处理title中无意义字符
            if not title:  # 如果处理后title为空
                title = name  # title等于截取的name
            title = title.strip().strip('.').strip('-').strip()  # 去除title中的'.''-'和空格
            return title, artist  # 返回字符串，即最终得到的文件名和艺术家
        except Exception as e:  # 异常捕捉
            self.logger.error(e)  # 将异常写进日志文件

    def one_key_remove(self):
        """
        一键删除重复文件
        :return: int
        """
        try:
            pgb_value: int = 0
            des_path = f"{self.base_path}重复文件/".replace('\\', '/')  # 存储重复文件的文件夹绝对路径
            if exists(des_path):  # 判断路径是否存在
                files = listdir(des_path)  # 获取路径下的所有文件
                for file in files:  # 遍历files获取每一个重复文件
                    file = f'{des_path}{file}'  # 拼接文件的绝对路径
                    if exists(file) and isfile(file):  # 判断文件是否存在
                        remove(file)  # 删除文件
                        pgb_value += 1  # 进度值加一
                        log = f'[{str(datetime.now())[:-3]}] [INFO]:     [删除成功]:  [{file}]'  # 日志信息
                        self.log_signal.emit(log, pgb_value, None)  # 发送日志到UI
                        self.logger.info(f" [删除成功]: [{file}] \n")  # 将日志写进日志文件
                    elif isdir(file):  # 判断是否为文件夹
                        for f in listdir(file):  # 遍历获取文件
                            remove(f"{file}{'/'}{f}")  # 删除文件
                            pgb_value += 1  # 进度值加一
                            log = f'[{str(datetime.now())[:-3]}] [INFO]:     [删除成功]:  [{f}]'  # 日志信息
                            self.log_signal.emit(log, pgb_value, None)  # 发送日志到UI
                            self.logger.info(f" [删除成功]: [{f}] \n")  # 将日志写进日志文件
                        rmtree(file, ignore_errors=True)  # 删除子文件夹
                    else:  # 否则文件不存在
                        log = f'[{str(datetime.now())[:-3]}] [ERROR]:    [文件不存在]:  [{file}]'  # 拼接日志信息
                        self.log_signal.emit(log, pgb_value, None)  # 发送日志到UI
                        self.logger.error(f"[文件不存在]: [{file}] \n")  # 写进日志文件
            if exists(des_path) and not listdir(des_path):  # 判断文件夹是否存在并且文件夹下是否为空
                rmtree(des_path)  # 没有文件删除文件夹
                return 1  # 没有异常返回1
        except Exception as e:  # 异常捕捉
            log = f'[{str(datetime.now())[:-3]}] [ERROR]:    [删除失败]:  [{file}]'  # 拼接日志信息
            self.log_signal.emit(log, pgb_value, None)  # 发送日志到UI
            self.logger.error(f"[删除失败]: [{file} ------ {e}] \n")  # 将日志写进日志文件
            return 0  # 出现异常返回0

    def recursion_move(self, base_path, result_list, pgb_value):
        """
        递归创建文件夹并移动重复文件
        :param base_path: str 移动文件的目标根路径
        :param result_list: list 文件名列表
        :param pgb_value: int 进度值
        :return: None
        """
        try:
            des_path = base_path  # 目标路径
            if not exists(des_path):  # 如果目标文件夹不存在
                mkdir(des_path)  # 创建文件夹
            num = 1  # 有多次重复的文件无法保存在同一路径,创建子文件夹的次数
            for file in result_list:  # 遍历获取文件名
                pgb_value += 1  # 进度值加一
                if not exists(file):  # 如果文件不存在
                    log = f'[{str(datetime.now())[:-3]}] [ERROR]:    [文件不存在]:  [{file}]'  # 拼接日志信息
                    self.log_signal.emit(log, pgb_value, None)  # 发送日志到UI
                    self.logger.error(f"[文件不存在]: [{file}] \n")  # 将日志写进日志文件
                    continue  # 跳过本次循环进入下次循环
                base_name = basename(file)  # 获取不带路径的文件名
                if base_name in listdir(des_path):  # 判断文件是否已经在目标路径下存在
                    if des_path == f'{self.base_path}{"同名不同艺术家文件,请自行确认删除其中之一/"}':  # 判断相似文件是否多次重复， 如果相似文件路径下文件已经存在
                        des_path = f"{self.base_path}重复文件/"  # 修改移动的目标路径为音乐根路径下的重复文件目录
                        self.recursion_move(des_path, [file], 0)  # 递归调用自己重新移动该文件
                        continue  # 跳过本次循环
                    while True:
                        num += 1  # 文件重复次数加一
                        des_path = f"{base_path}{num}次重复文件/".replace("\\", "/")  # 拼接第二次重复的目标路径
                        if not exists(des_path):  # 如果文件夹不存在
                            mkdir(des_path)  # 创建文件夹
                            move(file, des_path)  # 移动文件
                            log = f'[{str(datetime.now())[:-3]}] [INFO]:     [移动成功]:  [原路径: "{file}" ------ 目标路径: "{des_path}{base_name}"]'  # 拼接日志信息
                            self.log_signal.emit(log, pgb_value, None)  # 发送日志到UI
                            self.logger.info(
                                f' [移动成功]: [原路径: "{file}" ------ 目标路径: "{des_path}{base_name}"] \n')  # 将日志写进日志文件
                            num = 1  # 重置文件重复次数为1
                            des_path = base_path  # 重置文件移动的目标路径
                            break  # 结束循环
                        elif exists(des_path) and base_name not in listdir(des_path):  # 如果文件夹已存在并且文件不在该路径下
                            move(file, des_path)  # 移动该文件
                            log = f'[{str(datetime.now())[:-3]}] [INFO]:     [移动成功]:  [原路径: "{file}" ------ 目标路径: "{des_path}"]'  # 拼接日志信息
                            self.log_signal.emit(log, pgb_value, None)  # 发送日志到UI
                            self.logger.info(
                                f' [移动成功]: [原路径: "{file}" ------ 目标路径: "{des_path}{base_name}"] \n')  # 将日志写进日志文件
                            num = 1  # 重置文件重复次数为1
                            des_path = base_path  # 重置移动文件的目标路径
                            break  # 结束循环
                        else:
                            continue  # 否则文件已经3次重复,进入下一次循环继续移动
                else:  # 否则目标下没有该文件
                    move(file, des_path)  # 移动文件至目标路径
                    log = f'[{str(datetime.now())[:-3]}] [INFO]:     [移动成功]:  [原路径: "{file}" ------ 目标路径: "{des_path}{base_name}"]'  # 拼接日志信息
                    self.log_signal.emit(log, pgb_value, None)  # 发送日志到UI
                    self.logger.info(f' [移动成功]: [原路径: "{file}" ------ 目标路径: "{des_path}{base_name}"] \n')  # 将日志写进日志文件
                    num = 1  # 重置文件重复次数
        except Exception:  # 异常捕捉
            log = f"[{str(datetime.now())[:-3]}] [ERROR]:    [移动失败]:  [{file}]"  # 拼接日志信息
            self.log_signal.emit(log, pgb_value, None)  # 发送日志到UI
            self.logger.error(f"[移动失败]: [{file}] \n")  # 将日志写进日志文件

    def move_file(self):
        """
        将重复文件移动到用户音乐根目录下的"重复文件/"目录下
        :return: None
        """
        pgb_value = 0  # 初始进度之为1
        if self.result_list:  # 判断重复文件列表是否为空
            des_path = f"{self.base_path}重复文件/".replace("\\", "/")  # 放置重复文件的目录
            self.recursion_move(des_path, self.result_list, pgb_value)  # 调用函数反复移动文件
        if self.user_check_result:  # 判断相似文件列表是否为空
            pgb_value = self.result_cnt  # 移动重复文件的进度值为重复文件总数加上相似文件总数,所以进度值要接着重复文件总数继续累加
            des_path = f"{self.base_path}同名不同艺术家文件,请自行确认删除其中之一/".replace("\\", "/")  # 放置相似文件的目录
            self.recursion_move(des_path, self.user_check_result, pgb_value)  # 调用函数反复移动文件
        self.rm_empty_dir(self.base_path)  # 文件移动完成删除空的文件夹

    def seek(self, base_dir):
        """
        查找重复文件、移动重复文件、删除重复文件、文件按音质分类
        :param base_dir: str 音乐文件根路径
        :return: None
        """
        for root, dirs, files in walk(base_dir):  # 遍历音乐文件根目录下所有资源,获取所有文件
            for file in files:  # 遍历文件列表得到每一个文件
                if splitext(file)[1] in self.support_type:  # 判断文件是否为本类支持的类型
                    self.log_signal.emit(None, None, file)  # 发送文件名至UI显示
        self.seek_repeat(base_dir)  # 调用查找重复文件函数
        self.finished_signal.emit('seek_repeat_finish')  # 查找重复文件完成后发送完成信号至主线程
        while True:
            sleep(0.5)
            if self.th_flag == 1:  # 判断线程执行状态值, 为1时移动重复文件
                if self.user_check_result_cnt or self.result_cnt:  # 判断相似文件总数或者重复文件总数是为0
                    self.move_file()  # 不为0说明有相似或者重复文件, 移动文件
                    self.finished_signal.emit('move_file_finish')  # 移动完成后发送完成信号至主线程
            if self.th_flag == 2:  # 判断线程执行状态值, 为2时执行删除重复文件
                res = self.one_key_remove()  # 删除重复文件
                self.finished_signal.emit(f"remove_finish_{res}")  # 删除完成后发送完成信号至主线程
            elif self.th_flag == 3:  # 判断线程执行状态值, 为3时执行文件按音质分类
                self.ready_sort()  # 执行文件按音质分类
                break  # 结束循环
            elif self.th_flag == 4:  # 判断线程执行状态值,为4时不执行按音质分类
                break  # 结束循环
            self.th_flag = 0  # 重置线程执行状态值为0

    def seek_repeat(self, base_dir):
        """
        递归遍历获取所有文件，并调用查找重复文件函数
        :param base_dir: str 用户传入的音乐文件的根目录
        :return: None
        """
        try:
            if isdir(base_dir):  # 判断用户传入的音乐文件根目录是否为目录
                child_files = listdir(base_dir)  # 获取根目录下所有子文件及子文件夹
                for child_file in child_files[::-1]:  # 遍历child_files得到每一个文件或文件夹
                    file = f"{base_dir}{child_file}".replace("\\", '/')  # 将文件拼接为绝对路径中，并替换路径中的斜杠
                    if isfile(file):  # 判断是否为文件
                        self.get_result(file)  # 查找重复文件
                    elif isdir(file):  # 如果是文件夹
                        file = f"{base_dir}{child_file}/".replace("\\", '/')  # 将文件拼接为绝对路径中，并替换路径中的双斜杠
                        if isdir(file):  # 如果是文件夹
                            # if file == f"{self.base_path}分类失败/":            # 如果分类失败文件夹在音乐根目录下
                            #     continue                                      # 跳过本次循环
                            self.seek_repeat(file)  # 递归获取文件夹下文件再查找
        except Exception as e:  # 捕获异常
            self.logger.error(f"[{e}] \n")  # 将异常写进日志文件

    def is_ascii(self, s) -> bool:
        """
        判断是否为ascii编码字符串
        :param s: ascii str
        :return: bool
        """
        if not s:  # 判断字符串是否为空
            return None
        # return all(ord(c) <= 255 for c in s)      # 判断所有字符是否为ascii编码
        for i in s:  # 遍历字符串获取单个字符
            if i in ['-', '_', '&', ' ', '.']:  # 跳过常见的ascii字符
                continue  # 跳过本次循环
            if ord(i) <= 255:  # 如果有一个字符为ascii编码
                return True  # 返回True
        return False  # 如果循环执行完都没有返回True则说明没有ascii字符，返回False

    def get_tinytag(self, filename, ext_name) -> dict:
        """
        通过tingtag库获取文件元数据信息
        :param filename: str 绝对路径文件名
        :param ext_name: str 文件扩展名
        :return: dict
        """
        try:
            if ext_name not in self.tinytag_type:  # 判断文件是否是TintTag支持的类型
                return  # 不支持的类型结束函数运行
            tag = TinyTag.get(filename)  # 获取文件标签
            tag_dict = tag.as_dict()  # 获取文件标签字典
            return tag_dict  # 返回文件元数据字典
        except Exception:  # 异常捕捉
            return  # 返回None

    def get_meta_data(self, filename, ext_name) -> dict:
        """
        获取文件元数据
        :param filename: str 绝对路径文件名
        :param ext_name: str 文件扩展名
        :return: dict
        """
        try:
            meta_data = {  # 定义一个字典存储文件元数据
                'channels': None,  # 通道数，即声道数
                'samplerate': None,  # 采样率 kHz
                'bitrate': None,  # 比特率 kbps
                'bitdepth': None,  # 位深 bit
                'duration': None,  # 持续时长 s
                'title': None,  # 标题
                'artist': None,  # 歌手、艺术家
                'album': None  # 专辑名
            }
            meta_keys = meta_data.keys()  # 获取元数据字典所有key
            if ext_name in self.support_type:  # 判断是否为本类支持的类型
                tag_dict = self.get_tinytag(filename, ext_name)  # 通过tingtag库获取文件元数据
                info_dict = self.get_tags(filename, ext_name)  # 通过MediaFile库获取文件元数据
                mutagen_dict = self.get_mutagen_meta(filename, ext_name)  # 通过mutagen库获取文件元数据
                mp4_meta = self.get_mp4_metadata(filename, ext_name)  # 获取mp4或者m4a文件标签
                wav_meta = self.get_wav_metadata(filename, ext_name)  # 通过soundfile库获取wav文件元数据
                for key in meta_keys:  # 遍历元数据字典key
                    # 判断字典是否已实例化并且元数据字典的key在文件标签字典中并且文件标签字典的key对应的value不为空
                    if isinstance(tag_dict, dict) and key in tag_dict.keys() and tag_dict[key]:
                        if key == 'bitrate':  # 如果当前key等于'bitrate'
                            tag_dict[key] = int(tag_dict[key])  # 将浮点型'bitrate'转换为int
                        meta_data[key] = tag_dict[key]  # 根据key取出文件标签中的value值并赋值给文件元数据字典中key对应的value值
                    # 如果文件是MediaFile支持的类型并且MediaFile返回的字典已实例化并且当前key在MediaFile返回的字典中并且key对应的value值不为空
                    elif ext_name in self.media_file_type and isinstance(info_dict, dict) and \
                            key in info_dict.keys() and info_dict[key]:
                        meta_data[key] = info_dict[key]  # 将info_dict返回的字典中key对应的value值赋值给当前文件元数据字典key对应的value
                    # 如果文件是SoundFile库支持的类型并且SoundFile返回的字典已实例化并且当前key在SoundFile返回的字典中并且key对应的value值不为空
                    elif ext_name in self.mutagen_type and isinstance(mutagen_dict, dict) and \
                            key in mutagen_dict.keys() and mutagen_dict[key]:
                        meta_data[key] = mutagen_dict[key]  # 将sound_dict字典中key对应的value值赋值给当前文件元数据字典key对应的value
                    # 如果文件是mp4或者m4a格式并且获取MP4、m4a标签返回的字典已实例化并且当前key在mp4_meta字典的key中并且当前key在mp4_meta中对应的value不为空
                    elif (ext_name == '.mp4' or ext_name == '.m4a') and isinstance(mp4_meta,
                                                                                   dict) and key in mp4_meta.keys() and \
                            mp4_meta[key]:
                        # 将mp4_meta中当前key对应的value赋值给元数据字典当前key对应的value
                        meta_data[key] = mp4_meta[key]
                    # 如果文件是wav格式并且获取wav标签返回的字典已实例化并且当前key在wav_mate字典的key中并且当前key在wav_mate中对应的value不为空
                    elif ext_name == '.wav' and isinstance(wav_meta, dict) and key in wav_meta.keys() and wav_meta[key]:
                        meta_data[key] = wav_meta[key]  # 将wav_meta中当前key对应value赋值给元数据字典当前key对应的value
            if meta_data['bitdepth']:  # 判断文件元数据字典的'位深'是否有值
                if ext_name in ['.aiff', '.wav', '.flac']:  # 如果当前文件是数组中的格式
                    sound = SoundFile(filename)  # 获取文件位深，获取文件的声音对象
                    subtype = sound.subtype  # 通过SoundFile的subtype属性获取文件位深
                    if 'PCM' in subtype and '_' in subtype:  # 判断返回的值是否为类似"PCM_16"格式
                        bitdepth = sound.subtype.split("_")[1]  # 取'_'后面的元素作为文件位深
                        if str.isdigit(bitdepth):  # 判断取到的值是否为数字如果是数字将值转换为int
                            meta_data['bitdepth'] = int(bitdepth)  # 更新到字典
            return meta_data  # 返回文件元数据字典
        except Exception as e:  # 异常捕捉
            self.logger.error(f'[获取文件元数据失败]:  [{filename} ---- {e}]')  # 将异常写进日志文件
            return meta_data  # 返回字典

    def file_sort(self, base_path=None):
        """
        对文件按音质分类分别为：标准音质、高品音质、无损音质、Hi_Res高解析音质、Hi_Res母带音质
        :param base_path: str 音乐文件根路径
        :return:  None
        """
        log = None  # 初始化日志信息
        if isdir(base_path):  # 判断是否为文件夹
            child_files = listdir(base_path)  # 获取文件下所有文件
            for file in child_files:  # 遍历文件数组
                file_path = f"{base_path}{file}".replace('\\', '/')  # 拼接文件路径
                if isfile(file_path):  # 判断是否为文件
                    try:
                        ext_name = splitext(file_path)[1]  # 获取文件扩展名
                        if ext_name not in self.support_type:  # 判断文件是否为本类支持的格类型
                            continue  # 跳过本次循环
                        self.pgb_value += 1  # 进度值加一
                        if '铃声' in file_path:  # 判断文件是否为铃声
                            self.log_signal.emit(None, self.pgb_value, None)  # 发送进度值
                            continue
                        meta_data = self.get_meta_data(file_path, ext_name)  # 获取文件元数据
                        channels = meta_data['channels']  # 取出文件的通道数据
                        samplerate = meta_data['samplerate']  # 取出文件的采样率
                        bitrate = meta_data['bitrate']  # 取出文件的比特率
                        bitdepth = meta_data['bitdepth']  # 取出文件的位深
                        file_name = basename(file_path)  # 获取不带路径的文件名
                        if channels and channels > 2:  # 如果通道数大于2说明是多通道文件，单独存一个文件夹
                            des_dir = f"{self.base_path}{channels}{'声道文件/'}"  # 拼接目标文件夹路径
                            des_file = f"{des_dir}{file_name}"  # 拼接目标文件路径
                            if not exists(des_dir) or not isdir(des_dir):  # 判断目标路径文件夹是否存在
                                mkdir(des_dir)  # 不存在就创建
                            if not exists(des_file):  # 判断目标路径文件是否存在
                                move(file_path, des_file)  # 移动到目标文件路径
                                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [分类成功]:  [原路径: "{file_path}" ------ 目标路径: "{des_file}"]'  # 日志
                                self.logger.info(
                                    f' [分类成功]: [原路径: "{file_path}" ------ 目标路径: "{des_file}"] \n')  # 将日志写进日志文件
                        if bitrate and bitrate <= 128:  # 根据比特率分类，128kbps为标准音质
                            des_dir = f"{self.base_path}{'标准音质/'}"  # 拼接目标文件夹路径
                            des_file = f"{des_dir}{file_name}"  # 拼接目标文件路径
                            if not exists(des_dir) or not isdir(des_dir):  # 判断目标文件夹路径是否存在
                                mkdir(des_dir)  # 创建文件夹
                            if not exists(des_file):  # 判断目标路径文件是否存在
                                move(file_path, des_file)  # 移动到目标问价路径下
                                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [分类成功]:  [原路径: "{file_path}" ------ 目标路径: "{des_file}"]'  # 日志
                                self.logger.info(
                                    f' [分类成功]: [原路径: "{file_path}" ------ 目标路径: "{des_file}"] \n')  # 将日志写进日志文件
                        elif bitrate and 128 < bitrate <= 320:  # 320kbps为高品质音质
                            des_dir = f"{self.base_path}{'高品音质/'}"  # 拼接目标文件夹路径
                            des_file = f"{des_dir}{file_name}"  # 拼接目标文件路径
                            if not exists(des_dir) or not isdir(des_dir):  # 判断目标文件夹是否存在
                                mkdir(des_dir)  # 创建文件夹
                            if not exists(des_file):  # 判断目标路径文件是否存在
                                move(file_path, des_file)  # 移动到目标文件夹路径下
                                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [分类成功]:  [原路径: "{file_path}" ------ 目标路径: "{des_file}"]'  # 日志
                                self.logger.info(
                                    f' [分类成功]: [原路径: "{file_path}" ------ 目标路径: "{des_file}"] \n')  # 将日志写进日志文件

                        # 判断文件位深是否等于16bit，并且文件采样率大于等于44.1kHZ并且小于等于48kHZ，并且通道数小于等于2，
                        # 将这类分为无损音质文件
                        elif bitdepth and bitdepth == 16 and (44100 <= samplerate <= 48000) and channels <= 2:
                            des_dir = f"{self.base_path}{'无损音质/'}"  # 拼接目标文件夹路径
                            des_file = f"{des_dir}{file_name}"  # 拼接目标文件路径
                            if not exists(des_dir) or not isdir(des_dir):  # 判断目标文件夹路径是否存在
                                mkdir(des_dir)  # 创建目标文件夹
                            if not exists(des_file):  # 判断目标文件路径下文件是否存在
                                move(file_path, des_file)  # 移动文件
                                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [分类成功]:  [原路径: "{file_path}" ------ 目标路径: "{des_file}"]'  # 日志
                                self.logger.info(' [分类成功]: [原路径: "{0}" ------ 目标路径: "{1}"] \n'.format(file_path,
                                                                                                      des_file))  # 将日志写进日志文件

                        # 判断文件位深是否等于24bit,并且采样率大于等于44.1kHZ并且下雨等于96kHZ,并且文件通道小于等于2
                        # 将此类分为Hi-Res高解析音质文件
                        elif bitdepth and bitdepth >= 24 and (41000 <= samplerate <= 96000) and channels <= 2:
                            des_dir = f"{self.base_path}{'Hi-Res高解析/'}"  # 拼接目标文件夹路径
                            des_file = f"{des_dir}{file_name}"  # 拼接目标文件路径
                            if not exists(des_dir) or not isdir(des_dir):  # 判断目标文件夹路径是否存在
                                mkdir(des_dir)  # 创建文件夹
                            if not exists(des_file):  # 判断目标文件路径下问价是否存在
                                move(file_path, des_file)  # 移动文件
                                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [分类成功]:  [原路径: "{file_path}" ------ 目标路径: "{des_file}"]'  # 日志
                                self.logger.info(
                                    f' [分类成功]: [原路径: "{file_path}" ------ 目标路径: "{des_file}"] \n')  # 将日志写进日志文件

                        # 判断文件位深是否大于等于24bit,并且采样率大于96kHz并且通道数小于等于2
                        # 或者位深为1，采样频率大于等于2.8MHZ，这类文件为DSD文件，将这两类文件分为母带音质
                        elif bitdepth and (bitdepth >= 24 and samplerate > 96000 and channels <= 2) \
                                or (bitdepth == 1 and samplerate >= 2800000):
                            des_dir = f"{self.base_path}{'Hi-Res母带音质/'}"  # 拼接目标文件夹路径
                            des_file = f"{des_dir}{file_name}"  # 拼接目标文件路径
                            if not exists(des_dir) or not isdir(des_dir):  # 判断目标文件夹路径是否存在
                                mkdir(des_dir)  # 创建文件夹
                            if not exists(des_file):  # 判断目标问价路径下文件是否存在
                                move(file_path, des_file)  # 移动文件
                                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [分类成功]:  [原路径: "{file_path}" ------ 目标路径: "{des_file}"]'  # 日志
                                self.logger.info(
                                    f' [分类成功]: [原路径: "{file_path}" ------ 目标路径: "{des_file}"] \n')  # 将日志写进日志文件
                        self.log_signal.emit(log, self.pgb_value, None)  # 发送日志和进度值
                    except Exception as e:  # 异常捕捉
                        if isfile(file_path):  # 如果是文件
                            self.sort_failed.append(file_path)  # 将文件追加到分类失败列表中后续统一移动
                            self.sort_failed_cnt += 1  # 分类失败文件计数加一
                        log = f"[{str(datetime.now())[:-3]}] [ERROR]:    [分类失败]:  [{file_path} ---- {e}]"  # 异常日志
                        self.logger.error(f"[分类失败]:  [{file_path} ---- {e}] \n")  # 将日志发送至UI
                        self.log_signal.emit(log, self.pgb_value, None)  # 发送日志和进度值
                        continue  # 跳过本次循环
                else:  # 否则为文件夹
                    file_path = f"{file_path}{'/'}"  # 拼接文件夹路径的'/'
                    if isdir(file_path):  # 判断是否为文件夹
                        # 这几个文件夹是保存结果的文件夹，不需要从这些文件夹移动文件进行分类
                        if file_path == f"{self.base_path}{'重复文件/'}" or \
                                file_path == f"{self.base_path}{'重复文件/重复文件2/'}" or \
                                file_path == f"{self.base_path}{'同名不同艺术家文件,请自行确认删除其中之一/'}" or \
                                file_path == f"{self.base_path}{'解锁失败/'}" or \
                                file_path == f"{self.base_path}{'分类失败/'}":
                            continue  # 跳过循环
                        self.file_sort(file_path)  # 递归调用自己

    def change_name(self, filename, ext_name):
        """
        修改文件名,比如：'[mqms]', '[mqms2]', '_MQ', '_HQ', '_SQ'等这些字符在文件名中将他们给替换掉
        文件名编码转换, 部分文件名包含ascii字符, 将ascii字符转换为utf-8字符
        :param filename: str 绝对路径文件名
        :param ext_name: str 文件扩展名
        :return: str 修改文件名后的文件绝对路径
        """
        try:
            base_name = basename(filename)  # 获取不带路径的文件名
            name = splitext(base_name)[0]   # 不包含路径和扩展名的文件名
            if self.is_ascii(name):  # 判断文件名是否为ascii字符
                name = self.ascii_to_utf8(name)  # 将ascii字符转换为utf8字符
            dir_path = f"{dirname(filename)}/"  # 按照文件名切割得到文件路径
            with open(filename, 'rb') as f:  # 打开文件
                data = f.read(6)  # 读取6个字节
                if b'ID3' in data and ext_name not in self.id3_type:  # 判断文件是否包含ID3标签并且是tinytag库无法读取的文件类型
                    id3 = ID3(filename)  # 实例化ID3对象
                    ID3.delete(id3)  # 删除文件ID3标签
            # 判断文件名前两个字符是否为数字,类似 "06.孙露 - 漂洋过海来看你", 将此类数字替换为空
            if str.isdigit(name[0]) and str.isdigit(name[1]) and not str.isdigit(name[2]):
                if name[2] == '.' or name[2] == '-':  # 如果第三个字符等于'.'或者'-'
                    name = name[3:]  # 从第四个字符开始截取到末尾
            elif str.isdigit(name[0]) and not str.isdigit(name[1]):  # 如果第一个字符是数字并且第二个字符不是数字
                if name[1] == '-' or name[1] == '.':  # 如果第二个字符为'-'或者'.'
                    name = name[2:]  # 从第三个字符开始截取到末尾
            # 将不包含路径和扩展名的文件名按‘-’号切割， 处理文件名中重复出现艺术家信息的文件
            names = str.split(name, '-')
            length = len(names)  # 字符数组长度
            if length >= 3:  # 如果长度大于3
                for i in range(1, length):  # 遍历字符数组
                    if names[0].strip() in names[i].strip():  # 判断艺术家信息同时出现在文件名中两次的文件
                        # 用第一个元素（一般为艺术家信息）和其他为艺术家信息的元素比较两个艺术家信息占用的字符长度
                        if len(names[0].strip()) <= len(names[i].strip()):  # 将第一个元素和其他元素对比长度
                            names[0] = names[i].strip()  # 如果其他元素长度大于第一个元素的长度用占用字符更多的艺术家信息替换掉占用字符少的艺术家信息
                            names[i] = ''  # 将占用字符少的艺术家信息替换为空
                        else:
                            names[i] = ''  # 第一个元素的艺术家信息占用更多字符，将另一个艺术家信息置为空
                        names[0] = f"{names[0]}{'-'}"  # 给第一个元素拼接一个‘-’，否则文件名中没有‘-’号
                        name = ''.join(names).strip()  # 拼接文件名
            # 部分文件名中会出现一下列表中的一些字符，将这些字符全部替换为空， 这类字符一般出现在文件名末尾
            unvalued_char = [' - 副本', '-副本', '副本', '[mqms]', '[mqms2]', '_MQ', '_HQ', '_SQ', 'SQ', '_[mqms]',
                             '_[mqms2]', 'MQ', 'HQ']
            for i in unvalued_char:  # 遍历数组
                if i in name:  # 如果数组中元素在name中
                    name = str.split(name, i)[0]  # 按无意义字符切割文件名取第一个元素
            name = name.strip()  # 去除文件名前后空格
            # 处理文件名中类似 "慢摇外文重音超嗨旋律歌曲 - 891563485" 一长串数字给去掉
            if len(name) > 6 and all(str.isdigit(n) for n in name[-6:]):  # 截取文件名末尾6个元素判断是否全部为数字
                name = name[::-1]  # 翻转文件名
                for i in name:  # 遍历翻转后的文件名获取每个字符
                    if str.isdigit(i):  # 判断单个字符是否为数字
                        continue  # 跳过本次循环
                    elif not str.isdigit(i):  # 如果遍历到的字符不是数字
                        i_ind = str.index(name, i)  # 查找字符的索引
                        name = name[i_ind:][::-1]  # 从查找到不为数字字符的索引位置开始截取到末尾然后在翻转
                        break  # 结束循环
            name = name.strip()  # 去除文件名前后空格
            new_basename = f"{name}{ext_name}"  # 拼接新的文件名
            des_path = f"{dir_path}{new_basename}"  # 拼接新的绝对路径文件名
            if filename != des_path and not exists(des_path):  # 如果新的文件名不等于以前的文件名并且新的文件名不存在
                rename(filename, des_path)  # 重命名文件
                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [修改文件名成功]:  [原文件名: "{filename}" ------ 新文件名: "{des_path}"]'  # 拼接日志
                self.log_signal.emit(log, 0, None)  # 将日志发送至UI
                self.logger.info(f' [修改文件名成功]: [原文件名: "{filename}" ------ 新文件名: "{des_path}"] \n')  # 将日志写进日志文件

            # 如果新的文件名不等于以前的文件名并且新的文件名已经存在,将文件移动至别的目录后重新修改文件名
            elif filename != des_path and exists(des_path):
                new_dir_path = f"{self.base_path}temp/"  # 拼接新的文件夹路径为用户音乐根目录下temp文件夹
                if not exists(new_dir_path):  # 如果文件夹不存在
                    mkdir(new_dir_path)  # 创建文件夹
                des_path = f"{new_dir_path}{new_basename}"  # 拼接新的文件绝对路径
                if not exists(des_path):  # 判断文件是否存在
                    move(filename, des_path)  # 移动文件
                else:  # 如果文件已经存在说明文件已两次重复
                    num = 2  # 文件重复次数
                    while True:  # 在循环中重复移动并判断文件是否N次重复
                        dir_path = f"{new_dir_path}{num}次重复文件/"  # 拼接2次重复的文件夹路径
                        des_path = f"{dir_path}{new_basename}"  # 拼接文件绝对路径
                        if not exists(des_path):  # 判断文件夹是否存在
                            mkdir(dir_path)  # 创建文件夹
                            move(filename, des_path)  # 移动文件并修改文件名
                            break  # 移动成功后退出循环
                        elif exists(des_path):  # 否则文件再次重复
                            num += 1  # 文件重复次数加一
                            continue  # 继续下一次循环判断
                log = f'[{str(datetime.now())[:-3]}] [INFO]:     [移动并修改文件名成功]:  [原文件名: "{filename}" ------ 新文件名: "{des_path}"]'  # 拼接日志
                self.log_signal.emit(log, 0, None)  # 将日志发送至UI
                self.logger.info(f' [移动并修改文件名成功]: [原文件名: "{filename}" ------ 新文件名: "{des_path}"] \n')  # 将日志写进日志文件
            return des_path  # 将修改后的文件路径信息返回
        except Exception as e:  # 异常捕捉
            self.logger.error(e)  # 将异常写进日志文件
            return filename  # 返回原文件名

    def rm_empty_dir(self, path):
        """
        完成重复文件查找和音质分类后会有一些空的文件夹，将空的文件夹删除
        :param path: str 文件路径
        :return: None
        """
        try:
            dir_list = []  # 存放音乐根目录下所有dir
            for root, dirs, files in walk(path):  # 遍历文件树
                for d in dirs:  # 遍历获取文件树下所有dir
                    dir_list.append(join(root, d))  # 将根路径和dir拼接后存入列表
            for d in dir_list[::-1]:  # 倒叙遍历dir列表
                d = d.replace("\\", "/")  # 替换路径中反斜杠
                if not listdir(d):  # 判断文件夹中是否有文件
                    rmtree(d, True)  # 删除文件夹
                    log = f"[{str(datetime.now())[:-3]}] [INFO]:     [空文件夹删除成功]:  [{d}]"  # 日志信息
                    self.log_signal.emit(log, None, None)  # 发送日志到UI
                    self.logger.info(f" [空文件夹删除成功]: [{d}] \n")  # 将日志写进日志文件
        except Exception as e:  # 捕捉异常
            log = f"[{str(datetime.now())[:-3]}] [ERROR]:    [空文件夹删除失败]:  [{d}]"  # 拼接日志信息
            self.log_signal.emit(log, None, None)  # 将日志法中至UI
            self.logger.error(f"{e} \n")  # 将日志写进日志文件

    def edit_media_metadata(self, filename, info_dict):
        """
        将文件元数据写入文件
        :param filename: str 绝对路径文件名
        :param info_dict: dict 文件元数据
        :return: bool
        """
        try:
            audio = MediaFile(filename)  # 实例化文件元数据对象
            if info_dict['title']:  # 判断传入的字典中title是否为空
                title = info_dict['title']  # 取出文件title
                audio.update({'title': title})  # 将title更新到文件元数据对象中
            if info_dict['artist']:  # 判断传入的艺术家信息是否为空
                artist = info_dict['artist']  # 取出artist
                audio.update({'artist': artist})  # 将艺术家信息更新到文件元数据对象中
            audio.save()  # 保存文件元数据
            return True  # 没有异常返回True
        except Exception:  # 异常捕捉
            return False  # 发生异常返回False

    def get_mp4_metadata(self, filename, ext_name):
        """
        获取mp4、m4a文件的元数据
        :param filename: str 绝对路径文件名
        :param ext_name: str 文件扩展名
        :return: dict 元数据字典
        """
        try:
            if ext_name != '.mp4' and ext_name != '.m4a':  # 如果文件不是mp4和m4a格式
                return  # 返回空
            mp4_audio = MP4(filename)  # 实例化文件元数据对象
            meta = {  # 初始化字典
                'channels': int(mp4_audio.info.channels),  # 获取文件通道数
                'bitdepth': int(mp4_audio.info.bits_per_sample),  # 获取文件位深
                'samplerate': int(mp4_audio.info.sample_rate),  # 获取文件采样率
                'duration': float(mp4_audio.info.length),  # 获取文件时长
                'bitrate': int(mp4_audio.info.bitrate // 1000),  # 获取文件比特率并转换为kbps
                # 'codec': mp4_audio.info.codec,
                'title': None,  # 文件title
                'album': None,  # 文件专辑
                'artist': None,  # 艺术家
                'year': None,  # 年份
            }
            # mp4_info = mp4_audio.info.__dict__
            keys = mp4_audio.keys()  # 获取文件元数据对象字典所有key
            if not meta['samplerate'] and '\xa9sam' in keys:  # 判断meta字典采样率如果为空并且'\xa9sam'在文件元数据对象key中
                meta['samplerate'] = int(''.join(mp4_audio.get('\xa9sam')))  # 给meta字典采样率赋值
            if not meta['bitrate'] and '\xa9btr' in keys:  # 如果文件比特率为空并且'\xa9btr'在文件元数据对象key中
                meta['bitrate'] = int(''.join(mp4_audio.get('\xa9btr')))  # 给meta字典比特率赋值
            if not meta['bitdepth'] and '\xa9btd' in keys:  # 如果meta字典位深为空并且'\xa9btd'在文件元数据对象key中
                meta['bitdepth'] = int(''.join(mp4_audio.get('\xa9btd')))  # 给meta字典位深赋值
            if '\xa9nam' in keys:  # 判断'\xa9nam'是否在文件元数据对象key中
                meta['title'] = ''.join(mp4_audio.get('\xa9nam'))  # 给meta字典title赋值
            if '\xa9alb' in keys:  # 判断'\xa9alb'是否在文件元数据对象key中
                meta['album'] = ''.join(mp4_audio.get('\xa9alb'))  # 给meta字典album赋值
            if '\xa9ART' in keys:  # 判断'\xa9ART'是否在文件元数据对象key中
                meta['artist'] = ''.join(mp4_audio.get('\xa9ART'))  # 给meta字典artist赋值
            if '\xa9day' in keys:  # 判断'\xa9day'是否在文件元数据对象中
                meta['year'] = ''.join(mp4_audio.get('\xa9day'))  # 给meta字典year赋值
                if len(meta['year']) > 4:  # 如果year的value值长度大于4
                    meta['year'] = meta['year'][:4]  # 从起始位置截取前四个字符修改meta字典中year
            if meta['codec'] != 'alac':
                meta['codec'] = 'aac'
            return meta  # 返回meta字典
        except Exception:  # 异常捕捉
            return meta  # 返回meta字典

    def embed_mp4_metadata(self, filename, meta_tags):
        """
        为mp4和m4a文件写入元数据
        :param filename: str 绝对路径文件名
        :param meta_tags: dict 写入文件的元数据字典
        :return: bool 无异常返回True，有异常返回False
        """
        try:
            # tags字典key对应的value值为文件元数据对象中的key,文件元数据对象中的部分key为自定义
            tags = {'album': '\xa9alb',  # tags字典'album'的value在文件元数据对象中自定义的key为'\xa9alb'
                    'bitdepth': '\xa9btd',  # tags字典'bitdepth'的value在文件元数据对象中自定义的key为'\xa9btd'
                    'samplerate': '\xa9sam',  # tags字典'samplerate'的value在文件元数据中自定义的key为'\xa9sam'
                    'artist': '\xa9ART',  # tags字典'artist'的value在文件元数据中自定义的key为'\xa9ART'
                    'date': '\xa9day',  # tags字典'date'的value在文件元数据中自定义的key为'\xa9day'
                    'title': '\xa9nam',  # tags字典'title'的value在文件元数据中自定义的key为'\xa9nam'
                    'bitrate': '\xa9btr',  # tags字典'bitrate'的value在文件元数据中自定义的key为'\xa9btr'
                    }
            audiofile = MP4(filename)  # 实例化文件元数据对象
            keys = meta_tags.keys()  # 获取需要写入文件的字典中所有key
            for key in keys:  # 遍历需写入文件的字典所有key
                if meta_tags[key]:  # 如果key的value不为空
                    audiofile[tags[key]] = meta_tags[key]  # 给文件元数据对象所对应的key赋值
            audiofile.save()  # 保存文件元数据
            return True  # 没有异常返回True
        except Exception:  # 异常捕捉
            return False  # 发生异常返回False

    def get_wav_metadata(self, filename, ext_name):
        """
        获取wav文件的元数据
        :param filename: str 绝对路径文件名
        :param ext_name: str 文件扩展名
        :return: dict 元数据字典
        """
        try:
            if ext_name != '.wav':  # 如果文件是wav格式
                return  # 结束函数并返回空
            info_list = []  # 存储.wav文件的元数据信息
            sound = SoundFile(filename)  # 实例化文件元数据对象
            info = sound.extra_info  # 获取文件元数据信息，得到的是字符串
            start_idx = 0  # 切割字符串的开始索引，默认为0
            end_idx = -1  # 切割字符串的结束索引，默认为结尾
            if 'Channels' in info:  # 判断文件通道信息是否在字符串中
                start_idx = info.index('Channels')  # 如果在更改切割的开始索引为通道信息的开始索引位置
            if 'Bytes/sec' in info:  # 判断比特率信息是否在字符串中
                end_idx = info.index('Bytes/sec') + 30  # 如果在更改切割字符串的结束索引为比特率信息再加上30个字符的位置为结束索引
            info = info[start_idx:end_idx]  # 根据索引切割需要的字符串部分
            info = info.split(":")  # 将key-value格式的字符串按冒号切割得到字符串数组
            for i in range(len(info)):  # 根据字符串数组的长度遍历字符数组
                if not i or i == 3:  # 索引0和3不是想要的数据，跳过获取
                    continue
                info_list.append(info[i].split("\n")[0].strip())  # 将元素按照换行符切割取索引0位置的元素
            bitrate = int(info_list[3]) * 8 // 1000  # 文件比特率byte/second 转换为 kbit/second
            meta_data = {'channels': int(info_list[0]),  # 将取到的文件通道数更新到元数据字典
                         'samplerate': int(info_list[1]),  # 取到的采样率更新到元数据字典中
                         'bitdepth': int(info_list[2]),  # 取到的位深更新到文件元数据字典中
                         'bitrate': bitrate,  # 文件比特率更新到元数据字典中
                         }
            return meta_data  # 将获取到的元数据返回
        except Exception:  # 异常捕捉
            return  # 返回空

    def add_ogg_metadata(self, filename, info_dict):
        """
        ogg格式文件写入元数据
        :param filename: str 绝对路劲文件名
        :param info_dict: str 需要写入的元数据字典
        :return: bool 无异常返回True, 有异常返回False
        """
        try:
            if filename.endswith('ogg'):  # 截取文件扩展名
                audio = OggVorbis(filename)  # 实例化文件元数据对象
                keys = info_dict.keys()  # 获取需要写入的字典中所有key
                for key in keys:  # 遍历所有key
                    if info_dict[key] and not audio[key]:  # 如果需要写入的字典的key不为空并且文件元数据对象key的value为空
                        audio[key] = u'{}'.format(info_dict[key])  # 赋值给文件元数据对象
                audio.save()  # 保存文件元数据
            return True  # 没有异常返回True
        except Exception:  # 异常捕捉
            return False  # 返回False

    def get_tags(self, filename, ext_name):
        """
        通过MediaFile库获取文件元数据信息
        :param filename: str 绝对路径文件名
        :param ext_name: str 文件扩展名
        :return: dict 文件元数据字典
        """
        try:
            if ext_name not in self.media_file_type:  # 如果文件不是MediaFile支持的类型
                return  # 结束并返回空
            audio = MediaFile(filename)  # 实例化文件元数据对象
            meta_dict = {'bitdepth': audio.bitdepth,  # 初始化字典, 获取文件位深
                         'samplerate': audio.samplerate,  # 获取文件采样率
                         'bitrate': audio.bitrate // 1000,  # 获取文件比特率并转换为kbps
                         'artist': audio.artist,  # 获取文件艺术家
                         'title': audio.title,  # 获取文件标题
                         'channels': audio.channels,  # 获取文件通道数
                         'album': audio.album,  # 获取文件专辑名
                         'duration': audio.length  # 获取文件时长
                         }
            info_dict = audio.as_dict()  # 将文件元数据转换为字典
            info_keys = info_dict.keys()  # 获取文件元数据字典所有key
            meta_keys = meta_dict.keys()  # 获取meta_dict字典所有key
            if 'bitrate' in info_dict.keys():  # 如果'bitrate'在文件元数据字典中
                info_dict['bitrate'] = info_dict['bitrate'] // 1000  # 将文件元数据字典比特率转换为kbps
            for key in meta_keys:  # 遍历mete_keys
                if not meta_dict[key] and key in info_keys:  # 如果meta_dict的key的valeu为空并且key在info_dict的keys中
                    meta_dict[key] = info_dict[key]  # 将info_dict中key的value赋值给meta_dict的key
            if not meta_dict[
                'samplerate'] and 'sample_rate' in info_keys:  # 如果meta_dict中采样率的值为空并且'sample_rate'在info_dict中
                meta_dict['samplerate'] = info_dict[
                    'sample_rate']  # 将info_dict中'sample_rate'的value赋值给meta_dict的'samplerate'
            return meta_dict  # 返回元数据字典
        except Exception:  # 异常捕捉
            return meta_dict  # 返回元数据字典

    def edit_flac_metadata(self, filename, info_dict):
        """
        写入flac文件元数据
        :param filename: str 绝对路径文件名
        :param info_dict: str 写入文件的字典
        :return: bool 没有异常返回True, 有异常返回False
        """
        try:
            audio = FLAC(filename)  # 实例化文件元数据对象
            if info_dict['title']:  # 判断需写入的title是否为空
                audio["title"] = u"{}".format(info_dict['title'])  # 给文件元数据对象title赋值
            if info_dict['artist']:  # 判断需写入的artist是否为空
                audio['artist'] = u"{}".format(info_dict['artist'])  # 给文件元数据对象artist赋值
            audio.save()  # 保存文件元数据对象的数据
            return True  # 没有异常返回True
        except Exception:  # 异常捕捉
            return False  # 有异常返回False

    def modified_id3(self, file_name, info):
        """
        给文件添加ID3标签
        :param file_name: str 绝对路径文件名
        :param info: str 需写入文件的数据
        :return: bool 没有异常返回True, 有异常返回False
        """
        try:
            id3 = ID3()  # 实例化ID3对象
            if info['title']:  # 判断title的value是否为空
                id3.add(TIT2(encoding=3, text=info['title']))  # ID3标签中添加title
            if info['artist']:  # 判断artist的value是否为空
                id3.add(TPE1(encoding=3, text=info['artist']))  # ID3标签中添加artist
            id3.save(file_name)  # 保存Id3数据
            return True  # 没有异常返回True
        except Exception:  # 异常捕捉
            return False  # 有异常返回False

    def get_id3_tags(self, filename):
        """
        获取文件ID3标签
        :param filename: str 绝对路文件名
        :return: dict 元数据字典
        """
        try:
            info_dict = {"title": None, "artist": None}  # 初始化字典存储元数据信息
            id3 = ID3(filename)  # 实例化ID3对象
            info_dict["title"] = ''.join(id3.get('TIT2'))  # 取出文件title并赋值给字典
            info_dict["artist"] = ''.join(id3.get('TPE1'))  # 取出文件artist并赋值给字典
            return info_dict  # 没有异常返回字典
        except Exception:  # 异常捕捉
            return info_dict  # 有异常返回为赋值的字典

    def get_mutagen_meta(self, filename, ext_name):
        """
        通过mutagen库获取文件元数据
        :param filename: str 绝对路径文件名
        :param ext_name: str 文件扩展名
        :return: dict 文件元数据字典
        """
        try:
            if ext_name not in self.mutagen_type:  # 如果文件为不支持的类型
                return  # 结束并返回空
            if ext_name in self.id3_type:  # 判断文件是否为支持ID3标签并且同时支持tingtag库读取文件
                info = {"title": '', "artist": ''}  # 初始化字典
                with open(filename, 'rb') as f:  # 以二进制模式打开并读取文件
                    data = f.read(6)  # 读取6个字节
                    if b'ID3' in data:  # 判断ID3字符是否在读取的数据中
                        id3 = ID3(filename)  # 实例化ID3对象
                        title = ''.join(id3.get('TIT2'))  # 获取文件title
                        artist = ''.join(id3.get('TPE1'))  # 获取文件artist
                        info['artist'] = artist  # 将artist赋值给字典
                        info['title'] = title  # 将title赋值给字典
                if ext_name == '.mp3' or ext_name == '.wma':  # 判断文件是否为mp3或者wma格式
                    return info  # 返回字典
            if ext_name == ".aiff":  # 如果是aiff格式文件
                audio = AIFF(filename)  # 实例化文件元数据对象
                info_dict = audio.info.__dict__  # 获取文件元数据字典
            elif ext_name == '.wav':  # 如果文件是wav文件
                audio = WAVE(filename)  # 实例化文件元数据对象
                info_dict = audio.info.__dict__  # 获取文件元数据字典
            elif ext_name == '.flac':  # 如果是flac格式文件
                audio = FLAC(filename)  # 实例化文件元数据对象
                info_dict = audio.info.__dict__  # 获取文件元数据字典
                key_list = ["title", "artist", "album"]  # 列表为需要重新赋值的key
                if audio:  # 判断文件元数据对象是否为空
                    for key in key_list:  # 遍历获取需重新赋值的key
                        if key in audio.keys() and audio[key]:  # 判断key是否在文件元数据对象中并且文件元数据key的value不为空
                            info_dict[key] = ''.join(audio[key])  # 赋值给info_dict的key
            elif ext_name == '.dff':  # 如果文件是dff格式
                audio = DSDIFF(filename)  # 实例化文件元数据对象
                info_dict = {"bitrate": audio.info.bitrate // 1000,  # 初始化字典, 获取文件比特率
                             "bitdepth": audio.info.bits_per_sample,  # 获取文件位深
                             "samplerate": audio.info.sample_rate,  # 获取文件采样率
                             "channels": audio.info.channels,  # 获取文件通道数
                             "duration": audio.info.length  # 获取文件时长
                             }
            elif ext_name == '.ac3':  # 如果文件是ac3格式
                audio = AC3(filename)  # 实例化文件元数据对象
                info_dict = audio.info.__dict__  # 获取文件元数据字典
            elif ext_name == '.aac':  # 如果文件是aac格式
                audio = AAC(filename)  # 实例化文件元数据对象
                info_dict = audio.info.__dict__  # 获取文件元数据字典
                info_dict = {**info, **info_dict}  # 跟info字典合并
            elif ext_name == '.ogg':  # 如果文件是ogg格式
                with open(filename, 'rb') as f:  # 打开并以二进制模式读取文件
                    info_dict = OggVorbisInfo(f).__dict__  # 实例化文件元数据对象并获取文件元数据字典
            info_keys = info_dict.keys()  # 获取字典所有key
            if 'bits_per_sample' in info_keys and info_dict['bits_per_sample']:  # 判断key是否存在
                info_dict['bitdepth'] = info_dict['bits_per_sample']  # 添加新的key并赋值
                info_dict.pop('bits_per_sample', None)  # 移除元素
            if 'sample_rate' in info_keys and info_dict['sample_rate']:  # 判断'sample_rate'是否在字典key中
                info_dict['samplerate'] = info_dict['sample_rate']  # 添加新的key并赋值
                info_dict.pop('sample_rate', None)  # 移除元素
            if 'bitrate' in info_keys and info_dict['bitrate']:  # 判断key是否存在并且key的value是否为空
                info_dict['bitrate'] = info_dict['bitrate'] // 1000  # 修改bps为kbps
            if 'length' in info_keys and info_dict['length']:  # 判断key是否存在并且value是否为空
                info_dict['duration'] = info_dict['length']  # 添加新的key并赋值
            return info_dict  # 返回元数据字典
        except Exception:  # 异常捕捉
            return  # 有异常返回空

    def ready_sort(self):
        """
        对文件按音质进行分类
        :return: None
        """
        if self.base_path:  # 判断音乐根路径是否为空
            self.pgb_value = 0  # 初始化进度值为0
            self.file_sort(self.base_path)  # 调用文件按音质分类函数
            self.finished_signal.emit("file_sort_finish")  # 音质分类完成发送完成信号至主线程
            if self.sort_failed:  # 判断文件分类失败列表是否为空
                for file in self.sort_failed:  # 遍历分类失败列表
                    des_path = f"{self.base_path}/分类失败/"  # 拼接文件移动的路径
                    if not exists(des_path):  # 判断文件夹是否存在
                        mkdir(des_path)  # 创建文件夹
                    move(file, des_path)  # 移动文件
                self.finished_signal.emit("move_sort_failed_finish")
            self.rm_empty_dir(self.base_path)  # 删除空文件夹

    def ascii_to_utf8(self, asc_s):
        """
        将ascii编码字符转换为utf8编码
        :param asc_s: ascii str
        :return: utf8 str
        """
        if not asc_s:  # 判断字符串是否为空
            return
        if all(ord(s) <= 255 for s in asc_s):  # 判断字符串所有字符是否都为ascii字符
            try:
                return asc_s.encode('iso-8859-1').decode('gbk').encode('utf8').decode('utf8')  # 整个字符串转换编码
            except Exception as e:  # 异常捕捉
                except_s = str(e)   # 将异常对象转换为字符串异常信息
                if 'position' in except_s:  #　判断异常信息中是否包含'position'
                    # 获取解码异常字符在字符串中的索引位置
                    ind = ''.join([i for i in except_s.split('position')[1][:4] if str.isdigit(i)])
                    asc_s = asc_s.replace(asc_s[int(ind)], '')  # 将解码异常的字符替换为空
                    return self.ascii_to_utf8(asc_s)    # 递归调用自己重新解码
        else:  # 否则字符中混合有ascii编码字符和其他编码字符, 将ascii字符和其他编码字符拆分后解码
            return self.split_char_decode(asc_s)

    def split_char_decode(self, asc_s):
        """
        对字符串中混合有ascii编码字符和其他编码字符进行拆分后单独解码
        :param asc_s: str 混合编码字符串
        :return: utf-8 str
        """
        length = len(asc_s)  # 获取字符串长度
        start_ind = 0  # 定义变量用作截取字符的开始索引
        decode_list = []  # 将截取出来的字符转码后追加到列表
        for i in range(length):  # 遍历字符串获取每个字符
            try:
                if i >= length:  # 如果索引大于等于字符串长度
                    break  # 结束循环
                if i == length - 1:  # 如果索引等于字符串长度减一
                    wait_decode = asc_s[start_ind: length]  # 最后一次判断字符编码时直接执行到循环结束并未截取字符,将最后的字符截取出来
                    if ord(wait_decode[0]) <= 255:  # 判断最后一次截取的字符第一个元素是否为ascii字符
                        # 转码并追加至列表
                        decode_list.append(wait_decode.encode('iso-8859-1').decode('gbk').encode('utf-8').decode('utf-8'))
                    elif ord(wait_decode[0]) > 255:  # 判断最后一次截取的字符第一个元素是否不是ascii字符
                        decode_list.append(wait_decode.encode('utf-8').decode('utf-8'))  # 转码并追加至列表
                    break
                if ord(asc_s[i]) <= 255 and ord(asc_s[i + 1]) > 255:  # 判断当前索引的元素是否为ascii字符并且下一个字符不是ascii字符
                    end_ind = i  # 定义变量用作截取字符的结束索引
                    wait_decode: object = asc_s[start_ind: end_ind + 1]  # 截取ascii字符
                    # 转码并追加至列表
                    decode_list.append(wait_decode.encode('iso-8859-1').decode('gbk').encode('utf-8').decode('utf-8'))
                    start_ind = end_ind + 1  # 将本次截取字符的结束索引作为下一次截取的开始索引
                    continue  # 跳过循环
                if ord(asc_s[i]) > 255 and ord(asc_s[i + 1]) <= 255:  # 判断当前索引的字符不是ascii字符并且下一个字符是ascii字符
                    end_ind = i  # 将当前索引赋值给截取字符的结束索引
                    decode_list.append(asc_s[start_ind: end_ind + 1].encode('utf-8').decode('utf-8'))  # 截取字符并转码后追加至列表
                    start_ind = end_ind + 1  # 将当前索引赋值给截取字符的结束索引
                    continue  # 跳过循环
            except Exception as e:  # 异常捕捉
                except_s = str(e)   # 将异常信息对象转换为字符串异常信息
                if 'position' in except_s:  #　判断异常信息中是否包含'position'
                    # 获取解码异常字符在字符串中的索引位置
                    ind = ''.join([i for i in except_s.split('position')[1][:4] if str.isdigit(i)])
                    asc_s = asc_s.replace(asc_s[int(ind)], '')  # 将出现异常的字符替换为空
                    return self.split_char_decode(asc_s)    # 递归调用自己重新解码
        return ''.join(decode_list)  # 连接列表所有转码后的元素并返回
