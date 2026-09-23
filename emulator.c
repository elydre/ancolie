#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <time.h>

#ifdef GUI
#include <SDL2/SDL.h>
#include <fcntl.h>
#endif

// emulator memory
#define MEMORY_SIZE   65536
#define SCREEN_MEMORY 63536

// binary file format
#define MAGIC_NUMBER 0xF057
#define ARCH_VERSION 0x0100
#define MAX_SECTIONS 16

#define SECTION_TYPE_CODE 0
#define SECTION_TYPE_DATA 1

#undef min
#define min(a, b) ((a) < (b) ? (a) : (b))

#ifdef DEBUG
#define DEBUGF(fmt, ...) printf(fmt, ##__VA_ARGS__)
#else
#define DEBUGF(fmt, ...)
#endif

uint16_t *xmem, *rwmem;
uint16_t sp, up; // stack pointer and user pointer

int use_gui;

typedef struct {
    uint16_t magic;
    uint16_t version;
    uint16_t section_count;
} file_header_t;

typedef struct {
    uint16_t type;
    uint16_t debut;
    uint16_t size;
    uint16_t dest_addr;
} section_header_t;

#ifdef GUI

#define FPS_TARGET 30
#define SCREEN_X 80
#define SCREEN_Y 25

typedef struct {
    uint16_t type;
    uint16_t value;
} keyboard_event_t;

typedef struct {
    uint32_t width;
    uint32_t height;
    uint32_t charcount;
    uint32_t charsize;

    uint8_t *data;
} font_data_t;

typedef struct {
    SDL_Window *window;
    SDL_Renderer *renderer;
    SDL_Texture *texture;
    font_data_t *font;

    uint64_t sleep_ticks;
    int cursor_pos;

    keyboard_event_t kbbuf[256];
    int kbbuf_size;

    uint32_t *fb;
    int pitch;
} gui_context_t;

gui_context_t gui;

static inline void print_char(uint32_t xo, uint32_t yo, char c, uint32_t fg) {
    if (c == 0) c = ' ';

    uint8_t *char_data = gui.font->data + (c * gui.font->charsize);

    uint32_t x = 0;
    uint32_t y = 0;

    for (uint32_t i = 0; i < gui.font->charsize; i++) {
        for (int j = 7; j >= 0; j--) {
            gui.fb[(xo + x) + (yo + y) * (gui.pitch / 4)] = char_data[i] & (1 << j) ? fg : 0;
            if (x == gui.font->width - 1) {
                x = 0;
                y++;
                break;
            }
            x++;
        }
    }
}

void rwmem_to_screen(void) {
    static char last_screen[SCREEN_X * SCREEN_Y];
    static int last_cursor_pos = -1;

    int cursor_x, cursor_y;

    if (last_cursor_pos != gui.cursor_pos) {
        if (last_cursor_pos >= 0 && last_cursor_pos < SCREEN_X * SCREEN_Y) {
            cursor_x = last_cursor_pos % SCREEN_X;
            cursor_y = last_cursor_pos / SCREEN_X;
            print_char(cursor_x * gui.font->width, cursor_y * gui.font->height,
                    rwmem[SCREEN_MEMORY + cursor_y * SCREEN_X + cursor_x] & 0xFF, 0xFFFFFFFF);
        }
        last_cursor_pos = gui.cursor_pos;
    }

    for (int y = 0; y < SCREEN_Y; y++) {
        for (int x = 0; x < SCREEN_X; x++) {
            char c = rwmem[SCREEN_MEMORY + y * SCREEN_X + x] & 0xFF;
            if (last_screen[y * SCREEN_X + x] != c) {
                print_char(x * gui.font->width, y * gui.font->height, c, 0xFFFFFFFF);
                last_screen[y * SCREEN_X + x] = c;
            }
        }
    }

    // print_char((gui.cursor_pos % SCREEN_X) * gui.font->width,
    //         (gui.cursor_pos / SCREEN_X) * gui.font->height, '_', 0xAAAAAAAA);
    cursor_x = gui.cursor_pos % SCREEN_X;
    cursor_y = gui.cursor_pos / SCREEN_X;

    for (uint32_t y = 0; y < gui.font->height; y++) {
        for (int x = 1; x < 3; x++) {
            gui.fb[(cursor_x * gui.font->width + x) + (cursor_y * gui.font->height + y) * (gui.pitch / 4)] ^= 0xAAAAAAAA;
        }
    }

}

