from lk_utils.lk_logger import lk

from src.assign_analyser import AssignAnalyser
from src.writer import Writer


class VirtualRunner:
    """
    虚拟运行机将分析 pyfile 并生成对象之间的调用关系.
    """
    
    def __init__(self, module_analyser, ast_tree, ast_indents):
        self.module_analyser = module_analyser
        self.ast_tree = ast_tree
        self.ast_indents = ast_indents
        
        self.writer = Writer(module_analyser.get_top_module())
        self.module_linos = module_analyser.indexing_module_linos()
        # -> {module: [lino, ...]}
        
        self.assign_analyser = AssignAnalyser(
            module_analyser, ast_tree, ast_indents
        )
        self.assign_reachables = self.assign_analyser.top_assigns_prj_only
        # -> {var: module}
        self.assign_reached = {}  # {var: feeler}
        
        self.call_chain = []
        self.outer_call_chain = []
        
        self.registered_methods = {
            "<class '_ast.arg'>"      : self.parse_arg,
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
        runtime_module = self.module_analyser.get_runtime_module()
        calls = self.run_block(runtime_module)
        calls = self.writer.record(runtime_module, calls)
        self.recurse_module_called(calls)
        
        self.writer.show()
    
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
        ast_line = self.ast_tree.get(lino)
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
    
    def parse_arg(self, arg: str):
        pass
    
    def parse_assign(self, assign: dict):
        """
        IN: assign: e.g. {"init": "Init"}
                键是新变量, 值来自 self.assign_reachables.
        OT: (updated) self.assign_reached
        """
        for new_var, known_var in assign.items():
            if known_var.startswith('self.'):
                known_var = known_var.replace('self.', '', 1)
                # 'self.run_line' -> 'row_line'
            module = self.assign_reachables.get(known_var.split('.', 1)[0])
            lk.logt('[D0505]', assign, module)
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
                self.call_chain.append(module)
    
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
