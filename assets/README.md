# assets/ -- local bundled dependencies (personal use)

These files are bundled so the installer never needs network access.

## abc2midi-src/
Minimal source subset of abcMIDI (only the files abc2midi needs).
Origin: https://github.com/sshlien/abcmidi
Build:  clang -DANSILIBS -DHAVE_CONFIG_H -O2 -I. -o abc2midi \
          parseabc.c store.c genmidi.c midifile.c queues.c \
          parser2.c stresspat.c music_utils.c -lm
To update: re-clone upstream, copy the 8 .c + their headers + config.h/sizes.h/VERSION.

## TimGM6mb.sf2
GM SoundFont (~6MB) used by timidity to render MIDI to audio.
Origin: Debian package timgm6mb-soundfont (pool.debian.org)
To update: download newer timgm6mb-soundfont_*.deb, extract usr/share/sounds/sf2/.