font_data_t *load_psf_font(const char *path) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) {
        perror("Failed to open font file");
        return NULL;
    }

    uint32_t magic;
    uint32_t version;
    uint32_t headersize;
    uint32_t charcount;
    uint32_t charsize;
    uint32_t height;
    uint32_t width;

    if (pread(fd, &magic, 4, 0)      != 4 ||
        pread(fd, &version, 4, 4)    != 4 ||
        pread(fd, &headersize, 4, 8) != 4 ||
        pread(fd, &charcount, 4, 16) != 4 ||
        pread(fd, &charsize, 4, 20)  != 4 ||
        pread(fd, &height, 4, 24)    != 4 ||
        pread(fd, &width, 4, 28)     != 4
    ) {
        perror("Failed to read font header");
        close(fd);
        return NULL;
    }

    if (magic != 0x864ab572 || version != 0)
        return NULL;

    int size = charcount * charsize;
    uint8_t *font = malloc(size);

    if (pread(fd, font, size, headersize) != size) {
        perror("Failed to read font data");
        free(font);
        close(fd);
        return NULL;
    }

    close(fd);

    font_data_t *psf = malloc(sizeof(font_data_t));
    psf->width = width;
    psf->height = height;
    psf->charcount = charcount;
    psf->charsize = charsize;
    psf->data = font;

    return psf;
}

void cleanup_gui(void) {
    if (gui.font) {
        free(gui.font->data);
        free(gui.font);
    }
    if (gui.texture)
        SDL_DestroyTexture(gui.texture);
    if (gui.renderer)
        SDL_DestroyRenderer(gui.renderer);
    if (gui.window)
        SDL_DestroyWindow(gui.window);

    SDL_Quit();
}

void init_gui(void) {
    memset(&gui, 0, sizeof(gui_context_t));

    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "SDL_Init Error: %s\n", SDL_GetError());
        exit(1);
    }

    gui.font = load_psf_font("asset/zap-light20.psf");

    if (gui.font == NULL) {
        fprintf(stderr, "Failed to load font\n");
        cleanup_gui();
        exit(1);
    }

    gui.window = SDL_CreateWindow("Emulator", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, SCREEN_X * gui.font->width, (SCREEN_Y + 1) * gui.font->height, SDL_WINDOW_SHOWN);
    if (gui.window == NULL) {
        fprintf(stderr, "SDL_CreateWindow Error: %s\n", SDL_GetError());
        cleanup_gui();
        exit(1);
    }

    gui.renderer = SDL_CreateRenderer(gui.window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    if (gui.renderer == NULL) {
        fprintf(stderr, "SDL_CreateRenderer Error: %s\n", SDL_GetError());
        cleanup_gui();
        exit(1);
    }

    gui.texture = SDL_CreateTexture(gui.renderer, SDL_PIXELFORMAT_RGBA8888, SDL_TEXTUREACCESS_STREAMING, SCREEN_X * gui.font->width, (SCREEN_Y + 1) * gui.font->height);
    if (gui.texture == NULL) {
        fprintf(stderr, "SDL_CreateTexture Error: %s\n", SDL_GetError());
        cleanup_gui();
        exit(1);
    }

    if (SDL_LockTexture(gui.texture, NULL, (void **) &gui.fb, &gui.pitch) != 0) {
        fprintf(stderr, "SDL_LockTexture Error: %s\n", SDL_GetError());
        cleanup_gui();
        exit(1);
    }
}

void update_gui(void) {
    SDL_UnlockTexture(gui.texture);

    SDL_RenderClear(gui.renderer);
    SDL_RenderCopy(gui.renderer, gui.texture, NULL, NULL);
    SDL_RenderPresent(gui.renderer);

    SDL_LockTexture(gui.texture, NULL, (void **) &gui.fb, &gui.pitch);
}

#define SMOOTHING_FACTOR 5

