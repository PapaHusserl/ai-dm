from ai_dm.llm.errors import LlmFatal, LlmTransient, RetriesExhausted


def call_with_retries(adapter, req, policy, sleeper, on_attempt=None, on_start=None):
    attempt = 0
    while True:
        attempt += 1
        if on_start is not None:
            on_start(attempt)
        try:
            response = adapter.complete(req)
        except LlmTransient as error:
            if on_attempt is not None:
                on_attempt(attempt, None, error)
            if attempt > len(policy.delays):
                raise RetriesExhausted(attempt, error) from error
            pause = max(policy.delays[attempt - 1], error.retry_after or 0)
            sleeper(min(pause, max(policy.delays)))
            continue
        except LlmFatal as error:
            if on_attempt is not None:
                on_attempt(attempt, None, error)
            raise
        if on_attempt is not None:
            on_attempt(attempt, response, None)
        return response
