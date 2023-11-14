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

from PyQt5.QtCore import pyqtSignal, QThread
import os
import logging
from os.path import join as pj
from os.path import *
from time import strftime
import sqlite3
import glob
import re
import pandas as pd
import codecs
import base64
from io import BytesIO
import plistlib

from src import extract_archive, ccl_bplist
from src.utils import resource_path, decode_bplist, refresh_temp_dir, clean_path, dictionary_recursor, row_combiner


# Dictionary for storing columns we want to combine prior to dataframe creation
combiner_dict = {'File Info': {'Filename': 'Filename', 'Original_Filename': 'Original Filename', 
                               'Directory': 'Dir', 'FileType': 'Mime Type', 'FileSize': 'Size', 
                               'FileSize_MB': 'Size (MB)', 'Width': 'Width', 'Height': 'Height',
                               'Play_Back_Style': 'Playback', 'Orientation': 'Orientation', 
                               'Duration': 'Duration', 'Original_Hash': 'Original Hash'},
                 'Other': {'Application_Package': 'App', 'Imported_Via': 'Imported Via'},
                 'Timestamps': {'Created_Date': 'Created', 'Modified_Date': 'Modified', 
                                'EXIF_Timestamp': 'Exif', 'Added_Date': 'Added', 'Timezone': 'Timezone'},
                 'Location': {'Latitude': 'Lat', 'Longitude': 'Long',
                              'Location Lookup': 'Location Lookup', 'Location_Lookup_Validity': 'Location Valid'},
                 'Album': {'Album_Title': 'Title', 'Album_Local_Cloudstate': 'Album Cloud State'},
                 'Trash': {'Trashed_State': 'State', 'Trashed_Date': 'Date'},
                 'Activity': {'Hidden': 'Hidden', 'Share_Count': 'Share Count', 'View_Count': 'View Count', 
                              'Play_Count': 'Play Count', 'Favourited': 'Favourite', 'Sharing': 'Sharing Info'},
                 'Adjustments/Mutations': {},
                 'Cloud MetaData': {},
                 'iCloud': {'Cloud_Placeholder': 'Placeholder Quality', 
                            'File_Local_Cloudstate': 'Cloud State', 'Saved_Asset_Type': 'Assets Origin',
                            'Cloud Owner': 'Cloud Owner', 'Master_Fingerprint': 'Cloud Fingerprint'}}

with open(resource_path('EULA_short.txt'), 'r') as f:
    short_eula = f.read()


def parse_cloud_owner(row, cloudstore_df, col='Master_Fingerprint'):
    cloud_owner = ''
    for cloud_row in cloudstore_df.itertuples():
        # if relatedIdentifier == MasterFingerprint
        if cloud_row.relatedIdentifier == row[col]:
            try:
                d = ccl_bplist.load(BytesIO(codecs.decode(cloud_row.RECORD[2:-1], 'hex')))
                cloud_owner += '{}'.format(ccl_bplist.load(BytesIO(d['p']['anch']))['p']['ckmd'])
            except Exception as e:
                logging.error('Master Fingerprint: {} - error '
                              'identifying cloud ownership - might not be an owner - {}'.format(row[col], e))
                pass
    return cloud_owner


def parse_adjustment_info(row):
    adjustment_info = ''
    if row.Adjusted == 'Yes':
        for n, col in {'Package': 'Adjustment_Package', 'Format ID': 'Adjustment_Format_ID',
                       'Format Name': 'Adjustment_Format_Name', 'Timestamp': 'Adjusted_Timestamp'}.items():
            try:
                adjustment_info += '{}: {}\n'.format(n, row[col])
            except:
                pass
    return adjustment_info


def parse_album_info(row):
    album_info = ''
    if row.Album_Title:
        for new, col_name in {'Title': 'Album_Title', 'Cloud State': 'Album_Local_Cloudstate',
                              'Shared With': 'Invitee_Fullname', 'Shared Date': 'Invitee_Invited_Date'}.items():
            try:
                if row[col_name]:
                    album_info += '{}: {}\n'.format(new, row[col_name])
            except:
                pass
    return album_info


