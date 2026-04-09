#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Rongzhong Li
# Petoi LLC
# May.22nd, 2022

import os
os.environ["PETOI_SHOW_GUI"] = "1"

from tkinter import PhotoImage
from FirmwareUploader import *
from SkillComposer import *
from Calibrator import *
from Debugger import *


language = languageList['English']
apps = ['Firmware Uploader', 'Joint Calibrator', 'Skill Composer', 'Debugger']  # ,'Task Scheduler']

def txt(key):
    return language.get(key, textEN[key])

class UI:
    def __init__(self):
        global language
        # try:
            
        # except Exception as e:
        #     print('Create configuration file')
        #     self.defaultLan = 'English'
        #     self.configName = 'Bittle'
        #     self.defaultPath = releasePath[:-1]
        #     self.defaultSwVer = '2.0'
        #     self.defaultBdVer = NyBoard_version
        #     self.defaultMode = 'Standard'
        #     self.configuration = [self.defaultLan, self.configName, self.defaultPath, self.defaultSwVer, self.defaultBdVer,
        #                           self.defaultMode]

        if not os.path.exists(defaultConfPath):
            self.defaultLan = 'English'
            self.configName = 'Bittle'
            self.defaultPath = releasePath[:-1]
            self.defaultSwVer = '2.0'
            self.defaultBdVer = NyBoard_version
            self.defaultMode = 'Standard'
            self.configuration = [self.defaultLan, self.configName, self.defaultPath, self.defaultSwVer, self.defaultBdVer,
                                  self.defaultMode]
            # If missing, create the file and write default configuration first
            with open(defaultConfPath, "w", encoding="utf-8") as f:
                lines = '\n'.join(self.configuration) + '\n'
                f.writelines(lines)
            print("The file does not exist and has been automatically created.")
        else:
            with open(defaultConfPath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            lines = [line.split('\n')[0] for line in lines]  # remove the '\n' at the end of each line
            num = len(lines)
            logger.debug(f"len(lines): {num}")
            
            # Validate and set default language, use 'English' if empty or invalid
            self.defaultLan = lines[0] if len(lines) > 0 and lines[0].strip() else 'English'
            if self.defaultLan not in languageList:
                logger.warning(f"Invalid language '{self.defaultLan}' in config, using 'English' instead")
                self.defaultLan = 'English'
            
            # Validate and set other configuration values with defaults
            self.configName = lines[1] if len(lines) > 1 and lines[1].strip() else 'Bittle'
            self.defaultPath = lines[2] if len(lines) > 2 and lines[2].strip() else releasePath[:-1]
            self.defaultSwVer = lines[3] if len(lines) > 3 and lines[3].strip() else '2.0'
            if len(lines) > 4 and lines[4].strip():
                if lines[4] == "BiBoard_V0":
                    self.defaultBdVer = "BiBoard_V0_1"
                else:
                    self.defaultBdVer = lines[4]
            else:
                self.defaultBdVer = NyBoard_version
            self.defaultMode = lines[5] if len(lines) > 5 and lines[5].strip() else 'Standard'
            if len(lines) >= 8:
                self.defaultCreator = lines[6] if len(lines) > 6 and lines[6].strip() else 'Nature'
                self.defaultLocation = lines[7] if len(lines) > 7 and lines[7].strip() else 'Earth'
                self.configuration = [self.defaultLan, self.configName, self.defaultPath, self.defaultSwVer, self.defaultBdVer,
                                      self.defaultMode, self.defaultCreator, self.defaultLocation]
            else:
                self.configuration = [self.defaultLan, self.configName, self.defaultPath, self.defaultSwVer, self.defaultBdVer,
                                      self.defaultMode]

        language = languageList[self.defaultLan]

        self.window = Tk()
        self.ready = False

        self.OSname = self.window.call('tk', 'windowingsystem')
        if self.OSname == 'win32':
            logger.debug(f"resourcePath: {resourcePath}")
            self.window.iconbitmap(resourcePath + 'Petoi.ico')
            self.window.geometry('398x360+800+400')
        elif self.OSname == 'aqua':
            self.window.geometry('+800+400')
            self.backgroundColor = 'gray'
        else:
            self.window.tk.call('wm', 'iconphoto', self.window._w, "-default",
                                PhotoImage(file= resourcePath + 'Petoi.png'))
            self.window.geometry('+800+400')

        self.myFont = tkFont.Font(
            family='Times New Roman', size=20, weight='bold')
        self.window.title(txt('uiTitle'))
        self.createMenu()
        bw = 23
        self.modelLabel = Label(self.window, text=displayName(self.configName), font=self.myFont)
        self.modelLabel.grid(row=0, column=0, pady=10)
        for i in range(len(apps)):
            self.moduleButton = Button(self.window, text=txt(apps[i]), font=self.myFont, fg='blue', width=bw, relief='raised',
                   command=lambda app=apps[i]: self.utility(app))
            self.moduleButton.grid(row=1 + i, column=0, padx=10, pady=(0, 10))
            if apps[i] == 'Debugger':
                tip(self.moduleButton, txt('tipDebugger'))

        self.ready = True
        self.window.protocol('WM_DELETE_WINDOW', self.on_closing)
        self.window.update()

        self.window.resizable(False, False)
        self.window.mainloop()

    def createMenu(self):
        self.menubar = Menu(self.window, background='#ff8000', foreground='black', activebackground='white',
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

        self.window.config(menu=self.menubar)

    def changeModel(self, modelName):
        self.configName = copy.deepcopy(modelName)
        self.modelLabel.configure(text=self.configName)
        print(self.configName)
        if self.configName == "Bittle X":
            if 'NyBoard' in self.defaultBdVer:
                self.defaultBdVer = "BiBoard_V1_0"
        elif self.configName == "Bittle X+Arm":
            self.defaultBdVer = "BiBoard_V1_0"

    def changeLan(self, l):
        global language
        if self.ready and txt('lan') != l:
            self.defaultLan = l
            print(self.defaultLan)
            language = copy.deepcopy(languageList[l])
            self.menubar.destroy()
            self.createMenu()
            self.window.title(txt('uiTitle'))
            for i in range(len(apps)):
                self.window.winfo_children()[1 + i].config(text=txt(apps[i]))
                if apps[i] == 'Debugger':
                    tip(self.window.winfo_children()[1 + i], txt('tipDebugger'))
    
    def saveConfig(self,filename):
        if len(self.configuration) == 6:
            self.configuration = [self.defaultLan, self.configName, self.defaultPath, self.defaultSwVer, self.defaultBdVer,
                         self.defaultMode]
        else:
            self.configuration = [self.defaultLan, self.configName, self.defaultPath, self.defaultSwVer, self.defaultBdVer,
                                  self.defaultMode, self.defaultCreator, self.defaultLocation]

        saveConfigToFile(self.configuration, filename)

    def utility(self, app):
        global language

        self.saveConfig(defaultConfPath)
        logger.info(f"{self.configuration}")
        self.window.destroy()

        if app == 'Firmware Uploader':
            Uploader(self.configName, language)
        elif app == 'Joint Calibrator':
            self.showBootPrompt("cali")
            Calibrator(self.configName, language)
        elif app == 'Skill Composer':
            self.showBootPrompt("skil")
            SkillComposer(self.configName, language)
        elif app == 'Debugger':
            Debugger(self.configName, language)
        elif app == 'Task Scheduler':
            print('schedule')

    def showBootPrompt(self, prom="cali"):
        window = tk.Tk()
        window.geometry('+800+500')

        def on_closing():
            window.destroy()

        window.protocol('WM_DELETE_WINDOW', on_closing)
        window.title(txt('Boot prompt'))

        labelC = tk.Label(window, font='sans 14 bold', justify='left')
        labelC['text'] = txt('poweron')
        labelC.grid(row=0, column=0)
        buttonC = tk.Button(window, text=txt('Confirm'), command=on_closing)
        buttonC.grid(row=1, column=0, pady=10)

        window.focus_force()  # new window gets focus
        window.mainloop()

    def showAbout(self):
        messagebox.showinfo('Petoi Desktop App',
                            u'Petoi Desktop App\nOpen Source on GitHub\nCopyright © Petoi LLC\nwww.petoi.com')
        self.window.focus_force()

    def on_closing(self):
        if messagebox.askokcancel(txt('Quit'), txt('Do you want to quit?')):
            self.saveConfig(defaultConfPath)
            logger.info(f"{self.configuration}")
            self.window.destroy()


if __name__ == '__main__':
    UI()
