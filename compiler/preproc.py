import compiler.tokens as toks
import compiler.utils as utl

import os

def include(tokens_lines, file_path):
    # support #include "file.cream"

    new_tokens_lines = []

    for line in tokens_lines:
        if line[1][0] == "#" and line[1][1] == "include":
            if len(line[1]) == 3 and utl.is_string(line[1][2]):
                include_file = line[1][2][1:-1]
            else:
                utl.say_error(f"Bad syntax\nSyntax example: #include \"file.cream\"")

            include_file = os.path.join(os.path.dirname(file_path), include_file)

            try:
                with open(include_file, "r") as ifile:
                    lines = ifile.read()

            except FileNotFoundError:
                utl.say_error(f"Could not open include file: {include_file}")

            tokens_lines = toks.tokenize_lines(lines)
            tokens_lines = include(tokens_lines, include_file)

            new_tokens_lines.extend(tokens_lines)

        else:
            new_tokens_lines.append(line)

    return new_tokens_lines

def preprocess(tokens_lines, file_path):
    # TODO: #define AA BB and #define AA(x, y) BB(132, y, func(z))

    tokens_lines = include(tokens_lines, file_path)

    return tokens_lines
