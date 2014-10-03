#!/bin/bash
# Script to generate thumbnails with filters.

file=$1

fps="1/10"
s1="scale=1280:-1"
s2="scale=640:-1"
s3="scale=176:-1"

ffmpeg -v 99 -y -re -i "$file" -an -filter_complex " \
    [0:v]fps=$fps, split=3[sp1][sp2][sp3]; \
    [sp1] $s1 [out1]; \
    [sp2] $s2 [out2]; \
    [sp3] $s3 [out3]" \
    -map "[out1]" -update 1 "$file"-t1.jpg \
    -map "[out2]" -update 1 "$file"-t2.jpg \
    -map "[out3]" -update 1 "$file"-t3.jpg