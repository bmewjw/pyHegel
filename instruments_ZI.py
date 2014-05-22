# -*- coding: utf-8 -*-
# vim: set autoindent shiftwidth=4 softtabstop=4 expandtab:

import numpy as np
import zhinst.ziPython as zi
import zhinst.utils as ziu

from instruments_base import BaseInstrument,\
                            BaseDevice, scpiDevice, InvalidAutoArgument,\
                            MemoryDevice, ReadvalDev,\
                            ChoiceBase, _general_check,\
                            ChoiceStrings, ChoiceMultiple, ChoiceMultipleDep, Dict_SubDevice,\
                            _decode_block_base, make_choice_list,\
                            sleep, locked_calling, ProxyMethod
from instruments_base import ChoiceIndex as _ChoiceIndex
from instruments_logical import FunctionDevice
from scipy.special import gamma

class ChoiceIndex(_ChoiceIndex):
    def __call__(self, input_val):
        return self[input_val]
    def tostr(self, input_choice):
        return self.index(input_choice)

def _tostr_helper(val, t):
    # This function converts from pyHegel val to ZI val (on set/write)
    if t == None:
        return val
    if t == bool:
        return int(val)
    if t == float:
        return float(val)
    if t == int:
        return int(val)
    if type(t) == type and issubclass(t, basestring):
        return t(val)
    return t.tostr(val)

def _fromstr_helper(valstr, t):
    # This function converts from ZI val to pyHegel (on get/ask)
    if t == None:
        return valstr
    if t == bool:
        return bool(valstr)
    if t == float:
        return float(valstr)
    if t == int:
        return int(valstr)
    if type(t) == type and issubclass(t, basestring):
        return t(valstr)
    return t(valstr)



class ziDev(scpiDevice):
    _autoset_val_str = ''
    def __init__(self, setstr=None, getstr=None, autoget=True, str_type=None, insert_dev=True,
                 input_sel='auto', input_repeat=None, input_type='auto', input_src='main', **kwarg):
        """
        input_sel can be None: then it returns the whole thing
                    otherwise it is the index to use
                    When auto, it is None for input_src='main' and 0 otherwise
        input_repeat is an iterable that will be passed to set/getstr
                     as rpt_i
        The _tostr and _fromstr converter no longer need to convert to and from
        str, but to and from the device representation
        insert_dev when True, inserts '/{dev}/' to the entry if input_src=='main'

        str_type available (pyHegel, zi):
                  None (no conversion)
                  bool (bool, 'int')
                  float(float, 'double')
                  int(int, 'int')
                  str(str, 'byte')
                  unicode(unicode, 'byte')

        if ask_write_options is given, it is used as is, otherwise:
         input_type can be None, 'auto', 'int', 'double', 'byte'
              and for getstr only it can also be: 'dio', 'sample', 'dict'
             'auto' will select according to str_type unless input_src is not
              'main' in which case it will be None
           it is used as the t value for ask_write_opt options.
         input_src selects the source of the info. It can be
             'main', 'sweep', 'record' or 'zoomFFT'
        """
        if input_sel == 'auto':
            if input_src == 'main':
                input_sel = None
            else:
                input_sel = 0
        self._input_sel = input_sel
        self._input_repeat = input_repeat
        ask_write_opt = kwarg.pop('ask_write_opt', None)
        if ask_write_opt == None:
            t = input_type
            if t == 'auto':
                if input_src == 'main':
                    t = {None:None, bool:'int', float:'double', int:'int', str:'byte', unicode:'byte'}[str_type]
                else:
                    t = None
            ask_write_opt = dict(t=t, src=input_src)
        kwarg.update(ask_write_opt=ask_write_opt)
        if autoget and setstr != None:
            getstr = setstr
        insert_dev_pre = '/{{dev}}/'
        if insert_dev and input_src=='main':
            if getstr:
                getstr = insert_dev_pre+getstr
            if setstr:
                setstr = insert_dev_pre+setstr
        super(ziDev, self).__init__(setstr, getstr, str_type=str_type, **kwarg)
    def _tostr(self, val):
        # This function converts from val to a str for the command
        t = self.type
        return _tostr_helper(val, t)
    def _fromstr(self, valstr):
        # This function converts from the query result to a value
        t = self.type
        return _fromstr_helper(valstr, t)
    def _apply_sel(self, val):
        if self._input_sel != None:
            return val[self._input_sel]
        return val
    def _setdev(self, val, **kwarg):
        if self._setdev_p == None:
            raise NotImplementedError, self.perror('This device does not handle _setdev')
        options = self._combine_options(**kwarg)
        command = self._setdev_p
        repeat = self._input_repeat
        if repeat == None:
            repeat = [1]
            val = [val]
        for i, rpt_i in enumerate(repeat):
            options['rpt_i'] = rpt_i
            cmd = command.format(**options)
            v = self._tostr(val[i])
            self.instr.write(cmd, v, **self._ask_write_opt)
    def _getdev(self, **kwarg):
        if self._getdev_p == None:
            raise NotImplementedError, self.perror('This device does not handle _getdev')
        try:
            options = self._combine_options(**kwarg)
        except InvalidAutoArgument:
            self.setcache(None)
            raise
        command = self._getdev_p
        ret = []
        repeat = self._input_repeat
        if repeat == None:
            repeat = [1]
        for i in repeat:
            options['rpt_i'] = i
            cmd = command.format(**options)
            reti = self.instr.ask(cmd, **self._ask_write_opt)
            reti = self._apply_sel(reti)
            reti = self._fromstr(reti)
            ret.append(reti)
        if self._input_repeat == None:
            return ret[0]
        return ret



# sweeper structure
#  sweep/averaging/sample
#  sweep/averaging/tc
#  sweep/bandwidth
#  sweep/bandwidthcontrol
#  sweep/clearhistory
#  sweep/device
#  sweep/endless
#  sweep/fileformat
#  sweep/filename
#  sweep/gridnode
#  sweep/historylength
#  sweep/loopcount
#  sweep/phaseunwrap
#  sweep/samplecount
#  sweep/scan
#  sweep/settling/tc
#  sweep/settling/time
#  sweep/start
#  sweep/stop
#  sweep/xmapping

# record structure
#  trigger/0/bandwidth
#  trigger/0/bitmask
#  trigger/0/bits
#  trigger/0/count
#  trigger/0/delay
#  trigger/0/duration
#  trigger/0/edge
#  trigger/0/findlevel
#  trigger/0/highlevel
#  trigger/0/holdoff/count
#  trigger/0/holdoff/time
#  trigger/0/hwtrigsource (new in 13.10)
#  trigger/0/lowlevel
#  trigger/0/path
#  trigger/0/pulse/max
#  trigger/0/pulse/min
#  trigger/0/retrigger
#  trigger/0/source
#  trigger/0/type
#  trigger/buffersize
#  trigger/clearhistory
#  trigger/device
#  trigger/endless
#  trigger/filename
#  trigger/forcetrigger (new in 13.10)
#  trigger/historylength
#  trigger/triggered

# zoomFFT structure
#  zoomFFT/absolute
#  zoomFFT/bit
#  zoomFFT/device
#  zoomFFT/endless
#  zoomFFT/loopcount
#  zoomFFT/mode
#  zoomFFT/overlap
#  zoomFFT/settling/tc
#  zoomFFT/settling/time
#  zoomFFT/window  (new in 13.10)

#######################################################
##    Zurich Instruments UHF (600 MHz, 1.8 GS/s lock-in amplifier)
#######################################################

