#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <time.h>

#ifdef GUI
#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#endif

#define MEMORY_SIZE 65536

#undef min
#define min(a, b) ((a) < (b) ? (a) : (b))

#ifdef DEBUG
#define DEBUGF(fmt, ...) printf(fmt, ##__VA_ARGS__)
#else
#define DEBUGF(fmt, ...) do {} while (0)
#endif

uint16_t *xmem, *rwmem;
uint16_t sp; // stack pointer

int use_gui;

#ifdef GUI

#define FPS_TARGET 10
#define SCREEN_X 80
#define SCREEN_Y 25

SDL_Window *window;
SDL_Renderer *renderer;
TTF_Font *font;
SDL_Texture *screen_texture;
SDL_Texture *info_texture;

int font_width, font_height;
int cursor_pos = 0;

typedef struct {
    uint16_t type;
    uint16_t value;
} keyboard_event_t;

keyboard_event_t keyboard_buffer[256];
int keyboard_buffer_size = 0;

void render_screen(void) {
    SDL_Texture *previous_target = SDL_GetRenderTarget(renderer);
    SDL_SetRenderTarget(renderer, screen_texture);

    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);

    for (int y = 0; y < SCREEN_Y; y++) {
        for (int x = 0; x < SCREEN_X; x++) {
            uint16_t addr = (MEMORY_SIZE - (SCREEN_X * SCREEN_Y)) + (y * SCREEN_X) + x;

            char c = (char)(rwmem[addr] & 0xFF);
            char str[2] = {c, '\0'};

            SDL_Color color = {255, 255, 255, 255};
            SDL_Surface *surface = TTF_RenderText_Blended(font, str, color);
            SDL_Texture *texture = SDL_CreateTextureFromSurface(renderer, surface);

            SDL_Rect dstrect = {x * font_width, y * font_height, font_width, font_height};
            SDL_RenderCopy(renderer, texture, NULL, &dstrect);

            SDL_FreeSurface(surface);
            SDL_DestroyTexture(texture);
        }
    }

    // Render the cursor
    int cursor_x = cursor_pos % SCREEN_X;
    int cursor_y = cursor_pos / SCREEN_X;

    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
    SDL_Rect cursor_rect = {cursor_x * font_width, cursor_y * font_height, font_width, font_height};
    SDL_RenderDrawRect(renderer, &cursor_rect);

    SDL_SetRenderTarget(renderer, previous_target);
}

void init_gui(void) {
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "SDL_Init Error: %s\n", SDL_GetError());
        exit(1);
    }

    // Initialize SDL_ttf
    if (TTF_Init() == -1) {
        fprintf(stderr, "TTF_Init Error: %s\n", TTF_GetError());
        SDL_Quit();
        exit(1);
    }

    // load a font (using system font for simplicity)
    font = TTF_OpenFont("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16);
    if (font == NULL) {
        fprintf(stderr, "TTF_OpenFont Error: %s\n", TTF_GetError());
        TTF_Quit();
        SDL_Quit();
        exit(1);
    }
    TTF_SetFontHinting(font, TTF_HINTING_LIGHT);

    if (TTF_SizeText(font, "M", &font_width, NULL) != 0) {
        fprintf(stderr, "TTF_SizeText Error: %s\n", TTF_GetError());
        TTF_CloseFont(font);
        TTF_Quit();
        SDL_Quit();
        exit(1);
    }
    font_height = TTF_FontHeight(font);

    window = SDL_CreateWindow("Emulator", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, SCREEN_X * font_width, (SCREEN_Y + 1) * font_height, SDL_WINDOW_SHOWN);
    if (window == NULL) {
        fprintf(stderr, "SDL_CreateWindow Error: %s\n", SDL_GetError());
        TTF_CloseFont(font);
        TTF_Quit();
        SDL_Quit();
        exit(1);
    }

    renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    if (renderer == NULL) {
        SDL_DestroyWindow(window);
        fprintf(stderr, "SDL_CreateRenderer Error: %s\n", SDL_GetError());
        TTF_CloseFont(font);
        TTF_Quit();
        SDL_Quit();
        exit(1);
    }

    screen_texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA8888, SDL_TEXTUREACCESS_TARGET, SCREEN_X * font_width, SCREEN_Y * font_height);
    if (screen_texture == NULL) {
        SDL_DestroyRenderer(renderer);
        SDL_DestroyWindow(window);
        fprintf(stderr, "SDL_CreateTexture Error: %s\n", SDL_GetError());
        TTF_CloseFont(font);
        TTF_Quit();
        SDL_Quit();
        exit(1);
    }

    info_texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA8888, SDL_TEXTUREACCESS_TARGET, SCREEN_X * font_width, font_height);
    if (info_texture == NULL) {
        SDL_DestroyTexture(screen_texture);
        SDL_DestroyRenderer(renderer);
        SDL_DestroyWindow(window);
        fprintf(stderr, "SDL_CreateTexture Error: %s\n", SDL_GetError());
        TTF_CloseFont(font);
        TTF_Quit();
        SDL_Quit();
        exit(1);
    }

    memset(keyboard_buffer, 0, sizeof(keyboard_buffer));
}

