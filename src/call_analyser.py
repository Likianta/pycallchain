class CallFlow:
    """
    data format:
        flow: [CallBag1, CallBag2, ...]
    """
    
    def __init__(self):
        self.flow = []


class CallBag:
    """
    data format:
        bag: {filepath1: [module1, module2, ...], filepath2: [...], ...}
    """
    
    def __init__(self):
        self.bag = {}
        
    def update(self, filepath, *modules):
        pass
