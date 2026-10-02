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

def validate_expression(tokens: list):
    if not tokens:
        utl.say_error("Empty expression")

    previous = "("
    i = 0

    while i < len(tokens):
        token = tokens[i]

        print(f"Validating token: {token}, previous: {previous}")

        if token in defs.CHARS_OPR:
            if previous in ("operator", "(") and token != "&":
                utl.say_error(f"Missing value before operator '{token}'")

            if token == "&" and previous not in ("operator", "("):
                utl.say_error(f"Unexpected '&' operator without a variable")

            if i == len(tokens) - 1 and token not in ("++", "--"):
                utl.say_error(f"Operator at the end of expression '{token}'")

            if token in ("++", "--"):
                if previous != "operand":
                    utl.say_error(f"Unexpected '{token}' operator without a variable")
            else:        
                previous = "operator"

        elif token == "(":
            if previous == "operand":
                utl.say_error("Missing operator before opening parenthesis")
            previous = "("

        elif token == ")":
            if previous in ("operator", "("):
                utl.say_error("Missing value before closing parenthesis")
            previous = "operand"

        else:
            if previous == "operand":
                utl.say_error(f"Missing operator before value '{token}'")
            previous = "operand"

            if len(tokens) > i + 1 and tokens[i + 1] == "(" and defs.is_func(token):
                close_paren = toks.find_closing_paren(tokens, i + 1)
                if close_paren == -1:
                    utl.say_error("Unclosed parenthesis in function call", correct_syntax = "func_name(var1, var2)")
                i = close_paren

        i += 1


def infix_to_rpn(tokens: list):
    validate_expression(tokens)

    stack = []
    rpn = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token in defs.CHARS_OPR:
            while (stack and stack[-1] != '(' and
                     defs.get_operator_priority(stack[-1]) >= defs.get_operator_priority(token)):
                rpn.append(stack.pop())
            stack.append(token)
        elif token == '(':
            stack.append(token)
        elif token == ')':
            while stack and stack[-1] != '(':
                rpn.append(stack.pop())
            if not stack:
                utl.say_error("Too many closing parentheses in expression")
            stack.pop()  # pop the '('
        else:
            if i + 1 < len(tokens) and tokens[i + 1] == '(' and defs.is_func(token):
                close_paren = toks.find_closing_paren(tokens, i + 1)
                if close_paren == -1:
                    utl.say_error("Unclosed parenthesis in function call", correct_syntax = "func_name(var1, var2)")
                rpn.extend(tokens[i:close_paren + 1])
                i = close_paren
            else:
                rpn.append(token)

        i += 1

    while stack:
        if stack[-1] == '(':
            utl.say_error("Too many opening parentheses in expression")
        rpn.append(stack.pop())

    return rpn

