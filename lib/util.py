import sys, os, re, yaml, glob, traceback, inspect, io, subprocess, datetime, timeit
import secrets, base64
#
import beepy         # pip3 install beepy --upgrade

# for encryptions
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC



class Attributed(dict):

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__



def get_linenumber():
    cf = inspect.currentframe()
    return cf.f_back.f_lineno



def replace(subject, pattern, replacement = '', flags = 0):
    if isinstance(subject, dict):
        for key, value in subject.items():
            subject[key] = replace(value, replacement)
        return subject
    #
    if isinstance(pattern, dict):
        replacement = pattern
        for key, value in replacement.items():
            subject = subject.replace(key, str(value))
        return subject
    #
    return re.compile(pattern, flags).sub(replacement, subject)



def extract(regexp_search, text, group = 1):
    if regexp_search == '':
        return ''
    #
    found = re.search(regexp_search, text)
    if found:
        return found.group(group)
    return ''



def extract_int(regexp_search, text, group = 1):
    val = extract(regexp_search, text, group)
    if val == '':
        return None
    return int(val)



def parse_table_line(line, pointers):
    data = []
    for col in pointers:
        start, end = col
        data.append(line[start:end].strip())
    return data



def parse_table(payload):
    pointers    = []
    start       = 0
    columns     = payload[1].split()

    # parse column sizes based on second line
    for i, val in enumerate(columns):
        end = start + len(val)
        if i == len(columns) - 1:
            end = 1000
        pointers.append((start, end))
        start += len(val) + 1

    # parse column names
    names = parse_table_line(payload[0].lower(), pointers)

    # parse data
    data = []
    for i, line in enumerate(payload):
        if i <= 1:
            continue
        if line.strip() == '':
            break
        #
        data.append(dict(zip(names, parse_table_line(line, pointers))))
    return data



def get_files(glob_pattern, reverse = False, recursive = True):
    files = list(glob.glob(glob_pattern, recursive = recursive))
    if '/**/*' in glob_pattern and recursive:
        glob_pattern = glob_pattern.replace('/**/*', '/*')
        for file in glob.glob(glob_pattern):
            files.append(file)

    # to sort files without extensions, to have 1) schema.sql, 2) schema.100.sql
    filenames = {}
    for i, file in enumerate(files):
        files[i] = file.replace('\\', '/')          # consolidate slashes
        base, ext = os.path.splitext(files[i])
        if not (base in filenames):
            filenames[base] = []
        if not (ext in filenames[base]):            # also deduplicate
            filenames[base].append(ext)
    #
    out = []
    for base in sorted(filenames.keys(), reverse = reverse):
        for ext in sorted(filenames[base], reverse = reverse):
            out.append(base + ext)
    return out



def remove_cloud_junk(root = ''):
    root = root or os.path.abspath(os.path.curdir)

    # remove duplicated files
    for file in glob.glob(root + '/**/*.*', recursive = True):
        number = extract('(\s+[0-9]+\.)[^\.]+$', file)
        if number and os.path.exists(file.replace(number, '.')):
            os.remove(file)

    # remove empty folders
    for path, _, _ in os.walk(root, topdown = False):
        if '/.git/' in path:
            continue
        if len(os.listdir(path)) == 0:
            os.rmdir(path)



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



def store_yaml(w, payload, fix = False):
    payload = yaml.dump(payload, allow_unicode = True, default_flow_style = False, indent = 4) + '\n'
    if fix:
        payload = fix_yaml(payload)
    w.write(payload)



def print_header(message, append = ''):
    if append == None:
        append = ''
    print('\n{}{}\n{}'.format(message, (' ' + str(append)).rstrip(), '-' * len(message)))



def print_help(message):
    print('  -> {}'.format(message))



def print_table(data, columns = [], right_align = [], spacer = 3, start = 2, no_header = False, capture = False, limit_top = None, limit_bottom = None):
    if capture:
        buffer = io.StringIO()
        sys.stdout = buffer

    # lists to align table columns
    align       = []
    auto_align  = {}
    widths      = []

    # exception for 1 line dictionary
    if columns == []:
        if isinstance(data, dict):
            columns = list(data.keys())             # get from dictionary keys
            data    = [data]
        elif isinstance(data, list):
            if len(data) == 0 and widths == []:
                return
            if widths == []:
                columns = list(data[0].keys())      # get from first row
            else:
                columns = []
                for col in widths:
                    columns.append('')

    # if we pass the whole map...
    if isinstance(columns, dict):
        for name, width in columns.items():
            widths.append(width)
            align.append('R' if (name.upper() in right_align or name.lower() in right_align) else 'L')

    # all columns align to right
    if isinstance(right_align, bool) and right_align:
        right_align = columns

    # get column widths from headers and data
    if widths == []:
        for i, name in enumerate(columns):
            widths.append(len(name))
            align.append('R' if (name.upper() in right_align or name.lower() in right_align) else 'L')
            auto_align[i] = True
        #
        for row in data:
            # remove non printed columns
            filtered = {}
            for name, value in row.items():
                if name in columns:
                    filtered[name] = value

            # calculate column widths based on values from all rows
            for i, name in enumerate(filtered):
                if name in columns:
                    value       = str(filtered[name])
                    widths[i]   = max(widths[i], len(value))
                    #
                    if not (value.isnumeric() or value == None or value == ''):
                        auto_align[i] = False

        # auto align numeric columns to the right
        for i, numeric in auto_align.items():
            if numeric:
                align[i] = 'R'

    # create pattern for line replacement
    pattern     = start * ' '
    splitter    = []
    #
    for i, w in enumerate(widths):
        pattern += '{:' + align[i].replace('L', '<').replace('R', '>') + str(w) + '}' + (' ' * spacer)
        splitter.append(w * '-')

    # show data
    if not no_header:
        print()
        print(pattern.format(*columns).upper().replace('_', ' '))
        print(pattern.format(*splitter))
    #
    total_rows = len(data)
    if total_rows > 0:
        for i, row in enumerate(data):
            if limit_bottom != None and i < total_rows - limit_bottom:
                continue
            if limit_top != None and i >= limit_top:
                break
            #
            args = []
            for name in columns:
                args.append(row.get(name.lower(), '') or '')
            print(pattern.format(*args))
        #
        if not no_header:   # no footer if no header
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



