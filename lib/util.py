import re

def replace_dict(text, translation):
    regex = re.compile('|'.join(map(re.escape, translation)))
    return regex.sub(lambda match: translation[match.group(0)], text)

