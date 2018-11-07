""" Module which provides a common functional interface for loading video frames/images from different
    input data formats. """

from __future__ import print_function, division, absolute_import

import os
import sys
import copy
import datetime

# tkinter import that works on both Python 2 and 3
try:
    from tkinter import messagebox
except:
    import tkMessageBox as messagebox


import cv2
import numpy as np

from RMS.Astrometry.Conversions import unixTime2Date
from RMS.Formats.FFfile import read as readFF
from RMS.Formats.FFfile import reconstructFrame as reconstructFrameFF
from RMS.Formats.FFfile import validFFName, filenameToDatetime
from RMS.Formats.FFfile import getMiddleTimeFF
from RMS.Formats.Vid import readFrame as readVidFrame
from RMS.Formats.Vid import VidStruct





class InputTypeFF(object):
    def __init__(self, dir_path, config, single_ff=False):
        """ Input file type handle for FF files.
        
        Arguments:
            dir_path: [str] Path to directory with FF files. 
            config: [ConfigStruct object]

        Keyword arguments:
            single_ff: [bool] If True, a single FF file should be given as input, and not a directory with FF
                files. False by default.

        """

        self.input_type = 'ff'

        self.dir_path = dir_path
        self.config = config

        # This type of input should have the calstars file
        self.require_calstars = True

        if single_ff:
            print('Using FF file:', self.dir_path)
        else:
            print('Using FF files from:', self.dir_path)


        self.ff_list = []


        # Add the single FF file to the list
        if single_ff:

            self.dir_path, file_name = os.path.split(self.dir_path)

            self.ff_list.append(file_name)

        else:

            # Get a list of FF files in the folder
            for file_name in os.listdir(dir_path):
                if validFFName(file_name):
                    self.ff_list.append(file_name)


        # Check that there are any FF files in the folder
        if not self.ff_list:
            messagebox.showinfo(title='File list warning', message='No FF files in the selected folder!')

            sys.exit()


        # Sort the FF list
        self.ff_list = sorted(self.ff_list)

        # Init the first file
        self.current_ff_index = 0
        self.current_ff_file = self.ff_list[self.current_ff_index]

        # Update the beginning time
        self.beginning_datetime = filenameToDatetime(self.current_ff_file)

        # Init the frame number
        self.current_frame = 0


        self.cache = {}

        # Load the first chunk for initing parameters
        self.loadChunk()

        # Read FPS from FF file if available, otherwise use from config
        if hasattr(self.ff, 'fps'):
            self.fps = self.ff.fps

        else:
            self.fps = self.config.fps



    def nextChunk(self):
        """ Go to the next FF file. """

        self.current_ff_index = (self.current_ff_index + 1)%len(self.ff_list)
        self.current_ff_file = self.ff_list[self.current_ff_index]

        # Update the beginning time
        self.beginning_datetime = filenameToDatetime(self.current_ff_file)



    def prevChunk(self):
        """ Go to the previous FF file. """

        self.current_ff_index = (self.current_ff_index - 1)%len(self.ff_list)
        self.current_ff_file = self.ff_list[self.current_ff_index]

        # Update the beginning time
        self.beginning_datetime = filenameToDatetime(self.current_ff_file)



    def loadChunk(self, read_nframes=None):
        """ Load the FF file. 
    
        Keyword arguments:
            read_nframes: [bool] Does nothing, here to preserve common function interface with other file
                types.
        """

        # Load from cache to avoid recomputing
        if self.current_ff_file in self.cache:
            return self.cache[self.current_ff_file]

        # Load the FF file from disk
        self.ff = readFF(self.dir_path, self.current_ff_file)

        # Reset the current frame number
        self.current_frame = 0
                
        # Store the loaded file to cache for faster loading
        self.cache = {}
        self.cache[self.current_ff_file] = self.ff

        return self.ff


    def name(self):
        """ Return the name of the FF file. """

        return self.current_ff_file


    def currentTime(self, dt_obj=False):
        """ Return the middle time of the current image. """

        if dt_obj:
            return datetime.datetime(*getMiddleTimeFF(self.current_ff_file, self.fps, \
                ret_milliseconds=False))

        else:
            return getMiddleTimeFF(self.current_ff_file, self.fps, ret_milliseconds=True)



    def nextFrame(self):
        """ Increment the current frame. """

        self.current_frame = (self.current_frame + 1)%self.ff.nframes


    def prevFrame(self):
        """ Decrement the current frame. """
        
        self.current_frame = (self.current_frame - 1)%self.ff.nframes


    def loadFrame(self, avepixel=False):
        """ Load the current frame. """

        # Reconstruct the frame from an FF file
        frame = reconstructFrameFF(self.ff, self.current_frame, avepixel=avepixel)

        return frame


    def currentFrameTime(self, dt_obj=False):
        """ Return the time of the frame. """

        # Compute the datetime of the current frame
        dt = self.beginning_datetime + datetime.timedelta(seconds=self.current_frame/self.fps)
        
        if dt_obj:
            return dt

        else:
            return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond/1000)




