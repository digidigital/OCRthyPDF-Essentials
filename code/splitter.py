#!/usr/bin/env python3
'''Version 0.3'''
import zxing
import logging
import argparse
import re
import subprocess
import shlex

from tempfile import TemporaryDirectory
from pikepdf import Pdf, PdfImage, Page, PdfError, _cpphelpers 
from os import path

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

parser.add_argument('filename', metavar='/path/to/inputfile.pdf', type=str,
                    help='Filename of PDF')
parser.add_argument('-d', '--drop-filename', action='store_true',
                    help='Do not use input filename for output filename')
parser.add_argument('-s', '--separator', type=str, default="NEXT",
                    help='Barcode text used to find separator pages. Default: NEXT')
parser.add_argument('--sticker-mode', action='store_true',
                    help='New PDF-Seqment starts at QR-Code (Page will be kept). Add custom postfix to barcode content by using | as delimiter')
parser.add_argument('-o', '--output-folder', metavar='/path/to/output/folder', type=str, 
                    help='Where to save the split files? Default: Same as input folder')
parser.add_argument('--log', default="WARNING", choices=['WARNING', 'INFO', 'DEBUG'],
                    help='Available log levels: WARNING, INFO, DEBUG')

args = parser.parse_args()

logger = logging.getLogger('splitPDF')
loglevel=logging.getLevelName(args.log)
if isinstance(loglevel, int):
    logging.basicConfig(level=loglevel)
else:
    raise ValueError('Invalid log level: %s' % loglevel)

def splitPDF(filename:str, outpath:str, separator='NEXT', stickerMode=False, dropname=False):
    sourcePDF = Pdf.open(filename)
    reader = zxing.BarCodeReader()

    if not outpath:
        outpath=path.dirname(filename)

    if dropname == True:
        sourceName = ''
    else:
        sourceName = path.basename(filename).split('.',1)[0]+'_'
    
    # key: page number where barcode was found, value: a value in the barcode separated 
    # by | or the number of QR-Codes found
    separatorPages={}
    
    # All files created while splitting
    fileList=[]
    pageNumber=0
    totalImages=0
    logger.info('Extracting images and searching for QR-Codes / Barcodes')
    splitIndex=1 
    for page in sourcePDF.pages:
        logger.debug('Analyzing page: %d'% (pageNumber+1))
        #splitIndex is used as postfix if no other postfix is in barcode  
        with TemporaryDirectory() as temp_dir:
            
            for image in page.images.keys():
                totalImages+=1 
                pdfimage = PdfImage(page.images[image]) 
                extractedImage = str(temp_dir) + str(image)
                logger.debug('Extracting image: ' + extractedImage)
                try:
                    savedImage = pdfimage.extract_to(fileprefix=extractedImage)
                    logger.debug('Saved as: ' + savedImage)
                    #If image not JPG or PNG convert to PNG
                    if not re.findall("\.(jpg\Z|JPG\Z|png\Z|PNG\Z)", savedImage):
                        newImage = savedImage + '.png'
                        logger.debug('Converting %s to %s'% (savedImage, newImage))
                        command = shlex.split("convert '" + savedImage + "' '" + newImage + "'")
                        try:
                            subprocess.run(command) 
                        except:
                            logger.debug('Conversion failed')
                            break
                        savedImage = newImage
                except NotImplementedError:
                    logger.debug('Unable to extract image: ' + extractedImage + ' - Not implemented')
                    break
                except:
                    logger.debug('Some error occured while extracting ' + extractedImage)
                    break
                try:
                    barcode = reader.decode(savedImage)
                except: 
                    logger.debug('Decoding barcode failed.')
                    barcode = False
                    break
                if barcode:
                    logger.info('QR-Code / Barcode containing text "%s" found on page %d' % (barcode.parsed, pageNumber+1))
                    barcodeComponents = barcode.parsed.split('|',1)
                    if len(barcodeComponents)==2 and barcodeComponents[0] == separator:
                        separatorPages [pageNumber] = str(barcodeComponents[1])
                    elif barcodeComponents[0] == separator:
                        separatorPages [pageNumber] = "%04d"% (int(splitIndex))
                        splitIndex+=1  
                        print(splitIndex)
                        print(separatorPages [pageNumber])
                    else:
                        logger.info('Ignored. Reason: Does not start with separator "%s". Use | as delimiter if you want to use a custom postfix' % (separator))     
        pageNumber+=1
    
    logger.info('Analysis completed: %d separators found on %d pages in %d images.'%(len(separatorPages),pageNumber,totalImages))

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
        fileIndex=1

        for x in range (0,len(pageList)+1): 

            if x == len(pageList):
                #Last segment ends with last page of PDF
                endPage=len(sourcePDF.pages) 
            else:
                #Stop at page before separator was found
                endPage=pageList[x]
            splitPDF = Pdf.new()

            filenamePostfix= "%04d"% (fileIndex)
            
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
            fileIndex+=1

    if len(fileList) > 0:
        return fileList 
    else:
        return None

if __name__ == "__main__":

    print(str(splitPDF (args.filename, args.output_folder, args.separator, args.sticker_mode, args.drop_filename)))