class zurich_UHF(BaseInstrument):
    """
    This instrument controls a Zurich Instrument UHF lock-in amplifier
     To use this instrument, the most useful devices are probably:
       fetch
       readval
    """
    def __init__(self, zi_dev=None, host='localhost', port=8004):
        """
        By default will use the first zi device available.
        """
        # The SRQ for this intrument does not work
        # as of version 7.2.1.0
        timeout = 500 #ms
        # Note that deleting the _zi_daq frees up all the memory of
        #  sweep, record, .... and renders them unusable
        # To free up the memory of sweep, call sweep.clear() before deleting
        # (or replacing) it.
        # TODO get version 4 to work (it adds timestamps to many commands
        #                             so dictionnary get like in idn need to change)
        APIlevel = 1 # 1 or 4 for version 13.10
        self._zi_daq = zi.ziDAQServer(host, port, APIlevel)
        self._zi_record = self._zi_daq.record(10, timeout) # 10s length
        self._zi_sweep = self._zi_daq.sweep(timeout)
        self._zi_zoomFFT = self._zi_daq.zoomFFT(timeout)
        self._zi_devs = ziu.devices(self._zi_daq)
        self._zi_sep = '/'
        if zi_dev == None:
            try:
                zi_dev = self._zi_devs[0]
                print 'Using zi device ', zi_dev
            except IndexError:
                raise ValueError, 'No devices are available'
        elif zi_dev not in self._zi_devs:
            raise ValueError, 'Device "%s" is not available'%zi_dev
        self._zi_dev = zi_dev
        super(zurich_UHF, self).__init__()
    def _tc_to_enbw_3dB(self, tc=None, order=None, enbw=True):
        """
        When enbw=True, uses the formula for the equivalent noise bandwidth
        When enbw=False, uses the formula for the 3dB point.
        When either or both tc and order are None, the cached values are used
        for the current_demod channel.
        If you enter the bandwith frequencyfor tc, a time constant is returned.
        If you enter a timeconstant for tc, a bandwidth frequency is returned.
        """
        if order == None:
            order = self.demod_order.getcache()
        if tc == None:
            tc = self.demod_tc.getcache()
        if enbw:
            return (1./(2*np.pi*tc)) * np.sqrt(np.pi)*gamma(order-0.5)/(2*gamma(order))
        else:
            return np.sqrt(2.**(1./order) -1) / (2*np.pi*tc)
    def init(self, full=False):
        #self.write('Comm_HeaDeR OFF') #can be OFF, SHORT, LONG. OFF removes command echo and units
        super(zurich_UHF, self).init(full=full)
        if full:
            tc_to_bw = ProxyMethod(self._tc_to_enbw_3dB)
            func1 = lambda v: tc_to_bw(v, enbw=False)
            self.demod_bw3db = FunctionDevice(self.demod_tc, func1, func1)
            func2 = lambda v: tc_to_bw(v)
            self.demod_enbw = FunctionDevice(self.demod_tc, func2, func2)
    def _current_config(self, dev_obj=None, options={}):
        return self._conf_helper('memory_size', 'trig_coupling', options)
    def _conv_command(self, comm):
        """
        comm can be a string, a list of strings (to concatenate together)
        or a list of tuples (command, value)
        and it replaces {dev} with the current device
        """
        sep = self._zi_sep
        if isinstance(comm, (list, tuple)):
            if isinstance(comm[0], (list, tuple)):
                comm = [(c.format(dev=self._zi_dev), v) for c,v in comm]
            else: # a list of strings to join using sep
                comm = sep+ sep.join(comm)
        else: # a single command
            comm = comm.format(dev=self._zi_dev)
        return comm
    def _select_src(self, src):
        """
        available sources are:
            'main', 'sweep', 'record' and 'zoomFFT'
        returns object and prepend string
        """
        if src == 'main':
            ret = self._zi_daq
            pre = ''
        elif src == 'sweep':
            ret = self._zi_sweep
            pre = 'sweep'
        elif src == 'record':
            ret = self._zi_record
            pre = 'trigger'
        elif src == 'zoomFFT':
            ret = self._zi_zoomFFT
            pre = 'zoomFFT'
        else:
            raise ValueError, 'Invalid src'
        if ret == None:
            raise ValueError, 'Requested src is not available'
        return ret, pre
    def list_nodes(self, base='/', src='main', recursive=True, absolute=True, leafs_only=True, settings_only=False):
        """
        base = '/' unless src is not 'main' in which case
        it will be '/*'
        see _select_src for available src
        """
        base = self._conv_command(base)
        flags = 0
        if base == '/' and src != 'main':
            base = '/*'
        if recursive:
            flags |= 1
        if absolute:
            flags |= (1<<1)
        if leafs_only:
            flags |= (1<<2)
        if settings_only:
            flags |= (1<<3)
        src, pre = self._select_src(src)
        return src.listNodes(pre+base, flags)
    def _subscribe(self, base='/{dev}/demods/*/sample', src='main'):
        base = self._conv_command(base)
        src, pre = self._select_src(src)
        sub = getattr(src, 'subscribe')
        sub(base)
    def _unsubscribe(self, base='/{dev}/demods/*/sample', src='main'):
        base = self._conv_command(base)
        src, pre = self._select_src(src)
        unsub = getattr(src, 'unsubscribe')
        unsub(base)
    def echo_dev(self):
        """
        It is suppose to wait until all buffers are flushed.
        """
        self._zi_daq.echoDevice(self._zi_dev)
    def flush(self):
        """
        Flush data in socket connection and API buffers.
        Use between subscribe and poll.
        """
        self._zi_daq.flush()
    def _flat_dict(self, in_dict):
        """
        this converts the get(str,False) or get for
        other than main object in a flat dict
        i.e.
          {'a':{'0':{'c':4, 'd':5}}}
            into
          {'a/0/c':4, 'a/0/d':5}
        """
        sep = self._zi_sep
        out_dict = {}
        for k,v in in_dict.iteritems():
            if isinstance(v, dict):
                v = self._flat_dict(v)
                for ks, vs in v.iteritems():
                    out_dict[k+sep+ks] = vs
            else:
                out_dict[k] = v
        return out_dict
    @locked_calling
    def read(self, timeout_ms=0):
        """
        read currently available susbscribed data.
        """
        # timeout value of -1 disables it. poll becomes completely blocking
        # with a non negative timeout poll is blocking for the timeout duration
        # poll and pollevent use the timeout in the same way
        #  poll also has a duration.
        #   it seems to repeat pollEvent as long as duration is not finished
        #   so the duration can be rounded up by timeout if no data is available.
        return self._zi_daq.pollEvent(timeout_ms)
    @locked_calling
    def write(self, command, val=None, src='main', t=None, sync=True):
        """
         use like:
             obj.write('/dev2021/sigins/0/on', 1, t='int')
                t can be 'byte', 'double', 'int'
             obj.write([('/dev2021/sigins/0/on', 1), ('/dev2021/sigins/1/on', 0)])
             obj.write('loopcount', 2, src='zoomFFT')
                the 'sweepFFT/' is automatically inserted
        see _select_src for available src
            it only affects t==None
            for src not 'main', the only choice is
            t==None, and to give a single val.
        sync is for 'double' or 'int' and is to use the sync interface

        You can replace /dev2021/ by /{dev}/
        """
        command = self._conv_command(command)
        if t=='byte':
            self._zi_daq.setByte(command, val)
        elif t=='double':
            if sync:
                self._zi_daq.syncSetDouble(command, val)
            else:
                self._zi_daq.setDouble(command, val)
        elif t=='int':
            if sync:
                self._zi_daq.syncSetInt(command, val)
            else:
                self._zi_daq.setInt(command, val)
        elif t==None:
            src, pre = self._select_src(src)
            if pre == '':
                src.set(command)
            else:
                src.set(pre+'/'+command, val)
        else:
            raise ValueError, 'Invalid value for t=%r'%t
    @locked_calling
    def ask(self, question, src='main', t=None):
        """
        use like:
            obj.ask('/dev2021/sigins/0/on', t='int')
              t can be 'byte', 'double', 'int', 'sample' or 'dict'
                for demods sample data, only t='sample' works
              In which case only one value can be asked for (not * or partial tree)
              The default is to return the value of the only item
              of the dict, unless there is more than one item,
              then a dict is return
            obj.ask('/dev2021/sigins')
            obj.ask('/dev2021/sig*')
            obj.ask('averaging/tc', src='sweep')
            obj.ask('*', src='sweep')
            obj.ask('/dev2021/demods/0/sample', t='sample')
            obj.ask('/dev2021/dios/0/input', t='dio')
        """
        question = self._conv_command(question)
        if t=='byte':
            return self._zi_daq.getByte(question)
        elif t=='double':
            return self._zi_daq.getDouble(question)
        elif t=='int':
            return self._zi_daq.getInt(question)
        elif t=='sample':
            return self._zi_daq.getSample(question)
        elif t=='dio':
            return self._zi_daq.getDIO(question)
        elif t==None or t=='dict':
            src, pre = self._select_src(src)
            if pre == '':
                ret = self._flat_dict(src.get(question))
                #ret = src.get(question, True) # True makes it flat
            else:
                ret = self._flat_dict(src.get(pre+'/'+question))
            if t == 'dict' or len(ret) != 1:
                return ret
            return ret.values()[0]
        else:
            raise ValueError, 'Invalid value for t=%r'%t
    def timestamp_to_s(self, timestamp):
        """
        Using a timestamp from the instrument, returns
        the number of seconds since the instrument turn on.
        """
        # The timestamp just seems to be the counter of the 1.8 GHz clock
        return timestamp/self.clockbase.getcache()
    def idn(self):
        name = 'Zurich Instrument'
        python_ver = self._zi_daq.version()
        python_rev = str(self._zi_daq.revision())
        server_ver = self.ask('/zi/about/version')[0]
        #server_rev = self.ask('/zi/about/revision')[0]
        server_rev = self.ask('/zi/about/revision', t='int')
        server_fw_rev = str(self.ask('/zi/about/fwrevision')[0])
        system_devtype = self.ask('/{dev}/features/devtype')[0]
        system_serial = self.ask('/{dev}/features/serial')[0]
        #system_code = self.ask('/{dev}/features/code')[0] # not available in vs 13.10 TODO fix that
        system_options = self.ask('/{dev}/features/options')[0]
        system_analog_board_rev = self.ask('/{dev}/system/analogboardrevision')[0]
        system_digital_board_rev = self.ask('/{dev}/system/digitalboardrevision')[0]
        system_fpga_rev = str(self.ask('/{dev}/system/fpgarevision')[0])
        system_fw_rev = str(self.ask('/{dev}/system/fwrevision')[0])
        #return '{name} {system_devtype} #{system_serial} (analog/digital/fpga/fw_rev:{system_analog_board_rev}/{system_digital_board_rev}/{system_fpga_rev}/{system_fw_rev}, code:{system_code}, opt:{system_options}  [server {server_ver}-{server_rev} fw:{server_fw_rev}] [python {python_ver}-{python_rev}])'.format(
        return '{name} {system_devtype} #{system_serial} (analog/digital/fpga/fw_rev:{system_analog_board_rev}/{system_digital_board_rev}/{system_fpga_rev}/{system_fw_rev}, opt:{system_options}  [server {server_ver}-{server_rev} fw:{server_fw_rev}] [python {python_ver}-{python_rev}])'.format(
             name=name, python_ver=python_ver, python_rev=python_rev,
             server_ver=server_ver, server_rev=server_rev, server_fw_rev=server_fw_rev,
             system_devtype=system_devtype, system_serial=system_serial,
             #system_code=system_code, system_options=system_options,
             system_options=system_options,
             system_analog_board_rev=system_analog_board_rev, system_digital_board_rev=system_digital_board_rev,
             system_fpga_rev=system_fpga_rev, system_fw_rev=system_fw_rev)

    def _fetch_ch_helper(self, ch):
        if ch==None:
            ch = self.find_all_active_channels()
        if not isinstance(ch, (list)):
            ch = [ch]
        return ch
    def _fetch_getformat(self, **kwarg):
        xaxis = kwarg.get('xaxis', True)
        ch = kwarg.get('ch', None)
        ch = self._fetch_ch_helper(ch)
        if xaxis:
            multi = ['time(s)']
        else:
            multi = []
        for c in ch:
            multi.append('ch_%s'%c)
        fmt = self.fetch._format
        multi = tuple(multi)
        fmt.update(multi=multi, graph=[], xaxis=xaxis)
        return BaseDevice.getformat(self.fetch, **kwarg)
    def _fetch_getdev(self, ch=None, xaxis=True, raw=False):
        """
           Options available: ch, xaxis
            -ch:    a single value or a list of values for the channels to capture
                    a value of None selects all the active ones from C1 to C4.
                    If obtaining more than one channels, they should have the same xaxis
            -xaxis: Set to True (default) to return the timebase as the first colum
            -raw: Set to true to return the vertical values as raw integers, otherwise
                  they are converted floats
        """
        # TODO handle complex ffts...
        ch = self._fetch_ch_helper(ch)
        ret = []
        first = True
        for c in ch:
            data = self.data.get(ch=c)
            header = data.header
            if xaxis and first:
                first = False
                ret = [header.HORIZ_INTERVAL*np.arange(header.WAVE_ARRAY_COUNT) + header.HORIZ_OFFSET]
            if raw:
                y = data.data1
            else:
                y = data.data1*header.VERTICAL_GAIN - header.VERTICAL_OFFSET
            ret.append(y)
        ret = np.asarray(ret)
        if ret.shape[0]==1:
            ret=ret[0]
        return ret
    def _create_devs(self):
        self.clockbase = ziDev(getstr='clockbase', str_type=float)
        self.fpga_core_temp = ziDev(getstr='stats/physical/fpga/temp', str_type=float)
        self.calib_required = ziDev(getstr='system/calib/required', str_type=bool)
        self.mac_addr = ziDev('system/nics/0/mac/{rpt_i}', input_repeat=range(6), str_type=int)
        self.current_demod = MemoryDevice(0, choices=range(8))
        self.current_osc = MemoryDevice(0, choices=range(2))
        self.current_sigins = MemoryDevice(0, choices=range(2))
        self.current_sigouts = MemoryDevice(0, choices=range(2))
        def ziDev_ch_gen(ch, *arg, **kwarg):
            options = kwarg.pop('options', {}).copy()
            options.update(ch=ch)
            app = kwarg.pop('options_apply', ['ch'])
            options_conv = kwarg.pop('options_conv', {}).copy()
            options_conv.update(ch=lambda base_val, conv_val: base_val)
            kwarg.update(options=options, options_apply=app, options_conv=options_conv)
            return ziDev(*arg, **kwarg)
        ziDev_ch_demod = lambda *arg, **kwarg: ziDev_ch_gen(self.current_demod, *arg, **kwarg)
        ziDev_ch_osc = lambda *arg, **kwarg: ziDev_ch_gen(self.current_osc, *arg, **kwarg)
        ziDev_ch_sigins = lambda *arg, **kwarg: ziDev_ch_gen(self.current_sigins, *arg, **kwarg)
        ziDev_ch_sigouts = lambda *arg, **kwarg: ziDev_ch_gen(self.current_sigouts, *arg, **kwarg)
        self.demod_freq = ziDev_ch_demod(getstr='demods/{ch}/freq', str_type=float)
        self.demod_harm = ziDev_ch_demod('demods/{ch}/harmonic', str_type=int)
        self.demod_en = ziDev_ch_demod('demods/{ch}/enable', str_type=bool)
        self.demod_sinc_en = ziDev_ch_demod('demods/{ch}/sinc', str_type=bool)
        self.demod_bypass_en = ziDev_ch_demod('demods/{ch}/bypass', str_type=bool, doc="Don't know what this does.")
        self.demod_osc_src = ziDev_ch_demod(getstr='demods/{ch}/oscselect', str_type=int, choices=[0,1])
        self.demod_adc_src = ziDev_ch_demod('demods/{ch}/adcselect', str_type=int, choices=range(13))
        self.demod_rate = ziDev_ch_demod('demods/{ch}/rate', str_type=float, setget=True, doc="""
            The rate are power of 2 fractions of the base sampling rate.
            With the base of 1.8 GS/s, the weeb interface has a max rate of
              1.8e9/2**7 = 14.1 MS/s
            and a min rate of
              1.8e9/2**30 = 1.68 S/s
            The recommended rate is 7-10 higher rate than filter bandwidth for
            sufficient antialiasing suppression.
        """)
        self.demod_tc = ziDev_ch_demod('demods/{ch}/timeconstant', str_type=float, setget=True)
        self.demod_order = ziDev_ch_demod('demods/{ch}/order', str_type=int, choices=range(1,9))
        self.demod_phase = ziDev_ch_demod('demods/{ch}/phaseshift', str_type=float, setget=True)
        self.demod_trigger = ziDev_ch_demod('demods/{ch}/trigger', str_type=int)
        self.demod_data = ziDev_ch_demod(getstr='demods/{ch}/sample', input_type='sample', doc='It will wait for the next available samples (depends on rate). X and Y are in RMS')
        self.osc_freq = ziDev_ch_osc('oscs/{ch}/freq', str_type=float, setget=True)
        # TODO figure out what sigins/{ch}/bw does
        self.sigins_ac_en = ziDev_ch_sigins('sigins/{ch}/ac', str_type=bool)
        self.sigins_50ohm_en = ziDev_ch_sigins('sigins/{ch}/imp50', str_type=bool)
        self.sigins_en = ziDev_ch_sigins('sigins/{ch}/on', str_type=bool)
        range_lst = np.concatenate( (np.linspace(0.01, .1, 10), np.linspace(0.2, 1.5, 14)))
        range_lst = [float(v) for v in np.around(range_lst, 3)]
        self.sigins_range = ziDev_ch_sigins('sigins/{ch}/range', str_type=float, setget=True, choices=range_lst, doc='The voltage range amplitude A (the input needs to be between -A and +A. There is a attenuator for A<= 0.1')
        self.sigouts_en = ziDev_ch_sigouts('sigouts/{ch}/on', str_type=bool)
        self.sigouts_offset = ziDev_ch_sigouts('sigouts/{ch}/offset', str_type=float, setget=True)
        self.sigouts_range = ziDev_ch_sigouts('sigouts/{ch}/range', str_type=float, setget=True, choices=[0.15, 1.5])
        self.sigouts_autorange_en = ziDev_ch_sigouts('sigouts/{ch}/autorange', str_type=bool)
        self.sigouts_output_clipped = ziDev_ch_sigouts(getstr='sigouts/{ch}/over', str_type=bool)
        # There is also amplitudes/7, enables/3, enables/7, syncfallings/3 and /7, syncrisings/3 and /7
        #   TODO find out what those are
        self.sigouts_ampl_Vp = ziDev_ch_sigouts(getstr='sigouts/{ch}/amplitudes/3', str_type=bool, doc='Amplitude A of sin wave (it goes from -A to +A without an offset')
        # TODO: triggers, SYSTEM(/EXTCLK), EXTREFS, status stats
        #       conn, inputpwas, outputpwas
        #       auxins/0/sample, auxins/0/averaging
        #       auxouts/0-4, dios/0, scopes/0
        self.sweep_device = ziDev('device', str_type=str, input_src='sweep')
        self.sweep_x_start = ziDev('start', str_type=float, input_src='sweep')
        self.sweep_x_stop = ziDev('stop', str_type=float, input_src='sweep')
        self.sweep_x_count = ziDev('samplecount', str_type=int, input_src='sweep')
        self.sweep_x_src_node = ziDev('gridnode', str_type=str, input_src='sweep')
        self.sweep_x_log = ziDev('xmapping', str_type=bool, input_src='sweep')
        self.sweep_loop_count = ziDev('loopcount', str_type=int, input_src='sweep')
        self.sweep_endless_loop_en = ziDev('endless', str_type=bool, input_src='sweep')
        #auto_bw_ch = ChoiceIndex(['auto', 'fixed', 'manual'])
        #self.sweep_auto_bw_mode = ziDev('bandwidthcontrol', choices=auto_bw_ch, input_src='sweep')
        self.sweep_auto_bw_en = ziDev('bandwidthcontrol', str_type=bool, input_src='sweep')
        self.sweep_auto_bw_fixed = ziDev('bandwidth', str_type=float, input_src='sweep')
        self.sweep_settling_time_s = ziDev('settling/time', str_type=float, input_src='sweep')
        self.sweep_settling_n_tc = ziDev('settling/tc', str_type=float, input_src='sweep')
        self.sweep_averaging_count = ziDev('averaging/sample', str_type=int, input_src='sweep')
        #self.sweep_averaging_n_tc = ziDev('averaging/tc', str_type=float, choices=[0, 5, 15, 50], input_src='sweep')
        self.sweep_averaging_n_tc = ziDev('averaging/tc', str_type=float, input_src='sweep')
        sweep_mode_ch = ChoiceIndex(['sequential', 'binary', 'bidirectional'])
        self.sweep_mode = ziDev('scan', choices=sweep_mode_ch, input_src='sweep')

        self.sweep_phase_unwrap_en = ziDev('phaseunwrap', str_type=bool, input_src='sweep')
