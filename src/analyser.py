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
            .ModuleAnalyser#get_project_modules() (原本是想提升初始化效率, 实际提升不大
            ). 未来会考虑移除该参数.
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
    
    global module_analyser
    module_analyser = ModuleAnalyser(prjdir, pyfile, exclude_dirs)
    
    runner = VirtualRunner()
    runner.main()


class VirtualRunner:
    
    def __init__(self):
        self.module_linos = module_analyser.indexing_module_linos()
        # -> {module: [lino, ...]}
        
        self.assign_analyser = AssignAnalyser()
        
        self.module_hooks = self.assign_analyser.top_assigns_prj_only
        # -> {var: module}
        self.var_hooks = {}  # {var: feeler}
        
        self.calls = []
        self.outer_calls = []
        
        self.registered_methods = {
            "<class '_ast.Call'>": self.parse_call,
            # "<class '_ast.ClassDef'>"   : self.parse_class_def,
            # "<class '_ast.FunctionDef'>": self.parse_function_def,
            # "<class '_ast.Import'>"     : self.parse_import,
            # "<class '_ast.ImportFrom'>" : self.parse_import,
            # "<class '_ast.Name'>"       : self.parse_name,
        }
    
    def main(self):
        """
        
        PS: 请配合 src.utils.ast_helper.dump_by_filter_schema() 的输出结果 (ast_hel
        per_result.json)
        完成本方法的制作.
        
        flow: (prefix = 'testflight.test_app_launcher')
            {prefix}.module
                {prefix}.main
                    {prefix}.child_method
                    {prefix}.child_method2
                    {prefix}.Init
                    {prefix}.Init.main
            如需追踪观察此流, 请查看 log 中的 [I3914] 级别打印.
        """
        start = module_analyser.get_top_module() + '.' + 'module'
        calls = self.run_block(start)
        self.recurse_module_called(calls)
    
    def recurse_module_called(self, calls):
        for i in calls:
            child_calls = self.run_block(i)
            # lk.logt('[I4429]', len(child_calls), child_calls)
            return self.recurse_module_called(child_calls)
    
    def run_block(self, current_module: str):
        """
        IN: module: str
        OT: self.calls: list
        """
        lk.logd('run block', current_module, style='■')
        
        if current_module not in self.module_linos:
            # 说明此 module 是从外部导入的模块, 如 module = 'testflight.downloader'.
            assert module_analyser.is_prj_module(current_module)
            self.outer_calls.append(current_module)
            # return module_path
        
        # update hooks
        # self.module_hooks 需要在每次更新 self.run_block() 时同步更新. 这是因为, 不同
        # 的 block 定义的区间范围不同, 而不同的区间范围包含的变量指配 (assigns) 也可能是不同
        # 的.
        # 例如在 module = testflight.test_app_launcher.module 层级, self.module_ho
        # oks = {'main': 'testflight.test_app_launcher.main'}. 到了 module = test
        # flight.test_app_launcher.Init 来运行 run_block 的时候, self.module_hooks
        # 就变成了 {'main': 'testflight.test_app_launcher.Init.main'}. 也就是说在不
        # 同的 block 区间, 'main' 指配的 module 对象发生了变化, 因此必须更新 self.module
        # _hooks 才能适应最新变化.
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
        
        lk.logt('[I3914]', self.calls)
        return self.calls
    
    def run_line(self, lino: int):
        """
        调试方法记录 (2019年7月31日):
            假设应存在如下调用关系:
                flow: (prefix = 'testflight.test_app_launcher')
                    {prefix}.main  # <- 调用方
                        {prefix}.child_method   # <- 调用结果
                        {prefix}.child_method2  # <- 调用结果
                        {prefix}.Init           # <- 调用结果
                        {prefix}.Init.main      # <- 调用结果
            如果本方法在调试过程中发现只能识别到 {prefix}.Init, 其他三个识别不到, 请遵循以下
            改进步骤:
                1. 打开 testflight/test_app_launcher.py, 以下简称 py 文件
                2. 打开 res/sample/test_app_launcher(ast_helper_result).json, 以
                    下简称 json 文件
                3. 在 py 文件中找到 {prefix}.child_method 对应的行号, 例如对应行号 21,
                    则在 json 文件中找到键为 21 的对象, 如下所示:
                        {
                            "21": [
                                ["<class '_ast.Expr'>", "child_method"],
                                ["<class '_ast.Call'>", "child_method"],
                                ["<class '_ast.Name'>", "child_method"]
                            ], ...
                        }
                4. 在控制台找到调用方所在的日志行, 分析从 I4252 到 I3914 之间的日志内容
        """
        ast_line = ast_tree.get(lino)
        lk.logd(ast_line, length=12)
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
    """
    一些特殊 module 变量:
        top_module: pyfile 所在的 module. 如 'src.app', 'src.app.downloader' 等.
            top_module 可在 prj_modules 中找到.
        runtime_module: pyfile 运行时首先会被执行的 module, 或者成为非定义层的 module.
            例如:
                1 | a = 1
                2 | print(a)
                3 |
                4 | def bbb():
                5 |      pass
                6 |
            其中 [1, 2, 3, 6] 是 runtime_module 的区间
            runtime_module 的表示方法为在 top_module 后加 '.module' 如 'src.app
            .module', 'src.app.downloader.module' 等.
        除此之外的其他的 module 变量, 通常是指定义层的 module, 目前有 function defined 和
            class defined 两大类. 如 'src.app.main' (由 `def main():` 产生), 'src
            .app.Init' (由 `class Init:` 产生), 'src.app.Init.main' (由 `class
            Init:\ndef main(self):` 产生) 等.
    """
    
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
            top_module: str.
                当为空时, 将使用默认值 self.top_module: 'src.app'
                不为空时, 请注意传入的是当前要观察的 module 的上一级 module. 例如我们要编译
                    src.app.main.child_method 所在的层级, 则 top_module 应传入 src.
                    app.main. 用例参考: src.analyser.AssignAnalyser#update_assign
                    s
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
                lino: int. 行号, 从 1 开始数.
                obj_type: str. 对象类型, 例如 "<class 'FunctionDef'>" 等. 完整的支持
                    列表参考 src.utils.ast_helper.AstHelper#eval_node().
                obj_val: str/dict. 对象的值, 目前仅存在 str 或 dict 类型的数据.
                    示例:
                        (str) 'print'
                        (dict) {'src.downloader.Downloader':
                            'src.downloader.Downloader'} (多用于描述 Import)
            lino_indent: dict. {lino: indent, ...}. 由 AstHelper#create
                _lino_indent_dict() 提供.
                lino: int. 行号, 从 1 开始数.
                indent: int. 该行的列缩进位置, 为 4 的整数倍数, 如 0, 4, 8, 12 等.
            self.top_module: str. e.g. 'src.app'
        OT:
            module_linos: dict. {module: [lino, ...]}
                module: str. 模块的路径名.
                lino_list: list. 模块所涉及的行号列表, 已经过排序, 行号从 1 开始数, 最大
                    不超过当前 pyfile 的总代码行数.
                e.g. {
                    'src.app.module': [1, 2, 3, 9, 10],
                    'src.app.main': [4, 5, 8],
                    'src.app.main.child_method': [6, 7],
                    ...
                }
                有了 module_linos 以后, 我们就可以在已知 module 的调用关系的情况下, 专注
                于读取该 module 对应的区间范围, 逐行分析每条语句, 并进一步发现新的调用关系,
                以此产生裂变效应. 详见 src.analyser.VirtualRunner#main().
        """
        if top_module == '':
            top_module = self.top_module
            assert linos is None
            linos = list(ast_indents.keys())
            linos.sort()
        else:
            assert linos is not None
        
        lk.logd('indexing module linos', top_module)
        
        # ------------------------------------------------
        
        def eval_ast_line():
            ast_line = ast_tree[lino]  # type: list
            # ast_line is type of list, assert it not empty.
            assert ast_line
            # here we only take its first element.
            return ast_line[0]
        
        # ast_defs: ast definitions
        ast_defs = ("<class '_ast.FunctionDef'>", "<class '_ast.ClassDef'>")
        indent_module_holder = {}  # format: {indent: module}
        module_linos = {}  # format: {module: lino_list}
        
        last_indent = 0
        # last_indent 初始化值不影响方法的正常执行. 因为我们事先能保证 linos 参数的第一个 l
        # ino 的 indent 一定是正常的, 而伴随着第一个 lino 的循环结尾, last_indent 就能得
        # 到安全的更新, 因此 last_indent 的初始值无论是几都是安全的.
        
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
            
            # lk.loga(lino, indent, obj_type, obj_val)
            
            # ------------------------------------------------
            # 当 indent >= last_indent 时: 在 indent_holder 中开辟新键.
            # 当 indent < last_indent 时: 从 indent_holder 更新并移除高缩进的键.
            
            # noinspection PyUnresolvedReferences
            parent_module = indent_module_holder.get(
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
            
            node = module_linos.setdefault(current_module, [])
            node.append(lino)  # NOTE: the lino is in ordered
            
            # update indent_module_holder
            indent_module_holder.update({indent: current_module})
            # -> {0: 'src.app.main'}, {4: 'src.app.main.child_method'}, ...
            
            # update last_indent
            last_indent = indent
        
        # sort
        for lino_list in module_linos.values():
            lino_list.sort()
        
        lk.loga(indent_module_holder)
        lk.logt('[I4204]', module_linos)
        """
        -> module_linos = {
            'testflight.test_app_launcher.module': [1, 3, 4, 38, 39],
            'testflight.test_app_launcher.main'  : [8, 11, 12, 21, 22, 24, 25,
                                                    27, 28],
            'testflight.test_app_launcher.main.child_method' : [14, 15],
            'testflight.test_app_launcher.main.child_method2': [17, 18, 19],
            'testflight.test_app_launcher.Init'              : [31],
            'testflight.test_app_launcher.Init.main'         : [33, 35]
        }
        """
        
        return module_linos
    
    # ------------------------------------------------ checkers
    
    def is_prj_module(self, unknown_module: str):
        if unknown_module in self.prj_modules:
            return unknown_module
        unknown_module = get_parent_module(unknown_module)
        if unknown_module in self.prj_modules:
            return unknown_module
        return False


class AssignAnalyser:
    
    def __init__(self):
        self.top_module = module_analyser.top_module
        self.prj_modules = module_analyser.prj_modules
        
        self.max_lino = max(ast_indents.keys())
        
        self.top_linos = [
            lino
            for lino, indent in ast_indents.items()
            if indent == 0
        ]
        
        self.top_assigns = self.update_assigns(self.top_module, self.top_linos)
        # 注意: self.top_assigns 是包含非项目模块的.
        # -> {'os': 'os', 'downloader': 'testflight.downloader', 'Parser': 'test
        # flight.parser.Parser', 'main': 'testflight.app.main', 'Init': 'testfli
        # ght.app.Init'}
        self.top_assigns_prj_only = self.get_only_prj_modules(self.top_assigns)
        lk.loga(self.top_assigns)
        lk.loga(self.top_assigns_prj_only)
    
    @staticmethod
    def update_assigns(module, linos):
        assigns = {}
        
        module_linos = module_analyser.indexing_module_linos(
            get_parent_module(module), linos
        )
        # 注意: 这里第一个参数传入 get_parent_module(module) 而非 module. 原因详见 src.
        # analyser.ModuleAnalyser#indexing_module_linos() 注释.
        
        for module in module_linos.keys():
            var = module.rsplit('.', 1)[1]
            assigns[var] = module
        
        # ------------------------------------------------
        
        # ABBR: defs: definitions. imps: imports.
        # ast_defs = ("<class '_ast.FunctionDef'>", "<class '_ast.ClassDef'>")
        ast_imps = ("<class '_ast.Import'>", "<class '_ast.ImportFrom'>")
        
        for lino in linos:
            ast_line = ast_tree.get(lino)
            # lk.logt('[TEMPRINT]', lino, ast_line)
            # -> [(obj_type, obj_val), ...]
            
            for element in ast_line:
                obj_type, obj_val = element
                # lk.logt('[TEMPRINT]', obj_type, obj_val)
                if obj_type in ast_imps:
                    for k, v in obj_val.items():
                        module = k
                        var = v
                        assigns[var] = module
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
        assigns.update(self.update_assigns(target_module, lino_reachables))
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
    main(
        prjdir='../',
        pyfile='../testflight/test_app_launcher.py',
        exclude_dirs=['../dust/']
    )
