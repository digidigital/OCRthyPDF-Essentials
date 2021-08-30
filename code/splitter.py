#!/usr/bin/env python3
#Version 0.4
import zxing
import logging
import argparse
import re
import subprocess
import shlex
import sys
import time
import concurrent.futures

from tempfile import TemporaryDirectory
from pikepdf import Pdf, PdfImage, Page, PdfError, _cpphelpers 
from os import path
from multiprocessing import cpu_count

startScriptTime = time.time()
parser = argparse.ArgumentParser(description="""Split a PDF-file into separate files based on a separator barcode / QR-Code. 
Without --sticker-mode the separator page will be discarded. In Sticker Mode
a QR-Code starts a new segment and the page will be added to the output.
Be sure to add a QR-Code to the first page as well.
You can use the pattern <SEPARATOR>|<CUSTOM_POSTFIX> in your QR-Code to add
a custom postfix to the filename by using --sticker-mode (Use individual 
postfixes in each code since no segment numbers are added). 

Examples: 
    NEXT|CoverLetter NEXT|Attachments 
    or 
    NEXT|CoverLetter_Miller NEXT|CoverLetter_Smith

If you use Sticker Mode without a custom prefix segment numnbers will be added
to the filename.""")

def analyzePage(PDF, pageNumber, separator):
    reader = zxing.BarCodeReader()
    separatorCode=None
    logger.info('Analyzing page: %d'% (pageNumber+1))
       
    with TemporaryDirectory() as temp_dir:
        
        for image in PDF.pages[0].images.keys():
            pdfimage = PdfImage(PDF.pages[0].images[image]) 
            extractedImage = str(temp_dir) + str(image)
            logger.debug('Extracting image: ' + extractedImage)
            try:
                savedImage = pdfimage.extract_to(fileprefix=extractedImage)
                logger.debug('Saved as: ' + savedImage)
                #If image not JPG or PNG convert to PNG
                if not re.findall("\.(jpg\Z|JPG\Z|png\Z|PNG\Z)", savedImage):
                    newImage = savedImage + '.jpg'
                    logger.debug('Converting %s to %s'% (savedImage, newImage))
                    command = shlex.split("convert -verbose -quality 100% '" + savedImage + "' '" + newImage + "'")
                    logger.debug(command)
                    try:
                        subprocess.run(command)  
                        savedImage = newImage
                    except:
                        logger.debug('Conversion failed')
                        continue
                    
            except NotImplementedError:
                logger.debug('PikePDF was unable to extract image: ' + extractedImage + ' - Not implemented')
                continue
            except:
                logger.debug('Some error occured while extracting ' + extractedImage)
                continue
            
            try:
                logger.debug('Trying to find barcode in: %s' % (savedImage)) 
                barcode = reader.decode(savedImage)
            except: 
                logger.debug('Decoding barcode failed. Most likely the image format is not supported.')
                barcode = False
                continue

            if barcode:
                logger.info('QR-Code / Barcode containing text "%s" found on page %d. Use | as delimiter if you want to use a custom postfix' % (barcode.parsed, pageNumber+1))
                barcodeComponents = barcode.parsed.split('|',1)
                if len(barcodeComponents)==2 and barcodeComponents[0] == separator:
                    separatorCode = str(barcodeComponents[1])  
                    #Do not search for barcodes in remaining images
                    break

                elif barcodeComponents[0] == separator:
                    separatorCode = ''  
                    #Do not search for barcodes in remaining images
                    break

                else:
                    logger.info('Ignored. Reason: "%s" on page %d does not start with separator "%s". Use | as delimiter if you want to use a custom postfix' % (barcode.parsed, pageNumber+1, separator))     
                    continue

    return (pageNumber,separatorCode)

parser.add_argument('filename', metavar='/path/to/inputfile.pdf', type=str,
                    help='Filename of PDF')
parser.add_argument('-d', '--drop-filename', action='store_true',
                    help='Do not use input filename for output filename')
parser.add_argument('-s', '--separator', type=str, default="NEXT",
                    help='Barcode text used to find separator pages. Default: NEXT')
parser.add_argument('--sticker-mode', action='store_true',
                    help='New PDF-Seqment starts at QR-Code (Page will be kept). Add custom postfix to barcode content by using | as delimiter')
parser.add_argument('-r', '--rewrite', action='store_true',
                    help='Split a rewritten version of the source PDF.')
parser.add_argument('-o', '--output-folder', metavar='/path/to/output/folder', type=str, 
                    help='Where to save the split files? Default: Same as input folder')
parser.add_argument('--log', default="WARNING", choices=['WARNING', 'INFO', 'DEBUG'],
                    help='Available log levels: WARNING, INFO, DEBUG')

args = parser.parse_args()

logger = logging.getLogger('splitPDF')
loglevel=logging.getLevelName(args.log.upper())
if isinstance(loglevel, int):
    logging.basicConfig(level=loglevel)
else:
    raise ValueError('Invalid log level: %s' % loglevel)

