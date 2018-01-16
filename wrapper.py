import os
import logging
import subprocess
import re
from termcolor import colored
from typing import Dict


# print_nodes is a hack approach, so instead of importing click control and getting
# at the data ourselves, what we are going to do, is create a tmp aal with bogus inputs
# give it to magi to run, and look at the logs returned by magi to find the variables
# we care about.
# a bit of logic needs to go into this to infer which of the previous incorrect instructions
# correlates to which run
def print_nodes() -> None:
    pass

# see comments for print_nodes on issues with implement
def print_keys(click_element) -> None:
    pass


def get_click_element() -> str:
    cursor = colored('(element) > ', 'green')
    ask_click = 'Click Element:\n'
    click_element = input('{click}{cursor}'.format(cursor=cursor, click=ask_click))
    while click_element == '\h':
        print_nodes()
        click_element = input('{click}{cursor}'.format(cursor=cursor, click=ask_click))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = True if input(
        'set click_element to {element}? (y/n)\n'.format(element=click_element)
    )[0].lower() == 'y' else False
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_click_element()
    return click_element

def get_key_for_element(element: str) -> str:
    cursor = colored('(key) > ', 'green')
    ask_key = 'Element Key (to change):\n'
    element_key = input('{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key))
    while element_key == '\h':
        print_keys(element)
        element_key = input('{ekey}{cursor}'.format(cursor=cursor, ekey=ask_key))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = True if input(
        'set key to {key}? (y/n)\n'.format(key=element_key)
    )[0].lower() == 'y' else False
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_key_for_element(element)
    return element_key

def get_value_for_key(element_key: str) -> str:
    cursor = colored('(value) > ', 'green')
    ask_value = '{key}:\n'.format(key=element_key)
    key_value = input('{kv}{cursor}'.format(cursor=cursor, kv=ask_value))
    while key_value == '\h':
        key_value = input('{kv}{cursor}'.format(cursor=cursor, kv=ask_value))
    # probably not the best way, but if yes Yes y or Y, accept the input
    accept = True if input(
        'set value for {key} to {value}? (y/n)\n'.format(key=element_key, value=key_value)
    )[0].lower() == 'y' else False
    # super ghetto, but just recurse for no reason until they figure out what they want
    if not accept:
        return get_key_for_element(element_key)
    return element_key

def get_inputs_from_user() -> Dict:
    inputs = {}
    click_element = get_click_element()
    element_key = get_key_for_element(click_element)
    key_value = get_value_for_key(element_key)
    # TODO: add last step verification here.
    return inputs

def parse_input_file(path: str) -> Dict:
    pass


if __name__ == '__main__':
    _ = get_inputs_from_user()
    pass
