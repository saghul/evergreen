
import sys

__all__ = ['clear_sys_exc_info']


if sys.version_info[0] < 3:
    from sys import exc_clear as clear_sys_exc_info
else:
    def clear_sys_exc_info():
        """No-op In py3k.
        Exception information is not visible outside of except statements.
        sys.exc_clear became obsolete and removed."""