def print_now(line, close = False):
    sys.stdout.write('\r' + str(line) + ('\n' if close else ''))  # overwrite current line and dont end it
    sys.stdout.flush()



def print_progress(done, target = 100, start = None, extra = '', width = 78):
    if done == None:
        return None

    # adjust number of dots for extra content
    dots    = width - 5               # count with 100%
    extra   = str(extra)
    #
    if len(extra) > 0:
        dots -= len(extra)         # count with extra length
        extra += ' '
    if start:
        dots -= 9                  # shorten to fit the timer
    #
    perc    = min(done + 1, target) / target
    show    = min(int(perc * 100 + 0.5), 100)
    dots    = int(dots * perc)

    # calculate/estimate time to the end
    estimate = ''
    if start:
        sofar       = round(get_start() - start, 2)
        estimate    = int((sofar / (perc * 100)) * 100 * (1 - perc))
        estimate    = str(datetime.timedelta(seconds = estimate)).rjust(8, ' ')
        if show == 100:
            estimate = ''.rjust(8, ' ')

    # refresh printed line
    line = '{} {}%'.format('.' * dots, show)
    text = ('{:<' + str(width - 9) + '} {} ').format(extra + line, estimate)
    sys.stdout.write('\r{}'.format(text))
    sys.stdout.flush()
    #
    if done + 1 == target:
        print()
        beep(sound = 1)
        return None
    return done + 1



def print_program_help(parser, program):
    print()
    parser.print_help(sys.stderr)
    print()
    print_header('FOR DOCUMENTATION AND EXAMPLES VISIT:')
    print('https://github.com/jkvetina/ADT/blob/main/doc/{}.md'.format(program))
    print()
    sys.exit()



def is_boolean(v):
    # to allow argparse evaluate to True, False AND None
    if isinstance(v, bool):
        return v
    if str(v).upper() in ('ON', 'YES', 'Y', 'TRUE', '1'):
        return True
    if str(v).upper() in ('OFF', 'NO', 'N', 'FALSE', '0'):
        return False
    return None



def is_boolstr(v):
    # to allow argparse evaluate to True, False or passed string value
    if v == None:
        return False
    return v



def beep(sound = 1):
    beepy.beep(sound)



def quit(message = ''):
    if message != None and len(str(message)) > 0:
        print(message)
        print()
    sys.exit()



def raise_error(message = '', stop = True, *extras):
    # print exception to screen
    splitter    = 80 * '#'
    exception   = traceback.format_exc().rstrip()
    if exception != 'NoneType: None':
        print('\n{}{}\n{}'.format(splitter, exception, splitter))

    # show more friendly message at the end
    message = 'ERROR: {}'.format(message)
    print('\n{}\n{}'.format(message, '-' * len(message)), extras if isinstance(extras, str) else '')
    if len(extras) > 0:
        for line in extras:
            print_help(line.rstrip())
    print()
    beep(sound = 3)
    if stop:
        sys.exit()



def assert_(condition, message, *extras):
    if (not condition or condition == None or condition == ''):
        message = 'ASSERT: {}'.format(message)
        print('\n{}\n{}'.format(message, '-' * len(message)))
        if len(extras) > 0:
            for line in extras:
                print_help(line.rstrip())
        print()
        sys.exit()



def run_command(command, stop = True, silent = False):
    result = subprocess.run(command, shell = True, capture_output = True, text = True)
    if result.returncode != 0 and not silent:
        # get all lines below error line
        lines = []
        for line in result.stdout.splitlines():
            line = line.rstrip()
            if line == 'Rollback':
                break
            if 'ERROR' in line.upper() or len(lines) > 0:
                lines.append(line)
        #
        print('\n#\n# REQUEST FAILED:\n#\n{}\n'.format('\n'.join(lines)))
        if stop:
            raise_error('COMMAND_ERROR: {} {}'.format(result.returncode, result.stderr.strip()))
    return (result.stdout or '')



def cleanup_sqlcl(output, lines = False):
    output = output.splitlines()
    if output[0].startswith('SQLcl') and output[2].startswith('Copyright') and output[4].startswith('Connected'):
        output = output[5:]
    size = len(output)
    if output[size - 2].startswith('Disconnected') and output[size - 1].startswith('Version'):
        size -= 2
        output = output[:size]
    #
    if not lines:
        output = '\n'.join(output)
    return output



def get_string(string, max_length = None, append = '..'):
    string = str(string)
    if max_length == None:
        return string
    cutoff = max_length - len(append)
    return (string[:cutoff] + '..') if len(string) > max_length else string


def get_start():
    return timeit.default_timer()

