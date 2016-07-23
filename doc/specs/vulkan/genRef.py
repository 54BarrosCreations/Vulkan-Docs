#!/usr/bin/python3
#
# Copyright (c) 2016 The Khronos Group Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# genRef.py - create Vulkan ref pages from spec source files
#
#
# Usage: genRef.py files

from reflib import *
from vkapi import *
import argparse, copy, os, pdb, re, string, sys

# Return True if name is a Vulkan extension name (ends with an upper-case
# author ID). This assumes that author IDs are at least two characters.
def isextension(name):
    return name[-2:].isalpha() and name[-2:].isupper()

# Print Khronos CC-BY copyright notice on open file fp. If comment is
# True, print as an asciidoc comment block, which copyrights the source
# file. Otherwise print as an asciidoc include of the copyright in markup,
# which copyrights the outputs.
def printCopyrightBlock(fp, comment=True):
    if (comment):
        print('// Copyright (c) 2014-2016 Khronos Group. This work is licensed under a', file=fp)
        print('// Creative Commons Attribution 4.0 International License; see', file=fp)
        print('// http://creativecommons.org/licenses/by/4.0/', file=fp)
        print('', file=fp)
    else:
        print('include::footer.txt[]', file=fp)
        print('', file=fp)

# Add a spec asciidoc macro prefix to a Vulkan name, depending on its type
# (protos, structs, enums, etc.)
def macroPrefix(name):
    if (name in basetypes.keys()):
        return 'basetype:' + name
    elif (name in defines.keys()):
        return 'slink:' + name
    elif (name in enums.keys()):
        return 'elink:' + name
    elif (name in flags.keys()):
        return 'elink:' + name
    elif (name in funcpointers.keys()):
        return 'tlink:' + name
    elif (name in handles.keys()):
        return 'slink:' + name
    elif (name in protos.keys()):
        return 'flink:' + name
    elif (name in structs.keys()):
        return 'slink:' + name
    elif (name == 'TBD'):
        return 'No cross-references are available'
    else:
        return 'UNKNOWN:' + name

# Return an asciidoc string with a list of 'See Also' references for the
# Vulkan entity 'name', based on the relationship mapping in vkapi.py and
# the additional references in explicitRefs. If no relationships are
# available, return None.
def seeAlsoList(apiName, explicitRefs = None):
    refs = {}

    # Add all the implicit references to refs
    if (apiName in mapDict.keys()):
        for name in sorted(mapDict[apiName].keys()):
            refs[name] = None

    # Add all the explicit references
    if (explicitRefs != None):
        for name in explicitRefs.split():
            refs[name] = None

    names = [macroPrefix(name) for name in sorted(refs.keys())]
    if (len(names) > 0):
        return ', '.join(names) + '\n'
    else:
        return None

# Generate header of a reference page
# pageName - string name of the page
# pageDesc - string short description of the page
# specText - string that goes in the "C Specification" section
# fieldName - string heading an additional section following specText, if not None
# fieldText - string that goes in the additional section
# descText - string that goes in the "Description" section
# fp - file to write to
def refPageHead(pageName, pageDesc, specText, fieldName, fieldText, descText, fp):
    printCopyrightBlock(fp, comment=True)

    s = pageName + '(3)'
    print(s,
          ''.ljust(len(s), '='),
          '',
          sep='\n', file=fp)

    print('Name',
          '----',
          pageName + ' - ' + pageDesc,
          '',
          sep='\n', file=fp)

    print('C Specification',
          '---------------',
          '',
          specText,
          '',
          sep='\n', file=fp)

    if (fieldName != None):
        print(fieldName,
              ''.ljust(len(fieldName), '-'),
              '',
              fieldText,
              sep='\n', file=fp)

    print('Description',
          '-----------',
          '',
          descText,
          '',
          sep='\n', file=fp)

