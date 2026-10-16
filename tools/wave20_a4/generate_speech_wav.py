# Generate authentic offline speech WAV on Windows
import subprocess
from pathlib import Path

out_wav = Path(__file__).resolve().parent / "speech_sample.wav"
ps_cmd = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile('{str(out_wav).replace('\\', '/')}')
$s.Speak('ViralMint delivers original native motion graphics.')
$s.Dispose()
"""
res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
if res.returncode != 0:
    print("PowerShell error:", res.stderr)
else:
    print("Success! Created:", out_wav.exists(), "Size:", out_wav.stat().st_size if out_wav.exists() else 0)