def parse_share_details(row):
    share_details = ''
    if row.Shared_URL:
        for share_item, col_name in {'URL': 'Shared_URL', 'Start': 'Shared_From', 'End': 'Shared_Ends'}.items():
            try:
                if row[col_name]:
                    share_details += '{}: {}\n'.format(share_item, row[col_name])
            except Exception:
                pass
    return share_details


def get_cloud_metatdata(row, col='Cloud_Media_Metadata'):
    # from cloud bplist ZCLOUDMASTERMEDIAMETADATA.ZDATA
    hex_string = row[col]
    info = ''
    try:
        file_metadata_dict = plistlib.loads(codecs.decode(hex_string[2:-1], 'hex'))
    except:
        return info

    if file_metadata_dict.keys():
        wanted_keys = ['Make', 'Model', 'Software', 'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
                       'LensModel', 'Latitude', 'Longitude', 'Altitude', 'PixelWidth', 'PixelHeight',
                       'ColorModel', 'name']

        for key, value in dictionary_recursor(file_metadata_dict):
            if key in wanted_keys:
                info += '{}: {}\n'.format(key, value)

    return info


def get_address(row, col='Location_Lookup'):
    hex_string = row[col]
    address = ''
    if hex_string != 'NULL':
        try:
            obj_nk = decode_bplist(hex_string, hxd=True)
        except ValueError:
            return address
        for part in ['_street', '_city', '_postalCode', '_country']:
            try:
                p = '{}\n'.format(obj_nk['root']['postalAddress'][part])
                if p != '$null\n':
                    address += p
            except Exception as e:
                pass
    return address


