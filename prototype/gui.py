import sys
import threading
import time
import tkinter as tk
import PIL
from PIL import Image, ImageTk
import cv2
import os
import re
import PySimpleGUI as sg
from collections import OrderedDict
from tracker_library import TrackerClasses
from tracker_library import centroid_tracker as ct
from tracker_library import cell_analysis_functions as analysis
from tracker_library import export_data as export
from tracker_library import matplotlib_graphing

# State Constants
MAIN_MENU = 1
VIDEO_PLAYER = 2
CELL_SELECTION = 3
EXPORT = 4

class App:
    """
    TODO: change slider resolution based on vid length
    TODO: make top menu actually do something :P    """
    def __init__(self):

        # ------ App states ------ #
        self.play = True  # Is the video currently playing?
        self.delay = 0.0003  # Delay between frames - not sure what it should be, not accurate playback
        self.frame = 1  # Current frame
        self.frames = None  # Number of frames
        # ------ Other vars ------ #
        self.edited_vid = None
        self.vid = None
        self.photo = None
        self.edited = None
        self.next = "1"
        # ------ Tracker Instances ------- #
        self.video_player = None
        # ------ Menu Definition ------ #
        menu_def = [['&File', ['&Open', '&Save', '---', 'Properties', 'E&xit']],
                    ['&Edit', ['Paste', ['Special', 'Normal', ], 'Undo'], ],
                    ['&Help', '&About...']]

        # Main Menu Layout
        layout1 = [[sg.Menu(menu_def)],
                   [sg.Text('Select video')], [sg.Input(key="_FILEPATH_"), sg.Button("Browse")],  # File Selector
                   [sg.Text('Select Type of Cell Tracking'), sg.Push(), sg.Text('Tracker Settings. Leave Blank for Defaults')],
                   # Section to select type of analysis with radio buttons
                   [sg.R('Individual Cell Tracking', 1, key="individual_radio"), sg.Push(),
                    sg.Text('Real World Width of the Video (mm)'), sg.Input(key="video_width_mm")],
                   # Take Input for Constants
                   [sg.R('Full Culture Tracking', 1, key="culture_radio"), sg.Push(),
                    sg.Text('Real World Height of the Video (mm)'), sg.Input(key="video_height_mm")],
                   [sg.Push(), sg.Text('Number of pixels per mm'), sg.Input(key='pixels_per_mm')],
                   [sg.Push(), sg.Text('Time Between Images (mins)'), sg.Input(key="time_between_frames")],
                   [sg.Push(), sg.Text('Min Cell Size (Default = 10)'), sg.Input(key="min_size")],
                   [sg.Push(), sg.Text('Max Cell Size (Default = 500)'), sg.Input(key="max_size")],
                   [sg.Push(), sg.Text('Video Editor Settings')],
                   [sg.Push(), sg.Text('Contrast (Default = 1.25)'), sg.Input(key="contrast")],
                   [sg.Push(), sg.Text('Brightness (0 leaves the brightness unchanged. Default = .1)'), sg.Input(key="brightness")],
                   [sg.Push(), sg.Text('Blur Intensity (Default = 10)'), sg.Input(key="blur")],
                   [sg.Button('Run'), sg.Button('Exit')]]

        # Video Player Layout
        layout2 = [[sg.Menu(menu_def)],
                   [sg.Text('Original Video'), sg.Push(), sg.Text('Tracker Video', justification='r')],
                   # Titles for each video window
                   [sg.Canvas(size=(400, 300), key="canvas", background_color="blue"),
                    sg.Canvas(size=(400, 300), key="edited_video", background_color="blue")],
                   # Windows for edited/original video to play
                   [sg.T("0", key="counter", size=(10, 1))], # Frame Counter
                   [sg.Button("Pause", key="Play"), sg.Button('Next frame'),
                    sg.Push(),
                    sg.Button('Export Data', disabled=True),
                    sg.Button('Exit')]]  # Play/Pause Buttons, Next Frame Button
        # Export/Quit buttons. Disabled by default but comes online when video is done playing

        # Cell Selection (For Individual Tracking)
        layout3 = [[sg.Menu(menu_def)],
                   [sg.Text('Original Video'), sg.Push(), sg.Text('Tracker Video', justification='r')],
                   # Titles for each video window
                   [sg.Canvas(size=(400, 300), key="original_first_frame", background_color="blue"),
                    sg.Canvas(size=(400, 300), key="edited_first_frame", background_color="blue")],
                   # Windows for edited/original video to play
                   [sg.Text('Enter Id number of cell you wish to track:'), sg.Input(key="cell_id")],
                   # Take input of Cell ID Number
                   [sg.Button('Track', key="track_individual"), sg.Button("Exit")]]  # Run and Exit Buttons

        # Export Data Menu
        layout4 = [[sg.Menu(menu_def)],
                   [sg.Text("Select Export Settings")],
                   [sg.Check('Export Data to Excel Sheet', key='excel_export', enable_events=True)],
                   [sg.Text('Excel File to Export to (.xlsx):\n  Leave blank for auto generated filename', key='excel_file_label', visible=False), sg.Input(key="excel_filename", visible=False)],
                   [sg.Text('Select Graphs to Export:')],
                   [sg.Check('Area over Time', key="Area over Time")],
                   # Individual Tracker Specific Export Items
                   [sg.Check('Movement over Time', key='Movement over Time', enable_events=True, visible=False)],
                   [sg.Text('Number of Points to Label.\n  By default only the First and Last point will be labeled, reducing this number improves visual clarity', key="num_labels_desc", visible=False), sg.Input(key='num_labels', visible=False)],
                   [sg.Text('Select Images to Export', key="images_label", visible=False)],
                   [sg.Check('Export Final Path of Tracked Cell', key="path_image", visible=False)],
                   # Culture Tracker Specific Export Items
                   [sg.Check('Average Displacement', key="average_displacement", visible=False)],
                   [sg.Check('Average Speed', key="average_speed", visible=False)],

                   [sg.Button('Export'), sg.Button("Cancel", key="Cancel")],
                   # Export Button finishes script and program, Cancel returns to previous page
                   [sg.Text("Data Currently Exporting. Application will close once process is finished",
                            key="export_message", text_color="red", visible=False)]]


        num_layouts = 4

        # Set the theme
        sg.theme()
        # ----------- Create actual layout using Columns and a row of Buttons ------------- #
        layout = [[sg.Column(layout1, key='-COL1-'), sg.Column(layout2, visible=False, key='-COL2-'),
                   sg.Column(layout3, visible=False, key='-COL3-'), sg.Column(layout4, visible=False, key='-COL4-')],
                  [sg.Button('Cycle Layout'), sg.Button('1'), sg.Button('2'), sg.Button('3'), sg.Button('4'),
                   sg.Button('Exit')]]

        self.window = sg.Window('Cell Analyzer', layout, resizable=True, size=(800, 600)).Finalize()
        # set return_keyboard_events=True to make hotkeys for video playback
        # Get the tkinter canvas for displaying the video
        canvas = self.window.Element("canvas")
        self.canvas = canvas.TKCanvas
        self.edited_canvas = self.window.Element("edited_video").TKCanvas
        self.first_frame_orig = self.window.Element("original_first_frame").TKCanvas
        self.first_frame_edited = self.window.Element("edited_first_frame").TKCanvas

        layout = 1
        running = True
        # Main event Loop
        while running:
            event, values = self.window.Read()
            print(event, values)

            # ---- Global Events ---- #
            # Event to change layout, at the moment just jumps to the next layout
            if event == 'Cycle Layout':
                self.window[f'-COL{layout}-'].update(visible=False)
                layout = ((layout + 1) % num_layouts)
                if layout == 0:
                    layout += 1
                self.window[f'-COL{layout}-'].update(visible=True)
            elif event in '1234':
                self.window[f'-COL{layout}-'].update(visible=False)
                layout = int(event)
                self.window[f'-COL{layout}-'].update(visible=True)

            # Exit Event
            if event is None or event.startswith('Exit'):
                """Handle exit"""
                running = False

            # ---- Main Menu Events ---- #
            # File Selection Browse Button
            if event == "Browse":
                """Browse for files when the Browse button is pressed"""
                # Open a file dialog and get the file path
                video_path = None
                try:
                    video_path = sg.filedialog.askopenfile().name
                except AttributeError:
                    print("no video selected, doing nothing")

                if video_path:
                    print(video_path)
                    # Initialize video
                    self.vid = MyVideoCapture(video_path)
                    # Calculate new video dimensions
                    self.vid_width = 500
                    self.vid_height = int(self.vid_width * self.vid.height / self.vid.width)
                    # print("old par: %f" % (self.vid.width / self.vid.height))
                    # print("new par: %f" % (self.vid_width / self.vid_height))
                    # print(self.vid.fps)
                    # print(int(self.vid.frames))
                    self.frames = int(self.vid.frames)

                    # Update right side of counter
                    self.window.Element("counter").Update("0/%i" % self.frames)
                    # change canvas size approx to video size
                    #self.canvas.config(width=self.vid_width, height=self.vid_height)

                    # Reset frame count
                    self.frame = 1
                    self.delay = 1 / self.vid.fps

                    # Update the video path text field
                    self.window.Element("_FILEPATH_").Update(video_path)

            # Check input values then run subsequent tracking script
            if event == "Run":
                # Grab References to each field
                file = self.window["_FILEPATH_"].get()
                width = self.window["video_width_mm"].get()
                height = self.window["video_height_mm"].get()
                pixels_per_mm = self.window["pixels_per_mm"].get()
                mins = self.window["time_between_frames"].get()
                min_size = self.window["min_size"].get()
                max_size = self.window["max_size"].get()
                contrast = self.window["contrast"].get()
                brightness = self.window["brightness"].get()
                blur = self.window["blur"].get()

                # Check that all fields have been filled out with valid data then determine next action based on tracking type
                if isValidParameters(file, width, height, mins, pixels_per_mm, min_size, max_size, contrast, brightness, blur):

                    # If individual tracking has been selected
                    if self.window.Element("individual_radio").get():
                        # Initialize Individual Tracker with given arguments
                        # If valid pixels per mm were given then call the individual tracker with that parameter
                        if isValidPixels(pixels_per_mm):
                            self.video_player = TrackerClasses.IndividualTracker(file, int(mins),
                                                                                 pixels_per_mm=float(pixels_per_mm))
                        else:
                            # Otherwise call it with the video's height/width
                            self.video_player = TrackerClasses.IndividualTracker(file, int(mins), width_mm=float(width), height_mm=float(height))

                        # Set all extra input arguments if they are valid
                        if isValidInt(min_size) and (min_size != "" and min_size is not None):
                            self.video_player.set_min_size(int(min_size))
                        if isValidInt(max_size) and (max_size != "" and max_size is not None):
                            self.video_player.set_max_size(int(max_size))
                        if isValidFloat(contrast) and (contrast != "" and contrast is not None):
                            self.video_player.set_contrast(float(contrast))
                        if isValidFloat(brightness) and (brightness != "" and brightness is not None):
                            self.video_player.set_brightness(float(brightness))
                        if isValidInt(blur) and blur != "" and blur is not None:
                            self.video_player.set_blur_intensity(int(blur))


                        # Continue to Individual Cell Selection Page
                        self.window[f'-COL{MAIN_MENU}-'].update(visible=False)
                        self.window[f'-COL{CELL_SELECTION}-'].update(visible=True)

                        # Display First Frame of Edited and UnEdited Video on Cell Selection View
                        self.display_first_frame()

                        # Start video display thread
                        self.load_video()


                    # Culture Tracking is selected
                    elif self.window.Element("culture_radio").get():
                        # Initialize Culture Tracker
                        # If valid pixels per mm were given then call the individual tracker with that parameter
                        if isValidPixels(pixels_per_mm):
                            self.video_player = TrackerClasses.CultureTracker(file, int(mins),
                                                                                 pixels_per_mm=float(pixels_per_mm))
                        else:
                            # Otherwise call it with the video's height/width
                            self.video_player = TrackerClasses.CultureTracker(file, int(mins), width_mm=float(width),
                                                                                 height_mm=float(height))

                        # Set all extra input arguments if they are valid
                        if isValidInt(min_size) and (min_size != "" and min_size is not None):
                            self.video_player.set_min_size(int(min_size))
                        if isValidInt(max_size) and (max_size != "" and max_size is not None):
                            self.video_player.set_max_size(int(max_size))
                        if isValidFloat(contrast) and (contrast != "" and contrast is not None):
                            self.video_player.set_contrast(float(contrast))
                        if isValidFloat(brightness) and (brightness != "" and brightness is not None):
                            self.video_player.set_brightness(float(brightness))
                        if isValidInt(blur) and blur != "" and blur is not None:
                            self.video_player.set_blur_intensity(int(blur))

                        # Continue to video player page
                        self.window[f'-COL{MAIN_MENU}-'].update(visible=False)
                        self.window[f'-COL{VIDEO_PLAYER}-'].update(visible=True)

                        # Start video display thread
                        self.load_video()

                    # No Method is Selected do not run
                    else:
                        sg.PopupError("Method of Tracking must be selected before running")

            # ---- Cell Selection Events ---- #
            if event == "track_individual":
                # When Track button is pressed update the individual tracker to keep track of the input cell
                # and then attempt to move forward to video player stage

                selected = self.select_cell()

                # If user has entered a valid cell id and the tracker has been updated Continue to video player page
                if selected:
                    self.window[f'-COL{CELL_SELECTION}-'].update(visible=False)
                    self.window[f'-COL{VIDEO_PLAYER}-'].update(visible=True)
                    # Video should start playing due to self.update method


            # ---- Video Player Events ---- #
            if event == "Play":
                if self.play:
                    self.play = False
                    self.window.Element("Play").Update("Play")
                else:
                    self.play = True
                    self.window.Element("Play").Update("Pause")

            if event == 'Next frame':
                # Jump forward a frame
                self.set_frame(self.frame + 1)

            if event == "Export Data":
                # Continue to export interface
                self.window[f'-COL{VIDEO_PLAYER}-'].update(visible=False)
                self.window[f'-COL{EXPORT}-'].update(visible=True)
                # Enable individual cell tracking specifics exports if it meets the reqs
                if self.window.Element("individual_radio").get():
                    self.window['Movement over Time'].update(visible=True)
                    self.window['images_label'].update(visible=True)
                    self.window['path_image'].update(visible=True)

                # Enable culture tracker specific exports
                elif self.window.Element("culture_radio").get():
                    self.window['average_displacement'].update(visible=True)
                    self.window['average_speed'].update(visible=True)


            # ---- Export Events ---- #
            if event == "excel_export":
                # When Excel Export Checkbox is checked enable the input for a filename
                if self.window['excel_filename'].visible:
                    self.window['excel_file_label'].update(visible=False)
                    self.window['excel_filename'].update(visible=False)
                else:
                    self.window['excel_file_label'].update(visible=True)
                    self.window['excel_filename'].update(visible=True)

            if event == "Movement over Time":
                # When graph for movement over time checkbox is checked enable the input for num labels
                if self.window['num_labels_desc'].visible:
                    self.window['num_labels_desc'].update(visible=False)
                    self.window['num_labels'].update(visible=False)
                else:
                    self.window['num_labels_desc'].update(visible=True)
                    self.window['num_labels'].update(visible=True)

            if event == "Export":
                # Grab all values for exports
                export_excel = self.window.Element("excel_export").get()
                excelfile = self.window.Element("excel_filename").get()
                valid_filename = True

                # If excel filename field is entered
                if excelfile != '' and excelfile is not None:
                    # Determine if file is in the correct format
                    if re.match(".*[.]xlsx$", excelfile):
                        valid_filename = True
                    else:
                        valid_filename = False
                        sg.PopupError("Given Excel File Name is in an incorrect format.\nEnsure the filename ends in "
                                      ".xlsx or leave the field blank for an autogenerated name")

                exportgraph_area = self.window.Element("Area over Time").get()

                # Individual Tracker Specific Checkboxes
                exportgraph_movement = self.window.Element("Movement over Time").get()
                num_labels = self.window.Element("num_labels").get()
                exportpath_image = self.window.Element("path_image").get()

                # Culture Tracker Specific Checkboxes
                export_average_displacement = self.window.Element("average_displacement").get()
                export_average_speed = self.window.Element("average_speed").get()


                # Valid Inputs as needed
                if isValidExportParameters() and valid_filename:
                    # Display Export Message
                    self.window['export_message'].update(visible=True)

                    # TODO Allow User to input filenames for all different exports
                    # Continue Script and Export Data
                    # If export raw excel data was selected call excel export data
                    if export_excel:
                        # If a filename was supplied pass it as a parameter
                        if excelfile != '' and excelfile is not None:
                            self.video_player.export_to_excel(excelfile)
                        else:
                            self.video_player.export_to_excel()

                    # Create Area vs Time graph
                    if exportgraph_area:
                        self.video_player.export_area_graph()

                    # Individual Tracker Exports
                    if self.window.Element("individual_radio").get():
                        # Create X vs Y Position graph
                        if exportgraph_movement:
                            # If a number of labels was supplied pass it as a parameter
                            if num_labels != '' and num_labels is not None:
                                self.video_player.export_movement_graph(num_labels=num_labels)
                            else:
                                self.video_player.export_movement_graph()

                        # Image Exports
                        if exportpath_image:
                            self.video_player.export_final_path()

                    elif self.window.Element("culture_radio").get():
                        # Create Average Displacement Graph
                        if export_average_displacement:
                            self.video_player.export_average_displacement_graph()

                        # Create Average Speed Graph
                        if export_average_speed:
                            self.video_player.export_average_speed_graph()

                    # Close app once Export is finished
                    running = False

            # Return to previous page
            if event == "Cancel":
                # Continue to export interface
                self.window[f'-COL{EXPORT}-'].update(visible=False)
                self.window[f'-COL{VIDEO_PLAYER}-'].update(visible=True)

        # Exiting
        print("bye :)")
        self.window.Close()
        sys.exit()


    #################
    # Video methods #
    #################
    def load_video(self):
        """Start video display in a new thread"""
        thread = threading.Thread(target=self.update, args=())
        thread.daemon = 1
        thread.start()

    def update(self):
        """Update the canvas elements within the video player interface with the next video frame recursively"""
        """Ran by Thread started by load_video"""
        start_time = time.time()
        if self.vid:
            # Only Update video while it is visible on video player interface and is supposed to play
            if self.window[f'-COL{VIDEO_PLAYER}-'].visible:
                if self.play:
                    # Retrieve the next frame from the video
                    original, edited = self.video_player.next_frame()

                    # next_frame() will return values of None if all frames have already been read
                    # If there are valid frames returned
                    if original is not None and edited is not None:
                        # Display next frame for unedited video
                        # convert image from BGR to RGB so that it is read correctly by PIL
                        original = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
                        self.photo = PIL.ImageTk.PhotoImage(
                            image=PIL.Image.fromarray(original).resize((self.vid_width, self.vid_height), Image.NEAREST)
                        )
                        self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

                        # Display next frame for edited video
                        self.edited = PIL.ImageTk.PhotoImage(
                            image=PIL.Image.fromarray(edited).resize((self.vid_width, self.vid_height),
                                                                        Image.NEAREST)
                        )
                        self.edited_canvas.create_image(0, 0, image=self.edited, anchor=tk.NW)

                        # Update video frame counter
                        self.frame += 1
                        self.update_counter(self.frame)
                    else:
                        # Video is finished playing
                        # Stop Video playback (Set to Pause)
                        self.play = False
                        self.window.Element("Play").Update("Play")

                        # Make Export Button Clickable
                        self.window["Export Data"].update(disabled=False)

                        print("OUT OF FRAMES")

        # The tkinter .after method lets us recurse after a delay without reaching recursion limit. We need to wait
        # between each frame to achieve proper fps, but also count the time it took to generate the previous frame.
        #self.canvas.after(abs(int((self.delay - (time.time() - start_time)) * 1000)), self.update)
        self.canvas.after(abs(int(self.delay * 1000)), self.update)

    def set_frame(self, frame_no):
        """Jump to a specific frame"""
        if self.vid:
            # Get a frame from the video source only if the video is supposed to play
            ret, frame = self.vid.goto_frame(frame_no)
            self.frame = frame_no
            self.update_counter(self.frame)

            if ret:
                self.photo = PIL.ImageTk.PhotoImage(
                    image=PIL.Image.fromarray(frame).resize((self.vid_width, self.vid_height), Image.NEAREST))
                self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

    def update_counter(self, frame):
        """Helper function for updating slider and frame counter elements"""
        self.window.Element("counter").Update("{}/{}".format(frame, self.frames))

    '''
        Outputs first frame to the cell selection screen
    '''
    def display_first_frame(self):
        # Use Individual Tracker to grab and display the edited first frame
        unedited, processed = self.video_player.get_first_frame()

        # Calculate new video dimensions
        self.vid_width = 400
        self.vid_height = 300
        self.frames = int(self.vid.frames)

        # Update right side of counter
        self.window.Element("counter").Update("0/%i" % self.video_player.frames)
        # change canvas size approx to video size
        #self.canvas.config(width=self.vid_width, height=self.vid_height)

        # Reset frame count
        self.frame = 0
        self.delay = 1 / self.vid.fps

        # Display Original photo in left frame of selected view
        # scale image to fit inside the frame
        # convert image from BGR to RGB so that it is read correctly by PIL
        frame = cv2.cvtColor(unedited, cv2.COLOR_BGR2RGB)
        self.photo = PIL.ImageTk.PhotoImage(
            image=PIL.Image.fromarray(frame).resize((self.vid_width, self.vid_height), Image.NEAREST)
        )

        self.first_frame_orig.create_image(0, 0, image=self.photo, anchor=tk.NW)

        # Display edited photo in right frame of selected window
        self.edited = PIL.ImageTk.PhotoImage(
            image=PIL.Image.fromarray(processed).resize((self.vid_width, self.vid_height), Image.NEAREST)
        )
        self.first_frame_edited.create_image(0, 0, image=self.edited, anchor=tk.NW)

        self.frame += 1
        self.update_counter(self.frame)

    '''
    Selects the cell to track 
    if valid the id will be saved and the tracking data will be initialized based on info from the first frame, 
    otherwise it will display an error
    @:return True if the entered cell id is valid and the tracker has been successfully updated. Otherwise returns false
    '''
    def select_cell(self):
        success = False
        # Check if selected id is valid
        cell_id = self.window["cell_id"].get()

        try:
            cell_id = int(cell_id)

            if not self.video_player.is_valid_id(cell_id):
                # if invalid display error message
                sg.PopupError("Invalid Cell ID")
            else:
                # if selection is valid, set the tracker's cell id
                self.video_player.set_tracked_cell(cell_id)

                # Initialize tracker info
                self.video_player.initialize_tracker_data()
                success = True

        except ValueError:
            # if invalid display error message
            sg.PopupError("Cell ID must be an integer")

        return success


