import compiler.preproc as preproc
import compiler.builtin as blt
import compiler.tokens as toks
import compiler.config as conf
import compiler.output as out
import compiler.utils as utl
import compiler.defs as defs
import compiler.op as op


def compile_assembly(lines):
    output = out.output_code()

    asm_id = utl.get_new_userasm()

    for line in lines:
        defs.CURRENT_LNO, tokens = line

        if len(tokens) < 1:
            continue

        # label definition
        if len(tokens) == 2 and tokens[1] == ":":
            label = f"{asm_id}_{tokens[0]}"
            if not utl.is_valid_name(tokens[0]):
                utl.say_error(f"Invalid label name: {tokens[0]}")
            if output.does_label_exist(label):
                utl.say_error(f"Label already exists: {tokens[0]}")
            output.add_label(label)
            continue

        # check if the first token is a valid opcode
        if not defs.is_opcode(tokens[0]):
            utl.say_error(f"Unknown opcode: {tokens[0]}")

        opcode = defs.get_opcode(tokens[0])
        args = toks.split_func_args(tokens[1:])

        if len(args) != opcode.argc:
            utl.say_error(f"Opcode {opcode.name} expects {opcode.argc} arguments, got {len(args)}")

        gen = []
        label = None

        for e in args:
            if len(e) == 1 and utl.is_number(e[0]):
                gen.append((1, utl.to_number(e[0])))
            elif len(e) == 1 and opcode.name == "jmp":
                label = f"{asm_id}_{e[0]}"
                if output.does_label_exist(label):
                    continue
                utl.say_error(f"Label {e[0]} does not exist")
            elif len(e) == 2 and e[0] == "&" and defs.is_variable(e[1]):
                v = defs.get_variable(e[1])
                if v.is_static:
                    gen.append((0, v.addr))
                else:
                    gen.append((3, utl.to_u16(-v.offset)))
            elif len(e) == 3 and e[0] == "[" and utl.is_number(e[1]) and e[2] == "]":
                gen.append((0, utl.to_number(e[1])))
            elif len(e) == 3 and e[0] == "[" and e[1] in ["sp", "up"] and e[2] == "]":
                gen.append((2 if e[1] == "sp" else 3, 0))
            elif len(e) == 5 and e[0] == "[" and e[1] in ["sp", "up"] and e[2] in ["+", "-"] and utl.is_number(e[3]) and e[4] == "]":
                gen.append((2 if e[1] == "sp" else 3, utl.to_u16(utl.to_number(e[3]) * (1 if e[2] == "+" else -1))))
            else:
                utl.say_error("Bad argument syntax", correct_syntax = "123 OR &var_name OR [123] OR [sp+123] OR [up+123]")

        if label is None:
            output.add(opcode.name, *gen)
            continue

        if len(gen) != 1:
            utl.say_error("Unexpected number of arguments for jump", internal=True)

        output.add_goto(label, *gen)

    output.set_dont_optimize()

    return output


def compile_lines(lines: list, labels: tuple = None, tree: list = [], new_scope: str = None):
    output = out.output_code()

    if new_scope is not None:
        old_scope = defs.CURRENT_SCOPE
        defs.CURRENT_SCOPE = new_scope
        if new_scope not in defs.LOCAL_VARS:
            defs.LOCAL_VARS[new_scope] = []

    current_line = 0
    size = len(lines)

    while current_line < size:
        sub_output, to_skip = compile_line(lines[current_line:], labels, tree)
        output.atend(sub_output)
        current_line += to_skip

    if new_scope is not None:
        variable_decl = out.output_code()
        variable_decl.add_comment(f"\n--- begin of {new_scope} ---")
        v_count = len([v for v in defs.LOCAL_VARS[new_scope] if not (v.is_static or v.is_func_arg)])
        if v_count == 1:
            variable_decl.add("push", (1, 0))
        elif v_count > 1:
            variable_decl.add("sub", (0, defs.STACK_PTR), (1, v_count))
        output.atdebut(variable_decl)
        defs.CURRENT_SCOPE = old_scope

    return output


