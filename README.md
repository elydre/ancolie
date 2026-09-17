# cream & ancolie

custom instruction set, esoteric programming language (`ancolie`), single pass compiler (`llc`), emulator and operating system (`frostOS`).

## how to use ?

```sh
# compile a ancolie program
python llc.py -o program.bin program.li

# emulator without GUI support
gcc -o emulator emulator.c
./emulator program.bin

# emulator with GUI support
gcc -DGUI -o emulator emulator.c -lSDL2 -lSDL2_ttf
./emulator --gui program.bin
```

## Todo

### Compiler

- [x] variable on stack
- [x] RPN calculator
- [x] if statements
- [x] while loops
- [x] pointers operations
- [x] built-in functions
- [x] alloca
- [x] break and continue
- [x] for loops
- [x] elif/else statements
- [x] output file format
- [x] heap variables (static)
- [x] heap strings
- [x] comments
- [x] functions
- [ ] preprocessor
- [ ] function with variable arguments
- [ ] heap arrays
- [ ] sub stack scope
- [ ] structs
- [ ] asm statements
- [ ] some optimizations
- [ ] multiple source files

### Extra

- [x] C emulator
- [x] basic command line interface for compiler
- [x] add screen to the emulator
- [ ] langage documentation
- [ ] create a basic operating system

## ancolie language

```c
// this is a comment

/* Everything is a 16-bit word.
** The language has no type system.
** Values, pointers and characters are all
** represented by the same 16-bit value.
*/
: var             // variable declaration
: ptr str i       // multiple variable declaration

$ hello           // static variable declaration (set to 0)
$ var = 3         // static variable declaration with initialization

/* The language use RPN (Reverse Polish Notation).
*/
var = 3           // variable assignment
var = 3 4 +       // assignment from RPN expression (3 + 4)
var = i           // assignment from another variable

/* Strings are stored in the heap, the variable
** is a pointer to the string.
*/
str = "hello"     // string assignment

/* Pointers are memory accesses to an address.
*/
var = [0]         // variable assignment from memory address 0
[0] = var         // memory address 0 assignment from variable
var = [str]       // variable assignment from string pointer
var = [str 1 +]   // assignment from string pointer + 1 (next character)

/* The built-in function alloca() allocates memory
** on the stack and returns a pointer to it.
*/
ptr = alloca(10)  // allocate 10 bytes on the stack
[ptr] = 3         // assign 3 to the first byte of the allocation
```

## Computer architecture

### opcode (may be subject to change)

```
opcode (8 bit)  sources (4 * 2bit)  [  arg0 (16 bit)   ] ... [ arg3 (16 bit)    ]
000000          00000000            [ 0000000000000000 ] ... [ 0000000000000000 ]

(arguments quantity is determined by the opcode)
```