# sweeper structure
#  sweep/fileformat
#  sweep/filename
#  sweep/historylength

        #self._devwrap('fetch', autoinit=False, trig=True)
        #self.readval = ReadvalDev(self.fetch)
        # This needs to be last to complete creation
        super(zurich_UHF, self)._create_devs()
    def clear_history(self, src='sweep'):
        """
        empties the read buffer (the next read will be empty).
        also, during a sweep, it restarts all loops.
        """
        self.write('clearhistory', 1, src=src)
    def sweep_progress(self):
        return self._zi_sweep.progress()
    def is_sweep_finished(self):
        if self._zi_sweep.finished() and self.sweep_progress() == 1.:
            return True
        return False
    def sweep_start(self):
        self._zi_sweep.execute()
    def sweep_stop(self):
        self._zi_sweep.finish()
    def run_and_wait(self):
        self.sweep_start()
        while not self.is_sweep_finished():
            pass
    def sweep_data(self):
        """ Call after running a sweep """
        return self._flat_dict(self._zi_sweep.read())
    def set_sweep_mode(self, start, stop, count, logsweep=False, src='oscs/0/freq', subs='all',
                       bw='auto', loop_count=1, mode='sequential',
                       avg_count=1, avg_n_tc=0, settle_time_s=0, settle_n_tc=15):
        """
        bw can be a value (fixed mode), 'auto' or None (uses the currently set timeconstant)
           The following discussion is for version 13.06
           for auto the computed bandwidth (the one asked for, but the instruments rounds it
           to another value) is the equivalent noise bandwidth and is:
               min(df/2,  f/100**(1/n))
                 where n is order,
                 f is frequency, and df[1:] = diff(f), df[0]=df[1]
               It is also bounded by the max and min available bandwidth (time constants)
                available for the order (min tc=1.026e-7, max tc=76.35)
               The reason for df/2 is to have independent points,
               The reason for f/100*(1/n) is to kill the harmonics in a similar way.
                 The H harmonic is attenuated for order n by ~100*(H*Kn)**n,
                  where Kn is 2*pi*ENBW(tau=1, order=n)
                  hence the attenuation for the 2nd harmonic is
                    ~314 for order 1,  ~247 for 2, ~164 for 3, ..., =31.5 for 8 (no approximation, approx gave 3)
                       the formula for no approximation is sqrt(1 + (F)**2)**n
                        with F = 100**(1./n) * (H*Kn)
               Enabling sync does not seem to change anything
        mode is 'sequential', 'binary', or 'bidirectional'
          Note that 1 loopcount of bidirectionnal includes twice the count
          of points (the up and down sweep together)
        subs is the list of demods channels to subscribe to
        loop_count <= 0 turns on endless mode (infinite count, need to use finish to stop)
        subs is a list of demods channel number to subscribe to (to record in the sweep result)
              or it is 'all' to record all active channels.
              Channels are active if they are enabled and the data rate is not 0.
              If no channels are active, the sweep will not progress, it will stall.
              If an active channel is subscribed to, deactivating without changing the
              subscription will hang the sweep.
        The total settling time in seconds is max(settle_time_s, settle_n_tc*timeconstant_s)
        where timeconstant_s is the timeconstant in seconds for each frequency (can change with bw='auto').
        The total averaging time in seconds is max(avg_count/rate, avg_n_tc*timeconstant_s, 1/rate).
        (a minimum of 1 sample)
        where rate is the demod rate for that channel.
        In between points of the sweep, there can be an additiontion ~60 ms delay.

        The usual parameter for the web interface:
              they all use bw='auto', settle_time_s=0
            parameter/high: settle_n_tc=15, avg_count=1, avg_n_tc=0
            parameter/low : settle_n_tc=5,  avg_count=1, avg_n_tc=0
            avg param/high: settle_n_tc=15, avg_count=1000, avg_n_tc=15
            avg param/low : settle_n_tc=5,  avg_count=100,  avg_n_tc=5
            noise/high:     settle_n_tc=50, avg_count=1000, avg_n_tc=50
            noise/low :     settle_n_tc=15, avg_count=100,  avg_n_tc=15
        """
        # sweep/bandwidthcontrol = 0 is still enabled if sweep/bandwidth=0
        self.sweep_device.set(self._zi_dev)
        self.sweep_x_start.set(start)
        self.sweep_x_stop.set(stop)
        self.sweep_x_count.set(count)
        self.sweep_x_src_node.set(src)
        self.sweep_x_log.set(logsweep)
        self.sweep_x_log.set(logsweep)
        if bw == None:
            #self.sweep_auto_bw_mode.set('manual')
            #self.sweep_auto_bw_mode.set('fixed')
            if self.sweep_auto_bw_fixed.getcache()<=0:
                self.sweep_auto_bw_fixed.set(1)
            self.sweep_auto_bw_en.set(False)
        elif bw == 'auto':
            #self.sweep_auto_bw_mode.set('auto')
            self.sweep_auto_bw_fixed.set(0)
            self.sweep_auto_bw_en.set(True)
        else:
            #self.sweep_auto_bw_mode.set('fixed')
            self.sweep_auto_bw_fixed.set(bw)
            self.sweep_auto_bw_en.set(True)
        if loop_count <= 0:
            self.sweep_endless_loop_en.set(True)
        else:
            self.sweep_endless_loop_en.set(False)
            self.sweep_loop_count.set(loop_count)
        self.sweep_x_log.set(logsweep)
        self.sweep_mode.set(mode)
        self.sweep_averaging_count.set(avg_count)
        self.sweep_averaging_n_tc.set(avg_n_tc)
        self.sweep_settling_time_s.set(settle_time_s)
        self.sweep_settling_n_tc.set(settle_n_tc)
        for i in range(8):
            # This will remove multiple subscribes to a particular channel
            self._unsubscribe('/{dev}/demods/%i/sample'%i, src='sweep')
        # This removes subscribes to * (it is not removed by above iteration)
        self._unsubscribe('/{dev}/demods/*/sample', src='sweep')
        if subs == 'all':
            self._subscribe('/{dev}/demods/*/sample', src='sweep')
        else:
            if not isinstance(subs, (list, tuple, np.ndarray)):
                subs = [subs]
            for i in subs:
                self._subscribe('/{dev}/demods/%i/sample'%i, src='sweep')