if args.log.upper() == "DEBUG":
    gsQuiet=''
else:
    gsQuiet=' -q '

def splitPDF(filename:str, outpath:str, separator='NEXT', stickerMode=False, dropName=False, noRepair=False):
       
    logger.info('Rewriting PDF.')
    tempSourceDir=TemporaryDirectory()
    rewrittenPDF= tempSourceDir.name + "/repaired.pdf"
    
    command = shlex.split("gs -o " + rewrittenPDF + gsQuiet + " -sDEVICE=pdfwrite  -dPDFSETTINGS=/prepress '" + filename + "'")
   
    logger.debug(command)     
    try:  
        subprocess.run(command) 
    except:
        logger.debug('Rewriting failed')
        sys.exit("Unable to start rewrite step. Is Ghostscript installed?")
     
    sourcePDF = Pdf.open(rewrittenPDF)
 
    if not outpath:
        outpath=path.dirname(filename)

    if dropName == True:
        sourceName = ''
    else:
        sourceName = path.basename(filename).split('.',1)[0]+'_'
    
    # key: page number where barcode was found, value: a value in the barcode separated 
    # by | or the number of QR-Codes found
    separatorPages={}
    
    # let's see how quick we can analyze th epages in multiprocessing/threading
    startTime = time.time()

    # All files created while splitting
    fileList=[]
    logger.info('Extracting images and searching for QR-Codes / Barcodes')

    separatePages=[]
    with Pdf.open(rewrittenPDF) as pdf:
        pageCollection=[]

        #creating single page PDFs since passing a page directly raises a pickle exception :(
        for page in pdf.pages:
            tempPDF = Pdf.new()
            tempPDF.pages.append(page)
            pageCollection.append(tempPDF)
        
        max_workers=round((cpu_count()*2/3),0)

        logger.info('Analyzing pages with %d workers' % (max_workers))
        with concurrent.futures.ThreadPoolExecutor(max_workers) as executor:
            future_page_analyzer = {executor.submit(analyzePage, pageCollection[pageNumber], pageNumber, separator): pageNumber for pageNumber in range(len(pdf.pages))}
            for future in concurrent.futures.as_completed(future_page_analyzer):
                thread = future_page_analyzer[future]
                try:
                    if future.result()[1] != None:
                        separatorPages[future.result()[0]]=future.result()[1]
                        #result=future.result()

                except Exception as exc:
                    logger.info('Thread %r generated an exception: %s' % (thread, exc))
        
        for page in pageCollection:
            page.close()

    logger.info('Analysis completed: %d separators found on %d pages. This took about %d seconds'%(len(separatorPages),len(pageCollection), int(time.time() - startTime)))

    if args.rewrite:
        logger.info('Pages will be copied from rewritten PDF. Check for font substitutions!')
        sourcePDF = Pdf.open(rewrittenPDF)
    else:
        logger.info('Pages will be copied from original PDF.')   
        sourcePDF = Pdf.open(filename)
        
    #Separator pages start new segment and will be kept 
    if stickerMode == True and len(separatorPages)>0:
        logger.info('Assembling PDFs in "Sticker Mode"')
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
                logger.debug('Adding source page %d to new PDF' % (includePage+1))
                splitPDF.pages.append(sourcePDF.pages[includePage])  
            saveAs = outpath + '/' + sourceName  +  filenamePostfix + '.pdf'
            logger.info('Saving PDF: %s' % (saveAs))
            fileList.append(saveAs)
            try:
                splitPDF.save(saveAs)
            except:
                logger.debug('Saving PDF failed.')
            splitPDF.close() 

    #Separator pages are dropped    
    elif len(separatorPages)>0:
        logger.info('Assembling PDFs in "Separator Page Mode"')
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

            filenamePostfix= "%04d"% (x+1)
            
            hasPages = False

            pageRange = range (startPage, endPage)
            for includePage in pageRange:
                logger.debug('Adding source page %d to new PDF' % (includePage+1))
                splitPDF.pages.append(sourcePDF.pages[includePage])  
                hasPages = True
            if hasPages:
                saveAs = outpath + '/' + str(sourceName) + str(filenamePostfix) + '.pdf'
                logger.info('Saving PDF: %s' % (saveAs))
                fileList.append(saveAs)
                try:
                    splitPDF.save(saveAs)
                except:
                    logger.debug('Saving PDF failed.')
            else:
                logger.debug('Segment %s has no pages. QR-Codes on first page, last page or on consecutive pages?'% (str(filenamePostfix)))
            splitPDF.close() 
            
            startPage=endPage+1
    logger.info('Finished splitting %s in: %d seconds.'%(args.filename, int(time.time() - startScriptTime)))
    sourcePDF.close()
    
    if len(fileList) > 0:
        return fileList 
    else:
        return None

if __name__ == "__main__":

    print(str(splitPDF (args.filename, args.output_folder, args.separator, args.sticker_mode, args.drop_filename, args.rewrite)))
