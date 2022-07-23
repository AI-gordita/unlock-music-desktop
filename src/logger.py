# -*- coding:utf-8 -*-

from sys import stdout
from logging import getLogger, Formatter, FileHandler, DEBUG, StreamHandler
from colorlog import ColoredFormatter

log_colors_config = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red',
}


# ProjectPath = os.path.split(os.path.split(os.path.realpath(__file__))[0])[0]
# LogsPath = os.path.join(ProjectPath,  r'../logs/main.log'.format(time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())))


class MyLogs:

    def logger(self, level, msg):
        """ 获取logger"""
        logger = getLogger()
        formatter = ColoredFormatter(
            '%(log_color)s[%(asctime)s] [%(levelname)s]: %(message)s', log_colors=log_colors_config)
        formatter2 = Formatter('[%(asctime)s] [%(levelname)s]: %(message)s')
        if not logger.handlers:
            # 文件日志
            file_handler = FileHandler("./main.log", encoding="utf-8")
            file_handler.setLevel(DEBUG)
            file_handler.setFormatter(formatter2)  # 可以通过setFormatter指定输出格式
            # 控制台日志
            console_handler = StreamHandler(stdout)
            # 指定日志的最低输出级别，默认为WARN级别
            logger.setLevel(DEBUG)
            # console_handler.formatter = formatter  # 也可以直接给formatter赋值
            console_handler.setFormatter(formatter)  # 指定格式
            # 为logger添加的日志处理器
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        if level == "DEBUG":
            logger.debug(msg)
        elif level == "INFO":
            logger.info(msg)
        elif level == "WARNING":
            logger.warning(msg)
        elif level == "ERROR":
            logger.error(msg)
        elif level == "CRITICAL":
            logger.critical(msg)
        logger.removeHandler(console_handler)
        logger.removeHandler(file_handler)
        file_handler.close()  # 不关闭会警告

    def debug(self, msg):
        self.logger("DEBUG", msg)

    def info(self, msg):
        self.logger("INFO", msg)

    def warning(self, msg):
        self.logger("WARNING", msg)

    def error(self, msg: object) -> object:
        self.logger("ERROR", msg)

    def critical(self, msg):
        self.logger("CRITICAL", msg)


if __name__ == '__main__':
    log = MyLogs()
    log.debug("---测试开始----")
    log.info("操作步骤")
    log.warning("----测试结束----")
    log.error("----测试错误----")
