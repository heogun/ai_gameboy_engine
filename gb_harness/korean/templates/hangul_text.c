#include <gb/gb.h>
#include "hangul_text.h"

extern unsigned char font_korean_tiles[];
extern unsigned char font_korean_map_base[];

void init_korean_font(void) {
}

void print_korean(UINT8 x, UINT8 y, const unsigned char *str) {
    (void)x;
    (void)y;
    (void)str;
}

void print_korean_win(UINT8 x, UINT8 y, const unsigned char *str) {
    UINT8 i = 0;
    while (str[i] != 0) {
        set_win_tile_xy(x + i, y, str[i]);
        i++;
        if (x + i >= 20) {
            break;
        }
    }
}