# In the result data set:
#   available: auxin0, auxin0pwr, auxin0stddev
#              auxin1, auxin1pwr, auxin1stddev
#              bandwidth, tc (for auto they are the computed ones, the ones set to, the used one are truncated)
#              frequency, frequencystddev
#              grid
#              nexttimestamp, settimestamp (both in s, timestamps of set and first read)
#              settling  (=nexttimestamp-settimestamp)
#              timestamp (single value, in raw clock ticks: 1.8 GHz)
#              r, rpwr, rstddev
#              phase, phasestddev
#              x, xpwr, xstddev
#              y, ypwr, ystddev
# All points are in order of start-stop, even for binary.
#  however
# bandwidth is enbw (related to tc)
#  for the various stddev to not be nan, you need avg count>1
#    for i the iterations of N averages
#   base(avg): sum_i x_i/N
#   pwr: sum_i (x_i**2)/N
#   stddev: (1/N) sum_i (x_i - base)**2
#    so stddev = sqrt(pwr - base**2)
#      sould probably use 1/(N-1) instead
#  The r, rpwr and rstddev are calculated from r_i = sqrt(x_i**2 + y_i**2)
#    not from x, xpwr and xstddev



# Problems discovered:
#  get('*') is slow and does not return sample data (because it is slow?, uses polling)
#  get of subdevices does not work like get of main device (not option to flatten)
# documentation errors: pollEvent arg2 and 3, should only have 2 arg and
#                       description of arg3 is for arg2
# errors in documentation ziAPI.h
#    example description of ziAPIGetValueB talks about DIO samples...
#    as of 13.10 that is fixed since most of the documentation as been removed
# timeit zi.ask('/{dev}/stats/physical/digitalboard/temps/0', t='int')
#  100 loops, best of 3: 2.55 ms per loop
# timeit zi.ask('/{dev}/stats/physical/digitalboard/temps/0')
#  10 loops, best of 3: 250 ms per loop (for 13.06 and 100 ms for 13.10)
# This is because it uses get_as_poll
#  some are faster like '/zi' or '/{dev}/stats/cmdstream'
#
# za=instruments_ZI.ziAPI()
def _time_poll(za):
    import time
    s = '/dev2021/demods/0/sinc'
    to=time.time()
    za.get_as_poll('/dev2021/demods/0/sinc')
    done = False
    n = 0
    while not done:
        n += 1
        r=za.poll(1000)
        if r['path'].lower() == s:
            done = True
    return time.time()-to,n,r