void cleanup_gui(void) {
    SDL_DestroyTexture(screen_texture);
    SDL_DestroyTexture(info_texture);
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    TTF_CloseFont(font);
    TTF_Quit();
    SDL_Quit();
}

void update_gui(void) {
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);

    SDL_Rect screen_rect = {0, 0, SCREEN_X * font_width, SCREEN_Y * font_height};
    SDL_RenderCopy(renderer, screen_texture, NULL, &screen_rect);
 
    SDL_Rect info_rect = {0, SCREEN_Y * font_height, SCREEN_X * font_width, font_height};
    SDL_RenderCopy(renderer, info_texture, NULL, &info_rect);

    SDL_RenderPresent(renderer);
}

#define SMOOTHING_FACTOR 20

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

            if (keyboard_buffer_size < (int)(sizeof(keyboard_buffer) / sizeof(keyboard_event_t))) {
                keyboard_buffer[keyboard_buffer_size++] = kevent;
            }
        }
    }

    SDL_RenderClear(renderer);
    SDL_Rect screen_rect = {0, 0, SCREEN_X * font_width, SCREEN_Y * font_height};
    SDL_RenderCopy(renderer, screen_texture, NULL, &screen_rect);

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
            last_ips = (last_ips * (iter-1) + (double)ips) / iter; // smooth the IPS value
            last_fps = (last_fps * (iter-1) + 1000.0 / (double)(delta_time + 0.1)) / iter; // smooth the FPS value
        }
        snprintf(str, sizeof(str), "CPU: %.1fMHz, FPS: %.1f", last_ips / 1000000, last_fps);
    }
    while (strlen(str) < 80) {
        strcat(str, " ");
    }

    SDL_Color color = {255, 255, 255, 255}; // white color
    SDL_Surface *surface = TTF_RenderText_Blended(font, str, color);
    SDL_Texture *new_info_texture = SDL_CreateTextureFromSurface(renderer, surface);
    SDL_FreeSurface(surface);
    SDL_DestroyTexture(info_texture);
    info_texture = new_info_texture;

    update_gui();
}
#endif

static inline uint16_t RVAL(uint8_t source, uint16_t val) {
    if (source == 0)
        DEBUGF("RVAL: [%04X] = %04X\n", val, rwmem[val]);
    else if (source == 1)
        DEBUGF("RVAL: %04X = %04X pass\n", val, val);
    else if (source == 2)
        DEBUGF("RVAL: [sp+%X] = %04X\n", val, rwmem[rwmem[sp] + val]);
    else if (source == 3)
        DEBUGF("RVAL: [[%04X]] = %04X\n", val, rwmem[rwmem[val]]);

    switch (source) {
        case 0: return rwmem[val];
        case 1: return val;
        case 2: return rwmem[rwmem[sp] + val];
        // case 3: return rwmem[rwmem[val]];
        default: {
            fprintf(stderr, "Error: Invalid source type %d\n", source);
            exit(1);
        }
    }
}