class MyVideoCapture:
    """
    Defines a new video loader with openCV
    Original code from https://solarianprogrammer.com/2018/04/21/python-opencv-show-video-tkinter-window/
    Modified by me
    """

    def __init__(self, video_source):
        # Open the video source
        self.vid = cv2.VideoCapture(video_source)
        if not self.vid.isOpened():
            raise ValueError("Unable to open video source", video_source)

        # Get video source width and height
        self.width = self.vid.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.frames = self.vid.get(cv2.CAP_PROP_FRAME_COUNT)
        self.fps = self.vid.get(cv2.CAP_PROP_FPS)

    def get_frame(self):
        """
        Return the next frame
        """
        if self.vid.isOpened():
            ret, frame = self.vid.read()
            if ret:
                # Return a boolean success flag and the current frame converted to BGR
                return ret, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                return ret, None
        else:
            return 0, None

    def goto_frame(self, frame_no):
        """
        Go to specific frame
        """
        if self.vid.isOpened():
            self.vid.set(cv2.CAP_PROP_POS_FRAMES, frame_no)  # Set current frame
            ret, frame = self.vid.read()  # Retrieve frame
            if ret:
                # Return a boolean success flag and the current frame converted to BGR
                return ret, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                return ret, None
        else:
            return 0, None

    # Release the video source when the object is destroyed
    def __del__(self):
        if self.vid.isOpened():
            self.vid.release()


