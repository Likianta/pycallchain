from lk_utils.lk_logger import lk

from src.module_analyser import ModuleHelper


class AssignAnalyser:
    
    def __init__(self, module_helper: ModuleHelper, ast_tree, ast_indents):
        self.module_helper = module_helper
        self.ast_tree = ast_tree
        self.ast_indents = ast_indents
        
        self.prj_modules = module_helper.get_prj_modules()  # type: tuple
        
        self.max_lino = max(ast_indents.keys())
        lk.loga(self.max_lino)
        
        self.top_linos = [
            lino for lino, indent in ast_indents.items()
            if indent == 0
        ]
        
        runtime_module = module_helper.get_runtime_module()
        self.top_assigns = self.update_assigns(runtime_module, self.top_linos)
        # -> {'os': 'os', 'downloader': 'testflight.downloader', 'Parser':
        # 'testflight.parser.Parser', 'main': 'testflight.app.main', 'Init':
        # 'testflight.app.Init'}
        self.top_assigns = self.get_only_prj_modules(self.top_assigns)
        # -> {'downloader': 'testflight.downloader', 'Parser': 'testflight
        # .parser.Parser', 'main': 'testflight.app.main', 'Init': 'testflight
        # .app.Init'}
        lk.loga(self.top_assigns)
    
    def update_assigns(self, target_module, linos):
        assigns = {}
        
        module_linos = self.module_helper.indexing_module_linos(
            self.module_helper.get_parent_module(target_module), linos
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
            ast_line = self.ast_tree.get(lino)
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
        if target_module == self.module_helper.get_runtime_module():
            return self.top_assigns_prj_only if only_prj_modules \
                else self.top_assigns
        
        # ------------------------------------------------
        
        target_linos = module_linos[target_module]
        start_offset, end_offset = target_linos[0], target_linos[-1] + 1
        indent = self.ast_indents[start_offset]
        if indent == 0:
            module = target_module
        else:
            while True:
                parent_module = self.module_helper.get_parent_module(
                    target_module
                )
                parent_linos = module_linos[parent_module]
                start_offset, end_offset = parent_linos[0], parent_linos[-1] + 1
                parent_indent = self.ast_indents[start_offset]
                if parent_indent == 0:
                    break
                else:
                    continue
            module = parent_module
        
        while end_offset < self.max_lino:
            if end_offset in self.ast_indents:
                indent = self.ast_indents[end_offset]
                if indent == 0:
                    break
            end_offset += 1
        
        lino_reachables = [
            lino
            for lino in range(start_offset, end_offset)
            if lino in self.ast_indents
        ]
        
        # ------------------------------------------------
        
        if only_prj_modules:
            assigns = self.top_assigns_prj_only.copy()
        else:
            assigns = self.top_assigns.copy()
        
        assigns.update(
            self.update_assigns(
                module, lino_reachables
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
        return {
            k: v for k, v in assigns.items()
            if self.module_helper.is_prj_module(k)
        }
