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
    from typing import Dict, List, Tuple
except ImportError:
    GCMD = 'pip install --user packages/typing-3.6.2-py2-none-any.whl'
    GREMOTE_PROC = Popen(GCMD, stderr=PIPE, stdout=PIPE, shell=True)
    GSTDOUT, GSTDERR = GREMOTE_PROC.communicate()
    if GSTDERR:
        print('Unable to install typing package locally, see error below:\n')
        print(GSTDERR)
        exit(3)
    from typing import Dict, List, Tuple
try:
    from termcolor import colored
except ImportError:
    GCWD = os.getcwd()
    GCMD = 'tar -xzvf termcolor-1.1.0.tar.gz && '\
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
    from termcolor import colored

VERSION = '0.0.1'

LOG_CONFIG = {
    'version': 1,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': True
        },
    }
}

logging.config.dictConfig(LOG_CONFIG)
LOG = logging.getLogger(__name__)

class ParseError(Exception):
    pass

def print_notice() -> None:
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
                updated_line = line.replace(msg_str+change_me_tag, click_config[msg_str.lower()])
            elif node_str in line:
                updated_line = line.replace(node_str+change_me_tag, click_config[ele_str])
            elif key_str in line:
                updated_line = line.replace(key_str+change_me_tag, click_config[key_str.lower()])
            elif val_str in line:
                updated_line = line.replace(val_str+change_me_tag, click_config[val_str.lower()])

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
    temp_file = ''
    if residual:
        # create our temporary aal file
        temp_name = tempfile.gettempdir()+'/'+file_ptr
        temp_file = open(temp_name, 'wb')
    else:
        prefix_path = os.environ['PWD']
        if os.path.isfile(prefix_path+'/'+base_template):
            temp_file = open(prefix_path+'/'+file_ptr, u'wb')
        else:
            raise IOError('File does not exist: {path}'.format(path=base_template))

    with open(base_template, 'rb') as template:
        for line in template:
            temp_file.write(line)
    temp_file.close()
    fill_template(temp_file.name, click_config)
    # add the absolute path to name as it will run remotely from home dir
    # os.getcwd unfortunately resolves symbolic links which differ from users to control
    # environment variable pwd does not resolve the sym links
    return temp_file.name

