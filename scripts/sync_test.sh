#!/bin/bash -x
#
# Tool to check video and audio sync.
# Loop with 1 beep per second with 4 increasing frequencies.
# Can be used to measure delays up to 4 seconds.
#
# Beep duration: 0.125s
#

font="/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
size="860x300"

DURATION="0.125"
T="floor(t)"
beep="lt(mod(t\,1)\,0.125)"
hz="*2*PI*t"

f_1="(sin( 440 $hz) + sin( 880 $hz)/3 + sin(1320 $hz)/5 + sin(1760 $hz)/7)"
f_2="(sin( 660 $hz) + sin(1320 $hz)/4 + sin(1980 $hz)/6)"
f_3="(sin( 880 $hz) + sin(1760 $hz)/3)"
f_4="(sin(1320 $hz) + sin(2640 $hz)/4)"


ffplay -f lavfi "aevalsrc=\
    if(mod($T\,2)           \,\
        if(mod($T+1\,4)     \,\
            $f_2 * $beep    \,\
            $f_4 * $beep    \
        )                   \,\
        if(mod($T\,4)       \,\
            $f_3 * $beep    \,\
            $f_1 * $beep    \
        )                   \
    ) *.95 + .005,        \
    asplit[a][out1];        \
    color=c=red:s=200x60, hue=H=mod(t\,4)*1.7[c];
    [a]volume=0.5,showwaves=s=$size:mode=line, \
    drawtext=fontsize=30:fix_bounds=1:fontcolor=#ffffff:fontfile=$font:y=15:text='%{pts\:hms}'[wave]; \
    [wave][c]overlay=W/2-100:5:enable=lte(mod(t\,1)\,$DURATION)[out0]"
