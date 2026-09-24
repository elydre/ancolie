import compiler.utils as utl

class opcode:
    def __init__(self, name, opcode, argc):
        self.name = name
        self.opcode = opcode
        self.argc = argc

class variable:
    def __init__(self, name, ptrlvl, offset_or_addr = -1, scope = None, is_static = False, is_func_arg = False):
        self.name = name
        self.ptrlvl = ptrlvl # number of [] at declaration (actually unused)
        self.is_static = is_static
        self.is_func_arg = is_func_arg

        if scope is None:
            scope = CURRENT_SCOPE

        if offset_or_addr == -1:
            if is_static:
                utl.say_error(f"Static variable {name} must have an address", internal=True)
            if scope in LOCAL_VARS.keys() and LOCAL_VARS[scope]:
                offset_or_addr = LOCAL_VARS[scope][-1].offset + 1
            else:
                offset_or_addr = 1

        self.scope = scope

        if is_static:
            self.addr = offset_or_addr
            self.offset = None
        else:
            self.offset = offset_or_addr
            self.addr = None

    def add(self):
        if self.is_static:
            if self.scope not in STATIC_VARS:
                STATIC_VARS[self.scope] = []
            STATIC_VARS[self.scope].append(self)
        else:
            if self.scope not in LOCAL_VARS:
                LOCAL_VARS[self.scope] = []
            LOCAL_VARS[self.scope].append(self)

class func:
    def __init__(self, name, argc, does_return = True, is_builtin = False, blt_handler = None, no_rpn = False, is_vaargs = False, opcodes = None):
        self.name = name
        self.argc = argc
        self.does_return = does_return
        self.is_builtin = is_builtin
        self.is_vaargs = is_vaargs

        self.blt_handler = blt_handler  # function to call if builtin
        self.no_rpn = no_rpn            # illegal use in RPN (alloca)
        self.opcodes = opcodes          # compiled user code if not a builtin

    def add(self):
        ALL_FUNCS.append(self)

class struct:
    class struct_field:
        def __init__(self, name, ptrlvl, offset):
            self.name = name
            self.ptrlvl = ptrlvl
            self.offset = offset

    def __init__(self, name):
        self.name = name
        self.fields = []

    def add_field(self, name, ptrlvl):
        self.fields.append(struct.struct_field(name, ptrlvl, self.get_size()))

    def get_field(self, name):
        if not any(e.name == name for e in self.fields):
            return None

        return next(e for e in self.fields if e.name == name)

    def get_size(self):
        return len(self.fields)

    def add(self):
        ALL_STRUCTS.append(self)


def is_opcode(s):
    return s in [e.name for e in OPCODES]

def get_opcode(name):
    for e in OPCODES:
        if e.name == name:
            return e
    utl.say_error(f"Unknown opcode: {name}", internal=True)


def is_variable(s, scope = None):
    if scope is None:
        scope = CURRENT_SCOPE

    if scope in STATIC_VARS.keys() and s in [e.name for e in STATIC_VARS[scope]]:
        return True
    if scope in LOCAL_VARS.keys() and s in [e.name for e in LOCAL_VARS[scope]]:
        return True
    if "global" in STATIC_VARS.keys() and s in [e.name for e in STATIC_VARS["global"]]:
        return True
    return False

def get_variable(s, scope = None):
    if scope is None:
        scope = CURRENT_SCOPE

    if scope in STATIC_VARS.keys() and s in [e.name for e in STATIC_VARS[scope]]:
        return next(e for e in STATIC_VARS[scope] if e.name == s)
    if scope in LOCAL_VARS.keys() and s in [e.name for e in LOCAL_VARS[scope]]:
        return next(e for e in LOCAL_VARS[scope] if e.name == s)
    if "global" in STATIC_VARS.keys() and s in [e.name for e in STATIC_VARS["global"]]:
        return next(e for e in STATIC_VARS["global"] if e.name == s)

    utl.say_error(f"Unknown variable: {s}")


def is_func(s):
    return s in [e.name for e in ALL_FUNCS]

def get_func(s):
    if not is_func(s):
        utl.say_error(f"Unknown function: {s}")

    return next(e for e in ALL_FUNCS if e.name == s)


def is_struct(s):
    return s in [e.name for e in ALL_STRUCTS]

def get_struct(s):
    if not is_struct(s):
        utl.say_error(f"Unknown struct: {s}")

    return next(e for e in ALL_STRUCTS if e.name == s)


OPCODES = [
    opcode("nop",    0x00, 0),
    opcode("mov",    0x01, 2),
    opcode("push",   0x02, 1),
    opcode("pop",    0x03, 1),
    opcode("sub",    0x04, 2),
    opcode("add",    0x05, 2),
    opcode("mul",    0x06, 2),
    opcode("div",    0x07, 2),
    opcode("mod",    0x08, 2),
    opcode("eq",     0x09, 2),
    opcode("neq",    0x0A, 2),
    opcode("lt",     0x0B, 2),
    opcode("gt",     0x0C, 2),
    opcode("lte",    0x0D, 2),
    opcode("gte",    0x0E, 2),
    opcode("and",    0x0F, 2),
    opcode("band",   0x10, 2),
    opcode("bor",    0x11, 2),
    opcode("jmp",    0x12, 2),
    opcode("jmpr",   0x13, 2),
    opcode("out",    0x14, 2),
    opcode("in",     0x15, 2),
    opcode("ssp",    0x16, 1),
    opcode("sup",    0x17, 1),
    opcode("mss",    0x18, 4),
    opcode("pushs",  0x19, 2),
    opcode("pops",   0x1A, 2),
    opcode("memset", 0x1B, 3),
    opcode("memmov", 0x1C, 3),
    opcode("hlt",    0xFF, 0),
]

MEMORY_SIZE = 65536 - (80 * 25)

MAGIC_NUMBER = 0xF057
ARCH_VERSION = 0x0100

CHARS_SPE = [",", ".", "(", ")", ":", "=", "{", "}", "[", "]", "&", "$", "!", "//", "' '", "#", "++", "--"]
CHARS_OPR = ["+", "-", "*", "/", "%", ">>", "<<", "==", "!=", "<", ">", "<=", ">=", "&&", "|"]
CHARS_SPE += CHARS_OPR

KEYWORDS = ["if", "elif", "else", "while", "func", "vafunc", "return", "break", "continue", "for", "sub", "asm", "struct"]

NEW_VAR = ":"
NEW_VAR_STATIC = "$"

COND_RES_ADDR   = MEMORY_SIZE - 1
FUNC_RET_ADDR   = MEMORY_SIZE - 2
STACK_DEBUT_PTR = MEMORY_SIZE - 3
STACK_PTR       = MEMORY_SIZE - 4

STATIC_ADDR     = MEMORY_SIZE - 4 # will be decremented as static variables / strings are added
STATIC_BYTES    = bytearray()

CURRENT_LNO = 0
CURRENT_SCOPE = "global"

EXTRAERR = False
VERBOSE = False

LOCAL_VARS = {}
STATIC_VARS = {}

ALL_FUNCS = []
ALL_STRUCTS = []

DATA_SEQ = []