# za.poll() # first empty the poll buffer
# timeit _time_poll(za)
# timeit print _time_poll(za)
#  This is always 100 ms (version 13.10). When subscribing to something like
#    /dev2021/demods/0/sample at 1.717 kS/s  (timeit za.poll()  returns ~25 ms)
#  polls will return more quickly but with the information from /dev2021/demods/0/sample multiples times
#  between the /dev2021/demods/0/sinc ones
#
# /dev2021/system/calib/required was not in listnodes (13.06) but is there in 13.10
#
#  tests:
# set(zi.demod_en,True, ch=0)
# set(zi.demod_rate,13.41)
# set(zi.demod_order,3)
#   get(zi.demod_tc) # 0.0938 s (1.00 enbw, 0.865 3dB bw)
#   first test settling time/average time is maximum of both n_tc and time
# zi.set_sweep_mode(10e3,10e4,10, bw=1, settle_time_s=0, settle_n_tc=0, avg_count=1)
# timeit zi.run_and_wait() # 1.78s
# zi.set_sweep_mode(10e3,10e4,10, bw=1, settle_time_s=1, settle_n_tc=0, avg_count=1)
# timeit zi.run_and_wait() # 11.5s
# zi.set_sweep_mode(10e3,10e4,10, bw=1, settle_time_s=0, settle_n_tc=5, avg_count=1)
# timeit zi.run_and_wait() # 6.25s
# zi.set_sweep_mode(10e3,10e4,10, bw=1, settle_time_s=0, settle_n_tc=0, avg_count=13)
# timeit zi.run_and_wait() # 10.8s
# zi.set_sweep_mode(10e3,10e4,10, bw=1, settle_time_s=0, settle_n_tc=0, avg_count=0, avg_n_tc=5)
# timeit zi.run_and_wait() # 5.59s
#
#  test the calculations for stddev
# zi.set_sweep_mode(10e3,10e4,10, bw=1, settle_time_s=0, settle_n_tc=0, avg_count=2)
# zi.run_and_wait()
# r=zi.sweep_data(); rr=r['dev2021/demods/0/sample'][0][0]
# sqrt(rr['ypwr']-rr['y']**2)/rr['ystddev'] # should be all 1.
#
#  test auto time constants
def _calc_bw(demod_result_dict, order=3):
    r=demod_result_dict
    f=r['grid']
    df = np.diff(f)
    df = np.append(df[0], df)
    k = 100.**(1./order)
    m =np.array([df/2, f/k])
    bw = np.min(m, axis=0)
    return bw
