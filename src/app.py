from os.path import abspath

from lk_utils import read_and_write_basic
from lk_utils.lk_logger import lk
from lk_utils.file_sniffer import findall_files


def main(prjdir='./', launch='src/app.py'):
    """
    ARGS:
        prjdir: str. 目标项目的路径. 可以传绝对路径或相对本文件的路径.
        launch: str. 启动文件, 路径传相对于 prjdir 的路径. 例如, prjdir 是
            'D:/myproject/', 启动文件是 'D:/myproject/src/app.py', 则 launch 填
            'src/app.py'.
    """
    
    files = findall_files(prjdir)
    py_files = (x for x in files if x.endswith('.py'))
    # -> ['./src/app.py', './src/downloader.py', ..., 'utils/renamer.py']
    
    entrance = prjdir + launch  # -> './src/app.py'
    

    

if __name__ == "__main__":
    main()
    lk.print_important_msg()
    lk.over()
    lk.dump_log()
