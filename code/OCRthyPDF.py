#!/usr/bin/env python3

license = """OCRthyPDF Essentials
Make your PDF files text-searchable (A GUI for OCRmyPDF)
Copyright (C) 2021 Björn Seipel
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.
You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see 
https://github.com/digidigital/OCRthyPDF-Essentials/blob/main/LICENSE
Licenses used by other software in the snap version:
OCRmyPDF - Mozilla Public License 2.0 http://mozilla.org/MPL/2.0/
For details of licenses used by OCRmyPDF see https://github.com/jbarlow83/OCRmyPDF/blob/master/debian/copyright
"""

from os import path, getcwd, environ, makedirs, listdir, set_blocking 
import PySimpleGUI as sg
import ocrmypdf, ast, signal, subprocess, shlex
from configparser import ConfigParser
from random import randint

theme='DefaultNoMoreNagging'
sg.theme(theme)   
background = sg.LOOK_AND_FEEL_TABLE[theme]['BACKGROUND']

#App values
aboutPage = 'https://github.com/digidigital/OCRthyPDF-Essentials/blob/main/About.md'
version = '0.5'
applicationTitle = 'OCRthyPDF Essentials'

# Read licenses
license += """
********************************************
The following components are libraries used by this program 
or distributed with in a Snap or AppImages
********************************************
"""
licensePath = path.abspath(path.dirname(__file__))+ '/../licenses'
licenses = listdir(licensePath)
for f in licenses:
    license += "\n\n#*#*#*#*# " + f.split("_", 1)[0] + " #*#*#*#*#\n\n"
    with open(licensePath + '/' + f) as licenseFile:
        license += licenseFile.read()

# Config related
boolOptions = []
stringOptions = ['ocr', 'noise', 'optimization', 'postfix', 'standard', 'confidence', 'deskew', 'rotate', 'background', 'sidecar']
configPath = environ['HOME']+'/.config/OCRthyPDF'
configini = configPath + '/config.ini'
config = ConfigParser()

# Other
runningOCR = False

# OCRmyPDF Exit codes
exitCode = { 
    0 : 'OCR completed.',
    1 : 'Invalid arguments, exited with an error.',
    2 : 'The input file does not seem to be a valid PDF.',
    3 : 'An external program required by OCRmyPDF is missing.',
    4 : 'An output file was created, but it does not seem to be a valid PDF. The file will be available.',
    5 : 'The user running OCRthyPDF does not have sufficient permissions to read the input file and write the output file. Maybe you need to adjust the settings in the Snap store',
    6 : 'The file already appears to contain text so it may not need OCR. See output message.',
    7 : 'An error occurred in an external program (child process) and OCRmyPDF cannot continue.',
    8 : 'The input PDF is encrypted. OCRmyPDF does not read encrypted PDFs. Use another program such as AESify to remove encryption.',
    9 : 'A custom configuration file was forwarded to Tesseract using --tesseract-config, and Tesseract rejected this file.',
    10 : 'A valid PDF was created, PDF/A conversion failed. The file will be available.',
    15 : 'Some totally unexpexted error occurred.',
    130 : 'The program was interrupted by pressing Stop OCR button.'
}


def getLangs():
    # does not work in snap's standard python version.
    # Keeping it for future revision since workaround is easier than addin required version of python to snap ;)
    #tesseractOutput = subprocess.check_output('tesseract --list-langs', stderr=subprocess.STDOUT , shell=True, text=True).split('\n')
    args = shlex.split('tesseract --list-langs')
    p = subprocess.Popen (args,stdout=subprocess.PIPE)
    tesseractOutput =[]
    while True:
        tesseractOutput.append(p.stdout.readline().decode().strip())
        if p.poll() is not None:
            break  
    print (tesseractOutput)
    languageList = []
    for line in tesseractOutput:
        if line != 'osd' and line != '' and not line.startswith('List'):
            languageList.append(line)
    languageList.sort()
    return languageList         

def readConfig():
    print ('Reading config')
    config.read(configini)
    window['opt_languages'].set_value(ast.literal_eval(config.get('Languages', 'opt_languages')))       
    for o in boolOptions:
        window['opt_' + o].update(value = config.getboolean('OCRmyPDFoptions', 'opt_' + o)) 
    for o in stringOptions:
        window['opt_' + o].update(value = config.get('OCRmyPDFoptions', 'opt_' + o))
          
def writeConfig():
    print ('Creating / Updating config')
    config.set('Languages', 'opt_languages' , repr(window['opt_languages'].get()))
    for o in boolOptions + stringOptions:
        config.set('OCRmyPDFoptions', 'opt_' + o, str(window['opt_' + o].get()))
    fp=open(configini,'w+')
    config.write(fp)
    fp.close()

