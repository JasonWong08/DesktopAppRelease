#!/usr/bin/python3
# -*- coding: utf-8 -*-

# !/usr/bin/python3

# Jason Wong
# Petoi LLC
# May.1st, 2022

import subprocess
from tkinter import ttk
from tkinter import filedialog
from tkinter.scrolledtext import ScrolledText
import pathlib
import logging
import queue
import time
# import webbrowser
from PetoiRobot import *

regularW = 14
language = languageList['English']
NyBoard_version_list = ['NyBoard_V1_0', 'NyBoard_V1_1', 'NyBoard_V1_2']
BiBoard_version_list = ['BiBoard_V0_1', 'BiBoard_V0_2', 'BiBoard_V1_0']

def txt(key):
    return language.get(key, textEN[key])

# Custom logging handler to redirect logs to Console text widget
class ConsoleHandler(logging.Handler):
    def __init__(self, text_widget, log_queue):
        super().__init__()
        self.text_widget = text_widget
        self.log_queue = log_queue
        
    def emit(self, record):
        try:
            msg = self.format(record) + '\n'
            # Put log message in queue for thread-safe GUI update
            self.log_queue.put(msg)
        except Exception:
            self.handleError(record)
    
class Uploader:
    def __init__(self,model,lan):
        connectPort(goodPorts, needTesting=False, needSendTask=False, needOpenPort=False)
        self.configName = model
        self.win = Tk()
        self.OSname = self.win.call('tk', 'windowingsystem')
        self.shellOption = True
        self.win.geometry('+260+100')
        if self.OSname == 'aqua':
            self.backgroundColor ='gray'
        else:
            self.backgroundColor = None

        if self.OSname == 'win32':
            self.shellOption = False
        self.win.resizable(True, True)  # Allow window resizing
        self.bParaUpload = True
        self.bFacReset = False
        self.bIMUerror = False
        self.portWasManuallySelected = False  # Flag to track if port was manually selected
        self.validPort = ""
        self.uploadSuccess = False
        # Configure window grid to allow resizing
        # Row 0: File directory (fixed height)
        # Row 1: Controls container (fixed height, centered)
        # Row 2: Status bar (fixed height)
        # Row 3: Console (expandable)
        Grid.rowconfigure(self.win, 0, weight=0)  # File directory - fixed height
        Grid.rowconfigure(self.win, 1, weight=0)  # Controls - fixed height
        Grid.rowconfigure(self.win, 2, weight=0)  # Status bar - fixed height
        Grid.rowconfigure(self.win, 3, weight=1)  # Console - expandable
        # Configure columns to allow horizontal resizing
        Grid.columnconfigure(self.win, 0, weight=1)
        Grid.columnconfigure(self.win, 1, weight=1)
        Grid.columnconfigure(self.win, 2, weight=1)
        self.strProduct = StringVar()
        global language
        language = lan
        # self.BittleNyBoardModes = list(map(lambda x: txt(x),['Standard', 'Mind+', 'RandomMind', 'Voice', 'Camera','Ultrasonic', 'RandomMind_Ultrasonic', 'PIR', 'Touch', 'Light', 'Gesture', 'InfraredDistance']))
        # self.NybbleNyBoardModes = list(map(lambda x: txt(x),['Standard', 'Mind+', 'RandomMind', 'Voice', 'Camera','Ultrasonic', 'RandomMind_Ultrasonic', 'PIR', 'Touch', 'Light', 'Gesture', 'InfraredDistance']))
        # for NyBoard, the mode is the same between Bittle and Nybble now
        # self.BittleNyBoardModes = list(map(lambda x: txt(x),
        #                                    ['Standard', 'Mind+', 'RandomMind', 'Voice', 'Camera', 'Ultrasonic',
        #                                     'RandomMind_Ultrasonic', 'PIR', 'Touch', 'Light', 'Gesture',
        #                                     'InfraredDistance','Voice_RobotArm']))
        self.BittleNyBoardModes = list(map(lambda x: txt(x),
                                           ['Standard', 'Mind+', 'RandomMind', 'Voice', 'Camera', 'Ultrasonic',
                                            'RandomMind_Ultrasonic', 'PIR', 'Touch', 'Light', 'Gesture',
                                            'InfraredDistance']))
        self.NybbleNyBoardModes = list(map(lambda x: txt(x),
                                     ['Standard', 'Mind+', 'RandomMind', 'Voice', 'Camera', 'Ultrasonic',
                                      'RandomMind_Ultrasonic', 'PIR', 'Touch', 'Light', 'Gesture',
                                      'InfraredDistance']))
        # self.BittleBiBoardModes = list(map(lambda x: txt(x), ['Standard', 'Camera','Ultrasonic','PIR','Touch','Light','Gesture']))
        # self.NybbleBiBoardModes = list(map(lambda x: txt(x), ['Standard']))
        # for BiBoard, the mode is the same between Bittle and Nybble now
        self.BiBoardModes = list(map(lambda x: txt(x), ['Standard']))
        self.inv_txt = {v: k for k, v in language.items()}
        self.initWidgets()
        if self.strProduct.get() == 'Bittle X' or self.strProduct.get() == 'Bittle X+Arm' or self.strProduct.get() == 'Nybble Q':
            board_version_list = BiBoard_version_list
        else:
            board_version_list = NyBoard_version_list + BiBoard_version_list
        self.cbBoardVersion['values'] = board_version_list
        self.updateMode()
        self.setActiveOption()
        if self.OSname == 'aqua':
            # For macOS, update port list and it will handle selection
            self.updatePort()

        self.win.protocol('WM_DELETE_WINDOW', self.on_closing)
        self.win.update()

        # For macOS stability: Use main-thread timer instead of background thread
        # Background threads cause Tkinter crashes on macOS when packaged
        self.keepChecking = True
        
        # Initialize lastPortList from actual system ports to avoid false "new port" detection
        try:
            # Communication is already imported via "from PetoiRobot import *"
            currentPorts = Communication.Print_Used_Com()
            self.lastPortList = [p.split('/')[-1] for p in currentPorts]
        except:
            self.lastPortList = list(portStrList) if portStrList else []
        
        # Flag to prevent showing "new port" message on first check
        self.isFirstCheck = True
        
        # Start port checking in main thread using timer
        self.win.after(500, self.checkPortsMainThread)
        
        # Start console log update from queue
        self.win.after(self.logUpdateInterval, self.updateConsoleFromQueue)

        self.win.focus_force()    # force the main interface to get focus
        self.win.mainloop()


    def buildMenu(self):
        self.menuBar = Menu(self.win)
        self.win.configure(menu=self.menuBar)
        
        if self.OSname == 'win32':
            self.win.iconbitmap(resourcePath + 'Petoi.ico')
        
        self.helpMenu = Menu(self.menuBar, tearoff=0)
        self.helpMenu.add_command(label=txt('labAbout'), command=self.about)
        self.menuBar.add_cascade(label=txt('labHelp'), menu=self.helpMenu)

    def initWidgets(self):
        self.win.title(txt('uploaderTitle'))
        self.buildMenu()
        self.strFileDir = StringVar()
        self.strPort = StringVar()
        self.strStatus = StringVar()
        self.strSoftwareVersion = StringVar()
        self.strBoardVersion = StringVar()
        
        self.intMode = IntVar()
        self.strMode = StringVar()

        lines = []
        try:
            with open(defaultConfPath, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # f.close()
            lines = [line.split('\n')[0] for line in lines]    # remove the '\n' at the end of each line
            self.defaultLan = lines[0]
            self.configName = lines[1]
            strDefaultPath = lines[2]
            strSwVersion = lines[3]
            strBdVersion = lines[4]
            mode = lines[5]
            if len(lines) >= 8:
                strCreator = lines[6]
                strLocation = lines[7]
                self.configuration = [self.defaultLan, self.configName, strDefaultPath, strSwVersion, strBdVersion,
                                      mode, strCreator, strLocation]
            else:
                self.configuration = [self.defaultLan, self.configName, strDefaultPath, strSwVersion, strBdVersion, mode]
        except Exception as e:
            print ('Create configuration file')
            self.defaultLan = 'English'
            strDefaultPath = releasePath[:-1]
            strSwVersion = '2.0'
            strBdVersion = NyBoard_version_list[-1]
            mode = 'Standard'
            self.configuration = [self.defaultLan, self.configName, strDefaultPath, strSwVersion, strBdVersion, mode]
            
        num = len(lines)
        logger.debug(f"len(lines): {num}")
        self.lastSetting = [self.configName,strDefaultPath,strSwVersion,strBdVersion,mode]
        self.currentSetting = []
        
        logger.info(f"The firmware file folder is {strDefaultPath}")
        self.strFileDir.set(strDefaultPath)

        fmFileDir = ttk.Frame(self.win)
        fmFileDir.grid(row=0, columnspan=3, ipadx=2, padx=2, sticky=W + E + N + S)

        self.labFileDir = Label(fmFileDir, text=txt('labFileDir'), font=('Arial', 16))
        self.labFileDir.grid(row=0, column=0, ipadx=2, padx=2, sticky=W)

        self.btnFileDir = Button(fmFileDir, text=txt('btnFileDir'), font=('Arial', 12), foreground='blue',
                                        background=self.backgroundColor, command=self.open_dir)  # bind open_dir function
        self.btnFileDir.grid(row=0, column=1, ipadx=5, padx=5, pady=5, sticky=E)

        self.entry = Entry(fmFileDir, textvariable=self.strFileDir, font=('Arial', 16), foreground='green', background='white')
        self.entry.grid(row=1, columnspan=2, ipadx=5, padx=5, sticky=E + W)
        
        fmFileDir.columnconfigure(0, weight=8)  # set column width
        fmFileDir.columnconfigure(1, weight=1)  # set column width
        fmFileDir.rowconfigure(1, weight=1)

        # Create a container frame for all controls (dropdowns and buttons) to keep them centered
        # This ensures their position remains stable when console font size changes
        fmControls = ttk.Frame(self.win)
        fmControls.grid(row=1, column=0, columnspan=3, pady=5, sticky=N+S)
        # Configure columns to center the content horizontally
        fmControls.columnconfigure(0, weight=1)
        fmControls.columnconfigure(2, weight=1)
        # Column 1 will contain the actual controls and won't expand
        
        # Inner container to hold all controls with fixed layout
        fmControlsInner = ttk.Frame(fmControls)
        fmControlsInner.grid(row=0, column=1, sticky=N)

        fmProduct = ttk.Frame(fmControlsInner)
        fmProduct.grid(row=0, column=0, ipadx=2, padx=2, sticky=W)
        self.labProduct = ttk.Label(fmProduct, text=txt('labProduct'), font=('Arial', 16))
        self.labProduct.grid(row=0, column=0, ipadx=5, padx=5, sticky=W)

        self.cbProduct = ttk.Combobox(fmProduct, textvariable=self.strProduct, foreground='blue', font=12)
        # list of product
        cbProductList = ['Nybble', 'Nybble Q', 'Bittle', 'Bittle X', 'Bittle X+Arm']
        # set default value of Combobox
        self.cbProduct.set(displayName(self.lastSetting[0]))
        # set list for Combobox
        self.cbProduct['values'] = cbProductList
        self.cbProduct.grid(row=1, ipadx=5, padx=5, sticky=W)
        self.cbProduct.bind("<<ComboboxSelected>>", self.chooseProduct)
        if self.strProduct.get() == 'Bittle X+Arm':
            tip(self.cbProduct, "Bittle X+Arm" + " (" + "Bittle + " + txt('Robotic Arm') + ")")
        else:
            tip(self.cbProduct, self.strProduct.get())

        fmSoftwareVersion = ttk.Frame(fmControlsInner)
        fmSoftwareVersion.grid(row=0, column=1, ipadx=2, padx=2, sticky=W)
        self.labSoftwareVersion = ttk.Label(fmSoftwareVersion, text=txt('labSoftwareVersion'), font=('Arial', 16))
        self.labSoftwareVersion.grid(row=0, ipadx=5, padx=5, sticky=W)
        self.cbSoftwareVersion = ttk.Combobox(fmSoftwareVersion, textvariable=self.strSoftwareVersion, foreground='blue', font=12)
        self.cbSoftwareVersion.bind("<<ComboboxSelected>>",self.chooseSoftwareVersion)

        # list of software_version
        software_version_list = ['1.0', '2.0']
        # set default value of Combobox
        self.cbSoftwareVersion.set(self.lastSetting[2])
        
        # set list for Combobox
        self.cbSoftwareVersion['values'] = software_version_list
        self.cbSoftwareVersion.grid(row=1, ipadx=5, padx=5, sticky=W)

        fmBoardVersion = ttk.Frame(fmControlsInner)
        fmBoardVersion.grid(row=0, column=2, ipadx=2, padx=2, sticky=W)
        self.labBoardVersion = ttk.Label(fmBoardVersion, text=txt('labBoardVersion'), font=('Arial', 16))
        self.labBoardVersion.grid(row=0, ipadx=5, padx=5, sticky=W)
        
        self.cbBoardVersion = ttk.Combobox(fmBoardVersion, textvariable=self.strBoardVersion, foreground='blue', font=12)
        self.cbBoardVersion.bind("<<ComboboxSelected>>", self.chooseBoardVersion)
        # list of board_version
        board_version_list = NyBoard_version_list + BiBoard_version_list
        # set default value of Combobox
        self.cbBoardVersion.set(self.lastSetting[3])
        # set list for Combobox
        if self.strProduct.get() == 'Bittle X':
            if self.lastSetting[3] in NyBoard_version_list:
                self.cbBoardVersion.set(BiBoard_version_list[2])
            board_version_list = BiBoard_version_list
        elif self.strProduct.get() == 'Bittle X+Arm':
            if self.lastSetting[3] in NyBoard_version_list:
                self.cbBoardVersion.set(BiBoard_version_list[2])
            board_version_list = BiBoard_version_list
        elif self.strProduct.get() == 'Nybble Q':
            if self.lastSetting[3] in NyBoard_version_list:
                self.cbBoardVersion.set(BiBoard_version_list[2])
            board_version_list = BiBoard_version_list
        else:
            board_version_list = NyBoard_version_list + BiBoard_version_list
        self.cbBoardVersion['values'] = board_version_list
        self.cbBoardVersion.grid(row=1, ipadx=5, padx=5, sticky=W)

        fmMode = ttk.Frame(fmControlsInner)
        fmMode.grid(row=1, column=0, ipadx=2, padx=2, pady=6, sticky=W)
        self.labMode = ttk.Label(fmMode, text=txt('labMode'), font=('Arial', 16))
        self.labMode.grid(row=0, column=0, ipadx=5, padx=5, sticky=W)

        if self.strProduct.get() == 'Bittle' or self.strProduct.get() == 'Nybble':
            if 'NyBoard' in self.strBoardVersion.get():
                if self.strProduct.get() == 'Bittle':
                    cbModeList = self.BittleNyBoardModes
                else:
                    cbModeList = self.NybbleNyBoardModes
            else:
                cbModeList = self.BiBoardModes
        else:    # if self.strProduct.get() == 'Bittle X' or self.strProduct.get() == 'Bittle X+Arm':
            cbModeList = self.BiBoardModes

        self.cbMode = ttk.Combobox(fmMode, textvariable=self.strMode, foreground='blue', font=12)
        # set default value of Combobox
        self.cbMode.set(txt(self.lastSetting[4]))
        # set list for Combobox
        self.cbMode['values'] = cbModeList   # the mode names are already translated
        self.cbMode.grid(row=1, ipadx=5, padx=5, sticky=W)

        fmSerial = ttk.Frame(fmControlsInner)    # relief=GROOVE
        fmSerial.grid(row=1, column=1, ipadx=2, padx=2, pady=6, sticky=W)
        self.labPort = ttk.Label(fmSerial, text=txt('labPort'), font=('Arial', 16))
        self.labPort.grid(row=0, ipadx=5, padx=5, sticky=W)
        self.cbPort = ttk.Combobox(fmSerial, textvariable=self.strPort, foreground='blue', font=12)    # width=38,
        
        # Refresh port list from system to ensure we have all available ports
        # This is especially important after manual port selection
        try:
            # Communication is already imported via "from PetoiRobot import *"
            
            # Remember user's manually selected port (if any) BEFORE clearing portStrList
            user_selected_port = portStrList[0] if len(portStrList) > 0 else None
            # Check if port was manually selected (from manualSelect dialog)
            # manuallySelectedPort is imported from PetoiRobot.ardSerial via "from PetoiRobot import *"
            # IMPORTANT: Check this flag BEFORE clearing portStrList, as it might be cleared elsewhere
            try:
                # Import manuallySelectedPort from the module to ensure we can access it
                from PetoiRobot.ardSerial import manuallySelectedPort
                is_manually_selected = manuallySelectedPort
            except (NameError, ImportError):
                # If manuallySelectedPort is not available, assume it's not manually selected
                is_manually_selected = False
            
            # Get all system ports
            currentPorts = Communication.Print_Used_Com()
            current_port_names = [p.split('/')[-1] for p in currentPorts]
            
            # Update global portStrList with all system ports
            portStrList.clear()
            portStrList.extend(current_port_names)
            logger.info(f"Refreshed port list from system: {current_port_names}")
            
            # If user manually selected a port and it's still available, set it as current selection
            if user_selected_port and user_selected_port in current_port_names:
                self.strPort.set(user_selected_port)
                # Store whether this was manually selected for later display
                self.portWasManuallySelected = is_manually_selected
                if is_manually_selected:
                    logger.info(f"Preserved manually selected port: {user_selected_port}")
                else:
                    logger.info(f"Automatically detected serial port: {user_selected_port}")
                # Clear the global flag after checking
                try:
                    from PetoiRobot.ardSerial import manuallySelectedPort
                    # Use the module reference to set the value
                    import PetoiRobot.ardSerial as ardSerial_module
                    ardSerial_module.manuallySelectedPort = False
                except (NameError, ImportError):
                    pass
            else:
                # No port selected or port not available, mark as not manually selected
                self.portWasManuallySelected = False
        except Exception as e:
            logger.error(f"Failed to refresh port list: {e}")
            self.portWasManuallySelected = False
        
        self.updatePortlist()
        self.cbPort.grid(row=1, ipadx=5, padx=5, sticky=W)

        fmFacReset = ttk.Frame(fmControlsInner)    # relief=GROOVE
        fmFacReset.grid(row=1, column=2, ipadx=2, padx=2, pady=6, sticky=W + E)
        self.btnFacReset = Button(fmFacReset, text=txt('btnFacReset'), font=('Arial', 16, 'bold'), fg='red',
                                  relief='groove', command=self.factoryReset)
        self.btnFacReset.grid(row=0, ipadx=5, ipady=5, padx=9, pady=8, sticky=W + E + N + S)
        tip(self.btnFacReset, txt('tipFacReset'))
        fmFacReset.columnconfigure(0, weight=1)
        fmFacReset.rowconfigure(0, weight=1)

        fmUpload = ttk.Frame(fmControlsInner)
        fmUpload.grid(row=2, columnspan=3, ipadx=2, padx=2, pady=8, sticky=W + E + N + S)
        self.btnUpgrade = Button(fmUpload, text=txt('btnUpgrade'), font=('Arial', 16, 'bold'), foreground='blue',
                                background=self.backgroundColor, relief='groove', command=self.upgrade)
        self.btnUpgrade.grid(row=0, column=0, ipadx=5, padx=5, pady=5, sticky=W + E)
        tip(self.btnUpgrade, txt('tipUpgrade'))
        self.btnUpdateMode = Button(fmUpload, text=txt('btnUpdateMode'), font=('Arial', 16, 'bold'), foreground='blue',
                                       background=self.backgroundColor, relief='groove', command=self.uploadeModeOnly)
        self.btnUpdateMode.grid(row=0, column=1, ipadx=5, padx=5, pady=5, sticky=W + E)
        tip(self.btnUpdateMode, txt('tipUpdateMode'))
        fmUpload.columnconfigure(0, weight=1)
        fmUpload.columnconfigure(1, weight=1)
        fmUpload.rowconfigure(0, weight=1)

        fmStatus = ttk.Frame(self.win)
        fmStatus.grid(row=2, columnspan=3, ipadx=2, padx=2, pady=5, sticky=W + E + N + S)
        self.statusBar = ttk.Label(fmStatus, textvariable=self.strStatus, font=('Arial', 16), relief=SUNKEN)
        self.statusBar.grid(row=0, ipadx=5, padx=5, sticky=W + E + N + S)
        fmStatus.columnconfigure(0, weight=1)

        # Console frame for displaying log file content
        fmConsole = ttk.Frame(self.win)
        fmConsole.grid(row=3, columnspan=3, ipadx=2, padx=2, pady=5, sticky=W + E + N + S)
        
        # Header frame for Console label and Clear button
        fmConsoleHeader = ttk.Frame(fmConsole)
        fmConsoleHeader.grid(row=0, column=0, columnspan=2, sticky=W + E)
        # Configure columns so buttons stay on the right when window resizes
        fmConsoleHeader.columnconfigure(0, weight=1)  # Label column expands
        fmConsoleHeader.columnconfigure(1, weight=0)  # Copy button - fixed width
        fmConsoleHeader.columnconfigure(2, weight=0)  # Clear button - fixed width
        
        self.labConsole = ttk.Label(fmConsoleHeader, text=txt('Console') + ':', font=('Arial', 14, 'bold'))
        self.labConsole.grid(row=0, column=0, ipadx=5, padx=5, sticky=W)
        
        self.btnCopyConsole = Button(fmConsoleHeader, text=txt('Copy'), font=('Arial', 10),
                                    command=self.copyConsole)
        self.btnCopyConsole.grid(row=0, column=1, ipadx=5, padx=5, sticky=E)
        
        self.btnClearConsole = Button(fmConsoleHeader, text=txt('Clear'), font=('Arial', 10),
                                     command=self.clearConsole)
        self.btnClearConsole.grid(row=0, column=2, ipadx=5, padx=5, sticky=E)
        
        # Create scrollbars for the console text
        scrollbarY = Scrollbar(fmConsole)
        scrollbarY.grid(row=1, column=1, sticky=N + S)
        
        scrollbarX = Scrollbar(fmConsole, orient=HORIZONTAL)
        scrollbarX.grid(row=2, column=0, sticky=W + E)
        
        # Create console text widget
        self.txtConsole = Text(fmConsole, height=15, width=80, font=('Courier', 16),
                              wrap=NONE, state=DISABLED,
                              yscrollcommand=scrollbarY.set,
                              xscrollcommand=scrollbarX.set)
        self.txtConsole.grid(row=1, column=0, ipadx=5, padx=5, sticky=W + E + N + S)
        
        scrollbarY.config(command=self.txtConsole.yview)
        scrollbarX.config(command=self.txtConsole.xview)
        
        fmConsole.columnconfigure(0, weight=1)
        fmConsole.rowconfigure(1, weight=1)
        
        # Initialize console logging system
        self.logQueue = queue.Queue()
        self.logUpdateInterval = 20  # Update every 20ms for better real-time display (was 50ms)
        self.isFirstOperation = True  # Flag to track if this is the first firmware operation
        
        # Set up custom logging handler to redirect logs to Console
        self.setupConsoleLogging()

    def uploadeModeOnly(self):
        self.bParaUpload = False
        self.bFacReset = False
        self.prepareConsoleForNewOperation()
        self.uploadSuccess = self.autoupload()

    def factoryReset(self):
        self.bParaUpload = True
        self.bFacReset = True
        self.prepareConsoleForNewOperation()
        self.uploadSuccess = self.autoupload()

    def upgrade(self):
        self.bParaUpload = True
        self.bFacReset = False
        self.prepareConsoleForNewOperation()
        self.uploadSuccess = self.autoupload()

    def updatePortlist(self):
        """Update port list in UI (called from main thread only)"""
        port_number_list = []
        if len(portStrList) == 0:
            port_number_list = [' ']
            print("Cannot find the serial port!")
        else:
            logger.info(f"portStrList is {portStrList}")
            for p in portStrList:
                portName = p
                logger.debug(f"{portName}")
                port_number_list.append(portName)
            logger.debug(f"port_number_list is {port_number_list}")
        
        # Update UI directly (safe since we're always on main thread now)
        if self.OSname == 'aqua':
            self.updatePort()
        else:
            # Get current selection before updating list
            currentSelection = self.strPort.get()
            
            # Update the combobox values
            self.cbPort['values'] = port_number_list
            
            # Preserve user's selection if it's still valid, otherwise select first port
            if currentSelection and currentSelection in port_number_list:
                # Keep current selection - user's choice should be preserved
                self.cbPort.set(currentSelection)
                logger.debug(f"Preserved user's port selection: {currentSelection}")
            elif port_number_list:
                # Only change to first port if current selection is invalid or empty
                self.cbPort.set(port_number_list[0])
                # Mark as auto-detected if not already marked as manually selected
                if not hasattr(self, 'portWasManuallySelected') or not self.portWasManuallySelected:
                    self.portWasManuallySelected = False
                logger.debug(f"Auto-selected first port: {port_number_list[0]}")

    def checkPortsMainThread(self):
        """Check ports in main thread using timer (safe for macOS)"""
        if not self.keepChecking:
            return
            
        try:
            # Communication is already imported via "from PetoiRobot import *"
            
            # Get current port list
            currentPorts = Communication.Print_Used_Com()
            
            # Convert to port names only (remove '/dev/' prefix)
            current_port_names = [p.split('/')[-1] for p in currentPorts]
            
            # Check if ports changed
            if set(current_port_names) != set(self.lastPortList):
                logger.info(f"Port list changed: {current_port_names}")
                
                # Detect added and removed ports
                added_ports = set(current_port_names) - set(self.lastPortList)
                removed_ports = set(self.lastPortList) - set(current_port_names)
                
                # Get current selection
                currentSelection = self.strPort.get()
                
                # Update global portStrList
                portStrList.clear()
                portStrList.extend(current_port_names)
                
                # Handle port changes
                if added_ports:
                    # New port(s) added
                    logger.info(f"New port(s) added: {added_ports}")
                    
                    # Get board version to determine preferred port
                    boardVer = self.strBoardVersion.get()
                    added_list = sorted(added_ports)
                    
                    # Determine if we should show popup based on board version and ports
                    should_show_popup = False
                    preferred_port = None
                    
                    if boardVer in BiBoard_version_list:
                        # For BiBoard, ONLY show popup when wchusbserial is detected
                        # This avoids duplicate popups when both usbmodem and wchusbserial appear at different times
                        for port in added_list:
                            if 'wchusbserial' in port.lower():
                                preferred_port = port
                                should_show_popup = True
                                break
                        
                        if not should_show_popup:
                            # Detected other ports (like usbmodem) but not wchusbserial
                            # Just update the port list silently, don't popup
                            logger.info(f"BiBoard: Detected non-preferred ports {added_list}, updating list silently")
                            self.updatePortlist()
                    else:
                        # For NyBoard, prefer usbmodem, then usbserial-
                        for port in added_list:
                            if 'usbmodem' in port.lower():
                                preferred_port = port
                                should_show_popup = True
                                break
                        if not preferred_port:
                            for port in added_list:
                                if 'usbserial-' in port.lower():
                                    preferred_port = port
                                    should_show_popup = True
                                    break
                        # If still not found, use the first one
                        if not preferred_port and added_list:
                            preferred_port = added_list[0]
                            should_show_popup = True
                    
                    # Only show popup and auto-select if we found the preferred port
                    if should_show_popup and preferred_port:
                        new_port = preferred_port
                        
                        # Only show message if this is not the first check
                        # (to avoid false "new port" message when opening the interface)
                        if not self.isFirstCheck:
                            # Show info message for preferred new port
                            messagebox.showinfo(txt('Info'), txt('New port prompt') + new_port)
                            self.force_focus()  # Force the main interface to get focus
                            
                            # Update UI and auto-select new port
                            if self.OSname == 'aqua':
                                # For macOS, update port list and it will handle selection
                                self.updatePort()
                                # But we want to force select the preferred new port
                                if new_port in current_port_names:
                                    self.cbPort.set(new_port)
                            else:
                                # For Windows/Linux, directly update and select
                                self.cbPort['values'] = current_port_names
                                self.cbPort.set(new_port)
                            
                            # Mark that this port was auto-detected, not manually selected
                            self.portWasManuallySelected = False
                            # Clear the global flag if it exists
                            try:
                                manuallySelectedPort = False
                            except NameError:
                                pass
                            logger.info(f"Automatically detected serial port: {new_port}")
                        else:
                            # First check, just update UI without popup
                            logger.info(f"First check - detected ports without popup: {added_ports}")
                            self.updatePortlist()
                    
                elif removed_ports:
                    # Port(s) removed
                    logger.info(f"Port(s) removed: {removed_ports}")
                    
                    # Check if current selection was removed
                    if currentSelection in removed_ports:
                        logger.info(f"Current port {currentSelection} was removed")
                        
                        # Update UI
                        if self.OSname == 'aqua':
                            self.updatePort()
                        else:
                            self.cbPort['values'] = current_port_names
                            if len(current_port_names) > 0:
                                # Select first available port
                                self.cbPort.set(current_port_names[0])
                                logger.info(f"Switched to first available port: {current_port_names[0]}")
                            else:
                                # No ports available, set to empty
                                self.cbPort.set('')
                                logger.info("No ports available, cleared selection")
                    else:
                        # Current selection still valid, just update list
                        self.updatePortlist()
                
                # Update last port list
                self.lastPortList = current_port_names.copy()
                
                # Clear first check flag after first detection
                if self.isFirstCheck:
                    self.isFirstCheck = False
                    logger.debug("First check completed, future changes will show notifications")
        except Exception as e:
            logger.error(f"Error checking ports: {e}")
        
        # Schedule next check (every 500ms)
        if self.keepChecking:
            self.win.after(500, self.checkPortsMainThread)
    
    def about(self):
        self.msgbox = messagebox.showinfo(txt('titleVersion'), txt('msgVersion'))
        self.force_focus()

    def setActiveMode(self):
        if self.strSoftwareVersion.get() == '1.0':
            stt = DISABLED
            self.strMode.set(txt('Standard'))
            board_version_list = NyBoard_version_list
            self.strBoardVersion.set(board_version_list[-1])
        else:
            stt = NORMAL
            board_version_list = NyBoard_version_list + BiBoard_version_list
        # set list for Combobox
        self.cbBoardVersion['values'] = board_version_list
        self.cbMode.config(state = stt)
    
    def chooseSoftwareVersion(self, event):
        self.setActiveMode()

    def setActiveOption(self):
        if self.cbBoardVersion.get() in BiBoard_version_list:
            stt = DISABLED
            self.strSoftwareVersion.set('2.0')
        else:
            stt = NORMAL

        self.cbSoftwareVersion.config(state=stt)

    def updatePort(self):
        if self.OSname == 'aqua':
            list = copy.deepcopy(portStrList)
            boardVer = self.strBoardVersion.get()
            
            # Get current selection before updating
            currentSelection = self.strPort.get()
            
            if boardVer in NyBoard_version_list:
                if len(list) > 0:
                    itemSet = " "
                    for item in list:
                        if 'usbmodem' in item:  # prefer the USB modem device because it can restart the NyBoard
                            itemSet = item
                            break
                        elif 'usbserial-' in item:  # prefer the "serial-" device
                            itemSet = item
                            break
                            
                    # Remove unwanted ports (need to use list() to avoid modification during iteration)
                    items_to_remove = []
                    for item in list:
                        if 'wchusbserial' in item or 'cu.SLAB_USBtoUART' in item:
                            items_to_remove.append(item)
                    for item in items_to_remove:
                        list.remove(item)
                    
                    # Update values first
                    self.cbPort['values'] = list
                    
                    # Preserve user's selection if it's still valid
                    if currentSelection and currentSelection in list:
                        self.cbPort.set(currentSelection)
                        logger.debug(f"Preserved user's port selection: {currentSelection}")
                    elif itemSet != " " and itemSet in list:
                        self.cbPort.set(itemSet)
                    elif len(list) > 0:
                        self.cbPort.set(list[0])
            elif boardVer == "BiBoard_V1_0":
                if len(list) > 0:
                    itemSet = " "
                    for item in list:
                        if 'wchusbserial' in item:  # prefer the "wchusbserial" for BiBoard V1
                            itemSet = item
                            break
                        elif 'serial-' in item:  # prefer the "serial-" device
                            itemSet = item
                            break
                            
                    # Remove unwanted ports (need to use list() to avoid modification during iteration)
                    items_to_remove = []
                    for item in list:
                        if 'usbmodem' in item or 'cu.SLAB_USBtoUART' in item:
                            items_to_remove.append(item)
                    for item in items_to_remove:
                        list.remove(item)
                    
                    # Update values first
                    self.cbPort['values'] = list
                    
                    # Preserve user's selection if it's still valid
                    if currentSelection and currentSelection in list:
                        self.cbPort.set(currentSelection)
                        logger.debug(f"Preserved user's port selection: {currentSelection}")
                    elif itemSet != " " and itemSet in list:
                        self.cbPort.set(itemSet)
                    elif len(list) > 0:
                        self.cbPort.set(list[0])
            else:
                # Update values first
                self.cbPort['values'] = list
                
                # Preserve user's selection if it's still valid
                if currentSelection and currentSelection in list:
                    self.cbPort.set(currentSelection)
                    logger.debug(f"Preserved user's port selection: {currentSelection}")
                elif len(list) > 0:
                    self.cbPort.set(list[0])

    def chooseBoardVersion(self, event):
        self.setActiveOption()
        self.updateMode()
        self.updatePort()

    def chooseProduct(self, event):
        if self.strProduct.get() == 'Bittle X':
            if self.strBoardVersion.get() in NyBoard_version_list:
                self.strBoardVersion.set(BiBoard_version_list[2])
            board_version_list = BiBoard_version_list
        elif self.strProduct.get() == 'Nybble Q' or self.strProduct.get() == 'Bittle X+Arm':
            if self.strBoardVersion.get() in NyBoard_version_list:
                self.cbBoardVersion.set(BiBoard_version_list[2])
            board_version_list = BiBoard_version_list
        else:
            board_version_list = NyBoard_version_list + BiBoard_version_list

        if self.strProduct.get() == 'Bittle X+Arm':
            tip(self.cbProduct, "Bittle X+Arm" + " (" + "Bittle + " + txt('Robotic Arm') + ")")
        else:
            tip(self.cbProduct, self.strProduct.get())

        self.cbBoardVersion['values'] = board_version_list
        self.updateMode()
        self.setActiveOption()
        if self.OSname == 'aqua':
            # For macOS, update port list and it will handle selection
            self.updatePort()

    def updateMode(self):
        if self.strProduct.get() == 'Bittle' or self.strProduct.get() == 'Nybble':
            if 'NyBoard' in self.strBoardVersion.get():
                if self.strProduct.get() == 'Bittle':
                    modeList = self.BittleNyBoardModes
                else:
                    modeList = self.NybbleNyBoardModes
            else:
                modeList = self.BiBoardModes
        else:    # if self.strProduct.get() == 'Bittle X' or self.strProduct.get() == 'Bittle X+Arm':
            modeList = self.BiBoardModes

        self.cbMode['values'] = modeList

        if self.strMode.get() not in modeList:
            messagebox.showwarning(txt('Warning'),txt('msgMode'))
            # printH("modeList[0]:", modeList[0])
            self.strMode.set(modeList[0])
            self.force_focus()  # force the main interface to get focus

    def formalize(self, strdir=' '):
        sep = "/"
        listDir = strdir.split("/")
        if (strdir == str(pathlib.Path().resolve())):
            strdir = sep.join(listDir) + sep + "release"
        else:
            if (listDir[-1].find("release") == -1) and len(listDir) >= 2:
                while listDir[-1].find("release") == -1 and len(listDir) >= 2:
                    listDir = listDir[:-1]
                if listDir[-1] != "release":
                    strdir = " "
                else:
                    strdir = sep.join(listDir)
        self.strFileDir.set(strdir)


    def open_dir(self):
        # call askdirectory to open file director
        logger.debug(f"{self.strFileDir.get()}")
        if (self.strFileDir.get()).find(releasePath[:-1]) != -1:
            initDir = releasePath[:-1]
        else:
            initDir = self.strFileDir
        dirpath = filedialog.askdirectory(title=txt('titleFileDir'), initialdir=initDir)

        if dirpath:
            self.formalize(dirpath)
        self.force_focus()

    def encode(self, in_str, encoding='utf-8'):
        if isinstance(in_str, bytes):
            return in_str
        else:
            return in_str.encode(encoding)

    def WriteInstinctPrompts(self, port):
        serObj = Communication(port, 115200, 0.5)
        logger.info(f"Connect to usb serial port: {port}.")
        strSoftwareVersion = self.strSoftwareVersion.get()
        promptJointCalib = {
            'message':txt('reset joints?'),
            'operating':txt('reseting joints'),
            'result':txt('joints reset'),
        }
        promptInstinct = {
            'message':txt('update instincts?'),
            'operating':txt('updating instincts'),
            'result':txt('instincts updated')
        }
        promptIMU = {
            'message':txt('calibrate IMU?'),
            'operating':txt('calibrating IMU'),
            'result':txt('IMU calibrated')
        }
        if strSoftwareVersion == '1.0':
            promptList = [promptJointCalib,promptInstinct,promptIMU]
        elif strSoftwareVersion == '2.0':
            promptList = [promptJointCalib,promptIMU]

        strBoardVersion = self.strBoardVersion.get()
        
        progress = 0
        bCount = False
        bResetMode = False
        retMsg = False
        self.bIMUerror = False
        prompStr = ""
        counterIMU = 0
        while True:
            # Use update_idletasks() instead of update() to avoid event loop nesting
            # This updates the display without processing events, which is safer
            self.win.update_idletasks()
            
            # Manually process console queue for immediate display during serial operations
            try:
                while not self.logQueue.empty():
                    msg = self.logQueue.get_nowait()
                    if msg:
                        self.txtConsole.config(state=NORMAL)
                        self.txtConsole.insert(END, msg)
                        self.txtConsole.see(END)
                        self.txtConsole.config(state=DISABLED)
            except:
                pass
            
            time.sleep(0.01)
            if serObj.main_engine.in_waiting > 0:
                x = str(serObj.main_engine.readline())
                prompStr = x[2:-1]
                logger.debug(f"new line:{x}")
                if x != "":
                    print(prompStr)
                    logger.info(prompStr)
                    questionMark = "Y/n"
                    if self.bFacReset and strBoardVersion in BiBoard_version_list:    # for BiBoard Factory reset
                        newBoardMark = "Set up the new board"
                        if prompStr.find(newBoardMark) != -1:
                            bResetMode = True

                        if not bResetMode and (prompStr.find("Ready!") != -1):
                            time.sleep(1)
                            serObj.Send_data(self.encode("!"))
                            continue

                        if bResetMode:
                            if prompStr.find(questionMark) != -1:
                                if progress > 0 and retMsg:
                                    self.strStatus.set(promptList[progress-1]['result'])
                                    self.statusBar.update()
                                if prompStr.find("joint") != -1:
                                    prompt = promptJointCalib
                                elif prompStr.find("Instinct") != -1:
                                    prompt = promptInstinct
                                elif prompStr.find("Calibrate") != -1:
                                    prompt = promptIMU
                                elif prompStr.find("assurance") != -1:
                                    serObj.Send_data(self.encode("n"))
                                    continue
                                # Update status bar before showing message box
                                # Only show first line in status bar (message box can show full text)
                                status_message = prompt['message'].split('\n')[0].strip()
                                self.strStatus.set(status_message)
                                self.statusBar.update()
                                retMsg = messagebox.askyesno(txt('Warning'), prompt['message'])
                                if retMsg:
                                    self.strStatus.set(prompt['operating'])
                                    self.statusBar.update()
                                    serObj.Send_data(self.encode("Y"))
                                else:
                                    self.strStatus.set('')
                                    self.statusBar.update()
                                    serObj.Send_data(self.encode("n"))
                                progress += 1
                            if prompStr.find("Ready!") != -1:
                                break
                    else:
                        if prompStr.find(questionMark) != -1:
                            if self.bParaUpload and (strBoardVersion in NyBoard_version_list):  # for NyBoard upgrade firmware
                                if progress > 0 and retMsg:
                                    self.strStatus.set(promptList[progress-1]['result'])
                                    self.statusBar.update()
                                if prompStr.find("joint") != -1:
                                    prompt = promptJointCalib
                                elif prompStr.find("Instinct") != -1:
                                    prompt = promptInstinct
                                elif prompStr.find("Calibrate") != -1:
                                    prompt = promptIMU
                                elif prompStr.find("assurance") != -1:
                                    serObj.Send_data(self.encode("n"))
                                    continue
                                # Update status bar before showing message box
                                # Only show first line in status bar (message box can show full text)
                                status_message = prompt['message'].split('\n')[0].strip()
                                self.strStatus.set(status_message)
                                self.statusBar.update()
                                retMsg = messagebox.askyesno(txt('Warning'), prompt['message'])
                                if retMsg:
                                    self.strStatus.set(prompt['operating'])
                                    self.statusBar.update()
                                    serObj.Send_data(self.encode("Y"))
                                else:
                                    self.strStatus.set('')
                                    self.statusBar.update()
                                    serObj.Send_data(self.encode("n"))
                                progress += 1
                            else:    # for BiBoard upgrade firmware
                                if prompStr.find("joint") != -1:
                                    prompt = promptJointCalib
                                    serObj.Send_data(self.encode("n"))
                                elif prompStr.find("Instinct") != -1:
                                    prompt = promptInstinct
                                    serObj.Send_data(self.encode("n"))
                                elif prompStr.find("Calibrate") != -1:
                                    prompt = promptIMU
                                    serObj.Send_data(self.encode("n"))
                                elif prompStr.find("assurance") != -1:
                                    serObj.Send_data(self.encode("n"))
                                    continue
                        elif prompStr.find(questionMark) == -1 and self.bParaUpload:
                            if prompStr[:3] == "IMU":
                                if progress > 0 and retMsg:
                                    self.strStatus.set(promptList[progress - 1]['result'])
                                    self.statusBar.update()
                                counterIMU += 1
                                if counterIMU == 3:
                                    self.bIMUerror = True
                                    self.strStatus.set(txt('caliIMUerrorStatus'))
                                    self.statusBar.update()
                                    break

                        if prompStr.find("sent to mpu.setXAccelOffset") != -1 or prompStr.find("Ready!") != -1:
                            if strBoardVersion in NyBoard_version_list:
                                if retMsg:
                                    self.strStatus.set(promptList[progress - 1]['result'])
                                    self.statusBar.update()
                                if strSoftwareVersion == '2.0':
                                    continue
                                else:
                                    break
                            else:
                                break
                        elif prompStr.find("Calibrated:") != -1:
                            self.strStatus.set(txt('9685 Calibrated'))
                            self.statusBar.update()
                            break
            else:
                if self.bFacReset:    # for NyBoard Factory reset
                    if strBoardVersion in NyBoard_version_list:
                        if prompStr.find("Optional: Connect PWM 3") != -1 and (not bCount):
                            bCount = True
                            start = time.time()
                            logger.info(f"start timer")
                        if bCount and (time.time() - start > 5):
                            break
                else:    # for NyBoard upgrade firmware
                    if (strBoardVersion in NyBoard_version_list) and (prompStr.find("Optional: Connect PWM 3") != -1):
                        break

        serObj.Close_Engine()
        logger.info("close the serial port.")
        self.force_focus()

        if self.bIMUerror and strBoardVersion in NyBoard_version_list:
            # Update status bar before showing message box
            self.strStatus.set(txt('caliIMUerrorMessage'))
            self.statusBar.update()
            messagebox.showwarning(txt('Warning'), message=txt('caliIMUerrorMessage'))
            return

        if not self.bFacReset and strBoardVersion in NyBoard_version_list:
            # Update status bar before showing message box
            # Only show first line in status bar (message box can show full text)
            status_message = txt('parameterFinish').split('\n')[0].strip()
            self.strStatus.set(status_message)
            self.statusBar.update()
            messagebox.showinfo(title=None, message=txt('parameterFinish'))


    def saveConfig(self,filename):
        if len(self.configuration) == 6:
            self.configuration = [self.defaultLan, self.lastSetting[0], self.lastSetting[1], self.lastSetting[2],
                                  self.lastSetting[3], self.lastSetting[4]]
        else:
            self.configuration = [self.defaultLan, self.lastSetting[0], self.lastSetting[1], self.lastSetting[2],
                                  self.lastSetting[3], self.lastSetting[4], self.configuration[6],self.configuration[7]]

        saveConfigToFile(self.configuration, filename)

        # 更新配置文件
        # 第9行：保存此次运行程序时的系统串口列表
        # 第10行：保存此次运行程序得到的可以打开的串口列表
        allPortNames = portStrList
        newValidPorts = readValidPortsFromConfig()
        if self.validPort != "" and self.validPort not in newValidPorts:
            newValidPorts.append(self.validPort)
        savePortsToConfig(allPortNames, newValidPorts)


    def showMessage(self,sta):
        self.strStatus.set(sta)
        self.statusBar.update()

        if self.OSname == 'aqua':    # for macOS
            # folder_path = "file:///Applications/Petoi Desktop App.app/Contents/Resources"
            folder_path = "/Applications/Petoi Desktop App.app/Contents/Resources" + '\n'
        else:    # for Windows or Linux
            path = os.getcwd()
            # folder_path = "file://" + path  # Replace with the actual folder path
            folder_path = path + '\n'  # Replace with the actual folder path

        print(folder_path)
        messagebox.showinfo('Petoi Desktop App', txt('logLocation') + folder_path + txt('checkLogfile'))
        # Open the folder in the default file browser
        # webbrowser.open_new_tab(folder_path)


    def autoupload(self):
        # No need to pause thread anymore - using main-thread timer now
        try:
            logger.info(f"lastSetting: {self.lastSetting}.")
            strProd = self.strProduct.get()
            strDefaultPath = self.strFileDir.get()
            strSoftwareVersion = self.strSoftwareVersion.get()
            strBoardVersion = self.strBoardVersion.get()
            strMode = self.inv_txt[self.strMode.get()]
            self.currentSetting = [strProd, strDefaultPath, strSoftwareVersion, strBoardVersion, strMode]
            logger.info(f"currentSetting: {self.currentSetting}.")

            if self.strFileDir.get() == '' or self.strFileDir.get() == ' ':
                # Update status bar before showing message box
                self.strStatus.set(txt('msgFileDir'))
                self.statusBar.update()
                messagebox.showwarning(txt('Warning'), txt('msgFileDir'))
                self.force_focus()  # force the main interface to get focus
                return False

            # NyBoard_V1_X software version are all the same
            if "NyBoard_V1" in strBoardVersion:
                pathBoardVersion = "NyBoard_V1"
            else:
                pathBoardVersion = strBoardVersion

            if strProd == "Bittle X":
                strProdPath = "Bittle"
            elif strProd == "Bittle X+Arm":
                strProdPath = "BittleX+Arm"
            elif strProd == "Nybble Q":
                strProdPath = "Nybble"
            else:
                strProdPath = strProd
            path = self.strFileDir.get() + '/' + strSoftwareVersion + '/' + strProdPath + '/' + pathBoardVersion + '/'

            if self.OSname == 'x11' or self.OSname == 'aqua':
                port = '/dev/' + self.strPort.get()
            else:
                port = self.strPort.get()
            logger.info(f"{self.strPort.get()}")
            if port == ' ' or port == '':
                # Update status bar before showing message box
                self.strStatus.set(txt('msgPort'))
                self.statusBar.update()
                messagebox.showwarning(txt('Warning'), txt('msgPort'))
                self.force_focus()
                return False

            if strBoardVersion in NyBoard_version_list:
                if self.bFacReset:
                    fnWriteI = path + 'WriteInstinctAutoInit.ino.hex'
                    fnOpenCat = path + 'OpenCatStandard.ino.hex'
                    self.currentSetting[4] = 'Standard'
                else:
                    fnWriteI = path + 'WriteInstinct.ino.hex'
                    fnOpenCat = path + 'OpenCat' + strMode + '.ino.hex'
                filename = [fnWriteI, fnOpenCat]
                logger.info(f"{filename}")
                uploadStage = ['Parameters', 'Main function']
                for s in range(len(uploadStage)):
                    # if s == 0 and self.bParaUploaded and self.currentSetting[:4] == self.lastSetting[:4]:
                    # for NyBoard uplod mode only
                    if s == 0 and (not self.bParaUpload):
                        continue               # no need upload configuration firmware
                    # if calibrate IMU failed
                    elif s == 1 and self.bIMUerror:
                        continue               # no need upload main function firmware

                    self.strStatus.set(txt('Uploading') + txt(uploadStage[s]) + '...' )
                    self.statusBar.update()
                    # self.inProgress = True
                    # status = txt('Uploading') + txt(uploadStage[s]) + '.'
                    # t = threading.Thread(target=self.progressiveDots, args=(status,))
                    # t.start()
                    if self.OSname == 'win32':
                        avrdudePath = resourcePath + 'avrdudeWin/'
                    elif self.OSname == 'x11':     # Linux
                        avrdudePath = '/usr/bin/'
                        path = pathlib.Path(avrdudePath + 'avrdude')
                        if not path.exists():
                            # Update status bar before showing message box
                            self.strStatus.set(txt('msgNoneAvrdude'))
                            self.statusBar.update()
                            messagebox.showwarning(txt('Warning'), txt('msgNoneAvrdude'))
                            self.force_focus()  # force the main interface to get focus
                            return False
                        # avrdudeconfPath = '/etc/avrdude/'      # Fedora / CentOS
                        avrdudeconfPath = '/etc/'            # Debian / Ubuntu
                    else:
                        avrdudePath = resourcePath + 'avrdudeMac/'

                    try:
                        # for NyBoard factory reset or upgrade firmware
                        if s == 0 and self.bIMUerror:    # alread upload configuration firmware,but calibrate IMU failed
                            pass                         # no need upload configuration firmware again
                        else:
                            if self.OSname == 'x11':     # Linuxself.OSname == 'x11':     # Linux
                                # Use list form to avoid shell parsing issues with paths containing spaces
                                cmd = [avrdudePath + 'avrdude', '-C', avrdudeconfPath + 'avrdude.conf', 
                                       '-v', '-V', '-patmega328p', '-carduino', '-P', port, 
                                       '-b115200', '-D', '-Uflash:w:' + filename[s] + ':i']
                                use_shell = False
                            else:
                                # Use list form to avoid shell parsing issues with paths containing spaces
                                cmd = [avrdudePath + 'avrdude', '-C', avrdudePath + 'avrdude.conf', 
                                       '-v', '-V', '-patmega328p', '-carduino', '-P', port, 
                                       '-b115200', '-D', '-Uflash:w:' + filename[s] + ':i']
                                use_shell = False

                            # Run the program and capture output in real-time
                            # Allow GUI to update display before blocking operation
                            self.win.update_idletasks()
                            
                            # Use Popen with PIPE for real-time output
                            process = subprocess.Popen(cmd, shell=use_shell, 
                                                     stdout=subprocess.PIPE,
                                                     stderr=subprocess.STDOUT,
                                                     bufsize=1,
                                                     universal_newlines=True,
                                                     encoding='ISO-8859-1')
                            
                            # Use thread-based timeout mechanism to avoid blocking
                            has_error = False
                            process_timeout = False
                            timeout_seconds = 30  # 30 seconds timeout (reduced from 120)
                            last_output_time = [time.time()]  # Use list to allow modification in thread
                            output_queue = queue.Queue()
                            reader_finished = [False]
                            fuse_error_detected = [False]  # Track fuse-related errors
                            
                            # Thread function to read output
                            def read_output():
                                try:
                                    while True:
                                        line = process.stdout.readline()
                                        if not line:
                                            break
                                        output_queue.put(line)
                                        last_output_time[0] = time.time()
                                except:
                                    pass
                                finally:
                                    reader_finished[0] = True
                            
                            # Start reader thread
                            reader_thread = threading.Thread(target=read_output, daemon=True)
                            reader_thread.start()
                            
                            # Main loop: process output and monitor timeout
                            while True:
                                # Check if we have output to process
                                try:
                                    line = output_queue.get(timeout=0.1)
                                    line = line.strip()
                                    if line:
                                        logger.info(line)
                                        self.processConsoleQueue()
                                        
                                        # Check for fuse-related errors that often cause hanging
                                        if ("lfuse changed" in line.lower()) or \
                                           ("hfuse changed" in line.lower()) or \
                                           ("efuse changed" in line.lower()):
                                            fuse_error_detected[0] = True
                                            logger.info("Warning: Fuse change detected - may cause hanging")
                                        
                                        # Check for error messages
                                        if ("programmer is not responding" in line) or \
                                            ("can't open device" in line) or \
                                            ("attempt" in line) or \
                                            ("error" in line.lower()) or \
                                            ("Errno" in line):
                                            has_error = True
                                except queue.Empty:
                                    pass
                                
                                # Check if reader thread finished
                                if reader_finished[0] and output_queue.empty():
                                    break
                                
                                # Check for timeout (shorter timeout if fuse error detected)
                                current_timeout = 10 if fuse_error_detected[0] else timeout_seconds
                                if time.time() - last_output_time[0] > current_timeout:
                                    if fuse_error_detected[0]:
                                        logger.info(f"Timeout: No output for {current_timeout} seconds after fuse error")
                                    else:
                                        logger.info(f"Timeout: No output from avrdude for {current_timeout} seconds")
                                    process.kill()
                                    process_timeout = True
                                    has_error = True
                                    break
                                
                                # Allow GUI to update
                                self.win.update_idletasks()
                            
                            # Wait for process to complete (with timeout)
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                            
                            # Wait for reader thread to finish
                            reader_thread.join(timeout=2)
                            
                            # Final console queue processing
                            self.processConsoleQueue()
                            
                            # Check if there were errors
                            if process_timeout:
                                status = txt(uploadStage[s]) + txt('failed to upload') + ' (Timeout)'
                                self.strStatus.set(status)
                                self.statusBar.update()
                                logger.info(f"Upload failed: avrdude timeout - possibly wrong port selected")
                                return False
                            elif has_error or process.returncode != 0:
                                status = txt(uploadStage[s]) + txt('failed to upload')
                                self.strStatus.set(status)
                                self.statusBar.update()
                                return False
                            
                            time.sleep(0.2)

                    # self.inProgress = False
                    except:
                        status = txt(uploadStage[s]) + txt('failed to upload')
                        self.strStatus.set(status)
                        self.statusBar.update()
                        # Update status bar before showing message box
                        self.strStatus.set(txt('Replug prompt'))
                        self.statusBar.update()
                        messagebox.showwarning(txt('Warning'), txt('Replug prompt'))
                        return False
                    else:
                        status = txt(uploadStage[s]) + txt('is successully uploaded')
                    
                    self.strStatus.set(status)
                    self.statusBar.update()

                    if s == 0:
                        self.WriteInstinctPrompts(port)
                    else:
                        pass
            elif strBoardVersion in BiBoard_version_list:
                modeName = "Standard"
                # fnBootLoader = path + 'OpenCatEsp32Standard.ino.bootloader.bin'
                fnBootLoader = path + 'OpenCatEsp32' + modeName + '.ino.bootloader.bin'
                # fnPartitions = path + 'OpenCatEsp32Standard.ino.partitions.bin'
                fnPartitions = path + 'OpenCatEsp32' + modeName + '.ino.partitions.bin'
                # fnMainFunc = path + 'OpenCatEsp32Standard.ino.bin'
                fnMainFunc = path + 'OpenCatEsp32' + modeName + '.ino.bin'
                fnBootApp = path + 'boot_app0.bin'

                filename = [fnBootLoader, fnPartitions, fnBootApp, fnMainFunc]
                logger.info(f"{filename}")
                self.strStatus.set(txt('Uploading') + txt('Main function') + ', ' + txt('Time consuming') + '...' )
                self.statusBar.update()
                if self.OSname == 'win32':   # Windows
                    esptoolPath = resourcePath + 'esptoolWin/'
                elif self.OSname == 'x11':  # Linux
                    esptoolPath = '/usr/bin/'
                    path = pathlib.Path(esptoolPath + 'esptool')
                    if not path.exists():
                        # Update status bar before showing message box
                        self.strStatus.set(txt('msgNoneEsptool'))
                        self.statusBar.update()
                        messagebox.showwarning(txt('Warning'), txt('msgNoneEsptool'))
                        self.force_focus()  # force the main interface to get focus
                        return False
                else:    # Mac
                    esptoolPath = resourcePath + 'esptoolMac/'
                # print()
                try:
                    # check_call(esptoolPath + 'esptool --chip esp32 --port %s --baud 921600 --before default_reset --after hard_reset write_flash -z --flash_mode dio --flash_freq 80m --flash_size 16MB 0x1000 %s 0x8000 %s 0xe000 %s 0x10000 %s' % \
                    # (port, filename[0], filename[1], filename[2], filename[3]), shell=self.shellOption)
                    # subprocess.check_call(esptoolPath + 'esptool --chip esp32 --port %s --baud 921600 --before default_reset --after hard_reset write_flash -z --flash_mode dio --flash_freq 80m --flash_size 4MB 0x1000 %s 0x8000 %s 0xe000 %s 0x10000 %s' % \
                    #     (port, filename[0], filename[1], filename[2], filename[3]), shell=self.shellOption)
                    # Use list form to avoid shell parsing issues with paths containing spaces
                    cmd = [esptoolPath + 'esptool', '--chip', 'esp32', '--port', port, 
                           '--baud', '921600', '--before', 'default_reset', '--after', 'hard_reset', 
                           'write_flash', '-z', '--flash_mode', 'dio', '--flash_freq', '80m', 
                           '--flash_size', '4MB', '0x1000', filename[0], 
                           '0x8000', filename[1], '0xe000', filename[2], '0x10000', filename[3]]
                    # Run the program and capture output in real-time
                    # Allow GUI to update display before blocking operation
                    self.win.update_idletasks()
                    
                    # Use Popen with PIPE for real-time output
                    process = subprocess.Popen(cmd, shell=False, 
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             bufsize=1,
                                             universal_newlines=True,
                                             encoding='ISO-8859-1')
                    
                    # Use thread-based timeout mechanism to avoid blocking
                    has_error = False
                    process_timeout = False
                    timeout_seconds = 30  # 30 seconds timeout (reduced from 120)
                    last_output_time = [time.time()]  # Use list to allow modification in thread
                    output_queue = queue.Queue()
                    reader_finished = [False]
                    
                    # Thread function to read output
                    def read_output():
                        try:
                            while True:
                                line = process.stdout.readline()
                                if not line:
                                    break
                                output_queue.put(line)
                                last_output_time[0] = time.time()
                        except:
                            pass
                        finally:
                            reader_finished[0] = True
                    
                    # Start reader thread
                    reader_thread = threading.Thread(target=read_output, daemon=True)
                    reader_thread.start()
                    
                    # Main loop: process output and monitor timeout
                    while True:
                        # Check if we have output to process
                        try:
                            line = output_queue.get(timeout=0.1)
                            line = line.strip()
                            if line:
                                logger.info(line)
                                self.processConsoleQueue()
                                
                                # Check for error messages
                                if ("Traceback" in line) or \
                                    ("Failed to connect to ESP32" in line) or \
                                    ("error" in line.lower()) or \
                                    ("Errno" in line):
                                    has_error = True
                        except queue.Empty:
                            pass
                        
                        # Check if reader thread finished
                        if reader_finished[0] and output_queue.empty():
                            break
                        
                        # Check for timeout
                        if time.time() - last_output_time[0] > timeout_seconds:
                            logger.info(f"Timeout: No output from esptool for {timeout_seconds} seconds")
                            process.kill()
                            process_timeout = True
                            has_error = True
                            break
                        
                        # Allow GUI to update
                        self.win.update_idletasks()
                    
                    # Wait for process to complete (with timeout)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    
                    # Wait for reader thread to finish
                    reader_thread.join(timeout=2)
                    
                    # Final console queue processing
                    self.processConsoleQueue()
                    
                    # Check if there were errors
                    if process_timeout:
                        status = txt('Main function') + txt('failed to upload') + ' (Timeout)'
                        self.strStatus.set(status)
                        self.statusBar.update()
                        logger.info(f"Upload failed: esptool timeout - possibly wrong port selected")
                        return False
                    elif has_error or process.returncode != 0:
                        status = txt('Main function') + txt('failed to upload')
                        self.strStatus.set(status)
                        self.statusBar.update()
                        return False
                    
                    time.sleep(0.2)

                except Exception as e:
                    printH("Excep:", e)
                    logger.info(f"Excep: {e}")
                    status = txt('Main function') + txt('failed to upload')
                    # self.strStatus.set(status)
                    # self.statusBar.update()
                    # self.showMessage(status)
                    return False
                else:
                    # Don't set success status here - let WriteInstinctPrompts handle status updates
                    # Status will be set after WriteInstinctPrompts completes
                    pass
                    
                # Call WriteInstinctPrompts first, then set success status if needed
                self.WriteInstinctPrompts(port)
                
                # Set success status after WriteInstinctPrompts completes
                # Only if no errors occurred (bIMUerror will be set if there's an error)
                if not self.bIMUerror:
                    status = txt('Main function') + txt('is successully uploaded')
                    self.strStatus.set(status)
                    self.statusBar.update()

            # for there is no calibrate IMU error
            if not self.bIMUerror:
                print('Finish!')
                # Update status bar before showing message box
                self.strStatus.set(txt('msgFinish'))
                self.statusBar.update()
                messagebox.showinfo(title=None, message=txt('msgFinish'))
            self.force_focus()  # force the main interface to get focus

            self.lastSetting = self.currentSetting
            self.validPort = self.strPort.get()
            if self.bFacReset:
                self.strMode.set(txt('Standard'))
            self.saveConfig(defaultConfPath)

            return True
        except Exception as e:
            logger.error(f"Error in autoupload: {e}")
            return False
        
    def setupConsoleLogging(self):
        """Set up custom logging handler to redirect logs to Console text widget"""
        try:
            # Create a custom handler that also stores logs in memory before GUI is ready
            console_handler = ConsoleHandler(self.txtConsole, self.logQueue)
            # Format: timestamp - levelname - message (no module name)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.INFO)
            
            # Only add handler to root logger (will capture all child loggers including ardSerial)
            root_logger = logging.getLogger()
            root_logger.addHandler(console_handler)
            
            self.console_handler = console_handler
            
            # Display any startup logs that were recorded before GUI was ready
            self.displayStartupLogs()
        except Exception as e:
            print(f"Error setting up console logging: {e}")
    
    def displayStartupLogs(self):
        """Display startup logs that were generated before GUI was ready"""
        try:
            # Display startup information directly to console
            import sys
            import time
            
            self.txtConsole.config(state=NORMAL)
            
            # Format timestamp
            current_time = time.strftime('%Y-%m-%d %H:%M:%S')
            ms = int((time.time() % 1) * 1000)
            timestamp = f"{current_time},{ms:03d}"
            
            # Display startup logs in the same format as logging
            startup_logs = [
                f"{timestamp} - INFO - ardSerial date: {ardSerialDate}\n",
                # f"\n",
                f"{timestamp} - INFO - Python version is {sys.version.split()[0].split('.')}\n"
            ]
            
            # Save the first 2 startup log lines for later restoration (after Clear button)
            self.savedStartupLogs = [
                f"{timestamp} - INFO - ardSerial date: {ardSerialDate}",
                f"{timestamp} - INFO - Python version is {sys.version.split()[0].split('.')}"
            ]
            
            # Add configuration info if available
            if hasattr(self, 'configuration') and len(self.configuration) >= 6:
                # startup_logs.append(f"\n")
                startup_logs.append(f"{timestamp} - INFO - {self.configuration}\n")
            
            # Add firmware folder info
            if hasattr(self, 'strFileDir'):
                # startup_logs.append(f"\n")
                startup_logs.append(f"{timestamp} - INFO - The firmware file folder is {self.strFileDir.get()}\n")
            
            # Add port information (from initialization)
            if hasattr(self, 'strPort') and portStrList:
                # startup_logs.append(f"\n")
                startup_logs.append(f"{timestamp} - INFO - Refreshed port list from system: {portStrList}\n")
                
                if self.strPort.get():
                    # startup_logs.append(f"\n")
                    # Check if port was manually selected or auto-detected
                    if hasattr(self, 'portWasManuallySelected') and self.portWasManuallySelected:
                        startup_logs.append(f"{timestamp} - INFO - Preserved manually selected port: {self.strPort.get()}\n")
                    else:
                        startup_logs.append(f"{timestamp} - INFO - Automatically detected serial port: {self.strPort.get()}\n")
                
                # startup_logs.append(f"\n")
                startup_logs.append(f"{timestamp} - INFO - portStrList is {portStrList}\n")
            
            for log in startup_logs:
                self.txtConsole.insert(END, log)
            
            self.txtConsole.see(END)
            self.txtConsole.config(state=DISABLED)
            self.txtConsole.update_idletasks()
        except Exception as e:
            print(f"Error displaying startup logs: {e}")
    
    def prepareConsoleForNewOperation(self):
        """Prepare console for a new operation"""
        try:
            self.txtConsole.config(state=NORMAL)
            
            if self.isFirstOperation:
                # First operation: don't clear, just add a separator
                self.txtConsole.insert(END, "\n" + "="*80 + "\n")
                self.txtConsole.insert(END, "=== Starting Firmware Operation ===\n")
                self.txtConsole.insert(END, "="*80 + "\n\n")
                self.isFirstOperation = False
            else:
                # Subsequent operations: keep only first 2 lines of startup info
                # (ardSerial date and Python version)
                content = self.txtConsole.get(1.0, END)
                lines = content.split('\n')
                
                # Find the first 2 startup info lines
                startup_lines = []
                found_ardserial = False
                found_python = False
                
                for line in lines:
                    # Look for ardSerial date line
                    if 'ardSerial date' in line and not found_ardserial:
                        startup_lines.append(line)
                        found_ardserial = True
                    # Look for Python version line
                    elif 'Python version' in line and not found_python:
                        startup_lines.append(line)
                        found_python = True
                    
                    # Stop after finding both
                    if found_ardserial and found_python:
                        break
                
                # If startup lines not found in console (e.g., after Clear button),
                # use saved startup logs
                if not startup_lines and hasattr(self, 'savedStartupLogs'):
                    startup_lines = self.savedStartupLogs
                
                # Clear and restore only the first 2 startup lines
                self.txtConsole.delete(1.0, END)
                if startup_lines:
                    for line in startup_lines:
                        self.txtConsole.insert(END, line + '\n')
                    # Add empty line after startup info
                    self.txtConsole.insert(END, "\n")
                
                # Add separator for new operation
                self.txtConsole.insert(END, "="*80 + "\n")
                self.txtConsole.insert(END, "=== Starting Firmware Operation ===\n")
                self.txtConsole.insert(END, "="*80 + "\n\n")
            
            self.txtConsole.see(END)
            self.txtConsole.config(state=DISABLED)
            
            # Clear any pending log messages in queue
            while not self.logQueue.empty():
                try:
                    self.logQueue.get_nowait()
                except queue.Empty:
                    break
                    
            logger.debug("Console prepared for new operation")
        except Exception as e:
            print(f"Error preparing console for new operation: {e}")
    
    def clearConsole(self):
        """Clear the console text widget but preserve the first 2 startup log lines"""
        try:
            self.txtConsole.config(state=NORMAL)
            
            # Get current content
            content = self.txtConsole.get(1.0, END)
            lines = content.split('\n')
            
            # Find and preserve the first 2 startup log lines
            startup_lines = []
            found_ardserial = False
            found_python = False
            
            for line in lines:
                if 'ardSerial date' in line and not found_ardserial:
                    startup_lines.append(line)
                    found_ardserial = True
                elif 'Python version' in line and not found_python:
                    startup_lines.append(line)
                    found_python = True
                
                if found_ardserial and found_python:
                    break
            
            # If startup lines not found in console, use saved startup logs
            if not startup_lines and hasattr(self, 'savedStartupLogs'):
                startup_lines = self.savedStartupLogs
            
            # Clear and restore only the first 2 startup lines
            self.txtConsole.delete(1.0, END)
            if startup_lines:
                for line in startup_lines:
                    self.txtConsole.insert(END, line + '\n')
                # Add an empty line for separation
                self.txtConsole.insert(END, '\n')
            
            self.txtConsole.see(END)
            self.txtConsole.config(state=DISABLED)
            
            # Clear queue
            while not self.logQueue.empty():
                try:
                    self.logQueue.get_nowait()
                except queue.Empty:
                    break
        except Exception as e:
            print(f"Error clearing console: {e}")
    
    def copyConsole(self):
        """Copy selected text or all text from console widget to clipboard"""
        try:
            # Check if there is selected text
            if self.txtConsole.tag_ranges('sel'):
                # Get selected text
                selected_text = self.txtConsole.get('sel.first', 'sel.last')
                # Copy to clipboard
                self.win.clipboard_clear()
                self.win.clipboard_append(selected_text)
                self.strStatus.set(txt('Copied selected text to clipboard'))
                self.statusBar.update()
            else:
                # No selection, copy all text
                all_text = self.txtConsole.get('1.0', END)
                # Remove the last newline that Text widget always adds
                all_text = all_text.rstrip('\n')
                if all_text:
                    self.win.clipboard_clear()
                    self.win.clipboard_append(all_text)
                    self.strStatus.set(txt('Copied all output to clipboard'))
                    self.statusBar.update()
                else:
                    self.strStatus.set(txt('No output to copy'))
                    self.statusBar.update()
        except Exception as e:
            messagebox.showerror(txt('Error'), f'{txt("Error")}: {str(e)}')
            self.strStatus.set(txt('Failed to copy'))
            self.statusBar.update()
    
    def processConsoleQueue(self):
        """Immediately process all pending messages in the console queue for real-time display"""
        try:
            updated = False
            
            # Process ALL pending messages immediately
            while not self.logQueue.empty():
                try:
                    msg = self.logQueue.get_nowait()
                    if msg:
                        if not updated:
                            self.txtConsole.config(state=NORMAL)
                            updated = True
                        self.txtConsole.insert(END, msg)
                except queue.Empty:
                    break
            
            if updated:
                # Auto-scroll to the end
                self.txtConsole.see(END)
                # Disable text widget to make it read-only
                self.txtConsole.config(state=DISABLED)
                # Force immediate GUI update
                self.txtConsole.update_idletasks()
                self.win.update()  # Full update for immediate display
        except Exception as e:
            print(f"Error processing console queue: {e}")
    
    def updateConsoleFromQueue(self):
        """Update console text widget with messages from the log queue"""
        if not self.keepChecking:
            return
        
        try:
            # Process all pending log messages in the queue (up to 100 at a time to avoid blocking)
            updated = False
            count = 0
            max_batch = 100
            
            while not self.logQueue.empty() and count < max_batch:
                try:
                    msg = self.logQueue.get_nowait()
                    if msg:
                        if not updated:
                            self.txtConsole.config(state=NORMAL)
                            updated = True
                        self.txtConsole.insert(END, msg)
                        count += 1
                except queue.Empty:
                    break
            
            if updated:
                # Auto-scroll to the end
                self.txtConsole.see(END)
                # Disable text widget to make it read-only
                self.txtConsole.config(state=DISABLED)
                # Force update display immediately for better responsiveness
                self.txtConsole.update_idletasks()
        except Exception as e:
            print(f"Error updating console from queue: {e}")
        
        # Schedule next update with shorter interval for better real-time display
        if self.keepChecking:
            self.win.after(self.logUpdateInterval, self.updateConsoleFromQueue)
    
    def force_focus(self):
        self.win.after(1, lambda: self.win.focus_force())
        
    def on_closing(self):
        if messagebox.askokcancel(txt('Quit'), txt('Do you want to quit?')):
            # Stop main-thread timer
            self.keepChecking = False
            
            # Remove console handler from root logger
            if hasattr(self, 'console_handler'):
                root_logger = logging.getLogger()
                root_logger.removeHandler(self.console_handler)
            if not self.uploadSuccess:
                self.saveConfig(defaultConfPath)
            logger.info(f"{self.configuration}")
            self.win.destroy()

if __name__ == '__main__':
    model = 'Bittle'
    Uploader = Uploader(model, language)