void gui_loop(uint64_t ips, uint64_t delta_time) {
    SDL_Event event;

    while (SDL_PollEvent(&event)) {
        if (event.type == SDL_QUIT) {
            cleanup_gui();
            exit(0);
        } else if (event.type == SDL_KEYDOWN || event.type == SDL_KEYUP) {
            keyboard_event_t kevent;
            kevent.type = (event.type == SDL_KEYDOWN) ? 1 : 2;
            kevent.value = event.key.keysym.sym;

            if (gui.kbbuf_size < (int)(sizeof(gui.kbbuf) / sizeof(keyboard_event_t))) {
                gui.kbbuf[gui.kbbuf_size++] = kevent;
            }
        }
    }

    // Update the line 26 of the screen with the stack pointer value
    static double last_ips = 0;
    static double last_fps = 0.0;
    static int iter = 0;

    char str[100];

    if (ips == 0) {
        snprintf(str, sizeof(str), "paused");
        iter = 0;
    } else {
        if (iter < SMOOTHING_FACTOR) {
            iter++;
        }
        if (iter < 2) {
            last_ips = (double)ips;
            last_fps = 1000.0 / (double)(delta_time + 0.1);
        } else {
            last_ips = (last_ips * (iter-1) + (double) ips) / iter;                        // smooth the IPS value
            last_fps = (last_fps * (iter-1) + 1000.0 / (double)(delta_time + 0.1)) / iter; // smooth the FPS value
        }
        snprintf(str, sizeof(str), "CPU: %.1f MHz, FPS: %.1f", last_ips / 1000000, last_fps);
    }
    while (strlen(str) < 80) {
        strcat(str, " ");
    }

    // Render the info line
    for (int i = 0; i < 80; i++) {
        print_char(i * gui.font->width, SCREEN_Y * gui.font->height, str[i], 0xAAAAAAAA);
    }

    update_gui();
}
#endif

static inline uint16_t RVAL(uint8_t source, uint16_t val) {
    switch (source) {
        case 0:
            DEBUGF("[%04X] => %04X\n", val, rwmem[val]);
            return rwmem[val];
        case 1:
            DEBUGF("%04X\n", val);
            return val;
        case 2:
            DEBUGF("[sp+%X=%04X] => %04X\n", val, (rwmem[sp] + val) & 0xFFFF, rwmem[rwmem[sp] + val]);
            return rwmem[(rwmem[sp] + val) & 0xFFFF];
        case 3:
            DEBUGF("[up+%X=%04X] => %04X\n", val, (rwmem[up] + val) & 0xFFFF, rwmem[rwmem[up] + val]);
            return rwmem[(rwmem[up] + val) & 0xFFFF];
        default:
            fprintf(stderr, "Error: Invalid source type %d\n", source);
            exit(1);
    }
}

static inline void WVAL(uint16_t addr, uint8_t source, uint16_t value) {
    switch (source) {
        case 0:
            DEBUGF("[%04X] <= %04X\n", addr, value);
            rwmem[addr] = value;
            break;
        case 1:
            DEBUGF("%04X <= %04X pass\n", addr, value);
            // cannot write to immediate value
            break;
        case 2:
            DEBUGF("[sp+%X=%04X] <= %04X\n", addr, (rwmem[up] + addr) & 0xFFFF, value);
            rwmem[(rwmem[sp] + addr) & 0xFFFF] = value;
            break;
        case 3:
            DEBUGF("[up+%X=%04X] <= %04X\n", addr, (rwmem[up] + addr) & 0xFFFF, value);
            rwmem[(rwmem[up] + addr) & 0xFFFF] = value;
            break;
        default:
            fprintf(stderr, "Error: Invalid source type %d\n", source);
            exit(1);
    }
}

char *opcode_to_string(uint8_t opcode) {
    switch (opcode) {
        case 0x00: return "nop";
        case 0x01: return "mov";
        case 0x02: return "push";
        case 0x03: return "pop";
        case 0x04: return "sub";
        case 0x05: return "add";
        case 0x06: return "mul";
        case 0x07: return "div";
        case 0x08: return "mod";
        case 0x09: return "eq";
        case 0x0A: return "neq";
        case 0x0B: return "lt";
        case 0x0C: return "gt";
        case 0x0D: return "lte";
        case 0x0E: return "gte";
        case 0x0F: return "and";
        case 0x10: return "band";
        case 0x11: return "bor";
        case 0x12: return "jmp";
        case 0x13: return "jmpr";
        case 0x14: return "out";
        case 0x15: return "in";
        case 0x16: return "sup";
        case 0x17: return "ssp";
        case 0x18: return "mss";
        case 0x19: return "pushs";
        case 0x1A: return "pops";
        case 0x1B: return "memset";
        case 0x1C: return "memmov";
        case 0xFF: return "halt";
        default:
            fprintf(stderr, "Error: Unknown opcode 0x%02X\n", opcode);
            exit(1);
    }
}

