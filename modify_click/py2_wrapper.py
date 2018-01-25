
from __future__ import with_statement
from __future__ import absolute_import
from io import open
__version__ = u'0.1.0'

import argparse
import os
import logging
import logging.config
import sys
import tempfile
from subprocess import PIPE, Popen

# on control server, cannot connect outward, so we need to install the packages
# from source/binary ourself
try:
    from typing import Any, BinaryIO, Dict, List, Tuple, Union  # pylint: disable=unused-import
except ImportError:
    GCMD = u'pip install --user packages/typing-3.6.2-py2-none-any.whl'
    GREMOTE_PROC = Popen(GCMD, stderr=PIPE, stdout=PIPE, shell=True)
    GSTDOUT, GSTDERR = GREMOTE_PROC.communicate()
    if GSTDERR:
        print u'Unable to install typing package locally, see error below:\n'
        print GSTDERR
        exit(3)
    from typing import Any, Dict, List, Tuple
try:
    from termcolor import colored
except ImportError:
    GCWD = os.getcwdu()
    os.chdir(GCWD + u'/packages/')
    GCMD = u'tar -xzf termcolor-1.1.0.tar.gz && '\
        u'cd termcolor-1.1.0 && '\
        u'python setup.py build && '\
        u'python setup.py install --user'
    GREMOTE_PROC = Popen(GCMD, stderr=PIPE, stdout=PIPE, shell=True)
    GSTDOUT, GSTDERR = GREMOTE_PROC.communicate()
    os.chdir(GCWD)
    if GSTDERR:
        print u'Unable to install typing package locally, see error below:\n'
        print GSTDERR
        exit(3)
    from termcolor import colored  # type: ignore

logging.config.fileConfig(fname=u'logging.config', disable_existing_loggers=False)
LOG = logging.getLogger(__name__)

# these logs only exist when experiment swapped in, where magi running and mounted
MAGI_LOG_LOCATION = u'/var/log/magi/logs/daemon.log'

def print_condition(colored_output, failed = False):
    if failed:
        sys.stderr.write(colored(u'%s\n' % colored_output, u'red'))
    else:
        sys.stdout.write(colored(u'%s\n' % colored_output, u'green'))

def print_notice():
    # ignore for conversion to py2
    # flake8: noqa=E502
    print u'Notice: this script is going to access magi logs.  This may take a while.\n ' \
        u'Make sure your experiment is swapped in, magi is running on the click node.\n ' \
        u'If you need assistances, please email lincoln@isi.edu.\n'


def fill_template(file_name, click_config):
    LOG.debug(u"%s %s", file_name, unicode(click_config))
    template_contents = []
    revised_contents = []
    change_me_tag = u"_REPLACE"
    msg_str = u"MSG"
    key_str = u"KEY"
    val_str = u"VALUE"
    # special case, rather than use node interally, we will use element, as it is a
    # click element, but with external code, such as the aal file, it is refered to as
    # a node.  So here we manually translate.
    node_str = u"NODE"
    ele_str = u"element"
    # read template
    with open(file_name, u'r') as file_read:
        for line in file_read:
            template_contents.append(line)
    # replace the keyword lines with the contents from the dictionary
    for line in template_contents:
        updated_line = line
        # just to shortcut branch prediction
        if change_me_tag in line:
            if msg_str in line:
                updated_line = line.replace(msg_str + change_me_tag, click_config[msg_str.lower()])
            elif node_str in line:
                updated_line = line.replace(node_str + change_me_tag, click_config[ele_str])
            elif key_str in line:
                updated_line = line.replace(key_str + change_me_tag, click_config[key_str.lower()])
            elif val_str in line:
                updated_line = line.replace(val_str + change_me_tag, click_config[val_str.lower()])
        revised_contents.append(updated_line)
    # write back our updated template file
    with open(file_name, u'w') as file_write:
        for line in revised_contents:
            file_write.write(line)
    LOG.debug(u'write finished - template updated')