static inline void WVAL(uint16_t addr, uint8_t source, uint16_t value) {
    if (source == 0)
        DEBUGF("WVAL: [%04X] = %04X\n", addr, value);
    else if (source == 1)
        DEBUGF("WVAL: %04X = %04X pass\n", addr, value);
    else if (source == 2)
        DEBUGF("WVAL: [sp+%X] = %04X\n", addr, value);
    else if (source == 3)
        DEBUGF("WVAL: [[%04X]] = %04X\n", addr, value);

    switch (source) {
        case 0: rwmem[addr] = value; break;
        case 1: break; // cannot write to immediate value
        case 2: rwmem[rwmem[sp] + addr] = value; break;
        // case 3: rwmem[rwmem[addr]] = value; break;
        default: {
            fprintf(stderr, "Error: Invalid source type %d\n", source);
            exit(1);
        }
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
        case 0x0D: return "and";
        case 0x0E: return "band";
        case 0x0F: return "bor";
        case 0x10: return "jmp";
        case 0x11: return "jmpr";
        case 0x12: return "out";
        case 0x13: return "in";
        case 0x14: return "sleep";
        case 0x15: return "ssp";
        case 0x16: return "mss";
        case 0x17: return "pushs";
        case 0x18: return "pops";
        case 0x19: return "memset";
        case 0x1A: return "memmov";
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
                if (keyboard_buffer_size == 0)
                    return 0;

                keyboard_event_t kevent = keyboard_buffer[0];
                return kevent.type;
            }
            #endif
            fprintf(stderr, "Keyboard input requested but GUI is not enabled\n");
            return 0;
        case 0x1011:
            #ifdef GUI
            if (use_gui) {
                if (keyboard_buffer_size == 0)
                    return 0;

                keyboard_event_t kevent = keyboard_buffer[0];
                // shift the buffer
                for (int i = 1; i < keyboard_buffer_size; i++) {
                    keyboard_buffer[i - 1] = keyboard_buffer[i];
                }
                keyboard_buffer_size--;
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
                render_screen();
                update_gui();
                break;
            }
            #endif
            fprintf(stderr, "Screen update requested but GUI is not enabled\n");
            break;
        case 0x1021:
            #ifdef GUI
            if (use_gui) {
                cursor_pos = value;
                break;
            }
            #endif
            fprintf(stderr, "Cursor position update requested but GUI is not enabled\n");
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
    int icount = 0;
    int update_interval = 1000000;
    uint64_t last_time = 0;
    uint64_t sleep_to = 0;
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
            case 0x0D: // and
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) && RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x0E: // band
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) & RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x0F: // bor
                WVAL(xmem[pc], source0, RVAL(source0, xmem[pc]) | RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x10: // jmp
                if (RVAL(source1, xmem[pc + 1]) == 0)
                    pc = RVAL(source0, xmem[pc]);
                else
                    pc += 2;
                break;
            case 0x11: // jmpr
                if (RVAL(source1, xmem[pc + 1]) == 0)
                    pc += RVAL(source0, xmem[pc]);
                else
                    pc += 2;
                break;
            case 0x12: // out
                port_out(RVAL(source0, xmem[pc]), RVAL(source1, xmem[pc + 1]));
                pc += 2;
                break;
            case 0x13: // in
                WVAL(xmem[pc], source0, port_in(RVAL(source1, xmem[pc + 1])));
                pc += 2;
                break;
            case 0x14: // sleep
                #ifdef GUI
                if (use_gui) {
                    sleep_to = SDL_GetTicks() + RVAL(source0, xmem[pc]) * 50; // minecraft tick
                } else {
                #endif
                    usleep(RVAL(source0, xmem[pc]) * 50000); // minecraft tick
                #ifdef GUI
                }
                #endif

                pc++;
                break;
            case 0x15: // ssp
                sp = RVAL(source0, xmem[pc]);
                pc++;
                break;
            case 0x16: // mss
            {
                uint16_t dest = RVAL(source0, xmem[pc])     + RVAL(source1, xmem[pc + 1]);
                uint16_t src  = RVAL(source2, xmem[pc + 2]) + RVAL(source3, xmem[pc + 3]);

                DEBUGF("mss: [%04X] = [%04X] = %04X\n", dest, src, rwmem[src]);
                rwmem[dest] = rwmem[src];
                pc += 4;
                break;
            }
            case 0x17: // pushs
                rwmem[sp]--;
                rwmem[rwmem[sp]] = rwmem[(uint16_t)(RVAL(source0, xmem[pc]) + RVAL(source1, xmem[pc + 1]))];
                pc += 2;
                break;
            case 0x18: // pops
                rwmem[(uint16_t)(RVAL(source0, xmem[pc]) + RVAL(source1, xmem[pc + 1]))] = rwmem[rwmem[sp]];
                rwmem[sp]++;
                pc += 2;
                break;
            case 0x19: // memset
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
            case 0x1A: // memmov
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

            while (sleep_to > 0) {
                current_time = SDL_GetTicks();

                int to_sleep = min((int)(sleep_to - current_time), (int)(current_time - last_time));
                last_time = current_time;

                if (to_sleep > 0) {
                    gui_loop(0, 0);
                    usleep(to_sleep * 1000);
                } else {
                    sleep_to = 0;
                }
            }

            if (icount >= update_interval) {
                current_time = SDL_GetTicks();
                uint64_t delta_time = current_time - last_time;
                last_time = current_time;

                uint64_t ips = (uint64_t) icount * 1000 / (double)(delta_time + 0.1);
                gui_loop(ips, delta_time);

                // recalculate the update interval based on the target FPS
                update_interval = ((update_interval * 9) + (int)(ips / FPS_TARGET)) / 10;

                icount = 0;
            }
        }
        #endif

        // print the beginning of the stack
        DEBUGF("\033[90m[ ");
        for (int i = 0; i < 5; i++) {
            if (i == 0)
                DEBUGF("%04X=", rwmem[sp] + i);
            DEBUGF("%04X ", rwmem[rwmem[sp] + i]);
        }
        DEBUGF("]\033[0m\n");

        if (pc >= MEMORY_SIZE - 10)
            return;
    }
}

typedef struct {
    uint16_t magic;
    uint16_t version;
    uint16_t section_count;
} file_header_t;

typedef struct {
    uint16_t debut;
    uint16_t size;
    uint16_t dest_addr;
    uint16_t type;
} section_header_t;

#define MAGIC_NUMBER 0xF057
#define ARCH_VERSION 1
#define MAX_SECTIONS 16

#define SECTION_TYPE_CODE 0
#define SECTION_TYPE_DATA 1



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
