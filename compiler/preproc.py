import compiler.tokens as toks
import compiler.utils as utl
import compiler.defs as defs

import os

def include(tokens_lines, file_path):
    # support #include "file.cream"

    new_tokens_lines = []

    for lineno, line in tokens_lines:
        defs.CURRENT_LNO = lineno
    
        if line[0] == "#" and line[1] == "include":
            if len(line) == 3 and utl.is_string(line[2]):
                include_file = line[2][1:-1]
            else:
                utl.say_error("Bad syntax", correct_syntax = "#include \"file.cream\"")

            include_file = os.path.join(os.path.dirname(file_path), include_file)

            try:
                with open(include_file, "r") as ifile:
                    lines = ifile.read()

            except FileNotFoundError:
                utl.say_error(f"Could not open include file: {include_file}")

            tokens_lines = toks.tokenize_lines(lines, include_file)
            tokens_lines = include(tokens_lines, include_file)

            new_tokens_lines.extend(tokens_lines)

        else:
            new_tokens_lines.append((lineno, line))

    return new_tokens_lines


def define(tokens_lines):
    # support #define MACRO replacement
    # and     #define MACRO(arg) replacement(arg)

    class define_data:
        def __init__(self):
            self.to_replace = None
            self.args = None
            self.replacement_tokens = []

    defines = []

    new_tokens_lines = []

    for lineno, line in tokens_lines:
        defs.CURRENT_LNO = lineno

        if line[0] == "#" and line[1] == "define":
            if len(line) < 4:
                utl.say_error("Bad syntax", correct_syntax = "#define MACRO replacement")

            new_define = define_data()
            defines.append(new_define)
            
            new_define.to_replace = line[2]

            # check for parentheses

            if line[3] != "(":
                new_define.replacement_tokens = line[3:]
                continue

            closing_par = toks.find_closing_paren(line, 3)

            if closing_par == -1:
                utl.say_error(f"Unclosed parentheses in define statement", correct_syntax = "#define MACRO(arg) something(arg)")

            # check if the closing parenthesis is the last token in the line
            if closing_par == len(line) - 1:
                new_define.replacement_tokens = line[3:]
                continue

            args = toks.split_func_args(line[4:closing_par])
            for e in args:
                if len(e) != 1:
                    utl.say_error("Invalid argument in define statement", correct_syntax = "#define MACRO(arg) something(arg)")
                if not utl.is_valid_name(e[0]):
                    utl.say_error(f"Invalid argument name in define statement: {e[0]}", correct_syntax = "#define MACRO(arg) something(arg)")
            new_define.args = [e[0] for e in args]
            new_define.replacement_tokens = line[closing_par + 1:]

            continue

        # line length may be changed, we can't use a for range loop
        i = -1
        while i < len(line) - 1:
            i += 1

            for e in defines:
                if line[i] != e.to_replace:
                    continue

                if e.args is None:
                    line[i:i + 1] = e.replacement_tokens
                    i -= len(e.replacement_tokens) - 1
                    continue

                if line[i + 1] != "(":
                    continue

                closing_par = toks.find_closing_paren(line, i + 1)

                if closing_par == -1:
                    utl.say_error(f"Unclosed parentheses in macro call")

                args = toks.split_func_args(line[i + 2:closing_par])

                if len(args) != len(e.args):
                    utl.say_error(f"Macro call has wrong number of arguments\nExpected {len(e.args)} but got {len(args)}")

                replacement_tokens = e.replacement_tokens.copy()

                for j in range(len(e.args)):
                    for k in range(len(replacement_tokens)):
                        if replacement_tokens[k] == e.args[j]:
                            replacement_tokens[k:k + 1] = args[j]

                line[i:closing_par + 1] = replacement_tokens
                i -= len(replacement_tokens) - 1

        new_tokens_lines.append((lineno, line))

    return new_tokens_lines


def preprocess(tokens_lines, file_path):
    tokens_lines = include(tokens_lines, file_path)
    tokens_lines = define(tokens_lines)

    return tokens_lines
