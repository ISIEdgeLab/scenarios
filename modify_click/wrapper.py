
__version__ = '0.1.0'

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
    GCMD = 'pip install --user packages/typing-3.6.2-py2-none-any.whl'
    GREMOTE_PROC = Popen(GCMD, stderr=PIPE, stdout=PIPE, shell=True)
    GSTDOUT, GSTDERR = GREMOTE_PROC.communicate()
    if GSTDERR:
        print('Unable to install typing package locally, see error below:\n')
        print(GSTDERR)
        exit(3)
    from typing import Any, Dict, List, Tuple
try:
    from termcolor import colored
except ImportError:
    GCWD = os.getcwd()
    os.chdir(GCWD + '/packages/')
    GCMD = 'tar -xzf termcolor-1.1.0.tar.gz && '\
        'cd termcolor-1.1.0 && '\
        'python setup.py build && '\
        'python setup.py install --user'
    GREMOTE_PROC = Popen(GCMD, stderr=PIPE, stdout=PIPE, shell=True)
    GSTDOUT, GSTDERR = GREMOTE_PROC.communicate()
    os.chdir(GCWD)
    if GSTDERR:
        print('Unable to install typing package locally, see error below:\n')
        print(GSTDERR)
        exit(3)
    from termcolor import colored  # type: ignore

logging.config.fileConfig(fname='logging.config', disable_existing_loggers=False)
LOG = logging.getLogger(__name__)

# these logs only exist when experiment swapped in, where magi running and mounted
MAGI_LOG_LOCATION = '/var/log/magi/logs/daemon.log'

def print_condition(colored_output: str, failed: bool = False) -> None:
    if failed:
        sys.stderr.write(colored('%s\n' % colored_output, 'red'))
    else:
        sys.stdout.write(colored('%s\n' % colored_output, 'green'))

def print_notice() -> None:
    # ignore for conversion to py2
    # flake8: noqa=E502
    print(
        'Notice: this script is going to access magi logs.  This may take a while.\n ' \
        'Make sure your experiment is swapped in, magi is running on the click node.\n ' \
        'If you need assistances, please email lincoln@isi.edu.\n'
    )


def fill_template(file_name: str, click_config: Dict) -> None:
    LOG.debug("%s %s", file_name, str(click_config))
    template_contents = []
    revised_contents = []
    change_me_tag = "_REPLACE"
    msg_str = "MSG"
    key_str = "KEY"
    val_str = "VALUE"
    # special case, rather than use node interally, we will use element, as it is a
    # click element, but with external code, such as the aal file, it is refered to as
    # a node.  So here we manually translate.
    node_str = "NODE"
    ele_str = "element"
    # read template
    with open(file_name, 'r') as file_read:
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
    with open(file_name, 'w') as file_write:
        for line in revised_contents:
            file_write.write(line)
    LOG.debug('write finished - template updated')


def create_template_aal(click_config: Dict, residual: bool = True) -> str:
    LOG.debug('creating template')
    file_ptr = 'generated_click_template.aal'
    base_template = 'click_template.aal'
    temp_file = None  # type = BinaryIO
    if residual:
        # create our temporary aal file
        temp_name = tempfile.gettempdir() + '/' + file_ptr
        temp_file = open(temp_name, 'wb')
    else:
        # add the absolute path to name as it will run remotely from home dir
        # os.getcwd unfortunately resolves symbolic links which differ from users to control
        # environment variable pwd does not resolve the sym links
        prefix_path = os.environ['PWD']
        if os.path.isfile(prefix_path + '/' + base_template):
            temp_file = open(prefix_path + '/' + file_ptr, u'wb')
        else:
            raise IOError('File does not exist: {path}'.format(path=base_template))

    with open(base_template, 'rb') as template:
        for line in template:
            temp_file.write(line)
    temp_file.close()
    fill_template(temp_file.name, click_config)
    return temp_file.name


