MIT License

mift - Copyright (c) 2021-2022 Control-F

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software, 'mift', and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Supports Python versions 3.6, 3.7, 3.8 & 3.9
NB: This tool currently supports iOS versions <= 15.4

'mift' (Mobile Image Forensic Toolkit) is a forensic media analysis tool 
developed by Control-F supporting artefacts for the Android and iOS operating 
systems

To install dependencies, execute 'pip install -r requirements.txt' in the root
directory of mift. To install the required modules on an offline machine, such
as a forensic workstation, use the install script in the '/offline_install'
directory. Execute with 'python install.py'. Offline install only supports 
Python 3.8 (Windows x64 build).

To build an executable file, execute 'pyinstaller spec.spec' from a command shell 
in the root directory of mift.



Contact/Author - mike.bangham@controlf.co.uk



Credits

Yogesh Khatri
https://github.com/ydkhatri/MacForensics/tree/master/IOS_KTX_TO_PNG

CCL Forensics
https://github.com/cclgroupltd/ccl-bplist

Alex Caithness - CCL Forensics - code review