| NUMBER | OPCODE | ARGUMENTS   | DESCRIPTION                |
| ------ | ------ | ----------- | ---------------------------|
| `0x00` |  nop   |             | no operation               |
|        |        |             |                            |
| `0x01` |  mov   | `a` `b`     | `a <- b`                   |
|        |        |             |                            |
| `0x02` |  push  | `a`         | `sp--`, `[sp] <- a`        |
| `0x03` |  pop   | `a`         | `a <- [sp]`, `sp++`        |
|        |        |             |                            |
| `0x04` |  sub   | `a` `b`     | `a <- a - b`               |
| `0x05` |  add   | `a` `b`     | `a <- a + b`               |
| `0x06` |  mul   | `a` `b`     | `a <- a * b`               |
| `0x07` |  div   | `a` `b`     | `a <- a / b`               |
| `0x08` |  mod   | `a` `b`     | `a <- a % b`               |
|        |        |             |                            |
| `0x09` |  eq    | `a` `b`     | `a <- a == b`              |
| `0x0A` |  neq   | `a` `b`     | `a <- a != b`              |
| `0x0B` |  lt    | `a` `b`     | `a <- a < b`               |
| `0x0C` |  gt    | `a` `b`     | `a <- a > b`               |
|        |        |             |                            |
| `0x0D` |  and   | `a` `b`     | `a <- a && b`              |
| `0x0E` |  band  | `a` `b`     | `a <- a & b`               |
| `0x0F` |  bor   | `a` `b`     | `a <- a bor b` (md sorry)  |
|        |        |             |                            |
| `0x10` |  jmp   | `a` `b`     | `pc  = a if b == 0`        |
| `0x11` |  jmpr  | `a` `b`     | `pc += a if b == 0`        |
|        |        |             |                            |
| `0x12` |  out   | `port` `a`  | output `a` to `port`       |
| `0x13` |  in    | `a` `port`  | input from `port` to `a`   |
|        |        |             |                            |
| `0x14` |  ssp   | `a`         | `sp <- a`                  |
| `0x15` |  sup   | `a`         | `up <- a`                  |
|        |        |             |                            |
| `0x16` |  mss   | `A` `a` `B` `b` | `[A + a] <- [B + b]`   |
| `0x17` |  pushs | `A` `a`     | `sp--`, `[sp] <- [A + a]`  |
| `0x18` |  pops  | `A` `a`     | `[A + a] <- [sp]`, `sp++`  |
|        |        |             |                            |
| `0x19` | memset | `a` `b` `c` | `memset(addr=a val=b s=c)` |
| `0x1A` | memmov | `a` `b` `c` | `memmov(dest=a src=b s=c)` |
|        |        |             |                            |
| `0xFF` |  hlt   |             | halt the computer          |

each argument can be one of the following:

| SOURCE | DESCRIPTION | EXPLANATION     |
| ------ | ----------- | --------------- |
|  0     | `[a]`       | memory address  |
|  1     | `a`         | value           |
|  2     | `sp+a`      | stack address   |
|  3     | `up+a`      | base + offset   |

### Used ports

| PORT         | DIRECTION | DESCRIPTION                                    |
| ------------ | --------- | ---------------------------------------------- |
| **redstone** | -         | -                                              |
| `0`          | in/out    | 4 bit **front** redstone signal                |
| `1`          | in/out    | 4 bit **left** redstone signal                 |
| `2`          | in/out    | 4 bit **back** redstone signal                 |
| `3`          | in/out    | 4 bit **right** redstone signal                |
| `4`          | in/out    | 4 bit **north** redstone signal                |
| `5`          | in/out    | 4 bit **east** redstone signal                 |
| `6`          | in/out    | 4 bit **south** redstone signal                |
| `7`          | in/out    | 4 bit **west** redstone signal                 |
| **debug**    | -         | -                                              |
| `0x1000`     | out       | print hexadecimal value (emulator stdout)      |
| `0x1001`     | out       | print decimal value (emulator stdout)          |
| `0x1002`     | out       | print character (emulator stdout)              |      
| **keyboard** | -         | -                                              |
| `0x1010`     | in        | get kb state (0 noting, 1 pressed, 2 released) |
| `0x1011`     | in        | get kb char and pop it from the buffer         |
| **screen**   | -         | -                                              |
| `0x1020`     | out       | flush the screen from memory                   |
| `0x1021`     | out       | set cursor position (`n = x + y*80`)           |
| **clock**    | -         | -                                              |
| `0x1030`     | in        | get ingame time in ticks                       |
| `0x1031`     | out       | sleep for `n` ticks (1 tick = 50ms)            |


## Compiled file format

```
[HEADER]
magic number         (16 bit)
ARCH version         (16 bit)
section count        (16 bit)

section 0 type       (16 bit)
section 0 debut      (16 bit)
section 0 size       (16 bit)
section 0 dest-addr  (16 bit)

section 1 type       (16 bit)
section 1 debut      (16 bit)
section 1 size       (16 bit)
section 1 dest-addr  (16 bit)
...

[SECTION 0 DATA]
...

[SECTION 1 DATA]
...
```

- `magic number` is used to identify the file format, it should be `0xF057`
- `debut` and `size` are in bytes (8 bits), `dest-addr` is in words (16 bit)
- `section debut` is the offset in the file where the section data starts

section type:
- 0: code (in X memory)
- 1: data (in RW memory)
