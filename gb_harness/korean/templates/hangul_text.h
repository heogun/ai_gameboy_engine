#ifndef HANGUL_TEXT_H
#define HANGUL_TEXT_H

#include <gb/gb.h>

void init_korean_font(void);
void print_korean(UINT8 x, UINT8 y, const unsigned char *str);
void print_korean_win(UINT8 x, UINT8 y, const unsigned char *str);

#endif
