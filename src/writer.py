class Writer:
    writer = None
    
    def __init__(self, top_module):
        self.top_module = top_module  # -> 'testflight.app'
        
        self.tile_view = {}  # 平铺视图
        self.cascade_view = {}  # 层叠视图
    
    def record(self, caller: str, call_chain: list):
        self.tile_view.update({caller: call_chain.copy()})
        
        filtered_call_chain = [
            x for x in call_chain
            if self.is_inner_module(x)
        ]
        return filtered_call_chain
    
    def show(self):
        """
        IN: self.tile_view: dict. {module: [call1, call2, ...]}
                e.g. {
                    'testflight.app.module': [
                        'testflight.app.main'
                    ],
                    'testflight.app.main': [
                        'testflight.app.main.child_method',
                        'testflight.app.main.child_method2',
                        'testflight.app.Init',
                        'testflight.app.Init.main',
                        'testflight.downloader.Downloader',
                        'testflight.parser.Parser'
                    ],
                    'testflight.app.main.child_method': [
                    ],
                    'testflight.app.main.child_method2': [
                        'testflight.app.main.child_method'
                    ],
                    'testflight.app.Init': [
                    ],
                    'testflight.app.Init.main': [
                    ]
                }
        OT: self.cascade_view: dict. {runtime_module: {module1: {module11: {...
                }, module12: {...}, ...}}}
                e.g. {
                    'testflight.app.module': {
                        'testflight.app.main': {
                            'testflight.app.main.child_method': {},
                            'testflight.app.main.child_method2': {
                                'testflight.app.main.child_method': {},
                            },
                            'testflight.app.Init': {},
                            'testflight.app.Init.main': {},
                            'testflight.downloader.Downloader': {},
                            'testflight.parser.Parser': {},
                        }
                    }
                }
        """
        chain_stacks = []
        
        
        
    
    def is_inner_module(self, module: str):
        return bool(module.startswith(self.top_module))
