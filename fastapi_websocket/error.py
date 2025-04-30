from abc import abstractmethod


class BaseRequestError(Exception):
    @abstractmethod
    def json(self) -> dict:
        # For some reason python does not allow abstract exception, so, at least - raise this exception
        raise NotImplementedError(f".json() method is not implemented in {self!r}")


class RequestError(BaseRequestError):
    def __init__(self, reason: str, code: str):
        self.reason = reason
        self.code = code

    def json(self) -> dict:
        return {
            "reason": self.reason,
            "code": self.code,
        }
