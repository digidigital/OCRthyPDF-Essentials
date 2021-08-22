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

"""

from os import path, environ, makedirs, listdir, set_blocking 
import PySimpleGUI as sg
import ast, signal, subprocess, shlex
from configparser import ConfigParser
from random import randint

theme='DefaultNoMoreNagging'
sg.theme(theme)   
background = sg.LOOK_AND_FEEL_TABLE[theme]['BACKGROUND']

#App values
aboutPage = 'https://github.com/digidigital/OCRthyPDF-Essentials/blob/main/About.md'
version = '0.6'
applicationTitle = 'OCRthyPDF Essentials'

# Read licenses
license += """
********************************************
The following components are libraries used by this program 
or distributed as dependencies in a Snap or AppImage
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
    # tesseractOutput = subprocess.check_output('tesseract --list-langs', stderr=subprocess.STDOUT , shell=True, text=True).split('\n')
    # seems not work in snap's standard core18 python version.
    # Keeping it for future revision since workaround seems easier than adding required version of python to snap ;)
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

# Just a simple popup message in a function so I can change formatting and behaviour in one place. :)
def popUp(message):
    windowLocation = window.current_location()
    popWindow = sg.Window('',
        [[sg.Text(message)],
        [sg.OK()]
        ], 
        element_justification = 'c',
        no_titlebar = True,
        font=('Open Sans Semibold', 10, 'normal'),
        auto_close= True,
        auto_close_duration = 10,
        modal=True,
        finalize = True, 
        keep_on_top = True,
        location = (windowLocation[0]+window.size[0]/3,windowLocation[1]+window.size[1]/3)       
    )
        
    while True:
        event, values = popWindow.read() 
        if event == sg.WIN_CLOSED: 
            break
        else:
            popWindow.close()

# If filename is longer than 'limit' split filename in two shorter parts an add '...' in the middle so it fits in limit
def limitFilenameLen(filename, limit=57):
    x = len(filename)
    if x <= limit:
        return filename
    else:
        return filename[0:int(limit/2 - 3)] + '...' + filename[x - int(limit/2 - 3):x]  

