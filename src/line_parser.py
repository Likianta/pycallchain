from lk_utils.lk_logger import lk

from src.assign_analyser import VarsHolder, AssignAnalyser


class LineParser:
    
    def __init__(self, module_helper, ast_tree, ast_indents):
        self.assign_analyser = AssignAnalyser(
            module_helper, ast_tree, ast_indents
        )
        self.vars_holder = VarsHolder()
        
        self.support_methods = {
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
    
    def reset(self):
        """
        caller: src.module_analyser.ModuleAnalyser#analyse_module
        """
        self.vars_holder.clear()
    
    def main(self, ast_line):
        """
        ARGS:
            ast_line: [(obj_type, obj_val), ...]
        
        IN: ast_line
            self.vars_holder
        OT: self.vars_holder (updated)
            [module, ...]
        
        caller: src.module_analyser.ModuleAnalyser#analyse_line
        """
        out = []
        for i in ast_line:
            obj_type, obj_val = i
            # lk.loga(obj_type, obj_val)
            # obj_type: str. e.g. "<class '_ast.Call'>"
            # obj_val: str/dict. e.g. '__name__', {'os': 'os'}, ...
            method = self.support_methods.get(obj_type, self.do_nothing)
            res = method(obj_val)
            if res:
                out.append(res)
        return out
    
    # ------------------------------------------------ support_methods
    
    @staticmethod
    def do_nothing(data):
        lk.logt('[TEMPRINT]', 'nothing todo', data)
        # return ''
    
    def parse_arg(self, arg):
        """
        IN: arg: str. 函数的参数.
                e.g.
                    source = `def main(prjdir, pyfile)`
                    -> arg1 = 'prjdir', arg2 = 'pyfile' (调用者将会分两次传入)
        OT: self.vars_holder (updated)
            f'<{arg}>': str. 一个特殊的 module, 由 '<>' 包裹的.
        """
        self.vars_holder.update(arg, f'<{arg}>')
        return f'<{arg}>'
    
    def parse_assign(self, assign: dict):
        """
        IN: assign: {(str)new_var: (str)known_var}. e.g. {"init": "Init"}
                键是新变量, 值来自 self.assign_reachables.
        OT: (updated) self.assign_reached
        """
        for new_var, known_var in assign.items():
            module = self.vars_holder.get(known_var.split('.', 1)[0])
            lk.logt('[D0505]', known_var, module)
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
                self.vars_holder.update(new_var, module)
    
    def parse_attribute(self, call: str) -> str:
        """
        IN: call: e.g. 'downloader.Downloader'
                call 的值是类似于 module 的写法, 可以按照点号切成多个片段, 其中第一个片段是
                var, 可在 self.vars_holder 中发现它, 进而得到它的真实 module; 其余则是
                该 module 级别以下的调用, 简单加在该 module 末尾即可, 即 'downloader
                .Downloader' -> self.assign_reached: {'downloader': 'testflight
                .downloader'} -> 'testflight.downloader' -> 'testflight
                .downloader.Downloader' -> 更新到 self.call_chain 中.
        OT: (updated) self.call_chain
        """
        if '.' in call:
            head, tail = call.split('.', 1)
        else:
            head, tail = call, ''
        
        module = self.vars_holder.get(head)
        
        lk.logt('[D0521]', call, module)
        
        if module is None:
            # var = 'os'
            return ''
        else:
            # var = 'downloader.Downloader'
            if tail:
                module += '.' + tail
            return module
    
    def parse_call(self, call: str):
        """
        IN: data: e.g. 'child_method'
        OT: (updated) self.call_chain
        
        NOTE: parse_call 与 parse_attribute 方法无区别.
        """
        if '.' in call:
            head, tail = call.split('.', 1)
        else:
            head, tail = call, ''
        
        module = self.vars_holder.get(head)
        
        lk.logt('[D0521]', call, module)
        
        if module is None:
            # var = 'os'
            return ''
        else:
            # var = 'downloader.Downloader'
            if tail:
                module += '.' + tail
            return module
    
    @staticmethod
    def parse_class_def(data):
        # raise Exception
        pass
    
    @staticmethod
    def parse_function_def(data):
        # raise Exception
        pass
