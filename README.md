# PHYS 2210 Oscilloscope

Standalone **Python 3.12** script for fetching Tektronix **TBS2074B** waveforms and measurements over Ethernet. Requires only `python-vxi11` plus Python's standard library.

Connect your computer to the scope's network, enable the desired channels, and set the correct probe factors. Replace `SCOPE_IP` with the address shown on the scope:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install python-vxi11==0.9
.venv/bin/python capture.py --host SCOPE_IP
```

Add `--channels CH1 CH2` to select channels or `--output ./my_capture` to choose a new output folder. By default, CSVs, raw responses, and metadata go to `data/<timestamp>/` beside the script.

Press **Stop** on the scope first if channels must share a stopped acquisition; running acquisitions are read sequentially. The script preserves acquisition settings and restores its temporary transfer/measurement settings.
