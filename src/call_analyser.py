class CallStream:
    """
    data format:
        stream: [CallPack, ...]
    """
    
    def __init__(self):
        self.stream = []

    def update(self, packet):
        self.stream.append(packet)


class CallPack:
    """
    data format:
        packet: {filepath: [module, ...], ...}
    """
    
    def __init__(self):
        self.packet = {}
        
    def update(self, filepath, *modules):
        node = self.packet.setdefault(filepath, [])
        node.extend(modules)
