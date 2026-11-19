#!/usr/bin/env python3
"""Export Tektronix TBS2000B waveforms and measurements over USB.

Windows: install NI-VISA and pyvisa; run py capture_usb.py --identify first.
macOS/Linux: install pyvisa pyvisa-py pyusb libusb-package.
Capture: python capture_usb.py [--channels CH1 CH2]
Adapted from JustinChenzeting/PHYS-2210-Oscilloscope, commit 171490e7.
"""
import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import sys

BASE = Path(__file__).resolve().parent
MANUAL = 'https://download.tek.com/manual/TBS2000B-Programmer-Manual-EN-US-077114904.pdf'


MODEL_CHANNELS = {
    'TBS2072B': 2, 'TBS2074B': 4,
    'TBS2102B': 2, 'TBS2104B': 4,
    'TBS2202B': 2, 'TBS2204B': 4,
}


def create_manager(backend):
    """Select the vendor VISA driver on Windows, or explicit pyvisa-py."""
    import pyvisa
    if backend == 'py':
        import libusb_package
        import usb.backend.libusb1
        if usb.backend.libusb1.get_backend(find_library=libusb_package.find_library) is None:
            raise RuntimeError('libusb could not be loaded.')
    try:
        return pyvisa.ResourceManager('@' + backend)
    except Exception as exc:
        hint = ('Install NI-VISA with USB support, then reconnect the scope. '
                'The VISA library and Python must have matching bitness.'
                if backend == 'ivi' else
                'Install pyvisa-py pyusb libusb-package and configure USB access for this OS.')
        raise RuntimeError(f'Cannot initialize the {backend} VISA backend. {hint} Details: {exc}') from exc


def is_tektronix_usb(resource):
    parts = resource.upper().split('::')
    if len(parts) < 5 or not parts[0].startswith('USB') or parts[-1] != 'INSTR':
        return False
    try:
        vendor = int(parts[1], 16 if parts[1].startswith('0X') else 10)
    except ValueError:
        return False
    return vendor == 0x0699


def select_resource(manager, requested):
    if requested:
        if not is_tektronix_usb(requested):
            raise ValueError('--resource must be a Tektronix USB VISA instrument resource')
        return requested
    resources = [r for r in manager.list_resources('USB?*::INSTR') if is_tektronix_usb(r)]
    if len(resources) != 1:
        raise RuntimeError(f'Expected one Tektronix USB instrument; found {resources}. '
                           'Run --list, check the USB cable and driver, or specify --resource.')
    return resources[0]


def open_scope(manager, resource, timeout_ms):
    scope = manager.open_resource(resource)
    try:
        scope.timeout = timeout_ms
        scope.chunk_size = 1024 * 1024
        scope.read_termination = '\n'
        scope.write_termination = '\n'
        return scope
    except BaseException:
        scope.close()
        raise