uint16_t port_in(uint16_t port) {
    switch (port) {
        case 0 ... 8:
            fprintf(stderr, "Redstone input from port 0x%04X\n", port);
            return 0;
        case 0x1010:
            #ifdef GUI
            if (use_gui) {
                if (gui.kbbuf_size == 0)
                    return 0;

                keyboard_event_t kevent = gui.kbbuf[0];
                return kevent.type;
            }
            #endif
            fprintf(stderr, "Keyboard input requested but GUI is not enabled\n");
            return 0;
        case 0x1011:
            #ifdef GUI
            if (use_gui) {
                if (gui.kbbuf_size == 0)
                    return 0;

                keyboard_event_t kevent = gui.kbbuf[0];
                // shift the buffer
                for (int i = 1; i < gui.kbbuf_size; i++) {
                    gui.kbbuf[i - 1] = gui.kbbuf[i];
                }
                gui.kbbuf_size--;
                return kevent.value;
            }
            #endif
            fprintf(stderr, "Keyboard input requested but GUI is not enabled\n");
            return 0;
        case 0x1030:
            // get minecraft time (24h) in ticks
            {
                time_t now = time(NULL);
                struct tm *tm_info = localtime(&now);
                int hours = tm_info->tm_hour;
                int minutes = tm_info->tm_min;
                int seconds = tm_info->tm_sec;

                double total_seconds = (hours + 18) * 3600 + minutes * 60 + seconds;
                total_seconds /= 3.6;
                return ((uint16_t) total_seconds) % 24000;
            }
        default:
            fprintf(stderr, "Input from port 0x%04X\n", port);
            return 0;
    }
}

void port_out(uint16_t port, uint16_t value) {
    switch (port) {
        case 0 ... 8:
            fprintf(stderr, "Redstone output to port 0x%04X: %04X\n", port, value);
            break;
        case 0x1000:
            printf("0x%x\n", value);
            break;
        case 0x1001:
            printf("%d\n", value);
            break;
        case 0x1002:
            putchar(value & 0xFF);
            break;
        case 0x1020:
            #ifdef GUI
            if (use_gui) {
                rwmem_to_screen();
                break;
            }
            #endif
            fprintf(stderr, "Screen update requested but GUI is not enabled\n");
            break;
        case 0x1021:
            #ifdef GUI
            if (use_gui) {
                gui.cursor_pos = value;
                break;
            }
            #endif
            fprintf(stderr, "Cursor position update requested but GUI is not enabled\n");
            break;
        case 0x1031:
            #ifdef GUI
            if (use_gui) {
                gui.sleep_ticks = SDL_GetTicks() + value * 50; // minecraft tick
            } else {
            #endif
                usleep(value * 50000); // minecraft tick
            #ifdef GUI
            }
            #endif
            break;
        default:
            fprintf(stderr, "Output to port 0x%04X: %04X\n", port, value);
            break;
    }
}

