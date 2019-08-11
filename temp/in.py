"""
abbr note:
    ast: abstract syntax tree
    dir: directory
    lino: line number
    linos: line numbers
    obj: object
    prj: project
    pyfile: python file (path) or any file postfixed with '.py'
    val: value
    var: variant
"""
from os.path import abspath, exists

from lk_utils import file_sniffer
from lk_utils.lk_logger import lk

from src.module_analyser import ModuleHelper
from src.pyfile_analyser import PyfileAnalyser
from src.writer import Writer


class VirtualRunner:
    """
    虚拟运行机将分析 pyfile 并生成对象之间的调用关系.
    
    docs: docs/call flow 实现方案.txt
    """
    
    def __init__(self, prjdir, pyfile):
        self.prjdir = prjdir
        self.pyfile = pyfile
        
        self.module_helper = ModuleHelper(prjdir)
        self.pyfile_analyser = PyfileAnalyser(self.module_helper)
        self.writer = Writer()
    
    def main(self):
        call_stream = [self.pyfile]
        
        for pyfile in call_stream:
            lk.logd(pyfile, style='◆')
            
            module_calls, prj_modules = self.pyfile_analyser.main(pyfile)
            """
            module_calls: {module1: [call1, call2, ...], ...}
            prj_modules: [prj_module1, prj_module2, ...]
            """

            # ------------------------------------------------
            
            for module, calls in module_calls.items():
                lk.loga(module, len(calls), calls)
                self.writer.record(module, calls)

            # ------------------------------------------------
            
            new_pyfiles = self.get_new_pyfiles(prj_modules)
            for i in new_pyfiles:
                if i not in call_stream:
                    call_stream.append(i)
                    
        # TEST
        self.writer.show(
            self.module_helper.get_module_by_filepath(
                self.pyfile
            ) + '.module'
        )
    
    def get_new_pyfiles(self, prj_modules):
        return [self.module_helper.get_pyfile_by_prj_module(x)
                for x in prj_modules]
            
            
def main(prjdir, pyfile):
    """
    假设测试项目为 testflight, 启动文件为 testflight/test_app_launcher.py.
    项目结构为:
        testflight
        |-downloader.py
        |-parser.py
        |-test_app_launcher.py  # <- here is the launch file.
    本模块所有代码设计均可参照测试项目源码来理解.
    
    IN: prjdir: project directory. e.g. '../testflight/', make sure it exists.
        pyfile: the launch file. e.g. '../testflight/test_app_launcher.py', make
            sure it exists.
        exclude_dirs: None/iterable. 设置要排除的目录, 目前仅被用于 src.analyser
            .ModuleAnalyser#get_project_modules() (原本是想提升初始化效率, 实际提升不
            大). 未来会考虑移除该参数.
    OT:
    """
    assert exists(prjdir) and exists(pyfile)
    # prettify paths
    prjdir = file_sniffer.prettify_dir(abspath(prjdir))
    # '../testflight/' -> 'D:/myprj/testflight/'
    pyfile = file_sniffer.prettify_file(abspath(pyfile))
    # '../testflight/test_app_launcher.py'
    # -> 'D:/myprj/testflight/test_app_launcher.py'
    
    runner = VirtualRunner(prjdir, pyfile)
    runner.main()


# ------------------------------------------------

if __name__ == '__main__':
    # main(
    #     prjdir='../',
    #     pyfile='../testflight/app.py'
    # )
    
    # TEST
    main(
        prjdir='../',
        # pyfile='../temp/in.py'
        pyfile=__file__
    )

    lk.print_important_msg(False)
    lk.over()
    # lk.dump_log()
