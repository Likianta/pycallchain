from lk_utils.read_and_write_basic import write_json

from src.ast_analyser import AstAnalyser
from src.module_analyser import ModuleHelper, ModuleIndexing


def main():
    ifile = '../../temp/in.py'
    ofile = 'module_linos_dump.json'
    
    ast_ana = AstAnalyser(ifile)
    ast_tree = ast_ana.main()
    ast_indents = ast_ana.get_lino_indent_dict()
    
    # mod_hlp: module helper
    mod_hlp = ModuleHelper('../../')
    mod_hlp.bind_file(ifile)
    
    # mod_idx: module index
    mod_idx = ModuleIndexing(mod_hlp, ast_tree, ast_indents)
    
    out = mod_idx.indexing_module_linos()
    
    write_json(out, ofile)


if __name__ == '__main__':
    main()