void execute_program() {
    uint16_t pc; // program counter
    pc = sp = 0;

    #ifdef GUI
    uint64_t last_time = 0;
    int icount = 0;
    #endif

    while (1) {
        uint16_t instruction = xmem[pc++];

        uint8_t opcode = instruction & 0xFF00 >> 8;

        uint8_t source0 = instruction >> 14 & 0x03;
        uint8_t source1 = instruction >> 12 & 0x03;
        uint8_t source2 = instruction >> 10 & 0x03;
        uint8_t source3 = instruction >> 8 & 0x03;

        DEBUGF("pc: %04X \033[34m%s\033[0m\n", pc - 1, opcode_to_string(opcode));

        switch (opcode) {
            case 0x00: // nop
                break;
            case 0x01: // mov
                WVAL(xmem[pc], source0, RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x02: // push
                uint16_t v = RVAL(source0, xmem[pc]);
                rwmem[sp]--;
                rwmem[rwmem[sp]] = v;
                pc++;
                break;
            case 0x03: // pop
                WVAL(xmem[pc], source0, rwmem[rwmem[sp]]);
                rwmem[sp]++;
                pc++;
                break;
            case 0x04: // sub
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) - RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x05: // add
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) + RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x06: // mul
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) * RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x07: // div
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) / RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x08: // mod
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) % RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x09: // eq
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) == RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x0A: // neq
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) != RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x0B: // lt
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) < RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x0C: // gt
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) > RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x0D: // lt
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) <= RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x0E: // gt
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) >= RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x0F: // and
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) && RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x10: // band
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) & RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x11: // bor
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) | RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x12: // jmp
                if (RVAL(source1, xmem[pc + 1]) == 0)
                    pc = RVAL(source0, xmem[pc]);
                else
                    pc += 2;
                break;
            case 0x13: // jmpr
                if (RVAL(source1, xmem[pc + 1]) == 0)
                    pc += RVAL(source0, xmem[pc]);
                else
                    pc += 2;
                break;
            case 0x14: // out
                port_out(RVAL(source0, xmem[pc]), RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x15: // in
                WVAL(xmem[pc], source0, port_in(RVAL(source1, xmem[pc + 1])));
                pc += 2;
                break;
            case 0x16: // ssp
                sp = RVAL(source0, xmem[pc]);
                pc++;
                break;
            case 0x17: // sup
                up = RVAL(source0, xmem[pc]);
                pc++;
                break;
            case 0x18: // mss
            {
                uint16_t dest = RVAL(source0, xmem[pc])     + RVAL(source1, xmem[pc + 1]);
                uint16_t src  = RVAL(source2, xmem[pc + 2]) + RVAL(source3, xmem[pc + 3]);

                DEBUGF("mss: [%04X] = [%04X] = %04X\n", dest, src, rwmem[src]);
                rwmem[dest] = rwmem[src];
                pc += 4;
                break;
            }
            case 0x19: // pushs
                rwmem[sp]--;
                rwmem[rwmem[sp]] = rwmem[(uint16_t)(RVAL(source0, xmem[pc]) + RVAL(source1, xmem[pc + 1]))];
                pc += 2;
                break;
            case 0x1A: // pops
                rwmem[(uint16_t)(RVAL(source0, xmem[pc]) + RVAL(source1, xmem[pc + 1]))] = rwmem[rwmem[sp]];
                rwmem[sp]++;
                pc += 2;
                break;
            case 0x1B: // memset
            {
                uint16_t addr = RVAL(source0, xmem[pc]);
                uint16_t val  = RVAL(source1, xmem[pc + 1]);
                uint16_t size = RVAL(source2, xmem[pc + 2]);

                DEBUGF("memset: [%04X] = %04X, size = %04X\n", addr, val, size);
                for (uint16_t i = 0; i < size && (addr + i) < MEMORY_SIZE; i++) {
                    rwmem[addr + i] = val;
                }
                pc += 3;
                break;
            }
            case 0x1C: // memmov
            {
                uint16_t dest = RVAL(source0, xmem[pc]);
                uint16_t src  = RVAL(source1, xmem[pc + 1]);
                uint16_t size = RVAL(source2, xmem[pc + 2]);

                DEBUGF("memmov: [%04X] = [%04X], size = %04X\n", dest, src, size);
                if (src < dest) {
                    for (int i = size - 1; i >= 0; i--) {
                        if ((src + i) < MEMORY_SIZE && (dest + i) < MEMORY_SIZE) {
                            rwmem[dest + i] = rwmem[src + i];
                        }
                    }
                } else {
                    for (uint16_t i = 0; i < size; i++) {
                        if ((src + i) < MEMORY_SIZE && (dest + i) < MEMORY_SIZE) {
                            rwmem[dest + i] = rwmem[src + i];
                        }
                    }
                }
                pc += 3;
                break;
            }
            case 0xFF: // halt
                return;
            default:
                DEBUGF("Unknown opcode: 0x%02X\n", opcode);
                return;
        }

        #ifdef GUI
        if (use_gui) {
            uint64_t current_time;
            icount++;

            while (gui.sleep_ticks > 0) {
                current_time = SDL_GetTicks();

                int to_sleep = min((int)(gui.sleep_ticks - current_time), (int)(current_time - last_time));
                last_time = current_time;

                if (to_sleep > 0) {
                    gui_loop(0, 0);
                    usleep(to_sleep * 1000);
                } else {
                    gui.sleep_ticks = 0;
                }
            }

            if (icount % 10000 == 0) {
                current_time = SDL_GetTicks();
                uint64_t delta_time = current_time - last_time;

                if (delta_time > (1000 / FPS_TARGET)) {
                    last_time = current_time;
                    uint64_t ips = (uint64_t) icount * 1000 / (double)(delta_time + 0.1);
                    gui_loop(ips, delta_time);
                    icount = 0;
                }
            }
        }
        #endif

        #ifdef DEBUG
        // print the beginning of the stack
        DEBUGF("\033[90m[ ");
        for (int i = 0; i < 5; i++) {
            if (i == 0)
                DEBUGF("%04X=", rwmem[sp] + i);
            DEBUGF("%04X ", rwmem[rwmem[sp] + i]);
        }
        DEBUGF("]\033[0m\n");
        #endif

        if (pc >= MEMORY_SIZE - 10)
            return;
    }
}

