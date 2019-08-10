from src.ast_analyser import AstAnalyser
from src.module_analyser import ModuleAnalyser, ModuleHelper


class PyfileAnalyser:
    
    def __init__(self, module_helper: ModuleHelper):
        self.module_helper = module_helper
    
    def main(self, pyfile: str):
        """
        IN:
        OT: prj_modules: list
        """
        self.module_helper.bind_file(pyfile)
        
        ast_analyser = AstAnalyser(pyfile)
        ast_tree = ast_analyser.main()
        ast_indents = ast_analyser.get_lino_indent_dict()
        
        module_analyser = ModuleAnalyser(
            self.module_helper, ast_tree, ast_indents
        )
        
        return module_analyser.main()
