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

from src.ast_analyser import AstAnalyser
from src.module_analyser import ModuleAnalyser
from src.writer import Writer


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
    global ast_tree, ast_indents
    ast_tree = ast_analyser.main()
    # -> {lino: [(obj_type, obj_val), ...]}
    ast_indents = ast_analyser.get_lino_indent_dict()
    # -> {lino: indent}
    
    global module_analyser
    module_analyser = ModuleAnalyser(
        prjdir, pyfile, ast_tree, ast_indents
    )
    
    runner = VirtualRunner()
    runner.main()


class VirtualRunner:
    
    def __init__(self):
        self.writer = Writer(module_analyser.get_top_module())
        
        self.module_linos = module_analyser.indexing_module_linos()
        # -> {module: [lino, ...]}
        
        self.assign_analyser = AssignAnalyser()
        
        self.assign_reachables = self.assign_analyser.top_assigns_prj_only
        # -> {var: module}
        self.assign_reached = {}  # {var: feeler}
        
        self.call_chain = []
        self.outer_call_chain = []
        
        self.registered_methods = {
            "<class '_ast.Assign'>"   : self.parse_assign,
            "<class '_ast.Attribute'>": self.parse_attribute,
            "<class '_ast.Call'>"     : self.parse_call,
            # "<class '_ast.ClassDef'>"   : self.parse_class_def,
            # "<class '_ast.FunctionDef'>": self.parse_function_def,
            # "<class '_ast.Import'>"     : self.parse_import,
            # "<class '_ast.ImportFrom'>" : self.parse_import,
            # "<class '_ast.Name'>"       : self.parse_name,
        }
    
    def main(self):
        """
        
        PS: 请配合 src.utils.ast_helper.dump_by_filter_schema() 的输出结果 (或 res
        /sample/test_app_launcher(ast_helper_result).json) 完成本方法的制作.
        
        flow:
            testflight.test_app_launcher.module
                testflight.test_app_launcher.main
                    testflight.test_app_launcher.child_method
                    testflight.test_app_launcher.child_method2
                    testflight.test_app_launcher.Init
                    testflight.test_app_launcher.Init.main
                    testflight.downloader.Downloader
                    testflight.parser.Parser
            如需追踪观察此流, 请查看 log 中的 [I3914] 级别打印.
        """
        runtime_module = module_analyser.get_runtime_module()
        calls = self.run_block(runtime_module)
        calls = self.writer.record(runtime_module, calls)
        self.recurse_module_called(calls)
        
        lk.logt('[TEMPRINT]', self.writer.writer)
    
    def recurse_module_called(self, calls):
        for i in calls:
            child_calls = self.run_block(i)
            child_calls = self.writer.record(i, child_calls)
            # lk.logt('[I4429]', len(child_calls), child_calls)
            self.recurse_module_called(child_calls)
    
    def run_block(self, current_module: str):
        """
        IN: module: str
        OT: self.calls: list
        """
        lk.logd('run block', current_module, style='■')
        
        # update assign_reachables
        # self.assign_reachables 需要在每次更新 self.run_block() 时同步更新. 这是因为,
        # 不同的 block 定义的区间范围不同, 而不同的区间范围包含的变量指配 (assigns) 也可能是
        # 不同的.
        # 例如在 module = testflight.test_app_launcher.module 层级, self.module
        # _hooks = {'main': 'testflight.test_app_launcher.main'}. 到了 module =
        # testflight.test_app_launcher.Init 来运行 run_block 的时候, self.module
        # _hooks 就变成了 {'main': 'testflight.test_app_launcher.Init.main'}. 也就
        # 是说在不同的 block 区间, 'main' 指配的 module 对象发生了变化, 因此必须更新 self
        # .assign_reachables 才能适应最新变化.
        self.assign_reachables = self.assign_analyser \
            .indexing_assign_reachables(
            current_module, self.module_linos
        )
        lk.logt('[I4252]', 'update assign_reachables',
                self.assign_reachables)
        
        # reset assign_reached and call_chain
        self.assign_reached.clear()
        self.call_chain.clear()
        
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
        
        lk.logt('[I3914]', self.call_chain)
        return self.call_chain
    
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
        # lk.logd(ast_line, length=12)
        # -> [(obj_type, obj_val), ...]
        
        for i in ast_line:
            obj_type, obj_val = i
            # lk.loga(obj_type, obj_val)
            # obj_type: str. e.g. "<class '_ast.Call'>"
            # obj_val: str/dict. e.g. '__name__', {'os': 'os'}, ...
            
            method = self.registered_methods.get(obj_type, self.do_nothing)
            method(obj_val)
    
    # ------------------------------------------------ run_line related
    
    @staticmethod
    def do_nothing(data):
        # lk.logt('[TEMPRINT]', 'nothing todo', data)
        pass
    
    def parse_assign(self, assign: dict):
        """
        IN: assign: e.g. {"init": "Init"}
                键是新变量, 值来自 self.assign_reachables.
        OT: (updated) self.assign_reached
        """
        lk.logt('[D0505]', assign)
        
        for new_var, known_var in assign.items():
            module = self.assign_reachables.get(known_var.split('.', 1)[0])
            """
            case 1:
                known_var = "downloader.Downloader"
                -> known_var.split('.', 1)[0] = "downloader"
                -> module = 'testflight.downloader'
            """
            if module is None:
                # source_line = 'a = os.path(...)' -> known_var = 'os.path'
                continue
            else:
                # source_line = 'a = Init()' -> known_var = 'Init'
                self.assign_reached[new_var] = module
    
    def parse_attribute(self, call: str):
        """
        IN: call: e.g. 'downloader.Downloader'
                call 的值是类似于 module 的写法, 可以按照点号切成多个片段, 其中第一个片段是
                var, 可在 self.assign_reached 中发现它, 进而得到它的真实 module; 其余
                则是该 module 级别以下的调用, 简单加在该 module 末尾即可, 即 'downloader
                .Downloader' -> self.assign_reached: {'downloader': 'testflight
                .downloader'} -> 'testflight.downloader' -> 'testflight
                .downloader.Downloader' -> 更新到 self.call_chain 中.
        OT: (updated) self.call_chain
        """
        if '.' in call:
            head, tail = call.split('.', 1)
        else:
            head, tail = call, ''
        # assert var in self.assign_reached
        module = self.assign_reached.get(head)
        
        lk.logt('[D0521]', call, module)
        
        if module is None:
            # var = 'os'
            return
        else:
            # var = 'downloader.Downloader'
            if tail:
                module += '.' + tail
            self.call_chain.append(module)
    
    def parse_call(self, var: str):
        """
        IN: data: e.g. 'child_method'
        OT: (updated) self.call_chain
        """
        if '.' in var:
            head, tail = var.split('.', 1)
        else:
            head, tail = var, ''
        module = self.assign_reachables.get(head)
        
        lk.logt('[D0005]', var, module)
        
        if module is None:
            # e.g. var = 'abspath' -> module = None
            return
        else:
            if tail:
                module += '.' + tail
            # e.g. var = 'child_method' -> module = 'src.app.main.child_method'
            self.call_chain.append(module)
    
    @staticmethod
    def parse_class_def(data):
        lk.logt('[E1036]', 'a class def found in block region, this should not '
                           'be happend', data)
        raise Exception
    
    @staticmethod
    def parse_function_def(data):
        lk.logt('[E1036]', 'a function def found in block region, this should '
                           'not be happend', data)
        raise Exception


