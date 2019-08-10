import ast
from lk_utils import read_and_write_basic


code_snip = """
def main():
    pass
"""

# text = read_and_write_basic.read_file('../testflight/app.py')
root = ast.parse(code_snip)
out = ast.dump(root)
read_and_write_basic.write_file(out, '../temp/out.txt')
