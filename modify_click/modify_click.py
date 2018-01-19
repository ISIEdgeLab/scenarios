#!/usr/bin/env python
# pylint: disable=import-error
import sys

PY_VERSION = int(sys.version_info[0])
if PY_VERSION == 2:
    from py2_wrapper import main
    main()
elif PY_VERSION == 3:
    from wrapper import main
    main()
