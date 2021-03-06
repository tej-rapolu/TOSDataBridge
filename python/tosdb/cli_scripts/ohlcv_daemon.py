# Copyright (C) 2014 Jonathon Ogden   < jeog.dev@gmail.com >
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#   See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License,
#   'LICENSE.txt', along with this program.  If not, see 
#   <http://www.gnu.org/licenses/>.


import tosdb 
from tosdb.intervalize.ohlc import TOSDB_OpenHighLowCloseIntervals as OHLCIntervals, \
                                   TOSDB_CloseIntervals as CIntervals

from tosdb.cli_scripts.daemon import Daemon as _Daemon
from tosdb.cli_scripts import _ohlcv_callbacks

from argparse import ArgumentParser as _ArgumentParser
from time import localtime as _localtime, strftime as _strftime, sleep as _sleep
from os.path import realpath as _path
from sys import stderr as _stderr

AINIT_TIMEOUT = 5000
BLOCK_SIZE = 1000
    

class MyDaemon(_Daemon):
    def __init__(self, addr, auth, outdir, pidfile, errorfile, interval, itype, symbols):
        _Daemon.__init__(self, pidfile, stderr = errorfile)
        self._addr = addr    
        self._auth = auth
        self._outdir = _path(outdir)
        self._interval = interval
        self._has_vol = 'V' in itype
        self._is_ohlc = 'OHLC' in itype
        self._symbols = symbols   
        self._iobj = None     
        # date prefix for filename          
        dprfx = _strftime("%Y%m%d", _localtime())
        # generate paths from filenames
        self._paths = {s.upper() : (_path(self._outdir) + '/' + dprfx + '_' \
                                   + s.replace('/','-S-').replace('$','-D-').replace('.','-P-') \
                                   + '_' + itype + '_' + str(self._interval) + 'sec.tosdb') \
                                     for s in self._symbols}
        # create callback object
        if self._has_vol:            
            self._callback = _ohlcv_callbacks._Matcher('ohlc' if self._is_ohlc else 'c', self._write)
        else:
            l = (lambda o: str((o.o, o.h, o.l, o.c))) if self._is_ohlc else (lambda o: str(o.c))
            self._callback = _ohlcv_callbacks._Basic(l, self._write)       
        

    def run(self):
        # create block
        blk = tosdb.VTOSDB_ThreadSafeDataBlock(self._addr, self._auth, BLOCK_SIZE, date_time=True)
        blk.add_items(*(self._symbols))
        blk.add_topics('last')
        if self._has_vol:
            blk.add_topics('volume') 
           
        # create interval object
        IObj = OHLCIntervals if self._is_ohlc else CIntervals
        self._iobj = IObj(blk, self._interval, interval_cb=self._callback.callback)
        try:
            while self._iobj.running():
                _sleep(1)
        except:
            self._iobj.stop()
        finally:
            blk.close()            
        

    def _write(self, item, s):
        with open(self._paths[item], 'a') as f:
            f.write(s)
      

if __name__ == '__main__':
    parser = _ArgumentParser() 
    parser.add_argument('addr', type=str, 
                        help = 'address of the host system "address port"')
    parser.add_argument('--root', help='root directory to search for the library (on host)')
    parser.add_argument('--path', help='the exact path of the library (on host)')
    parser.add_argument('--auth', help='password to use if authentication required')
    parser.add_argument('outdir', type=str, help = 'directory to output data to')
    parser.add_argument('pidfile', type=str, help = 'path of pid file')
    parser.add_argument('errorfile', type=str, help = 'path of error file')
    parser.add_argument('interval', type=int, help="interval size in seconds")
    parser.add_argument('--ohlc', action="store_true", 
                        help="use open/high/low/close instead of close")
    parser.add_argument('--vol', action="store_true", help="use volume")
    parser.add_argument('symbols', nargs='*', help="symbols to pull")
    args = parser.parse_args()

    addr_parts = args.addr.split(' ')
    addr = (addr_parts[0],int(addr_parts[1]))
    
    if args.ohlc:
        itype = 'OHLCV' if args.vol else 'OHLC'
    else:
        itype = 'CV' if args.vol else 'C'

    if not args.path and not args.root:
        print("need --root or --path argument", file=_stderr)
        exit(1)

    # connect              
    tosdb.admin_init(addr, password=args.auth, timeout=AINIT_TIMEOUT)   
    tosdb.vinit(args.path, args.root)
    
    MyDaemon(addr, args.auth, args.outdir, args.pidfile, args.errorfile, 
             args.interval, itype, args.symbols).start()