# zi.set_sweep_mode(10e3,10e4,10, bw='auto', settle_time_s=0, settle_n_tc=0, avg_count=1)
# zi.set_sweep_mode(10,1010,10, bw='auto', settle_time_s=0, settle_n_tc=0, avg_count=1)
# instruments_ZI._calc_bw(rr)/rr['bandwidth'] # should all be 1
#  repeat with
# zi.set_sweep_mode(10,1010,10, bw='auto', settle_time_s=0, settle_n_tc=0, avg_count=1, logsweep=True)
# set(zi.demod_sinc_en,True)
# zi.set_sweep_mode(10,1010,10, bw='auto', settle_time_s=0, settle_n_tc=0, avg_count=1) # same bandwidth calc but much slower to run
#
# find all available time constants
def _find_tc(zi, start, stop, skip_start=False, skip_stop=False):
    if skip_start:
        tc_start = start
    else:
        zi.demod_tc.set(start)
        tc_start = zi.demod_tc.getcache()
    #if tc_start<start:
    #    print 'tc<'
    #    return []
    if skip_stop:
        tc_stop = stop
    else:
        zi.demod_tc.set(stop)
        tc_stop = zi.demod_tc.getcache()
    if tc_start == tc_stop:
        print start, stop, (stop-start), tc_start, tc_stop
        return [tc_start]
    df = stop-start
    mid = start+df/2.
    zi.demod_tc.set(mid)
    tc_mid = zi.demod_tc.getcache()
    print start, stop, df, tc_start, tc_mid, tc_stop,
    if tc_start == tc_mid:
        print 'A'
        t1 = [tc_start]
        if skip_start==True and skip_stop==False:
            # previously tc_mid == tc_stop, so no other points in between
            t2 = [tc_stop]
        else:
            t2 = _find_tc(zi, mid, tc_stop, False, True)
    elif tc_mid == tc_stop:
        print 'B'
        if skip_start==False and skip_stop==True:
            # previously tc_mid == tc_start, so no other points in between
            t1 = [tc_start]
        else:
            t1 = _find_tc(zi, tc_start, mid, True, False)
        t2 = [tc_stop]
    else:
        print 'C'
        t1 = _find_tc(zi, tc_start, tc_mid, True, True)
        t2 = _find_tc(zi, tc_mid, tc_stop, True, True)
    if t1[-1] == t2[0]:
        t1 = t1[:-1]
    return t1+t2
#  for demod_order=3
#  array(instruments_ZI._find_tc(zi, 10,2000))
#    returns:  array([  9.5443716 ,  10.90785408,  12.72582912,  15.27099514,  19.08874321, 25.45165825,  38.17748642,  76.35497284])
#  array(instruments_ZI._find_tc(zi, 1e-8, 1.026e-7))
#    returns: array([  1.02592772e-07,   1.02593908e-07,   1.02595038e-07,  1.02596161e-07,   1.02597291e-07,   1.02598420e-07,  1.02599557e-07])
#  for demod_order=1
#  array(instruments_ZI._find_tc(zi, 1e-8, 1.026e-7))
#             array([  2.99000007e-08,   6.00999996e-08,   1.02592772e-07, 1.02593908e-07,   1.02595038e-07,   1.02596161e-07,  1.02597291e-07,   1.02598420e-07,   1.02599557e-07])
#  array(instruments_ZI._find_tc(zi, 10,2000))
#    returns:  array([  9.5443716 ,  10.90785408,  12.72582912,  15.27099514,  19.08874321, 25.45165825,  38.17748642,  76.35497284])
#
# From those observations the time constant is selected as:
#      numerically, the algorithm used is Vo(i+1) = (Vi + (t-1)Voi)/t
#      where t is a number express in dt (the time step for the incoming data, here 1/f = 1/1.8GHz)
#      to be easier to implement numerically (divisions are slow), lets express
#        t as N/n where N is a power of 2 (so division by N can be done with shift operators)
#      then the formula can be reexpressed as
#             Vo(i+1) = (n Vi  + (N-n) Voi)/N
#      Therefore the largest time constant is obtained with n=1
#      The max one of 76.355 s  ==> N=2**37  (N/f=76.355)
#      The top segment of time constants uses N=2**37 and n:1..4095 (4095=2**12-1)
#      After that it uses N=2**25  (N/f = 0.018641351)
# m = 2**37/1.8e9
# v=array(instruments_ZI._find_tc(zi, m/50,m/1)); len(v); m/v  # returns 50 points, numbers from 50 to 1
# v=array(instruments_ZI._find_tc(zi, m/10000,m/4050)); len(v); m/v # returns 50 points, numbers 12288(3*2**12), 8192(2*2**12) and 4097 to 4050
#                                                                   # note that 2**12 = 4096
# m2 = 2**25/1.8e9
# v=array(instruments_ZI._find_tc(zi, m2/50,m2/1)); len(v); m2/v # returns 51 points, numbers from 50 to 1 (there are 2 points around 1)
#   explore second section
# n=14; v=array(instruments_ZI._find_tc(zi, m2/(2**n+40),m2/2**n)); 2**n;len(v); np.round(m2/v)
# set zi.demod_order,1
# n=17; v=array(instruments_ZI._find_tc(zi, m2/2**n,m2/(2**n+40))); 2**n;len(v); np.round(m2/v) #25 pts from 131073 to 131112
# v=array(instruments_ZI._find_tc(zi, m2/2**25,m2/181684)); 2**n;len(v); np.round(m2/v) # 12 pts:  623457,  310172, et 181702 - 181684 en saut de 2
#  these give t=(v*f):   53.82, 108.18, 184.667, 184.669 ...
# it seems to do the time constants calculation in floats instead of double
#
# in 13.10 get('', true) fails (was returning a flat dictionnary)
#  also zhinst loads all the examples.
#  and list_nodes shows FEATURES/CODE but it cannot be read
# sweep has lots of output to the screen (can it be disabled?)
#
# python says revision 20298, installer says 20315
#
# echoDevice does not work
# syncSetInt takes 250 ms (with 13.06,100 ms with 13.10)
#  compare
#   timeit zi.write('/dev2021/sigins/0/on', 1, t='int')
#   timeit zi.write('/dev2021/sigins/0/on', 1, t='int', sync=False)
# setInt followed by getInt does not return the new value, but the old one instead

##################################################################
#   Direct Access to ZI C API
#    use ziAPI class
##################################################################

import ctypes
import weakref
from ctypes import Structure, Union, pointer, POINTER, byref,\
                   c_int, c_longlong, c_ulonglong, c_short, c_ushort, c_uint,\
                   c_double, c_uint32, c_uint8, c_uint16, c_int64, c_uint64,\
                   c_void_p, c_char_p, c_char, c_ubyte, create_string_buffer
c_uchar_p = c_char_p # POINTER(c_ubyte)
c_uint8_p = c_char_p # POINTER(c_uint8)
c_uint32_p = POINTER(c_uint32)

from instruments_lecroy import StructureImproved

ziDoubleType = c_double
ziIntegerType = c_int64
ziTimeStampType = c_uint64
ziAPIDataType = c_int
ziConnection = c_void_p

MAX_PATH_LEN = 256
MAX_EVENT_SIZE = 0x400000
#MAX_BINDATA_SIZE = 0x10000

class DemodSample(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('timeStamp', ziTimeStampType),
                ('x', c_double),
                ('y', c_double),
                ('frequency', c_double),
                ('phase', c_double),
                ('dioBits', c_uint32),
                ('trigger', c_uint32),
                ('auxIn0', c_double),
                ('auxIn1', c_double) ]

class AuxInSample(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('timeStamp', ziTimeStampType),
                ('ch0', c_double),
                ('ch1', c_double) ]

class DIOSample(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('timeStamp', ziTimeStampType),
                ('bits', c_uint32),
                ('reserved', c_uint32) ]