'''
    Checks if the given tracker parameters are valid. User only needs valid height/width or pixels. 
    Displays error popups if arguments given are invalid
    @param videofile The path to the video file to check
    @param width Width of the video frame in mm
    @param height Height of the video frame in mm
    @time_between_frames Time in minutes between each image in the video
    @pixels Pixels per mm
    @return True if all given parameters are valid, false if not
'''
def isValidParameters(videofile, width, height, time_between_frames, pixels, min_size, max_size, contrast, brightness, blur):
    valid = False

    # User is only required to enter valid dimensions or pixels so ensure one of them is correct
    # Video Validation
    if isValidVideo(videofile):
        # Time Validation
        if isValidTime(time_between_frames):
            # Validate Dimensions or Pixel measurement
            if isValidDimensions(width, height) or isValidPixels(pixels):
                # If the optional parameter is filled and valid, or left empty proceed
                # Validate min size
                if (isValidInt(min_size) and (min_size != "" and min_size is not None)) or min_size == "":
                    # Validate max size
                    if (isValidInt(max_size) and (max_size != "" and max_size is not None)) or max_size == "":
                        # Validate contrast
                        if (isValidFloat(contrast) and (contrast != "" and contrast is not None)) or contrast =="":
                            # Validate brightness
                            if (isValidFloat(brightness) and (brightness != "" and brightness is not None)) or brightness =="":
                                # Validate Blur
                                if (isValidInt(blur) and blur != "" and blur is not None) or blur =="":
                                    valid = True
                                # Display Blur Error Messsage
                                else:
                                    sg.popup_error("Entered: Blur intensity is invalid. Blur intensity must be a positive integer or left empty for the default value")
                            # Display brightness error message
                            else:
                                sg.popup_error(
                                    "Entered: Brightness is invalid. Brightness must be a positive integer/float or left empty for the default value")
                        # Contrast error message
                        else:
                            sg.popup_error(
                                "Entered: Contrast is invalid. Contrast must be a positive integer or left empty for the default value")
                    # Max Size error message
                    else:
                        sg.popup_error(
                            "Entered: Max size is invalid. Max size must be a positive integer or left empty for the default value")
                # Min size error message
                else:
                    sg.popup_error(
                        "Entered: min size is invalid. Min size must be a positive integer or left empty for the default value")
            # Dimensions/Pixel Measurement Error
            else:
                sg.popup_error("Entered: Dimensions or Pixels per mm is invalid. Either the width and height fields or the pixels per mm field must be filled. They must be a positive integer/float")
        # Time Error Message
        else:
            sg.popup_error(
                "Entered: time between frames is invalid. This Field must be filled with a positive integer.")
    # Video Validation
    else:
        sg.popup_error(
            "Entered: Video File is invalid. Supported File types: .mp4, .avi")



    # if isValidVideo(videofile) and isValidTime(time_between_frames) and (isValidDimensions(width, height) or isValidPixels(pixels)):
    #     valid = True

    return valid


