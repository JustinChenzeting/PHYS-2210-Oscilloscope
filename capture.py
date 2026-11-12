#!/usr/bin/env python3
"""Export Tektronix TBS2074B waveforms and measurements over Ethernet.

Use Python 3.12. Install: python3 -m pip install python-vxi11==0.9
Run:     python3 capture.py --host SCOPE_IP [--channels CH1 CH2]
"""
import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import statistics

BASE = Path(__file__).resolve().parent
MANUAL = 'https://download.tek.com/manual/TBS2000B-Programmer-Manual-EN-US-077114904.pdf'


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
    parser.add_argument('--host', required=True, help='Current IP address or hostname of the scope')
    parser.add_argument('--channels', nargs='+', choices=['CH1','CH2','CH3','CH4'],
                        help='Channels to fetch (default: all enabled channels)')
    parser.add_argument('--output', type=Path,
                        help='New output directory (default: data/<timestamp> beside this script)')
    args = parser.parse_args()
    try:
        import vxi11
    except ImportError as exc:
        parser.error(f'{exc}. Use Python 3.12 with python-vxi11==0.9 installed; see README.md.')
    timestamp = datetime.now().astimezone()
    output = args.output or BASE/'data'/timestamp.strftime('%Y%m%d_%H%M%S_%f')
    output.mkdir(parents=True, exist_ok=False)
    scope = None
    metadata = {'host':args.host, 'retrieved_at':timestamp.isoformat(), 'transport':'VXI-11',
                'reference':MANUAL, 'channels':{}, 'restoration':{},
                'voltage_note':'Volts use the instrument preamble, including its configured probe factor.',
                'time_note':'Time is relative to the trigger. Retrieval time is not the acquisition timestamp.'}
    saved = {}
    all_waves = {}
    measurements = []
    restore_commands = ['HEADER','DATA:SOURCE','DATA:ENCDG','DATA:WIDTH','DATA:START','DATA:STOP',
                        'MEASUREMENT:IMMED:SOURCE1','MEASUREMENT:IMMED:TYPE']
    def query(command):
        result = scope.ask(command).strip()
        # Normalize a single scalar query if the caller had response headers enabled.
        return result.rsplit(None, 1)[-1]
    try:
        scope = vxi11.Instrument(args.host)
        scope.timeout = 15
        metadata['identity'] = scope.ask('*IDN?').strip()
        if ',TBS2074B,' not in metadata['identity']:
            raise ValueError('This exporter was verified for the TBS2074B; check another model before using it.')
        for command in restore_commands:
            saved[command] = query(command+'?')
        metadata['original_query_settings'] = saved.copy()
        scope.write('HEADER 0')
        metadata['acquisition_state_before'] = query('ACQUIRE:STATE?')
        metadata['trigger_state_before'] = query('TRIGGER:STATE?')
        enabled = [f'CH{i}' for i in range(1,5) if query(f'SELECT:CH{i}?') == '1']
        channels = list(dict.fromkeys(args.channels or enabled))
        if not channels or any(ch not in enabled for ch in channels):
            raise ValueError(f'Requested channels must already be enabled. Enabled: {enabled}')
        scope.write('DATA:ENCDG ASCII;:DATA:WIDTH 1;:DATA:START 1')
        for channel in channels:
            scope.write(f'DATA:SOURCE {channel}')
            count = int(query('WFMOUTPRE:RECORDLENGTH?'))
            scope.write(f'DATA:STOP {count}')
            response = scope.ask('WAVFRM?')
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
            for setting in ['SCALE','POSITION','OFFSET','COUPLING','PROBE:GAIN']:
                info['settings'][setting] = query(f'{channel}:{setting}?')
            metadata['channels'][channel] = info
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
            print(f'{channel}: {len(codes)} points; dt={preamble["x_increment"]:g} s; '
                  f'Vpp={max(volts)-min(volts):g} V',flush=True)
        metadata['acquisition_state_after'] = query('ACQUIRE:STATE?')
        metadata['record_status'] = ('Stopped records; acquisition was not restarted.'
            if metadata['acquisition_state_before']==metadata['acquisition_state_after']=='0'
            else 'Acquisition running or changed; different channels/measurements may be from different records.')
        with (output/'measurements.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(measurements[0]))
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
        (output/'metadata.json').write_text(json.dumps(metadata,indent=2,allow_nan=False)+'\n')
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