def refPageTail(pageName, seeAlso, fp, auto = False):
    # This is difficult to get working properly in asciidoc
    # specURL = 'link:{vkspecpath}/vkspec.html'

    # This needs to have the current repository branch path installed in
    # place of '1.0'
    specURL = 'https://www.khronos.org/registry/vulkan/specs/1.0/xhtml/vkspec.html'

    if (seeAlso == None):
        seeAlso = 'No cross-references are available\n'

    notes = [
        'For more information, see the Vulkan Specification at URL',
        '',
        specURL + '#' + pageName,
        '',
        ]

    if (auto):
        notes.extend([
            'This page is a generated document.',
            'Fixes and changes should be made to the generator scripts,'
            'not directly.',
            ])
    else:
        notes.extend([
            'This page is extracted from the Vulkan Specification.',
            'Fixes and changes should be made to the Specification,'
            'not directly.',
            ])

    print('See Also',
          '--------',
          '',
          seeAlso,
          '',
          sep='\n', file=fp)

    print('Document Notes',
          '--------------',
          '',
          '\n'.join(notes),
          '',
          sep='\n', file=fp)

    printCopyrightBlock(fp, comment=False)

# Emit a single reference page in baseDir
#   baseDir - base directory to emit page into
#   pi - pageInfo for this page relative to file
#   file - list of strings making up the file, indexed by pi
def emitPage(baseDir, pi, file):
    pageName = baseDir + '/' + pi.name + '.txt'
    fp = open(pageName, 'w')

    # Add a dictionary entry for this page
    global genDict
    genDict[pi.name] = None
    logDiag('emitPage:', pageName)

    # Short description
    if (pi.desc == None):
        pi.desc = '(no short description available)'

    # Specification text
    specText = ''.join(file[pi.begin:pi.include+1])

    # Member/parameter list, if there is one
    field = None
    fieldText = None
    if (pi.param != None):
        if (pi.type == 'structs'):
            field = 'Members'
        elif (pi.type in ['protos', 'funcpointers']):
            field = 'Parameters'
        else:
            logWarn('PyOutputGenerator::emitPage: unknown field type:', pi.type,
                'for', pi.name)
        fieldText = ''.join(file[pi.param:pi.body])

    # Description text
    descText = ''.join(file[pi.body:pi.end+1])

    refPageHead(pi.name,
                pi.desc,
                specText,
                field, fieldText,
                descText,
                fp)
    refPageTail(pi.name, seeAlsoList(pi.name, pi.refs), fp, auto = False)
    fp.close()

# Autogenerate a single reference page in baseDir
# Script only knows how to do this for /enums/ pages, at present
#   baseDir - base directory to emit page into
#   pi - pageInfo for this page relative to file
#   file - list of strings making up the file, indexed by pi
def autoGenEnumsPage(baseDir, pi, file):
    pageName = baseDir + '/' + pi.name + '.txt'
    fp = open(pageName, 'w')

    # Add a dictionary entry for this page
    global genDict
    genDict[pi.name] = None
    logDiag('autoGenEnumsPage:', pageName)

    # Short description
    if (pi.desc == None):
        pi.desc = '(no short description available)'

    # Description text
    txt = ''.join([
        'For more information, see:\n\n',
        '  * The reference page for ' + macroPrefix(pi.embed) +
            ', where this interface is defined.\n',
        '  * The See Also section for other reference pages using this type.\n',
        '  * The Vulkan Specification.\n' ])

    refPageHead(pi.name,
                pi.desc,
                ''.join(file[pi.begin:pi.include+1]),
                None, None,
                txt,
                fp)
    refPageTail(pi.name, seeAlsoList(pi.name, pi.refs), fp, auto = True)
    fp.close()

# Pattern to break apart a Vk*Flags{authorID} name, used in autoGenFlagsPage.
flagNamePat = re.compile('(?P<name>\w+)Flags(?P<author>[A-Z]*)')

