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
from src.module_analyser import ModuleAnalyser
from src.virtual_runner import VirtualRunner


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
    
    ast_analyser = AstAnalyser(pyfile)
    ast_tree = ast_analyser.main()
    # -> {lino: [(obj_type, obj_val), ...]}
    ast_indents = ast_analyser.get_lino_indent_dict()
    # -> {lino: indent}
    
    module_analyser = ModuleAnalyser(
        prjdir, pyfile, ast_tree, ast_indents
    )
    
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
