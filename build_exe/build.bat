@echo off
echo -------------------------------------------
echo Control-F 2022 - Binary Concat
echo -------------------------------------------
echo Due to Github file size restrictions, the executable for this program has been broken into chunks. This script will rebuild the executable from the chunks found in the build_exe directory (in order).
echo -------------------------------------------
COPY /B mift.0 + mift.1 + mift.2 + mift.3 + mift.4 + mift.5 + mift.6 + mift.7 + mift.8 mift.exe
echo -------------------------------------------
echo Finished!