import compiler.output as out
import compiler.utils as utl
import compiler.defs as defs

def compute_opcodes_pattern(str):
    if not str.startswith("#"):
        return (None, [str])

    if not ":" in str:
        utl.say_error(f"Invalid pattern optimization string: {str}", internal=True)

    alias, opcodes = str.split(":", 1)

    if not alias:
        utl.say_error(f"Invalid pattern optimization string: {str}", internal=True)

    return (alias, opcodes.split("|"))


class opti_pattern:
    def __init__(self, name, pattern, replacement):
        self.name = name
        self.pattern = pattern
        self.replacement = replacement

    def tryreplace(self, code, start):
        matching_opcodes = {} # "#1: aaa"
        matching_args = {}    # "$1: (1, 123)"

        if len(code.instructions) - start < len(self.pattern):
            return None

        for i, pline in enumerate(self.pattern):
            instr = code.instructions[start + i]

            if instr.dont_optimize:
                return None

            sline = instr.raw_args
            if not sline or len(pline) != len(sline):
                return None

            # check opcode
            alias, opcodes = compute_opcodes_pattern(pline[0])

            if alias and alias in matching_opcodes.keys():
                utl.say_error(f"Redefinition of pattern opcode alias: {alias}", internal=True)

            if not sline[0] in opcodes:
                return None

            if alias:
                matching_opcodes[alias] = sline[0]

            # check args
            for j, parg in enumerate(pline[1:]):
                sarg = sline[j + 1]

                if not isinstance(parg, str):
                    if parg != sarg:
                        return None
                    continue

                if parg.startswith("$$"):
                    parg = parg[1:]
                    if parg not in matching_args.keys():
                        utl.say_error(f"Pattern argument not defined: {parg}", internal=True)
                    if matching_args[parg] != sarg:
                        return None

                elif parg.startswith("$"):
                    if parg in matching_args.keys():
                        utl.say_error(f"Redefinition of pattern argument: {parg}", internal=True)
                    matching_args[parg] = sarg

                else:
                    utl.say_error(f"Unexpected pattern argument: {parg}", internal=True)

        # the pattern matches !
        # now we need to generate the replacement instructions
        output = out.output_code()

        lineno = code.instructions[start].lineno

        for rline in self.replacement:
            opcode = rline[0]
            if opcode.startswith("#"):
                if opcode not in matching_opcodes.keys():
                    utl.say_error(f"Pattern opcode alias not defined: {opcode}", internal=True)
                opcode = matching_opcodes[opcode]

            args = []
            for rarg in rline[1:]:
                if not isinstance(rarg, str):
                    args.append(rarg)
                    continue
                if rarg.startswith("$"):
                    if rarg not in matching_args.keys():
                        utl.say_error(f"Pattern argument not defined: {rarg}", internal=True)
                    args.append(matching_args[rarg])
                else:
                    args.append(rarg)

            output.add(opcode, *args)

        utl.verbose(f"Optimization pattern line {lineno}: {self.name}")

        for instr in output.instructions:
            instr.lineno = lineno

        return output.instructions

ops = "sub|add|mul|div|mod|eq|neq|lt|gt|lte|gte|and|band|bor"

patterns = [
    opti_pattern(
        "a = b",
        [
            ("push", "$1"),
            ("pop", "$2")
        ],
        [
            ("mov", "$2", "$1")
        ]
    ),
    opti_pattern(
        "a = a # n",
        [
            ("push", "$1"),
            (f"#1:{ops}", (2, 0), "$2"),
            ("pop", "$$1")
        ],
        [
            ("#1", "$1", "$2")
        ]
    ),
    opti_pattern(
        "a = a # b",
        [
            ("push", "$1"),
            ("push", "$2"),
            (f"#1:{ops}", (2, 1), (2, 0)),
            ("pop", (1, 0)),
            ("pop", "$$1")
        ],
        [
            ("#1", "$1", "$2")
        ]
    ),
    opti_pattern(
        "a = n # p",
        [
            ("push", "$2"),
            (f"#1:{ops}", (2, 0), (2, 1)),
            ("pop", "$1")
        ],
        [
            ("mov", "$1", "$2"),
            ("#1", "$1", (2, 0))
        ]
    ),
    opti_pattern(
        "a = b # n",
        [
            ("push", "$2"),
            (f"#1:{ops}", (2, 0), "$3"),
            ("pop", "$1")
        ],
        [
            ("mov", "$1", "$2"),
            ("#1", "$1", "$3")
        ]
    ),
    opti_pattern(
        "in(a)",
        [
            ("push", "$1"),
            ("in", (0, defs.FUNC_RET_ADDR), (2, 0)),
            ("pop", (1, 0))
        ],
        [
            ("in", (0, defs.FUNC_RET_ADDR), "$1")
        ]
    ),
    opti_pattern(
        "b = in(a)",
        [
            ("in", (0, defs.FUNC_RET_ADDR), "$1"),
            ("mov", "$2", (0, defs.FUNC_RET_ADDR))
        ],
        [
            ("in", "$2", "$1")
        ]
    ),
    opti_pattern(
        "out(a, b)",
        [
            ("push", "$1"),
            ("push", "$2"),
            ("out", (2, 1), (2, 0)),
            ("pop", (1, 0)),
            ("pop", (1, 0))
        ],
        [
            ("out", "$1", "$2")
        ]
    ),
    opti_pattern(
        "? # a",
        [
            ("push", "$1"),
            (f"#1:{ops}", (2, 1), (2, 0)),
            ("pop", (1, 0))
        ],
        [
            ("#1", (2, 0), "$1")
        ]
    )
]

def optimize(code):
    max_iter = len(code.instructions) * len(patterns) * 2
    inter = 0

    longest_pattern = max([len(p.pattern) for p in patterns])

    i = 0
    while i < len(code.instructions) and inter < max_iter:
        for pattern in patterns:
            new_instructions = pattern.tryreplace(code, i)
            if new_instructions is None:
                continue
            code.instructions[i:i + len(pattern.pattern)] = new_instructions
            i += len(new_instructions) - len(pattern.pattern) - longest_pattern
            if i < 0:
                i = 0
            break
        else:
            i += 1
        inter += 1

    if inter >= max_iter:
        utl.say_error(f"Infinite loop detected in optimization pass", internal=True)

    return code
