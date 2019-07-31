"""
abbr note:
    ast: abstract syntax tree
    dir: directory
    lino: line number
    linos: line number list
    obj: object
    prj: project
    pyfile: python file (path) or any file postfixed with '.py'
    val: value
    var: variant
"""
from os.path import abspath, exists

from lk_utils import file_sniffer
from lk_utils.lk_logger import lk

from src.ast_analyser import AstAnalyser


def main(prjdir, pyfile, exclude_dirs=None):
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
    global ast_tree, ast_indents
    ast_tree = ast_analyser.main()
    # -> {lino: [(obj_type, obj_val), ...]}
    ast_indents = ast_analyser.get_lineno_indent_dict(pyfile)
    # -> {lino: indent}
    
    module_analyser = ModuleAnalyser(prjdir, pyfile, exclude_dirs)
    
    runner = VirtualRunner(module_analyser)
    runner.main()


class VirtualRunner:
    
    def __init__(self, module_analyser):
        self.module_analyser = module_analyser  # type: ModuleAnalyser
        self.module_linos = module_analyser.indexing_module_linos()
        # -> {module: [lino, ...]}
        
        self.assign_analyser = AssignAnalyser(
            self.module_analyser.top_module, self.module_analyser.prj_modules
        )
        
        self.module_hooks = self.assign_analyser.top_assigns_prj_only
        # -> {var: module}
        self.var_hooks = {}  # {var: feeler}
        
        self.calls = []
        self.outer_calls = []
        
        self.registered_methods = {
            "<class '_ast.Call'>"       : self.parse_call,
            # "<class '_ast.ClassDef'>"   : self.parse_class_def,
            # "<class '_ast.FunctionDef'>": self.parse_function_def,
            # "<class '_ast.Import'>"     : self.parse_import,
            # "<class '_ast.ImportFrom'>" : self.parse_import,
            # "<class '_ast.Name'>"       : self.parse_name,
        }
    
    def main(self):
        """
        
        PS: 请配合 src.utils.ast_helper.test2() 的输出结果 (ast_helper_result.json)
        完成本方法的制作.
        """
        start = self.module_analyser.get_top_module() + '.' + 'module'
        calls = self.run_block(start)
        lk.logt('[I4413]', len(calls), calls)
        self.recurse_module_called(calls)
        
    def recurse_module_called(self, calls):
        for i in calls:
            child_calls = self.run_block(i)
            lk.logt('[D4429]', len(child_calls), child_calls)
            return self.recurse_module_called(child_calls)
    
    def run_block(self, current_module: str):
        """
        IN: module: str
        OT: self.calls: list
        """
        lk.logd('run block', current_module, style='■')
        
        if current_module not in self.module_linos:
            # 说明此 module 是从外部导入的模块, 如 module = 'testflight.downloader'.
            assert self.module_analyser.is_prj_module(current_module)
            self.outer_calls.append(current_module)
            # return module_path
        
        # update hooks
        # self.module_hooks 需要在每次更新 self.run_block() 时同步更新. 这是因为, 不同
        # 的 block 定义的区间范围不同, 而不同的区间范围包含的变量指配 (assigns) 也可能是不同
        # 的.
        # 例如在 module = testflight.test_app_launcher.module 层级, self.module
        # _hooks = {'main': 'testflight.test_app_launcher.main'}. 到了 module =
        # testflight.test_app_launcher.Init 来运行 run_block 的时候, self.module
        # _hooks 就变成了 {'main': 'testflight.test_app_launcher.Init.main'}. 也就
        # 是说在不同的 block 区间, 'main' 指配的 module 对象发生了变化, 因此必须更新 self
        # .module_hooks 才能适应最新变化.
        self.module_hooks = self.assign_analyser.indexing_assign_reachables(
            current_module, self.module_linos
        )
        lk.logt('[I4252]', 'update module hooks', self.module_hooks)
        
        # reset hooks
        self.var_hooks.clear()
        self.calls.clear()
        
        linos = self.module_linos[current_module]
        # the linos is in ordered.
        lk.loga(current_module, linos)
        
        for lino in linos:
            self.run_line(lino)

        # | for index, lino in enumerate(linos):
        # |     # noinspection PyBroadException
        # |     try:
        # |         self.run_line(lino)
        # |     except Exception:
        # |         if index == 0:
        # |             continue
        # |         else:
        # |             raise Exception

        return self.calls
    
    def run_line(self, lino: int):
        ast_line = ast_tree.get(lino)
        lk.logd(ast_line, length=8)
        # -> [(obj_type, obj_val), ...]
        
        for i in ast_line:
            obj_type, obj_val = i
            lk.loga(obj_type, obj_val)
            # obj_type: str. e.g. "<class '_ast.Call'>"
            # obj_val: str/dict. e.g. '__name__', {'os': 'os'}, ...
            
            method = self.registered_methods.get(obj_type, self.do_nothing)
            method(obj_val)
    
    # ------------------------------------------------ run_line related
    
    @staticmethod
    def do_nothing(data):
        # lk.logt('[TEMPRINT]', 'nothing todo', data)
        pass
    
    def parse_call(self, data: str):  # related to "<class '_ast.Call'>"
        """
        data:
        """
        lk.logt('[I3516]', 'parsing call', data, self.module_hooks.get(data))
        if data in self.module_hooks:
            # e.g. data = 'child_method'
            #   -> self.module_hooks[data] = 'src.app.main.child_method'
            self.calls.append(self.module_hooks[data])
        # else: e.g. print()
    
    @staticmethod
    def parse_class_def(data):  # related to "<class '_ast.ClassDef'>"
        lk.logt('[E1036]', 'a class def found in block region, this should not '
                           'be happend', data)
        raise Exception
    
    @staticmethod
    def parse_function_def(data):  # related to "<class '_ast.FunctionDef'>"
        lk.logt('[E1036]', 'a function def found in block region, this should '
                           'not be happend', data)
        raise Exception


