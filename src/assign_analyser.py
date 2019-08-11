from lk_utils.lk_logger import lk

from src.line_parser import LineParser


class AssignAnalyser:
    
    def __init__(self, module_helper, ast_tree, ast_indents):
        self.module_helper = module_helper
        self.ast_tree = ast_tree
        self.ast_indents = ast_indents
        
        self.max_lino = max(ast_indents.keys())
        lk.loga(self.max_lino)
        
        self.top_linos = [
            lino for lino, indent in ast_indents.items()
            if indent == 0
        ]
        
        self.top_assigns = self.find_global_vars()  # type: dict
        # -> {'os': 'os', 'downloader': 'testflight.downloader', 'Parser':
        # 'testflight.parser.Parser', 'main': 'testflight.app.main', 'Init':
        # 'testflight.app.Init'}
        lk.loga(self.top_assigns)
    
    def find_global_vars(self):
        """
        哪些是全局变量:
            runtime 层级的 Import, ImportFrom
            runtime 层级的 Assign
            行内的 `global xxx`

        IN: module_linos: provided by src.module_analyser.ModuleIndexing
                #indexing_module_linos
            self.module_helper
            self.ast_tree
            self.ast_indents
        OT: dict. {var: module}
        """
        top_linos = tuple(
            lino for lino, indent in self.ast_indents.items()
            if indent == 0
        )
        
        # ------------------------------------------------
        # runtime 层级的 Import, ImportFrom & runtime 层级的 Assign
        
        line_parser = LineParser()
        
        for lino in top_linos:
            ast_line = self.ast_tree[lino]
            line_parser.main(ast_line)
            # line_parser 会自动帮我们处理 ast_line 涉及的 Import, ImportFrom,
            # Assign 等的变量与 module 的对照关系.
        
        # ------------------------------------------------
        # 行内的 `global xxx`
        
        for lino in self.ast_indents:
            if lino in top_linos:
                continue
            pass  # TODO
        
        return line_parser.get_vars()
    
    def indexing_assign_reachables(
            self, target_module, module_linos
    ) -> dict:
        if self.module_helper.is_runtime_module(target_module):
            # 相当于返回 self.find_global_vars() 的结果.
            return self.top_assigns
        
        if target_module not in module_linos:
            lk.logt('[E2459]', target_module, module_linos)
            raise Exception

        lk.logt('[I0114]', target_module)
        
        # ------------------------------------------------
        
        """
        workflow:
            1. 以 target_module 的 linos[0] 为起点, 向前找到第一个 indent 为 0 的
            lino
            2. 以 target_module 的 linos[-1] 为起点, 向后找到第一个 indent 为 0 的
            lino
            3. 在此区间内, 将所有 ast_defs 进行解析, 并认定为 var_reachables
        """
        
        # ------------------------------------------------ lino reachables
        
        target_linos = module_linos[target_module]
        curr_module_lino = target_linos[0]
        start_offset, end_offset = target_linos[0], target_linos[-1] + 1
        
        # the start lino reachable
        indent = self.ast_indents[start_offset]
        # lk.logt('[TEMPRINT]20190811182309', target_module, start_offset,
        #         indent)
        if indent == 0:
            pass
        else:
            while True:
                parent_module = self.module_helper.get_parent_module(
                    target_module
                )
                # lk.logt('[TEMPRINT]20190811182549', target_module,
                #         parent_module)
                parent_linos = module_linos[parent_module]
                start_offset, end_offset = parent_linos[0], parent_linos[-1] + 1
                parent_indent = self.ast_indents[start_offset]
                if parent_indent == 0:
                    break
                else:
                    continue
        
        # the end lino reachable
        while end_offset < self.max_lino:
            if end_offset in self.ast_indents:
                indent = self.ast_indents[end_offset]
                if indent == 0:
                    break
            end_offset += 1
        
        # get lino reachalbes
        lino_reachables = [
            lino
            for lino in range(start_offset, end_offset)
            if lino in self.ast_indents and lino != curr_module_lino
        ]
        """
        这里为什么要判断 `lino != curr_module_lino`?
        因为 target_module 不能指任自身, 所以应去除.
        例如 target_module = 'src.app.module', 在源码中, 不能因此自动产生 `module:
        src.app.module` 的对应关系. 所以不能加入到 assigns 中.
        """
        
        # parse vars
        line_parser = LineParser()
        
        ast_defs = ("<class '_ast.FunctionDef'>", "<class '_ast.ClassDef'>")
        
        for lino in lino_reachables:
            ast_line = self.eval_ast_line(lino)
            if ast_line[0] in ast_defs:
                line_parser.main(ast_line)
        
        return line_parser.get_vars()
    
    def eval_ast_line(self, lino):
        ast_line = self.ast_tree[lino]  # type: list
        # ast_line is type of list, assert it not empty.
        assert ast_line
        # here we only take its first element. which will show us method or
        # class definitions.
        return ast_line[0]
