import compiler.utils as utl
import compiler.defs as defs


def get_static_addr(size: int, data: list = None):
    if data == None:
        data = [0] * size
    elif len(data) != size:
        utl.say_error(f"(Internal) Data size mismatch in get_static_addr\nExpected {size}, got {len(data)}")

    byte_data = bytearray()
    for d in data:
        if type(d) != int or d < 0 or d > 0xFFFF:
            utl.say_error(f"(Internal) Invalid data value in get_static_addr\nExpected int in range [0, 65535], got {d}")
        byte_data += d.to_bytes(2, byteorder='little')

    defs.STATIC_ADDR -= size
    defs.STATIC_BYTES = byte_data + defs.STATIC_BYTES

    return defs.STATIC_ADDR


class output_file:
    class section:
        TYPE_CODE = 0
        TYPE_DATA = 1

        def __init__(self, dest_addr, type, data):
            self.debut = 0
            self.size = len(data)
            self.dest_addr = dest_addr
            self.type = type
            self.data = data

    def __init__(self):
        self.sections = []

    def add_section(self, dest_addr, type, data):
        self.sections.append(self.section(dest_addr, type, data))

    def write(self, file):
        header = bytearray()
        header += defs.MAGIC_NUMBER.to_bytes(2, byteorder='little')
        header += defs.ARCH_VERSION.to_bytes(2, byteorder='little')
        header += len(self.sections).to_bytes(2, byteorder='little')

        # update debut values
        debut = 6 + len(self.sections) * 8
        for section in self.sections:
            section.debut = debut
            debut += section.size

        for section in self.sections:
            header += section.type.to_bytes(2, byteorder='little')
            header += section.debut.to_bytes(2, byteorder='little')
            header += section.size.to_bytes(2, byteorder='little')
            header += section.dest_addr.to_bytes(2, byteorder='little')

        file.write(header)

        for section in self.sections:
            file.write(section.data)


