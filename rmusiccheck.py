#!/usr/bin/python
# -*- coding: utf-8 -*-
'''rMusicCheck 0.3

Author:      Rabit <home@rabits.org>
License:     GPL v3
Description: Script will check your local music database, verify artists & albums and list new albums by musicbrainz database
Required:    

Usage:
  $ ./rmusiccheck.py --help
'''

from sys import stderr, stdout, exit as sysexit
import os, time, urllib2, re, readline

from optparse import OptionParser
import ConfigParser

if os.geteuid() == 0:
    stderr.write("ERROR: rMusicCheck is running by the root user, but this is really dangerous! Please use unprivileged user.\n")
    sysexit()

# Predefines
SCHEME_FIELDS = {
    'required': {
        'artist': ur'[\w0-9_\-\ ,.!?&\']+',
        'album':  ur'[\w0-9_\-\ ,.!?&\']+',
        'track':  ur'\d+',
        'title':  ur'[\w0-9_\-\ ,.!?&\']+',
        'year':   ur'\d{4}',
    },
    'optional': {
        'genre':  ur'[a-zA-Z0-9_\-\ ]+',
    },
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
        default='{genre}/{artist}/[{year}] {album}/{track} - {title}', help='scheme of your music folder (available: %s) %s' % (','.join(SCHEME_FIELDS['required'].keys() + SCHEME_FIELDS['optional'].keys()), '["%default"]'))
parser.add_option('-m', '--manual-fix', action="store_true", dest='manual-fix',
        default=False, help='scheme of your music folder (available: %s) %s' % (','.join(SCHEME_FIELDS['required'].keys() + SCHEME_FIELDS['optional'].keys()), '["%default"]'))
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

for field in SCHEME_FIELDS['required']:
    if field not in options['scheme']:
        parser.error('Unable to find required field "{%s}" in your scheme "%s"' % (field, options['scheme']))

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


class Report:
    """
    Report class for collect number of problems
    """
    def __init__(self):
        log('DEBUG', 'Init report')
        self.data = {
            'extensions':{},
            'depth':[],
            'empty':[],
            'fields':{},
        }

    def pushExtension(self, path, ext):
        if ext not in self.data['extensions']:
            self.data['extensions'][ext] = []
        self.data['extensions'][ext].append(path)

    def pushDepth(self, path):
        self.data['depth'].append(path)

    def pushEmpty(self, path):
        self.data['empty'].append(path)

    def pushFields(self, path, fields):
        req = SCHEME_FIELDS['required'].keys()
        self.data['fields'][path] = [r for r in req if r not in fields]

    def show(self):
        log('REPORT', 'Found next bad extensions: %s' % ', '.join(self.data['extensions']))
        log('REPORT', 'Found bad music file depth:\n    %s' % '\n    '.join(self.data['depth']))
        log('REPORT', 'Found empty directories:\n    %s' % '\n    '.join(self.data['empty']))
        log('REPORT', 'Unable to get required field(s) for path(s):')
        for path, fields in self.data['fields'].items():
            log('REPORT', '    (%s)\t%s' % (', '.join(fields), path))