def create_template_aal(click_config, residual = True):
    LOG.debug(u'creating template')
    file_ptr = u'generated_click_template.aal'
    base_template = u'click_template.aal'
    temp_file = None  # type = BinaryIO
    if residual:
        # create our temporary aal file
        temp_name = tempfile.gettempdir() + u'/' + file_ptr
        temp_file = open(temp_name, u'wb')
    else:
        # add the absolute path to name as it will run remotely from home dir
        # os.getcwd unfortunately resolves symbolic links which differ from users to control
        # environment variable pwd does not resolve the sym links
        prefix_path = os.environ[u'PWD']
        if os.path.isfile(prefix_path + u'/' + base_template):
            temp_file = open(prefix_path + u'/' + file_ptr, u'wb')
        else:
            raise IOError(u'File does not exist: {path}'.format(path=base_template))

    with open(base_template, u'rb') as template:
        for line in template:
            temp_file.write(line)
    temp_file.close()
    fill_template(temp_file.name, click_config)
    return temp_file.name


# because this runs on users, but magi runs on control, we need to copy our generated aal
# file from the localhost to the control host, perferably in the same the location.
def scp_file_to_control(aal_file, exp, proj, control):
    # pylint: disable=bad-continuation
    remote_proc = Popen(u'scp {aal} {control}.{exp}.{proj}.isi.deterlab.net:{aal}'
                        .format(
                            aal=aal_file,
                            control=control,
                            exp=exp,
                            proj=proj
                        ),
                        stderr=PIPE, stdout=PIPE, shell=True
                        )
    stdout, stderr = remote_proc.communicate()
    LOG.debug(stdout)
    LOG.debug(stderr)
    if stderr:
        return False
    return True


# ssh into the vrouter server, find the logs, and do best to parse the
# logs for the current run. want_fail here is based on the command send with run_magi
# if it wanted an error (as with print_ functions) or expected success (updating click)
def check_magi_logs(keyword, experiment_id, project_id,
                    server, want_fail = False):
    # more efficient mechanisms... make an assumption about what magi is spewing to logs
    # using tail -n X, here we make no assumption, just hope magi logs are not HUGE and being rolled
    remote_cmd = u'ssh {vrouter}.{exp}.{proj}.isi.deterlab.net ' \
        u'cat {magi_logs}'.format(
            exp=experiment_id,
            proj=project_id,
            magi_logs=MAGI_LOG_LOCATION,
            vrouter=server,
        )
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    # only way to check if we 'succeeded' or 'failed'
    check_failure = stdout.split(u'\n')[-2]
    # if we wanted to 'fail' we should see runtime exception, other wise we
    # we would like to see 'write response' although these are particular to what is calling them
    if u'Sending back a RunTimeException event.' in check_failure and want_fail:
        pass
    elif u'write response: 200: OK' in check_failure and not want_fail:
        # 4 is magic number to include the line above with socket write.
        return (True, u'\n'.join(stdout.split(u'\n')[-4:]))
    else:
        return (False, stderr)
    # in case of error, lets spew additional lines to help programmer/debugger find issue
    last_twenty_lines = []
    count = 0
    # start at the end of the logs, and go to the beginning - searching
    for line in stdout.decode(u'utf-8').strip().split(u'\n')[::-1]:
        if keyword.upper() in line:
            # this correlates to magi_modules/clickControl with how it writes to logs, which
            # in our case is through a list, so lets parse that list, given we've found our keyword
            pretty = line[line.index(u'['):]
            pretty_list = sorted([unicode(x.replace(u"'", u'')).strip() for x in pretty[1:-1].split(u',')])
            return (True, u'\n'.join(pretty_list) + u'\n')
        if count < 20:
            last_twenty_lines.append(line)
        count += 1
    return (False, u'\n'.join(last_twenty_lines[::-1]))


# run magi script passing in the templated aal file for click to parse
# it should return a tuple (bool, str) where bool is wether run succeeded
# the str being the logs assosciated with the run.
def run_magi(aal_file, experiment_id, project_id,
             server = u'control'):
    remote_cmd = u'ssh {control}.{exp}.{proj}.isi.deterlab.net ' \
        u'sudo magi_orchestrator.py -c localhost -f {aal}'.format(
            exp=experiment_id,
            proj=project_id,
            aal=aal_file,
            control=server,
        )
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    LOG.debug(stdout)
    LOG.debug(stderr)
    # this return code is meaningless, but hey, maybe ssh fails - good to know
    if remote_proc.returncode == 0:
        return (True, stdout)
    return (False, stderr)