class output_code:
    class instruction:
        TYPE_COMMENT = 0
        TYPE_LABEL = 1
        TYPE_OPCODE = 2
        TYPE_GOTO = 3
        TYPE_PUSH_LABEL = 4
        TYPE_NOTSET = 5

        def __init__(self):
            self.string = ""
            self.bytes = bytearray()
            self.psize = 0
            self.type = self.TYPE_NOTSET
            self.lineno = defs.CURRENT_LNO

            self.goto_label = None
            self.goto_val = None
            self.raw_args = None

        def setcomment(self, comment):
            self.type = self.TYPE_COMMENT
            self.string = comment
            self.psize = 0
            self.bytes = bytearray()

        def setlabel(self, label):
            self.type = self.TYPE_LABEL
            self.string = label
            self.psize = 0
            self.bytes = bytearray()

        def setgoto(self, label, val):
            self.type = self.TYPE_GOTO

            self.string = f"goto {label} if "

            if val[0] == 0: # val1 is a memory address
                self.string += f"[{hex(val[1])[2:]}]"
            elif val[0] == 1: # val1 is a value
                self.string += f"{hex(val[1])[2:]}"
            elif val[0] == 2: # val1 is a stack pointer offset
                self.string += f"[sp+{hex(val[1])[2:]}]"
            elif val[0] == 3: # val1 is a user pointer offset
                self.string += f"[up+{hex(val[1])[2:]}]"

            self.string += f" == 0"

            self.psize = 3
            self.bytes = bytearray()

            self.goto_label = label
            self.goto_val = val

        def setpush_label(self, label):
            self.type = self.TYPE_PUSH_LABEL

            self.string = f"push {label}"

            self.psize = 2
            self.bytes = bytearray()

            self.goto_label = label

        def setopcode(self, opcode, v1, v2, v3, v4):
            self.type = self.TYPE_OPCODE

            op = defs.find_opcode(opcode)

            self.string = f"{opcode} "
            argc = 0

            b = bytearray()
            b.append(op.opcode)
            b.append(0) # placeholder for sources and padding

            for i, v in enumerate([v1, v2, v3, v4]):
                if type(v) != tuple and v != None:
                    utl.say_error(f"(Internal) Invalid argument type for opcode {opcode}\nExpected tuple, got {type(v)}")
                s = (v[0] if v else 0)
                if s not in [0, 1, 2, 3]:
                    utl.say_error(f"(Internal) Invalid source type for opcode {opcode}\nExpected 0, 1, 2 or 3, got {s}")
                b[1] |= (s << (2 * -(i - 3)))

                if v == None:
                    break
                if v[0] == 0: # val is a memory address
                    self.string += f"[{hex(v[1])[2:]}] "
                elif v[0] == 1: # val is a value
                    self.string += f"{hex(v[1])[2:]} "
                elif v[0] == 2: # val is a stack pointer offset
                    self.string += f"[sp+{hex(v[1])[2:]}] "
                elif v[0] == 3: # val is a user pointer offset
                    self.string += f"[up+{hex(v[1])[2:]}] "

                argc += 1

            self.raw_args = [opcode]

            for v in [v1, v2, v3, v4]:
                if v == None:
                    break
                b += v[1].to_bytes(2, byteorder='little')
                self.raw_args.append(v)

            self.string = self.string.strip()

            if argc != op.argc:
                utl.say_error(f"(Internal) Bad number of arguments for opcode {opcode}\nExpected {op.argc}, got {argc}")

            self.psize = len(b) // 2
            self.bytes = b


    def __init__(self):
        self.instructions = []

    def add(self, opcode, v1 = None, v2 = None, v3 = None, v4 = None):
        instr = self.instruction()
        instr.setopcode(opcode, v1, v2, v3, v4)
        self.instructions.append(instr)

    def add_comment(self, comment):
        instr = self.instruction()
        instr.setcomment(comment)
        self.instructions.append(instr)

    def add_label(self, label):
        instr = self.instruction()
        instr.setlabel(label)
        self.instructions.append(instr)

    def add_goto(self, label, val):
        instr = self.instruction()
        instr.setgoto(label, val)
        self.instructions.append(instr)

    def add_push_label(self, label):
        instr = self.instruction()
        instr.setpush_label(label)
        self.instructions.append(instr)

    def atdebut(self, other):
        self.instructions = other.instructions + self.instructions

    def atend(self, other):
        self.instructions += other.instructions

    def dump(self, hide_labels = False):
        pc = 0
        for instr in self.instructions:
            if instr.type == self.instruction.TYPE_COMMENT:
                print(f"\033[32m{instr.string}\033[0m")
            elif instr.type == self.instruction.TYPE_LABEL:
                if not hide_labels: print(f"\033[33m{instr.string}::\033[0m")
            elif instr.type == self.instruction.TYPE_GOTO:
                print(f"\033[33m{hex(pc)[2:].zfill(4)}: {instr.string}\033[0m")
            elif instr.type == self.instruction.TYPE_OPCODE:
                print(f"\033[34m{hex(pc)[2:].zfill(4)}: {instr.string}\033[0m")
            elif instr.type == self.instruction.TYPE_PUSH_LABEL:
                print(f"\033[33m{hex(pc)[2:].zfill(4)}: {instr.string}\033[0m")
            else:
                utl.say_error(f"(Internal) Unknown instruction type: {instr.type}")
            pc += instr.psize

    def resolve_labels(self):
        pc = 0
        label_addresses = {}

        # first pass: record label addresses
        for instr in self.instructions:
            if instr.type == self.instruction.TYPE_LABEL:
                label_addresses[instr.string] = pc
            pc += instr.psize

        # second pass: resolve goto instructions
        for instr in self.instructions:
            if instr.type == self.instruction.TYPE_GOTO:
                resolved_address = label_addresses.get(instr.goto_label)
                if resolved_address is None:
                    utl.say_error(f"(Internal) Unknown label: {instr.goto_label}")
                # replace the goto instruction with a jmp instruction
                instr.setopcode("jmp", (1, resolved_address), instr.goto_val, None, None)
            
            elif instr.type == self.instruction.TYPE_PUSH_LABEL:
                resolved_address = label_addresses.get(instr.goto_label)
                if resolved_address is None:
                    utl.say_error(f"(Internal) Unknown label: {instr.goto_label}")
                # replace the push_label instruction with a push instruction
                instr.setopcode("push", (1, resolved_address), None, None, None)

    def to_bytes(self):
        code_bytes = bytearray()
        for instr in self.instructions:
            code_bytes += instr.bytes
        return code_bytes
