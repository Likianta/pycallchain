import ast
from lk_utils import read_and_write_basic
from lk_utils.lk_logger import lk

a = read_and_write_basic.read_file('../temp/in.py')
root = ast.parse(a)

for index, node in enumerate(ast.iter_child_nodes(root)):
    for node2 in ast.iter_child_nodes(node):
        if hasattr(node2, 'col_offset'):
            lk.loga(index, node2.lineno, node2.col_offset)
