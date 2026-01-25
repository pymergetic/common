from hdrpkg.__header__ import Demo


class DemoImpl(Demo):
    def hello(self) -> str:
        return "hi"


