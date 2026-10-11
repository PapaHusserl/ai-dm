class LlmError(Exception):
    pass


class LlmTransient(LlmError):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class LlmFatal(LlmError):
    pass


class RetriesExhausted(LlmTransient):
    def __init__(self, attempts, last):
        super().__init__(f"повторы исчерпаны ({attempts} вызовов): {last}")
        self.attempts = attempts
        self.last = last


class MissingKey(LlmFatal):
    pass


# имена сетевых ошибок (SDK и httpx): без кода статуса их считаем временными
NETWORK_NAMES = {
    "APIConnectionError", "APITimeoutError", "ConnectError", "ConnectTimeout", "ReadTimeout",
    "TimeoutException", "NetworkError", "TransportError", "RemoteProtocolError", "ReadError",
    "WriteError",
}


def is_network_error(error):
    return any(cls.__name__ in NETWORK_NAMES for cls in type(error).__mro__)


# Для этапа 6 (репорт об ошибке): исходное исключение лежит в __cause__ (raise ... from error),
# а в тексте LlmError ключ уже вычищен redact. Трейсбек (и __cause__) в репорт не выводить:
# в них остаётся исходный текст ошибки провайдера, возможно с ключом.