class FFMimickInterface(object):
    def __init__(self, maxpixel, avepixel, nrows, ncols, nframes):
        """ Object which mimicks the interface of an FF structure. """

        self.maxpixel = maxpixel
        self.avepixel = avepixel
        self.nrows = nrows
        self.ncols = ncols
        self.nframes = nframes



def computeFramesToRead(read_nframes, total_frames, fr_chunk_no, current_frame_chunk):

    ### Compute the number of frames to read

    if read_nframes == -1:
        frames_to_read = total_frames

    else:

        # If the number of frames to read was not given, use the default value
        if read_nframes is None:
            frames_to_read = fr_chunk_no

        else:
            frames_to_read = read_nframes


        # Make sure not to try to read more frames than there's available
        if (current_frame_chunk + 1)*fr_chunk_no > total_frames:
            frames_to_read = total_frames - current_frame_chunk*fr_chunk_no


    return int(frames_to_read)



class InputTypeVideo(object):
    def __init__(self, dir_path, config, beginning_time=None):
        """ Input file type handle for video files.
        
        Arguments:
            dir_path: [str] Path to the video file.
            config: [ConfigStruct object]

        Keyword arguments:
            beginning_time: [datetime] datetime of the beginning of the video. Optional, None by default.

        """

        self.input_type = 'video'

        # Separate dir path and file name
        self.file_path = dir_path
        self.dir_path, self.file_name = os.path.split(dir_path)
        
        self.config = config

        # This type of input probably won't have any calstars files
        self.require_calstars = False

        # Remove the file extension
        file_name_noext = ".".join(self.file_name.split('.')[:-1])

        if beginning_time is None:
            
            try:
                # Try reading the beginning time of the video from the name if time is not given
                self.beginning_datetime = datetime.datetime.strptime(file_name_noext, "%Y%m%d_%H%M%S.%f")

            except:
                messagebox.showerror('Input error', 'The time of the beginning cannot be read from the file name! Either change the name of the file to be in the YYYYMMDD_hhmmss format, or specify the beginning time using command line options.')
                sys.exit()

        else:
            self.beginning_datetime = beginning_time



        print('Using video file:', self.file_path)

        # Open the video file
        self.cap = cv2.VideoCapture(self.file_path)

        self.current_frame_chunk = 0

        # Prop values: https://stackoverflow.com/questions/11420748/setting-camera-parameters-in-opencv-python

        # Get the FPS
        self.fps = self.cap.get(5)

        # Get the total time number of video frames in the file
        self.total_frames = self.cap.get(7)

        # Get the image size
        self.nrows = int(self.cap.get(4))
        self.ncols = int(self.cap.get(3))


        # Set the number of frames to be used for averaging and maxpixels
        self.fr_chunk_no = 256

        # Compute the number of frame chunks
        self.total_fr_chunks = self.total_frames//self.fr_chunk_no
        if self.total_fr_chunks == 0:
            self.total_fr_chunks = 1

        self.current_fr_chunk_size = self.fr_chunk_no

        self.current_frame = 0


        self.cache = {}


    def nextChunk(self):
        """ Go to the next frame chunk. """

        self.current_frame_chunk += 1
        self.current_frame_chunk = self.current_frame_chunk%self.total_fr_chunks

        # Update the current frame
        self.current_frame = self.current_frame_chunk*self.fr_chunk_no


    def prevChunk(self):
        """ Go to the previous frame chunk. """

        self.current_frame_chunk -= 1
        self.current_frame_chunk = self.current_frame_chunk%self.total_fr_chunks

        # Update the current frame
        self.current_frame = self.current_frame_chunk*self.fr_chunk_no


    def loadChunk(self, read_nframes=None):
        """ Load the frame chunk file. 
    
        Keyword arguments:
            read_nframes: [int] Number of frames to read. If not given (None), self.fr_chunk_no frames will be
                read. If -1, all frames will be read in.
        """

        # Check if all frames FF was cached and read that from cache
        if read_nframes == -1:
            if -1 in self.cache:
                return self.cache[-1]

        else:

            # First try to load the frame from cache, if available
            if self.current_frame_chunk in self.cache:
                return self.cache[self.current_frame_chunk]


        # If all frames should be taken, set the frame to 0
        if read_nframes == -1:
            self.cap.set(1, 0)

        # Otherwise, set it to the appropriate chunk
        else:

            # Set the first frame location
            self.cap.set(1, self.current_frame_chunk*self.fr_chunk_no)


        # Compute the number of frames to read
        frames_to_read = computeFramesToRead(read_nframes, self.total_frames, self.fr_chunk_no, \
            self.current_frame_chunk)

        maxpixel = np.zeros(shape=(self.nrows, self.ncols), dtype=np.uint8)
        avepixel = np.zeros(shape=(self.nrows, self.ncols), dtype=np.float64)

        # Load the chunk of frames
        for i in range(frames_to_read):

            ret, frame = self.cap.read()

            # If the end of the video files was reached, stop the loop
            if frame is None:
                break

            # Convert frame to grayscale
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Get the maximum values
            maxpixel = np.max([maxpixel, frame], axis=0)

            # Compute the running average
            avepixel += frame.astype(np.float64)/frames_to_read


        avepixel = avepixel.astype(np.uint8)


        self.current_fr_chunk_size = i + 1


        # Init the structure that mimicks the FF file structure
        ff_struct_fake = FFMimickInterface(maxpixel, avepixel, self.nrows, self.ncols, \
            self.total_frames)

        # Store the FF struct to cache to avoid recomputing
        self.cache = {}

        if read_nframes == -1:
            cache_id = -1

        else:
            cache_id = self.current_frame_chunk

        self.cache[cache_id] = ff_struct_fake


        return ff_struct_fake
        


    def name(self):
        """ Return the name of the chunk, which is just the time of the middle of the current frame chunk. """

        return str(self.currentTime(dt_obj=True))


    def currentTime(self, dt_obj=False):
        """ Return the mean time of the current image. """

        # Compute number of seconds since the beginning of the video file to the mean time of the frame chunk
        seconds_since_beginning = (self.current_frame_chunk*self.fr_chunk_no \
            + self.current_fr_chunk_size/2)/self.fps

        # Compute the absolute time
        dt = self.beginning_datetime + datetime.timedelta(seconds=seconds_since_beginning)

        if dt_obj:
            return dt

        else:
            return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond/1000)


    def nextFrame(self):
        """ Increment the current frame. """

        self.current_frame = (self.current_frame + 1)%self.total_frames


    def prevFrame(self):
        """ Decrement the current frame. """
        
        self.current_frame = (self.current_frame - 1)%self.total_frames


    def loadFrame(self, avepixel=False):
        """ Load the current frame. """


        # Set the frame location
        self.cap.set(1, self.current_frame)

        # Read the frame
        ret, frame = self.cap.read()

        # Convert frame to grayscale
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        return frame


    def currentFrameTime(self, dt_obj=False):
        """ Return the time of the frame. """

        # Compute the datetime of the current frame
        dt = self.beginning_datetime + datetime.timedelta(seconds=self.current_frame/self.fps)
        
        if dt_obj:
            return dt

        else:
            return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond/1000)