TREE_ACTION = {0:'removed', 1:'add', 2:'change'}
class TreeChange(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('timeStamp', ziTimeStampType),
                ('action', c_uint32),
                ('name', c_char*32) ]

# TODO: find a way to display all the *0 stuff
class ByteArrayData(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('length', c_uint32),
                ('bytes', c_char*0) ] # c_uint8*0

class ScopeWave(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('dt', c_double),
                ('ScopeChannel', c_uint),
                ('TriggerChannel', c_uint),
                ('BWLimit', c_uint),
                ('Count', c_uint),
                ('Data', c_short*0) ]

class ziDoubleTypeTS(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('timeStamp', ziTimeStampType),
                ('value', ziDoubleType) ]

class ziIntegerTypeTS(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('timeStamp', ziTimeStampType),
                ('value', ziIntegerType) ]

class ByteArrayDataTS(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('timeStamp', ziTimeStampType),
                ('length', c_uint32),
                ('bytes', c_char*0) ] # c_uint8*0

class ZIScopeWave(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('TimeStamp', ziTimeStampType),
                ('dt', c_double),
                ('ScopeChannel', c_uint),
                ('TriggerChannel', c_uint),
                ('BWLimit', c_uint),
                ('Count', c_uint),
                ('Data', c_short*0) ]

class ZIPWASample(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('binPhase', c_double),
                ('x', c_double),
                ('y', c_double),
                ('countBin', c_uint32),
                ('reserved', c_uint32) ]

class ZIPWAWave(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('timeStamp', ziTimeStampType),
                ('sampleCount', c_uint64),
                ('inputSelect', c_uint32),
                ('oscSelect', c_uint32),
                ('harmonic', c_uint32),
                ('binCount', c_uint32),
                ('frequency', c_double),
                ('pwaType', c_uint8),
                ('mode', c_uint8), #0:zoom, 1: harmonic
                ('overflow', c_uint8), #bit0: data accumulator overflow, bit1: counter at limit, bit7: invalid (missing frames), other bits are reserved
                ('commensurable', c_uint8),
                ('reservedUInt', c_uint32),
                ('data', ZIPWASample*0) ]


# These point to the first element of DATA with the correct type.
class ziEventUnion(Union):
    _fields_ = [('Void', c_void_p),
                ('Double', POINTER(ziDoubleType)),
                ('DoubleTS', POINTER(ziDoubleTypeTS)),
                ('Integer', POINTER(ziIntegerType)),
                ('IntegerTS', POINTER(ziIntegerTypeTS)),
                ('ByteArray', POINTER(ByteArrayData)),
                ('ByteArrayTS', POINTER(ByteArrayDataTS)),
                ('Tree', POINTER(TreeChange)),
                ('SampleDemod', POINTER(DemodSample)),
                ('SampleAuxIn', POINTER(AuxInSample)),
                ('SampleDIO', POINTER(DIOSample)),
                ('ScopeWave', POINTER(ZIScopeWave)),
                ('ScopeWave_old', POINTER(ScopeWave)),
                ('pwaWave', POINTER(ZIPWAWave)) ]

ziAPIDataType_vals = {0:'None', 1:'Double', 2:'Integer', 3:'SampleDemod', 4:'ScopeWave_old',
                 5:'SampleAuxIn', 6:'SampleDIO', 7:'ByteArray', 16:'Tree_old',
                 32:'DoubleTS', 33:'IntegerTS', 35:'ScopeWave', 38:'ByteArrayTS', 48:'Tree',
                 8:'pwaWave'}

class ziEvent(StructureImproved):
    _names_cache = [] # every sub class needs to have its own cache
    _fields_ = [('valueType', ziAPIDataType),
                ('count', c_uint32),
                ('path', c_char*MAX_PATH_LEN), # c_uint8*MAX_PATH_LEN
                ('value', ziEventUnion),
                ('data', c_char*MAX_EVENT_SIZE) ] # c_uint8*MAX_EVENT_SIZE
    def __repr__(self):
        if self.count == 0:
            return 'ziEvent(None)'
        data = getattr(self.value, ziAPIDataType_vals[self.valueType])
        return "zevent('%s', count=%i, data0=%r)"%(self.path, self.count, data.contents)
    def show_all(self, multiline=True, show=True):
        if self.count == 0:
            strs = ['None']
        else:
            strs = ['Path=%s'%self.path,'Count=%i'%self.count]
            data = getattr(self.value, ziAPIDataType_vals[self.valueType])
            for i in range(self.count):
                strs.append('data_%i=%r'%(i, data[i]))
        if multiline:
            ret = '%s(\n  %s\n)'%(self.__class__.__name__, '\n  '.join(strs))
        else:
            ret = '%s(%s)'%(self.__class__.__name__, ', '.join(strs))
        if show:
            print ret
        else:
            return ret


ZIResult_enum = c_int
ZI_INFO_SUCCESS =    0x0000
ZI_WARNING_GENERAL = 0x4000
ZI_ERROR_GENERAL =   0x8000

ZIAPIVersion = c_int
#zi_api_version = {1:'ziAPIv1', 3:'ziAPIv3'}
zi_api_version = {1:'ziAPIv1', 4:'ziAPIv4'}

zi_result_dic = {ZI_INFO_SUCCESS:'Success (no error)',
                 ZI_INFO_SUCCESS+1:'Max Info',
                 ZI_WARNING_GENERAL:'Warning (general)',
                 ZI_WARNING_GENERAL+1:'FIFO Underrun',
                 ZI_WARNING_GENERAL+2:'FIFO Overflow',
                 ZI_WARNING_GENERAL+3:'NotFound',
                 ZI_WARNING_GENERAL+4:'Max Warning',
                 ZI_ERROR_GENERAL:'Error (general)',
                 ZI_ERROR_GENERAL+1:'USB communication failed',
                 ZI_ERROR_GENERAL+2:'Malloc failed',
                 ZI_ERROR_GENERAL+3:'mutex unable to init',
                 ZI_ERROR_GENERAL+4:'mutex unable to destroy',
                 ZI_ERROR_GENERAL+5:'mutex unable to lock',
                 ZI_ERROR_GENERAL+6:'mutex unable to unlock',
                 ZI_ERROR_GENERAL+7:'thread unable to start',
                 ZI_ERROR_GENERAL+8:'thread unable tojoin',
                 ZI_ERROR_GENERAL+9:'socket cannot init',
                 ZI_ERROR_GENERAL+10:'socket unable to connect',
                 ZI_ERROR_GENERAL+11:'hostname not found',
                 ZI_ERROR_GENERAL+12:'Connection invalid',
                 ZI_ERROR_GENERAL+13:'timed out',
                 ZI_ERROR_GENERAL+14:'command failed internally',
                 ZI_ERROR_GENERAL+15:'command failed in server',
                 ZI_ERROR_GENERAL+16:'provided buffer length to short',
                 ZI_ERROR_GENERAL+17:'unable to open or read from file',
                 ZI_ERROR_GENERAL+18:'Duplicate entry',
                 ZI_ERROR_GENERAL+19:'invalid attempt to change a read-only node',
                 ZI_ERROR_GENERAL+20:'Max Error' }