# If filename is longer than 'limit' split filename in two shorter parts an add '...' in the middle so it fits in limit
def limitFilenameLen(filename, limit=67):
    x = len(filename)
    if x <= limit:
        return filename
    else:
        return filename[0:int(limit/2 - 3)] + '...' + filename[x - int(limit/2 - 3):x]  

#Installed languages 
languages = getLangs()


tab1_layout =   [
                    [sg.T('Existing text/OCR strategy:'), sg.InputCombo(('Skip pages with text', 'Redo OCR', 'Force OCR'), default_value='Skip pages with text', key='opt_ocr', enable_events = True)],  
                    [sg.T('Deskew pages (crooked scans):', tooltip = 'Will correct pages scanned at a skewed angle by rotating them back into place.'),sg.InputCombo(('yes', 'no'), default_value='no', key='opt_deskew', enable_events = True, tooltip = 'Will correct pages scanned at a skewed angle by rotating them back into place.')],
                    [sg.T('Fix page rotation:', tooltip = 'Attempts to determine the correct orientation for each page and rotates the page if necessary.'),sg.InputCombo(('yes', 'no'), default_value='no', key='opt_rotate', enable_events = True, tooltip = 'Attempts to determine the correct orientation for each page and rotates the page if necessary.')],
                    [sg.T('Minimum page rotation confidence:'),sg.Spin(('5','10', '15', '20', '25'),initial_value = '15', key='opt_confidence', size=(2,1),enable_events=True)],
                    [sg.T('Noise:'), sg.InputCombo(('Do nothing', 'Clean for OCR but keep original page', 'Clean for OCR and keep cleaned page'), default_value='Do nothing', key='opt_noise', enable_events = True, tooltip = 'Clean up pages before OCR. This makes it less likely that OCR will try to find text in background noise. If you keep the cleaned pages review the PDF to ensure that the program did not remove something important.')],
                    [sg.T('Remove background:'), sg.InputCombo(('yes', 'no'), default_value='no', key='opt_background', enable_events = True)],
                    [sg.T('Optimization level:'), sg.InputCombo(('0', '1', '2', '3'), default_value='1', key='opt_optimization', enable_events = True, tooltip = '0 = Disables optimization, 1 = Lossless optimizations, 2 + 3 = Reduced image quality ')],
                    [sg.T('Output type:'), sg.InputCombo(('Standard PDF', 'PDF/A-1b', 'PDF/A-2b', 'PDF/A-3b'), default_value='PDF/A-2b', key='opt_standard', enable_events = True)],
                    [sg.T('Postfix (overwrite original if empty!):'), sg.In('_OCR', key='opt_postfix', change_submits = True, size = (15,1), enable_events = True)],
                    [sg.T('Save recognized text as separate .txt file:'),sg.InputCombo(('yes', 'no'), default_value='no', key='opt_sidecar', enable_events = True)]          
                ]   

tab2_layout =   [
                    [
                        sg.T('Select document language(s):')
                    ],
                    [ 
                        sg.Listbox(values=languages, key='opt_languages', select_mode='multiple', highlight_background_color = 'green', highlight_text_color = 'white', enable_events = True, size=(30, 6))
                    ]
                ]   

tab3_layout =   [
                    [
                        sg.Multiline('', key='console', expand_x = True, expand_y = True)
                    ]
                ] 

tab4_layout =   [
                    [
                        sg.Multiline(license, expand_x = True, expand_y = True)
                    ]
                ] 

layout = [  
            [
                sg.Text(('PDF:')), 
                sg.InputText(key='filename_short-', readonly=True, size=(60,1)), 
                sg.InputText(key='filename', visible=False,  readonly=True, enable_events=True), 
                sg.FileBrowse(('Browse'), initial_folder = environ['HOME'], file_types=(("PDF", "*.pdf"),("PDF", "*.PDF"),),)
            ],
            #[sg.Checkbox('Advanced options', key='advanced_options', enable_events=True)],
            [
                sg.TabGroup([[
                    sg.Tab('Options', tab1_layout), 
                    sg.Tab('Languages', tab2_layout),
                    sg.Tab('Console', tab3_layout),
                    sg.Tab('Licenses', tab4_layout)
                ]], size = (550,300))
            ], 
            [
                sg.Button('Start OCR', key='start_ocr', disabled = True),
                sg.Button('Stop OCR', key='stop_ocr', disabled = True),
                sg.ProgressBar(100, key='progress_bar', size=(32,20))  
            ]
         ]

# Create the Window
window = sg.Window(applicationTitle  + ' ' + version, layout, finalize = True)

