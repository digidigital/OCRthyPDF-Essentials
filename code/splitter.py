#!/usr/bin/env python3
#Version 0.7.1

import logging
import argparse
import subprocess
import shlex
import sys
import time
import concurrent.futures
import pdftotext
from pyzbar.pyzbar import decode, ZBarSymbol
from tempfile import TemporaryDirectory
from pikepdf import Pdf, PdfImage, PdfError, _cpphelpers 
from os import path
from multiprocessing import cpu_count
from shutil import copy2

def searchPDF (PDFfile, separator):
    try:
        startAnalysisTime = time.time()
        with open(PDFfile, "rb") as fp:
            pdfAsText = pdftotext.PDF(fp)        
            separatorPages={}
            pageNumber=0
            for page in pdfAsText:
                logging.info('Searching for separator on page: %d'% (pageNumber+1)) 
                if str(page).find(separator) != -1:
                    separatorPages[pageNumber]=''
                    logging.info('Found separator on page: %d'% (pageNumber+1))
                pageNumber += 1
        logging.info('Analysis completed: %d separators found on %d pages. This step took about %d seconds'%(len(separatorPages),pageNumber, int(time.time() - startAnalysisTime)))
        return separatorPages
    except Exception as error:
        logging.critical('Text-searching file %s failed. %e' % (PDFfile, error))
        return separatorPages

def analyzePage(PDF, pageNumber, separator='NEXT', mode='QR', cropfactor=1):

    #Set separatorCode to None. If separatorCode has any other value than None
    #a separator was found on the page
    separatorCode=None
    logging.debug('Analyzing page: %d'% (pageNumber+1))      
   
    if mode == 'QR':
        symbols = [ZBarSymbol.QRCODE]
    else: 
        symbols = None        
    
    for image in PDF.pages[0].images.keys():
        uncroppedImage = PdfImage(PDF.pages[0].images[image]).as_pil_image()
        width, height = uncroppedImage.size
        cropbox=(0, 0, int(width*cropfactor), int(height*cropfactor))
        pdfimage = uncroppedImage.crop(cropbox)  
        uncroppedImage.close()

        logging.debug('Extracting and analyzing an image of type %s on page %d' % (type(pdfimage),pageNumber+1))

        try:             
            barcodes = decode(pdfimage, symbols)
            
        except Exception as error: 
            logging.debug('Decoding barcode failed. Skipping one image on page %d - %s' % (pageNumber+1, error))
            continue
        
        pdfimage.close()

        for barcode in barcodes:
                
            barcodeText=str(barcode.data.decode("utf-8"))
            logging.debug('QR-Code / Barcode containing text "%s" found on page %d. Use | as delimiter if you want to use a custom postfix' % (str(barcodeText), pageNumber+1))
            barcodeComponents = barcodeText.split('|',1)
            
            if len(barcodeComponents)==2 and barcodeComponents[0] == separator:
                separatorCode = str(barcodeComponents[1])  
                #Do not checkfor barcodes in remaining data
                break

            elif barcodeComponents[0] == separator:
                separatorCode = ''  
                #Do not check for barcodes in remaining data
                break

            else:
                logging.debug('Ignored. Reason: "%s" on page %d does not start with separator "%s". Use | as delimiter if you want to use a custom postfix' % (str(barcodeText), pageNumber+1, separator))     
                continue
        
        

        #Skip remaining images if valid separator was found on page
        if separatorCode != None:
            break

    return (pageNumber,separatorCode)

def savePDFTextFile(PDFfile):
    '''Save text in PDF file to a text file'''
    logging.debug('Saving text %s.txt file' % PDFfile) 
    try:
        with open(PDFfile, "rb") as fp:
            pdfAsText = pdftotext.PDF(fp)        
            with open(PDFfile+'.txt', 'w') as f:
                for page in pdfAsText:
                    f.write('%s\n' % page)
    except Exception as error:
        logging.critical('Saving text file %s failed. %e' % (PDFfile, error))
        return
    logging.debug('Text file saved')
    

