from __future__ import annotations

from abc import ABC, abstractmethod

from pymergetic.common.header import header


@header
class Demo(ABC):
    @abstractmethod
    def hello(self) -> str: ...


