# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QLabel, QTextEdit, QLineEdit, QPushButton, QProgressBar


class UiForm(object):
    def setup_ui(self):
        layout = QGridLayout()
        layout.setSpacing(10)
        self.sf_label = QLabel()
        self.sf_label.setText("源文件: ")
        self.sf_edit = QTextEdit()
        self.sf_edit.setStyleSheet("QTextEdit{font-size:18px;border:2px solid rgb(192,192,192);}")

        self.tf_label = QLabel()
        self.tf_label.setText("目标文件: ")
        self.tf_edit = QTextEdit()
        self.tf_edit.setStyleSheet("QTextEdit{font-size:18px;border:2px solid rgb(192,192,192);}")

        self.success_label = QLabel()
        self.success_label.setText("成功项:")
        self.success_edit = QTextEdit()
        self.success_edit.setStyleSheet("QTextEdit{font-size:18px;border:2px solid rgb(192,192,192);}")

        self.failed_label = QLabel()
        self.failed_label.setText("失败项:")
        self.failed_edit = QTextEdit()
        self.failed_edit.setStyleSheet("QTextEdit{font-size:18px;border:2px solid rgb(192,192,192);}")

        self.src_label = QLabel()
        self.src_label.setText("源文件路径:")
        self.src_edit = QLineEdit()
        #self.src_edit.setMinimumWidth(320)
        self.src_edit.setPlaceholderText("请选择文件夹路径")
        self.src_edit.setDisabled(True)
        self.src_edit.setStyleSheet("QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")

        self.out_label = QLabel()
        self.out_label.setText("保存文件路径:")
        self.out_edit = QLineEdit()
        #self.out_edit.setMinimumWidth(320)
        self.out_edit.setPlaceholderText("请选择文件夹路径")
        self.out_edit.setDisabled(True)
        self.out_edit.setStyleSheet("QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")

        self.input_btn = QPushButton()
        self.input_btn.setText("选择文件夹(Ctrl+F)")
        self.input_btn.setShortcut("Ctrl+F")
        self.input_btn.setMaximumSize(170, 40)
        self.output_btn = QPushButton()
        self.output_btn.setMaximumSize(170, 40)
        self.output_btn.setText("选择文件夹(Ctrl+S)")
        self.output_btn.setShortcut('Ctrl+S')

        self.cause_label = QLabel()
        self.cause_label.setText("失败原因:")
        self.cause_edit = QTextEdit()
        self.cause_edit.setStyleSheet("QTextEdit{font-size:14px;border:2px solid rgb(192,192,192);}")

        self.pgb = QProgressBar()
        self.pgb.setTextVisible(False)
        self.pgb.setMinimum(0)
        self.pgb.setMinimumWidth(380)

        self.logs_label = QLabel()
        self.logs_label.setText("日志信息:")
        self.textEdit = QTextEdit()
        self.textEdit.setStyleSheet("QTextEdit{font-size:16px;border:2px solid rgb(192,192,192);}")

        self.unlock_btn = QPushButton()
        self.unlock_btn.setText("解锁(Ctrl+N)")
        self.unlock_btn.setShortcut("Ctrl+N")
        self.unlock_btn.setMaximumSize(150, 40)
        self.cancel_btn = QPushButton()
        self.cancel_btn.setMaximumSize(150, 40)
        self.cancel_btn.setText("退出(Esc)")
        self.cancel_btn.setShortcut('Esc')

        self.tools_label = QLabel()
        self.tools_label.setText("查找低质量重复文件(相似名或同名):")
        self.tools_edit = QLineEdit()
        self.tools_edit.setMaximumHeight(40)
        self.tools_edit.setPlaceholderText("建议选择含多个子文件夹的音乐根目录")
        self.tools_edit.setDisabled(True)
        self.tools_edit.setStyleSheet("QLineEdit{font-size:25px;border:2px solid rgb(192,192,192);}")
        self.tools_btn = QPushButton()
        self.tools_btn.setText("选择文件夹(Ctrl+R)")
        self.tools_btn.setShortcut('Ctrl+R')
        self.tools_btn.setMaximumSize(170, 40)

        self.hyperlink_label = QLabel()
        self.hyperlink_label.setText('<a href="https://github.com/AI-gordita/unlock-music-desktop">github源码、安装包地址</a>')
        self.hyperlink_label.setOpenExternalLinks(True)

        self.download_label = QLabel()
        self.download_label.setText('<a href="https://codeload.github.com/AI-gordita/unlock-music-desktop/zip/refs/heads/master">github源码、安装包点击下载</a>')
        self.download_label.setOpenExternalLinks(True)

        self.blog_label = QLabel()
        self.blog_label.setText('<a href="https://blog.csdn.net/qq_50068136/article/details/121890979?spm=1001.2014.3001.5502">博客地址,使用问题欢迎留言</a>')
        self.blog_label.setOpenExternalLinks(True)

        self.baiduyun_label = QLabel()
        self.baiduyun_label.setText('<a href="https://pan.baidu.com/s/1z0GR0WoeI8B_kteoa0-VTw">百度网盘安装包下载地址，提取码：1234</a>')
        self.baiduyun_label.setOpenExternalLinks(True)

        layout.addWidget(self.sf_label, 0, 0)
        layout.addWidget(self.tf_label, 0, 1)
        layout.addWidget(self.success_label, 0, 2)
        layout.addWidget(self.failed_label, 0, 3)

        layout.addWidget(self.sf_edit, 1, 0)
        layout.addWidget(self.tf_edit, 1, 1)
        layout.addWidget(self.success_edit, 1, 2)
        layout.addWidget(self.failed_edit, 1, 3)

        layout.addWidget(self.hyperlink_label, 2, 1, 1, 1, Qt.AlignCenter | Qt.AlignTop)
        layout.addWidget(self.download_label, 2, 2, 1, 1, Qt.AlignCenter | Qt.AlignTop)
        layout.addWidget(self.baiduyun_label, 2, 3, 1, 1, Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.blog_label, 2, 0, Qt.AlignLeft | Qt.AlignTop)

        layout.addWidget(self.logs_label, 3, 0)
        layout.addWidget(self.cause_label, 3, 3)

        layout.addWidget(self.textEdit, 4, 0, 1, 3)
        layout.addWidget(self.cause_edit, 4, 3)

        layout.addWidget(self.src_label, 5, 0)
        layout.addWidget(self.out_label, 5, 1)
        layout.addWidget(self.tools_label, 5, 2)

        layout.addWidget(self.src_edit, 6, 0)
        layout.addWidget(self.out_edit, 6, 1)
        layout.addWidget(self.pgb, 6, 3)
        layout.addWidget(self.tools_edit, 6, 2)

        layout.addWidget(self.input_btn, 7, 0, Qt.AlignRight | Qt.AlignTop)
        layout.addWidget(self.output_btn, 7, 1, Qt.AlignRight | Qt.AlignTop)
        layout.addWidget(self.unlock_btn, 7, 3, Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.cancel_btn, 7, 3, Qt.AlignRight | Qt.AlignTop)
        layout.addWidget(self.tools_btn, 7, 2, Qt.AlignRight | Qt.AlignTop)
        self.setLayout(layout)
