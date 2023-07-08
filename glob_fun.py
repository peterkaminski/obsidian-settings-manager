#! /usr/bin/env python
# HACK A TRONIC SPIKE
#
# Playing with a simplistic mechanism for controlling what to include and what to exclude.
# Globs are annoyingly tricky at times, but I like having some kind of pattern.
#
# No command line here, all "parameters" are environment variables.
# Simple use:
#     % IN_DIR=my_dir ./glob_fun.py
# Watch the fun:
#     % TRACE=1 IN_DIR=my_dir ./glob_fun.py

import os
from pathlib import Path

# HACK: No config file, fake it out here, this is just a spike
DIRECTIVES = '''
Include: .
Exclude: *.json
Exclude: workspace*
Include: snippets
Exclude: plugins
Include: plugins/buttons
Exclude: plugins/buttons/styles.css
Include: plugins/tag-wrangler
'''

# HACK: avoid command line parsing for this spike.
os.chdir(os.getenv('IN_DIR','.'))

# HACK: Using trivial env var to avoid command line parsing for this spike.
WANT_TRACING = os.getenv('TRACE')

def trace(*args, **kwargs):
    if WANT_TRACING:
        print(*args, **kwargs)

def only_files_from(item_list):
    return [item for item in item_list if Path(item).is_file()]

def get_items_from(item):
    '''
    Returns a list of Path objects for all the files described by item.

    Files are a list of themselves.
    Directories are the list of files in them, recursively.
    Globs are whatever files match the glob, if any.
    '''
    item_path = Path(item)
    if item_path.is_file():
        return [item_path]
    if item_path.is_dir():
        return only_files_from(item_path.glob('./**/*'))
    return only_files_from(Path().glob(item))

def process_item(item, operation, trace_description):
    '''Process item with operation.'''
    # Tracing here is more human than grep friendly,
    # but gives you a chance to see why files are/aren't being included.
    # For a non-spike we would figure out better tracing.
    items = get_items_from(item)
    trace(trace_description, item)
    for part in items:
        trace(part)
        operation(part)
    trace()

def process_one_directive(directive, collection):
    '''Update collection based on a single directive.'''
    include_part = directive.removeprefix('Include: ')
    if include_part != directive:  # We removed it, so we have something to include
        return process_item(include_part, collection.add, "Including from")

    exclude_part = directive.removeprefix('Exclude: ')
    if exclude_part != directive:  # We removed it, so we have something to include
        return process_item(exclude_part, collection.discard, "Excluding from")

    # SPIKE - error handling TBD - could do it by preloading the directives
    # and erroring out if there are unknown lines. That might be better?
    if directive:  # Ignore blank lines
        print(f'Unknown directive {directive!r}, ignoring.')

def process(directives):
    '''Return a set of files resulting from processing a sequence of directives.'''
    result = set()
    for directive in directives:
        process_one_directive(directive, result)
    return result

if __name__ == '__main__':
    print()
    result = process(DIRECTIVES.splitlines())
    print()
    print('Final list:')
    for x in sorted(map(str, result)):
        print(x)