# Autogenerate a single reference page in baseDir for a Vk*Flags type
#   baseDir - base directory to emit page into
#   flagName - Vk*Flags name
def autoGenFlagsPage(baseDir, flagName):
    pageName = baseDir + '/' + flagName + '.txt'
    fp = open(pageName, 'w')

    # Add a dictionary entry for this page
    global genDict
    genDict[flagName] = None
    logDiag('autoGenFlagsPage:', pageName)

    # Short description
    matches = flagNamePat.search(flagName)
    if (matches != None):
        name = matches.group('name')
        author = matches.group('author')
        logDiag('autoGenFlagsPage: split name into', name, 'Flags', author)
        flagBits = name + 'FlagBits' + author
        desc = 'Bitmask of ' + flagBits
    else:
        logWarn('autoGenFlagsPage:', pageName, 'does not not end in "Flags{author ID}". Cannot infer FlagBits type.')
        flagBits = None
        desc = 'Unknown Vulkan flags type'

    # Description text
    if (flagBits != None):
        txt = ''.join([
            'etext:' + flagName,
            ' is a mask of zero or more elink:' + flagBits + '.\n',
            'It is used as a member and/or parameter of the structures and commands\n',
            'in the See Also section below.\n' ])
    else:
        txt = ''.join([
            'etext:' + flagName,
            ' is an unknown Vulkan type, assumed to be a bitmask.\n' ])

    refPageHead(flagName,
                desc,
                'include::../api/flags/' + flagName + '.txt[]\n',
                None, None,
                txt,
                fp)
    refPageTail(flagName, seeAlsoList(flagName), fp, auto = True)
    fp.close()

# Autogenerate a single handle page in baseDir for a Vk* handle type
#   baseDir - base directory to emit page into
#   handleName - Vk* handle name
# @@ Need to determine creation function & add handles/ include for the
# @@ interface in generator.py.
def autoGenHandlePage(baseDir, handleName):
    pageName = baseDir + '/' + handleName + '.txt'
    fp = open(pageName, 'w')

    # Add a dictionary entry for this page
    global genDict
    genDict[handleName] = None
    logDiag('autoGenHandlePage:', pageName)

    # Short description
    desc = 'Vulkan object handle'

    descText = ''.join([
        'sname:' + handleName,
        ' is an object handle type, referring to an object used\n',
        'by the Vulkan implementation. These handles are created or allocated\n',
        'by the vk @@ TBD @@ function, and used by other Vulkan structures\n',
        'and commands in the See Also section below.\n' ])

    refPageHead(handleName,
                desc,
                'include::../api/handles/' + handleName + '.txt[]\n',
                None, None,
                descText,
                fp)
    refPageTail(handleName, seeAlsoList(handleName), fp, auto = True)
    fp.close()

# Extract reference pages from a spec asciidoc source file
#   specFile - filename to extract from
#   baseDir - output directory to generate page in
#
def genRef(specFile, baseDir):
    file = loadFile(specFile)
    if (file == None):
        return
    pageMap = findRefs(file)
    logDiag(specFile + ': found', len(pageMap.keys()), 'potential pages')

    sys.stderr.flush()

    # Fix up references in pageMap
    fixupRefs(pageMap, specFile, file)

    # Create each page, if possible

    for name in sorted(pageMap.keys()):
        pi = pageMap[name]

        printPageInfo(pi, file)

        if (pi.Warning):
            logDiag('genRef:', pi.name + ':', pi.Warning)

        if (pi.extractPage):
            emitPage(baseDir, pi, file)
        elif (pi.type == 'enums'):
            autoGenEnumsPage(baseDir, pi, file)
        elif (pi.type == 'flags'):
            autoGenFlagsPage(baseDir, pi.name)
        else:
            # Don't extract this page
            logWarn('genRef: Cannot extract or autogenerate:', pi.name)