def parse_waveform(response):
    """WAVFRM? provides one synchronized ASCII preamble and sample record."""
    preamble, data = response.strip().rsplit(';', 1)
    fields = next(csv.reader([preamble], delimiter=';'))
    if len(fields) < 16 or fields[2].upper() != 'ASCII' or fields[7] != 'Y':
        raise ValueError(f'Unsupported waveform preamble: {preamble}')
    p = dict(zip(['byte_count','bit_count','encoding','binary_format','byte_order',
                  'description','point_count','point_format','x_unit','x_increment',
                  'x_zero','point_offset','y_unit','y_multiplier','y_offset','y_zero'], fields))
    for key in ['byte_count','bit_count','point_count']:
        p[key] = int(p[key])
    for key in ['x_increment','x_zero','point_offset','y_multiplier','y_offset','y_zero']:
        p[key] = float(p[key])
    if p['x_unit'] != 's' or p['y_unit'] != 'V' or p['point_offset'] != 0:
        raise ValueError(f'Unsupported units or point offset: {p}')
    codes = [int(value) for value in data.strip().split(',')]
    if len(codes) != p['point_count'] or len(codes) < 2:
        raise ValueError('Incomplete waveform transfer')
    times = [p['x_zero'] + i*p['x_increment'] for i in range(len(codes))]
    volts = [(value-p['y_offset'])*p['y_multiplier']+p['y_zero'] for value in codes]
    if p['x_increment'] <= 0 or not all(math.isfinite(v) for v in times+volts):
        raise ValueError('Invalid waveform scale')
    return p, times, volts, codes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resource', help='USB VISA resource (default: discover the connected Tektronix scope)')
    parser.add_argument('--backend', choices=['ivi', 'py'],
                        default='ivi' if sys.platform == 'win32' else 'py',
                        help='VISA backend (default: ivi on Windows, py on macOS/Linux)')
    diagnostics = parser.add_mutually_exclusive_group()
    diagnostics.add_argument('--list', action='store_true', help='List USB VISA resources and exit')
    diagnostics.add_argument('--identify', action='store_true', help='Query *IDN? only and exit')
    parser.add_argument('--timeout-ms', type=int, default=60000, help='USB I/O timeout in ms (default: 60000)')
    parser.add_argument('--channels', nargs='+', choices=['CH1','CH2','CH3','CH4','MATH'],
                        default=['CH1'], help='Channels to fetch (default: CH1)')
    parser.add_argument('--output', type=Path,
                        help='New output directory (default: data/<timestamp> beside this script)')
    args = parser.parse_args()
    if args.timeout_ms <= 0:
        parser.error('--timeout-ms must be positive')
    try:
        import pyvisa
    except ImportError as exc:
        parser.error(f'{exc}. Install pyvisa into the Python environment running this script.')
    if args.list or args.identify:
        manager = None
        scope = None
        try:
            manager = create_manager(args.backend)
            print(f'Backend: {args.backend}; library: {manager.visalib}')
            if args.list:
                resources = manager.list_resources('USB?*::INSTR')
                for resource in resources:
                    print(resource)
                if not resources:
                    print('No USB VISA instruments found. Check the cable and Windows USB/VISA driver.')
                return
            resource = select_resource(manager, args.resource)
            scope = open_scope(manager, resource, args.timeout_ms)
            print(f'Resource: {resource}')
            print(scope.query('*IDN?').strip())
            return
        finally:
            try:
                if scope is not None:
                    scope.close()
            finally:
                if manager is not None:
                    manager.close()
    timestamp = datetime.now().astimezone()
    output = args.output or BASE/'data'/timestamp.strftime('%Y%m%d_%H%M%S_%f')
    output.mkdir(parents=True, exist_ok=False)
    scope = None
    manager = None
    metadata = {'resource':args.resource, 'retrieved_at':timestamp.isoformat(), 'transport':'USB VISA',
                'reference':MANUAL, 'backend':args.backend, 'channels':{}, 'restoration':{},
                'voltage_note':'Volts use the instrument preamble, including its configured probe factor.',
                'time_note':'Time is relative to the trigger. Retrieval time is not the acquisition timestamp.'}
    saved = {}
    all_waves = {}
    measurements = []
    restore_commands = ['HEADER','DATA:SOURCE','DATA:ENCDG','DATA:WIDTH','DATA:START','DATA:STOP',
                        'MEASUREMENT:IMMED:SOURCE1','MEASUREMENT:IMMED:TYPE']
    def query(command):
        result = scope.query(command).strip()
        # Normalize a single scalar query if the caller had response headers enabled.
        return result.rsplit(None, 1)[-1]
    try:
        manager = create_manager(args.backend)
        resource = select_resource(manager, args.resource)
        metadata['resource'] = resource
        metadata['visa_library'] = str(manager.visalib)
        scope = open_scope(manager, resource, args.timeout_ms)
        metadata['identity'] = scope.query('*IDN?').strip()
        print(f'Connected: {metadata["identity"]}', flush=True)
        identity_fields = [field.strip().upper() for field in metadata['identity'].split(',')]
        if (len(identity_fields) < 2 or identity_fields[0] != 'TEKTRONIX'
                or identity_fields[1] not in MODEL_CHANNELS):
            raise ValueError(f'Expected a Tektronix TBS2000B model; got {metadata["identity"]}')
        model = identity_fields[1]
        for command in restore_commands:
            saved[command] = query(command+'?')
        metadata['original_query_settings'] = saved.copy()
        scope.write('HEADER 0')
        metadata['acquisition_state_before'] = query('ACQUIRE:STATE?')
        metadata['trigger_state_before'] = query('TRIGGER:STATE?')
        enabled = [f'CH{i}' for i in range(1, MODEL_CHANNELS[model]+1) if query(f'SELECT:CH{i}?') == '1']
        if query('SELECT:MATH?') == '1':
            enabled.append('MATH')
        channels = list(dict.fromkeys(args.channels or enabled))
        if not channels or any(ch not in enabled for ch in channels):
            raise ValueError(f'Requested channels must already be enabled. Enabled: {enabled}')
        scope.write('DATA:ENCDG ASCII;:DATA:WIDTH 1;:DATA:START 1')
        for channel in channels:
            scope.write(f'DATA:SOURCE {channel}')
            count = int(query('WFMOUTPRE:RECORDLENGTH?'))
            scope.write(f'DATA:STOP {count}')
            response = scope.query('WAVFRM?')
            (output/f'{channel}_instrument_response.txt').write_text(response+'\n')
            preamble, times, volts, codes = parse_waveform(response)
            if len(codes) != count:
                raise ValueError('The scope did not return the complete record')
            with (output/f'{channel}_waveform.csv').open('w',newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['time_s','voltage_v','adc_code'])
                writer.writerows(zip(times,volts,codes))
            all_waves[channel] = (times,volts)
            info = {'preamble':preamble, 'settings':{}, 'sample_statistics':{
                'minimum_v':min(volts),'maximum_v':max(volts),'peak_to_peak_v':max(volts)-min(volts),
                'mean_v':statistics.fmean(volts),'rms_v':math.sqrt(statistics.fmean(v*v for v in volts)),
                'adc_endpoint_samples':sum(v in [-128,127] for v in codes)}}
            if channel == 'MATH':
                info['math_configuration'] = scope.query('MATH?').strip()
            for setting in ([] if channel == 'MATH' else ['SCALE','POSITION','OFFSET','COUPLING','PROBE:GAIN']):
                info['settings'][setting] = query(f'{channel}:{setting}?')
            metadata['channels'][channel] = info
            print(f'{channel}: {len(codes)} points; dt={preamble["x_increment"]:g} s; '
                  f'Vpp={max(volts)-min(volts):g} V', flush=True)
            if channel == 'MATH':
                continue
            scope.write(f'MEASUREMENT:IMMED:SOURCE1 {channel}')
            for name,command,unit in [('frequency','FREQUENCY','Hz'),('period','PERIOD','s'),
                                      ('peak_to_peak','PK2PK','V'),('rms','RMS','V'),
                                      ('mean','MEAN','V'),('minimum','MINIMUM','V'),('maximum','MAXIMUM','V')]:
                scope.write(f'MEASUREMENT:IMMED:TYPE {command}')
                value = float(query('MEASUREMENT:IMMED:VALUE?'))
                valid = math.isfinite(value) and abs(value)<1e36
                measurements.append({'channel':channel,'measurement':name,'value':value if valid else None,
                                     'unit':unit,'status':'valid' if valid else 'unavailable',
                                     'instrument_response':value})
        metadata['acquisition_state_after'] = query('ACQUIRE:STATE?')
        metadata['record_status'] = ('Stopped records; acquisition was not restarted.'
            if metadata['acquisition_state_before']==metadata['acquisition_state_after']=='0'
            else 'Acquisition running or changed; different channels/measurements may be from different records.')
        with (output/'measurements.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['channel','measurement','value','unit','status','instrument_response'])
            writer.writeheader()
            writer.writerows(measurements)
        first_times = next(iter(all_waves.values()))[0]
        if all(wave[0]==first_times for wave in all_waves.values()):
            with (output/'waveforms.csv').open('w',newline='') as f:
                writer=csv.writer(f)
                writer.writerow(['time_s']+[f'{ch}_voltage_v' for ch in channels])
                writer.writerows(zip(first_times,*(all_waves[ch][1] for ch in channels)))
        metadata['complete'] = True
    except Exception as exc:
        metadata['complete'] = False
        metadata['error'] = str(exc)
        raise
    except KeyboardInterrupt:
        metadata['complete'] = False
        metadata['error'] = 'Interrupted by user'
        raise
    finally:
        # Only transfer format and the remote immediate-measurement selector were changed.
        # Do not touch acquisition, trigger, channel, generator, or front-panel measurements.
        for command in restore_commands[1:]+restore_commands[:1]:
            if command in saved:
                try:
                    scope.write(command+' '+saved[command])
                    actual=query(command+'?')
                    metadata['restoration'][command]={'expected':saved[command],'actual':actual,'ok':actual==saved[command]}
                except Exception as exc:
                    metadata['restoration'][command]={'ok':False,'error':str(exc)}
        if scope is not None:
            try:
                scope.close()
            except Exception as exc:
                metadata['close_error'] = str(exc)
        if manager is not None:
            try:
                manager.close()
            except Exception as exc:
                metadata['manager_close_error'] = str(exc)
        (output/'metadata.json').write_text(json.dumps(metadata,indent=2,allow_nan=False)+'\n', encoding='utf-8')
    if not all(item['ok'] for item in metadata['restoration'].values()):
        raise RuntimeError(f'Some settings could not be restored; see {output}/metadata.json')
    (BASE/'data').mkdir(exist_ok=True)
    (BASE/'data/latest.txt').write_text(str(output.resolve())+'\n')
    for row in measurements:
        if row['measurement'] in ['frequency','peak_to_peak','rms']:
            print(f'{row["channel"]} {row["measurement"]}: {row["value"]} {row["unit"]} ({row["status"]})')
    print(f'Saved: {output.resolve()}')


if __name__=='__main__':
    main()
