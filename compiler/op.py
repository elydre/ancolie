import compiler.tokens as toks
import compiler.output as out
import compiler.utils as utl
import compiler.defs as defs
import compiler.op as op


def init():
    output = out.output_code()
    output.add_comment("\n--- program initialization ---")

    stack_debut = defs.STATIC_ADDR

    output.add("ssp",
            (1, defs.STACK_PTR))
    output.add("sup",
            (1, defs.STACK_DEBUT_PTR))
    output.add("mov",
            (0, defs.STACK_PTR),
            (1, stack_debut))
    output.add("mov",
            (0, defs.STACK_DEBUT_PTR),
            (1, stack_debut))

    return output

def fini():
    output = out.output_code()
    output.add_comment("\n--- program finalization ---")

    output.add("hlt")

    return output

def calculate_rpn(rpn: list):
    output = out.output_code()

    if not rpn:
        utl.say_error("Empty RPN expression")

    if len(rpn) > 2 and rpn[0] == '(' and rpn[-1] == ')':
        utl.say_extra_error("Unnecessary parentheses in RPN expression")
        rpn = rpn[1:-1]

    stack_size = 0
    have_ampersand = False

    skip_to = 0
    tmp_number = None

    for i, token in enumerate(rpn):
        if i < skip_to:
            continue

        if token == '&':
            have_ampersand = True
            continue

        if defs.is_variable(token):
            v = defs.get_variable(token)
            if have_ampersand:
                if v.is_static:
                    output.add("push",
                            (1, v.addr))
                else:
                    output.add("push",
                            (0, defs.STACK_DEBUT_PTR))
                    output.add("add",
                            (2, 0), (1, utl.to_u16(-v.offset)))
                have_ampersand = False
            else:
                if v.is_static:
                    output.add("push",
                            (0, v.addr))
                else:
                    output.add("push",
                        (3, utl.to_u16(-v.offset)))
            stack_size += 1
            continue

        elif have_ampersand:
            utl.say_error(f"Unexpected '&' before token: {token}\nCorrect syntax example: ptr = &var")

        if token == '[':
            o, end = op.load_ptraddr(rpn[i:])
            skip_to = i + end
            output.atend(o)

            # load the value from the pointer's address

            output.add("mss",
                    (0, defs.STACK_PTR), (1, 0),
                    (2, 0), (1, 0))

            stack_size += 1

        elif defs.is_func(token):
            open_parens = 1
            for j, t in enumerate(rpn[i + 2:]):
                if t == '(':
                    open_parens += 1
                elif t == ')':
                    open_parens -= 1
                    if open_parens == 0:
                        skip_to = i + 2 + j
                        break
            else:
                utl.say_error(f"Unclosed parenthesis in function call\nSyntax example: func_name(var1, var2)")

            f = defs.get_func(token)
            if not f.does_return:
                utl.say_error(f"Function {f.name} does not return a value, cannot use in RPN expression")

            if f.no_rpn:
                utl.say_error(f"Function {f.name} cannot be used in RPN expressions")

            output.atend(op.call_func(f, rpn[i + 2:skip_to]))
            skip_to += 1

            # push the return value to the stack if the function returns a value
            output.add("push",
                    (0, defs.FUNC_RET_ADDR))
            stack_size += 1

        elif utl.is_number(token) or utl.is_char(token):
            v = utl.to_number(token)

            if (i + 1 < len(rpn)) and rpn[i + 1] in defs.CHARS_OPR: # optimize basic calculations
                tmp_number = v
                continue

            output.add("push", (1, v))
            stack_size += 1

        elif utl.is_string(token):
            converted_string = utl.convert_string(token)

            addr = out.get_static_addr(len(converted_string), converted_string)
            output.add("push",
                    (1, addr))
            stack_size += 1


        elif token in defs.CHARS_OPR:

            if tmp_number is not None:
                a = (2, 0)
                b = (1, tmp_number)
            else:
                a = (2, 1)
                b = (2, 0)
                stack_size -= 1

            if token == '+':
                output.add("add", a, b)
            elif token == '-':
                output.add("sub", a, b)
            elif token == '*':
                output.add("mul", a, b)
            elif token == '/':
                output.add("div", a, b)
            elif token == '%':
                output.add("mod", a, b)
            elif token == '==':
                output.add("eq", a, b)
            elif token == '!=':
                output.add("neq", a, b)
            elif token == '<':
                output.add("lt", a, b)
            elif token == '>':
                output.add("gt", a, b)
            elif token == '<=':
                output.add("lte", a, b)
            elif token == '>=':
                output.add("gte", a, b)
            elif token == '&&':
                output.add("and", a, b)
            elif token == '|':
                output.add("bor", a, b)

            if tmp_number is None:
                output.add("pop",
                    (1, 0))
            else:
                tmp_number = None

        else:
            utl.say_error(f"Unknown token in RPN expression: {token}")

        if stack_size < 1:
            utl.say_error("Invalid RPN expression: not enough values on the stack")

    if have_ampersand:
        utl.say_error("Invalid RPN expression: unexpected '&' at the end of the expression")

    if stack_size > 1:
        utl.say_error("Invalid RPN expression: too many values on the stack after evaluation")

    return output