# Language related
languages = getLangs()
languageCodes = { 
    'aa':'aar', 'ab':'abk', 'ae':'ave', 'af':'afr', 'ak':'aka', 'am':'amh', 'an':'arg', 'ar':'ara', 'as':'asm', 'av':'ava', 
    'ay':'aym', 'az':'aze', 'ba':'bak', 'be':'bel', 'bg':'bul', 'bh':'bih', 'bi':'bis', 'bm':'bam', 'bn':'ben', 'bo':'bod', 
    'br':'bre', 'bs':'bos', 'ca':'cat', 'ce':'che', 'ch':'cha', 'co':'cos', 'cr':'cre', 'cs':'ces', 'cu':'chu', 'cv':'chv', 
    'cy':'cym', 'da':'dan', 'de':'deu', 'dv':'div', 'dz':'dzo', 'ee':'ewe', 'el':'ell', 'en':'eng', 'eo':'epo', 'es':'spa', 
    'et':'est', 'eu':'eus', 'fa':'fas', 'ff':'ful', 'fi':'fin', 'fj':'fij', 'fo':'fao', 'fr':'fra', 'fy':'fry', 'ga':'gle', 
    'gd':'gla', 'gl':'glg', 'gn':'grn', 'gu':'guj', 'gv':'glv', 'ha':'hau', 'he':'heb', 'hi':'hin', 'ho':'hmo', 'hr':'hrv', 
    'ht':'hat', 'hu':'hun', 'hy':'hye', 'hz':'her', 'ia':'ina', 'id':'ind', 'ie':'ile', 'ig':'ibo', 'ii':'iii', 'ik':'ipk', 
    'io':'ido', 'is':'isl', 'it':'ita', 'iu':'iku', 'ja':'jpn', 'jv':'jav', 'ka':'kat', 'kg':'kon', 'ki':'kik', 'kj':'kua', 
    'kk':'kaz', 'kl':'kal', 'km':'khm', 'kn':'kan', 'ko':'kor', 'kr':'kau', 'ks':'kas', 'ku':'kur', 'kv':'kom', 'kw':'cor', 
    'ky':'kir', 'la':'lat', 'lb':'ltz', 'lg':'lug', 'li':'lim', 'ln':'lin', 'lo':'lao', 'lt':'lit', 'lu':'lub', 'lv':'lav', 
    'mg':'mlg', 'mh':'mah', 'mi':'mri', 'mk':'mkd', 'ml':'mal', 'mn':'mon', 'mr':'mar', 'ms':'msa', 'mt':'mlt', 'my':'mya', 
    'na':'nau', 'nb':'nob', 'nd':'nde', 'ne':'nep', 'ng':'ndo', 'nl':'nld', 'nn':'nno', 'no':'nor', 'nr':'nbl', 'nv':'nav', 
    'ny':'nya', 'oc':'oci', 'oj':'oji', 'om':'orm', 'or':'ori', 'os':'oss', 'pa':'pan', 'pi':'pli', 'pl':'pol', 'ps':'pus', 
    'pt':'por', 'qu':'que', 'rm':'roh', 'rn':'run', 'ro':'ron', 'ru':'rus', 'rw':'kin', 'sa':'san', 'sc':'srd', 'sd':'snd', 
    'se':'sme', 'sg':'sag', 'si':'sin', 'sk':'slk', 'sl':'slv', 'sm':'smo', 'sn':'sna', 'so':'som', 'sq':'sqi', 'sr':'srp', 
    'ss':'ssw', 'st':'sot', 'su':'sun', 'sv':'swe', 'sw':'swa', 'ta':'tam', 'te':'tel', 'tg':'tgk', 'th':'tha', 'ti':'tir', 
    'tk':'tuk', 'tl':'tgl', 'tn':'tsn', 'to':'ton', 'tr':'tur', 'ts':'tso', 'tt':'tat', 'tw':'twi', 'ty':'tah', 'ug':'uig', 
    'uk':'ukr', 'ur':'urd', 'uz':'uzb', 've':'ven', 'vi':'vie', 'vo':'vol', 'wa':'wln', 'wo':'wol', 'xh':'xho', 'yi':'yid', 
    'yo':'yor', 'za':'zha', 'zh':'zho', 'zu':'zul'
}
systemLanguage = environ['LANG'][0:2]

tab1_layout =   [
                    [sg.T('Existing text/OCR strategy:'), sg.InputCombo(('Skip pages with text', 'Redo OCR', 'Force OCR', 'Remove ALL text'), default_value='Skip pages with text', key='opt_ocr', tooltip = '"Remove ALL text" will remove transparent AND visible text! Faster if you redo OCR on "image only" PDFs.', enable_events = True)],  
                    [sg.T('Deskew pages (crooked scans):', tooltip = 'Will correct pages scanned at a skewed angle by rotating them back into place.'),sg.InputCombo(('yes', 'no'), default_value='no', key='opt_deskew', enable_events = True, tooltip = 'Will correct pages scanned at a skewed angle by rotating them back into place.')],
                    [sg.T('Fix page rotation:', tooltip = 'Attempts to determine the correct orientation for each page and rotates the page if necessary.'),sg.InputCombo(('yes', 'no'), default_value='no', key='opt_rotate', enable_events = True, tooltip = 'Attempts to determine the correct orientation for each page and rotates the page if necessary.')],
                    [sg.T('Minimum page rotation confidence:'),sg.Spin(('5','10', '15', '20', '25'),initial_value = '15', key='opt_confidence', size=(2,1),enable_events=True)],
                    [sg.T('Noise:'), sg.InputCombo(('Do nothing', 'Clean for OCR but keep original page', 'Clean for OCR and keep cleaned page'), default_value='Do nothing', key='opt_noise', enable_events = True, tooltip = 'Clean up pages before OCR. If you keep the cleaned pages review the OCRed PDF!')],
                    [sg.T('Remove background:'), sg.InputCombo(('yes', 'no'), default_value='no', key='opt_background', enable_events = True)],
                    [sg.T('Optimization level:'), sg.InputCombo(('0', '1', '2', '3'), default_value='1', key='opt_optimization', enable_events = True, tooltip = '0 = Disables optimization, 1 = Lossless optimizations, 2 + 3 = Reduced image quality ')],
                    [sg.T('Output type:'), sg.InputCombo(('Standard PDF', 'PDF/A-1b', 'PDF/A-2b', 'PDF/A-3b'), default_value='PDF/A-2b', key='opt_standard', enable_events = True)],
                    [sg.T('Postfix (may overwrite original if empty!):'), sg.In('_OCR', key='opt_postfix', change_submits = True, size = (15,1), enable_events = True)],
                    [sg.T('Save recognized text as separate .txt file:'),sg.InputCombo(('yes', 'no'), default_value='no', key='opt_sidecar', enable_events = True)]          
                ]   