# help the user find which projects and or experiments they have access to
def print_linux_groups(project_id = None):
    if not project_id:
        remote_cmd = u'for i in `groups`; do find /groups/ -maxdepth 1 -group $i; done'
    else:
        remote_cmd = u'find /proj/{project}/exp/ -maxdepth 1 -group {project}'\
                .format(project=project_id)
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if not stderr:
        if not project_id:
            print u'\n'.join([x.split(u'/')[-1] for x in stdout.split(u'\n') if x])
        else:
            print u'\n'.join(sorted([x.split(u'/')[-1] for x in stdout.split(u'\n') if x]))
    else:
        print_condition(u'Unable to find any valid projects -- ', failed=True)
        LOG.error(stderr)


# print_click_internals is a hack approach, so instead of importing click control and getting
# at the data ourselves, what we are going to do, is create a tmp aal with bogus inputs
# give it to magi to run, and look at the error logs on vrouter, which will tell us what we did
# wrong (hopefully - via validateClickInputs)
def print_click_internals(click_element, experiment_id, project_id,
                          control_server, click_server):
    bogus_dict = {
        u'msg': u'print_click_internals',
        u'key': u'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        u'value': u'recycling',
    }
    # if we have an element we want to know the valid keys, otherwise we want valid elements
    if not click_element:
        bogus_dict[u'element'] = u'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa'
    else:
        bogus_dict[u'element'] = click_element
    # create a template file with our bogus_dict values
    aal = create_template_aal(bogus_dict)
    print_notice()
    # now copy our bogus template over to the control server
    scp_worked = scp_file_to_control(
        aal, experiment_id, project_id, control_server)
    if not scp_worked:
        print_condition(u'unable to scp generated aal file to control server.', failed=True)
        exit(4)
    # run magi using our bogus dict, hopefully we will get output that can be parsed
    success, out = run_magi(aal, experiment_id, project_id, server=control_server)
    if not success:
        print_condition(
            u'unable to run magi on control server --  Error:\n {}'.format(out),
            failed=True
        )
        exit(4)
    # need to check the output and verify it all worked.  We want it to fail, so we can parse error
    # logs for the correct output
    keyword = u'element' if not click_element else u'key'
    worked, element_logs = check_magi_logs(keyword, experiment_id, project_id,
                                           click_server, want_fail=True)
    if worked:
        print element_logs
    else:
        LOG.error(u'error retrieving logs from vrouter')
        LOG.error(element_logs)

def get_click_element(experiment_id, project_id, control, click):
    cursor = colored(u'(element) > ', u'green')
    ask_click = u'Click Element:\n'
    click_element = raw_input(colored(u'{click}{cursor}'.format(cursor=cursor, click=ask_click), u'red'))
    while click_element == ur'\h':
        print_click_internals(None, experiment_id, project_id, control, click)
        click_element = raw_input(u'{click}{cursor}'.format(cursor=cursor, click=ask_click))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = raw_input(u'set click_element to {element}? ([y]/n) '.format(element=click_element))
    accept = True if not accept_str or accept_str[0].lower() == u'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_click_element(experiment_id, project_id, control, click)
    LOG.debug(u'element set to "%s"', click_element)
    return click_element


