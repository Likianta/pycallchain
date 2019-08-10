from lk_utils.lk_logger import lk


class Writer:
    
    def __init__(self):
        self.stacks = []
        
        self.tile_view = {}  # 平铺视图
        self.cascade_view = {}  # 层叠视图
    
    def record(self, caller: str, call_chain: list):
        self.tile_view.update({caller: call_chain})
    
    def show(self, runtime_module):
        """
        IN: self.tile_view: dict. {module: [call1, call2, ...]}
                e.g. res/sample/pycallchain_tile_view.json
        OT: self.cascade_view: dict. {runtime_module: {module1: {module11: {...
                }, module12: {...}, ...}}}
                e.g. res/sample/pycallchain_cascade_view.json
        """
        node = self.cascade_view.setdefault(runtime_module, {})
        calls = self.tile_view.get(runtime_module)
        self.recurse(node, calls)
        
        lk.logt('[D3619]', self.stacks)
        lk.logt('[I3316]', self.cascade_view)
        
        # TEST output
        from lk_utils.read_and_write_basic import write_json
        write_json(self.cascade_view, '../temp/out.json')
        write_json(self.tile_view, '../temp/out2.json')
    
    def recurse(self, node: dict, calls):
        """
        
        demo:
            self.tile_views = {
                'src.app.module': ['src.prechecker.main', 'src.app.main'],
                'src.prechecker.main': [],
                'src.app.main': ['src.app.main.child_method']
            }
            self.cascade_view = {
                'src.app.module': {}  # <- current node param is pointed to `{}`
            }
            calls = ['src.prechecker.main', 'src.app.main']
        """
        if not calls:
            return
        for module in calls:
            if module in self.stacks:
                """
                关于可能出现 "回调地狱" 的情况:
                    假如 self.cascade_view 存在以下情况:
                        {A: {B: {A: {B: {A: {B: {A: ...}}}}}}}
                    说明出现了无限回调.
                    为了避免这种情况, 我们利用 `if module in self.stacks` 及时发现无限
                    回调的兆头, 立即停止并标记为不安全的:
                        {A: {B: {A: STOP_AND_MARK_UNSAFE}
                    这里就是做这件事的.
                对于 "回调地狱" 的情况, 将被标记为 '[◆CALLBACK_HELL◆]'.
                """
                node.update({module: '[◆CALLBACK_HELL◆]'})
                continue
            else:
                self.stacks.append(module)
                # -> module = 'src.prechecker.main'
            
            new_node = node.setdefault(module, {})
            new_calls = self.tile_view.get(module)
            # module = 'src.prechecker.main' -> new_calls = []
            self.recurse(new_node, new_calls)
            
            self.stacks.pop()
        """TODO
        demo:
            node = {}, calls = ['src.prechecker.main', 'src.app.main']
            -> i1: module = 'src.prechecker.main'
                -> self.stacks updated: ['src.prechecker.main']
                -> node updated: {'src.prechecker.main': new_node}
                    -> new_node = {}
                -> new_calls = []
                -> recurse: node = {}, calls = []
                    -> over
            -> i2: module = 'src.app.main'
                -> self.stacks updated: ['src.prechecker.main', 'src.app.main']
                -> node updated: {'src.app.main': new_node}
                    -> new_node = {}
                -> new_calls = ['src.app.main.child_method']
                -> recurse: node = {}, calls = ['src.app.main.child_method']
                    -> i1: module = 'src.app.main.child_method'
                        ->
        """
