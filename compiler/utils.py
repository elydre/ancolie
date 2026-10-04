import compiler.defs as defs

import ctypes
import sys

char_escape_dict = {
    "\\0": 0,
    "\\n": 10,
    "\\t": 9,
    "\\r": 13,
    "\\b": 8,
    "\\'": 39,
    '\\"': 34,
    "\\\\": 92
}

def say_error(message, correct_syntax = None, internal=False, extra=False):
    if extra and not defs.ARG_EXTRAERR:
        return
    
    line_name = f"{defs.CURRENT_LNO[0]}:{defs.CURRENT_LNO[1]}"

    error_name = ""
    if extra:
        error_name = "extra "
    if internal:
        error_name += "internal "
    error_name += "error"

    if sys.stderr.isatty() and defs.ARG_COOLERR:
        error_name = f"\033[1;91m( {error_name} )\033[0m"
        message = f"\033[1m{message}\033[0m"
        if correct_syntax:
            message += f"\n\033[32m// correct syntax: {correct_syntax}\033[0m"
        print(f"{error_name} {line_name} >> {message}", file=sys.stderr)
    else:
        print(f"{line_name}: {error_name}: {message}", file=sys.stderr)


    if internal:
        raise Exception(message)

    exit(1)

def verbose(message):
    if not defs.ARG_VERBOSE:
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
        n = int(s, 16)
    else:
        n = int(s)

    if n < 0 or n > 65535:
        say_error(f"Number out of range: {n}")

    return n

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
