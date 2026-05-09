import logging

TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def _trace(self: logging.Logger, msg: object, *args: object, **kwargs: object) -> None:
    if self.isEnabledFor(TRACE):
        self._log(TRACE, msg, args, **kwargs)


logging.Logger.trace = _trace  # type: ignore[attr-defined]