def get_key_for_element(element, experiment_id, project_id,
                        control, click):
    cursor = colored(u'(key) > ', u'green')
    ask_key = u'Element Key (to change):\n'
    element_key = raw_input(colored(u'{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key), u'red'))
    while element_key == ur'\h':
        print_click_internals(element, experiment_id, project_id, control, click)
        element_key = raw_input(u'{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = raw_input(u'set key to {key}? ([y]/n) '.format(key=element_key))
    accept = True if not accept_str or accept_str[0].lower() == u'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_key_for_element(element, experiment_id, project_id, control, click)
    LOG.debug(u'key set to "%s"', element_key)
    return element_key


def get_value_for_key(element_key):
    cursor = colored(u'(value) > ', u'green')
    ask_value = u'set "{key}" to what value:\n'.format(key=element_key)
    key_value = raw_input(colored(u'{kv}{cursor}'.format(cursor=cursor, kv=ask_value), u'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = raw_input(u'set "{key}" to {value}? ([y]/n) '.format(key=element_key, value=key_value))
    accept = True if not accept_str or accept_str[0].lower() == u'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_value_for_key(element_key)
    LOG.debug(u'key set to "%s"', key_value)
    return key_value


def get_experiment_id(project_id):
    cursor = colored(u'(experiment id) > ', u'green')
    ask_value = u'Experiment Identifier?\n'
    exp_value = raw_input(colored(u'{exp_id}{cursor}'.format(cursor=cursor, exp_id=ask_value), u'red'))
    while exp_value == ur'\h':
        print_linux_groups(project_id)
        exp_value = raw_input(colored(u'{exp_id}{cursor}'
                                  .format(cursor=cursor, exp_id=ask_value), u'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = raw_input(u'Experiment ID = {value}? ([y]/n) '.format(value=exp_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept_str or accept_str[0].lower() == u'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_experiment_id(project_id)
    LOG.debug(u'experiment set to "%s"', exp_value)
    return exp_value


def get_project_id():
    cursor = colored(u'(project) > ', u'green')
    ask_value = u'Project Name?\n'
    proj_value = raw_input(colored(u'{proj_id}{cursor}'.format(cursor=cursor, proj_id=ask_value), u'red'))
    while proj_value == ur'\h':
        print_linux_groups()
        proj_value = raw_input(colored(u'{proj_id}{cursor}'
                                   .format(cursor=cursor, proj_id=ask_value), u'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = raw_input(u'Project Name is {value}? ([y]/n) '.format(value=proj_value))
    accept = True if not accept_str or accept_str[0].lower() == u'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_project_id()
    LOG.debug(u'project set to "%s"', proj_value)
    return proj_value


def get_server(server_type):
    default = u'vrouter' if server_type == u'click' else u'control'
    cursor = colored(u'({stype}_server) [default={dtype}] > '
                     .format(stype=server_type, dtype=default), u'green')
    ask_type = u'{stype} server hostname? \n'.format(stype=server_type)
    response = raw_input(colored(u'{stype}{cursor}'.format(cursor=cursor, stype=ask_type), u'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    response = response if response else default
    accept_str = raw_input(u'{stype} server hostname is {value}? ([y]/n) '
                       .format(value=response, stype=server_type))
    accept = True if not accept_str or accept_str[0].lower() == u'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_server(server_type)
    LOG.debug(u'%s server hostname set to "%s"', server_type, response)
    return response


def get_inputs_from_user(options = None):
    inputs = {}
    try:
        if not options:  # about 99% sure this will throw, but yolo
            options.project = None
            options.experiment = None
            options.click_server = None
            options.control_server = None
        if options.project:
            project = options.project
        else:
            project = get_project_id()
        if options.experiment:
            experiment = options.experiment
        else:
            experiment = get_experiment_id(project)

        if options.click_server:
            click = options.click_server
        else:
            click = get_server(u'click')
        if options.control_server:
            control = options.control_server
        else:
            control = get_server(u'control')
        click_element = get_click_element(experiment, project, control, click)
        element_key = get_key_for_element(click_element, experiment, project, control, click)
        key_value = get_value_for_key(element_key)
        inputs[u'control_server'] = control
        inputs[u'click_server'] = click
        inputs[u'project'] = project
        inputs[u'experiment'] = experiment
        inputs[u'msg'] = u'user_inputs'
        inputs[u'element'] = click_element
        inputs[u'key'] = element_key
        inputs[u'value'] = key_value
        LOG.info(unicode(inputs))
        return inputs
    except KeyboardInterrupt:
        print_condition(u'\nexiting program - not saving results', failed=True)
        sys.exit(2)
    return inputs


def verified_host():
    rdict = {
        u'run': False,
        } # type: Dict[str, Any]
    remote_cmd = u'hostname'
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if stderr:
        return rdict
    if stdout:
        try:
            stdout = stdout.decode(u'utf-8').strip()
            hostname = stdout.split(u'.')
            if u'.'.join(hostname[-3:]) == u'isi.deterlab.net':
                rdict[u'run'] = True
                # huge assumption! that hostname now maps to Z.exp.proj.X.Y.W
                if len(hostname) == 6:
                    rdict[u'host'] = hostname[0]
                    rdict[u'experiment'] = hostname[1]
                    rdict[u'project'] = hostname[2]
                LOG.debug(u'host info: %s', unicode(rdict))
                return rdict
            else:
                LOG.error(u'invalid hostname: %s - %s', stdout, hostname)
        except IndexError:
            print_condition(
                u'unable to parse hostname, is the hostname set? Is it an ISI node?', failed=True
            )
            LOG.error(u'invalid hostname: %s', stdout)
    return rdict


# pylint: disable=fixme
# TODO: add checking, or make options better
def set_cmdline_opts(click_info, project = None, experiment = None):
    input_dict = {
        u'click_server': None,
        u'control_server': None,
        u'project': project,
        u'experiment': experiment,
        u'msg': click_info[0],
        u'element': click_info[1],
        u'key': click_info[2],
        u'value': click_info[3],
    }
    LOG.debug(unicode(input_dict))
    return input_dict


def parse_input_file(path):
    comment = u'#'
    input_dict = {
        u'click_server': None,
        u'control_server': None,
        u'project': None,
        u'experiment': None,
        u'msg': None,
        u'element': None,
        u'key': None,
        u'value': None,
    }  # type: Dict[str, Any]
    with open(path, u'r') as pfile:
        for line in pfile:
            # try our best to parse, if it didnt have what we were looking for, skip
            # dont try to hard to make sure it all works, simple parser
            try:
                key_value = line.split(u':')
                key = key_value[0].strip()
                value = key_value[1].strip()
                if comment in value:
                    value = value.split(comment)[0].strip()
                if key in input_dict:
                    LOG.debug(u'"%s" set to "%s"', key, value)
                    input_dict[key] = value
            # naughty to allow bare-except, but I dont want parser to break for any reason
            # pylint: disable=bare-except
            except:  # noqa: E722
                pass
    for key in input_dict:
        if not input_dict[key]:
            print_condition(u"Error parsing file: {} was not defined.".format(key), failed=True)
    return input_dict


# parse the user options specified
def parse_options():
    parser = argparse.ArgumentParser(
        description=u'Dynamically modify the click modular router.',
        add_help=True,
        epilog=u'If you need assistance, or find any bugs, please report them to lincoln@isi.edu',
    )
    parse_mode = parser.add_mutually_exclusive_group(required=True)
    parse_mode.add_argument(u'-i', u'--interactive', dest=u'interactive', action=u'store_true',
                            default=False,
                            help=u'use interactive mode to modify click modular router')

    parse_mode.add_argument(u'-f', u'--file', dest=u'file_input', action=u'store',
                            default=None,
                            help=u'parse a file rather than command line or interactive')

    parse_mode.add_argument(u'-c', u'--cmdline', dest=u'cmdline', action=u'store', nargs=4,
                            default=False, metavar=(u'MSG', u'ELEMENT', u'KEY', u'VALUE'),
                            help=u'provide msg, element, key, and value through cmd options')

    parser.add_argument(u'-e', u'--experiment', dest=u'experiment', action=u'store',
                        default=False, metavar=(u'EXPERIMENT'),
                        help=u'give deterlab experiment identifier')

    parser.add_argument(u'-p', u'--project', dest=u'project', action=u'store',
                        default=False, metavar=(u'PROJECT'),
                        help=u'give deterlab project identifier')

    parser.add_argument(u'-y', u'--yes', dest=u'ignore', action=u'store_true',
                        default=False,
                        help=u'dont prompt user for anything, cannot be used with -i')

    parser.add_argument(u'--control', dest=u'control_server', action=u'store',
                        default=False, metavar=(u'CONTROL HOSTNAME'),
                        help=u'specify the control node used in the experiment'\
                        u'[default is set to "control"]'
                       )

    parser.add_argument(u'--click', dest=u'click_server', action=u'store',
                        default=False, metavar=(u'CLICK HOSTNAME'),
                        help=u'specify the node with click installed on it'\
                        u'[default is set to "vrouter"]'
                       )

    parser.add_argument(u'-v', u'--verbose', dest=u'verbose', action=u'store_true',
                        default=False,
                        help=u'print out debug logs')

    parser.add_argument(u'--version', action=u'version',
                        version=u'%(prog)s {ver}'.format(ver=__version__))
    args = parser.parse_args()
    if args.ignore and args.interactive:
        parser.print_help()
        print_condition(u'ERROR: cannot use -i and -y in conjunction\n', failed=True)
        sys.exit(2)
    return args


# pylint: disable=too-many-branches, too-many-statements
def main():
    options = parse_options()
    # dont allow hosts not on deterlab to attempt to run this script
    hostname_check = verified_host()
    if hostname_check[u'run']:
        # set the logger based on verbosity
        if options.verbose:
            LOG.setLevel(logging.DEBUG)
        else:
            LOG.setLevel(logging.WARN)

        # This is all option handling, making sure user inputs are set correctly
        LOG.debug(unicode(options))
        config = {}  # type: Dict[str, str]
        if options.interactive:
            print_condition(u'Use \\h for available values - there is a delay with using help')
            config = get_inputs_from_user(options)
        elif options.file_input:
            config = parse_input_file(options.file_input)
        elif options.cmdline:
            config = set_cmdline_opts(options.cmdline)
        LOG.debug(u'config file after inputs: %s', config)
        if options.experiment:
            config[u'experiment'] = options.experiment
            LOG.debug(u'experiment set to: %s', config[u'experiment'])
        else:
            LOG.info(u'attempting to use experiment from hostname!')
            if hostname_check.get(u'experiment', None):
                config[u'experiment'] = hostname_check[u'experiment']

        if options.project:
            config[u'project'] = options.project
            LOG.debug(u'project set to: %s', config[u'project'])
        else:
            LOG.info(u'attempting to use project from hostname!')
            if hostname_check.get(u'project', None):
                config[u'project'] = hostname_check[u'project']

        if options.control_server:
            config[u'control_server'] = options.control_server
            LOG.debug(u'control_server set to: %s', config[u'control_server'])
        else:
            LOG.info(u'using "control" as default for control server')
            config[u'control_server'] = u'control'

        if options.click_server:
            config[u'click_server'] = options.click_server
            LOG.debug(u'click_server set to: %s', config[u'click_server'])
        else:
            LOG.info(u'using "vrouter" as default for click server')
            config[u'click_server'] = u'vrouter'


        LOG.debug(u'config with cmd line options: %s', config)

        # Main execution - we've gotten all the inputs from user, so now lets make changes to click
        aal_file = create_template_aal(config, residual=True)
        # if this script is run from the control_server, no need to scp it over
        # also may seem a bit awkward setting control server above, but it might work in odd case
        if hostname_check[u'host'] != config[u'control_server']:
            scp_worked = scp_file_to_control(
                aal_file, config[u'experiment'], config[u'project'], config[u'control_server']
            )
            if not scp_worked:
                print_condition(u'unable to scp generated aal file to control server.', failed=True)
                exit(4)
        # attempt to run our real aal on control server with magi
        success, out = run_magi(
            aal_file, config[u'experiment'], config[u'project'], config[u'control_server']
        )
        # check if it worked or not
        if not success:
            print_condition(u'some failure occured!\n {}'.format(out), failed=True)
        else:
            worked, click_logs = check_magi_logs(u'200. OK', config[u'experiment'],
                                                 config[u'project'], config[u'click_server'])
            if not worked:
                print_condition(u'unable to confirm click update was written!', failed=True)
            else:
                print_condition(u'confirmed changes send to click:\n {}'.format(click_logs[:-3]))
    # not being run on deterlab, so lets not handle this case (because ssh auth is a pain)
    else:
        print_condition(
            u'unable to run, must be on run on an isi.deterlab.net host'
            u'if this host is on deterlab, make sure the FQDN is the hostname',
            failed=True
        )


if __name__ == u'__main__':
    main()
