#!/usr/bin/env python
# pylint: disable=import-error
import sys

PY_VERSION = int(sys.version_info[0])
if PY_VERSION == 2:
    import py2_wrapper
    py2_wrapper.main()
elif PY_VERSION == 3:
    import wrapper
    wrapper.main()