class ModuleAnalyser:
    
    def __init__(self, prjdir, pyfile, exclude_dirs=None):
        self.prjdir = prjdir  # -> 'D:/myprj/'
        self.top_module = self.get_module_by_filepath(pyfile)
        self.prj_modules = self.get_project_modules(exclude_dirs)
        # -> ['testflight.test_app_launcher', 'testflight.downloader', ...]
    
    # ------------------------------------------------ getters
    
    def get_project_modules(self, exclude_dirs=None) -> list:
        """
        获得项目所有可导入的模块路径.

        第三方模块分为项目模块和外部模块. 本程序只负责分析项目模块的依赖关系, 因此通过本方法过滤
        掉外部模块的路径.
        例如:
            import sys  # builtin module
            import src.downloader  # project module
        那么本方法只收录 ['src.downloader'], 不收录 ['sys'].

        IN: prjdir: str. an absolute project directory. e.g. 'D:/myprj/'
        OT: prj_modules: list. e.g. ['testflight.test_app_launcher', 'testflight
                .downloader', ...]
        """
        all_files = file_sniffer.findall_files(self.prjdir)
        all_pyfiles = [x for x in all_files if x.endswith('.py')]
        # -> ['D:/myprj/src/app.py', 'D:/myprj/src/downloader.py', ...]
        
        if exclude_dirs:  # DEL (2019-07-31): 效益较低. 未来将会移除.
            lk.loga(exclude_dirs)
            for adir in exclude_dirs:
                all_files = file_sniffer.findall_files(
                    file_sniffer.prettify_dir(abspath(adir))
                )
                # lk.loga(all_files)
                pyfiles = (x for x in all_files if x.endswith('.py'))
                for f in pyfiles:
                    all_pyfiles.remove(f)
        
        prj_modules = [self.get_module_by_filepath(x) for x in all_pyfiles]
        # -> ['src.app', 'src.downloader', ...]
        
        lk.loga(len(all_pyfiles), prj_modules)
        
        return prj_modules
    
    def get_top_module(self):
        return self.top_module
    
    def get_module_by_filepath(self, fpath):
        """
        IN: fpath: str. 请确保传入的是绝对路径. e.g. 'D:/myprj/src/app.py'
        OT: module: str. e.g. 'src.app'
        """
        return fpath.replace(self.prjdir, '', 1).replace('/', '.')[:-3]
        # fpath = 'D:/myprj/src/app.py' -> 'src.app'
    
    # ------------------------------------------------ indexing
    
    def indexing_module_linos(self, top_module='', linos=None):
        """
        根据 {lino:indent} 和 ast_tree 创建 {module:linos} 的字典.
        
        ARGS:
            top_module
            linos: list. 您可以自定义要读取的 module 范围, 本方法会仅针对这个区间进行编译.
                例如:
                    1 | def aaa():
                    2 |     def bbb():      # <- start
                    3 |         def ccc():
                    4 |             pass
                    5 |                     # <- end
                    6 | def ddd():
                    7 |     pass
                则本方法只编译 start=2 - end=5 范围内的数据, 并返回 {'src.app.aaa.bbb'
                : [2, 5], 'src.app.aaa.bbb.ccc': [3, 4]} 作为编译结果.
                注意: 指定的范围的开始位置的缩进必须小于等于结束位置的缩进 (空行除外).

        IN:
            ast_tree: dict. {lino: [(obj_type, obj_val), ...], ...}
                lino: int. 行号, 从 1 开始数
                obj_type: str. 对象类型, 例如 "<class 'FunctionDef'>" 等. 完整的支持
                    列表参考 src.utils.ast_helper.AstHelper#eval_node()
                obj_val: str/dict. 对象的值, 目前仅存在 str 或 dict 类型的数据.
                    示例:
                        (str) 'print'
                        (dict) (多用于描述 Import) {'src.downloader.Downloader':
                            'src.downloader.Downloader'}
            lino_indent: dict. {lino: indent, ...}. 由 AstHelper#create
                _lino_indent_dict() 提供
                lino: int. 行号, 从 1 开始数
                indent: int. 该行的列缩进位置, 为 4 的整数倍数, 如 0, 4, 8, 12 等
            self.top_module: str. e.g. 'src.app'
        OT:
            module_linos: dict. {module: [lino, ...]}
                module: str. 模块的路径名.
                lino_list: list. 模块所涉及的行号列表, 已经过排序, 行号从 1 开始数, 最
                    大不超过当前 pyfile 的总代码行数.
                e.g. {'src.app.module': [1, 2, 3, 9, 10],
                      'src.app.main': [4, 5, 8],
                      'src.app.main.child_method': [6, 7],
                      ...}
                有了 module_linos 以后, 我们就可以在已知 module 的调用关系的情况下, 专注于
                读取该 module 对应的区间范围, 逐行分析每条语句, 并进一步发现新的调用关系, 以
                此产生裂变效应. 详见 src.analyser.VirtualRunner#main().
        """
        lk.logd('indexing module linos')
        
        if top_module == '':
            top_module = self.top_module
        if linos is None:
            linos = list(ast_tree.keys())
            linos.sort()
        
        # ------------------------------------------------
        
        def eval_ast_line():
            ast_line = ast_tree[lino]  # type: list
            # ast_line is type of list, assert it not empty.
            assert ast_line
            # here we only take its first element.
            return ast_line[0]
        
        # ast_defs: ast definitions
        ast_defs = ("<class '_ast.FunctionDef'>", "<class '_ast.ClassDef'>")
        indent_module_dict = {}  # format: {indent: module}
        out = {}  # format: {module: lino_list}
        
        last_indent = 0
        
        for lino in linos:
            # lk.loga(lino)
            
            obj_type, obj_val = eval_ast_line()
            
            indent = ast_indents.get(lino, -1)
            """
            special:
                indent 有一个特殊值 -1, 表示下面这种情况:
                    def abc():        # -> indent = 0
                        print('aaa',  # -> indent = 4
                              'bbb',  # -> indent = 10 -> -1
                              'ccc')  # -> indent = 10 -> -1
                当 indent 为 -1 时, 则认为本行的 indent 保持与上次 indent 一致.
            """
            
            if indent == -1:
                indent = last_indent
                assert obj_type not in ast_defs
            assert indent % 4 == 0, (lino, indent)
            
            """
            当 indent >= last_indent 时: 在 indent_holder 中开辟新键.
            当 indent < last_indent 时: 从 indent_holder 更新并移除高缩进的键.
            """
            
            lk.loga(lino, indent, obj_type, obj_val)
            
            # noinspection PyUnresolvedReferences
            parent_module = indent_module_dict.get(
                indent - 4, top_module
            )
            """
            case 1:
                indent = 0, obj_val = 'main'
                -> indent - 4 = -4
                -> -4 not in indent_module_dict. so assign default:
                    parent_module = top_module = 'src.app'
                -> current_module = 'src.app.main'
            case 2:
                indent = 4, obj_val = 'child_method'
                -> indent - 4 = 0
                -> parent_module = 'src.app.main'
                -> current_module = 'src.app.main.child_method'
            """
            if obj_type in ast_defs:
                # obj_type = "<class 'FunctionDef'>", obj_val = 'main'
                current_module = parent_module + '.' + obj_val
                # lk.logt('[TEMPRINT]', current_module)
                # -> 'src.app.main'
            elif indent > 0:
                current_module = parent_module
            else:
                current_module = parent_module + '.' + 'module'
                # -> 'src.app.module'
            
            # lk.loga(parent_module, current_module)
            
            node = out.setdefault(current_module, [])
            node.append(lino)  # NOTE: the lino is in ordered
            
            # update indent_module_dict
            indent_module_dict.update({indent: current_module})
            # -> {0: 'src.app.main'}, {4: 'src.app.main.child_method'}, ...
            
            # update last_indent
            last_indent = indent
        
        # sort
        for lino_list in out.values():
            lino_list.sort()
        
        # TEST print
        lk.loga(indent_module_dict)
        lk.logt('[I4204]', out)
        
        return out
    
    # ------------------------------------------------ checkers
    
    def is_prj_module(self, unknown_module: str):
        if unknown_module in self.prj_modules:
            return unknown_module
        unknown_module = get_parent_module(unknown_module)
        if unknown_module in self.prj_modules:
            return unknown_module
        return False


