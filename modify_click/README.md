## Modifying Click

### Description

Modify the click modular router without fussing with magi and magi agents.
Make the experience easier and have a better user experience.

### Details

The main module is `modify_click.py`.  It is a wrapper around the aptly named
`wrapper.py` and `py2_wrapper.py`.  modify_click.py only checks which version
of python is calling it.  It will call `py2_wrapper.py` if being called by
python version 2.x or wrapper.py for python 3.x.  It is an executable, so
you may call it directly: `./modify_click.py`

The code should be run on an `isi.deterlab.net` host, specifically one that
mounts the users filesystem, and has access to the control host for an
experiment.  It has been test on `users.isi.deterlab.net` and on the control
node for experiments `control.experiment.project.isi.deterlab.net`.

You must give `modify_click.py` and input type to specify how you would like
to communicate your click changes. The `-i` option will go through an
interactive prompt with the user.

```
Use \h for available values - there is a delay with using help
Project Name?
(project) > \h    
edgect
test
Project Name?
(project) > edgect
Project Name is edgect? ([y]/n) y
Experiment Identifier?
(experiment id) >
```

The `-f` option instead takes in a file for input.  This allows users to
script together their changes in a single file, or in a set of files to
automatically modify click during the duration of a test.  The file
[file_input_example.txt](./modify_click/file_input_example.txt)
gives examples and explanations of sample usages.

The last option is `-c` for command line.  If instead of generating a file
you would like to use the command line, you can specify options with `-c`.
In conjunction with `-p`, `-e`, `--control`, `--click` to specify the
project, experiment, control server hostname, and click server hostname.

More details:

Based on the inputs given by the user, the code configures a dictionary with
['msg', 'element', 'key', 'value'] keys.  These keys are required by the
clickAgent magi module (edgect/magi_modules).  Modifications were made to
clickControl.py to verify if the correct click modules were entered. Replies
are sent to /var/log/magi/daemon.log.  These logs are checked when a user
uses the \h (help) input to parse through what available click elements, or
keys are valid.  This command requires that a bogus aal is generated and run
through click in order to generate an error log message that can be parsed
by the wrapper code.

### Files
```
modify_click.py
 | - wrapper.py
 | - py2_wrapper.py
requirements.txt
click_template.aal
file_input_example.txt
__init__.py
```

Do not modify click_template.aal file.  Okay to modify file_input_example.txt

Feedback/Questions/Bugs: Lincoln Thurlow <lincoln@isi.edu>
