import os
import logging
import logging.config
import sys
import tempfile
from typing import Dict
from termcolor import colored

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
    node_str = "NODE"
    key_str = "KEY"
    val_str = "VALUE"
    # read template
    with open(file_name, 'r') as file_read:
        for line in file_read:
            template_contents.append(line)
    import pdb
    pdb.set_trace()
    # replace the keyword lines with the contents from the dictionary
    for line in template_contents:
        updated_line = line
        # just to shortcut branch prediction
        if change_me_tag in line:
            if msg_str in line:
                updated_line = line.replace(msg_str+change_me_tag, click_config[msg_str.lower()])
            elif node_str in line:
                updated_line = line.replace(node_str+change_me_tag, click_config[node_str.lower()])
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
def check_magi_logs(keyword: str) -> str:
    return keyword

# run magi script passing in the templated aal file for click to parse
# it should return a tuple (bool, str) where bool is wether run succeeded
# the str being the logs assosciated with the run.
def run_magi(aal_file: str) -> None:
    _ = aal_file

# print_nodes is a hack approach, so instead of importing click control and getting
# at the data ourselves, what we are going to do, is create a tmp aal with bogus inputs
# give it to magi to run, and look at the logs returned by magi to find the variables
# we care about.
# a bit of logic needs to go into this to infer which of the previous incorrect instructions
# correlates to which run
def print_nodes() -> None:
    bogus_dict = {
        'msg': 'print_nodes',
        'node': 'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        'key': 'garbage',
        'value': 'recycling',
    }
    # TODO: this is just for testing
    aal = create_template_aal(bogus_dict, residual=False)
    print_notice()
    run_magi(aal)
    node_logs = check_magi_logs('node')
    # some function here to format logs from error output to human readable
    print(node_logs)

# see comments for print_nodes on issues with implement
def print_keys(click_element: str) -> None:
    bogus_dict = {
        'msg': 'print_keys',
        'node': click_element,
        'key': 'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        'value': 'recycling',
    }
    aal = create_template_aal(bogus_dict)
    print_notice()
    run_magi(aal)
    key_logs = check_magi_logs('key')
    # some function here to format logs from error output to human readable
    print(key_logs)


def get_click_element() -> str:
    cursor = colored('(element) > ', 'green')
    ask_click = 'Click Element:\n'
    click_element = input(colored('{click}{cursor}'.format(cursor=cursor, click=ask_click), 'red'))
    while click_element == r'\h':
        print_nodes()
        click_element = input('{click}{cursor}'.format(cursor=cursor, click=ask_click))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('set click_element to {element}? ([y]/n) '.format(element=click_element))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_click_element()
    return click_element

def get_key_for_element(element: str) -> str:
    cursor = colored('(key) > ', 'green')
    ask_key = 'Element Key (to change):\n'
    element_key = input(colored('{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key), 'red'))
    while element_key == r'\h':
        print_keys(element)
        element_key = input('{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('set key to {key}? ([y]/n) '.format(key=element_key))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_key_for_element(element)
    return element_key

def get_value_for_key(element_key: str) -> str:
    cursor = colored('(value) > ', 'green')
    ask_value = 'set "{key}" to what value:\n'.format(key=element_key)
    key_value = input(colored('{kv}{cursor}'.format(cursor=cursor, kv=ask_value), 'red'))
    while key_value == r'\h':
        key_value = input('{kv}{cursor}'.format(cursor=cursor, kv=ask_value))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = input('set "{key}" to {value}? ([y]/n) '.format(key=element_key, value=key_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == 'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_key_for_element(element_key)
    return key_value

def get_inputs_from_user() -> Dict:
    inputs = {}
    try:
        click_element = get_click_element()
        element_key = get_key_for_element(click_element)
        key_value = get_value_for_key(element_key)
        # TODO: add last step verification here.
        inputs['msg'] = 'user_inputs'
        inputs['node'] = click_element
        inputs['key'] = element_key
        inputs['value'] = key_value
        LOG.info(inputs)
        return inputs
    except KeyboardInterrupt:
        print('exiting program - not saving results')
        sys.exit(2)
    return inputs

# TODO: need to implement this
def parse_input_file(path: str) -> Dict:
    _ = path


if __name__ == '__main__':
    _ = get_inputs_from_user()