# because this runs on users, but magi runs on control, we need to copy our generated aal
# file from the localhost to the control host, perferably in the same the location.
def scp_file_to_control(aal_file: str, exp: str, proj: str, control: str) -> bool:
    # pylint: disable=bad-continuation
    remote_proc = Popen('scp {aal} {control}.{exp}.{proj}.isi.deterlab.net:{aal}'\
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
# logs for the current run
# yolo - will run magi on smaller nodes tomorrow to verifying logging works
def check_magi_logs(keyword: str, experiment_id: str, project_id: str, server: str) -> str:
    # these logs only exist when experiment swapped in, where magi running and mounted
    magi_log_location = '/var/log/magi/logs/daemon.log'
    # more efficient mechanisms... make an assumption about what magi is spewing to logs
    # using tail -n X, here we make no assumption, just hope magi logs are not HUGE
    remote_cmd = 'ssh {vrouter}.{exp}.{proj}.isi.deterlab.net ' \
        'cat {magi_logs}'.format(
            exp=experiment_id,
            proj=project_id,
            magi_logs=magi_log_location,
            vrouter=server,
        )
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if stderr:
        return stderr

    # question of performance here - best way to search a file, i would like
    # to open file, seek to end and read in reverse since I really want tail of file
    # correct method is long and I dont feel like copying off stack overflow
    # so this will fail or take long when log grows past memory
    last_twenty_lines = []
    count = 0
    # for line in reversed(list(open(magi_log_location, 'rb'))):
    for line in stdout.decode('utf-8').strip().split('\n')[::-1]:
        if keyword.upper() in line:
            # this is a hack - better methods, but should be quick
            # now lets parse the line for user friendliness
            pretty = line[line.index('['):]
            pretty_list = sorted([str(x.replace("'", '')).strip() for x in pretty[1:-1].split(',')])
            return '\n'.join(pretty_list)+'\n'
        if count < 20:
            last_twenty_lines.append(line)
        count += 1
    raise ParseError(
        'unable to find "{kw}" in magi logs.  Dump of last 20 lines of logs: {logs}\n\n'.format(
            kw=keyword,
            logs='\n'.join(last_twenty_lines[::-1]),
        )
    )

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
    if not stderr:
        return (True, stdout)
    return (False, stderr)

# help the user find which projects are available to them
def print_projects() -> None:
    remote_cmd = 'for i in `groups`; do find /groups/ -maxdepth 1 -group $i; done'
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if not stderr:
        print('\n'.join([x.split('/')[-1] for x in stdout.split('\n') if x]))
    else:
        print('Unable to find any valid projects -- ')
        LOG.error(stderr)

# help the user find which experiments are apart of the selected project
def print_experiments(project_id: str) -> None:
    # if this should be defined by -user (only ones the user created, or all group projects
    remote_cmd = 'find /proj/{project}/exp/ -maxdepth 1 -group {project}'.format(project=project_id)
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if not stderr:
        print('\n'.join(sorted([x.split('/')[-1] for x in stdout.split('\n') if x])))
    else:
        print('Unable to find any valid experiments -- ')
        LOG.error(stderr)

# print_elements is a hack approach, so instead of importing click control and getting
# at the data ourselves, what we are going to do, is create a tmp aal with bogus inputs
# give it to magi to run, and look at the logs returned by magi to find the variables
# we care about.
# a bit of logic needs to go into this to infer which of the previous incorrect instructions
# correlates to which run
def print_elements(experiment_id: str, project_id: str,
                   control_server: str, click_server: str) -> None:
    bogus_dict = {
        'msg': 'print_elements',
        'element': 'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        'key': 'garbage',
        'value': 'recycling',
    }
    aal = create_template_aal(bogus_dict)
    print_notice()
    run_magi(aal, experiment_id, project_id, server=control_server)
    element_logs = check_magi_logs('element', experiment_id, project_id, click_server)
    # some function here to format logs from error output to human readable
    print(element_logs)

# see comments for print_elements on issues with implement
def print_keys(click_element: str, experiment_id: str, project_id: str,
               control_server: str, click_server: str) -> None:
    bogus_dict = {
        'msg': 'print_keys',
        'element': click_element,
        'key': 'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        'value': 'recycling',
    }
    aal = create_template_aal(bogus_dict)
    print_notice()
    run_magi(aal, experiment_id, project_id, server=control_server)
    key_logs = check_magi_logs('key', experiment_id, project_id, click_server)
    # some function here to format logs from error output to human readable
    print(key_logs)


def get_click_element(experiment_id: str, project_id: str, control: str, click: str) -> str:
    cursor = colored('(element) > ', 'green')
    ask_click = 'Click Element:\n'
    click_element = input(colored('{click}{cursor}'.format(cursor=cursor, click=ask_click), 'red'))
    while click_element == r'\h':
        print_elements(experiment_id, project_id, control, click)
        click_element = input('{click}{cursor}'.format(cursor=cursor, click=ask_click))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('set click_element to {element}? ([y]/n) '.format(element=click_element))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
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
        print_keys(element, experiment_id, project_id, control, click)
        element_key = input('{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('set key to {key}? ([y]/n) '.format(key=element_key))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
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
    accept = input('set "{key}" to {value}? ([y]/n) '.format(key=element_key, value=key_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
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
        print_experiments(project_id)
        exp_value = input(colored('{exp_id}{cursor}'\
            .format(cursor=cursor, exp_id=ask_value), 'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('Experiment ID = {value}? ([y]/n) '.format(value=exp_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
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
        print_projects()
        proj_value = input(colored('{proj_id}{cursor}'\
            .format(cursor=cursor, proj_id=ask_value), 'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('Project Name is {value}? ([y]/n) '.format(value=proj_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_project_id()
    LOG.debug('project set to "%s"', proj_value)
    return proj_value

def get_server(server_type: str) -> str:
    default = 'vrouter' if server_type == 'click' else 'control'
    cursor = colored('({stype}_server) [default={dtype}] > '\
        .format(stype=server_type, dtype=default), 'green')
    ask_type = '{stype} server hostname? \n'.format(stype=server_type)
    response = input(colored('{stype}{cursor}'.format(cursor=cursor, stype=ask_type), 'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    response = response if response else default
    accept = input('{stype} server hostname is {value}? ([y]/n) '\
        .format(value=response, stype=server_type))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_server(server_type)
    LOG.debug('%s server hostname set to "%s"', server_type, response)
    return response

def get_inputs_from_user(options: argparse = None) -> Dict:
    inputs = {}
    try:
        if not options: # about 99% sure this will throw, but yolo
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
        LOG.info(inputs)
        return inputs
    except KeyboardInterrupt:
        print('\nexiting program - not saving results')
        sys.exit(2)
    return inputs

def verified_host() -> Tuple[bool, str]:
    remote_cmd = 'hostname'
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if stderr:
        return (False, '')
    if stdout:
        try:
            stdout = stdout.decode('utf-8').strip()
            hostname = stdout.split('.')
            if '.'.join(hostname[-3:]) == 'isi.deterlab.net':
                return (True, hostname[0])
            else:
                LOG.error('invalid hostname: %s - %s', stdout, hostname)
        except IndexError:
            print('unable to parse hostname, is the hostname set? Is it an ISI node?')
            LOG.error('invalid hostname: %s', stdout)
    return (False, '')

# TODO: add checking, or make options better
def set_cmdline_opts(click_info: List[str], project: str = None, experiment: str = None):
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
    LOG.debug(input_dict)
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
    }
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
            except:
                pass
    for key in input_dict:
        if not input_dict[key]:
            print("Error parsing file: {} was not defined.".format(key))
    return input_dict

# parse the user options specified
def parse_options() -> Dict:
    parser = argparse.ArgumentParser(
        description='Dynamically modify the click modular router.',
        add_help=True,
        epilog='If you need assistance, or find any bugs, please report them to lincoln@isi.edu',
        # 'examples:\n\t%(prog)s -f file_input_example.txt\n' \
        # '\t%(prog)s -i\n' \
        # '\t%(prog)s -e simple edgect -c "add delay" link_1_2_bw latency 10ms\n\n' \
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
                        help='specify the control node used in the experiment')

    parser.add_argument('--click', dest='click_server', action='store',
                        default=False, metavar=('CLICK HOSTNAME'),
                        help='specify the node with click installed on it')

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        default=False,
                        help='print out debug logs')

    parser.add_argument('--version', action='version', version='%(prog)s %(VERSION)s')
    args = parser.parse_args()
    if args.ignore and args.interactive:
        parser.print_help()
        sys.stderr.write(colored('ERROR: cannot use -i and -y in conjunction\n', 'red'))
        sys.exit(2)
    return args

def main():
    # dont allow hosts not on deterlab to attempt to run this script
    host_on_isi, script_run_from = verified_host()
    if host_on_isi:
        options = parse_options()
        # set the logger based on verbosity
        if options.verbose:
            LOG.setLevel(logging.DEBUG)
        else:
            LOG.setLevel(logging.WARN)
        # check how the user is going to supply info to this program, this is required
        # setup dictionary that contains all pertinant click info
        LOG.debug(options)
        config = {}
        if options.interactive:
            print(colored('Use \\h for available values - there is a delay with using help', 'red'))
            config = get_inputs_from_user(options)
        elif options.file_input:
            config = parse_input_file(options.file_input)
        elif options.cmdline:
            config = set_cmdline_opts(options.cmdline)

        LOG.debug('config file after inputs: %s', config)

        if options.experiment:
            config['experiment'] = options.experiment
            LOG.debug()
        if options.project:
            config['project'] = options.project
        if options.control_server:
            config['control_server'] = options.control_server
        if options.click_server:
            config['click_server'] = options.click_server

        LOG.debug('config with cmd line options: %s', config)

        # main execution: create the aal file, and run_magi with the click settings
        aal_file = create_template_aal(config, residual=True)
        # if this script is run from the control_server, no need to scp it over
        if script_run_from != config['control_server']:
            _ = scp_file_to_control(
                aal_file, config['experiment'], config['project'], config['control_server']
            )
        run_magi(aal_file, config['experiment'], config['project'], config['control_server'])
    else:
        print(colored('unable to run, must be on run on an isi.deterlab.net host', 'red'))
        print(colored('if this host is on deterlab, make sure the FQDN is the hostname', 'red'))


if __name__ == '__main__':
    main()