tab2_layout =   [
                    [sg.T('Separator pattern for QR Code (postfix is optional): <Separator_Code>|<Custom_Postfix>')],
                    [sg.T('<Custom_Postfix> is added to the filename in "Sticker Mode" if available')],
                    [sg.T('Run splitter prior to OCR:'),sg.InputCombo(('yes', 'no'), default_value='no', key='opt_runsplitter', enable_events = True)],
                    [sg.T('Separator code (add at least this to your QR code):'), sg.In('NEXT', key='opt_separator', change_submits = True, size = (15,1), enable_events = True)],
                    [sg.T('Separator mode?:'), sg.InputCombo(('Drop separator page', 'Sticker Mode'), default_value='Drop separator page', key='opt_separatorpage', tooltip='Sticker Mode: QR Code starts new segment. Page is added to output', enable_events = True)],                  
                    [sg.T('Add segment number to filename:'),sg.InputCombo(('yes', 'no'), default_value='yes', key='opt_addpartnumber', tooltip='Set to "No" with Sticker Mode and <Custom_Postfix> to get clean filenames.', enable_events = True)],
                    [sg.T('Use source filename in output filename?:'),sg.InputCombo(('yes', 'no'), default_value='yes', key='opt_usesourcename', enable_events = True)],
                    [sg.T('Loglevel:'), sg.InputCombo(('INFO', 'DEBUG'), default_value='INFO', key='opt_splitterloglevel', enable_events = True)],
                            
                ]                   

tab3_layout =   [
                    [
                        sg.T('Select document language(s):')
                    ],
                    [ 
                        sg.Listbox(values=languages, key='opt_languages', select_mode='multiple', highlight_background_color = 'green', highlight_text_color = 'white', enable_events = True, size=(15, 12))
                    ]
                ]   

tab4_layout =   [
                    [
                        sg.Multiline('', key='console', expand_x = True, expand_y = True)
                    ]
                ] 

tab5_layout =   [
                    [
                        sg.Multiline(license, expand_x = True, expand_y = True)
                    ]
                ] 

col1 =  [
            [
                sg.Text('Single PDF:', pad = ((5,0),(8,0)))
            ],
            [
                sg.Text('Input Folder:', pad = ((5,0),(16,0))) 
            ],
            [
                sg.Text('Output Folder:', pad = ((5,0),(16,0)))
            ]
        ]   
col2 =  [
            [
                sg.InputText(key='filename_short', readonly=True, size=(52,1)), 
                sg.InputText(key='filename', visible=False,  readonly=True, enable_events=True), 
                sg.FileBrowse(('Browse'), file_types=(("PDF", "*.pdf"),("PDF", "*.PDF"),),)
            ],
            [
                sg.InputText(key='infolder_short', readonly=True, size=(52,1)), 
                sg.InputText(key='infolder', visible=False,  readonly=True, enable_events=True), 
                sg.FolderBrowse(('Browse'))
            ],
            [
                sg.InputText(key='outfolder_short', readonly=True, size=(52,1)), 
                sg.InputText(key='outfolder', visible=False,  readonly=True, enable_events=True), 
                sg.FolderBrowse(('Browse'))
            ]
        ]