def calculate_rpn(rpn: list, is_infix: bool = True):
    output = out.output_code()

    if len(rpn) > 1 and rpn[0] == '(' and toks.find_closing_paren(rpn, 0) == len(rpn) - 1:
        utl.say_error("Unnecessary parentheses in RPN expression", extra=True)
        rpn = rpn[1:-1]

    if len(rpn) == 0:
        utl.say_error("Empty expression")

    if is_infix:
        print(rpn)
        rpn = infix_to_rpn(rpn)
        print(rpn)

    stack_size = 0

    skip_to = 0
    tmp_number = None

    last_variable = None

    for i, token in enumerate(rpn):
        if i < skip_to:
            continue

        if last_variable is not None:
            finish = False
        
            if last_variable.is_static:
                output.add("push",
                        (0, last_variable.addr))
            else:
                output.add("push",
                    (3, utl.to_u16(-last_variable.offset)))

            if token == '&':
                if last_variable.is_static:
                    output.add("push",
                            (1, last_variable.addr))
                else:
                    output.add("push",
                            (0, defs.STACK_DEBUT_PTR))
                    output.add("add",
                            (2, 0), (1, utl.to_u16(-last_variable.offset)))
                finish = True
                    
            elif token in ("++", "--"):
                output.add("add" if token == "++" else "sub",
                        (0, last_variable.addr) if last_variable.is_static else (3, utl.to_u16(-last_variable.offset)), (1, 1))
                finish = True
            
            stack_size += 1
        
            if finish:
                last_variable = None
                continue
        
        last_variable = None
        
        if defs.is_variable(token):
            last_variable = defs.get_variable(token)
            continue

        elif token == '[':
            o, end = op.load_ptraddr(rpn[i:])
            skip_to = i + end
            output.atend(o)

            # load the value from the pointer's address

            output.add("mss",
                    (0, defs.STACK_PTR), (1, 0),
                    (2, 0), (1, 0))

            stack_size += 1

        elif defs.is_struct(rpn[i]):
            o, end = op.load_fieldaddr(rpn[i:])
            skip_to = i + end
            output.atend(o)

            # load the value from the pointer's address

            output.add("mss",
                    (0, defs.STACK_PTR), (1, 0),
                    (2, 0), (1, 0))

            stack_size += 1

        elif defs.is_func(token):
            f = defs.get_func(token)
            if not f.does_return:
                utl.say_error(f"Function {f.name} does not return a value, cannot use in expression")

            if f.no_rpn:
                utl.say_error(f"Function {f.name} cannot be used in expressions")

            if len(rpn) < i + 2 or rpn[i + 1] != '(':
                utl.say_error(f"Function {token} must be called with parentheses", correct_syntax = f"{token}(arg1, arg2)")

            end = toks.find_closing_paren(rpn, i + 1)
            if end == -1:
                utl.say_error("Unclosed parenthesis in function call", correct_syntax = f"{token}(arg1, arg2)")

            output.atend(op.call_func(f, rpn[i + 2:end]))
            skip_to = end + 1

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
            elif token == '|b':
                output.add("bor", a, b)
            elif token == '&b':
                output.add("band", a, b)
            elif token == '>>':
                if tmp_number is None:
                    utl.say_error(f"Bitshift operator requires a number as second operand")
                output.add("div", a, (1, 2 ** tmp_number))
            elif token == '<<':
                if tmp_number is None:
                    utl.say_error(f"Bitshift operator requires a number as second operand")
                output.add("mul", a, (1, 2 ** tmp_number))
            else:
                utl.say_error(f"Unknown operator in expression: {token}", internal=True)

            if tmp_number is None:
                output.add("pop",
                    (1, 0))
            else:
                tmp_number = None

        else:
            utl.say_error(f"Unknown token in expression: {token}")

        if stack_size < 1:
            utl.say_error("Invalid RPN expression: not enough values on the stack", internal=is_infix)

    if stack_size > 1:
        utl.say_error("Invalid RPN expression: too many values on the stack after evaluation", internal=is_infix)

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
        utl.say_error("Pointer resolution on non-pointer", internal=True)

    # find the closing bracket and send to RPN calculator

    open_brackets = 1
    end = 1

    for i, token in enumerate(tokens[1:]):
        if token == '[':
            open_brackets += 1
        elif token == ']':
            open_brackets -= 1
            if open_brackets == 0:
                end += i
                break
    else:
        utl.say_error("Unclosed brackets in pointer access", correct_syntax = "[ptr]")

    output.atend(op.calculate_rpn(tokens[1:end]))
    return (output, end + 1)

def load_fieldaddr(tokens: list):
    # resolve "struct_name[address].field_name" to the field's address
    output = out.output_code()

    struct = defs.get_struct(tokens[0])
    
    if len(tokens) < 4 or tokens[1] != "[":
        utl.say_error("Missing brackets in struct access", correct_syntax = "struct_name[address].field_name")

    # find the closing bracket and send to RPN calculator

    open_brackets = 1
    end = 1

    for i, token in enumerate(tokens[2:]):
        if token == '[':
            open_brackets += 1
        elif token == ']':
            open_brackets -= 1
            if open_brackets == 0:
                end += i + 1
                break
    else:
        utl.say_error("Unclosed brackets in struct access", correct_syntax = "struct_name[address].field_name")

    output.atend(op.calculate_rpn(tokens[2:end]))

    if tokens[end + 1] != ".":
        utl.say_error("Missing dot in struct access", correct_syntax = "struct_name[address].field_name")

    field = struct.get_field(tokens[end + 2])

    if field is None:
        utl.say_error(f"Struct {struct.name} has no field named {tokens[end + 2]}")

    if field.offset != 0:
        output.add("add",
                (2, 0), (1, utl.to_u16(field.offset)))

    return (output, end + 3)

def call_func(f: defs.func, tokens: list):
    args = toks.split_func_args(tokens)

    if not f.is_vaargs and len(args) != f.argc:
        utl.say_error(f"Wrong number of arguments for function {f.name}", correct_syntax = f"{f.name}({', '.join(['var' + str(i + 1) for i in range(f.argc)])})")

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
