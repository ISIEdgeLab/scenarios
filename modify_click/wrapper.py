import argparse
import os
import logging
import logging.config
import sys
import tempfile
from subprocess import PIPE, Popen
from typing import Dict, Tuple
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

def grep_magi_logs():
    pass

def print_notice() -> None:
    print(
        'Notice: this script is going to access magi logs.  This may take a while.\n ' \
        'Make sure your experiment is swapped in, magi is running on the vrouter node.\n ' \
        'If you need assistances, please email lincoln@isi.edu.\n'
    )

def fill_template(file_name: str, click_config: Dict) -> None:
    LOG.debug("%s %s", file_name, str(click_config))
    template_contents = []
    revised_contents = []
    change_me_tag = "_REPLACE"
    msg_str = "MSG"
    ele_str = "ELEMENT"
    key_str = "KEY"
    val_str = "VALUE"
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
            elif ele_str in line:
                updated_line = line.replace(ele_str+change_me_tag, click_config[ele_str.lower()])
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
    base_template = './click_template.aal'
    temp_file = ''
    if residual:
        # create our temporary aal file
        temp_name = tempfile.gettempdir()+file_ptr
        temp_file = open(temp_name, 'wb')
    else:
        if os.path.isfile(base_template):
            temp_file = open(file_ptr, 'wb')
        else:
            raise IOError('File does not exist: {path}'.format(path=base_template))

    with open(base_template, 'rb') as template:
        for line in template:
            temp_file.write(line)
    temp_file.close()
    fill_template(temp_file.name, click_config)
    return temp_file.name

# ssh into the control server, find the logs, and do best to parse the
# logs for the current run
# yolo - will run magi on smaller nodes tomorrow to verifying logging works
def check_magi_logs(keyword: str, experiment_id: str, project_id: str) -> str:
    # these logs only exist when experiment swapped in, where magi running and mounted
    magi_log_location = '/var/log/magi/logs/daemon.log'
    # more efficient mechanisms... make an assumption about what magi is spewing to logs
    # using tail -n X, here we make no assumption, just hope magi logs are not HUGE
    remote_cmd = 'ssh control.{exp}.{proj}.isi.deterlab.edu ' \
        'cat {magi_logs}'.format(
            exp=experiment_id,
            proj=project_id,
            magi_logs=magi_log_location,
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
    for line in stdout:
        if keyword.upper() in line:
            # this is a hack - better methods, but should be quick
            return line
        if count < 20:
            last_twenty_lines.append(line)
        count += 1
    raise ParseError(
        'unable to find "{kw}" in magi logs.  Dump of last 20 lines of logs: {logs}'.format(
            kw=keyword,
            logs=last_twenty_lines[::-1],
        )
    )

# run magi script passing in the templated aal file for click to parse
# it should return a tuple (bool, str) where bool is wether run succeeded
# the str being the logs assosciated with the run.
def run_magi(aal_file: str, experiment_id: str, project_id: str) -> Tuple[bool, str]:
    remote_cmd = 'ssh control.{exp}.{proj}.isi.deterlab.edu ' \
        'magi_orchestrator.py -c localhost -f {aal}'.format(
            exp=experiment_id,
            proj=project_id,
            aal=aal_file,
        )
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if not stderr:
        return (True, stdout)
    return (False, stderr)

# print_elements is a hack approach, so instead of importing click control and getting
# at the data ourselves, what we are going to do, is create a tmp aal with bogus inputs
# give it to magi to run, and look at the logs returned by magi to find the variables
# we care about.
# a bit of logic needs to go into this to infer which of the previous incorrect instructions
# correlates to which run
def print_elements(experiment_id: str, project_id: str) -> None:
    bogus_dict = {
        'msg': 'print_elements',
        'element': 'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        'key': 'garbage',
        'value': 'recycling',
    }
    # TODO: (residual=False) this is just for testing
    aal = create_template_aal(bogus_dict, residual=False)
    print_notice()
    run_magi(aal, experiment_id, project_id)
    element_logs = check_magi_logs('element', experiment_id, project_id)
    # some function here to format logs from error output to human readable
    print(element_logs)

# see comments for print_elements on issues with implement
def print_keys(click_element: str, experiment_id: str, project_id: str) -> None:
    bogus_dict = {
        'msg': 'print_keys',
        'element': click_element,
        'key': 'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        'value': 'recycling',
    }
    aal = create_template_aal(bogus_dict)
    print_notice()
    run_magi(aal, experiment_id, project_id)
    key_logs = check_magi_logs('key', experiment_id, project_id)
    # some function here to format logs from error output to human readable
    print(key_logs)


def get_click_element(experiment_id: str, project_id: str) -> str:
    cursor = colored('(element) > ', 'green')
    ask_click = 'Click Element:\n'
    click_element = input(colored('{click}{cursor}'.format(cursor=cursor, click=ask_click), 'red'))
    while click_element == r'\h':
        print_elements(experiment_id, project_id)
        click_element = input('{click}{cursor}'.format(cursor=cursor, click=ask_click))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('set click_element to {element}? ([y]/n) '.format(element=click_element))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_click_element(experiment_id, project_id)
    LOG.debug('element set to "%s"', click_element)
    return click_element

def get_key_for_element(element: str, experiment_id: str, project_id: str) -> str:
    cursor = colored('(key) > ', 'green')
    ask_key = 'Element Key (to change):\n'
    element_key = input(colored('{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key), 'red'))
    while element_key == r'\h':
        print_keys(element, experiment_id, project_id)
        element_key = input('{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('set key to {key}? ([y]/n) '.format(key=element_key))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_key_for_element(element, experiment_id, project_id)
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


def get_experiment_id() -> str:
    cursor = colored('(experiment id) > ', 'green')
    ask_value = 'Experiment Identifier?\n'
    exp_value = input(colored('{exp_id}{cursor}'.format(cursor=cursor, exp_id=ask_value), 'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('Experiment ID = {value}? ([y]/n) '.format(value=exp_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_experiment_id()
    LOG.debug('experiment set to "%s"', exp_value)
    return exp_value

def get_project_id() -> str:
    cursor = colored('(project) > ', 'green')
    ask_value = 'Project Name?\n'
    proj_value = input(colored('{proj_id}{cursor}'.format(cursor=cursor, proj_id=ask_value), 'red'))
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


def get_inputs_from_user() -> Dict:
    inputs = {}
    try:
        project = get_project_id()
        experiment = get_experiment_id()
        click_element = get_click_element(experiment, project)
        element_key = get_key_for_element(click_element, experiment, project)
        key_value = get_value_for_key(element_key)
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

# TODO: need to implement this
def parse_input_file(path: str) -> Dict:
    comment = '#'
    input_dict = {
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
        allow_abbrev=True,
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
                            default=[False], metavar=('MSG', 'ELEMENT', 'KEY', 'VALUE'),
                            help='provide msg, element, key, and value through cmd options')

    # unlike deter, we will parse -e pid, eid means nargs = '+', and check if valid later
    # can use with -i and -c, and shortcut the process
    parser.add_argument('-e', '--expinfo', dest='expinfo', action='store', nargs=2,
                        default=[False], metavar=('PROJECT', 'EXPERIMENT'),
                        help='give deterlab project and experiment info, cannot be used with -f')

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        default=False,
                        help='print out debug logs')

    parser.add_argument('--version', action='version', version='%(prog)s %(VERSION)s')

    args = parser.parse_args()
    return args

def main():
    options = parse_options()
    if options.interactive:
        _ = get_inputs_from_user()
    elif options.file_input:
        _ = parse_input_file('file_input_example.txt')


if __name__ == '__main__':
    main()
