import sys, os, re, yaml
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



def get_encryption_key(password, salt):
    kdf = PBKDF2HMAC(
        algorithm   = hashes.SHA256(),
        length      = 32,
        salt        = salt,
        iterations  = 100000,
        backend     = default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password))



def encrypt(message, password):
    iter    = 100000
    salt    = secrets.token_bytes(16)
    key     = get_encryption_key(password.encode(), salt)
    #
    return base64.urlsafe_b64encode(
        b'%b%b%b' % (
            salt,
            iter.to_bytes(4, 'big'),
            base64.urlsafe_b64decode(Fernet(key).encrypt(message.encode())),
        )
    ).decode('ascii')



def decrypt(token, password):
    decoded = base64.urlsafe_b64decode(token.encode('ascii'))
    salt    = decoded[:16]
    token   = base64.urlsafe_b64encode(decoded[20:])
    key     = get_encryption_key(password.encode(), salt)
    #
    return Fernet(key).decrypt(token).decode()



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



def get_yaml(h, file = ''):
    try:
        data = list(yaml.load_all(h, Loader = yaml.loader.SafeLoader))
    except Exception:
        raise_error('INVALID YAML FILE!', '{}\n'.format(file) if file != '' else '')
    #
    if len(data) > 0:
        return data[0].items()
    return {}



def debug_dots(payload, length, mask_keys = []):
    for key, value in payload.items():
        if key in mask_keys:
            value = '*' * min(len(value), 20)
        #
        if isinstance(value, dict):
            print('   {}:'.format(key))
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list):
                    sub_value = ' | '.join(sub_value)
                if sub_key in mask_keys:
                    sub_value = '*' * min(len(sub_value), 20)
                print('      {} {} {}'.format(sub_key, '.' * (length - 3 - len(sub_key)), sub_value or ''))
        #
        elif isinstance(value, list):
            print('   {} {} {}'.format(key, '.' * (length - len(key)), ' | '.join(value)))
        #
        else:
            print('   {} {} {}'.format(key, '.' * (length - len(key)), value or ''))
    print()



def debug_table(payload, pattern = '  {:>16} | {}', right = [1], upper = True, sort = True, skip_none = True, mask_keys = []):
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
            if skip_none and col2 == None:
                continue
            #
            print(pattern.format(
                col1.upper() if upper else col1,
                '*' * min(len(col2), 20) if col1 in mask_keys else col2
            ))
    #
    print()



def header(message, append = ''):
    print('\n{}{}\n{}'.format(message, (' ' + append).rstrip(), '-' * len(message)))



def quit(message = ''):
    if len(message) > 0:
        print(message)
    sys.exit()



def raise_error(message = '', additional = ''):
    message = 'ERROR: {}'.format(message)
    quit('\n{}\n{}{}'.format(message, '-' * len(message), ('\n' if len(additional) > 0 else '') + additional))



def assert_(condition, message = ''):
    if not condition:
        message = 'ERROR: {}'.format(message)
        quit('\n{}\n{}'.format(message, '-' * len(message)))