def splitPDF(filename:str, outpath:str, separator='NEXT', mode='QR', stickerMode=False, dropName=False, workers=0, skipRewrite=False, cropfactor=1, extractText=False):
    startSplitTime = time.time()   
    if not skipRewrite:
        logging.debug('Rewriting PDF %s to temporary file.' % filename)
        tempSourceDir = TemporaryDirectory()
        rewrittenPDF = path.join(tempSourceDir.name, "tempPDF.pdf")
 
        gsQuiet=''
        #gsQuiet=' -q '

        # Rewrite PDF and try to fix issues
        # Remove images if searching for keywords, remove text if searching for QR/Barcodes
        if mode == "KEYWORD":
            gsFilter = ' -dFILTERIMAGE -dFILTERVECTOR '
        else:
            gsFilter = ' -dFILTERTEXT -dFILTERVECTOR '
        
        command = shlex.split("gs -o " + rewrittenPDF + gsQuiet + " -sDEVICE=pdfwrite " + gsFilter + " -dPDFSETTINGS=/default -dNEWPDF -sstdout=%stderr '" + filename + "'")
       
        logging.debug(command)     
        try:  
            subprocess.run(command) 
            logging.debug('Rewriting completed after %d seconds.'%(int(time.time() - startSplitTime)))
        except Exception as error:
            logging.debug('Rewriting failed. Is Ghostscript installed and in PATH? %s' % error)
            sys.exit("Unable to start rewrite step. Is Ghostscript installed?")
        loadpdf = rewrittenPDF
    else: 
        logging.debug('Rewriting is skipped. Working with source PDF.')
        loadpdf = filename
    
    try:
        pdf = Pdf.open(loadpdf)
    except Exception as error:
        logging.critical('Loading PDF %s failed. %s' % (loadpdf, error))
        sys.exit("Unable to open PDF file.")

    if not outpath:
        outpath=path.dirname(filename)

    if dropName == True:
        sourceName = ''
    else:
        sourceName = path.basename(filename).split('.',1)[0]+'_'
    
    # key: page number where barcode was found, value: a value in the barcode separated 
    # by | or the number of QR-Codes found
    separatorPages={}
    
    if workers > 0:
        max_workers = workers
    else:
        max_workers = cpu_count() - 1

    if mode != 'KEYWORD':
        # let's see how quick we can analyze the pages in multiprocessing/threading
        startAnalysisTime = time.time()
        logging.debug('Extracting images and searching for QR-Codes / Barcodes')

        pageCollection=[]
        #creating single page PDFs since passing a page directly raises a pickle exception / images can not be accessed :(
        for page in pdf.pages:
            tempPDF = Pdf.new()
            tempPDF.pages.append(page)
            pageCollection.append(tempPDF)
        pdf.close()

        logging.debug('Analyzing pages with %d workers' % (max_workers))
        with concurrent.futures.ThreadPoolExecutor(max_workers) as executor:
            future_page_analyzer = {executor.submit(analyzePage, pageCollection[pageNumber], pageNumber, separator, mode, cropfactor): pageNumber for pageNumber in range(len(pdf.pages))}
            for future in concurrent.futures.as_completed(future_page_analyzer):
                thread = future_page_analyzer[future]
                try:
                    if future.result()[1] != None:
                        separatorPages[future.result()[0]]=future.result()[1]

                except Exception as exc:
                    logging.debug('Thread %r generated an exception: %s' % (thread, exc))
        
        logging.debug('Analysis completed: %d separators found on %d pages. This step took about %d seconds'%(len(separatorPages),len(pdf.pages), int(time.time() - startAnalysisTime)))
        
        pageCollection.clear()

    else:   
        separatorPages = searchPDF (filename, separator)

    # All filenames created while splitting go here
    fileList=[]

    if len(separatorPages)>0:
        logging.debug('Pages will be copied from original PDF.')   
        
        try:
            sourcePDF = Pdf.open(filename)
        except:
            logging.critical('Loading of PDF %s failed.' % filename)
            sys.exit("Unable to open PDF file.")
    
        #Separator pages start new segment and will be kept 
        if stickerMode == True:
            logging.debug('Assembling PDFs in "Sticker Mode"')
            pageList=sorted(separatorPages.keys())
            for x in range (0,len(pageList)):
                
                startPage=pageList[x]

                if x == len(pageList)-1:
                    #Last segment ends with last page of PDF
                    endPage=len(sourcePDF.pages) 
                else:
                    #Stop segment one Page before another QR-Code was found
                    endPage=pageList[x+1]
                    
                splitPDF = Pdf.new()

                #is either part of QR-Code or index number
                filenamePostfix=str(separatorPages[pageList[x]])
                if filenamePostfix=='':
                    filenamePostfix = "%04d"% (x+1) 

                pageRange = range (startPage, endPage)
                for includePage in pageRange:
                    logging.debug('Adding source page %d to new PDF' % (includePage+1))
                    splitPDF.pages.append(sourcePDF.pages[includePage])  
                saveAs = path.join(outpath , str(sourceName) + str(filenamePostfix) + '.pdf')
                logging.debug('Saving PDF: %s' % (saveAs))
                fileList.append(saveAs)
                try:
                    splitPDF.save(saveAs)
                    splitPDF.close()
                except Exception as e:
                    logging.critical('Saving split PDF %s failed. %s' % (saveAs, e))
                    continue
                
                try:                
                        if extractText==True:
                            savePDFTextFile (saveAs)
                except Exception as e:
                    logging.critical('Saving PDF %s failed. %s' % (saveAs, e))
                    continue
                          
        #Separator pages are dropped    
        else:
            logging.debug('Assembling PDFs in "Separator Page Mode"')
            startPage=0
            pageList=sorted(separatorPages.keys())

            #Multithreading candidate??
            for x in range (0,len(pageList)+1): 

                if x == len(pageList):
                    #Last segment ends with last page of PDF
                    endPage=len(sourcePDF.pages) 
                else:
                    #Stop at page before separator was found
                    endPage=pageList[x]
                splitPDF = Pdf.new()

                filenamePostfix= "%04d" % (x+1)
                
                hasPages = False

                pageRange = range (startPage, endPage)
                for includePage in pageRange:
                    logging.debug('Adding source page %d to new PDF' % (includePage+1))
                    splitPDF.pages.append(sourcePDF.pages[includePage])  
                    hasPages = True
                if hasPages:
                    saveAs = path.join(outpath , str(sourceName) + str(filenamePostfix) + '.pdf')
                    logging.info('Saving PDF: %s' % (saveAs))
                    fileList.append(saveAs)
                    try:
                        splitPDF.save(saveAs)
                        splitPDF.close() 
                    except Exception as e:
                        logging.critical('Saving raw text of split PDF %s failed. %s' % (saveAs, e))
                        continue

                    try:                
                        if extractText==True:
                            savePDFTextFile (saveAs)
                    except Exception as e:
                        logging.critical('Saving raw text of split PDF %s failed. %s' % (saveAs, e))
                        continue
                    
                    
                    
                else:
                    logging.debug('Segment %s has no pages. Separator on first page, last page or on consecutive pages?'% (str(filenamePostfix)))
                
                
                startPage=endPage+1
        logging.info('Finished splitting %s in: %d seconds.'%(filename, int(time.time() - startSplitTime)))
        
        sourcePDF.close()
        
    if len(fileList) == 0:
        saveAs = path.join(outpath , path.basename(filename))
        try: 
            logging.debug('Start to copy') 
            copy2(filename, saveAs)
            fileList.append(saveAs)
            logging.info('%s copied to %s' % (filename, saveAs)) 
            try:                
                if extractText==True:
                    savePDFTextFile (saveAs)
            except Exception as e:
                logging.critical('Saving raw text of PDF %s failed. %s' % (saveAs, e))             
        except:
            logging.critical('Writing source file to output folder failed')    

    logging.debug('Total time: %d seconds.'%(int(time.time() - startSplitTime)))
    return fileList
         
   
