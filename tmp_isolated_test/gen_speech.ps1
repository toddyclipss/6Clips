Add-Type -AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$out = "c:\Users\toddy\Desktop\ViralMint\tmp_isolated_test\storage\downloads\commentary.wav"
$speak.SetOutputToWaveFile($out)
$speak.Speak("Look at this play right here! Flanking the enemy squad on high ground, taking down the sniper, clutch headshot! That is an insane triple kill for the win! Let us go!")
$speak.Dispose()
