# OCRthyPDF-Essentials
Make your PDF files text-searchable (A GUI for [OCRmyPDF](https://github.com/jbarlow83/OCRmyPDF/))

It started with the idea to provide users that are not used to command line tools access to OCRmyPDF's basic features.  

![OCRthyPDF GUI](https://raw.githubusercontent.com/digidigital/OCRthyPDF-Essentials/main/screenshots/1.png)

It supports more than 100 languages "out-of-the-box" (all languages that are installed with tesseract).

The splitter function extends the text recognition provided by OCRmyPDF. It allows scanned documents to be separated at [separator pages](https://github.com/digidigital/OCRthyPDF-Essentials/blob/main/testing/Separator.pdf) - defined by a QR code - before text recognition. A QR code can mark a [separator-only page](https://github.com/digidigital/OCRthyPDF-Essentials/blob/main/testing/Separator.pdf) that is discarded. Alternatively, in sticker mode, the QR code defines the first page of a new document and is retained.

If you like the results created with OCRthyPDF but need more flexibility I suggest you give [OCRmyPDF](https://github.com/jbarlow83/OCRmyPDF/) a try on the command line. :)

# How To Install
If you are using Ubuntu or any other Distro that comes with <code>snap</code> pre-installed you can install it directly from the Snap Store 

[![Get it from the Snap Store](https://snapcraft.io/static/images/badges/en/snap-store-black.svg)](https://snapcraft.io/ocrthypdf)

or you can type

<code>sudo snap install ocrthypdf</code> 

in your terminal.

If your Distro does not have snap pre-installed you can find instructions for installing snap [here.](https://snapcraft.io/docs/installing-snapd)

# Toubleshooting
Snaps run in a restricted environment and need permissions to access files on your computer (Similar to apps on your smartphone). So first check if you have set the correct permissions in the snap store user interface.

You can start OCRthyPDF from the terminal with
<code>ocrthypdf --log INFO</code>
or
<code>ocrthypdf --log DEBUG</code> 
in order to get more info in case the application does not work as expected.

Info about subprocesses like OCRmyPDF, Splitter, Ghostscript, etc. is displayed in the console tab. Set 'Loglevel' to DEBUG and 'Limit console ...' to 'no' for detailed information. 

Still no clue what went wrong? Report an issue [here](https://github.com/digidigital/OCRthyPDF-Essentials/issues).
