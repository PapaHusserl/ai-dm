class LlmError(Exception):
    pass


class LlmTransient(LlmError):
    def __init__(self, message, retry_after=None, timeout=False):
        super().__init__(message)
        self.retry_after = retry_after
        # «медленная» ошибка: ответ не пришёл за таймаут или сервер отдал 504
        self.timeout = timeout


class LlmFatal(LlmError):
    def __init__(self, message, status=None):
        super().__init__(message)
        # код ответа провайдера, если он был: по нему отличаем отказ по ключу
        self.status = status


class RetriesExhausted(LlmTransient):
    def __init__(self, attempts, last):
        timeout = getattr(last, "timeout", False)
        if timeout:
            text = f"ответ не пришёл вовремя (таймаут или 504; вызовов: {attempts}): {last}"
        else:
            text = f"повторы исчерпаны (вызовов: {attempts}): {last}"
        super().__init__(text, timeout=timeout)
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


# имена ошибок «ответ не пришёл за таймаут»
TIMEOUT_NAMES = {
    "ReadTimeout", "WriteTimeout", "ConnectTimeout", "PoolTimeout", "TimeoutException",
    "APITimeoutError", "TimeoutError",
}


def is_timeout_error(error):
    return any(cls.__name__ in TIMEOUT_NAMES for cls in type(error).__mro__)


def is_auth_error(error):
    # 401/403; Gemini на неверный ключ отвечает 400 с текстом «API key not valid»
    status = getattr(error, "status", None)
    if status in (401, 403):
        return True
    return status == 400 and "API key not valid" in str(error)


def retry_after_of(error):
    response = getattr(error, "response", None)
    if response is None:
        return None
    millis = response.headers.get("retry-after-ms")
    try:
        return float(millis) / 1000
    except (TypeError, ValueError):
        pass
    try:
        return float(response.headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


# Для этапа 6 (репорт об ошибке): исходное исключение лежит в __cause__ (raise ... from error),
# а в тексте LlmError ключ уже вычищен redact. Трейсбек (и __cause__) в репорт не выводить:
# в них остаётся исходный текст ошибки провайдера, возможно с ключом.
