import compiler.defs as defs

LLC_VERSION = "1.1"

MAGIC_NUMBER = 0xF057
ARCH_VERSION = 0x0110

MAX_CASE_VAL = 127

NEW_VAR = ":"
NEW_VAR_STATIC = "$"

LLC_HEADER = f"""
#define _lCOMPILER "llc {LLC_VERSION}"
#define _lARCH {ARCH_VERSION}

#define _lSP {defs.STACK_PTR}
#define _lSCREEN {defs.MEMORY_SIZE}

#define NULL 0
#define INTMAX 0xFFFF
"""