layout = [  
            [
                sg.Column(col1, vertical_alignment = 't'), sg.Column(col2)      
            ],
            #[sg.Checkbox('Advanced options', key='advanced_options', enable_events=True)],
            [
                sg.TabGroup([[
                    sg.Tab('Options', tab1_layout), 
                    sg.Tab('Splitter', tab2_layout),
                    sg.Tab('Languages', tab3_layout),
                    sg.Tab('Console', tab4_layout),
                    sg.Tab('Licenses', tab5_layout)
                ]], size = (625,300))
            ], 
            [
                sg.Button('Start OCR', key='start_ocr', disabled = True),
                sg.Button('Stop OCR', key='stop_ocr', disabled = True),
                sg.ProgressBar(100, key='progress_bar', size=(39,20))  
            ]
         ]

# Create the Window
window = sg.Window(applicationTitle  + ' ' + version, layout, font=('Open Sans Semibold', 10, 'normal'), finalize = True)

# Check if config file exists and create one if none exists 
if len(config.read(configini)) == 0:
    makedirs(configPath, exist_ok=True)
    config.add_section('App')
    config.set('App', 'version', version)
    config.add_section('Languages')
    config.add_section('OCRmyPDFoptions')
   
    # Check if system language is available for OCR and set it as additional default
    if systemLanguage in languageCodes: 
        if languageCodes[systemLanguage] in languages:
            window['opt_languages'].set_value(['eng', languageCodes[systemLanguage]])

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
                
                #debug
                while True:
                    line = p.stdout.readline().decode()
                    #update console tab
                    if line != '':
                        window['console'].print(line)
                    else:
                        break
            else:     
                exitMessage = "Process terminated by signal"
            popUp(exitMessage)
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
        window['filename_short'].update(value = limitFilenameLen(values['filename'])) 
        # Clear infolder
        window['infolder'].update(value = '')
        window['infolder_short'].update(value = '')
        # If outfolder is empty set to same folder
        if window['outfolder'].get() == '':
            inFilePath = path.dirname(values['filename'])
            window['outfolder'].update(value = inFilePath)
            window['outfolder_short'].update(value = limitFilenameLen(inFilePath))
        # Enable Start button
        if runningOCR == False:
            window['start_ocr'].update(disabled=False)   

    if event == 'infolder' and not values['infolder'] == '' : 
        inFolderPath = values['infolder']
        # Shorten filename so it fits in the input text field
        window['infolder_short'].update(value = limitFilenameLen( inFolderPath)) 
        # Clear single PDF input
        window['filename'].update(value = '')
        window['filename_short'].update(value = '')
        # If outfolder is empty set to same folder
        if window['outfolder'].get() == '':
            window['outfolder'].update(value =  inFolderPath)
            window['outfolder_short'].update(value = limitFilenameLen( inFolderPath))
        # Enable Start button
        if runningOCR == False:
            window['start_ocr'].update(disabled=False) 

    if event == 'outfolder' and not values['outfolder'] == '' : 
        # Shorten filename so it fits in the input text field
        window['outfolder_short'].update(value = limitFilenameLen(values['outfolder'])) 
        
  
    if event == 'start_ocr':# oder Länge batch > 0?
        
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
        else:
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
#######################    
# Liste von Dateien erzeugen, die OCRed werden sollen
# wenn Einzeldatei, dann Liste mit Einzeldatei
# Wenn Folder, dann Dateinamen übernehmen
# 
# While Schleife basteln   
        # split output filename and add postfix
        inputFilename = path.basename(window['filename'].get())
        outFileParts = inputFilename.rsplit('.', 1)
        outFile = path.join(window['outfolder'].get(), outFileParts[0] + window['opt_postfix'].get() + '.' + outFileParts[1])
        
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
###########################