def compile_line(lines: list, labels: tuple, tree: list):
    defs.CURRENT_LNO, tokens = lines[0]

    output = out.output_code()
    output.add_comment(f"\n{defs.CURRENT_LNO[0]}:{defs.CURRENT_LNO[1]:03}  {' '.join(tokens)}")

    utl.verbose(f"{defs.CURRENT_LNO[0]}:{defs.CURRENT_LNO[1]:03}  {' '.join(tokens)}")

    new_tree = tree + [tokens[0]]

    if tokens[0] in (conf.NEW_VAR, conf.NEW_VAR_STATIC):
        def_char = tokens[0]
        tokens = tokens[1:]

        while len(tokens) > 0:
            ptrlvl = 0
            while tokens[ptrlvl] == '[':
                ptrlvl += 1

            end_brackets = 1 + ptrlvl * 2
            if len(tokens) < end_brackets:
                utl.say_error("Bad pointer declaration", correct_syntax = f"{def_char} [ptr_name]")

            # check for closing brackets
            if ptrlvl and (ptrlvl * ']' != ''.join(tokens[1 + ptrlvl:1 + ptrlvl * 2])):
                utl.say_error("Bad pointer declaration", correct_syntax = f"{def_char} [ptr_name]")

            var_name = tokens[ptrlvl]

            # check if the variable already exists
            if defs.is_variable(var_name):
                utl.say_error(f"Variable already exists: {tokens[ptrlvl]}")

            if not utl.is_valid_name(var_name):
                utl.say_error(f"Invalid variable name: {tokens[ptrlvl]}")

            if def_char == conf.NEW_VAR:
                v = defs.variable(var_name, ptrlvl)
                v.add()
                # variable will be automaticly added to stack by compile_lines

                if len(tokens) > end_brackets + 1 and tokens[end_brackets] == '=':
                    fast_assignment = op.fast_assign_var(v, tokens[end_brackets + 1:])

                    if fast_assignment:
                        output.atend(fast_assignment)
                        break

                    # reverse polish notation (RPN) expression
                    output.atend(op.calculate_expr(tokens[end_brackets + 1:]))

                    # move the result from the stack to the variable's memory location
                    output.add("pop", (3, utl.to_u16(-v.offset)))
                    break

            else:
                if len(tokens) > end_brackets:
                    if tokens[end_brackets] != '=' or len(tokens) != end_brackets + 2 or not utl.is_number(tokens[end_brackets + 1]):
                        utl.say_error(f"Bad static variable declaration, only const expected", correct_syntax = f"{tokens[0]} = 123")
                    val = utl.to_number(tokens[end_brackets + 1])
                else:
                    val = None

                addr = out.push_static_data([val if val else 0])
                defs.variable(var_name, ptrlvl, addr, is_static = True).add()

                if val is not None:
                    break

            tokens = tokens[end_brackets:]

    elif defs.is_variable(tokens[0]):
        if len(tokens) == 2 and tokens[1] in ("++", "--"):
            v = defs.get_variable(tokens[0])

            output.add("add" if tokens[1] == "++" else "sub",
                    (0, v.addr) if v.is_static else (3, utl.to_u16(-v.offset)), (1, 1))

            return (output, 1)

        elif len(tokens) < 3 or tokens[1] != '=':
            utl.say_error("Bad variable assignment", correct_syntax = "var_name = 123")

        v = defs.get_variable(tokens[0])

        fast_assignment = op.fast_assign_var(v, tokens[2:])

        if fast_assignment:
            output.atend(fast_assignment)
        else:
            # reverse polish notation (RPN) expression
            output.atend(op.calculate_expr(tokens[2:]))

            # move the result from the stack to the variable's memory location
            if v.is_static:
                output.add("pop", (0, v.addr))
            else:
                output.add("pop", (3, utl.to_u16(-v.offset)))

    elif tokens[0] == "[":
        o, end = op.load_ptraddr(tokens)

        if len(tokens) < end + 2 or tokens[end] != '=':
            utl.say_error("Bad pointer assignment", correct_syntax = "[ptr_name] = 123")

        output.atend(o)

        # reverse polish notation (RPN) expression
        output.atend(op.calculate_expr(tokens[end + 1:]))

        # pop the result from the stack to the pointer's memory location
        output.add("pops", (2, 1), (1, 0))

        # pop the pointer's address
        output.add("pop", (1, 0))

    elif defs.is_func(tokens[0]):
        f = defs.get_func(tokens[0])
        if len(tokens) < 3 or tokens[1] != '(' or tokens[-1] != ')':
            utl.say_error("Bad syntax on function call", correct_syntax = f"{f.name}({', '.join(['var' + str(i + 1) for i in range(f.argc)])})")

        output.atend(op.call_func(f, tokens[2:-1]))

    elif defs.is_struct(tokens[0]):
        o, end = op.load_fieldaddr(tokens)

        if len(tokens) < end + 2 or tokens[end] != '=':
            utl.say_error("Bad struct field assignment", correct_syntax = "struct_name[address].field_name = 123")

        output.atend(o)

        # reverse polish notation (RPN) expression
        output.atend(op.calculate_expr(tokens[end + 1:]))

        # pop the result from the stack to the pointer's memory location
        output.add("pops", (2, 1), (1, 0))

        # pop the pointer's address
        output.add("pop", (1, 0))

    elif tokens[0] == "if":
        if len(tokens) < 2:
            utl.say_error("Bad syntax", correct_syntax = "if var == 0")

        # reverse polish notation (RPN) expression
        output.atend(op.calculate_expr(tokens[1:]))

        # pop the result from the stack to the conditional result memory location
        output.add("pop",
                (0, defs.COND_RES_ADDR))

        # compile the lines inside the if block
        closing_line = toks.locate_braces(lines)
        inner_output = compile_lines(lines[2:closing_line], labels, new_tree)

        fin_label = utl.get_new_label()
        next_label = utl.get_new_label()

        # add a jump instruction to skip the if block if the condition is false
        output.add_goto(
            next_label,
            (0, defs.COND_RES_ADDR)) # jump if the condition is false

        output.atend(inner_output)

        # check if there is an elif or else block after the if block
        next_tokens = None
        while closing_line + 1 < len(lines) and lines[closing_line + 1][1][0] in ("elif", "else"):
            defs.CURRENT_LNO, next_tokens = lines[closing_line + 1]
            
            output.add_goto(
                fin_label, (1, 0)) # unconditional jump to the end of the if block
            output.add_label(next_label)

            if next_tokens[0] == "else":
                if len(next_tokens) != 1:
                    utl.say_error(f"Unexpected token '{next_tokens[1]}' after else", correct_syntax = "else " + "{ ... }")
                # compile the lines inside the else block
                tmp = toks.locate_braces(lines, closing_line + 1)
                inner_output = compile_lines(lines[closing_line + 3:tmp], labels, tree + ["else"])
                closing_line = tmp

                output.atend(inner_output)
                break

            # elif block

            if len(next_tokens) < 2:
                utl.say_error("Bad syntax", correct_syntax = "elif var == 0")

            # reverse polish notation (RPN) expression
            output.atend(op.calculate_expr(next_tokens[1:]))

            # pop the result from the stack to the conditional result memory location
            output.add("pop",
                (0, defs.COND_RES_ADDR))

            # compile the lines inside the elif block
            tmp = toks.locate_braces(lines, closing_line + 1)
            inner_output = compile_lines(lines[closing_line + 3:tmp], labels, tree + ["elif"])
            closing_line = tmp

            if closing_line + 1 < len(lines) and lines[closing_line + 1][1][0] in ("elif", "else"):
                next_label = utl.get_new_label()
            else:
                next_label = fin_label

            # add a jump instruction to skip the elif block if the condition is false
            output.add_goto(
                    next_label,
                    (0, defs.COND_RES_ADDR)) # jump if the condition is false

            output.atend(inner_output)


        if next_tokens is None:
            output.add_label(next_label)
        else:
            output.add_label(fin_label)

        return (output, closing_line + 1) # return the number of lines to skip

    elif tokens[0] == "while":
        if len(tokens) < 2:
            utl.say_error("Bad syntax", correct_syntax = "while var < 10")

        debut_label = utl.get_new_label()
        fin_label   = utl.get_new_label()

        # reverse polish notation (RPN) expression
        output.add_label(debut_label)
        output.atend(op.calculate_expr(tokens[1:]))

        # pop the result from the stack to the conditional result memory location
        output.add("pop",
                (0, defs.COND_RES_ADDR))

        # compile the lines inside the while block
        closing_line = toks.locate_braces(lines)
        inner_output = compile_lines(lines[2:closing_line], (debut_label, fin_label), new_tree)

        inner_output.add_goto(
                debut_label, (1, 0)) # unconditional jump to the beginning of the while loop

        output.add_goto(
                fin_label, (0, defs.COND_RES_ADDR)) # jump if the condition is false

        output.atend(inner_output)
        output.add_label(fin_label)

        return (output, closing_line + 1)

    elif tokens[0] == "for":
        # Syntax: for var (debut, fin)
        # debut and fin can be any expression that evaluates to an integer
        if len(tokens) < 5 or tokens[2] != '(' or tokens[-1] != ')':
            utl.say_error("Bad syntax in for loop", correct_syntax = "for var (0, 10)")

        if not defs.is_variable(tokens[1]):
            utl.say_error(f"For loop variable must be a declared variable: {tokens[1]}", correct_syntax = ":var ; for var (0, 10)")

        v = defs.get_variable(tokens[1])

        if v.is_static:
            utl.say_error(f"For loop variable must be a local variable: {tokens[1]}", correct_syntax = ":var ; for var (0, 10)")

        args = toks.split_func_args(tokens[3:-1])

        if len(args) not in (1, 2, 3):
            utl.say_error("Expected 1, 2 or 3 arguments for for loop", correct_syntax = "for var (debut) OR for var (debut, fin) OR for var (debut, fin, step)")

        # init the loop variable with the debut value
        fast_assignment = op.fast_assign_var(v, args[0])

        if fast_assignment:
            output.atend(fast_assignment)
        else:
            output.atend(op.calculate_expr(args[0]))

            # move the result from the stack to the variable's memory location
            output.add("pop",
                    (3, utl.to_u16(-v.offset)))

        debut_label = utl.get_new_label()
        next_label  = utl.get_new_label()
        fin_label   = utl.get_new_label()

        if len(args) == 3:
            # push the loop step value onto the stack
            output.atend(op.calculate_expr(args[2]))

        if len(args) >= 2:
            # push the loop fin value onto the stack
            output.atend(op.calculate_expr(args[1]))

        output.add_label(debut_label)

        if len(args) >= 2:
            # compare the loop variable with the fin value
            output.add("mov",
                    (0, defs.COND_RES_ADDR), (3, utl.to_u16(-v.offset)))
            output.add("lt",
                    (0, defs.COND_RES_ADDR), (2, 0))

            output.add_goto(
                    fin_label, (0, defs.COND_RES_ADDR)) # jump if the condition is false


        # compile the lines inside the for block
        closing_line = toks.locate_braces(lines)
        inner_output = compile_lines(lines[2:closing_line], (next_label, fin_label), new_tree)

        output.atend(inner_output)
        output.add_comment(f"\nIncrement the loop variable {v.name}")

        output.add_label(next_label)
        if len(args) == 3:
            output.add("add", (3, utl.to_u16(-v.offset)), (2, 1))
        else:
            output.add("add", (3, utl.to_u16(-v.offset)), (1, 1))

        output.add_goto(
                debut_label, (1, 0)) # unconditional jump to the beginning of the for loop

        output.add_label(fin_label)

        if len(args) == 2:
            output.add("pop", (1, 0)) # pop the fin value from the stack
        elif len(args) == 3:
            output.add("add", (0, defs.STACK_PTR), (1, 2)) # pop the step and fin values from the stack

        return (output, closing_line + 1)

    elif tokens[0] in ("func", "vafunc"):
        if tree != []:
            utl.say_error("Function declaration not allowed inside a block")

        if len(tokens) < 4 or tokens[2] != '(' or tokens[-1] != ')':
            utl.say_error("Bad syntax", correct_syntax = f"{tokens[0]} func_name(arg1, arg2)")

        if not utl.is_valid_name(tokens[1]):
            utl.say_error(f"Invalid function name: {tokens[1]}")

        if defs.is_func(tokens[1]):
            utl.say_error(f"Function already exists: {tokens[1]}")

        args = toks.split_func_args(tokens[3:-1])
        new_scope = f"func_{tokens[1]}"

        for i, e in enumerate(args):
            ptrlvl = 0
            while e[ptrlvl] == '[':
                ptrlvl += 1

            end_brackets = 1 + ptrlvl * 2
            if len(e) != end_brackets:
                utl.say_error("Bad syntax in arguments", correct_syntax = f"func_name(arg1, arg2)")

            # check for closing brackets
            if ptrlvl:
                if (ptrlvl * ']' != ''.join(e[1 + ptrlvl:1 + ptrlvl * 2])):
                    utl.say_error("Bad pointer declaration in arguments", correct_syntax = f"func_name([arg1], arg2)")
                e = [e[ptrlvl]]

            if not utl.is_valid_name(e[0]):
                utl.say_error(f"Invalid argument name: {e[0]}")
            defs.variable(e[0], 0, i + 1, is_func_arg = True, scope = new_scope).add()

        if tokens[0] == "vafunc" and len(args) != 2:
            utl.say_error("Variable argument function must have 2 arguments (arg count and arg pointer)", correct_syntax = "vafunc func_name(argc, argp)")

        # compile the lines inside the function block
        closing_line = toks.locate_braces(lines)
        func_lines = lines[2:closing_line]

        # check if the function has a return statement, if not add a return at the end
        if func_lines[-1][1][0] != "return":
            func_lines.append((func_lines[-1][0], ["return"]))

        f = defs.func(tokens[1], len(args), is_vaargs = (tokens[0] == "vafunc"))
        f.add()

        inner_output = out.output_code()
        inner_output.add_label(new_scope)
        inner_output.atend(compile_lines(func_lines, new_scope = new_scope, tree = new_tree))

        f.opcodes = inner_output

        return (output, closing_line + 1)

    elif tokens[0] == "sub":
        if len(tokens) != 1:
            utl.say_error("Nothing expected after sub keyword", correct_syntax = "sub { ... }")

        # compile the lines inside the sub block
        closing_line = toks.locate_braces(lines)

        sub_count = tree.count("sub") + 1
        var_name = f"sub{sub_count}"

        if not defs.is_variable(var_name):
            defs.variable(var_name, 0).add()
        var_offset = defs.get_variable(var_name).offset

        # backup the stack pointer to the variable
        output.add("mov",
                   (3, utl.to_u16(-var_offset)), (0, defs.STACK_PTR))

        output.atend(compile_lines(lines[2:closing_line], labels, new_tree))

        # restore the stack pointer from the variable
        output.add("mov",
                   (0, defs.STACK_PTR), (3, utl.to_u16(-var_offset)))

        return (output, closing_line + 1)

    elif tokens[0] == "asm":
        if len(tokens) != 1:
            utl.say_error("Nothing expected after asm keyword", correct_syntax = "asm { ... }")

        # compile the lines inside the sub block
        closing_line = toks.locate_braces(lines)

        output.atend(compile_assembly(lines[2:closing_line]))

        return (output, closing_line + 1)

    elif tokens[0] == "struct":
        if len(tokens) < 2:
            utl.say_error("Bad syntax", correct_syntax = "struct name { ... }")

        if not utl.is_valid_name(tokens[1]):
            utl.say_error(f"Invalid struct name: {tokens[1]}")

        if defs.is_struct(tokens[1]):
            utl.say_error(f"Struct already exists: {tokens[1]}")

        # interpret the lines inside the struct block as variable declarations
        closing_line = toks.locate_braces(lines)
        struct_lines = lines[2:closing_line]

        struct = defs.struct(tokens[1])
        struct.add()

        for line in struct_lines:
            defs.CURRENT_LNO, tokens = line

            if len(tokens) < 2 or tokens[0] != conf.NEW_VAR:
                utl.say_error("Bad field declaration in struct", correct_syntax = f"struct {tokens[1]} {{ {conf.NEW_VAR} field_name }}")

            tokens = tokens[1:]

            while len(tokens) > 0:
                ptrlvl = 0
                while tokens[ptrlvl] == '[':
                    ptrlvl += 1

                end_brackets = 1 + ptrlvl * 2
                if len(tokens) < end_brackets:
                    utl.say_error("Bad pointer declaration", correct_syntax = f"{def_char} [ptr_name]")

                # check for closing brackets
                if ptrlvl and (ptrlvl * ']' != ''.join(tokens[1 + ptrlvl:2 + ptrlvl * 2])):
                    utl.say_error("Bad pointer declaration", correct_syntax = f"{def_char} [ptr_name]")

                field_name = tokens[ptrlvl]

                if not utl.is_valid_name(field_name):
                    utl.say_error(f"Invalid field name: {field_name}")

                if struct.get_field(field_name):
                    utl.say_error(f"Field already exists in struct {struct.name}: {field_name}")

                struct.add_field(field_name, ptrlvl)
                tokens = tokens[end_brackets:]

        return (output, closing_line + 1)

    elif tokens[0] == "switch":
        if len(tokens) < 2:
            utl.say_error("Bad syntax", correct_syntax = "switch var")

        # calculate the expression to switch on
        val = op.calculate_expr(tokens[1:])

        end_label = utl.get_new_label()
        default_label = end_label

        # find the case and default blocks
        closing_line = toks.locate_braces(lines)
        case_lines = lines[2:closing_line]

        current_line = 0
        size = len(case_lines)

        case_labels = {} # value: label

        sub_output = out.output_code()

        while current_line < size:
            defs.CURRENT_LNO, tokens = case_lines[current_line]

            if len(tokens) == 0:
                current_line += 1
                continue

            if tokens[0] == "case":
                args = toks.split_func_args(tokens[1:])
                case_label = utl.get_new_label()

                for arg in args:
                    if len(arg) != 1:
                        utl.say_error("Bad syntax", correct_syntax = "case 123, 456 { ... }")
                    arg = arg[0]

                    if not (utl.is_number(arg) or utl.is_char(arg)):
                        utl.say_error(f"Case value must be a number or a character, got '{arg}'")

                    case_value = utl.to_number(arg)

                    if case_value > conf.MAX_CASE_VAL:
                        utl.say_error(f"Case value exceeds maximum allowed: {case_value} > {conf.MAX_CASE_VAL}")

                    if case_value in case_labels:
                        utl.say_error(f"Duplicate case value: {case_value}")

                    case_labels[case_value] = case_label

                # compile the lines inside the case block
                closing_case_line = toks.locate_braces(case_lines, current_line)
                sub_output.add_label(case_label)
                sub_output.atend(compile_lines(case_lines[current_line + 2:closing_case_line], (case_label, end_label), new_tree))

                # add unconditional jump to the end of the switch block
                sub_output.add_goto(end_label, (1, 0))

                current_line = closing_case_line + 1

            elif tokens[0] == "default":
                if len(tokens) != 1:
                    utl.say_error("Nothing expected after default keyword", correct_syntax = "default { ... }")

                if default_label != end_label:
                    utl.say_error("Duplicate default block")

                default_label = utl.get_new_label()

                # compile the lines inside the default block
                closing_default_line = toks.locate_braces(case_lines, current_line)
                sub_output.add_label(default_label)
                sub_output.atend(compile_lines(case_lines[current_line + 2:closing_default_line], (default_label, end_label), new_tree))

                current_line = closing_default_line + 1

        if len(case_labels) == 0:
            utl.say_error("Switch statement must have at least one case")

        # fill the table of case values and labels
        case_table = [default_label] * (max(case_labels.keys()) + 1)
        for value, label in case_labels.items():
            case_table[value] = label

        tab_addr = out.push_static_labels(case_table)

        # compare the switch value with the case values
        output.atend(val)

        # check if the value is in range
        output.add("pop", (0, defs.LLC_TEMP_ADDR))

        output.add("mov", (0, defs.COND_RES_ADDR), (0, defs.LLC_TEMP_ADDR))
        output.add("lt", (0, defs.COND_RES_ADDR), (1, len(case_table)))
        output.add_goto(default_label, (0, defs.COND_RES_ADDR))

        # get the address of the case label from the table
        output.add("load", (0, defs.LLC_TEMP_ADDR), (1, tab_addr))
        output.add("jmp", (0, defs.LLC_TEMP_ADDR), (1, 0)) # jump to the case label

        output.atend(sub_output)

        output.add_label(end_label)

        return (output, closing_line + 1)

    elif tokens[0] == "break":
        if not labels:
            utl.say_error(f"Unexpected break statement outside of a loop")

        # add an unconditional jump to the end of the loop
        output.add_goto(labels[1], (1, 0))

    elif tokens[0] == "continue":
        if not labels:
            utl.say_error(f"Unexpected continue statement outside of a loop")

        # add an unconditional jump to the beginning of the loop
        output.add_goto(labels[0], (1, 0))

    elif tokens[0] == "return":
        if defs.CURRENT_SCOPE == "global":
            utl.say_error(f"Unexpected return statement outside of a function")

        if len(tokens) > 1:
            # reverse polish notation (RPN) expression
            output.atend(op.calculate_expr(tokens[1:]))

            # move the result from the stack to the return value memory location
            output.add("pop",
                    (0, defs.FUNC_RET_ADDR))
        else:
            # set return value to 0
            output.add("mov",
                    (0, defs.FUNC_RET_ADDR), (1, 0))

        # go to the beginning of the substack
        output.add("mov",
                (0, defs.STACK_PTR), (0, defs.STACK_DEBUT_PTR))

        # restore stack debut and pc values
        output.add("pop",
                (0, defs.STACK_DEBUT_PTR))
        output.add("jmp",
                (2, 0), (1, 0))

    elif tokens[0] in ("else", "elif"):
        utl.say_error(f"Unexpected {tokens[0]} statement outside of an if block", correct_syntax = "if var == 0 { ... } elif var == 1 { ... } else { ... }")

    elif tokens[0] in ("case", "default"):
        utl.say_error(f"Unexpected {tokens[0]} statement outside of a switch block", correct_syntax = "switch var { case 1 { ... } case 2 { ... } default { ... } }")

    elif tokens[0] in defs.CHARS_SPE:
        utl.say_error(f"Unexpected character: '{tokens[0]}'")

    else:
        utl.say_error(f"Unknown word: {tokens[0]}")

    return (output, 1)


def compile(lines: str, path: str = None, use_header: bool = False):
    blt.add_builtin_functions()

    tokens_lines = toks.tokenize_lines(lines, path)

    if use_header:
        tokens_lines = toks.tokenize_lines(conf.LLC_HEADER, "(llc_header)") + tokens_lines

    tokens_lines = preproc.preprocess(tokens_lines, path if path else "")

    output = out.output_code()
    output.atend(compile_lines(tokens_lines, new_scope="global"))
    output.atend(op.fini())

    for f in defs.ALL_FUNCS:
        if f.is_builtin:
            continue
        if f.opcodes is None:
            utl.say_error(f"Function {f.name} has no opcodes")
        output.atend(f.opcodes)

    output.atdebut(op.init())

    return output