class AssignAnalyser:
    
    def __init__(self):
        self.prj_modules = module_analyser.prj_modules
        
        self.max_lino = max(ast_indents.keys())
        lk.loga(self.max_lino)
        
        self.top_linos = [
            lino
            for lino, indent in ast_indents.items()
            if indent == 0
        ]
        
        runtime_module = module_analyser.get_runtime_module()
        self.top_assigns = self.update_assigns(runtime_module, self.top_linos)
        # 注意: self.top_assigns 是包含非项目模块的.
        # -> {'os': 'os', 'downloader': 'testflight.downloader', 'Parser':
        # 'testflight.parser.Parser', 'main': 'testflight.app.main', 'Init':
        # 'testflight.app.Init'}
        self.top_assigns_prj_only = self.get_only_prj_modules(self.top_assigns)
        lk.loga(self.top_assigns)
        lk.loga(self.top_assigns_prj_only)
    
    @staticmethod
    def update_assigns(target_module, linos):
        assigns = {}
        
        module_linos = module_analyser.indexing_module_linos(
            get_parent_module(target_module), linos
        )
        # 注意: 这里第一个参数传入 get_parent_module(module) 而非 module. 原因详见 src
        # .analyser.ModuleAnalyser#indexing_module_linos() 注释.
        
        for module in module_linos.keys():
            if module == target_module:
                """
                因为 target_module 不能指任自身, 所以应去除.
                例如 target_module = 'src.app.module', 在源码中, 不能因此自动产生
                module-src.app.module 的对应关系. 所以不能加入到 assigns 中.
                """
                continue
            var = module.rsplit('.', 1)[1]
            # lk.logt('[TEMPRINT]', var, module)
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
        # the target_linos is already in ordered.
        target_linos_start = target_linos[0]
        target_indent = ast_indents[target_linos_start]
        if target_indent == 0:
            lino_reachables = [
                lino
                for lino in range(target_linos[0], target_linos[-1])
                if lino in ast_indents
            ]
            master_module = target_module
        else:
            # target_module = 'testflight.app.main.child_method'
            # -> parent_module = 'testflight.app.main'
            
            while True:
                parent_module = get_parent_module(target_module)
                parent_linos = module_linos[parent_module]
                parent_linos_start = parent_linos[0]
                parent_indent = ast_indents[parent_linos_start]
                if parent_indent == 0:
                    lino_reachables = [
                        lino
                        for lino in range(parent_linos[0], parent_linos[-1])
                        if lino in ast_indents
                    ]
                    break
                else:
                    continue
            
            master_module = parent_module
        
        if only_prj_modules:
            assigns = self.top_assigns_prj_only.copy()
        else:
            assigns = self.top_assigns.copy()
        
        assigns.update(
            self.update_assigns(
                master_module, lino_reachables
            )
        )
        
        # FIXME: dirty code
        var = target_module.rsplit('.', 1)[1]
        if assigns.get(var) == target_module:
            assigns.pop(var)
        
        if only_prj_modules:
            return self.get_only_prj_modules(assigns)
        else:
            return assigns
    
    def get_only_prj_modules(self, assigns: dict):
        new_assigns = {}
        for var, module in assigns.items():
            for prj_module in self.prj_modules:
                if module.startswith(prj_module):
                    new_assigns[var] = module
                    break
        return new_assigns


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
        pyfile='../testflight/app.py'
    )