class RMusicCheck:
    '''
    Basic control class
    '''
    def __init__(self):
        log('DEBUG', 'Init...')
        self.report = Report()
        splitted_scheme = options['scheme'].split('/')
        self.scheme_fields = [[j[1:-1] for j in re.findall(r'{\w+}', i)] for i in splitted_scheme]
        self.scheme_re = []
        self.required_fields = SCHEME_FIELDS['required'].keys()
        for part in splitted_scheme:
            part = re.escape(part)
            for field, regexp in SCHEME_FIELDS['required'].items() + SCHEME_FIELDS['optional'].items():
                f = '\\{%s\\}' % field
                if f in part:
                    part = part.replace(f, '(%s)' % regexp)
            self.scheme_re.append(part)
        self.db = {}

    def start(self):
        log('DEBUG', 'Process starting...')
        self.initTrees()
        self.report.show()

    def initTrees(self):
        log('DEBUG', 'Populating trees...')
        self.treepath = options['playlist']
        self.trees = [self.createTree(options['playlist'])]
        if options['other']:
            self.treepath = options['other']
            self.trees.append(self.createTree(options['other']))

    def pushDB(self, path):
        if not self.checkDepth(path):
            return
        data = self.parse(path)
        if data:
            data['year'] = int(data['year'])
            album = '%d %s' % (data['year'], data['album'])
            track = int(data.pop('track'))
            title = data.pop('title')
            if data['artist'] not in self.db:
                self.db[data['artist']] = {}
            if album not in self.db[data['artist']]:
                self.db[data['artist']][album] = data
                self.db[data['artist']][album]['tracks'] = {}
                self.db[data['artist']][album]['paths'] = {}
                self.db[data['artist']][album]['count'] = 0
            self.db[data['artist']][album]['tracks'][track] = title
            self.db[data['artist']][album]['paths'][track] = path
            self.db[data['artist']][album]['count'] += 1

    def createTree(self, basepath, path = ''):
        out = {}
        listdir = os.listdir(os.path.join(basepath, path))
        listdir.sort()
        if len(listdir) == 0:
            self.report.pushEmpty(path)
        for f in listdir:
            filepath = unicode(os.path.join(path, f))
            if os.path.isdir(os.path.join(basepath, filepath)):
                out[f] = self.createTree(basepath, filepath)
            else:
                if self.checkExtension(filepath):
                    self.pushDB(filepath)
                    out[f] = True
                else:
                    out[f] = False
        return out

    def checkExtension(self, path):
        ext = os.path.splitext(path)[1].lower()[1:]
        if ext not in options['audio-ext']:
            self.report.pushExtension(path, ext)
            return False
        return True

    def checkDepth(self, path):
        if len(path.split('/')) != len(self.scheme_fields):
            self.report.pushDepth(path)
            return False
        return True

    def checkFields(self, path, fields):
        for req in self.required_fields:
            if not req in fields:
                self.report.pushFields(path, fields)
                if options['manual-fix']:
                    path = self.changeMove(path, 'Please, change the path according to scheme "%s":' % options['scheme'])
                return False, path
        return True, path

    def changeMove(self, path_from, msg = 'You need to change value'):
        out = path_from
        readline.set_startup_hook(lambda: readline.insert_text(path_from))

        log('REQUEST', msg)
        try:
            out = raw_input('> ')
        finally:
            readline.set_startup_hook()

        path_from = os.path.join(self.treepath, path_from)
        path_to = os.path.join(self.treepath, out)

        log('MOVE', 'Moving file "%s" to "%s"...' % (path_from, path_to))
        try:
            dirs = os.path.dirname(path_to)
            if not os.path.isdir(dirs):
                os.makedirs(dirs)
            os.rename(path_from, path_to)
            log('MOVE', '   done')
        except OSError as e:
            log('MOVE', '   failed: %s' % e.strerror)

        return out

    def parse(self, path):
        out = {}
        while True:
            out.clear()
            splitted = os.path.splitext(path)[0].split('/')
            for level, part in enumerate(splitted):
                matched = re.match(self.scheme_re[level], part, re.UNICODE)
                if matched:
                    for mlevel, match in enumerate(matched.groups()):
                        out[self.scheme_fields[level][mlevel]] = match
            result, path = self.checkFields(path, out.keys())
            if not result and not options['manual-fix']:
                return False
            if result or not options['manual-fix']:
                break
        return out

# Request artist id: http://musicbrainz.org/ws/2/artist/?query=artist:Ария&fmt=json
# Request releases for id: http://musicbrainz.org/ws/2/artist/1f36a3a2-9687-4819-ac55-54d7ff0b8b88?inc=releases&fmt=json

rmc = RMusicCheck()
rmc.start()
