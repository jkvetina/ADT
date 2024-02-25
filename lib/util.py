import sys, os, re, yaml, traceback, io
import secrets, base64

# for encryptions
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC



class Attributed(dict):

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__



def replace(subject, pattern, replacement, flags = 0):
    return re.compile(pattern, flags).sub(replacement, subject)



def get_encryption_key(password, salt):
    k = PBKDF2HMAC(
        algorithm   = hashes.SHA256(),
        length      = 32,
        salt        = salt.encode(),
        iterations  = 100000,
        backend     = default_backend()
    )
    return Fernet(base64.urlsafe_b64encode(k.derive((7 * password).encode())))



def encrypt(message, password, salt = ''):
    if (password == None or password == ''):
        raise_error('NEED KEY TO ENCRYPT PASSWORDS!')
    #
    key     = get_encryption_key(password, salt)
    token   = key.encrypt(message.encode())

    # check decryption of encrypted password
    if message != decrypt(token, password, salt):
        raise_error('ENCRYPTION FAILED!')
    return token



def decrypt(token, password, salt = ''):
    if (password == None or password == ''):
        raise_error('NEED KEY TO DECRYPT PASSWORDS!')
    #
    key = get_encryption_key(password, salt)
    try:
        return key.decrypt(token).decode()
    except:
        raise_error('PASSWORD DECRYPTION FAILED')



def fix_path(dir):
    return os.path.normpath(dir).replace('\\', '/').rstrip('/') + '/'



def fix_yaml(payload):
    # change yaml formatting
    recent  = {}
    lines   = payload.splitlines()
    #
    curr_line_indent = 0
    prev_line_indent = 0
    next_line_indent = 0
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
            prev_line_indent = curr_line_indent
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
            if next_line_indent > curr_line_indent and prev_line_indent != curr_line_indent:
                width = 0
            #
            for j, split in recent.items():
                split[1] = split[1].ljust(width)
                lines[j] = '{}{}:{}'.format(*split)
            #
            recent = {}
        #
        prev_line_indent = curr_line_indent
    #
    return '\n'.join(lines)



def get_yaml(h, file = ''):
    try:
        data = list(yaml.load_all(h, Loader = yaml.loader.SafeLoader))
    except:
        raise_error('INVALID YAML FILE!', '{}\n'.format(file) if file != '' else '')
    #
    if len(data) > 0:
        return data[0].items()
    return {}



def print_header(message, append = ''):
    print('\n{}{}\n{}'.format(message, (' ' + append).rstrip(), '-' * len(message)))



def print_table(data, columns = [], right_align = [], spacer = 3, start = 2, capture = False):
    if capture:
        buffer = io.StringIO()
        sys.stdout = buffer

    # exception for 1 line dictionary
    if columns == []:
        if isinstance(data, dict):
            columns = list(data.keys())         # get from dictionary keys
            data    = [data]
        elif isinstance(data, list):
            if len(data) == 0:
                return
            columns = list(data[0].keys())      # get from first row

    # all columns align to right
    if isinstance(right_align, bool) and right_align:
        right_align = columns

    # get column widths from headers and data
    widths      = []
    align       = []
    auto_align  = {}
    #
    for i, name in enumerate(columns):
        widths.append(len(name))
        align.append('R' if (name.upper() in right_align or name.lower() in right_align) else 'L')
        auto_align[i] = True
    #
    for row in data:
        for i, name in enumerate(row):
            if name in columns:
                value       = str(row[name])
                widths[i]   = max(widths[i], len(value))
                #
                if not value.isnumeric():
                    auto_align[i] = False

    # auto align numeric columns to the right
    for i, numeric in auto_align.items():
        if numeric:
            align[i] = 'R'

    # create pattern for line replacement
    pattern     = start * ' '
    splitter    = []
    for i, w in enumerate(widths):
        pattern += '{:' + align[i].replace('L', '<').replace('R', '>') + str(w) + '}' + (' ' * spacer)
        splitter.append(w * '-')

    # show data
    print()
    print(pattern.format(*columns).upper().replace('_', ' '))
    print(pattern.format(*splitter))
    for i, row in enumerate(data):
        args = []
        for name in columns:
            args.append(row.get(name.lower(), '') or '')
        print(pattern.format(*args))
    print()

    # instead of printing to screen return content as string
    if capture:
        buffer      = buffer.getvalue()
        sys.stdout  = sys.__stdout__
        return buffer



def print_args(payload, length = 18, skip_keys = []):
    for key, value in payload.items():
        if (key in skip_keys or value == None or value == ''):
            continue
        #
        if isinstance(value, dict):
            print('   {}:'.format(key))
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list):
                    sub_value = ' | '.join(sub_value)
                if (sub_key in skip_keys or sub_value == None or sub_value == ''):
                    continue
                print('      {} {} {}'.format(sub_key, '.' * (length - 3 - len(sub_key)), sub_value or ''))
        #
        elif isinstance(value, list):
            print('   {} {} {}'.format(key, '.' * (length - len(key)), ' | '.join(value)))
        #
        else:
            print('   {} {} {}'.format(key, '.' * (length - len(key)), value or ''))
    print()



def print_pipes(payload, pattern = '  {:>16} | {}', right = [1], upper = True, sort = True, skip_none = True, skip = []):
    if isinstance(payload, dict):
        keys = payload.keys()
        if sort:
            keys = sorted(keys)
        #
        width = 0
        for column in keys:
            width = max(width, int(len(column) / 4) * 4 + 4)
        #
        if pattern == '':
            pattern = '{:' + ('>' if 1 in right else '<') + str(width) + '} | {}'
        #
        for col1 in keys:
            col2 = payload[col1]
            if col1 in skip or (skip_none and col2 == None):
                continue
            #
            print(pattern.format(
                col1.upper() if upper else col1,
                col2
            ))
    #
    print()



def quit(message = ''):
    if len(message) > 0:
        print(message)
        print()
    sys.exit()



def raise_error(message = '', extra = ''):
    # print exception to screen
    splitter    = 80 * '#'
    exception   = traceback.format_exc().rstrip()
    if exception != 'NoneType: None':
        print('\n{}{}\n{}'.format(splitter, exception, splitter))

    # show more friendly message at the end
    message = 'ERROR: {}'.format(message)
    print('\n{}\n{}'.format(message, '-' * len(message)))
    if len(extra) > 0:
        print(extra)
    print()
    sys.exit()



def assert_(condition, message, extra = ''):
    if (not condition or condition == None or condition == ''):
        message = 'ASSERT: {}'.format(message)
        print('\n{}\n{}'.format(message, '-' * len(message)))
        if len(extra) > 0:
            print(extra)
        print()
        sys.exit()

