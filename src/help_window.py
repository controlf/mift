"""
MIT License

mift - Copyright (c) 2021-2022 Control-F
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

__author__ = 'Mike Bangham - Control-F'
__description__ = 'Mobile Image Forensic Toolkit'

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
from os.path import join as pj
from src.utils import resource_path, transform_image


class HelpDialog(QDialog):
    def __init__(self):
        super(HelpDialog, self).__init__()
        self.setFixedSize(1900, 620)
        buttonbox = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttonbox.rejected.connect(self.reject)

        cloudmastermediametadata = 'Photos.sqlite\nZCLOUDMASTERMEDIAMETADATA.ZDATA\nMedia metadata attributed to the ' \
                                   'media file stored by the iCloud account.'
        self.helper_dict = {
            'File Properties': {
                'Current Filename': ['IMG_1123.MOV',
                                     'Photos.sqlite\nZASSET.ZFILENAME'],
                'Folder Path': ['DCIM/110APPLE',
                                'Photos.sqlite\nZASSET.ZDIRECTORY'],
                'Original Filename': ['chat-media-video-02cd54e6-3097.mov',
                                      'Photos.sqlite\nZASSET.ZORIGINALFILENAME'],
                'Imported By': ['3rd Party Package/App',
                                'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZIMPORTEDBY\n1 = Back Camera\n'
                                '2 = Front Camera\n3 = 3rd Party Package/App\n6 = 3rd Party Package/App\n'
                                '8 = System Package/App\n9 = Native Package/App'],
                'Parent Application': ['com.toyopagroup.picaboo',
                                       'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZCREATORBUNDLEID'],
                'File Type': ['Video',
                              'Photos.sqlite\nZASSET.ZKIND\n1 = Video\n0 = Image'],
                'Orientation': ['Vertical (Up)',
                                'Photos.sqlite\nZASSET.ZORIENTATION\n1 = Horizontal (Left)\n3 = Horizontal (Right)\n'
                                '6 = Vertical (Up)\n8 = Vertical (Down)'],
                'Duration': ['9 seconds',
                             'Photos.sqlite\nZASSET.ZDURATION'],
                'Playback Style': ['Video Frames',
                                   'Photos.sqlite\nZASSET.ZPLAYBACKSTYLE\n1 = Static Image\n3 = Live Image '
                                   '(embedded frames)\n4 = Video Frames'],
                'File Size': ['2514767b [2.4MB]',
                              'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZORIGINALFILESIZE'],
                'Dimensions': ['544 x 976',
                               'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZORIGINALWIDTH\n'
                               'ZADDITIONALASSETATTRIBUTES.ZORIGINALHEIGHT'],
                'Thumbnail Index': ['32',
                                    'Photos.sqlite\nZASSET.ZTHUMBNAILINDEX'],
                'Thumbnail Filename': ['5005.JPG',
                                       'PhotoData/Thumbnails/thumbnailConfiguration'],
                'Created Timestamp': ['2021-02-14 09:04:16',
                                      'Photos.sqlite\nZASSET.ZDATECREATED\nCocoa Timstamp'],
                'Modified Timestamp': ['2021-02-14 09:04:36',
                                       'Photos.sqlite\nZASSET.ZMODIFICATIONDATE\nCocoa Timstamp'],
                'Added Timestamp': ['2021-02-14 09:04:40',
                                    'Photos.sqlite\nZASSET.ZADDEDDATE\nCocoa Timstamp'],
                'EXIF Timestamp': ['2021:02:14 09:04:16',
                                   'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZEXIFTIMESTAMPSTRING\nCocoa Timstamp'],
                'Geo-Coords': ['40.7567765, -73.9870375',
                               'Photos.sqlite\nZASSET.ZLATITUDE\nZASSET.ZLONGITUDE\n'
                               'Approximate location resolved by the iOS device using the '
                               'devices internet connection.'],
                'Location Lookup': ['Times Square, Manhattan, NY 10036, United States',
                                    'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZREVERSELOCATIONDATA\n'
                                    'Approximate location resolved by the iOS device using the '
                                    'devices internet connection.'],
                'Original Hash': ['0169C10B8525E5EC8F1C568FF30BBAC83CE05EA819',
                                  'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZORIGINALHASH']},

            'Additional Properties': {
                'Album': ['USA',
                          'Photos.sqlite\nZGENERICALBUM.ZTITLE'],
                'Album (Cloud State)': ['Remote',
                                        'Photos.sqlite\nZGENERICALBUM.ZCLOUDLOCALSTATE\n'
                                        '0 = Local (Stored only on the device)\n'
                                        '1 = Remote (Is also stored in the cloud)'],
                'Trash State': ['Not Deleted',
                                'Photos.sqlite\nZASSET.ZTRASHEDSTATE\n'
                                'Can be found in the iOS Trash folder (remains for 30 days before the media is '
                                'securely deleted)'],
                'Trashed Date': ['None',
                                 'Photos.sqlite\nZASSET.ZTRASHEDDATE'],
                'Hidden': ['Yes',
                           'Photos.sqlite\nZASSET.ZHIDDEN\n0 = No\n1 = Yes'],
                'Favourite': ['No',
                              'Photos.sqlite\nZASSET.ZFAVORITE\n0 = No\n1 = Yes'],
                'View Count': ['5',
                               'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZVIEWCOUNT'],
                'Play Count': ['5',
                               'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZPLAYCOUNT'],
                '\n\nAdjusted/Mutated': ['', "iOS gives users to ability to modify and adjust captured or stored media."
                                             "This can include cropping, enhancing and converting a photo or trimming "
                                             "a video by reducing the frames. An adjusted media file can be saved as "
                                             "a new file, or in place of the existing file. The original filename and "
                                             "the adjustment details can provide insight into the previous name, the "
                                             "application used to make the adjustment and the timestamp of the "
                                             "adjustment. If the mutated version is saved a new file, the original "
                                             "file is kept in the DCIM directory while the mutated copy is stored "
                                             "in /PhotoData/Mutations/"],
                '\nAdjusted': ['\nYes',
                               'Photos.sqlite\nZASSET.ZHASADJUSTMENTS\n0 = No\n1 = Yes'],
                'Adjusted using': ['com.apple.mobileslideshow com.apple.photo (Photos)',
                                   'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZEDITORBUNDLEID\n'
                                   'ZUNMANAGEDADJUSTMENT.ZADJUSTMENTFORMATIDENTIFIER'],
                'Adjusted Timestamp': ['2021-02-26 20:14:02',
                                       'Photos.sqlite\nZUNMANAGEDADJUSTMENT.ZADJUSTMENTTIMESTAMP\nCocoa Timestamp']},

            'Cloud Properties': {
                'Cloud State': ['Remote',
                                'Photos.sqlite\nZASSET.ZCLOUDLOCALSTATE\n'
                                '0 = Local (Stored only on the device)\n'
                                '1 = Remote (Is also stored in the cloud)'],
                'Saved Asset Type': ['From Device',
                                     'Photos.sqlite\nZASSET.ZSAVEDASSETTYPE\n6 = From Cloud\n3 = From Device'],
                'Share Count': ['1',
                                'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZSHARECOUNT\nNumber of times shared with '
                                'other iCloud users or publicly'],
                'Shared URL': ['https://share.icloud.com/photos/06p9iNM-fg',
                               'Photos.sqlite\nZSHARE.ZSHAREURL'],
                'Shared From': ['2020-02-19 18:45:45',
                                'Photos.sqlite\nZSHARE.ZSTARTDATE\nCocoa Timestamp'],
                'Shared Expires': ['2021-04-19 20:18:37',
                                   'Photos.sqlite\nZSHARE.ZEXPIRYDATE\nCocoa Timestamp'],
                'Cloud Owner': ["David's iPhone",
                                'store.cloudphotodb\ncloudCache.SerializedRecord\nThe device name responsible for '
                                'primarily syncing the file to the cloud. Apple also refer to this as the Default '
                                'Owner.'],
                'File Fingerprint': ['Ad1XQdDwxuHQ5gyKNSUlkXGdQYJX',
                                     'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZMASTERFINGERPRINT'],
                '\n\nRecovered Cloud Metadata': ['', "iCloud\niCloud Photos automatically stores an original copy of "
                                                     "all user photos and videos on remote Apple servers, syncing said "
                                                     "media across all connected devices that share the same iCloud "
                                                     "account. Unless a user modifies the settings, lightweight, "
                                                     "lower resolution copies of these files are synced with said "
                                                     "devices while the originals remain on the server. iCloud offers "
                                                     "Shared Albums to users so they can share an album with selected "
                                                     "individuals. Comments can be created for media by those who have "
                                                     "shared access."],
                '\nSoftware': ['\n14.1', cloudmastermediametadata],
                'DateTime': ['2021-02-14 09:04:16', cloudmastermediametadata],
                'Model': ['iPhone 8 Plus', cloudmastermediametadata],
                'Make': ['Apple', cloudmastermediametadata],
                'DateTimeOriginal': ['2021-02-14 09:04:16', cloudmastermediametadata],
                'DateTimeDigitized': ['2021-02-14 09:04:16', cloudmastermediametadata],
                'LensModel': ['iPhone 8 Plus back dual camera 3.99mm f/1.8', cloudmastermediametadata],
                'Latitude': ['40.7567765', cloudmastermediametadata],
                'Longitude': ['-73.9870375', cloudmastermediametadata],
                'PixelHeight': ['544', cloudmastermediametadata],
                'ColorModel': ['RGB', cloudmastermediametadata],
                'PixelWidth': ['976', cloudmastermediametadata]}
                       }

        grid = QGridLayout()
        grid.setContentsMargins(1, 1, 1, 1)
        grid.addWidget(self.info_panel(), 0, 0, 1, 4)
        grid.addWidget(self.image_widget(), 1, 0, 2, 1)
        grid.addWidget(self.file_properties_widget(), 1, 1, 2, 1)
        grid.addWidget(self.additional_properties_widget(), 1, 2, 1, 1)
        grid.addWidget(self.cloud_properties_widget(), 1, 3, 2, 1)
        self.setLayout(grid)

        self.setWindowTitle("mift Helper")
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            obj.setToolTip(obj.objectName())
        return False

    @staticmethod
    def info_panel():
        groupbox = QGroupBox()
        layout = QGridLayout()

        header = QLabel('mift - Help & Report Key\n')
        header.setFont(QFont("Consolas", 18, weight=QFont.Bold))
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)

        instructions = QLabel('Please hover over the report fields (including headers) for details regarding the '
                              'property and the database, e.g. Photos.sqlite.'
                              '\n\nWhere a database is cited, further details regarding the table '
                              'and column will be given, e.g ZASSET.ZFILENAME. If the values have been decoded, '
                              'details of the conversions made will be listed e.g Boolean values such as: 1 = Yes')
        layout.addWidget(instructions, 1, 0, 1, 1)

        groupbox.setLayout(layout)
        return groupbox

    @staticmethod
    def image_widget():
        groupbox = QGroupBox()
        layout = QGridLayout()

        img = QLabel()
        img.setPixmap(transform_image(pj(resource_path('times_square.jpg')), 600, 600))
        layout.addWidget(img, 0, 0, 1, 1, alignment=Qt.AlignTop)

        groupbox.setLayout(layout)
        return groupbox

    def file_properties_widget(self):
        groupbox = QGroupBox()
        layout = QGridLayout()
        header = QLabel('File Properties\n')
        header.setFont(QFont("Consolas", weight=QFont.Bold))
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        count = 1
        for field, details in self.helper_dict['File Properties'].items():
            field_lbl = QLabel('{}: '.format(field))
            field_lbl.setFont(QFont("Consolas", weight=QFont.Bold))
            layout.addWidget(field_lbl, count, 0, 1, 1)
            lbl = QLabel('{}'.format(details[0]))
            lbl.setObjectName(details[1])
            lbl.installEventFilter(self)
            layout.addWidget(lbl, count, 1, 1, 1)
            count += 1
        groupbox.setLayout(layout)
        return groupbox

    def additional_properties_widget(self):
        groupbox = QGroupBox()
        layout = QGridLayout()
        header = QLabel('Additional Properties\n')
        header.setFont(QFont("Consolas", weight=QFont.Bold))
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        count = 1
        for field, details in self.helper_dict['Additional Properties'].items():
            field_lbl = QLabel('{}: '.format(field))
            field_lbl.setFont(QFont("Consolas", weight=QFont.Bold))
            layout.addWidget(field_lbl, count, 0, 1, 1)
            lbl = QLabel('{}'.format(details[0]))
            lbl.setObjectName(details[1])
            lbl.installEventFilter(self)
            layout.addWidget(lbl, count, 1, 1, 1)
            count += 1
        groupbox.setLayout(layout)
        return groupbox

    def cloud_properties_widget(self):
        groupbox = QGroupBox()
        layout = QGridLayout()
        header = QLabel('Cloud Properties\n')
        header.setFont(QFont("Consolas", weight=QFont.Bold))
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        count = 1
        for field, details in self.helper_dict['Cloud Properties'].items():
            field_lbl = QLabel('{}: '.format(field))
            field_lbl.setFont(QFont("Consolas", weight=QFont.Bold))
            layout.addWidget(field_lbl, count, 0, 1, 1)
            lbl = QLabel('{}'.format(details[0]))
            lbl.setObjectName(details[1])
            lbl.installEventFilter(self)
            layout.addWidget(lbl, count, 1, 1, 1)
            count += 1
        groupbox.setLayout(layout)
        return groupbox
