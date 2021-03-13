#!/bin/sh
# This command omits all national flags, Fitzpatrick Scale, and male/female gender modifiers
# There isn't enough space to do them all on 2MB flash. 
# You could easily copy a few on from each if needed, 
# or you could pick a different "default set" of emojis with a specific Fitzpatrick colour
# by renaming to the "base" emoji codepoint when you copy them over.
# When the matrixportal searches for an emoji, it first looks for the full filename (all codepoints)
# but then backs off to just the part before the first hyphen (first codepoint)
# which is usually a "default" version of the emoji.

fileconvert () {
    magick $1.png -adaptive-resize 21x21 -gamma 0.55 -dither None -colors 16 - | magick - -background black -alpha remove -alpha off -colors 16 -type Palette BMP:bmps/$1.bmp
}

for FNAME in `ls -1 *.png | egrep -v -e '-1f1|-1f3f[b-f]|-264[02]-' | sed 's/.png//g'`
do
    fileconvert $FNAME
done
