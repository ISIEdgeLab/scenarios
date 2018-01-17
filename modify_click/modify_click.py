import sys

py_version = int(sys.version_info[0])
print(py_version)
if py_version == 2:
    import py2_wrapper
    py2_wrapper.main()
elif py_version == 3:
    import wrapper
    wrapper.main()
