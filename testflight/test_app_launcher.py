import os

from testflight import downloader
from testflight.parser import Parser


# noinspection PyUnusedLocal
def main():
    """
    this is a testflight program.
    """
    print(os.path.abspath(__file__))
    
    def child_method():
        print('this is a child method of test2()')
    
    def child_method2():
        print('this is another child method of test2()')
        child_method()
    
    child_method()
    child_method2()
    
    init = Init()
    init.main()
    
    dl = downloader.Downloader()
    ps = Parser()


class Init:
    
    @staticmethod
    def main():
        print('initializing ok')


if __name__ == '__main__':
    main()
