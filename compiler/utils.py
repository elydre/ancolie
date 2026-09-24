import compiler.defs as defs

import ctypes

char_escape_dict = {
    "\\n": 10,
    "\\t": 9,
    "\\r": 13,
    "\\b": 8,
    "\\'": 39,
    '\\"': 34,
    "\\\\": 92
}

def say_error(message, internal=False):
    if internal:
        print(end = "Internal ")
    print(f"Error line {defs.CURRENT_LNO}: {message}")

    if internal:
        raise Exception(message)

    exit(1)

def say_extra_error(message):
    if not defs.EXTRAERR:
        return
    print(f"Extra Error line {defs.CURRENT_LNO}: {message}")
    exit(1)

def verbose(message):
    if not defs.VERBOSE:
        return
    print(message)

def is_valid_name(s):
    if not s:
        return False
    if not (s[0].isalpha() or s[0] == "_"):
        return False
    for c in s:
        if not (c.isalnum() or c == "_"):
            return False
    if s in defs.KEYWORDS:
        return False
    return True

CURRENT_LABEL = 0

def get_new_label():
    global CURRENT_LABEL
    label = f"label_{CURRENT_LABEL}"
    CURRENT_LABEL += 1
    return label

CURRENT_USERASM = 0

def get_new_userasm():
    global CURRENT_USERASM
    label = f"userasm_{CURRENT_USERASM}"
    CURRENT_USERASM += 1
    return label

def to_u16(value):
    return ctypes.c_ushort(value).value

def is_number(s):
    try:
        if s.startswith("0x"):
            int(s, 16)
        else:
            int(s)
        return True
    except ValueError:
        return False

def to_number(s):
    if is_char(s):
        if len(s) == 3:
            return ord(s[1])
        return char_escape_dict[s[1:3]]

    if s.startswith("0x"):
        return int(s, 16)
    else:
        return int(s)

def is_char(s):
    if s[0] != "'" or s[-1] != "'":
        return False
    if len(s) == 3:
        return True
    if len(s) == 4 and s[1:3] in char_escape_dict:
        return True
    return False

def is_string(s):
    if s[0] != '"' or s[-1] != '"':
        return False
    return True

def convert_string(s):
    # returns a list of numbers representing the string, with a null terminator at the end

    result = []
    i = 1
    while i < len(s) - 1:
        if s[i] == '\\':
            if i + 1 < len(s) - 1 and s[i:i+2] in char_escape_dict:
                result.append(char_escape_dict[s[i:i+2]])
                i += 2
            else:
                say_error(f"Invalid escape sequence: {s[i:i+2]}")
        else:
            result.append(ord(s[i]))
            i += 1

    result.append(0)  # null terminator
    return result