int main(int argc, char **argv) {
    char *filename = NULL;

    if (argc == 3 && strcmp(argv[1], "--gui") == 0) {
        filename = argv[2];
        use_gui = 1;
    } else if (argc == 2) {
        filename = argv[1];
        use_gui = 0;
    } else {
        fprintf(stderr, "Usage: %s [--gui] <file>\n", argv[0]);
        return 1;
    }

    #ifndef GUI
    if (use_gui) {
        fprintf(stderr, "Error: GUI support is not compiled in, please recompile with -DGUI\n");
        return 1;
    }
    #endif

    FILE *bytecode = fopen(filename, "rb");

    if (bytecode == NULL) {
        perror("Failed to open 'output.bin' you need to run the compiler first");
        return 1;
    }

    file_header_t header;

    if (fread(&header, sizeof(file_header_t), 1, bytecode) != 1) {
        perror("Failed to read file header");
        fclose(bytecode);
        return 1;
    }

    if (header.magic != MAGIC_NUMBER) {
        fprintf(stderr, "Error: Invalid magic number in bytecode file\n");
        fclose(bytecode);
        return 1;
    }

    if (header.version != ARCH_VERSION) {
        fprintf(stderr, "Error: Unsupported architecture version in bytecode file\n");
        fclose(bytecode);
        return 1;
    }

    if (header.section_count > MAX_SECTIONS) {
        fprintf(stderr, "Error: Too many sections in bytecode file\n");
        fclose(bytecode);
        return 1;
    }

    section_header_t sections[MAX_SECTIONS];

    if (fread(sections, sizeof(section_header_t), header.section_count, bytecode) != header.section_count) {
        perror("Failed to read section headers");
        fclose(bytecode);
        return 1;
    }

    xmem = calloc(MEMORY_SIZE, sizeof(uint16_t));
    rwmem = calloc(MEMORY_SIZE, sizeof(uint16_t));

    if (xmem == NULL || rwmem == NULL) {
        perror("Failed to allocate memory");
        fclose(bytecode);
        return 1;
    }

    for (int i = 0; i < header.section_count; i++) {
        if (sections[i].type != SECTION_TYPE_CODE && sections[i].type != SECTION_TYPE_DATA) {
            fprintf(stderr, "Error: Invalid section type %d in section %d\n", sections[i].type, i);
            fclose(bytecode);
            return 1;
        }

        if (sections[i].size % sizeof(uint16_t) != 0) {
            fprintf(stderr, "Error: Section %d size is not a multiple of 2\n", i);
            fclose(bytecode);
            return 1;
        }

        if (sections[i].dest_addr + (sections[i].size / sizeof(uint16_t)) > MEMORY_SIZE) {
            fprintf(stderr, "Error: Section %d exceeds memory bounds\n", i);
            fclose(bytecode);
            return 1;
        }

        if (sections[i].type == SECTION_TYPE_CODE) {
            if (fseek(bytecode, sections[i].debut, SEEK_SET) || fread(&xmem[sections[i].dest_addr], 1, sections[i].size, bytecode) != sections[i].size) {
                perror("Failed to read code section");
                fclose(bytecode);
                return 1;
            }
            printf("Loaded code section %d: %d bytes to address 0x%04X\n", i, sections[i].size, sections[i].dest_addr);
        } else if (sections[i].type == SECTION_TYPE_DATA) {
            if (fseek(bytecode, sections[i].debut, SEEK_SET) || fread(&rwmem[sections[i].dest_addr], 1, sections[i].size, bytecode) != sections[i].size) {
                perror("Failed to read data section");
                fclose(bytecode);
                return 1;
            }
            printf("Loaded data section %d: %d bytes to address 0x%04X\n", i, sections[i].size, sections[i].dest_addr);
        }
    }

    fclose(bytecode);

    #ifdef GUI
    if (use_gui) {
        init_gui();
        update_gui();
    }
    #endif

    printf("Starting emulation\n");

    execute_program();

    #ifdef GUI
    if (use_gui) {
        cleanup_gui();
    }
    #endif

    free(rwmem);
    free(xmem);

    return 0;
}