class ziAPI(object):
    _default_host = 'localhost'
    _default_port = 8004
    def __init__(self, hostname=_default_host, port=_default_port, autoconnect=True):
        self._last_result = 0
        self._ziDll = ctypes.CDLL('/Program Files/Zurich Instruments/LabOne/API/C/lib/ziAPI-win32.dll')
        self._conn = ziConnection()
        # skipped ziAPIAllocateEventEx
        self._makefunc('ziAPIInit', [POINTER(ziConnection)],  prepend_con=False)
        self._makefunc('ziAPIDestroy', [] )
        self._makefunc('ziAPIGetRevision', [POINTER(c_uint)], prepend_con=False )
        self._makefunc('ziAPIConnect', [c_char_p, c_ushort] )
        self._makefunc('ziAPIDisconnect', [] )
        self._makefunc('ziAPIListNodes', [c_char_p, c_char_p, c_int, c_int] )
        self._makefunc('ziAPIUpdateDevices', [] )
        self._makegetfunc('D', ziDoubleType)
        self._makegetfunc('I', ziIntegerType)
        self._makegetfunc('DemodSample', DemodSample, base='Get')
        self.getS = self.getDemodSample
        self._makegetfunc('DIOSample', DIOSample, base='Get')
        self.getDIO = self.getDIOSample
        self._makegetfunc('AuxInSample', AuxInSample, base='Get')
        self.getAuxIn = self.getAuxInSample
        self._makegetfunc('B', c_char_p)
        self._makefunc('ziAPISetValueD', [c_char_p, ziDoubleType] )
        self._makefunc('ziAPISetValueI', [c_char_p, ziIntegerType] )
        self._makefunc('ziAPISetValueB', [c_char_p, c_uchar_p, c_uint] )
        self._makefunc('ziAPISyncSetValueD', [c_char_p, POINTER(ziDoubleType)] )
        self._makefunc('ziAPISyncSetValueI', [c_char_p, POINTER(ziIntegerType)] )
        self._makefunc('ziAPISyncSetValueB', [c_char_p, c_uint8_p, c_uint32_p, c_uint32] )
        self._makefunc('ziAPISubscribe', [c_char_p] )
        self._makefunc('ziAPIUnSubscribe', [c_char_p] )
        self._makefunc('ziAPIPollDataEx', [POINTER(ziEvent), c_uint32] )
        self._makefunc('ziAPIGetValueAsPollData', [c_char_p] )
        self._makefunc('ziAPIGetError', [ZIResult_enum, POINTER(c_char_p), POINTER(c_int)], prepend_con=False)
        # skipped ReadMEMFile
        self._makefunc('ziAPIStartWebServer', [] )
        self._makefunc('ziAPIAsyncSetDoubleData', [c_char_p, ziDoubleType] )
        # The following 3 are missing in dll
        #self._makefunc('ziAPIAsyncSetIntegerData', [c_char_p, ziIntegerType] )
        #self._makefunc('ziAPIAsyncSetByteArray', [c_char_p, c_uint8_p, c_uint32] )
        #self._makefunc('ziAPIListImplementations', [c_char_p, c_uint32], prepend_con=False )
        self._makefunc('ziAPIConnectEx', [c_char_p, c_uint16, ZIAPIVersion, c_char_p] )
        self._makefunc('ziAPIGetConnectionAPILevel', [POINTER(ZIAPIVersion)] )
        self.init()
        if autoconnect:
            self.connect_ex(hostname, port)
    def _errcheck_func(self, result, func, arg):
        self._last_result = result
        if result<ZI_WARNING_GENERAL:
            return
        else:
            if result<ZI_ERROR_GENERAL:
                raise RuntimeWarning, 'Warning: %s'%zi_result_dic[result]
            else:
                raise RuntimeError, 'ERROR: %s'%zi_result_dic[result]
    def _makefunc(self, f, argtypes, prepend_con=True):
        rr = r = getattr(self._ziDll, f)
        r.restype = ZIResult_enum
        r.errcheck = ProxyMethod(self._errcheck_func)
        if prepend_con:
            argtypes = [ziConnection]+argtypes
            selfw = weakref.proxy(self)
            rr = lambda *arg, **kwarg: r(selfw._conn, *arg, **kwarg)
            setattr(self, '_'+f[5:] , rr) # remove 'ziAPI'
        r.argtypes = argtypes
        setattr(self, '_'+f , r)
    def _makegetfunc(self, f, argtype, base='GetValue'):
        fullname = 'ziAPI'+base+f
        if argtype == c_char_p:
            self._makefunc(fullname, [c_char_p, argtype, POINTER(c_uint), c_uint])
        else:
            self._makefunc(fullname, [c_char_p, POINTER(argtype)])
        basefunc = getattr(self, '_'+base+f)
        def newfunc(path):
            val = argtype()
            if argtype == c_char_p:
                val = create_string_buffer(1024)
                length = c_uint()
                basefunc(path, val, byref(length), len(val))
                return val.raw[:length.value]
            basefunc(path, byref(val))
            if isinstance(val, Structure):
                return val
            else:
                return val.value
        setattr(self, 'get'+f, newfunc)
    def __del__(self):
        # can't use the redirected functions because weakproxy no longer works here
        print 'Running del on ziAPI:', self
        del self._ziAPIDisconnect.errcheck
        del self._ziAPIDestroy.errcheck
        self._ziAPIDisconnect(self._conn)
        self._ziAPIDestroy(self._conn)
    def restart(self, hostname=_default_host, port=_default_port, autoconnect=True):
        self.disconnect()
        self.destroy()
        self.init()
        if autoconnect:
            self.connect_ex(hostname, port)
    def init(self):
        self._ziAPIInit(self._conn)
    def destroy(self):
        self._Destroy()
    def connect(self, hostname=_default_host, port=_default_port):
        """
        If you want to reconnect, you need to first disconnect, then destroy
        then init, before trying connect.
        """
        self._Connect(hostname, port)
        print 'Connected'
    def disconnect(self):
        self._Disconnect()
    def get_revision(self):
        rev = c_uint()
        self._ziAPIGetRevision(byref(rev))
        return rev.value
    def connect_ex(self, hostname=_default_host, port=_default_port, version=4, implementation=None):
        self._ConnectEx(hostname, port, version, implementation)
        print 'Connected ex'
    #def list_implementation(self):
    #    buf = create_string_buffer(1000)
    #    self._ziAPIListImplementations(buf, len(buf))
    #    return buf.value.split('\n')
    def get_connection_ver(self):
        ver = ZIAPIVersion()
        self._GetConnectionAPILevel(byref(ver))
        return ver.value, zi_api_version[ver.value]
    def list_nodes(self, path='/', flags=3):
        buf = create_string_buffer(102400)
        self._ListNodes(path, buf, len(buf), flags)
        return buf.value.split('\n')
    def update_devices(self):
        """
        Rescans the devices available
        """
        self._UpdateDevices()
    def subscribe(self, path):
        self._Subscribe(path)
    def unsubscribe(self, path):
        self._UnSubscribe(path)
    def poll(self, timeout_ms=0):
        ev = ziEvent()
        self._PollDataEx(byref(ev),timeout_ms)
        return ev
    def get_as_poll(self, path):
        self._GetValueAsPollData(path)
    def get_error(self, result=None):
        """
        if result==None, uses the last returned result
        """
        if result==None:
            result = self._last_result
        buf = c_char_p()
        base = c_int()
        self._ziAPIGetError(result, byref(buf), byref(base))
        print 'Message:', buf.value, '\nBase:', hex(base.value)
    def start_web_server(self):
        self._StartWebServer()
    def set(self, path, val):
        if isinstance(val, int):
            self._SetValueI(path, val)
        elif isinstance(val, float):
            self._SetValueD(path, val)
        elif isinstance(val, basestring):
            self._SetValueB(path, val, len(val))
        else:
            raise TypeError, 'Unhandled type for val'
    def set_async(self, path, val):
        if isinstance(val, int):
            self._AsyncSetIntegerData(path, val)
        elif isinstance(val, float):
            self._AsyncSetDoubleData(path, val)
        elif isinstance(val, basestring):
            self._AsyncSetByteArray(path, val, len(val))
        else:
            raise TypeError, 'Unhandled type for val'
    def set_sync(self, path, val):
        if isinstance(val, int):
            val = ziIntegerType(val)
            self._SyncSetValueI(path, byref(val))
        elif isinstance(val, float):
            val = c_double(val)
            self._SyncSetValueD(path, byref(val))
        elif isinstance(val, basestring):
            l = c_uint(len(val))
            self._SyncSetValueB(path, val, byref(l), l)
        else:
            raise TypeError, 'Unhandled type for val'

# asking for /dev2021/samples quits the session (disconnect) for 13.06 and 13.10
# In Visual studio use, Tools/Visual studio command prompt, then:
#    dumpbin /EXPORTS "\Program Files\Zurich Instruments\LabOne\API\C\lib\ziAPI-win32.dll"