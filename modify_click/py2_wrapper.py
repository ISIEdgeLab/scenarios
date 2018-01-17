# 3to2 tool to conver wrapper.py to this
from __future__ import with_statement
from __future__ import absolute_import
import argparse
import os
import logging
import logging.config
import sys
import tempfile
from subprocess import PIPE, Popen
from typing import Dict, List, Tuple
from termcolor import colored
from io import open

VERSION = u'0.0.1'

LOG_CONFIG = {
    u'version': 1,
    u'formatters': {
        u'standard': {
            u'format': u'%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    u'handlers': {
        u'default': {
            u'level': u'DEBUG',
            u'formatter': u'standard',
            u'class': u'logging.StreamHandler',
        },
    },
    u'loggers': {
        u'': {
            u'handlers': [u'default'],
            u'level': u'DEBUG',
            u'propagate': True
        },
    }
}

logging.config.dictConfig(LOG_CONFIG)
LOG = logging.getLogger(__name__)

class ParseError(Exception):
    pass

def grep_magi_logs():
    pass

def print_notice():
    print u'Notice: this script is going to access magi logs.  This may take a while.\n ' \
        u'Make sure your experiment is swapped in, magi is running on the click node.\n ' \
        u'If you need assistances, please email lincoln@isi.edu.\n'

def fill_template(file_name, click_config):
    LOG.debug(u"%s %s", file_name, unicode(click_config))
    template_contents = []
    revised_contents = []
    change_me_tag = u"_REPLACE"
    msg_str = u"MSG"
    ele_str = u"ELEMENT"
    key_str = u"KEY"
    val_str = u"VALUE"
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
                updated_line = line.replace(msg_str+change_me_tag, click_config[msg_str.lower()])
            elif ele_str in line:
                updated_line = line.replace(ele_str+change_me_tag, click_config[ele_str.lower()])
            elif key_str in line:
                updated_line = line.replace(key_str+change_me_tag, click_config[key_str.lower()])
            elif val_str in line:
                updated_line = line.replace(val_str+change_me_tag, click_config[val_str.lower()])

        revised_contents.append(updated_line)

    # write back our updated template file
    with open(file_name, u'w') as file_write:
        for line in revised_contents:
            file_write.write(line)
    LOG.debug(u'write finished - template updated')


def create_template_aal(click_config, residual = True):
    LOG.debug(u'creating template')
    file_ptr = u'generated_click_template.aal'
    base_template = u'./click_template.aal'
    temp_file = u''
    if residual:
        # create our temporary aal file
        temp_name = tempfile.gettempdir()+file_ptr
        temp_file = open(temp_name, u'wb')
    else:
        if os.path.isfile(base_template):
            temp_file = open(file_ptr, u'wb')
        else:
            raise IOError(u'File does not exist: {path}'.format(path=base_template))

    with open(base_template, u'rb') as template:
        for line in template:
            temp_file.write(line)
    temp_file.close()
    fill_template(temp_file.name, click_config)
    return temp_file.name

# ssh into the control server, find the logs, and do best to parse the
# logs for the current run
# yolo - will run magi on smaller nodes tomorrow to verifying logging works
def check_magi_logs(keyword, experiment_id, project_id):
    # these logs only exist when experiment swapped in, where magi running and mounted
    magi_log_location = u'/var/log/magi/logs/daemon.log'
    # more efficient mechanisms... make an assumption about what magi is spewing to logs
    # using tail -n X, here we make no assumption, just hope magi logs are not HUGE
    remote_cmd = u'ssh control.{exp}.{proj}.isi.deterlab.edu ' \
        u'cat {magi_logs}'.format(
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
        u'unable to find "{kw}" in magi logs.  Dump of last 20 lines of logs: {logs}'.format(
            kw=keyword,
            logs=last_twenty_lines[::-1],
        )
    )

# run magi script passing in the templated aal file for click to parse
# it should return a tuple (bool, str) where bool is wether run succeeded
# the str being the logs assosciated with the run.
def run_magi(aal_file, experiment_id, project_id):
    remote_cmd = u'ssh control.{exp}.{proj}.isi.deterlab.edu ' \
        u'magi_orchestrator.py -c localhost -f {aal}'.format(
            exp=experiment_id,
            proj=project_id,
            aal=aal_file,
        )
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if not stderr:
        return (True, stdout)
    return (False, stderr)

# help the user find which projects are available to them
def print_projects():
    remote_cmd = u'for i in `groups`; do find /groups/ -maxdepth 1 -group $i; done'
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    # TODO: need to strip the prefix /groups/
    if not stderr:
        print stdout
    else:
        print u'Unable to find any valid projects -- '
        LOG.error(stderr)

# help the user find which experiments are apart of the selected project
def print_experiments(project_id):
    remote_cmd = u'find /groups/{project} -maxdepth 1'.format(project=project_id)
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    # TODO: need to strip the prefix /groups/{}/
    if not stderr:
        print stdout
    else:
        print u'Unable to find any valid experiments -- '
        LOG.error(stderr)

# print_elements is a hack approach, so instead of importing click control and getting
# at the data ourselves, what we are going to do, is create a tmp aal with bogus inputs
# give it to magi to run, and look at the logs returned by magi to find the variables
# we care about.
# a bit of logic needs to go into this to infer which of the previous incorrect instructions
# correlates to which run
def print_elements(experiment_id, project_id):
    bogus_dict = {
        u'msg': u'print_elements',
        u'element': u'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        u'key': u'garbage',
        u'value': u'recycling',
    }
    # TODO: (residual=False) this is just for testing
    aal = create_template_aal(bogus_dict, residual=False)
    print_notice()
    run_magi(aal, experiment_id, project_id)
    element_logs = check_magi_logs(u'element', experiment_id, project_id)
    # some function here to format logs from error output to human readable
    print element_logs

# see comments for print_elements on issues with implement
def print_keys(click_element, experiment_id, project_id):
    bogus_dict = {
        u'msg': u'print_keys',
        u'element': click_element,
        u'key': u'aaaaaaaaaaaaaaa_1_aaaaaaaaaaaaaaaaa',
        u'value': u'recycling',
    }
    aal = create_template_aal(bogus_dict)
    print_notice()
    run_magi(aal, experiment_id, project_id)
    key_logs = check_magi_logs(u'key', experiment_id, project_id)
    # some function here to format logs from error output to human readable
    print key_logs


def get_click_element(experiment_id, project_id):
    cursor = colored(u'(element) > ', u'green')
    ask_click = u'Click Element:\n'
    click_element = raw_input(colored(u'{click}{cursor}'.format(cursor=cursor, click=ask_click), u'red'))
    while click_element == ur'\h':
        print_elements(experiment_id, project_id)
        click_element = raw_input(u'{click}{cursor}'.format(cursor=cursor, click=ask_click))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = raw_input(u'set click_element to {element}? ([y]/n) '.format(element=click_element))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == u'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_click_element(experiment_id, project_id)
    LOG.debug(u'element set to "%s"', click_element)
    return click_element

def get_key_for_element(element, experiment_id, project_id):
    cursor = colored(u'(key) > ', u'green')
    ask_key = u'Element Key (to change):\n'
    element_key = raw_input(colored(u'{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key), u'red'))
    while element_key == ur'\h':
        print_keys(element, experiment_id, project_id)
        element_key = raw_input(u'{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = raw_input(u'set key to {key}? ([y]/n) '.format(key=element_key))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == u'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_key_for_element(element, experiment_id, project_id)
    LOG.debug(u'key set to "%s"', element_key)
    return element_key

def get_value_for_key(element_key):
    cursor = colored(u'(value) > ', u'green')
    ask_value = u'set "{key}" to what value:\n'.format(key=element_key)
    key_value = raw_input(colored(u'{kv}{cursor}'.format(cursor=cursor, kv=ask_value), u'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = raw_input(u'set "{key}" to {value}? ([y]/n) '.format(key=element_key, value=key_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == u'y' else False
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
        print_experiments(project_id)
        exp_value = raw_input(colored(u'{exp_id}{cursor}'\
            .format(cursor=cursor, exp_id=ask_value), u'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = raw_input(u'Experiment ID = {value}? ([y]/n) '.format(value=exp_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == u'y' else False
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
        print_projects()
        proj_value = raw_input(colored(u'{proj_id}{cursor}'\
            .format(cursor=cursor, proj_id=ask_value), u'red'))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = raw_input(u'Project Name is {value}? ([y]/n) '.format(value=proj_value))
    # shouldnt reuse variable with different types...
    accept = True if not accept or accept[0].lower() == u'y' else False
    sys.stdout.flush()
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_project_id()
    LOG.debug(u'project set to "%s"', proj_value)
    return proj_value

def get_inputs_from_user(expinfo):
    inputs = {}
    try:
        if expinfo:
            print u'project : {}, experiment: {} (cmdline)'.format(expinfo[0], expinfo[1])
            project = expinfo[0]
            experiment = expinfo[1]
        else:
            project = get_project_id()
            experiment = get_experiment_id(project)
        click_element = get_click_element(experiment, project)
        element_key = get_key_for_element(click_element, experiment, project)
        key_value = get_value_for_key(element_key)
        inputs[u'msg'] = u'user_inputs'
        inputs[u'element'] = click_element
        inputs[u'key'] = element_key
        inputs[u'value'] = key_value
        LOG.info(inputs)
        return inputs
    except KeyboardInterrupt:
        print u'\nexiting program - not saving results'
        sys.exit(2)
    return inputs

def verified_host():
    remote_cmd = u'hostname'
    remote_proc = Popen(remote_cmd, stderr=PIPE, stdout=PIPE, shell=True)
    stdout, stderr = remote_proc.communicate()
    if stderr:
        return False
    if stdout:
        try:
            stdout = stdout.decode(u'utf-8').strip()
            hostname = stdout.split(u'.')
            if u'.'.join(hostname[-3:]) == u'isi.deterlab.net':
                return True
            else:
                LOG.error(u'invalid hostname: %s - %s', stdout, hostname)
        except IndexError:
            print u'unable to parse hostname, is the hostname set? Is it an ISI node?'
            LOG.error(u'invalid hostname: %s', stdout)
    return False

def parse_input_file(path):
    comment = u'#'
    input_dict = {
        u'msg': None,
        u'element': None,
        u'key': None,
        u'value': None,
    }
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
            except:
                pass
    for key in input_dict:
        if not input_dict[key]:
            print u"Error parsing file: {} was not defined.".format(key)
    return input_dict

# parse the user options specified
def parse_options():
    parser = argparse.ArgumentParser(
        description=u'Dynamically modify the click modular router.',
        add_help=True,
        epilog=u'If you need assistance, or find any bugs, please report them to lincoln@isi.edu',
        # 'examples:\n\t%(prog)s -f file_input_example.txt\n' \
        # '\t%(prog)s -i\n' \
        # '\t%(prog)s -e simple edgect -c "add delay" link_1_2_bw latency 10ms\n\n' \
    )
    parse_mode = parser.add_mutually_exclusive_group(required=True)
    parse_mode.add_argument(u'-i', u'--interactive', dest=u'interactive', action=u'store_true',
                            default=False,
                            help=u'use interactive mode to modify click modular router')

    parse_mode.add_argument(u'-f', u'--file', dest=u'file_input', action=u'store',
                            default=None,
                            help=u'parse a file rather than command line or interactive')

    parse_mode.add_argument(u'-c', u'--cmdline', dest=u'cmdline', action=u'store', nargs=4,
                            default=[False], metavar=(u'MSG', u'ELEMENT', u'KEY', u'VALUE'),
                            help=u'provide msg, element, key, and value through cmd options')

    # unlike deter, we will parse -e pid, eid means nargs = '+', and check if valid later
    # can use with -i and -c, and shortcut the process
    parser.add_argument(u'-e', u'--expinfo', dest=u'expinfo', action=u'store', nargs=2,
                        default=[False], metavar=(u'PROJECT', u'EXPERIMENT'),
                        help=u'give deterlab project and experiment info, cannot be used with -f')

    parser.add_argument(u'-v', u'--verbose', dest=u'verbose', action=u'store_true',
                        default=False,
                        help=u'print out debug logs')

    parser.add_argument(u'--version', action=u'version', version=u'%(prog)s %(VERSION)s')

    args = parser.parse_args()
    return args

def main():
    options = parse_options()
    # set the logger based on verbosity
    if options.verbose:
        LOG.setLevel(logging.DEBUG)
    else:
        LOG.setLevel(logging.WARN)
    # check how the user is going to supply info to this program, this is required
    if options.interactive:
        print colored(u'Use \\h for available values - there is a delay with using help', u'red')
        _ = get_inputs_from_user(options.expinfo)
    elif options.file_input:
        _ = parse_input_file(u'file_input_example.txt')


if __name__ == u'__main__':
    # dont allow hosts not on deterlab to attempt to run this script
    if verified_host():
        main()
    else:
        print colored(u'unable to run, must be on run on an isi.deterlab.net host', u'red')
        print colored(u'if this host is on deterlab, make sure the FQDN is the hostname', u'red')
