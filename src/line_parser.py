from lk_utils.lk_logger import lk


class VarsHolder:
    
    def __init__(self, global_vars=None):
        if global_vars:
            self.global_vars = global_vars
        else:
            self.global_vars = {}
        self.vars = {}  # format: {var: module}
    
    def update_global(self, var, module):
        self.global_vars.update({var: module})
    
    def update(self, var, module):
        self.vars.update({var: module})
    
    def get(self, var):
        if var in self.vars:
            return self.vars.get(var)
        else:
            return self.global_vars.get(var)
    
    def reset(self, vars_: dict):
        self.vars = vars_
    
    def clear(self):
        self.vars.clear()


class LineParser:
    
    def __init__(self, top_module, global_vars=None):
        self.top_module = top_module
        self.vars_holder = VarsHolder(global_vars)
        
        self.support_methods = {
            "<class '_ast.arg'>"        : self.parse_arg,
            "<class '_ast.Assign'>"     : self.parse_assign,
            "<class '_ast.Attribute'>"  : self.parse_attribute,
            "<class '_ast.Call'>"       : self.parse_call,
            "<class '_ast.ClassDef'>"   : self.parse_class_def,
            "<class '_ast.FunctionDef'>": self.parse_function_def,
            "<class '_ast.Import'>"     : self.parse_import,
            "<class '_ast.ImportFrom'>" : self.parse_import,
            # "<class '_ast.Name'>"       : self.parse_name,
        }
    
    def get_vars(self):
        return self.vars_holder.vars
    
    def get_global_vars(self):
        return self.vars_holder.global_vars
    
    def reset(self, var_reachables, master_module):
        """
        caller: src.module_analyser.ModuleAnalyser#analyse_module
        """
        if var_reachables:
            self.vars_holder.reset(var_reachables)
        else:
            self.vars_holder.clear()
        if master_module:
            self.vars_holder.update('self', master_module)
    
    # ------------------------------------------------
    
    def main(self, ast_line):
        """
        ARGS:
            ast_line: [(obj_type, obj_val), ...]
        
        IN: ast_line
            self.vars_holder
        OT: self.vars_holder (updated)
            module_called: list. [module, ...]
        
        caller: src.module_analyser.ModuleAnalyser#analyse_line
        """
        out = []
        for i in ast_line:
            obj_type, obj_val = i[0], i[1]
            # lk.loga(obj_type, obj_val)
            # obj_type: str. e.g. "<class '_ast.Call'>"
            # obj_val: str/dict. e.g. '__name__', {'os': 'os'}, ...
            method = self.support_methods.get(obj_type, self.do_nothing)
            res = method(obj_val)
            if res:
                if isinstance(res, list):
                    out.extend(res)
                else:
                    out.append(res)
        return out
    
    # ------------------------------------------------ support_methods
    
    @staticmethod
    def do_nothing(data):
        # lk.logt('[TEMPRINT]', 'nothing todo', data)
        # return ''
        pass
    
    def parse_arg(self, arg):
        """
        IN: arg: str. 函数的参数.
                e.g.
                    source = `def main(prjdir, pyfile)`
                    -> arg1 = 'prjdir', arg2 = 'pyfile' (调用者将会分两次传入)
        OT: self.vars_holder (updated)
            f'<{arg}>': str. 一个特殊的 module, 由 '<>' 包裹的.
        """
        module = self.vars_holder.get(arg)
        if module is None:
            module = f'<{arg}>'
        self.vars_holder.update(arg, module)
        return module
    
    def parse_assign(self, assign: dict):
        """
        IN: assign: {(str)new_var: (str)known_var}. e.g. {"init": "Init"}
                键是新变量, 值来自 self.assign_reachables.
        OT: (updated) self.assign_reached
        """
        out = []
        for new_var, known_var in assign.items():
            if known_var.startswith('self.'):
                module = known_var.replace(
                    'self', self.vars_holder.get('self'), 1
                )  # 'self.main' -> 'src.app.Init.main'
            else:
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
                out.append(module)
                # source_line = 'a = Init()' -> known_var = 'Init'
                self.vars_holder.update(new_var, module)
        return out
    
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
        
        if call.startswith('self.'):
            module = call.replace(
                'self', self.vars_holder.get('self'), 1
            )  # 'self.main' -> 'src.app.Init.main'
        else:
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
    
    def parse_class_def(self, data: str):
        """
        IN: data: str. e.g. "Init"
        OT: "src.app.Init"
        """
        var = data  # -> 'Init'
        module = self.top_module + '.' + var + '.__init__'
        # -> 'src.app.Init.__init__'
        lk.logt('[D3903]', 'parse_class_def', var, module)
        self.vars_holder.update(var, module)
    
    def parse_function_def(self, data: str):
        """
        IN: data: str. e.g. "main"
        OT: "src.app.main"
        """
        var = data  # -> 'main'
        module = self.top_module + '.' + var  # -> 'src.app.main'
        lk.logt('[D3902]', 'parse_function_def', var, module)
        self.vars_holder.update(var, module)
    
    def parse_import(self, data: dict):
        """
        IN: data: dict. {module: var}. e.g. {"lk_utils.lk_logger.lk": "lk"}
        """
        for module, var in data.items():
            self.vars_holder.update(var, module)
            # update: {"lk": "lk_utils.lk_logger.lk"}
