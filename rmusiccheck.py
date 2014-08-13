#!/usr/bin/python
'''rMusicCheck 0.1

Author:      Rabit <home@rabits.org>
License:     GPL v3
Description: Script will check your local music database, verify artists & albums and list new albums by musicbrainz database
Required:    

Usage:
  $ ./rmusiccheck.py --help
'''

from sys import stderr, stdout, exit as sysexit
import os, time, urllib2, base64, urlparse

from optparse import OptionParser
import ConfigParser

if os.geteuid() == 0:
    stderr.write("ERROR: rMusicCheck is running by the root user, but this is really dangerous! Please use unprivileged user.\n")
    sysexit()

def exampleini(option, opt, value, parser):
    print '[rmc]'
    for key in parser.option_list:
        if None not in [key.dest, key.type] and key.dest != 'config-file':
            print '%s: %s' % (key.dest, key.default)
    sysexit()

# Parsing command line options
parser = OptionParser(usage='%prog [options]', version=__doc__.split('\n', 1)[0])
parser.add_option('-p', '--playlist', type='string', dest='playlist', metavar='DIR',
        default=None, help='Your main music directory (required)')
parser.add_option('-o', '--other', type='string', dest='other', metavar='DIR',
        default=None, help='Other directory with non-playlist music [%default]')
parser.add_option('-u', '--url-db', type='string', dest='url-db', metavar='URL',
        default='http://musicbrainz.org/ws/2', help='Musicbrainz api url [%default]')
parser.add_option('-d', '--database', type='string', dest='database', metavar='DIR',
        default='${HOME}/.local/share/rmusiccheck', help='Your local database directory ["%default"]')
parser.add_option('-p', '--path-parse', type='string', dest='path-parse', metavar='PATH',
        default='{style}/{artist}/[{year}] {album}/{track_no} - {track_name}', help='Your local database directory ["%default"]')
parser.add_option('-c', '--config-file', type='string', dest='config-file', metavar='FILE',
        default=None, help='Get configuration from ini file (replaced by command line parameters) [%default]')
parser.add_option('-e', '--config-example', action='callback', callback=exampleini,
        default=None, help='print example ini config file to stdout')
parser.add_option('-l', '--log-file', type='string', dest='log-file', metavar='FILE',
        default=None, help='Copy log output to file [%default]')
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

if options['playlist'] == None:
    parser.error('Unable to get playlist directory from playlist option (= None)')
elif not os.path.isdir(options['playlist']):
    parser.error('Playlist folder "%s" is not exists' % options['playlist'])

if options['other'] != None and not os.path.isdir(options['playlist']):
    parser.error('Other folder "%s" is not exists' % options['other'])

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
        self.path_parse = []

    def start(self):
        log('DEBUG', 'Process starting...')
        print os.listdir(options['playlist'])

rmc = RMusicCheck()
rmc.start()
