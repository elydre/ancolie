import compiler.utils as utl
import compiler.defs as defs

def find_longest_match(string: str):
    longest_match = ""
    for match in defs.CHARS_SPE:
        if string.startswith(match) and len(match) > len(longest_match):
            longest_match = match
    return longest_match

def tokenize_line(line: str):
    tokens = []
    lines = []

    in_string = False
    string_token = None
    current_token = ""

    skip_to = 0

    for i, char in enumerate(line):
        if i < skip_to:
            continue

        if (in_string and char == string_token) or ((not in_string) and (char in ["'", '"'])):
            current_token += char
            if in_string:
                tokens.append(current_token)
                current_token = ""
            else:
                string_token = char
            in_string = not in_string
            continue

        if in_string:
            current_token += char
            continue

        elif char.isspace():
            tokens.append(current_token)
            current_token = ""
            continue

        matching = find_longest_match(line[i:])

        if matching:
            skip_to = i + len(matching)
            tokens.append(current_token)
            current_token = ""

            if matching == "//":
                break
            elif matching == "{" or matching == "}":
                if tokens:
                    lines.append(tokens.copy())
                tokens = [matching]
                lines.append(tokens.copy())
                tokens = []
            else:
                tokens.append(matching)
            continue

        current_token += char

    tokens.append(current_token)

    if tokens:
        lines.append(tokens.copy())

    for line in lines:
        while "" in line:
            line.remove("")

    while [] in lines:
        lines.remove([])

    return lines

def tokenize_lines(lines: str):
    tokens_lines = []

    for lno, line in enumerate(lines.splitlines(), start=1):
        defs.CURRENT_LNO = lno

        line = line.strip()
        for t in tokenize_line(line):
            tokens_lines.append((lno, t))

    return tokens_lines

def locate_braces(lines: list, current_line: int = 0):
     # find the opening brace '{'
    if current_line + 1 >= len(lines) or lines[current_line + 1][1] != ['{']:
        utl.say_error("Bad syntax\nExpected '{' after 'if' statement")

    # find the closing brace '}'
    closing_line = current_line + 2

    opening_braces = 1
    while closing_line < len(lines) :
        if lines[closing_line][1] == ['}']:
            opening_braces -= 1
            if opening_braces == 0:
                break
        elif lines[closing_line][1] == ['{']:
            opening_braces += 1
        closing_line += 1
    else:
        utl.say_error("Bad syntax\nExpected '}' after 'if' block")

    return closing_line

def split_func_args(tokens: list):
    args = []
    current_arg = []
    opening_brackets = 0

    for token in tokens:
        if token == ',' and opening_brackets == 0:
            args.append(current_arg)
            current_arg = []
        else:
            if token == '(':
                opening_brackets += 1
            elif token == ')':
                opening_brackets -= 1
            current_arg.append(token)

    if current_arg:
        args.append(current_arg)

    return args