# Generate baseDir/apispec.txt, the single-page version of the ref pages.
# This assumes there's a page for everything in the vkapi.py dictionaries.
# Extensions (KHR, EXT, etc.) are currently skipped
def genSinglePageRef(baseDir):
    pageName = baseDir + '/apispec.txt'
    fp = open(pageName, 'w')

    printCopyrightBlock(fp, comment=True)

    print('Vulkan API Reference Pages',
          '==========================',
          'include::../specversion.txt[]',
          '',
          ':doctype: book',
          ':numbered!:',
          ':toc2:',
          ':max-width: 200',
          ':numbered:',
          ':doctype: book',
          ':data-uri:',
          ':asciimath:',
          ':toclevels: 4',
          '',
          sep='\n', file=fp)

    print('include::khronoscopyright.txt[]', file=fp)
    print('', file=fp)

    # Inject the table of contents. Asciidoc really ought to be generating
    # this for us.

    sections = [
        [ protos,       'protos',       'Vulkan Commands' ],
        [ handles,      'handles',      'Object Handles' ],
        [ structs,      'structs',      'Structures' ],
        [ enums,        'enums',        'Enumerations' ],
        [ flags,        'flags',        'Flags' ],
        [ funcpointers, 'funcpointers', 'Function Pointer Types' ],
        [ basetypes,    'basetypes',    'Vulkan Scalar types' ],
        [ defines,      'defines',      'C Macro Definitions' ] ]

    print('Table of Contents', file=fp)
    print('-----------------', file=fp)
    for (apiDict,label,title) in sections:
        print('  * <<' + label + ',' + title + '>>', file=fp)
    print('', file=fp)

    for (apiDict,label,title) in sections:
        anchor = '[[' + label + ',' + title + ']]'
        print(anchor,
              title,
              ''.ljust(len(title), '-'),
              '',
              ':leveloffset: 2',
              '',
              sep='\n', file=fp)
        for refPage in sorted(apiDict.keys()):
            if (apiDict == defines or not isextension(refPage)):
                print('include::' + refPage + '.txt[]', file=fp)
            else:
                print('// not including ' + refPage, file=fp)
        print('\n' + ':leveloffset: 0' + '\n', file=fp)

    # An index of pages could be generated here

if __name__ == '__main__':
    global genDict
    genDict = {}

    parser = argparse.ArgumentParser()

    parser.add_argument('-diag', action='store', dest='diagFile',
                        help='Set the diagnostic file')
    parser.add_argument('-warn', action='store', dest='warnFile',
                        help='Set the warning file')
    parser.add_argument('-log', action='store', dest='logFile',
                        help='Set the log file for both diagnostics and warnings')
    parser.add_argument('-basedir', action='store', dest='baseDir',
                        default='man',
                        help='Set the base directory in which pages are generated')
    parser.add_argument('files', metavar='filename', nargs='*',
                        help='a filename to extract ref pages from')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')

    results = parser.parse_args()

    setLogFile(True,  True, results.logFile)
    setLogFile(True, False, results.diagFile)
    setLogFile(False, True, results.warnFile)

    baseDir = results.baseDir

    for file in results.files:
        genRef(file, baseDir)

    # Now figure out which pages *weren't* generated from the spec.
    # This relies on the dictionaries of API constructs in vkapi.py.

    # For Flags (e.g. Vk*Flags types), it's easy to autogenerate pages.
    for page in flags.keys():
        if not (page in genDict.keys()):
            logWarn('Autogenerating flags page:', page, 'which should be included in the spec')
            autoGenFlagsPage(baseDir, page)

    # autoGenHandlePage is no longer needed because they are added to
    # the spec sources now.
    # for page in structs.keys():
    #    if (typeCategory[page] == 'handle'):
    #        autoGenHandlePage(baseDir, page)

    sections = [
        [ enums,        'Enumerated Types' ],
        [ structs,      'Structures' ],
        [ protos,       'Prototypes' ],
        [ funcpointers, 'Function Pointers' ],
        [ basetypes,    'Vulkan Scalar Types' ] ]

    for (apiDict,title) in sections:
        flagged = False
        for page in apiDict.keys():
            if not (page in genDict.keys()):
                if (not flagged):
                    logWarn(title, 'with no ref page generated:')
                    flagged = True
                logWarn('    ', page)

    genSinglePageRef(baseDir)
