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

from src.ast_analyser import AstAnalyser
from src.module_analyser import ModuleIndexing, ModuleHelper


class VirtualRunner:
    """
    虚拟运行机将分析 pyfile 并生成对象之间的调用关系.
    """
    
    def __init__(self, prjdir, pyfile):
        self.prjdir = prjdir
        self.call_stream = [pyfile]
        self.module_helper = ModuleHelper(prjdir)
    
    def main(self):
        for pyfile in self.call_stream:
            self.run_single_file(pyfile)
    
    def run_single_file(self, pyfile: str):
        """

        """
        self.module_helper.bind_file(pyfile)
        
        ast_analyser = AstAnalyser(pyfile)
        
        module_analyser = ModuleIndexing(
            module_helper=self.module_helper,
            ast_tree=ast_analyser.main(),
            ast_indents=ast_analyser.get_lino_indent_dict()
        )
        
        module_linos = module_analyser.indexing_module_linos()
        for module, linos in module_linos.items():
            pass


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
    
    runner = VirtualRunner(module_analyser, ast_tree, ast_indents)
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
        pyfile='../temp/in.py'
    )