class AssignAnalyser:
    
    def __init__(self, top_module, prj_modules):
        self.top_module = top_module
        self.prj_modules = prj_modules
        
        self.max_lino = max(ast_indents.keys())
        
        self.top_linos = [
            lino
            for lino, indent in ast_indents.items()
            if indent == 0
        ]
        
        self.top_assigns = self.update_assigns(self.top_linos)
        # 注意: self.top_assigns 是包含非项目模块的.
        # -> {'os': 'os', 'downloader': 'testflight.downloader', 'Parser': 'test
        # flight.parser.Parser', 'main': 'testflight.app.main', 'Init': 'testfli
        # ght.app.Init'}
        self.top_assigns_prj_only = self.get_only_prj_modules(self.top_assigns)
        lk.loga(self.top_assigns)
        lk.loga(self.top_assigns_prj_only)
    
    def update_assigns(self, linos):
        assigns = {}
        
        # ABBR: defs: definitions. imps: imports.
        ast_defs = ("<class '_ast.FunctionDef'>", "<class '_ast.ClassDef'>")
        ast_imps = ("<class '_ast.Import'>", "<class '_ast.ImportFrom'>")
        
        for lino in linos:
            ast_line = ast_tree.get(lino)
            # lk.logt('[TEMPRINT]', lino, ast_line)
            # -> [(obj_type, obj_val), ...]
            
            for element in ast_line:
                obj_type, obj_val = element
                # lk.logt('[TEMPRINT]', obj_type, obj_val)
                if obj_type in ast_defs:
                    module = self.top_module + '.' + obj_val  # FIXME
                    # -> 'src.app.main'
                    value = obj_val  # -> 'main'
                    assigns[value] = module
                elif obj_type in ast_imps:
                    for k, v in obj_val.items():
                        module = k
                        value = v
                        assigns[value] = module
        return assigns
    
    def indexing_assign_reachables(
            self, target_module, module_linos, only_prj_modules=True
    ):
        is_top_module = bool(target_module.endswith('.module'))
        # OR: is_top_module = bool(target_module == self.top_module)
        if is_top_module:
            return self.top_assigns_prj_only if only_prj_modules \
                else self.top_assigns
        
        lino_reachables = None
        
        target_linos = module_linos[target_module]
        target_linos_start = target_linos[0]
        target_indent = ast_indents[target_linos_start]
        if target_indent == 0:
            lino_reachables = list(range(
                target_linos[0], target_linos[-1]
            ))
        else:
            # target_module = 'testflight.app.main.child_method'
            # -> parent_module = 'testflight.app.main'
            
            while True:
                parent_module = get_parent_module(target_module)
                parent_linos = module_linos[parent_module]
                parent_linos_start = parent_linos[0]
                parent_indent = ast_indents[parent_linos_start]
                if parent_indent == 0:
                    lino_reachables = list(range(
                        parent_linos[0], parent_linos[-1]
                    ))
                    break
                else:
                    continue
        
        if only_prj_modules:
            assigns = self.top_assigns_prj_only.copy()
        else:
            assigns = self.top_assigns.copy()
        
        lino_reachables = [x for x in lino_reachables if x in ast_indents]
        # 注: 为什么要这样做? 因为 ast_indents.keys() 的 linos 是不完整的, 因此要这样过滤
        # 一下.
        assigns.update(self.update_assigns(lino_reachables))
        # lk.loga(assigns)
        
        if only_prj_modules:
            return self.get_only_prj_modules(assigns)
        else:
            return assigns
    
    def get_only_prj_modules(self, assigns: dict):
        return {
            k: v
            for k, v in assigns.items()
            if v in self.prj_modules
               or get_parent_module(v) in self.prj_modules
        }


# ------------------------------------------------

def get_parent_module(module: str):
    if '.' not in module:
        # raise Exception
        return ''
    return module.rsplit('.', 1)[0]
    # 'testflight.app.main.child_method' -> 'testflight.app.main'


# ------------------------------------------------

if __name__ == '__main__':
    main('../', '../testflight/app.py', ['../dust/', '../temp/', '../tests/'])
