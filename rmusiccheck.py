#!/usr/bin/python
# -*- coding: utf-8 -*-
'''rMusicCheck 0.1

Author:      Rabit <home@rabits.org>
License:     GPL v3
Description: Script will check your local music database, verify artists & albums and list new albums by musicbrainz database
Required:    

Usage:
  $ ./rmusiccheck.py --help
'''

from sys import stderr, stdout, exit as sysexit
import os, time, urllib2, re

from optparse import OptionParser
import ConfigParser

if os.geteuid() == 0:
    stderr.write("ERROR: rMusicCheck is running by the root user, but this is really dangerous! Please use unprivileged user.\n")
    sysexit()

# Predefines
SCHEME_FIELDS = {
    'artist': { 'req': True,  're': r'[a-zA-Z0-9_- ]+' },
    'album':  { 'req': True,  're': r'[a-zA-Z0-9_- ]+' },
    'track':  { 'req': True,  're': r'\d+' },
    'title':  { 'req': True,  're': r'[a-zA-Z0-9_- ]+' },
    'year':   { 'req': True,  're': r'\d{4}' },
    'genre':  { 'req': False, 're': r'[a-zA-Z0-9_- ]+' },
}

def exampleini(option, opt, value, parser):
    print '[rmc]'
    for key in parser.option_list:
        if None not in [key.dest, key.type] and key.dest != 'config-file':
            print '%s: %s' % (key.dest, key.default)
    sysexit()

# Parsing command line options
parser = OptionParser(usage='%prog [options]', version=__doc__.split('\n', 1)[0])
parser.add_option('-p', '--playlist', type='string', dest='playlist', metavar='DIR',
        default=None, help='your main music directory (required)')
parser.add_option('-o', '--other', type='string', dest='other', metavar='DIR',
        default=None, help='other directory with non-playlist music [%default]')
parser.add_option('-u', '--url-db', type='string', dest='url-db', metavar='URL',
        default='http://musicbrainz.org/ws/2', help='musicbrainz api url [%default]')
parser.add_option('-d', '--database', type='string', dest='database', metavar='DIR',
        default='${HOME}/.local/share/rmusiccheck', help='your local database directory ["%default"]')
parser.add_option('-s', '--scheme', type='string', dest='scheme', metavar='PATH',
        default='{genre}/{artist}/[{year}] {album}/{track} - {title}', help='scheme of your music folder (available: %s) %s' % (','.join(SCHEME_FIELDS), '["%default"]'))
parser.add_option('-a', '--audio-ext', type='string', dest='audio-ext', metavar='EXT',
        default='mp3,flac', help='music file extensions, separated by comma ["%default"]')
parser.add_option('-c', '--config-file', type='string', dest='config-file', metavar='FILE',
        default=None, help='get configuration from ini file (replaced by command line parameters) [%default]')
parser.add_option('-e', '--config-example', action='callback', callback=exampleini,
        default=None, help='print example ini config file to stdout')
parser.add_option('-l', '--log-file', type='string', dest='log-file', metavar='FILE',
        default=None, help='copy log output to file [%default]')
parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
        help='verbose mode - moar output to stdout')
parser.add_option('-q', '--quiet', action='store_false', dest='verbose',
        help='silent mode - no output to stdout')
(options, args) = parser.parse_args()
options = vars(options)

# Parsing config file
if options['config-file'] != None:
    try:
        config = ConfigParser.ConfigParser()
        config.read(options['config-file'])

        for key in parser.option_list:
            if None not in [key.dest, key.type]:
                if options[key.dest] is key.default:
                    try:
                        if key.type in ['int', 'float', 'boolean']:
                            val = getattr(config, 'get%s' % key.type)('rmc', key.dest)
                        else:
                            val = config.get('rmc', key.dest)
                        options[key.dest] = val
                    except ConfigParser.NoOptionError:
                        continue
    except:
        parser.error('Error while parse config file. Please specify header and available options')

# Checking options
if options['playlist'] == None:
    parser.error('Unable to get playlist directory from playlist option (= None)')
