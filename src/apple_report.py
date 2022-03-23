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

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, QThread
import os
import logging
from os.path import join as pj
from os.path import dirname, basename, isfile, abspath
from time import strftime
from datetime import datetime
import webbrowser as wb
import sqlite3
import glob
import re
import pandas as pd
import codecs
import base64
from io import BytesIO
import plistlib

from src import extract_archive, ccl_bplist
from src.utils import resource_path, decode_bplist, refresh_temp_dir, clean_path, dictionary_recursor

with open(resource_path('EULA_short.txt'), 'r') as f:
    short_eula = f.read()


class MakeAppleReport(QWidget):
    def __init__(self, maingui, archive, report_dir, temp_out):
        super(MakeAppleReport, self).__init__(parent=maingui)
        self.maingui = maingui
        self.archive = archive
        self.main_table_name = ''
        self.save_dir = temp_out
        self.report_dir = report_dir
        self._init_archive_extraction(self.save_dir, archive)

    def _finished_archive_extraction(self, txt):
        # Process the salient files and build our dataframes
        self.maingui.status_lbl.setText('{}'.format(txt))
        try:
            self.photossqlitedb = [pj(dirpath, filename) for dirpath, _, filenames in os.walk(self.save_dir)
                                   for filename in filenames if filename == 'Photos.sqlite'][0]
        except IndexError as err:
            logging.info('ERROR - Photos.sqlite is missing. {}'.format(err))
            self.photossqlitedb = None

        try:
            self.storeclouddb = [pj(dirpath, filename) for dirpath, _, filenames in os.walk(self.save_dir)
                                 for filename in filenames if filename == 'store.cloudphotodb'][0]
        except IndexError as err:
            logging.info(err)
            self.storeclouddb = None

        if self.photossqlitedb:
            photos_df = pd.DataFrame()  # create an empty dataframe
            photodata_dir = dirname(abspath(self.photossqlitedb))
            cloudstore_df = self.build_cloud_store_dataframe()
            thumbnail_fn = self.parse_thumb_config(photodata_dir)
            try:
                photos_df = self.build_photos_dataframe()
                self.row_count = len(photos_df.Filename)
            except Exception as err:
                logging.error(err)
            
            if not photos_df.empty:
                self._init_thread(photos_df, self.archive, thumbnail_fn, photodata_dir, cloudstore_df)
            else:
                self.maingui.reset_widgets()
                err = 'Error - The photos.sqlite dataframe is empty\n\nIt is possible that mift is not ' \
                      'compatible with this version of iOS'
                logging.error(err)
                self.maingui.output_display.insertPlainText(err)

        else:
            self.maingui.output_display.insertPlainText('Error - Cannot proceed. Cannot find photos.sqlite.'
                                                        '\n\nRefer to logs.')
            self.maingui.reset_widgets()

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _init_archive_extraction(self, save_dir, archive):
        self._extract_archive_thread = extract_archive.ExtractArchiveThread(self,
                                                                            [clean_path(pj('Thumbnails', 'V2'))],
                                                                            save_dir,
                                                                            archive,
                                                                            maintain_dir_structure=True,
                                                                            key_dir='PhotoData')
        self._extract_archive_thread.progressSignal.connect(self._progress_archive_extraction)
        self._extract_archive_thread.finishedSignal.connect(self._finished_archive_extraction)
        self._extract_archive_thread.start()

    @staticmethod
    def parse_thumb_config(photodata_dir):  # get the name of the thumbnail e.g. 5005 or 5003
        try:
            with open(pj(photodata_dir, 'Thumbnails', 'thumbnailConfiguration'), 'rb') as thumb_config:
                thumbnail_config_dict = plistlib.load(thumb_config)
            return '{}.jpg'.format(thumbnail_config_dict['PLThumbnailManagerThumbnailFormatKey'])
        except:
            thm = glob.glob(photodata_dir+'/Thumbnails/V2/DCIM/*/*/*.JPG')[0]
            if thm:
                logging.info('The thumbnail basename is: {}'.format(basename(thm)))
                return basename(thm)
            else:
                logging.info('Unknown thumbnail basename! Defaulting to: 5003.jpg')
                return '5003.jpg'

    def build_cloud_store_dataframe(self):
        if self.storeclouddb:
            conn = sqlite3.connect(self.storeclouddb)
            cursor = conn.cursor()
            query = """SELECT identifier, relatedIdentifier, quote(serializedRecord) AS RECORD FROM cloudCache"""
            cloudstore_df = pd.read_sql_query(query, conn)
            cursor.close()
            conn.close()
            return cloudstore_df
        else:
            return None

    def build_photos_dataframe(self):
        with open(resource_path('photos_sqlite_query.txt'), 'r') as psq:
            sql_query = psq.read().strip('\n')

        self.maingui.status_lbl.setText('Parsing photos.sqlite...')
        try:
            conn = sqlite3.connect(self.photossqlitedb)
            cursor = conn.cursor()
        except:
            raise Exception('Could not connect to the photos.sqlite database')

        # check if iOS 12/13 or iOS 14. iOS 14 uses the table named ZASSET, whilst iOS 12/13 uses ZGENERICASSET
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = [i[0] for i in cursor]
        if 'ZGENERICASSET' not in tables:  # iOS 14
            logging.info('Detected Version of iOS >= 14. ZASSET is the main table.')
            sql_query = sql_query.replace('#MAIN_ASSET_TABLE#', 'ZASSET')
            self.main_table_name = 'ZASSET'
        else:  # iOS 12/13
            logging.info('Detected Version of iOS < 14. ZGENERICASSET is the main table.')
            sql_query = sql_query.replace('#MAIN_ASSET_TABLE#', 'ZGENERICASSET')
            self.main_table_name = 'ZGENERICASSET'

        # iOS versions interchange the table ZSHARE and ZMOMENTSHARE. Their cols are the same, just their name changes.
        if 'ZSHARE' not in tables:
            logging.info('ZMOMENTSHARE in use, not ZSHARE')
            sql_query = sql_query.replace('#SHARE_TABLE#', 'ZMOMENTSHARE')
        else:
            logging.info('ZSHARE in use, not ZMOMENTSHARE')
            sql_query = sql_query.replace('#SHARE_TABLE#', 'ZSHARE')

        cursor.execute("PRAGMA table_info(ZADDITIONALASSETATTRIBUTES)")
        if 'ZCREATORBUNDLEID' not in cursor.fetchall():  # iOS_15 uses ZIMPORTEDBYBUNDLEIDENTIFIER
            sql_query = sql_query.replace('ZCREATORBUNDLEID', 'ZIMPORTEDBYBUNDLEIDENTIFIER')

        #cursor.execute("PRAGMA table_info(ZMOMENT)")
        #if 'ZSUBTITLE' not in cursor.fetchall():
            #sql_query = sql_query.replace('ZMOMENT.ZSUBTITLE AS Moment_Subtitle,', '')

        #cursor.execute("PRAGMA table_info(ZMOMENTLIST)")
        #if 'ZREVERSELOCATIONDATA' not in cursor.fetchall():
            #sql_query = sql_query.replace(',quote(ZMOMENTLIST.ZREVERSELOCATIONDATA) AS Moment_Location', '')

        # Apple alters the digits that prefix the "Z_[1-9][1-9]ASSET" table and its embedded columns
        # We need to find out what these digits are before executing our main query
        asset_table = None
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name GLOB 'Z_[0-9]ASSETS'")
            asset_table = cursor.fetchone()[0]
            cursor.execute('SELECT * FROM {}'.format(asset_table))
        except:
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name GLOB 'Z_[0-9][0-9]ASSETS'")
            asset_table = cursor.fetchone()[0]
            cursor.execute('SELECT * FROM {}'.format(asset_table))
        if not asset_table:
            raise Exception('Error - Unable to read Asset table. Unknown table state.')

        column_names = [description[0] for description in cursor.description]
        r = re.compile(r"Z_\d{1,2}ASSETS")  # regex for 1 or 2 digits
        asset_column = list(filter(r.match, column_names))[0]
        r = re.compile(r".*ALBUMS")
        album_column = list(filter(r.match, column_names))[0]

        # make our replacements
        sql_query = sql_query.replace('#ASSETS_TABLE#', asset_table)
        sql_query = sql_query.replace('#ASSETS_COLUMN#', asset_column)
        sql_query = sql_query.replace('#ALBUM_COLUMN#', album_column)

        photos_df = pd.read_sql_query(sql_query, conn)
        self.maingui.status_lbl.setText('Successfully converted photos.sqlite to dataframe!')

        # remove any floating NaN values from out dataframe
        for col in ['Play_Count', 'View_Count', 'Share_Count', 'Height', 'Width', 'FileSize']:
            photos_df[col] = photos_df[col].fillna(0).astype('int')

        cursor.close()
        conn.close()
        return photos_df

    def _progress_report(self, value):
        self.maingui.progress_bar.setValue(value)

    def _status_report(self, msg):
        self.maingui.status_lbl.setText(msg)

    def _finished_report(self, report_path):
        self.maingui.progress_bar.setValue(self.row_count)
        self.maingui.output_display.clear()
        self.maingui.status_lbl.setText('Report generated successfully!')
        self.maingui.finished_btn.show()
        wb.open(report_path)

    def _init_thread(self, photos_df, archive, thumbnail_fn, photodata_dir, cloudstore_df):
        self.maingui.progress_bar.show()
        for btn in [self.maingui.select_datadir_btn, self.maingui.select_sony_btn, self.maingui.select_samsung_btn,
                    self.maingui.select_huawei_btn, self.maingui.select_ios_photos_btn,
                    self.maingui.select_ios_snapshots_btn]:
            btn.hide()
        self.maingui.progress_bar.setMaximum(self.row_count)
        self.maingui.progress_bar.setValue(0)
        self._thread = MakeAppleReportThread(self, photos_df, self.photossqlitedb, archive, thumbnail_fn,
                                             photodata_dir, cloudstore_df, self.report_dir)
        self._thread.progressSignal.connect(self._progress_report)
        self._thread.statusSignal.connect(self._status_report)
        self._thread.finishedSignal.connect(self._finished_report)
        self._thread.start()


