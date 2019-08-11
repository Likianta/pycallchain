from os.path import abspath

from lk_utils import file_sniffer
from lk_utils.lk_logger import lk

from src.assign_analyser import AssignAnalyser
from src.line_parser import LineParser


class ModuleHelper:
    top_module = ''
    runtime_module = ''
    
    def __init__(self, prjdir, exclude_dirs=None):
        self.prjdir = prjdir
        # self.top_module = self.get_module_by_filepath(pyfile)
        # self.runtime_module = self.top_module + '.module'
        self.prj_modules = self.load_prj_modules(exclude_dirs)  # -> [modules]
    
    def bind_file(self, pyfile):
        self.top_module = self.get_module_by_filepath(pyfile)
        self.runtime_module = self.top_module + '.module'
    
    # ------------------------------------------------ loads
    
    def load_prj_modules(self, exclude_dirs=None) -> tuple:
        """
        获得项目所有可导入的模块路径.

        第三方模块分为项目模块和外部模块. 本程序只负责分析项目模块的依赖关系, 因此通过本方法过滤
        掉外部模块的路径.
        例如:
            import sys  # builtin module
            import src.downloader  # project module
        那么本方法只收录 ['src.downloader'], 不收录 ['sys'].

        IN: self.prjdir: str. an absolute project directory. e.g. 'D:/myprj/'
            exclude_dirs: iterable. <- FIXME: no usage for now, and maybe
                                        removed in the future.
        OT: prj_modules: list. e.g. ['testflight.test_app_launcher',
        'testflight
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
        
        prj_modules = tuple(
            self.get_module_by_filepath(x)
            for x in all_pyfiles
        )
        # -> ('src.app', 'src.downloader', ...)
        
        lk.loga(len(all_files), len(all_pyfiles))
        # | lk.loga(len(all_pyfiles), prj_modules)
        
        return prj_modules
    
    # ------------------------------------------------ gets
    
    def get_prj_modules(self):
        return self.prj_modules
    
    def get_prj_module(self, module) -> str:
        """
        IN: self.prj_modules: tuple
        OT: prj_module: str
        """
        while module:
            if module in self.prj_modules:
                return module
            else:
                module = self.get_module_seg(module, 'l1')
        return ''  # 说明此 module 不存在于 prj_modules.
    
    def get_top_module(self):
        assert self.top_module, \
            'please call ModuleHelper#bind_file() first.'
        return self.top_module
    
    def get_runtime_module(self):
        assert self.runtime_module, \
            'please call ModuleHelper#bind_file() first.'
        return self.runtime_module
    
    def get_parent_module(self, module: str):
        if '.' not in module:
            return ''
        else:
            # module = module.rsplit('.', 1)[0]
            # if module in self.prj_modules:
            #     # 'src.app.main' -> 'src.app'
            #     module += '.module'
            # return module
            return self.get_module_seg(module, 'l1')
    
    @staticmethod
    def get_module_seg(module: str, cut: str):
        """
        ARGS:
            module
            cut: str. 'l0'/'l1'/'r0'/'r1'
                假设要切分的 module 为 'A.B.C'
                'l0': 取第一个片段 -> 'A'
                'l1': 取非末尾片段 -> 'A.B'
                'r0': 取末尾片段 -> 'C'
                'r1': 取非第一个片段 -> 'B.C'
        """
        if '.' not in module:
            return ''
        if cut == 'l0':
            return module.split('.', 1)[0]
        elif cut == 'l1':
            return module.rsplit('.', 1)[0]
        elif cut == 'r0':
            return module.rsplit('.', 1)[1]
        elif cut == 'r1':
            return module.split('.', 1)[1]
        else:
            lk.logt('[E4544]', 'the `cut` must be one of the following values: '
                               '"l0", "l1", "r0" or "r1"', cut, h='parent')
            raise ValueError
    
    def get_module_by_filepath(self, fpath):
        """
        IN: fpath: str. 请确保传入的是绝对路径. e.g. 'D:/myprj/src/app.py'
        OT: module: str. e.g. 'src.app'
        """
        return fpath.replace(self.prjdir, '', 1).replace('/', '.')[:-3]
        # fpath = 'D:/myprj/src/app.py' -> 'src.app'
    
    def get_pyfile_by_prj_module(self, prj_module):
        return self.prjdir + prj_module.replace('.', '/') + '.py'
    
    # ------------------------------------------------ checks
    
    def is_top_module(self, module: str):
        return module in self.prj_modules
    
    @staticmethod
    def is_runtime_module(module: str):
        return bool(module.endswith('.module'))
    
    def is_prj_module(self, unknown_module: str):
        """
        IN: unknown_module
            self.prj_modules
        OT: (<bool is_prj_module_or_not>, <str related_prj_module>)
        """
        if unknown_module in self.prj_modules:
            return True, unknown_module
        for i in self.prj_modules:
            if unknown_module.startswith(i + '.'):
                return True, i
        else:
            return False, ''


class ModuleIndexing:
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
            其中 linos = [1, 2, 3, 6] 是 runtime_module 的区间.
            runtime_module 的表示方法为在 top_module 后加 '.module' 如 'src.app
            .module', 'src.app.downloader.module' 等.
    除此之外的其他的 module 变量, 通常是指定义层的 module, 目前有 function defined 和
    class defined 两大类. 如 'src.app.main' (由 `def main()` 产生), 'src.app.Init'
    (由 `class Init` 产生), 'src.app.Init.main' (由 `class Init:  def main(self):`
    产生) 等.
    """
    
    def __init__(self, module_helper: ModuleHelper, ast_tree, ast_indents):
        """
        ARGS:
            module_helper: ModuleHelper.
            ast_tree: dict. 用于定位和获取指定行号的抽象行信息.
            ast_indents: dict. 用于定位和获取指定行号的缩进位置.
        """
        self.module_helper = module_helper
        self.ast_tree = ast_tree
        self.ast_indents = ast_indents
        
        self.top_module = module_helper.get_top_module()
        self.runtime_module = module_helper.get_runtime_module()
        self.prj_linos = list(ast_indents.keys())
    
    def indexing_module_linos(self, master_module='', linos=None):
        """
        获取 pyfile 内每个 module 对应的行号范围.
        根据 {lino:indent} 和 ast_tree 创建 {module:linos} 的字典.
        注: 每个 module (无论是父子关系还是兄弟关系) 之间的范围互不重叠.

        IN: master_module: str.
                当为空时, 将使用默认值 self.top_module (e.g. 'src.app')
                不为空时, 请注意传入的是当前要观察的 module 的上一级 module. 例如我们要编译
                    src.app.main.child_method 所在的层级, 则 top_module 应传入 src
                    .app.main. 用例参考: src.analyser.AssignAnalyser#update
                    _assigns
            linos: None/list. 您可以自定义要读取的 module 范围, 本方法会仅针对这个区间进行
                编译.
                例如:
                    1 | def aaa():
                    2 |     def bbb():      # <- start
                    3 |         def ccc():
                    4 |             pass
                    5 |                     # <- end
                    6 | def ddd():
                    7 |     pass
                则本方法只编译 range(2, 5) 范围内的数据, 并返回 {'src.app.aaa.bbb': [
                2, 5], 'src.app.aaa.bbb.ccc': [3, 4]} 作为编译结果.
                注意: 指定的范围的开始位置的缩进必须小于等于结束位置的缩进 (空行除外).
                如果该参数为 None, 则默认使用所有行号 (`range(0, len(code_lines))`).
            self.ast_tree: dict. {lino: [(obj_type, obj_val), ...], ...}
                lino: int. 行号, 从 1 开始数.
                obj_type: str. 对象类型, 例如 "<class 'FunctionDef'>" 等. 完整的支持
                    列表参考 src.utils.ast_helper.AstHelper#eval_node().
                obj_val: str/dict. 对象的值, 目前仅存在 str 或 dict 类型的数据.
                    示例:
                        (str) 'print'
                        (dict) {'src.downloader.Downloader':
                            'src.downloader.Downloader'} (多用于描述 Import)
            self.ast_indents: dict. {lino: indent, ...}. 由 AstHelper#create
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
        if master_module == '':
            master_module = self.top_module
            assert linos is None
            linos = self.prj_linos
            # the linos are already sorted.
        else:
            assert linos is not None
        
        lk.logd('indexing module linos', master_module)
        
        # ------------------------------------------------
        
        # ast_defs: abstract syntax tree definitions
        ast_defs = ("<class '_ast.FunctionDef'>", "<class '_ast.ClassDef'>")
        indent_module_holder = {}  # format: {indent: module}
        module_linos = {}  # format: {module: linos}
        
        last_module = ''
        last_indent = 0
        # last_indent 初始化值不影响方法的正常执行. 因为我们事先能保证 linos 参数的第一个
        # lino 的 indent 一定是正常的, 而伴随着第一个 lino 的循环结尾, last_indent 就能
        # 得到安全的更新, 因此 last_indent 的初始值无论是几都是安全的.
        
        for lino in linos:
            obj_type, obj_val = self.eval_ast_line(lino)
            # -> "<class '_ast.FunctionDef'>", 'main'
            
            indent = self.ast_indents.get(lino, -1)
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
                # assert obj_type not in ast_defs
            
            # lk.loga(lino, indent, obj_type, obj_val)
            
            # ------------------------------------------------
            # 当 indent >= last_indent 时: 在 indent_holder 中开辟新键.
            # 当 indent < last_indent 时: 从 indent_holder 更新并移除高缩进的键.
            
            parent_module = indent_module_holder.get(
                indent - 4, master_module
            )
            """
            case 1:
                indent = 0, obj_val = 'main'
                -> indent - 4 = -4
                -> -4 not in indent_module_dict. so assign default:
                    parent_module = master_module = 'src.app'
            case 2:
                indent = 4, obj_val = 'child_method'
                -> indent - 4 = 0
                -> parent_module = 'src.app.main'
            """
            if obj_type in ast_defs:
                # obj_type = "<class 'FunctionDef'>", obj_val = 'main'
                current_module = parent_module + '.' + obj_val
                # -> 'src.app.main'
            elif indent == 0 \
                    or last_module == self.runtime_module:
                current_module = self.runtime_module
                # | current_module = parent_module + '.module'
            else:
                # indent > 0 and last_parent_module not in (master_module, self
                # .runtime_module
                current_module = parent_module
            
            # update module_linos
            node = module_linos.setdefault(current_module, [])
            node.append(lino)  # NOTE: the lino is in ordered
            
            # update indent_module_holder
            indent_module_holder.update({indent: current_module})
            # -> {0: 'src.app.main'}, {4: 'src.app.main.child_method'}, ...
            
            # update last vars
            last_module = current_module
            last_indent = indent
        
        lk.logt('[D3421]', self.top_module, indent_module_holder)
        lk.logt('[I4204]', self.top_module, tuple(module_linos.keys()))
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
        
        # raise Exception  # TEST
        return module_linos
    
    def find_prj_modules(self):
        prj_modules = []
        
        # ast_imps: abstract syntax tree imports
        ast_imps = ("<class '_ast.ImportFrom'>", "<class '_ast.Import'>")
        
        for lino in self.prj_linos:
            # lk.loga(lino)
            
            obj_type, obj_val = self.eval_ast_line(lino)
            # -> "<class '_ast.FunctionDef'>", 'main'
            
            if obj_type in ast_imps:
                """
                obj_type = "<class '_ast.ImportFrom'>"
                obj_val = {"lk_utils.lk_logger.lk": "lk"}
                """
                for module in obj_val:
                    prj_module = self.module_helper.get_prj_module(module)
                    if prj_module:
                        prj_modules.append(prj_module)
        
        return prj_modules
    
    # ------------------------------------------------
    
    def eval_ast_line(self, lino):
        ast_line = self.ast_tree[lino]  # type: list
        # ast_line is type of list, assert it not empty.
        assert ast_line
        # here we only take its first element. which will show us method or
        # class definitions.
        return ast_line[0]


class ModuleAnalyser:
    line_parser = None
    
    def __init__(self, module_helper: ModuleHelper, ast_tree, ast_indents):
        self.module_helper = module_helper
        self.ast_tree = ast_tree
        self.ast_indents = ast_indents
        
        self.module_calls = {}  # format: {module: [call, ...], ...}
    
    def main(self):
        """
        IN: module_linos
        OT: (A, B)
                A: self.module_calls (updated)
                B: prj_modules
        """
        module_indexing = ModuleIndexing(
            self.module_helper, self.ast_tree, self.ast_indents
        )
        assign_analyser = AssignAnalyser(
            self.module_helper, self.ast_tree, self.ast_indents
        )
        
        prj_modules = module_indexing.find_prj_modules()
        
        module_linos = module_indexing.indexing_module_linos()
        
        self.line_parser = LineParser(assign_analyser.top_assigns)
        
        # ------------------------------------------------
        
        for module, linos in module_linos.items():
            var_reachables = assign_analyser.indexing_assign_reachables(
                module, module_linos
            )
            self.analyse_module(module, linos, var_reachables)
        
        # ------------------------------------------------
        
        return self.module_calls, prj_modules
    
    def analyse_module(self, module, linos, var_reachables):
        """
        发现该 module 下的与其他 module 之间的调用关系.
        """
        lk.logd('analyse_module', module, style='■')
        
        related_calls = []
        self.line_parser.reset(var_reachables)
        
        for lino in linos:
            ast_line = self.ast_tree[lino]
            modules = self.analyse_line(ast_line)
            for m in modules:
                if m not in related_calls:
                    related_calls.append(m)
        
        self.module_calls.update({module: tuple(related_calls)})
    
    def analyse_line(self, ast_line):
        return self.line_parser.main(ast_line)