class InputTypeUWOVid(object):
    def __init__(self, dir_path, config):
        """ Input file type handle for UWO .vid files.
        
        Arguments:
            dir_path: [str] Path to the vid file.
            config: [ConfigStruct object]

        """

        self.input_type = 'vid'



        # Separate directory path and file name
        self.vid_path = dir_path
        self.dir_path, vid_file = os.path.split(dir_path)

        self.config = config

        # This type of input probably won't have any calstars files
        self.require_calstars = False


        print('Using vid file:', self.vid_path)

        # Open the vid file
        self.vid = VidStruct()
        self.vid_file = open(self.vid_path, 'rb')

        # Read one video frame and rewind to beginning
        readVidFrame(self.vid, self.vid_file)
        self.vidinfo = copy.deepcopy(self.vid)
        self.vid_file.seek(0)
        
        # Try reading the beginning time of the video from the name
        self.beginning_datetime = unixTime2Date(self.vidinfo.ts, self.vidinfo.tu, dt_obj=True)


        self.current_frame_chunk = 0
        self.current_frame = 0
        self.current_fr_chunk_size = 0

        # Get the total time number of video frames in the file
        self.total_frames = os.path.getsize(self.vid_path)//self.vidinfo.seqlen

        # Get the image size
        self.nrows = self.vidinfo.ht
        self.ncols = self.vidinfo.wid


        # Set the number of frames to be used for averaging and maxpixels
        self.fr_chunk_no = 128

        # Compute the number of frame chunks
        self.total_fr_chunks = self.total_frames//self.fr_chunk_no
        if self.total_fr_chunks == 0:
            self.total_fr_chunks = 1

        self.frame_chunk_unix_times = []


        self.cache = {}

        # Do the initial load
        self.loadChunk()


        # Estimate the FPS
        self.fps = 1/((self.frame_chunk_unix_times[-1] - self.frame_chunk_unix_times[0])/self.current_fr_chunk_size)


    def nextChunk(self):
        """ Go to the next frame chunk. """

        self.current_frame_chunk += 1
        self.current_frame_chunk = self.current_frame_chunk%self.total_fr_chunks

        # Update the current frame
        self.current_frame = self.current_frame_chunk*self.fr_chunk_no


    def prevChunk(self):
        """ Go to the previous frame chunk. """

        self.current_frame_chunk -= 1
        self.current_frame_chunk = self.current_frame_chunk%self.total_fr_chunks

        # Update the current frame
        self.current_frame = self.current_frame_chunk*self.fr_chunk_no


    def loadChunk(self, read_nframes=None):
        """ Load the frame chunk file. 
    
        Keyword arguments:
            read_nframes: [int] Number of frames to read. If not given (None), self.fr_chunk_no frames will be
                read. If -1, all frames will be read in.
        """

        # Check if all frames FF was cached and read that from cache
        if read_nframes == -1:
            if -1 in self.cache:
                return self.cache[-1]

        else:

            # First try to load the frame from cache, if available
            if self.current_frame_chunk in self.cache:
                frame, self.frame_chunk_unix_times = self.cache[self.current_frame_chunk]
                return frame



        # If all frames should be taken, set the frame to 0
        if read_nframes == -1:
            self.vid_file.seek(0)

        # Otherwise, set it to the appropriate chunk
        else:

            # Set the vid file pointer to the right byte
            self.vid_file.seek(self.current_frame_chunk*self.fr_chunk_no*self.vidinfo.seqlen)


        # Compute the number of frames to read
        frames_to_read = computeFramesToRead(read_nframes, self.total_frames, self.fr_chunk_no, \
            self.current_frame_chunk)

        maxpixel = np.zeros(shape=(self.nrows, self.ncols), dtype=np.uint16)
        avepixel = np.zeros(shape=(self.nrows, self.ncols), dtype=np.float64)

        self.frame_chunk_unix_times = []

        # Load the chunk of frames
        for i in range(frames_to_read):

            frame = readVidFrame(self.vid, self.vid_file).astype(np.uint16)

            # If the end of the vid file was reached, stop the loop
            if frame is None:
                break

            # Add the unix time to list
            self.frame_chunk_unix_times.append(self.vid.ts + self.vid.tu/1000000.0)

            # Get the maximum values
            maxpixel = np.max([maxpixel, frame], axis=0)

            # Compute the running average
            avepixel += frame.astype(np.float64)/frames_to_read


        self.current_fr_chunk_size = i + 1

        avepixel = avepixel.astype(np.uint16)

        # Init the structure that mimicks the FF file structure
        ff_struct_fake = FFMimickInterface(maxpixel, avepixel, self.nrows, self.ncols, self.total_frames)

        # Store the FF struct to cache to avoid recomputing
        self.cache = {}



        if read_nframes == -1:
            cache_id = -1

        else:
            cache_id = self.current_frame_chunk

        # Save the computed FF to cache
        self.cache[cache_id] = [ff_struct_fake, self.frame_chunk_unix_times]

        return ff_struct_fake
        


    def name(self):
        """ Return the name of the chunk, which is just the time of the middle of the current frame chunk. """

        return str(self.currentTime(dt_obj=True))


    def currentTime(self, dt_obj=False):
        """ Return the mean time of the current image. """

        # Compute the mean UNIX time
        mean_utime = np.mean(self.frame_chunk_unix_times)

        mean_ts = int(mean_utime)
        mean_tu = int((mean_utime - mean_ts)*1000000)

        return unixTime2Date(mean_ts, mean_tu, dt_obj=dt_obj)


    def nextFrame(self):
        """ Increment the current frame. """

        self.current_frame = (self.current_frame + 1)%self.total_frames


    def prevFrame(self):
        """ Decrement the current frame. """
        
        self.current_frame = (self.current_frame - 1)%self.total_frames


    def loadFrame(self, avepixel=False):
        """ Load the current frame. """

        # Set the vid file pointer to the right byte
        self.vid_file.seek(self.current_frame*self.vidinfo.seqlen)

        # Load a frame
        frame = readVidFrame(self.vid, self.vid_file)

        # Save the frame time
        self.current_frame_time = unixTime2Date(self.vid.ts, self.vid.tu, dt_obj=True) 

        return frame



    def currentFrameTime(self, dt_obj=False):
        """ Return the time of the frame. """
        
        dt = self.current_frame_time

        if dt_obj:
            return dt

        else:
            return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond/1000)