if __name__ == "__main__":
   
    parser = argparse.ArgumentParser(description="""Split a PDF-file into separate files based on a separator QR-Code / barcode / keyword. 
Without --sticker-mode the separator page will be discarded. In Sticker Mode
a separator starts a new segment and the page will be added to the output.
Be sure to add a separator to the first page as well when using Sticker Mode.
You can use the pattern <SEPARATOR>|<CUSTOM_POSTFIX> in your QR-Code / Barcode
to add a custom postfix to the filename by using --sticker-mode (Use individual 
postfixes in each code since no segment numbers are added). 

Examples: 
    NEXT|CoverLetter NEXT|Attachments 
    or 
    NEXT|CoverLetter_Miller NEXT|CoverLetter_Smith

If you use Sticker Mode without a custom prefix segment numbers will be added
to the filename.""")

    parser.add_argument('filename', metavar='/path/to/inputfile.pdf', type=str,
                    help='Filename of PDF')
    parser.add_argument('-d', '--drop-filename', action='store_true',
                    help='Do not use input filename for output filename')
    parser.add_argument('-s', '--separator', type=str, default="NEXT",
                        help='Separator word used to find separator pages. Default: NEXT')
    parser.add_argument('--sticker-mode', action='store_true',
                        help='New PDF-Seqment starts at QR-Code (Page will be kept). Add custom postfix to barcode content by using | as delimiter')
    parser.add_argument('-w', '--workers', type=int, default=0,
                        help='Number of process workers. Default is CPU cores - 1.')
    parser.add_argument('-sr', '--skip-rewrite', action='store_true',
                        help='Skip rewrite / preparation step and work with unaltered source PDF.')
    parser.add_argument('-m,', '--mode',  default="QR", choices=['QR', 'BARCODE', 'KEYWORD'],
                        help='Select used separator: QR (default), BARCODE, KEYWORD')
    parser.add_argument('-af', '--area-factor', type=float, choices=[(1 * x / 4 ) for x in range(1, 5)], default=1.0,
                        help='Speed up QR/Barcode search by limiting search area. Origin is top left corner. Default is 1.0 (whole page). E.g. 0.5 is upper left quadrant.')
    parser.add_argument('-t', '--extract-text', action='store_true',
                    help='Save text in separate text file')
    parser.add_argument('-o', '--output-folder', metavar='/path/to/output/folder', type=str, 
                        help='Where to save the split files? Default: Same as input folder')
    parser.add_argument('--log', default="WARNING", choices=['WARNING', 'INFO', 'DEBUG'],
                        help='Available log levels: WARNING, INFO, DEBUG')

    args = parser.parse_args()

    #logger = logging.getLogger('splitPDF')
    loglevel=logging.getLevelName(args.log.upper())
    if isinstance(loglevel, int):
        logging.basicConfig(level=loglevel)
    else:
        raise ValueError('Invalid log level: %s' % loglevel)
        
    for file in splitPDF (args.filename, args.output_folder, args.separator, args.mode, args.sticker_mode, args.drop_filename, args.workers, args.skip_rewrite, args.area_factor, args.extract_text):
        print(file)
