"""
MIT License

mift - Copyright (c) 2021 Control-F
Author: Mike Bangham (Control-F)

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

"""

from time import strftime


def generate_html_grid_container(out_fn, report_name, source_file):
    outfile = open(out_fn, 'wb')
    s = """<!DOCTYPE html><head><style>
        p.a {
          font-family: "Segoe UI";
        }
        .grid-container {
            display: grid; 
            grid-template-columns: 500px auto;
            grid-template-rows: 500px auto;
            background-color: black; 
            padding: 1px;
        }
        .grid-item {
            background-color: rgba(255, 255, 255, 255);
            border: 1px solid rgba(0, 0, 0, 0);
            padding: 25px;
            font-family: "Segoe UI";
            font-size: 12px;
            text-align: left;
        }
        </style>
        </head>
        <body>"""

    outfile.write(str.encode(s))
    s = """<p class="a">
                <span style="font-weight:bold; font-size:30px">{}</span>
                <br /r><span style=font-weight:bold; font-size:12px">
                Database: '{}'<br />Report Date: {} {}<br /r><br /></span>
            </p>
            <div class="grid-container">""".format(report_name, source_file, strftime('%d-%m-%y'), strftime('%H:%M:%S'))
    outfile.write(str.encode(s))
    return outfile