class InputTypeImages(object):
    def __init__(self, dir_path, config, beginning_time=None, fps=None):
        """ Input file type handle for a folder with images.
        
        Arguments:
            dir_path: [str] Path to the vid file.
            config: [ConfigStruct object]

        """

        self.input_type = 'images'

        self.dir_path = dir_path
        self.config = config

        # This type of input probably won't have any calstars files
        self.require_calstars = False


        # Check if the beginning time was given
        if beginning_time is None:
            
            try:
                # Try reading the beginning time of the video from the name if time is not given
                self.beginning_datetime = datetime.datetime.strptime(os.path.basename(self.dir_path), \
                    "%Y%m%d_%H%M%S.%f")

            except:
                messagebox.showerror('Input error', 'The time of the beginning cannot be read from the file name! Either change the name of the file to be in the YYYYMMDD_hhmmss format, or specify the beginning time using command line options.')
                sys.exit()

        else:
            self.beginning_datetime = beginning_time




        # If FPS is not given, use one from the config file
        if fps is None:

            self.fps = self.config.fps
            print('Using FPS from config file: ', self.fps)

        else:

            self.fps = fps
            print('Using FPS:', self.fps)



        ### Find images in the given folder ###
        img_types = ['.png', '.jpg', '.bmp']

        self.img_list = []

        for file_name in sorted(os.listdir(self.dir_path)):

            # Check if the file ends with support file extensions
            for fextens in img_types:

                if file_name.lower().endswith(fextens):

                    self.img_list.append(file_name)
                    break


        if len(self.img_list) == 0:
            messagebox.showerror('Input error', "Can't find any images in the given directory! Only PNG, JPG and BMP are supported!")
            sys.exit()

        ### ###


        print('Using folder:', self.dir_path)


        self.current_frame_chunk = 0

        # Compute the total number of used frames
        self.total_frames = len(self.img_list)

        self.current_frame = 0
        self.current_img_file = self.img_list[self.current_frame]

        # Load the first image
        img = self.loadFrame()

        # Get the image size
        self.nrows = img.shape[0]
        self.ncols = img.shape[1]

        # Get the image dtype
        self.img_dtype = img.dtype


        # Set the number of frames to be used for averaging and maxpixels
        self.fr_chunk_no = 64

        self.current_fr_chunk_size = self.fr_chunk_no

        # Compute the number of frame chunks
        self.total_fr_chunks = self.total_frames//self.fr_chunk_no
        if self.total_fr_chunks == 0:
            self.total_fr_chunks = 1



        self.cache = {}

        # Do the initial load
        self.loadChunk()



    def nextChunk(self):
        """ Go to the next frame chunk. """

        self.current_frame_chunk += 1
        self.current_frame_chunk = self.current_frame_chunk%self.total_fr_chunks

        self.current_frame = self.current_frame_chunk*self.fr_chunk_no


    def prevChunk(self):
        """ Go to the previous frame chunk. """

        self.current_frame_chunk -= 1
        self.current_frame_chunk = self.current_frame_chunk%self.total_fr_chunks

        self.current_frame = self.current_frame_chunk*self.fr_chunk_no


    def loadChunk(self, read_nframes=None):
        """ Load the frame chunk file. 
    
        Keyword arguments:
            read_nframes: [int] Number of frames to read. If not given (None), self.fr_chunk_no frames will be
                read. If -1, all frames will be read in.
        """

        # Check if all frames FF was cached and read that from cache
        if read_nframes == -1:
            if -1 in self.cache:
                return self.cache[-1]

        else:

            # First try to load the frame from cache, if available
            if self.current_frame_chunk in self.cache:
                frame = self.cache[self.current_frame_chunk]
                return frame

            
        # Compute the first index of the chunk
        if read_nframes == -1:
            first_img_indx = 0

        else:
            first_img_indx = self.current_frame_chunk*self.fr_chunk_no


        # Compute the number of frames to read
        frames_to_read = computeFramesToRead(read_nframes, self.total_frames, self.fr_chunk_no, \
            self.current_frame_chunk)

        maxpixel = np.zeros(shape=(self.nrows, self.ncols), dtype=np.uint8)
        avepixel = np.zeros(shape=(self.nrows, self.ncols), dtype=np.float64)

        # Load the chunk of frames
        for i in range(frames_to_read):

            # Compute the image index
            img_indx = first_img_indx + i

            # Stop the loop if the ends of images has been reached
            if img_indx >= self.total_frames - 1:
                break

            # Load the image
            frame = self.loadFrame(fr_no=img_indx)

            # Get the maximum values
            maxpixel = np.max([maxpixel, frame], axis=0)

            # Compute the running average
            avepixel += frame.astype(np.float64)/frames_to_read


        avepixel = avepixel.astype(np.uint8)


        self.current_fr_chunk_size = i


        # Init the structure that mimicks the FF file structure
        ff_struct_fake = FFMimickInterface(maxpixel, avepixel, self.nrows, self.ncols, self.total_frames)

        # Store the FF struct to cache to avoid recomputing
        self.cache = {}

        if read_nframes == -1:
            cache_id = -1

        else:
            cache_id = self.current_frame_chunk

        self.cache[cache_id] = ff_struct_fake

        return ff_struct_fake
    

    def nextFrame(self):
        """ Increment current frame. """

        self.current_frame = (self.current_frame + 1)%self.total_frames
        self.current_img_file = self.img_list[self.current_frame]


    def prevFrame(self):
        """ Increment current frame. """

        self.current_frame = (self.current_frame - 1)%self.total_frames
        self.current_img_file = self.img_list[self.current_frame]


    def loadFrame(self, avepixel=None, fr_no=None):
        """ Loads the current frame. 
    
        Keyword arguments:
            avepixel: [bool] Does nothing, just for function interface consistency with other input types.
            fr_no: [int] Load a specific frame. None by defualt, then the current frame will be loaded.
        """


        # If a special frame number was given, use that one
        if fr_no is not None:
            current_img_file = self.img_list[fr_no]

        else:
            current_img_file = self.current_img_file


        # Get the current image
        img = cv2.imread(os.path.join(self.dir_path, current_img_file))

        # Convert the image to black and white
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        return img




    def name(self):
        """ Return the name of the chunk, which is just the time of the middle of the current frame chunk. """

        return str(self.currentTime(dt_obj=True))


    def currentTime(self, dt_obj=False):
        """ Return the mean time of the current image. """

        # Compute number of seconds since the beginning of the video file to the mean time of the frame chunk
        seconds_since_beginning = (self.current_frame_chunk*self.fr_chunk_no \
            + self.current_fr_chunk_size/2)/self.fps

        # Compute the absolute time
        dt = self.beginning_datetime + datetime.timedelta(seconds=seconds_since_beginning)

        if dt_obj:
            return dt

        else:
            return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond/1000)



    def currentFrameTime(self, dt_obj=False):
        """ Return the time of the frame. """

        # Compute the datetime of the current frame
        dt = self.beginning_datetime + datetime.timedelta(seconds=self.current_frame/self.fps)
        
        if dt_obj:
            return dt

        else:
            return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond/1000)




