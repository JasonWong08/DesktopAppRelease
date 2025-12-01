#!/usr/bin/python3
# -*- coding: UTF-8 -*-

# Junfeng Wang
# Petoi LLC
# Jun. 26th, 2024


from commonVar import *
from tkinter import ttk
from datetime import datetime

language = languageList['English']

def txt(key):
    return language.get(key, textEN[key])
    
class Debugger:
    def __init__(self,model,lan):
        global language
        language = lan
#        global goodPorts
        connectPort(goodPorts)
        start = time.time()
        while config.model_ == '':
            if time.time() - start > 5:
                config.model_ = model    # If can not get the model name, use the model set in the UI interface.
            time.sleep(0.01)
        self.configName = config.model_

        self.winDebug = Tk()
        self.debuggerReady = False
        self.dialogType = "voiceRst"
        self.strStatus = StringVar()
        
        # Serial port related variables
        self.availablePorts = []
        self.currentPort = None
        self.isConnected = False
        self.receiveThread = None
        self.stopReceiveThread = False
        self.autoscroll = BooleanVar(value=True)
        self.showTimestamp = BooleanVar(value=False)

        self.OSname = self.winDebug.call('tk', 'windowingsystem')
        if self.OSname == 'win32':
            # Windows
            self.winDebug.iconbitmap(resourcePath + 'Petoi.ico')
            self.winDebug.geometry('760x700+330+100')
        elif self.OSname == 'aqua':
            # macOS - slightly different size and position for Retina displays
            self.winDebug.geometry('780x720+300+80')
            self.backgroundColor = 'gray'
        else:
            # Linux
            self.winDebug.tk.call('wm', 'iconphoto', self.winDebug._w, "-default",
                                PhotoImage(file= resourcePath + 'Petoi.png'))
            self.winDebug.geometry('800x720+280+80')

        self.myFont = tkFont.Font(
            family='Times New Roman', size=20, weight='bold')
        self.normalFont = tkFont.Font(family='Arial', size=12)
        self.winDebug.title(txt('Debugger'))
        self.createMenu()
        
        # Configure main window columns for centering
        self.winDebug.columnconfigure(0, weight=1)
        self.winDebug.columnconfigure(1, weight=0)
        self.winDebug.columnconfigure(2, weight=1)
        
        # Row 0: Model label
        self.modelLabel = Label(self.winDebug, text=displayName(self.configName), font=self.myFont)
        self.modelLabel.grid(row=0, column=0, columnspan=3, pady=10)

        # Row 1: Reset voice module button (centered)
        bw = 23
        voiceResetButton = Button(self.winDebug, text=txt('Reset voice module'), font=self.myFont, fg='blue',
                                  width=bw, relief='raised',command=lambda: self.resetVoice())
        voiceResetButton.grid(row=1, column=1, pady=(0, 10))
        tip(voiceResetButton, txt('tipRstVoice'))

        # Row 2: Calibrate gyroscope button (centered)
        imuCaliButton = Button(self.winDebug, text=txt('Calibrate gyroscope'), font=self.myFont, fg='blue', width=bw,
                               relief='raised',
                               command=lambda: self.imuCali())
        imuCaliButton.grid(row=2, column=1, pady=(0, 10))
        tip(imuCaliButton, txt('tipImuCali'))
        
        # Store reference to button for later width matching
        self.refButton = imuCaliButton

        # Row 3: Serial port selection and connection status (aligned with buttons above)
        self.fmSerial = Frame(self.winDebug)
        self.fmSerial.grid(row=3, column=1, pady=(0, 10))
        
        # Get available ports
        self.updateAvailablePorts()
        
        # Connection status button - create first to measure its width
        self.connectBtn = Button(self.fmSerial, text=txt('Connected') if self.isConnected else txt('Connect'),
                                fg='green' if self.isConnected else 'red',
                                relief=SUNKEN if self.isConnected else RAISED,
                                font=self.normalFont, width=12,
                                command=self.toggleConnection)
        self.connectBtn.pack(side=RIGHT, padx=(2, 0))
        
        # Serial port combobox - will fill remaining space
        self.portCombo = ttk.Combobox(self.fmSerial, values=self.availablePorts, state='readonly', 
                                      font=self.normalFont)
        self.portCombo.pack(side=LEFT, fill=X, expand=True, padx=(0, 2))
        if len(goodPorts) > 0:
            # Set default to first connected port
            firstPort = list(goodPorts.values())[0]
            if firstPort in self.availablePorts:
                self.portCombo.set(firstPort)
                self.currentPort = list(goodPorts.keys())[0]
                self.isConnected = True
                # Update button state to reflect connection
                self.connectBtn.config(text=txt('Connected'), fg='green', relief=SUNKEN)
        elif len(self.availablePorts) > 0:
            self.portCombo.set(self.availablePorts[0])

        # Row 4: Status bar
        fmStatus = ttk.Frame(self.winDebug)
        fmStatus.grid(row=4, column=1, ipadx=2, pady=5, sticky=W + E)
        self.statusBar = ttk.Label(fmStatus, textvariable=self.strStatus, font=('Arial', 14), relief=SUNKEN)
        self.statusBar.grid(row=0, ipadx=5, sticky=W + E)
        fmStatus.columnconfigure(0, weight=1)
        
        # Row 5-7: Main terminal frame (contains input, output, and controls)
        fmSerialMonitor = ttk.Frame(self.winDebug)
        fmSerialMonitor.grid(row=5, column=1, pady=(5, 10), sticky=W + E + N + S)
        
        # Command input frame
        fmInput = ttk.Frame(fmSerialMonitor)
        fmInput.grid(row=0, column=0, pady=(0, 5), sticky=W + E)
        
        self.cmdInput = Entry(fmInput, font=self.normalFont)
        self.cmdInput.grid(row=0, column=0, sticky=W + E, padx=(0, 5))
        self.cmdInput.bind('<Return>', lambda e: self.sendCommand())
        
        self.sendBtn = Button(fmInput, text=txt('Send'), font=self.normalFont, width=10,
                             command=self.sendCommand)
        self.sendBtn.grid(row=0, column=1)
        
        fmInput.columnconfigure(0, weight=1)
        
        # Output text frame
        fmOutput = ttk.Frame(fmSerialMonitor)
        fmOutput.grid(row=1, column=0, pady=(0, 5), sticky=W + E + N + S)
        
        # Text widget with scrollbar
        scrollbar = Scrollbar(fmOutput)
        scrollbar.grid(row=0, column=1, sticky=N + S)
        
        # Use tabstops to ensure proper alignment (every 1.2cm)
        tabstops = tuple([f'{i * 1.2}c' for i in range(1, 50)])  # Create 50 tab stops
        self.outputText = Text(fmOutput, height=15, width=90, font=('Courier New', 10),
                              yscrollcommand=scrollbar.set, wrap=WORD, tabs=tabstops)
        self.outputText.grid(row=0, column=0, sticky=W + E + N + S)
        scrollbar.config(command=self.outputText.yview)
        
        fmOutput.columnconfigure(0, weight=1)
        fmOutput.rowconfigure(0, weight=1)
        
        # Control buttons frame
        fmControls = ttk.Frame(fmSerialMonitor)
        fmControls.grid(row=2, column=0, sticky=W + E)
        
        # Left side: checkboxes
        self.autoscrollCheck = Checkbutton(fmControls, text=txt('Autoscroll'), 
                                          variable=self.autoscroll, font=self.normalFont)
        self.autoscrollCheck.grid(row=0, column=0, padx=(0, 10), sticky=W)
        
        self.timestampCheck = Checkbutton(fmControls, text=txt('Show timestamp'),
                                         variable=self.showTimestamp, font=self.normalFont)
        self.timestampCheck.grid(row=0, column=1, padx=(0, 10), sticky=W)
        
        # Right side: copy and clear buttons
        self.copyBtn = Button(fmControls, text=txt('Copy'), font=self.normalFont, width=12,
                             command=self.copyOutput)
        self.copyBtn.grid(row=0, column=2, padx=(0, 5), sticky=E)
        
        self.clearBtn = Button(fmControls, text=txt('Clear output'), font=self.normalFont, width=12,
                              command=self.clearOutput)
        self.clearBtn.grid(row=0, column=3, sticky=E)
        
        fmControls.columnconfigure(1, weight=1)
        
        # Configure terminal frame to expand
        fmSerialMonitor.columnconfigure(0, weight=1)
        fmSerialMonitor.rowconfigure(1, weight=1)
        
        # Set row weights to enable expandable space
        self.winDebug.rowconfigure(5, weight=1)

        self.debuggerReady = True
        
        # Start serial receive thread if connected
        if self.isConnected:
            self.startReceiveThread()
        
        self.winDebug.protocol('WM_DELETE_WINDOW', self.on_closing)
        self.winDebug.update()
        
        # Now that window is rendered, match frame width to button width
        self.matchSerialFrameWidth()
        
        self.winDebug.resizable(True, True)
        self.winDebug.focus_force()    # force the main interface to get focus
        self.winDebug.mainloop()
        
    
    def createMenu(self):
        self.menubar = Menu(self.winDebug, background='#ff8000', foreground='black', activebackground='white',
                            activeforeground='black')
        file = Menu(self.menubar, tearoff=0, background='#ffcc99', foreground='black')
        for m in modelOptions:
            file.add_command(label=m, command=lambda model=m: self.changeModel(model))
        self.menubar.add_cascade(label=txt('Model'), menu=file)

        lan = Menu(self.menubar, tearoff=0)
        for l in languageList:
            lan.add_command(label=languageList[l]['lanOption'], command=lambda lanChoice=l: self.changeLan(lanChoice))
        self.menubar.add_cascade(label=txt('lanMenu'), menu=lan)

        helpMenu = Menu(self.menubar, tearoff=0)
        helpMenu.add_command(label=txt('About'), command=self.showAbout)
        self.menubar.add_cascade(label=txt('Help'), menu=helpMenu)

        self.winDebug.config(menu=self.menubar)


    def changeModel(self, modelName):
        self.modelLabel.configure(text=modelName)
        
    
    def changeLan(self, l):
        global language
        if self.debuggerReady and txt('lan') != l:
            # Get current status bar text before language change
            currentStatus = self.strStatus.get()
            
            language = copy.deepcopy(languageList[l])
            self.menubar.destroy()
            self.createMenu()
            self.winDebug.title(txt('Debugger'))
            self.winDebug.winfo_children()[1].config(text=txt('Reset voice module'))
            tip(self.winDebug.winfo_children()[1], txt('tipRstVoice'))
            self.winDebug.winfo_children()[2].config(text=txt('Calibrate gyroscope'))
            tip(self.winDebug.winfo_children()[2], txt('tipImuCali'))
            
            # Update connection button text based on current state
            self.connectBtn.config(text=txt('Connected') if self.isConnected else txt('Connect'))
            
            # Update other UI elements
            self.sendBtn.config(text=txt('Send'))
            self.autoscrollCheck.config(text=txt('Autoscroll'))
            self.timestampCheck.config(text=txt('Show timestamp'))
            self.copyBtn.config(text=txt('Copy'))
            self.clearBtn.config(text=txt('Clear output'))
            
            # Re-translate status bar text if it matches known translation keys
            if currentStatus and currentStatus.strip():
                self._retranslateStatusBar(currentStatus)
    
    def _retranslateStatusBar(self, currentStatus):
        """Re-translate status bar text when language changes"""
        # List of status message keys that might be displayed
        statusKeys = [
            'Copied selected text to clipboard',
            'Copied all output to clipboard',
            'No output to copy',
            'Failed to copy',
            'Output cleared',
            'Failed to send command',
            'Reset voice module',
            'Calibrate gyroscope',
            'calibrating IMU',
            'Reset successfully',
            'IMU Calibration successfully',
            'IMU Calibration failed'
        ]
        
        # Check if current status matches any translation of these keys in any language
        for key in statusKeys:
            # Check against all languages to find which key this status corresponds to
            for langDict in languageList.values():
                translatedValue = langDict.get(key, '')
                if translatedValue and currentStatus == translatedValue:
                    # Found matching key - re-translate with new language
                    self.strStatus.set(txt(key))
                    return
        
        # Check for status messages with additional info (format: "Key: value" or "Key value")
        # Check for "Sent: cmd" pattern - try all languages
        for langDict in languageList.values():
            sentText = langDict.get('Sent', '')
            if sentText and currentStatus.startswith(sentText + ':'):
                cmd = currentStatus.split(':', 1)[-1].strip()
                if cmd:
                    self.strStatus.set(f'{txt("Sent")}: {cmd}')
                    return
        
        # Check for "Connected to port" pattern
        for langDict in languageList.values():
            connectedText = langDict.get('Connected to', '')
            if connectedText and currentStatus.startswith(connectedText):
                # Extract port name (everything after "Connected to")
                portName = currentStatus[len(connectedText):].strip()
                if portName:
                    self.strStatus.set(f'{txt("Connected to")} {portName}')
                    return
        
        # Check for "Disconnected from port" pattern
        for langDict in languageList.values():
            disconnectedText = langDict.get('Disconnected from', '')
            if disconnectedText and currentStatus.startswith(disconnectedText):
                # Extract port name (everything after "Disconnected from")
                portName = currentStatus[len(disconnectedText):].strip()
                if portName:
                    self.strStatus.set(f'{txt("Disconnected from")} {portName}')
                    return
        
        # Check for "Failed to open port: port" pattern
        for langDict in languageList.values():
            failedText = langDict.get('Failed to open port', '')
            if failedText and currentStatus.startswith(failedText + ':'):
                portName = currentStatus.split(':', 1)[-1].strip()
                if portName:
                    self.strStatus.set(f'{txt("Failed to open port")}: {portName}')
                    return
            
    
    def showAbout(self):
        messagebox.showinfo(txt('titleVersion'), txt('msgVersion'))
        self.winDebug.focus_force()

            
    def createImage(self, frame, imgFile, imgW):
        img = Image.open(imgFile)

        ratio = img.size[0] / imgW
        img = img.resize((imgW, round(img.size[1] / ratio)))
        image = ImageTk.PhotoImage(img)
        imageFrame = Label(frame, image=image)
        imageFrame.image = image
        return imageFrame


    def resetVoice(self):
        if self.debuggerReady == 1:
            if not self.isConnected or not self.currentPort:
                messagebox.showwarning(txt('Warning'), txt('Please connect to a serial port first'))
                return
            
            cmd = "XAc"
            try:
                self.currentPort.Send_data(self.encode(cmd))
                self.displayOutput(f">> {cmd}")
                self.strStatus.set(txt('Reset voice module'))
                self.statusBar.update()
                self.dialogType = "voiceRst"
                self.showDialog(self.dialogType)
            except Exception as e:
                messagebox.showerror(txt('Error'), f'{txt("Error")}: {str(e)}')

    def imuCali(self):
        if self.debuggerReady == 1:
            if not self.isConnected or not self.currentPort:
                messagebox.showwarning(txt('Warning'), txt('Please connect to a serial port first'))
                return
            
            cmd = "d"
            try:
                self.currentPort.Send_data(self.encode(cmd))
                self.displayOutput(f">> {cmd}")
                self.strStatus.set(txt('Calibrate gyroscope'))
                self.statusBar.update()
                self.dialogType = "imuCali"
                self.showDialog(self.dialogType)
            except Exception as e:
                messagebox.showerror(txt('Error'), f'{txt("Error")}: {str(e)}')


    def showDialog(self, dialogType='voiceRst'):
        # Declare a global variable to access it within the function
        # Create the dialog window
        self.dialogWin = Toplevel(self.winDebug)
        self.dialogWin.title(txt('Warning'))
        self.dialogWin.geometry('680x320')

        fmDialog = Frame(self.dialogWin)  # relief=GROOVE to draw border
        fmDialog.grid(ipadx=3, ipady=3, padx=3, pady=5, sticky=W + E)

        if self.dialogType == "voiceRst":
            # creator label
            infoLabel = Label(fmDialog, text=txt('Voice indicates'), justify='left')
            infoLabel.grid(row=0, columnspan=2, padx=2, pady=6, sticky=W)

            # Load the image
            frameImage = self.createImage(fmDialog, resourcePath + 'VoiceSwitch.jpeg', 200)
            frameImage.grid(row=1, columnspan=2,pady=5)
        elif self.dialogType == "imuCali":
            # creator label
            infoLabel = Label(fmDialog, text=txt('IMU indicates'), justify='left')
            infoLabel.grid(row=0, columnspan=2, padx=2, pady=6, sticky=W)

            # Load the image
            frameImage = self.createImage(fmDialog, resourcePath + 'rest.jpeg', 200)
            frameImage.grid(row=1, columnspan=2, pady=5)

        # Create the buttons
        yesButton = tk.Button(fmDialog, text=txt('Yes'), width=10, command=lambda bFlag = True: self.getButtonClick(bFlag))
        yesButton.grid(row=2, column=0,  padx=3, pady=10)


        noButton = tk.Button(fmDialog, text=txt('No'), width=10, command=lambda bFlag = False: self.getButtonClick(bFlag))
        noButton.grid(row=2, column=1, padx=3, pady=10)

        self.dialogWin.mainloop()  # Start the event loop for the dialog window


    def encode(self, in_str, encoding='utf-8'):
        if isinstance(in_str, bytes):
            return in_str
        else:
            return in_str.encode(encoding)


    def getButtonClick(self, buttonValue):
        """Function to handle button clicks and close the window."""
        logger.debug(f"returnVal is {buttonValue}")
        self.dialogWin.destroy()  # Destroy the window
        if self.debuggerReady == 1:
            if self.dialogType == "voiceRst":
                if buttonValue == True:
                    if 'Chinese'in txt('lan'):
                        cmdList = ["XAa", "XAb"]
                    else:
                        cmdList = ["XAb", "XAa"]

                    for cmd in cmdList:
                        if self.currentPort:
                            self.currentPort.Send_data(self.encode(cmd))
                            self.displayOutput(f">> {cmd}")
                            self.winDebug.update()  # Force UI update
                        if cmd == cmdList[0]:
                            time.sleep(2)
                        else:
                            txtResult = txt('Reset successfully')
                            self.strStatus.set(txtResult)
                            self.statusBar.update()
                            messagebox.showinfo(None, txtResult)
                else:
                    self.strStatus.set(' ')
                    self.statusBar.update()
            elif self.dialogType == "imuCali":
                if buttonValue == True:
                    self.strStatus.set(txt('calibrating IMU'))
                    self.statusBar.update()
                    
                    # Temporarily pause the receive thread to avoid competition
                    wasReceiving = False
                    if self.receiveThread and self.receiveThread.is_alive():
                        wasReceiving = True
                        self.stopReceiveThread = True
                        time.sleep(0.1)  # Give thread time to stop
                    
                    if self.currentPort:
                        self.currentPort.Send_data(self.encode("gc"))
                        self.displayOutput(">> gc")
                    
                    # Create a flag variable to track whether calibration is successful.
                    calibration_success = False
                    # Set timeout (seconds):
                    timeout = 20
                    start_time = time.time()
                    
                    # Monitor serial output in real-time:
                    while time.time() - start_time < timeout:
                        # Brief pause to avoid high CPU usage.
                        time.sleep(0.01)
                        # Update UI to keep it responsive
                        self.winDebug.update()
                        
                        # Check current port
                        if self.currentPort and self.currentPort.main_engine.in_waiting > 0:
                            try:
                                # Read serial data of each line
                                data = self.currentPort.main_engine.readline()
                                data_str = data.decode('ISO-8859-1').strip()
                                # Display output in text widget
                                if data_str:
                                    self.displayOutput(data_str)
                                
                                # Check the successful calibration information in the serial output.
                                if "Calibration done" in data_str:
                                    calibration_success = True
                                    break
                            except Exception as e:
                                logger.error(f"Error reading serial data: {e}")
                        
                        # If calibration is successful, exit the loop.
                        if calibration_success:
                            break
                    
                    # Restart receive thread if it was running
                    if wasReceiving:
                        self.startReceiveThread()

                    # Show a message according to the calibration results.
                    if calibration_success:
                        txtResult = txt('IMU Calibration successfully')
                        messagebox.showinfo('Petoi Desktop App', txtResult)
                    else:
                        txtResult = txt('IMU Calibration failed')
                        messagebox.showinfo('Petoi Desktop App', txtResult)

                    self.strStatus.set(txtResult)
                    self.statusBar.update()
                else:
                    self.strStatus.set(' ')
                    self.statusBar.update()

    def matchSerialFrameWidth(self):
        """Match serial frame width to reference button width"""
        try:
            buttonWidth = self.refButton.winfo_width()
            if buttonWidth > 0:
                # Set frame to exact button width
                self.fmSerial.config(width=buttonWidth, height=self.connectBtn.winfo_reqheight())
                self.fmSerial.pack_propagate(False)  # Prevent frame from resizing
        except:
            pass
    
    def updateAvailablePorts(self):
        """Update the list of available serial ports"""
        allPorts = Communication.Print_Used_Com()
        self.availablePorts = [p.split('/')[-1] for p in allPorts]
        
    def toggleConnection(self):
        """Toggle serial port connection"""
        if self.isConnected:
            # Disconnect
            self.disconnectPort()
        else:
            # Connect
            self.connectSerialPort()
    
    def connectSerialPort(self):
        """Connect to selected serial port"""
        portName = self.portCombo.get()
        if not portName:
            messagebox.showwarning(txt('Warning'), txt('Please select a serial port'))
            return
        
        try:
            # Find full port path
            allPorts = Communication.Print_Used_Com()
            fullPath = None
            for p in allPorts:
                if p.split('/')[-1] == portName or p == portName:
                    fullPath = p
                    break
            
            if fullPath is None:
                fullPath = portName
            
            # Create serial connection
            serialObj = Communication(fullPath, 115200, 1)
            if serialObj.main_engine and serialObj.main_engine.is_open:
                self.currentPort = serialObj
                self.isConnected = True
                
                # Update button state
                self.connectBtn.config(text=txt('Connected'), fg='green', relief=SUNKEN)
                self.strStatus.set(f'{txt("Connected to")} {portName}')
                
                # Start receive thread
                self.startReceiveThread()
                
                # Add to goodPorts if not already there
                if serialObj not in goodPorts:
                    goodPorts[serialObj] = portName
            else:
                raise Exception(txt('Failed to open port'))
                
        except Exception as e:
            messagebox.showerror(txt('Error'), f'{txt("* Port ")}{portName}{txt(" cannot be opened")}: {str(e)}')
            self.strStatus.set(f'{txt("Failed to open port")}: {portName}')
    
    def disconnectPort(self):
        """Disconnect from current serial port"""
        if self.currentPort:
            try:
                # Stop receive thread
                self.stopReceiveThread = True
                if self.receiveThread and self.receiveThread.is_alive():
                    self.receiveThread.join(timeout=1)
                
                # Close serial port
                if self.currentPort.main_engine and self.currentPort.main_engine.is_open:
                    self.currentPort.main_engine.close()
                
                # Remove from goodPorts
                if self.currentPort in goodPorts:
                    del goodPorts[self.currentPort]
                
                portName = self.portCombo.get()
                self.currentPort = None
                self.isConnected = False
                
                # Update button state
                self.connectBtn.config(text=txt('Connect'), fg='red', relief=RAISED)
                self.strStatus.set(f'{txt("Disconnected from")} {portName}')
                
            except Exception as e:
                messagebox.showerror(txt('Error'), f'{txt("Error")}: {str(e)}')
    
    def startReceiveThread(self):
        """Start thread to receive serial data"""
        self.stopReceiveThread = False
        self.receiveThread = threading.Thread(target=self.receiveSerialData, daemon=True)
        self.receiveThread.start()
    
    def receiveSerialData(self):
        """Receive and display serial data"""
        while not self.stopReceiveThread and self.currentPort:
            try:
                if self.currentPort.main_engine and self.currentPort.main_engine.is_open:
                    if self.currentPort.main_engine.in_waiting > 0:
                        data = self.currentPort.main_engine.readline()
                        try:
                            data_str = data.decode('ISO-8859-1').strip()
                            if data_str:
                                self.displayOutput(data_str)
                        except:
                            pass
                time.sleep(0.01)
            except Exception as e:
                if not self.stopReceiveThread:
                    logger.error(f"Error receiving serial data: {e}")
                break
    
    def displayOutput(self, message):
        """Display message in output text widget"""
        if self.showTimestamp.get():
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            # Add timestamp on a separate line to preserve tab alignment in data
            self.outputText.insert(END, f"[{timestamp}]\n")
            if self.autoscroll.get():
                self.outputText.see(END)
        
        # Thread-safe update to text widget
        self.outputText.insert(END, message + '\n')
        
        if self.autoscroll.get():
            self.outputText.see(END)
        
        # Force update to display immediately
        self.outputText.update_idletasks()
    
    def sendCommand(self):
        """Send command from input field"""
        cmd = self.cmdInput.get().strip()
        if not cmd:
            return
        
        if not self.isConnected or not self.currentPort:
            messagebox.showwarning(txt('Warning'), txt('Please connect to a serial port first'))
            return
        
        try:
            # Send command
            self.currentPort.Send_data(self.encode(cmd))
            
            # Display sent command (using displayOutput for consistent formatting)
            self.displayOutput(f">> {cmd}")
            
            # Clear input field
            self.cmdInput.delete(0, END)
            
            self.strStatus.set(f'{txt("Sent")}: {cmd}')
            
        except Exception as e:
            messagebox.showerror(txt('Error'), f'{txt("Error")}: {str(e)}')
            self.strStatus.set(txt('Failed to send command'))
    
    def copyOutput(self):
        """Copy selected text or all text from output widget to clipboard"""
        try:
            # Check if there is selected text
            if self.outputText.tag_ranges('sel'):
                # Get selected text
                selected_text = self.outputText.get('sel.first', 'sel.last')
                # Copy to clipboard
                self.winDebug.clipboard_clear()
                self.winDebug.clipboard_append(selected_text)
                self.strStatus.set(txt('Copied selected text to clipboard'))
            else:
                # No selection, copy all text
                all_text = self.outputText.get('1.0', END)
                # Remove the last newline that Text widget always adds
                all_text = all_text.rstrip('\n')
                if all_text:
                    self.winDebug.clipboard_clear()
                    self.winDebug.clipboard_append(all_text)
                    self.strStatus.set(txt('Copied all output to clipboard'))
                else:
                    self.strStatus.set(txt('No output to copy'))
        except Exception as e:
            messagebox.showerror(txt('Error'), f'{txt("Error")}: {str(e)}')
            self.strStatus.set(txt('Failed to copy'))
    
    def clearOutput(self):
        """Clear output text widget"""
        self.outputText.delete('1.0', END)
        self.strStatus.set(txt('Output cleared'))

    def on_closing(self):
        if messagebox.askokcancel(txt('Quit'), txt('Do you want to quit?')):
            self.debuggerReady = False
            self.stopReceiveThread = True
            if self.receiveThread and self.receiveThread.is_alive():
                self.receiveThread.join(timeout=1)
            self.winDebug.destroy()
            closeAllSerial(goodPorts)
            os._exit(0)


if __name__ == '__main__':
    goodPorts = {}
    try:
        model = "Bittle"
        Debugger(model,language)
        closeAllSerial(goodPorts)
        os._exit(0)
    except Exception as e:
        logger.info("Exception")
        closeAllSerial(goodPorts)
        raise e