# because this runs on users, but magi runs on control, we need to copy our generated aal
# file from the localhost to the control host, perferably in the same the location.
def scp_file_to_control(aal_file: str, exp: str, proj: str, control: str) -> bool:
    # pylint: disable=bad-continuation
    remote_proc = Popen('scp {aal} {control}.{exp}.{proj}.isi.deterlab.net:{aal}'
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
def check_magi_logs(keyword: str, experiment_id: str, project_id: str,
                    server: str, want_fail: bool = False) -> Tuple[bool, str]:
    # more efficient mechanisms... make an assumption about what magi is spewing to logs
    # using tail -n X, here we make no assumption, just hope magi logs are not HUGE and being rolled
    remote_cmd = 'ssh {vrouter}.{exp}.{proj}.isi.deterlab.net ' \
        'cat {magi_logs}'.format(
            exp=experiment_id,
            proj=project_id,
            magi_logs=MAGI_LOG_LOCATION,
            vrouter=server,
        )
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    # only way to check if we 'succeeded' or 'failed'
    check_failure = stdout.split('\n')[-2]
    # if we wanted to 'fail' we should see runtime exception, other wise we
    # we would like to see 'write response' although these are particular to what is calling them
    if 'Sending back a RunTimeException event.' in check_failure and want_fail:
        pass
    elif 'write response: 200: OK' in check_failure and not want_fail:
        # 4 is magic number to include the line above with socket write.
        return (True, u'\n'.join(stdout.split(u'\n')[-4:]))
    else:
        return (False, stderr)
    # in case of error, lets spew additional lines to help programmer/debugger find issue
    last_twenty_lines = []
    count = 0
    # start at the end of the logs, and go to the beginning - searching
    for line in stdout.decode('utf-8').strip().split('\n')[::-1]:
        if keyword.upper() in line:
            # this correlates to magi_modules/clickControl with how it writes to logs, which
            # in our case is through a list, so lets parse that list, given we've found our keyword
            pretty = line[line.index('['):]
            pretty_list = sorted([str(x.replace("'", '')).strip() for x in pretty[1:-1].split(',')])
            return (True, '\n'.join(pretty_list) + '\n')
        if count < 20:
            last_twenty_lines.append(line)
        count += 1
    return (False, '\n'.join(last_twenty_lines[::-1]))


# run magi script passing in the templated aal file for click to parse
# it should return a tuple (bool, str) where bool is wether run succeeded
# the str being the logs assosciated with the run.
def run_magi(aal_file: str, experiment_id: str, project_id: str,
             server: str = 'control') -> Tuple[bool, str]:
    remote_cmd = 'ssh {control}.{exp}.{proj}.isi.deterlab.net ' \
        'sudo magi_orchestrator.py -c localhost -f {aal}'.format(
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
def print_linux_groups(project_id: str = None) -> None:
    if not project_id:
        remote_cmd = 'for i in `groups`; do find /groups/ -maxdepth 1 -group $i; done'
    else:
        remote_cmd = 'find /proj/{project}/exp/ -maxdepth 1 -group {project}'\
                .format(project=project_id)
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if not stderr:
        if not project_id:
            print('\n'.join([x.split('/')[-1] for x in stdout.split('\n') if x]))
        else:
            print('\n'.join(sorted([x.split('/')[-1] for x in stdout.split('\n') if x])))
    else:
        print_condition('Unable to find any valid projects -- ', failed=True)
        LOG.error(stderr)


# print_click_internals is a hack approach, so instead of importing click control and getting
# at the data ourselves, what we are going to do, is create a tmp aal with bogus inputs
# give it to magi to run, and look at the error logs on vrouter, which will tell us what we did
# wrong (hopefully - via validateClickInputs)
def print_click_internals(click_element: Union[None, str], experiment_id: str, project_id: str,
                          control_server: str, click_server: str) -> None:
    bogus_dict = {
        'msg': 'print_click_internals',
        'key': 'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        'value': 'recycling',
    }
    # if we have an element we want to know the valid keys, otherwise we want valid elements
    if not click_element:
        bogus_dict['element'] = 'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa'
    else:
        bogus_dict['element'] = click_element
    # create a template file with our bogus_dict values
    aal = create_template_aal(bogus_dict)
    print_notice()
    # now copy our bogus template over to the control server
    scp_worked = scp_file_to_control(
        aal, experiment_id, project_id, control_server)
    if not scp_worked:
        print_condition('unable to scp generated aal file to control server.', failed=True)
        exit(4)
    # run magi using our bogus dict, hopefully we will get output that can be parsed
    success, out = run_magi(aal, experiment_id, project_id, server=control_server)
    if not success:
        print_condition(
            'unable to run magi on control server --  Error:\n {}'.format(out),
            failed=True
        )
        exit(4)
    # need to check the output and verify it all worked.  We want it to fail, so we can parse error
    # logs for the correct output
    keyword = 'element' if not click_element else 'key'
    worked, element_logs = check_magi_logs(keyword, experiment_id, project_id,
                                           click_server, want_fail=True)
    if worked:
        print(element_logs)
    else:
        LOG.error('error retrieving logs from vrouter')
        LOG.error(element_logs)

def get_click_element(experiment_id: str, project_id: str, control: str, click: str) -> str:
    cursor = colored('(element) > ', 'green')
    ask_click = 'Click Element:\n'
    click_element = input(colored('{click}{cursor}'.format(cursor=cursor, click=ask_click), 'red'))
    while click_element == r'\h':
        print_click_internals(None, experiment_id, project_id, control, click)
        click_element = input('{click}{cursor}'.format(cursor=cursor, click=ask_click))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = input('set click_element to {element}? ([y]/n) '.format(element=click_element))
    accept = True if not accept_str or accept_str[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_click_element(experiment_id, project_id, control, click)
    LOG.debug('element set to "%s"', click_element)
    return click_element


def get_key_for_element(element: str, experiment_id: str, project_id: str,
                        control: str, click: str) -> str:
    cursor = colored('(key) > ', 'green')
    ask_key = 'Element Key (to change):\n'
    element_key = input(colored('{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key), 'red'))
    while element_key == r'\h':
        print_click_internals(element, experiment_id, project_id, control, click)
        element_key = input('{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = input('set key to {key}? ([y]/n) '.format(key=element_key))
    accept = True if not accept_str or accept_str[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_key_for_element(element, experiment_id, project_id, control, click)
    LOG.debug('key set to "%s"', element_key)
    return element_key


def get_value_for_key(element_key: str) -> str:
    cursor = colored('(value) > ', 'green')
    ask_value = 'set "{key}" to what value:\n'.format(key=element_key)
    key_value = input(colored('{kv}{cursor}'.format(cursor=cursor, kv=ask_value), 'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = input('set "{key}" to {value}? ([y]/n) '.format(key=element_key, value=key_value))
    accept = True if not accept_str or accept_str[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_value_for_key(element_key)
    LOG.debug('key set to "%s"', key_value)
    return key_value


def get_experiment_id(project_id: str) -> str:
    cursor = colored('(experiment id) > ', 'green')
    ask_value = 'Experiment Identifier?\n'
    exp_value = input(colored('{exp_id}{cursor}'.format(cursor=cursor, exp_id=ask_value), 'red'))
    while exp_value == r'\h':
        print_linux_groups(project_id)
        exp_value = input(colored('{exp_id}{cursor}'
                                  .format(cursor=cursor, exp_id=ask_value), 'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = input('Experiment ID = {value}? ([y]/n) '.format(value=exp_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept_str or accept_str[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_experiment_id(project_id)
    LOG.debug('experiment set to "%s"', exp_value)
    return exp_value


def get_project_id() -> str:
    cursor = colored('(project) > ', 'green')
    ask_value = 'Project Name?\n'
    proj_value = input(colored('{proj_id}{cursor}'.format(cursor=cursor, proj_id=ask_value), 'red'))
    while proj_value == r'\h':
        print_linux_groups()
        proj_value = input(colored('{proj_id}{cursor}'
                                   .format(cursor=cursor, proj_id=ask_value), 'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept_str = input('Project Name is {value}? ([y]/n) '.format(value=proj_value))
    accept = True if not accept_str or accept_str[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_project_id()
    LOG.debug('project set to "%s"', proj_value)
    return proj_value


def get_server(server_type: str) -> str:
    default = 'vrouter' if server_type == 'click' else 'control'
    cursor = colored('({stype}_server) [default={dtype}] > '
                     .format(stype=server_type, dtype=default), 'green')
    ask_type = '{stype} server hostname? \n'.format(stype=server_type)
    response = input(colored('{stype}{cursor}'.format(cursor=cursor, stype=ask_type), 'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    response = response if response else default
    accept_str = input('{stype} server hostname is {value}? ([y]/n) '
                       .format(value=response, stype=server_type))
    accept = True if not accept_str or accept_str[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_server(server_type)
    LOG.debug('%s server hostname set to "%s"', server_type, response)
    return response


def get_inputs_from_user(options: argparse.Namespace = None) -> Dict:
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
            click = get_server('click')
        if options.control_server:
            control = options.control_server
        else:
            control = get_server('control')
        click_element = get_click_element(experiment, project, control, click)
        element_key = get_key_for_element(click_element, experiment, project, control, click)
        key_value = get_value_for_key(element_key)
        inputs['control_server'] = control
        inputs['click_server'] = click
        inputs['project'] = project
        inputs['experiment'] = experiment
        inputs['msg'] = 'user_inputs'
        inputs['element'] = click_element
        inputs['key'] = element_key
        inputs['value'] = key_value
        LOG.info(str(inputs))
        return inputs
    except KeyboardInterrupt:
        print_condition('\nexiting program - not saving results', failed=True)
        sys.exit(2)
    return inputs


def verified_host() -> Dict[str, Any]:
    rdict = {
        'run': False,
        } # type: Dict[str, Any]
    remote_cmd = 'hostname'
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if stderr:
        return rdict
    if stdout:
        try:
            stdout = stdout.decode('utf-8').strip()
            hostname = stdout.split('.')
            if '.'.join(hostname[-3:]) == 'isi.deterlab.net':
                rdict['run'] = True
                # huge assumption! that hostname now maps to Z.exp.proj.X.Y.W
                if len(hostname) == 6:
                    rdict['host'] = hostname[0]
                    rdict['experiment'] = hostname[1]
                    rdict['project'] = hostname[2]
                LOG.debug('host info: %s', str(rdict))
                return rdict
            else:
                LOG.error('invalid hostname: %s - %s', stdout, hostname)
        except IndexError:
            print_condition(
                'unable to parse hostname, is the hostname set? Is it an ISI node?', failed=True
            )
            LOG.error('invalid hostname: %s', stdout)
    return rdict


# pylint: disable=fixme
# TODO: add checking, or make options better
def set_cmdline_opts(click_info: List[str], project: str = None, experiment: str = None) -> Dict:
    input_dict = {
        'click_server': None,
        'control_server': None,
        'project': project,
        'experiment': experiment,
        'msg': click_info[0],
        'element': click_info[1],
        'key': click_info[2],
        'value': click_info[3],
    }
    LOG.debug(str(input_dict))
    return input_dict


def parse_input_file(path: str) -> Dict:
    comment = '#'
    input_dict = {
        'click_server': None,
        'control_server': None,
        'project': None,
        'experiment': None,
        'msg': None,
        'element': None,
        'key': None,
        'value': None,
    }  # type: Dict[str, Any]
    with open(path, 'r') as pfile:
        for line in pfile:
            # try our best to parse, if it didnt have what we were looking for, skip
            # dont try to hard to make sure it all works, simple parser
            try:
                key_value = line.split(':')
                key = key_value[0].strip()
                value = key_value[1].strip()
                if comment in value:
                    value = value.split(comment)[0].strip()
                if key in input_dict:
                    LOG.debug('"%s" set to "%s"', key, value)
                    input_dict[key] = value
            # naughty to allow bare-except, but I dont want parser to break for any reason
            # pylint: disable=bare-except
            except:  # noqa: E722
                pass
    for key in input_dict:
        if not input_dict[key]:
            print_condition("Error parsing file: {} was not defined.".format(key), failed=True)
    return input_dict


# parse the user options specified
def parse_options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Dynamically modify the click modular router.',
        add_help=True,
        epilog='If you need assistance, or find any bugs, please report them to lincoln@isi.edu',
    )
    parse_mode = parser.add_mutually_exclusive_group(required=True)
    parse_mode.add_argument('-i', '--interactive', dest='interactive', action='store_true',
                            default=False,
                            help='use interactive mode to modify click modular router')

    parse_mode.add_argument('-f', '--file', dest='file_input', action='store',
                            default=None,
                            help='parse a file rather than command line or interactive')

    parse_mode.add_argument('-c', '--cmdline', dest='cmdline', action='store', nargs=4,
                            default=False, metavar=('MSG', 'ELEMENT', 'KEY', 'VALUE'),
                            help='provide msg, element, key, and value through cmd options')

    parser.add_argument('-e', '--experiment', dest='experiment', action='store',
                        default=False, metavar=('EXPERIMENT'),
                        help='give deterlab experiment identifier')

    parser.add_argument('-p', '--project', dest='project', action='store',
                        default=False, metavar=('PROJECT'),
                        help='give deterlab project identifier')

    parser.add_argument('-y', '--yes', dest='ignore', action='store_true',
                        default=False,
                        help='dont prompt user for anything, cannot be used with -i')

    parser.add_argument('--control', dest='control_server', action='store',
                        default=False, metavar=('CONTROL HOSTNAME'),
                        help='specify the control node used in the experiment'\
                        '[default is set to "control"]'
                       )

    parser.add_argument('--click', dest='click_server', action='store',
                        default=False, metavar=('CLICK HOSTNAME'),
                        help='specify the node with click installed on it'\
                        '[default is set to "vrouter"]'
                       )

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        default=False,
                        help='print out debug logs')

    parser.add_argument('--version', action='version',
                        version='%(prog)s {ver}'.format(ver=__version__))
    args = parser.parse_args()
    if args.ignore and args.interactive:
        parser.print_help()
        print_condition('ERROR: cannot use -i and -y in conjunction\n', failed=True)
        sys.exit(2)
    return args


# pylint: disable=too-many-branches, too-many-statements
def main() -> None:
    options = parse_options()
    # dont allow hosts not on deterlab to attempt to run this script
    hostname_check = verified_host()
    if hostname_check['run']:
        # set the logger based on verbosity
        if options.verbose:
            LOG.setLevel(logging.DEBUG)
        else:
            LOG.setLevel(logging.WARN)

        # This is all option handling, making sure user inputs are set correctly
        LOG.debug(str(options))
        config = {}  # type: Dict[str, str]
        if options.interactive:
            print_condition('Use \\h for available values - there is a delay with using help')
            config = get_inputs_from_user(options)
        elif options.file_input:
            config = parse_input_file(options.file_input)
        elif options.cmdline:
            config = set_cmdline_opts(options.cmdline)
        LOG.debug('config file after inputs: %s', config)
        if options.experiment:
            config['experiment'] = options.experiment
            LOG.debug('experiment set to: %s', config['experiment'])
        else:
            LOG.info('attempting to use experiment from hostname!')
            if hostname_check.get('experiment', None):
                config['experiment'] = hostname_check['experiment']

        if options.project:
            config['project'] = options.project
            LOG.debug('project set to: %s', config['project'])
        else:
            LOG.info('attempting to use project from hostname!')
            if hostname_check.get('project', None):
                config['project'] = hostname_check['project']

        if options.control_server:
            config['control_server'] = options.control_server
            LOG.debug('control_server set to: %s', config['control_server'])
        else:
            LOG.info('using "control" as default for control server')
            config['control_server'] = 'control'

        if options.click_server:
            config['click_server'] = options.click_server
            LOG.debug('click_server set to: %s', config['click_server'])
        else:
            LOG.info('using "vrouter" as default for click server')
            config['click_server'] = 'vrouter'


        LOG.debug('config with cmd line options: %s', config)

        # Main execution - we've gotten all the inputs from user, so now lets make changes to click
        aal_file = create_template_aal(config, residual=True)
        # if this script is run from the control_server, no need to scp it over
        # also may seem a bit awkward setting control server above, but it might work in odd case
        if hostname_check.get('host', None) != config['control_server']:
            scp_worked = scp_file_to_control(
                aal_file, config['experiment'], config['project'], config['control_server']
            )
            if not scp_worked:
                print_condition('unable to scp generated aal file to control server.', failed=True)
                exit(4)
        # attempt to run our real aal on control server with magi
        success, out = run_magi(
            aal_file, config['experiment'], config['project'], config['control_server']
        )
        # check if it worked or not
        if not success:
            print_condition('some failure occured!\n {}'.format(out), failed=True)
        else:
            worked, click_logs = check_magi_logs('200. OK', config['experiment'],
                                                 config['project'], config['click_server'])
            if not worked:
                print_condition('unable to confirm click update was written!', failed=True)
            else:
                print_condition('confirmed changes send to click:\n {}'.format(click_logs[:-3]))
    # not being run on deterlab, so lets not handle this case (because ssh auth is a pain)
    else:
        print_condition(
            'unable to run, must be on run on an isi.deterlab.net host'
            'if this host is on deterlab, make sure the FQDN is the hostname',
            failed=True
        )


if __name__ == '__main__':
    main()
