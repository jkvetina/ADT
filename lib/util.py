import sys, os, re



def fix_path(dir):
    return os.path.normpath(dir).replace('\\', '/').rstrip('/') + '/'



def fix_yaml(payload):
    # change yaml formatting
    recent  = {}
    lines   = payload.splitlines()
    #
    for i, line in enumerate(lines):
        # calculate indentation for current and next line
        found = re.search('^(\s*)', line).group(1)
        if not found:
            continue
        #
        curr_line_indent = len(found)
        #
        if i >= len(lines):
            next_line_indent = 0
            continue
        else:
            next_line_indent = len(re.search('^(\s*)', lines[i + 1]).group(1))

        # split current line
        found = re.search('^(\s*)([^:]+)[:](.*)$', line)
        if found and curr_line_indent > 0:
            recent[i] = [found.group(1), found.group(2), found.group(3)]

        # fix previous lines when end of group is detected
        if next_line_indent != curr_line_indent:
            # calculate the width of attributes
            width = 0
            for j, split in recent.items():
                width = max(width, int(len(split[1]) / 4) * 4 + 4)
            #
            for j, split in recent.items():
                split[1] = split[1].ljust(width)
                lines[j] = '{}{}:{}'.format(*split)
            #
            recent = {}
    #
    return '\n'.join(lines)



def debug_dots(payload, length, mask_keys = []):
    for key, value in payload.items():
        if key in mask_keys:
            value = '*' * len(value)
        #
        if isinstance(value, dict):
            print('   {}:'.format(key))
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list):
                    sub_value = ' | '.join(sub_value)
                if sub_key in mask_keys:
                    sub_value = '*' * len(sub_value)
                print('      {} {} {}'.format(sub_key, '.' * (length - 3 - len(sub_key)), sub_value or ''))
        #
        elif isinstance(value, list):
            print('   {} {} {}'.format(key, '.' * (length - len(key)), ' | '.join(value)))
        #
        else:
            print('   {} {} {}'.format(key, '.' * (length - len(key)), value or ''))
    print()



def debug_table(payload, pattern = '  {:>16} | {}', right = [1], upper = True, mask_keys = ['pwd', 'wallet_pwd']):
    if isinstance(payload, dict):
        width = 0
        for column in payload.keys():
            width = max(width, int(len(column) / 4) * 4 + 4)
        #
        if pattern == '':
            pattern = '{:' + ('>' if 1 in right else '<') + str(width) + '} | {}'
        #
        for col1, col2 in payload.items():
            print(pattern.format(
                col1.upper() if upper else col1,
                '*' * len(col2) if col1 in mask_keys else col2
            ))
    #
    print()



def header(message, append = ''):
    print('\n{}\n{}'.format(message, '-' * len(message)), append)



def quit(message = ''):
    if len(message) > 0:
        print(message)
    sys.exit()



def raise_error(message = ''):
    message = 'ERROR: {}'.format(message)
    quit('\n{}\n{}'.format(message, '-' * len(message)))



def assert_(condition, message = ''):
    if not condition:
        message = 'ERROR: {}'.format(message)
        quit('\n{}\n{}'.format(message, '-' * len(message)))