elif not os.path.isdir(options['playlist']):
    parser.error('Playlist folder "%s" is not exists' % options['playlist'])

if options['other'] != None and not os.path.isdir(options['playlist']):
    parser.error('Other folder "%s" is not exists' % options['other'])

options['audio-ext'] = options['audio-ext'].lower().split(',')

for field, data in SCHEME_FIELDS.items():
    if data['req'] and field not in options['scheme']:
        parser.error('Unable to find required field "{%s}" in scheme' % (field, options['scheme']))

# LOGGING
if options['log-file'] != None:
    class Tee(object):
        def __init__(self, *files):
            self.files = files
        def write(self, obj):
            for f in self.files:
                f.write(obj)
                f.flush()

    logfile = open(options['log-file'], 'a')
    stdout = Tee(stdout, logfile)
    stderr = Tee(stderr, logfile)

if options['verbose'] == True:
    import inspect
    def log(logtype, message):
        func = inspect.currentframe().f_back
        log_time = time.time()
        if logtype != "ERROR":
            stdout.write('[%s.%s %s, line:%03u]: %s\n' % (time.strftime('%H:%M:%S', time.localtime(log_time)), str(log_time % 1)[2:8], logtype, func.f_lineno, message))
        else:
            stderr.write('[%s.%s %s, line:%03u]: %s\n' % (time.strftime('%H:%M:%S', time.localtime(log_time)), str(log_time % 1)[2:8], logtype, func.f_lineno, message))
elif options['verbose'] == False:
    def log(logtype, message):
        if logtype == "ERROR":
            stderr.write('[%s %s]: %s\n' % (time.strftime('%H:%M:%S'), logtype, message))
else:
    def log(logtype, message):
        if logtype != "DEBUG":
            if logtype != "ERROR":
                stdout.write('[%s %s]: %s\n' % (time.strftime('%H:%M:%S'), logtype, message))
            else:
                stderr.write('[%s %s]: %s\n' % (time.strftime('%H:%M:%S'), logtype, message))




class RMusicCheck:
    '''
    Basic control class
    '''
    def __init__(self):
        log('DEBUG', 'Init...')
        splitted_scheme = options['scheme'].split('/')
        self.scheme_fields = [[j[1:-1] for j in re.findall(r'{\w+}', i)] for i in splitted_scheme]
        self.scheme_re = []
        for part in splitted_scheme:
            part = re.escape(part)
            for field, data in SCHEME_FIELDS.items():
                f = '\\{%s\\}' % field
                if f in part:
                    part = part.replace(f, data['re'])
            self.scheme_re.append(part)
        self.db = {}

    def start(self):
        log('DEBUG', 'Process starting...')
        self.initTrees()

    def initTrees(self):
        log('DEBUG', 'Populating trees...')
        self.trees = [self.createTree(options['playlist'], len(options['playlist']))]
        if options['other']:
            self.trees.append(self.createTree(options['other'], len(options['other'])))

    def pushDB(self, path):
         splitted = path.split('/')
         if len(splitted) != len(self.scheme_fields):
             log('WARNING', 'Skip: Bad number of subfolders: %s' % path)
             return False
         return True

    def createTree(self, path, basepathlen):
        out = {}
        for f in os.listdir(path):
            fullpath = os.path.join(path, f)
            if os.path.isdir(fullpath):
                out[f] = self.createTree(fullpath, basepathlen)
            else:
                if os.path.splitext(f)[1].lower()[1:] in options['audio-ext']:
                    if not self.pushDB(fullpath[basepathlen+1:]):
                        break
                    out[f] = True
                else:
                    out[f] = False
        return out

# Request artist id: http://musicbrainz.org/ws/2/artist/?query=artist:Ария&fmt=json
# Request releases for id: http://musicbrainz.org/ws/2/artist/1f36a3a2-9687-4819-ac55-54d7ff0b8b88?inc=releases&fmt=json

rmc = RMusicCheck()
rmc.start()
