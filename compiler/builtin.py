import compiler.output as out
import compiler.defs as defs
import compiler.op as op

def blt_alloca(args: list):
    output = out.output_code()
    # calculate the requested size in bytes
    output.atend(op.calculate_rpn(args[0]))

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


def blt_out(args: list):
    output = out.output_code()

    output.atend(op.calculate_rpn(args[0]))
    output.atend(op.calculate_rpn(args[1]))

    output.add("out", (2, 1), (2, 0))

    output.add("pop", (1, 0))
    output.add("pop", (1, 0))

    return output

def blt_in(args: list):
    output = out.output_code()

    output.atend(op.calculate_rpn(args[0]))
    output.add("in", (0, defs.FUNC_RET_ADDR), (2, 0))
    output.add("pop", (1, 0))

    return output

def blt_dump(args: list):
    output = out.output_code()

    output.atend(op.calculate_rpn(args[0]))

    output.add("out", (1, 0x1001), (2, 0))

    output.add("pop", (1, 0))

    return output

def blt_memset(args: list):
    output = out.output_code()

    output.atend(op.calculate_rpn(args[0]))
    output.atend(op.calculate_rpn(args[1]))
    output.atend(op.calculate_rpn(args[2]))

    output.add("memset", (2, 2), (2, 1), (2, 0))

    output.add("pop", (1, 0))
    output.add("pop", (1, 0))
    output.add("pop", (1, 0))

    return output

def blt_memmov(args: list):
    output = out.output_code()

    output.atend(op.calculate_rpn(args[0]))
    output.atend(op.calculate_rpn(args[1]))
    output.atend(op.calculate_rpn(args[2]))

    output.add("memmov", (2, 2), (2, 1), (2, 0))

    output.add("pop", (1, 0))
    output.add("pop", (1, 0))
    output.add("pop", (1, 0))

    return output

def blt_halt(args: list):
    output = out.output_code()

    output.add("hlt")

    return output

def blt_get_sp(args: list):
    output = out.output_code()

    # copy the current stack pointer value to return memory location
    output.add("mov",
            (0, defs.FUNC_RET_ADDR),
            (0, defs.STACK_PTR))

    return output

def blt_get_screen(args: list):
    output = out.output_code()

    # copy the current screen pointer value to return memory location
    output.add("mov",
            (0, defs.FUNC_RET_ADDR),
            (1, defs.MEMORY_SIZE))

    return output

def add_builtin_functions():
    defs.func("alloca",      1, True,  is_builtin=True, blt_handler = blt_alloca, no_rpn=True).add()
    defs.func("out",         2, False, is_builtin=True, blt_handler = blt_out).add()
    defs.func("in",          1, True,  is_builtin=True, blt_handler = blt_in).add()
    defs.func("dump",        1, False, is_builtin=True, blt_handler = blt_dump).add()
    defs.func("memset",      3, False, is_builtin=True, blt_handler = blt_memset).add()
    defs.func("memmov",      3, False, is_builtin=True, blt_handler = blt_memmov).add()
    defs.func("halt",        0, False, is_builtin=True, blt_handler = blt_halt).add()
    defs.func("_get_sp",     0, True,  is_builtin=True, blt_handler = blt_get_sp).add()
    defs.func("_get_screen", 0, True,  is_builtin=True, blt_handler = blt_get_screen).add()
