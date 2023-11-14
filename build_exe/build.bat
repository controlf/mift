@echo off
echo -------------------------------------------
echo Control-F 2022 - Binary Concat
echo -------------------------------------------
echo Due to Github file size restrictions, the executable for this program has been broken into chunks_ This script will rebuild the executable from the chunks found in the build_exe directory (in order).
echo -------------------------------------------
COPY /B mift_0 + mift_1 + mift_2 + mift_3 + mift_4 + mift_5 + mift_6 + mift_7 + mift_8 + mift_9 + mift_10 + mift_11 + mift_12 + mift_13 + mift_14 + mift_15 + mift_16 + mift_17 + mift_18 + mift_19 mift.exe
echo -------------------------------------------
echo Finished!