class MakeAppleReport(QThread):
    finishedSignal = pyqtSignal(object)
    progressSignal = pyqtSignal(list)

    def __init__(self, *args):
        QThread.__init__(self, args[0])
        self.tab_widget, self.maingui, self.archive, self.save_dir = args

    def run(self):
        extract_instance = extract_archive.ExtractArchive(self,
                                                          [clean_path(pj('Thumbnails', 'V2'))],
                                                          self.save_dir,
                                                          self.archive,
                                                          maintain_dir_structure=True,
                                                          key_dir='PhotoData')
        out = extract_instance.extract()
        self.progressSignal.emit([100, out])
        
        res = self.build_dataframes()
        if res:
            photos_df, cloudstore_df, thumbnail_fn, photodata_dir = res
            photos_df = self.thumbnail_path(photos_df, photodata_dir, thumbnail_fn)
            photos_df = self.parse_blob_data(photos_df, cloudstore_df)

            photos_df = self.rename_columns(photos_df)

            photos_df = self.combiner(photos_df)
            photos_df = self.drop_columns(photos_df)

            reordered_cols = ['media']
            reordered_cols.extend(combiner_dict.keys())
            photos_df = photos_df[reordered_cols]
            # Drop duplicate columns
            photos_df = photos_df.loc[:, ~photos_df.columns.duplicated()].copy()
            self.finishedSignal.emit(photos_df)
        else:
            self.finishedSignal.emit(pd.DataFrame())

    def combiner(self, photos_df):
        for new_col_name, col_dict in combiner_dict.items():
            cols = col_dict.values()
            if cols:
                combined = list()
                for idx, row in photos_df.iterrows():
                    combined.append(row_combiner(row, cols))
                photos_df[new_col_name] = combined
                # Drop the columns we have merged
                photos_df.drop(cols, axis=1, inplace=True)

        return photos_df

    def rename_columns(self, photos_df):
        d = dict()
        for col, attributes in combiner_dict.items():
            d.update(attributes)

        photos_df.rename(columns=d, inplace=True)
        return photos_df

    def drop_columns(self, photos_df):
        unwanted_cols = ['Album_Title', 'Album_Local_Cloudstate', 'Invitee_Fullname', 'Invitee_Invited_Date',
                         'Shared_URL', 'Shared_From', 'Shared_Ends', 'Location_Lookup', 'Cloud_Media_Metadata',
                         'Adjusted', 'Adjustment_Package', 'Adjustment_Format_ID', 'Adjustment_Format_Name',
                         'Adjusted_Timestamp', 'Cloud_File_Is_My_Asset', 'Cloud_File_Can_Be_Deleted',
                         'Shared_Thumbnail_BLOB', 'Thumbnail_Index']
        for col in unwanted_cols:
            try:
                photos_df.drop(col, axis=1, inplace=True)
            except:
                pass
        return photos_df

    def parse_blob_data(self, photos_df, cloudstore_df):
        func_dict = {'Location Lookup': get_address,
                     'Cloud MetaData': get_cloud_metatdata,
                     'Sharing': parse_share_details,
                     'Album': parse_album_info,
                     'Adjustments/Mutations': parse_adjustment_info
                     }
        for new_col_name, func in func_dict.items():
            col = list()
            for idx, row in photos_df.iterrows():
                col.append(func(row))
            photos_df[new_col_name] = col

        # cloud owner column
        if len(cloudstore_df.index) > 0:
            owner_col = list()
            for idx, row in photos_df.iterrows():
                owner_col.append(parse_cloud_owner(row, cloudstore_df))
            photos_df['Cloud Owner'] = owner_col
        else:  # must be empty (cloud not set up)
            photos_df['Cloud Owner'] = ''

        return photos_df

    def thumbnail_path(self, photos_df, photodata_dir, thumbnail_fn):
        thumbnail_col = list()
        total_rows = len(photos_df.index)
        count = 0
        for row in photos_df.itertuples():
            thumbnail_path_absolute = pj(photodata_dir, 'Thumbnails',
                                         'V2', dirname(row.Directory),
                                         basename(row.Directory),
                                         row.Filename,
                                         thumbnail_fn)
            renamed_thumb = abspath(dirname(thumbnail_path_absolute) +'.jpg')
            thumbnail_col.append(renamed_thumb)
            
            if isfile(thumbnail_path_absolute):
                os.rename(thumbnail_path_absolute, renamed_thumb)
            else:
                logging.error('Dump file is missing {}'.format(thumbnail_path_absolute))

            count += 1
            self.progressSignal.emit([int(count/total_rows*100), thumbnail_path_absolute])

        photos_df['media'] = thumbnail_col
        return photos_df

    def build_dataframes(self):
        try:
            # fetches the db and the wal for photos.sqlite
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
                return [photos_df, cloudstore_df, thumbnail_fn, photodata_dir]
            else:
                err = (
                    'Error - The photos.sqlite dataframe is empty\n\n'
                    'It is possible that mift is not compatible with this version of iOS')
                logging.error(err)
                self.maingui.add_log(err)
        else:
            self.maingui.add_log('Error - Cannot proceed. Cannot find photos.sqlite.\n\nRefer to logs.')

    def parse_thumb_config(self, photodata_dir):  # get the name of the thumbnail e.g. 5005 or 5003
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
            return pd.DataFrame()  # empty dataframe        

    def build_photos_dataframe(self):
        with open(resource_path('photos_sqlite_query.txt'), 'r') as psq:
            sql_query = psq.read().strip('\n')

        self.maingui.add_log('Parsing photos.sqlite...')
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
        tables = [i[1] for i in cursor]

        if 'ZIMPORTEDBYBUNDLEIDENTIFIER' in tables:  # iOS_15 uses ZIMPORTEDBYBUNDLEIDENTIFIER
            logging.info('iOS >= 15 detected. Using ZIMPORTEDBYBUNDLEIDENTIFIER')
            sql_query = sql_query.replace('ZCREATORBUNDLEID', 'ZIMPORTEDBYBUNDLEIDENTIFIER')

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
        self.maingui.add_log('Successfully converted photos.sqlite to dataframe!')

        # remove any floating NaN values from out dataframe
        for col in ['Play_Count', 'View_Count', 'Share_Count', 'Height', 'Width', 'FileSize']:
            photos_df[col] = photos_df[col].fillna(0).astype('int')

        cursor.close()
        conn.close()
        return photos_df
