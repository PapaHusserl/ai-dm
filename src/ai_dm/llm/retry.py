from ai_dm.llm.errors import LlmFatal, LlmTransient, RetriesExhausted


def give_up(policy, attempt, error):
    return attempt > len(policy.delays) or (error.timeout and not policy.retry_timeouts)


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
            if give_up(policy, attempt, error):
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