def fast_assign_var(v: defs.variable, tokens: list):
    output = out.output_code()

    if len(tokens) == 1 and defs.is_variable(tokens[0]):
        v2 = defs.get_variable(tokens[0])

        if v.is_static and v2.is_static:
            output.add("mov",
                    (0, v.addr),
                    (0, v2.addr))
        elif v.is_static and not v2.is_static:
            output.add("mov",
                    (0, v.addr),
                    (3, utl.to_u16(-v2.offset)))
        elif not v.is_static and v2.is_static:
            output.add("mov",
                    (3, utl.to_u16(-v.offset)),
                    (0, v2.addr))
        else:
            output.add("mov",
                    (3, utl.to_u16(-v.offset)),
                    (3, utl.to_u16(-v2.offset)))

        return output

    if defs.is_func(tokens[0]):
        f = defs.get_func(tokens[0])

        if len(tokens) < 4 or tokens[1] != '(' or tokens[-1] != ')':
            return None

        if not f.does_return:
            utl.say_error(f"Function {f.name} does not return a value, cannot assign to variable {v.name}")

        output.atend(op.call_func(f, tokens[2:-1]))

        # move the result from FUNC_RET_ADDR to the variable's memory location
        output.add("mov",
                (3, utl.to_u16(-v.offset)),
                (0, defs.FUNC_RET_ADDR))

        return output

    return None

def load_ptraddr(tokens: list):
    output = out.output_code()

    if tokens[0] != "[":
        utl.say_error(f"(Internal) ptr resolution on non-pointer")

    is_onstack = False
    end = 0

    if tokens[1] == "[":
        o, e = op.load_ptraddr(tokens[1:])
        output.atend(o)
        end += e
        is_onstack = True

    elif defs.is_variable(tokens[1]) and tokens[2] == ']':
        ptr = defs.get_variable(tokens[1])
        end += 1

    else:
        # find the closing bracket and send to RPN calculator
        open_brackets = 1
        for i, token in enumerate(tokens[1:]):
            if token == '[':
                open_brackets += 1
            elif token == ']':
                open_brackets -= 1
                if open_brackets == 0:
                    end += i
                    break
        else:
            utl.say_error(f"Unclosed brackets in pointer access\nSyntax example: [ptr]")

        output.atend(op.calculate_rpn(tokens[1:end + 1]))
        return (output, end + 2)

    end += 1
    # check closing bracket
    if end >= len(tokens) or tokens[end] != ']':
        utl.say_error(f"Unclosed brackets in pointer access\nSyntax example: [ptr]")

    if is_onstack:
        output.add("mss",
                (0, defs.STACK_PTR), (1, 0),
                (2, 0), (1, 0))

    # load the pointer's address from memory
    elif ptr.is_static:
        output.add("push",
                (0, ptr.addr))
    else:
        output.add("push",
                (3, utl.to_u16(-ptr.offset)))

    return (output, end + 1)


def call_func(f: defs.func, tokens: list):
    args = toks.split_func_args(tokens)

    if not f.is_vaargs and len(args) != f.argc:
        utl.say_error(f"Wrong number of arguments for function {f.name}\nSyntax example: {f.name}({', '.join(['var' + str(i + 1) for i in range(f.argc)])})")

    if f.is_builtin:
        return f.blt_handler(args)

    output = out.output_code()

    end_label = utl.get_new_label()

    if f.is_vaargs:
        for arg in args[::-1]:
            output.atend(op.calculate_rpn(arg))

    # push the stack debut and the call end label
    output.add_push_label(end_label)

    output.add("push",
            (0, defs.STACK_DEBUT_PTR))

    # push the arguments to the stack
    if f.is_vaargs:
        output.add("mov",
                (0, defs.STACK_DEBUT_PTR),
                (0, defs.STACK_PTR))

        output.add("push",
                (1, utl.to_u16(len(args))))
        output.add("push", # TODO check if this is not eq to STACK_DEBUT_PTR
                (0, defs.STACK_PTR))
        output.add("add",
                (2, 0), (1, 3))
    else:
        for arg in args:
            output.atend(op.calculate_rpn(arg))

        output.add("mov",
                (0, defs.STACK_DEBUT_PTR),
                (0, defs.STACK_PTR))

        if f.argc > 0:
            output.add("add",
                    (0, defs.STACK_DEBUT_PTR),
                    (1, utl.to_u16(f.argc)))

    output.add_goto(f"func_{f.name}", (1, 0)) # unconditional jump to the function's code

    output.add_label(end_label)

    if f.is_vaargs:
        output.add("add",
                (0, defs.STACK_PTR),
                (1, utl.to_u16(len(args) + 1))) # pop the arguments
    else:
        output.add("pop",
                (1, 0)) # pop the call end label from the stack

    return output
