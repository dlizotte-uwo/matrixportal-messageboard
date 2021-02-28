# This command omits all national flags, Fitzpatrick Scale, and male/female gender modifiers
# There isn't enough space to do them all on 2MB flash. 
# You could easily copy a few on from each if needed, 
# or you could pick a different "default set" of emojis with a specific Fitzpatrick colour
# by renaming to the "base" emoji codepoint when you copy them over.
ls -1 *.png | egrep -v -e '-1f1|-1f3f[b-f]|-264[02]-' | sed 's/.png//g' | xargs -I{} magick {}.png -gamma 0.76 -background black -alpha remove -alpha off -adaptive-resize 21x21 -colors 16 -type Palette BMP:bmps/{}.bmp