class MakeAppleReportThread(QThread):
    finishedSignal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)
    statusSignal = pyqtSignal(str)

    def __init__(self, parent, *args):
        QThread.__init__(self, parent)
        self.photos_df = args[0]
        self.photos_sqlite_db = args[1]
        self.archive = args[2]
        self.thumbnail_fn = args[3]
        self.photodata_dir = args[4]
        self.cloudstore_df = args[5]
        self.report_dir = args[6]

        self.date = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reports_dir = pj(self.report_dir, 'Apple_Report_{}'.format(self.date))
        os.makedirs(self.reports_dir, exist_ok=True)
        self.excel_report = pj(self.reports_dir, 'photosqlite_{}.xlsx'.format(self.date))

    @staticmethod
    def get_address(hex_string):
        if hex_string != 'NULL':
            obj_nk = decode_bplist(hex_string, hxd=True)
            try:
                address = ''
                for part in ['_street', '_city', '_postalCode', '_country']:
                    address += '{} '.format(obj_nk['root']['postalAddress'][part])
                return address
            except:
                return 'unknown'
        else:
            return 'NULL'

    def get_cloud_information(self):
        cloud_user_details = ''

        info_plist = glob.glob(self.photodata_dir + '/PhotoCloudSharingData/*/*/info.plist')
        if info_plist and isfile(info_plist[0]):
            with open(info_plist[0], 'rb') as info_f:
                plist_data = plistlib.load(info_f)

            required = ['cloudOwnerEmail', 'cloudOwnerFirstName', 'cloudOwnerLastName']
            for k, v in plist_data.items():
                if k in required:
                    cloud_user_details += '{}: {}<br /r>'.format(k, v)

        if isfile(pj(self.photodata_dir, 'cpl_enabled_marker')):
            with open(pj(self.photodata_dir, 'cpl_enabled_marker'), 'r') as cpl_enabled_f:
                cloud_user_details += 'Cloud Enabled Timestamp: {}<br /r>'.format(cpl_enabled_f.readline().strip())

        if isfile(pj(self.photodata_dir, 'cpl_download_finished_marker')):
            with open(pj(self.photodata_dir, 'cpl_download_finished_marker'), 'r') as cpl_download_f:
                cloud_user_details += 'Cloud Last Synced: {}<br /r>'.format(cpl_download_f.readline().strip())

        return cloud_user_details

    @staticmethod
    def get_file_metatdata(hex_string):  # from cloud bplist ZCLOUDMASTERMEDIAMETADATA.ZDATA
        info = ''
        try:
            file_metadata_dict = plistlib.loads(codecs.decode(hex_string[2:-1], 'hex'))
            wanted_keys = ['Make', 'Model', 'Software', 'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
                           'LensModel', 'Latitude', 'Longitude', 'Altitude', 'PixelWidth', 'PixelHeight',
                           'ColorModel', 'name']

            for key, value in dictionary_recursor(file_metadata_dict):
                if key in wanted_keys:
                    info += '<strong>{}:</strong> {}<br /r>'.format(key, value)
        except:
            pass

        return info

    def parse_cloud_owner(self, row):
        cloud_owner = ''

        if len(self.cloudstore_df) > 0:
            for cloud_row in self.cloudstore_df.itertuples():
                if cloud_row.relatedIdentifier == row.Master_Fingerprint:
                    try:
                        d = ccl_bplist.load(BytesIO(codecs.decode(cloud_row.RECORD[2:-1], 'hex')))
                        cloud_owner += '{}'.format(ccl_bplist.load(BytesIO(d['p']['anch']))['p']['ckmd'])
                        break
                    except Exception as e:
                        logging.error('Master Fingerprint: {} - error '
                                      'identifying cloud ownership - might not be an owner - {}'.format(row.Master_Fingerprint, e))
                        pass
        return cloud_owner

    @staticmethod
    def parse_adjustment_info(row):
        adjustment_info = ''
        if row.Adjusted == 'Yes':
            adjustment_info += '{}'.format(row.Adjusted)
            if row.Adjustment_Package:
                adjustment_info += '<br /r><strong>Adjustment Package:<br /r></strong> {}<br /r>{} ({})<br /r>' \
                                   '<strong>Adjusted Timestamp:</strong> {}'.format(row.Adjustment_Package,
                                                                                    row.Adjustment_Format_ID,
                                                                                    row.Adjustment_Format_Name,
                                                                                    row.Adjusted_Timestamp)
        return adjustment_info

    '''
    @staticmethod
    def parse_memories(row):  # not used
        memory_info = ''
        if row.Memory_Title:
            memory_info += '<strong>Memory</strong><br /r>' \
                           '<strong>Title: </strong>{}<br /r>' \
                           '<strong>Created: </strong>{}<br /r>' \
                           '<strong>Last Viewed: </strong>{}<br /r>'.format(row.Memory_Title,
                                                                            row.Memory_Creation_Timestamp,
                                                                            row.Memory_Last_Viewed_Date)
        return memory_info

    def parse_moments(self, row):  # not used
        moments_info = '<strong>Moment</strong><br /r>' \
                       '<strong>Title: </strong>{}<br /r>' \
                       '<strong>Start/End: </strong>{}<strong> - </strong>{}</strong><br /r>' \
                       '<strong>GPS: </strong>{}, {}'.format(row.Moment_Title,
                                                             row.Moment_Start_Date,
                                                             row.Moment_End_Date,
                                                             row.Moment_Latitude,
                                                             row.Moment_Longitude)
        try:
            moments_info += '<br /r><strong>Moment Reverse ' \
                            'Location:</strong> {}<br /r>'.format(self.get_address(row.Moment_Location))
        except:
            moments_info += '<br /r>'

        return moments_info
    '''

    @staticmethod
    def parse_album_info(row):
        album_info = ''
        if row.Album_Title:
            album_info += '<strong>Name:</strong> {}<br /r>' \
                          '<strong>Album (Cloud State):</strong> {}'.format(row.Album_Title,
                                                                            row.Album_Local_Cloudstate)
            if row.Invitee_Fullname:
                album_info += '<br /r><strong>Album Shared With: </strong>{}  {}'.format(row.Invitee_Fullname,
                                                                                         row.Invitee_Invited_Date)
            else:
                album_info += '<br /r><br /r><br /r>'
        else:
            album_info += '<br /r><br /r><br /r><br /r>'
        return album_info

    @staticmethod
    def parse_share_details(row):
        share_details = ''
        try:
            if row.Shared_URL:
                share_details += '<strong>URL:</strong> {}<br /r>' \
                                 '<strong>From:</strong> {}<br /r>' \
                                 '<strong>Expires:</strong>{}'.format(row.Shared_URL, row.Shared_From, row.Shared_Ends)
        except Exception:
            share_details += 'None'

    def create_html(self, count, total):
        html_reportname = abspath(pj(self.reports_dir, 'Apple_Photos_Report_{}.html'.format(count)))
        outfile = open(html_reportname, 'wb')

        s = """<!DOCTYPE html><head><meta http-equiv="content-type" content="text/html;charset=utf-8" /><style>
            p.a {
              font-family: "Segoe UI";
            }
            img {
                object-fit: cover;
                width: 300px;
                height: 100%;
                object-fit: cover;
            }

            .grid-container {
                display: grid; 
                grid-template-areas:
                    'pic f_prop_head f_prop_head add_prop_head add_prop_head cl_prop_head cl_prop_head'
                    'pic f_prop_lbl f_prop_val add_prop_lbl add_prop_val cl_prop_lbl cl_prop_val'
                    'pic f_prop_lbl f_prop_val add_prop_lbl add_prop_val cl_prop_lbl cl_prop_val';
                grid-gap: 15px;
                padding: 5px;
                font-family: "Segoe UI";
                font-size: 12px;
                text-align: left;
                background-color: white;
                border: 1px solid black;
            }

            .pic_ { grid-area: pic; }
            .prop_head { grid-area: f_prop_head; }
            .prop_lbl { grid-area: f_prop_lbl; }
            .prop_val { grid-area: f_prop_val; }
            .ad_prop_head { grid-area: add_prop_head; }
            .ad_prop_lbl { grid-area: add_prop_lbl; }
            .ad_prop_val { grid-area: add_prop_val; }
            .cloud_head { grid-area: cl_prop_head; }
            .cloud_lbl { grid-area: cl_prop_lbl; }
            .cloud_val { grid-area: cl_prop_val; }

            </style>
            </head>
            <body>"""
        outfile.write(str.encode(s))
        s = """<p class="a"><span style="font-weight:bold; font-size:30px">Apple Photos Artefact Report {}/{}</span>
        <br /r><span style="font-weight:bold; font-size:12px">Photos.sqlite Database: {}<br />Report Date: {}
        <br /r><br />{}<br /></span></p>""".format(count, total, self.photos_sqlite_db, self.date,
                                                   self.get_cloud_information())
        outfile.write(str.encode(s))
        return outfile

    def run(self):
        self.photos_df.to_excel(self.excel_report)

        self.row_count = len(self.photos_df.Filename)
        self.statusSignal.emit('Generating HTML report ({} entries)...'.format(self.row_count))
        report_split_count = int(self.row_count / 500)

        for count in range(0, report_split_count + 1):
            outfile = self.create_html(count, report_split_count)
            row_position = count * 500
            for row in self.photos_df.iloc[row_position:row_position + 500].itertuples():
                self.progressSignal.emit(1)
                # lets use the thumbnails to display the image and the videos in the html report. Apple have already
                # converted the HEIF files to JPGs and they are good quality.
                thumbnail_path_absolute = pj(self.photodata_dir, 'Thumbnails',
                                             'V2', dirname(row.Directory),
                                             basename(row.Directory),
                                             row.Filename,
                                             self.thumbnail_fn)

                if isfile(thumbnail_path_absolute):
                    thmb_data = open(thumbnail_path_absolute, 'rb').read()
                else:
                    thmb_data = open(resource_path('blank_jpeg.jpg'), 'rb').read()
                thmb_b64 = base64.b64encode(thmb_data)
                # now we can embed the thumbnail in our report so it is portable.
                thmb_b64 = thmb_b64.decode()



                main_body = ("""<div class="grid-container">
                                    <div class="pic_">
                                        <img src="data:image/jpeg;base64,{}" alt="img";padding: 0px 10px 10px 0px;">
                                    </div>

                                    <div class="prop_head">
                                        <span style="font-weight:bold; font-size:20px">File Properties</span>
                                    </div>

                                    <div class="prop_lbl">
                                        <strong>Current Filename:</strong><br/r>
                                        <strong>Folder Path:</strong><br/r>
                                        <strong>Original Filename:</strong><br/r><br/r>
                                        <strong>Imported By:</strong><br /r>
                                        <strong>Parent Application:</strong><br/r>
                                        <strong>File Type:</strong><br /r>
                                        <strong>Orientation:</strong><br /r>
                                        <strong>Duration:</strong><br /r>
                                        <strong>Playback Style:</strong><br /r>
                                        <strong>File Size:</strong><br /r>
                                        <strong>Dimensions:</strong><br /r><br /r>
                                        <strong>Thumbnail Index:</strong><br /r>
                                        <strong>Thumbnail Filename:</strong><br /r><br /r>
                                        <strong>Created Timestamp:</strong><br /r>
                                        <strong>Modified Timestamp:</strong><br /r>
                                        <strong>Added Timestamp:</strong><br /r>
                                        <strong>EXIF Timestamp:</strong><br /r><br /r>
                                        <strong>Geo-Coords:</strong><br /r>
                                        <strong>Location Lookup:</strong><br /r>
                                        <strong>Original Hash:</strong>	
                                    </div>

                                    <div class="prop_val">
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {} seconds<br /r>
                                        {}<br /r>
                                        {}b  [{}]<br /r>
                                        {} x {}<br /r><br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}, {}<br /r>
                                        {}<br /r>
                                        {}
                                    </div>

                                    <div class="ad_prop_head">
                                        <span style="font-weight:bold; font-size:20px">Additional Properties</span>
                                    </div>

                                    <div class="ad_prop_lbl">
                                        <strong>Album:</strong><br /r><br /r><br /r><br /r>
                                        <strong>Trash State:</strong><br /r>
                                        <strong>Trashed Date:</strong><br /r><br /r>
                                        <strong>Hidden:</strong><br /r>
                                        <strong>Favourite:</strong><br /r>
                                        <strong>View Count:</strong><br /r>
                                        <strong>Play Count:</strong><br /r><br /r>	
                                        <strong>Adjustment/Mutation:</strong><br /r><br /r><br /r><br /r>		
                                    </div>

                                    <div class="ad_prop_val">
                                        {}
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}
                                    </div>

                                    <div class="cloud_head">
                                        <span style="font-weight:bold; font-size:20px">Cloud Properties</span>
                                    </div>

                                    <div class="cloud_lbl">
                                        <strong>Cloud State:</strong><br /r>
                                        <strong>Saved Asset Type:</strong><br /r>
                                        <strong>Share Count:</strong><br /r>
                                        <strong>Share Details:</strong><br /r><br /r>
                                        <strong>Cloud Owner:</strong><br /r><br /r><br /r>
                                        <strong>Cloud Fingerprint:</strong><br /r><br /r><br /r>
                                        <strong>Recovered Cloud Metadata</strong><br /r><br /r>
                                    </div>

                                    <div class="cloud_val">
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}<br /r><br /r><br /r>
                                        {}<br /r><br /r><br /r>
                                        {}
                                    </div>
                                </div>""".format(
                    thmb_b64,
                    row.Filename,
                    row.Directory,
                    row.Original_Filename,
                    row.Imported_Via,
                    row.Application_Package,
                    row.FileType,
                    row.Orientation,
                    int(row.Duration),
                    row.Play_Back_Style,
                    row.FileSize, row.FileSize_MB,
                    int(row.Height), int(row.Width),
                    row.Thumbnail_Index,
                    self.thumbnail_fn,
                    row.Created_Date,
                    row.Modified_Date,
                    row.Added_Date,
                    row.EXIF_Timestamp,
                    row.Latitude, row.Longitude,
                    self.get_address(row.Location_Lookup),
                    row.Original_Hash if row.Original_Hash else '',
                    self.parse_album_info(row),
                    row.Trashed_State,
                    row.Trashed_Date,
                    row.Hidden,
                    row.Favourited,
                    str(int(row.View_Count)),
                    str(int(row.Play_Count)),
                    self.parse_adjustment_info(row),
                    row.File_Local_Cloudstate,
                    row.Saved_Asset_Type,
                    str(int(row.Share_Count)),
                    self.parse_share_details(row),
                    self.parse_cloud_owner(row),
                    row.Master_Fingerprint,
                    self.get_file_metatdata(row.Cloud_Media_Metadata)))
                outfile.write(str.encode(main_body))

            end = """<p class="a"></br></br></br></br>{}</p></body></html>""".format(short_eula)
            outfile.write(str.encode(end))
            outfile.close()

        refresh_temp_dir()
        logging.info('Report successfully generated: {}'.format(self.reports_dir))
        self.finishedSignal.emit(self.reports_dir)
