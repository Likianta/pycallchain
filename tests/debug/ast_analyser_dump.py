from lk_utils.read_and_write_basic import write_json

from src.ast_analyser import AstAnalyser


def main():
    """
    将 AstHelper 解析结果 (ast_tree) 输出到 ast_analyser_dump.json 文件.
    
    IN: temp/in.py
    OT: tests/debug/ast_analyser_dump.json
    """
    ifile = '../../temp/in.py'
    ofile = 'ast_analyser_dump.json'
    analyser = AstAnalyser(ifile)
    ast_tree = analyser.main()
    ast_indents = analyser.get_lino_indent_dict()
    
    out = ast_tree
    for lino, ast_data in ast_tree.items():
        indent = ast_indents[lino]
        out[lino].insert(0, indent)
    
    write_json(out, ofile)


if __name__ == '__main__':
    main()
