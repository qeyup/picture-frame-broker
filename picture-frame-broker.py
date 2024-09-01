#! /usr/bin/env python3
# 
# This file is part of the picture-frame-broker distribution.
# Copyright (c) 2023 Javier Moreno Garcia.
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License 
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#


import d2dcn
import argparse
import sys
import time
import os
import base64
import random
import json
import pathlib
import cv2
import threading

version = "0.2.0"

class pictureBroker():

    class field:
        IMAGE = "image"
        IMAGE_PATH = "image path"
        ID = "id"
        VERTICAL_ORIENTATION = "vertical orientation"
        INCLUDED = "include"
        EXCLUDED = "exclude"
        AVALILABLE_H_FOLDER = "available_h_folders"
        AVALILABLE_v_FOLDER = "available_v_folders"
        CONNECTED_H_FRAMES = "connected_h_frames"
        CONNECTED_V_FRAMES = "connected_v_frames"

    class param:
        GET_IMAGE_TIMEOUT = 30


    class command:
        GET_IMAGE = "getImage"

    class error:
        NOT_IMAGES_FOUND = "NOT IMAGES FOUND"


    class files:
        FB_INFO = "fbinfo.json"


    def __init__(self, root_folder, config_file):
        self.d2d = d2dcn.d2d()
        self.configCommands()

        self.__root_folder = root_folder
        self.__config_file = config_file


        self.__current_id_v_images_files = {}
        self.__current_id_h_images_files = {}

        self.__mutex = threading.RLock()
        self.__already_process = {}
        self.__available_v_images_folder = []
        self.__available_h_images_folder = []


    def __getFilesInDir(self, dir_path):

        # Get include/exclude
        try:
            folder_params = json.load(open(dir_path + "/" + pictureBroker.field.FB_INFO))
        except:
            folder_params = {}

        # Get excluded
        exclude_files = []
        if pictureBroker.field.EXCLUDED in folder_params and isinstance(folder_params[pictureBroker.field.EXCLUDED], list):
            for exclude_file in folder_params[pictureBroker.field.EXCLUDED]:
                exclude_files += pathlib.Path(dir_path).glob(exclude_file)
        else:
            exclude_files = []


        # Get included
        if pictureBroker.field.INCLUDED in folder_params and isinstance(folder_params[pictureBroker.field.INCLUDED], list):
            include_files = folder_params[pictureBroker.field.INCLUDED]
        else:
            include_files = ["*"]


        # Iterate include list
        v_res = []
        h_res = []
        for include_file in include_files:
            for file_path in pathlib.Path(dir_path).glob(include_file):

                # Get dimensions
                try:
                    img = cv2.imread(str(file_path))
                    wid = img.shape[1]
                    hgt = img.shape[0]
                    is_horizontal = wid > hgt

                except:
                    continue


                # Get list to include
                if is_horizontal:
                    used_list = h_res

                else:
                    used_list = v_res


                if os.path.isfile(file_path) and file_path not in used_list and file_path not in exclude_files:
                    used_list.append(file_path)


        # Return sorted files
        h_res.sort(reverse=True)
        v_res.sort(reverse=True)
        return v_res, h_res


    def __getAllFolders(self, path):

        # Find frame file
        folder_list = []
        for file_path in pathlib.Path(path).rglob(pictureBroker.files.FB_INFO):
            folder_path = os.path.dirname(os.path.realpath(file_path))
            folder_list.append(folder_path)


        random.shuffle(folder_list)
        return folder_list


    def sendPicture(self, args):

        id = args[pictureBroker.field.ID]
        v_orientation = args[pictureBroker.field.VERTICAL_ORIENTATION]


        # Select orientation
        if v_orientation:
            used_current_id_files = self.__current_id_v_images_files
            available_folder_list = self.__available_v_images_folder

        else:
            used_current_id_files = self.__current_id_h_images_files
            available_folder_list = self.__available_h_images_folder


        # Get ID current folder
        if id not in used_current_id_files or len(used_current_id_files[id]) == 0:


            # Get folders if not available
            if len(available_folder_list) == 0:
                return None


            # Get ID files and pop from common
            with self.__mutex:
                used_current_id_files[id] = available_folder_list[-1]
                available_folder_list.pop()

            if len(used_current_id_files[id]) == 0:
                used_current_id_files.pop(id)
                return None

            if v_orientation:
                self.connected_v_frames.value = len(used_current_id_files)

            else:
                self.connected_h_frames.value = len(used_current_id_files)


        # Get image
        image_file_path = used_current_id_files[id][-1]
        used_current_id_files[id].pop()


        # Send image
        response = {}
        with open(image_file_path, "rb") as image_file:
            raw_data = image_file.read()
            encoded_string = base64.b64encode(raw_data).decode('utf-8')

            response[pictureBroker.field.IMAGE_PATH] = str(image_file_path)
            response[pictureBroker.field.IMAGE] = str(encoded_string)


        return response


    def configCommands(self):

        response = d2dcn.commandArgsDef()
        response.add(pictureBroker.field.IMAGE_PATH, d2dcn.constants.valueTypes.STRING)
        response.add(pictureBroker.field.IMAGE, d2dcn.constants.valueTypes.STRING)

        request = d2dcn.commandArgsDef()
        request.add(pictureBroker.field.ID, d2dcn.constants.valueTypes.STRING)
        request.add(pictureBroker.field.VERTICAL_ORIENTATION, d2dcn.constants.valueTypes.BOOL)

        self.d2d.addServiceCommand(lambda args : self.sendPicture(args),
                                    pictureBroker.command.GET_IMAGE,
                                    request, response, d2dcn.constants.category.GENERIC,
                                    timeout=pictureBroker.param.GET_IMAGE_TIMEOUT,
                                    protocol=d2dcn.constants.commandProtocol.JSON_TCP)


        self.connected_v_frames = self.d2d.addInfoWriter(pictureBroker.field.CONNECTED_V_FRAMES, d2dcn.constants.valueTypes.INT, d2dcn.constants.category.GENERIC)
        self.connected_h_frames = self.d2d.addInfoWriter(pictureBroker.field.CONNECTED_H_FRAMES, d2dcn.constants.valueTypes.INT, d2dcn.constants.category.GENERIC)
        self.avalilable_v_folder = self.d2d.addInfoWriter(pictureBroker.field.AVALILABLE_v_FOLDER, d2dcn.constants.valueTypes.INT, d2dcn.constants.category.GENERIC)
        self.avalilable_h_folder = self.d2d.addInfoWriter(pictureBroker.field.AVALILABLE_H_FOLDER, d2dcn.constants.valueTypes.INT, d2dcn.constants.category.GENERIC)


    def startBroker(self):


        while True:

            with self.__mutex:
                current_v_length = len(self.__available_v_images_folder)
                current_h_length = len(self.__available_h_images_folder)

            if current_v_length == 0 or current_h_length == 0:
                available_folders = self.__getAllFolders(self.__root_folder)
                for folder in available_folders:

                    if folder not in self.__already_process:
                        v_images_files, h_images_files = self.__getFilesInDir(folder)
                        self.__already_process[folder] = (h_images_files, v_images_files)

                    else:
                        h_images_files, v_images_files = self.__already_process[folder]


                    with self.__mutex:
                        if current_v_length == 0 and len(v_images_files) > 0:
                            self.__available_v_images_folder.append(v_images_files)
                            self.avalilable_v_folder.value = len(self.__available_v_images_folder)

                        if current_h_length == 0 and len(h_images_files) > 0:
                            self.__available_h_images_folder.append(h_images_files)
                            self.avalilable_h_folder.value = len(self.__available_h_images_folder)

            time.sleep(1)


def main():

    parser = argparse.ArgumentParser(description="Device mounter daemon")
    parser.add_argument(
        '--root-folder',
        metavar = "[ROOT FOLDER]",
        required=False,
        default="./",
        help='Picture root folder')
    parser.add_argument(
        '--config-file',
        metavar = "[CONFIG FILE]",
        required=False,
        default="",
        help='Config file')

    args = parser.parse_args(sys.argv[1:])

    picture_broker = pictureBroker(args.root_folder, args.config_file)
    picture_broker.startBroker()


# Main execution
if __name__ == '__main__':

    try:
        main()

    except KeyboardInterrupt:
        pass