# Check if config file exists and create one if none exists 
if len(config.read(configini)) == 0:
    makedirs(configPath, exist_ok=True)
    config.add_section('App')
    config.set('App', 'version', version)
    config.add_section('Languages')
    config.add_section('OCRmyPDFoptions')
   
    #TODO: Add users locale to selected languages per default- Issue environ['LANG'] returns ISO 639-1, tesseract files use ISO 639-2/T:
    
    writeConfig()
else:
    readConfig()  
    

# Event Loop to process "events" and get the "values" of the inputs
while True:
    if runningOCR == True:
        line = p.stdout.readline().decode()
        
        #update console tab
        if line != '':
            window['console'].print(line)
            
            progressValue += 5
        else:
            #fake some output for long running steps :)
            progressValue += randint(0,10)

        # Animate progress bar
        if progressValue > 100:
            progressValue = 0
        window['progress_bar'].update(progressValue)
        if event == 'stop_ocr':
            window['console'].print('"Stop OCR" requested')

            #Try to stop subprocess with SIGINT - if timeout occurs kill it
            try: 
                p.send_signal(signal.SIGINT)
                p.wait(timeout=10)
                window['console'].print('Process was stopped with SIGINT')
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=10)
                window['console'].print('Process was killed')
            
            print('OCR stopped by user')          
        if p.poll() is not None: 
            if p.returncode >= 0:
                exitMessage = exitCode[p.returncode]
            else:     
                exitMessage = "Process terminated by signal"
            sg.popup('', exitMessage)
            window['console'].print(exitMessage)
            #reset progress bar
            window['progress_bar'].update(0)
            #enable start button
            window['start_ocr'].update(disabled=False)
            window['stop_ocr'].update(disabled=True)
            runningOCR=False
        event, values = window.read(timeout = 10)    
    else:
        event, values = window.read() 
    
    if event == sg.WIN_CLOSED: # if user closes window or clicks cancel
        break
    
    if event.startswith('opt'):
        writeConfig()
         
    if event == 'filename' and not values['filename'] == '' : 
        # Shorten filename so it fits in the input text field
        window['filename_short-'].update(value = limitFilenameLen(values['filename'])) 
        # Enable Start button
        window['start_ocr'].update(disabled=False)   
  
    if event == 'start_ocr':
        # check - input file selected. still exists ?
        
        args=''

        # OCR languages
        for l in window['opt_languages'].get():
            args = args + "-l " + l + " "

        # ocr strategy --redo-ocr --force-ocr
        ocrStrat = window['opt_ocr'].get()
        if ocrStrat == "Redo OCR":
            args=args + "--redo-ocr "
        elif ocrStrat == "Force OCR":
            args=args + "--force-ocr "
        elif ocrStrat == "Skip pages with text":
            args=args + "--skip-text "       

        # clean
        clean = window['opt_noise'].get()
        if clean == "Clean for OCR but keep original page":
            args=args + "--clean "
        elif clean == "Clean for OCR and keep cleaned page":
            args=args + "--clean-final "

        # sidecar
        if window['opt_sidecar'].get() == 'yes':
            args = args + "--sidecar "

        # background
        if window['opt_background'].get() == 'yes':
            args = args + "--remove-background "    
        
        # deskew
        if window['opt_deskew'].get() == 'yes':
            args = args + "--deskew "

        # rotate pages
        if window['opt_rotate'].get() == 'yes':
            args = args + "--rotate-pages --rotate-pages-threshold " + str(window['opt_confidence'].get()) + " "

        # optimization
        args=args + "--optimize " + str(window['opt_optimization'].get()) + " "

        # output type
        args=args + "--output-type "
        outputType = window['opt_standard'].get()
        if outputType == "PDF/A-1b":
            args=args + "pdfa-1 "
        elif outputType == "PDF/A-2b":
            args=args + "pdfa-2 "
        elif outputType == "PDF/A-3b":
            args=args + "pdfa-3 "
        else: 
            args=args + "pdf "
        
        # split output filename and add postfix
        outFileParts = window['filename'].get().rsplit('.', 1)
        outFile = outFileParts[0] + window['opt_postfix'].get() + '.' + outFileParts[1]
        
        commandLine = "ocrmypdf -v " + args + "'" + window['filename'].get() + "' '" + outFile + "'"

        execute = shlex.split(commandLine)
        print('Commandline: ' + commandLine)
        print(execute)
        p = subprocess.Popen (execute,stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #make STDOUT/readline non-blocking!
        set_blocking(p.stdout.fileno(), False)
        progressValue = 0
        #clear console tab and print command line
        window['console'].update(value=commandLine + "\n")
        #disable start button
        window['start_ocr'].update(disabled=True)
        #enable stop button
        window['stop_ocr'].update(disabled=False)
        runningOCR=True