'''
    Checks if the given video file is of correct file type and can be opened by opencv
    @param videofile The path to the video file to check
    @return True if the tracker can analyze it, false if it cannot
'''
def isValidVideo(videofile):
    valid = False
    if os.path.exists(videofile):
        if videofile.endswith(".avi") or videofile.endswith(".mp4"):
            valid = True
    return valid


'''
    Checks if the given dimensions are positive integers
    @param width Width in mm should be a positive integer
    @return True if valid, false if not
'''
def isValidDimensions(width, height):
    valid = False
    try:
        width = int(width)
        height = int(height)
        if 0 < width and 0 < height:
            valid = True
    except ValueError:
        valid = False

    return valid


'''
    Checks if the given number of minutes in a positive integer
    @param mins 
    @return True if valid, false if not
'''
def isValidTime(mins):
    valid = False
    try:
        val = int(mins)
        if 0 < val:
            valid = True
    except ValueError:
        valid = False

    return valid

'''
Checks if given pixel per mm value is a positive float
'''
def isValidPixels(pixels):
    valid = False
    try:
        val = float(pixels)
        if 0 < val:
            valid = True
    except ValueError:
        valid = False

    return valid

'''
Checks if given value is a positive float
'''
def isValidFloat(var):
    valid = False
    try:
        val = float(var)
        if 0 < val:
            valid = True
    except ValueError:
        valid = False

    return valid


'''
Checks if given value is a positive int
'''
def isValidInt(var):
    valid = False
    try:
        val = int(var)
        if 0 < val:
            valid = True
    except ValueError:
        valid = False

    return valid

'''
Checks if given export parameters are valid
'''
def isValidExportParameters():
    return True


if __name__ == '__main__':
    App()