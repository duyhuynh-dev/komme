class TasteProviderError(Exception):
    code = "provider_error"
    retryable = False

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UsernameNotFoundError(TasteProviderError):
    code = "username_not_found"


class PrivateOrUnavailableProfileError(TasteProviderError):
    code = "profile_unavailable"


class RateLimitedError(TasteProviderError):
    code = "rate_limited"
    retryable = True


class BlockedByRedditError(TasteProviderError):
    code = "blocked_by_reddit"


class NoPublicActivityError(TasteProviderError):
    code = "no_public_activity"


class InsufficientSignalError(TasteProviderError):
    code = "insufficient_signal"


class ProviderUnavailableError(TasteProviderError):
    code = "provider_unavailable"
    retryable = True

