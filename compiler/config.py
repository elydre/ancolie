import compiler.defs as defs

NEW_VAR = ":"
NEW_VAR_STATIC = "$"

LLC_HEADER = f"""
#define _lCOMPILER "llc"

#define _lSP {defs.STACK_PTR}
#define _lSCREEN {defs.MEMORY_SIZE}

#define _get_sp() [_lSP]
"""
