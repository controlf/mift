mift v1.15

mift - a mobile image forensic toolkit
-----------------------------------------------------------------------------

Control-F   (2021-2022)

Author/Contact - mike.bangham@controlf.co.uk

-----------------------------------------------------------------------------

mift is an open source tool for a deeper analysis of media files found on Android and iOS mobile devices.

mift currently supports parsers for:

* iOS (snapshots, media) <= 15.x

* Android Recents >= Android 5

* Samsung Gallery >= Android 10

* Samsung Cache >= Android 7

* Huawei Cache >= Android 8

* Sony Cache >= Android 9

-----------------------------------------------------------------------------
Building mift

The simplest way to build mift is to build the precompiled executable from /build_exe. Due to GitHub file size restrictions, the precompiled executable: 'mift.exe' has been broken into chunks. Using the batch script in the /build_exe  directory found in the root of mift, an executable can be generated which concatenates the chunks. Otherwise, please install all the required dependencies and use the spec.spec file provided.

-----------------------------------------------------------------------------
MIT License

mift
Copyright (c) 2021-2022 Control-F

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

-----------------------------------------------------------------------------
Credits

Yogesh Khatri - KTX > PNG script/executable
https://github.com/ydkhatri/MacForensics/tree/master/IOS_KTX_TO_PNG

CCL Forensics Binary Plist Parser
https://github.com/cclgroupltd/ccl-bplist

HTML report - modified - Mike Bangham - Control-F 2021-2022
Original HTML prior to modification: Copyright (c) Facebook, Inc. and its affiliates.

HEIC to JPG - ConvertTo-Jpeg.ps1
Copyright (c) 2018-2019 David Anson - modified by Mike Bangham 2022 Control-F