def detectInputType(input_path, config, beginning_time=None, fps=None, skip_ff_dir=False):
    """ Given the folder of a file, detect the input format.

    Arguments:
        input_path: [str] Input directory path or file name (e.g. dir with FF files, or path to video file).
        config: [Config Struct]

    Keyword arguments:
        beginning_time: [datetime] Datetime of the video beginning. Optional, only can be given for
            video input formats.
        fps: [float] Frames per second, used only when images in a folder are used.
        skip_ff_dir: [bool] Skip the input type where there are multiple FFs in the same directory. False
            by default. This is only used for ManualReduction.

    """


    # If the given dir path is a directory, search for FF files or individual images
    if os.path.isdir(input_path):

        # Check if there are valid FF names in the directory
        if any([validFFName(ff_file) for ff_file in os.listdir(input_path)]) and not skip_ff_dir:

            # Init the image handle for FF files in a directory
            img_handle = InputTypeFF(input_path, config)

        # If not, check if there any image files in the folder
        else:
            img_handle = InputTypeImages(input_path, config, beginning_time=beginning_time, fps=fps)


    # If the given path is a file, look for a single FF file, video files, or vid files
    else:

        dir_path, file_name = os.path.split(input_path)

        # Check if a single FF file was given
        if validFFName(file_name):

            # Init the image handle for FF a single FF files
            img_handle = InputTypeFF(input_path, config, single_ff=True)


        # Check if the given file is a video file
        elif file_name.endswith('.mp4') or file_name.endswith('.avi') or file_name.endswith('.mkv'):

            # Init the image hadle for video files
            img_handle = InputTypeVideo(input_path, config, beginning_time=beginning_time)


        # Check if the given files is the UWO .vid format
        elif file_name.endswith('.vid'):
            
            # Init the image handle for UWO-type .vid files
            img_handle = InputTypeUWOVid(input_path, config)


        else:
            messagebox.showerror(title='Input format error', message='Only these video formats are supported: .mp4, .avi, .mkv, .vid!')
            return None


    return img_handle