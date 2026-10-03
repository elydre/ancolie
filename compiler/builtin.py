import compiler.output as out
import compiler.utils as utl
import compiler.defs as defs
import compiler.op as op

def blt_rpn(args: list):
    output = out.output_code()

    output.atend(op.calculate_expr(args[0], is_infix=False))
    output.add("pop", (0, defs.FUNC_RET_ADDR))

    return output

def blt_alloca(args: list):
    output = out.output_code()
    # calculate the requested size in bytes
    output.atend(op.calculate_expr(args[0]))

    # add the requested size to the stack pointer
    output.add("sub",
            (0, defs.STACK_PTR),
            (2, 0))

    # pop calculated size from the stack
    # (this is not the right address, but we just have to remove 1 value from the stack)
    output.add("pop",
            (1, 0))

    # copy the current stack pointer value to return memory location
    output.add("mov",
            (0, defs.FUNC_RET_ADDR),
            (0, defs.STACK_PTR))

    return output

def blt_array(args: list):
    output = out.output_code()

    # push all arguments to the stack
    for arg in args[::-1]:
        output.atend(op.calculate_expr(arg))

    output.add("mov",
            (0, defs.FUNC_RET_ADDR),
            (0, defs.STACK_PTR))

    return output

def blt_sizeof(args: list):
    output = out.output_code()

    if len(args[0]) != 1 or not defs.is_struct(args[0][0]):
        utl.say_error(f"sizeof() expects a struct name as argument")

    struct = defs.get_struct(args[0][0])

    output.add("mov",
            (0, defs.FUNC_RET_ADDR),
            (1, struct.get_size()))

    return output

def blt_out(args: list):
    output = out.output_code()

    output.atend(op.calculate_expr(args[0]))
    output.atend(op.calculate_expr(args[1]))

    output.add("out", (2, 1), (2, 0))

    output.add("pop", (1, 0))
    output.add("pop", (1, 0))

    return output

def blt_in(args: list):
    output = out.output_code()

    output.atend(op.calculate_expr(args[0]))
    output.add("in", (0, defs.FUNC_RET_ADDR), (2, 0))
    output.add("pop", (1, 0))

    return output

def blt_dump(args: list):
    output = out.output_code()

    output.atend(op.calculate_expr(args[0]))

    output.add("out", (1, 0x1001), (2, 0))

    output.add("pop", (1, 0))

    return output

def blt_memset(args: list):
    output = out.output_code()

    output.atend(op.calculate_expr(args[0]))
    output.atend(op.calculate_expr(args[1]))
    output.atend(op.calculate_expr(args[2]))

    output.add("memset", (2, 2), (2, 1), (2, 0))

    output.add("pop", (1, 0))
    output.add("pop", (1, 0))
    output.add("pop", (1, 0))

    return output

def blt_memmov(args: list):
    output = out.output_code()

    output.atend(op.calculate_expr(args[0]))
    output.atend(op.calculate_expr(args[1]))
    output.atend(op.calculate_expr(args[2]))

    output.add("memmov", (2, 2), (2, 1), (2, 0))

    output.add("pop", (1, 0))
    output.add("pop", (1, 0))
    output.add("pop", (1, 0))

    return output


def add_builtin_functions():
    def new_builtin(name, args, does_return, func, no_rpn=False, is_vaargs=False):
        return defs.func(name, args, does_return, True, func, no_rpn, is_vaargs).add()

    new_builtin("rpn",    1, True,  blt_rpn)
    new_builtin("alloca", 1, True,  blt_alloca, no_rpn=True)
    new_builtin("array",  0, True,  blt_array, no_rpn=True, is_vaargs=True)
    new_builtin("sizeof", 1, True,  blt_sizeof)
    new_builtin("out",    2, False, blt_out)
    new_builtin("in",     1, True,  blt_in)
    new_builtin("dump",   1, False, blt_dump)
    new_builtin("memset", 3, False, blt_memset)
    new_builtin("memmov", 3, False, blt_memmov)
