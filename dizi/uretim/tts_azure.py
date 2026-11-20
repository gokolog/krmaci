#!/usr/bin/env python3
"""Azure Speech ile bolum01 seslendirmesini üretir ve zamanlamaya göre tek MP3'te birleştirir.

Kullanım:
  export AZURE_SPEECH_KEY=...   AZURE_SPEECH_REGION=westeurope
  python3 tts_azure.py            # -> bolum01_ses.mp3
Opsiyonel: AZURE_VOICE (varsayılan tr-TR-EmelNeural; erkek: tr-TR-AhmetNeural)
"""
import os, subprocess, sys, tempfile, urllib.request, html

KEY = os.environ.get("AZURE_SPEECH_KEY"); REGION = os.environ.get("AZURE_SPEECH_REGION", "westeurope")
VOICE = os.environ.get("AZURE_VOICE", "tr-TR-EmelNeural")
if not KEY: sys.exit("AZURE_SPEECH_KEY tanımlı değil.")

# (başlangıç sn, bitiş sn, metin) — bolum01.html içindeki VO ile aynı olmalı
VO = [
 (0.0, 3.0, "Gözünde bir delik var. Ve beynin bunu senden saklıyor."),
 (3.0, 8.0, "Sol gözünü kapat. Sağ gözünle artıya bak. Telefonu yavaşça yüzüne yaklaştır."),
 (9.4, 11.8, "Nokta kayboldu, değil mi?"),
 (12.0, 19.0, "Çünkü gözünün arkasında, sinirin çıktığı yerde hiç görme hücresi yok. Buna kör nokta denir."),
 (19.0, 25.0, "Peki neden hayatında hiç delik görmüyorsun? Beynin boşluğu tahminle doldurur. Yani gördüğünün bir kısmı… uydurma."),
 (25.0, 30.0, "Gözün yalan söylüyorsa, hafızan ne yapıyor? Sıradaki bölümde."),
]

def synth(text, path):
    ssml = f'<speak version="1.0" xml:lang="tr-TR"><voice name="{VOICE}"><prosody rate="+8%">{html.escape(text)}</prosody></voice></speak>'
    req = urllib.request.Request(f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"), method="POST",
        headers={"Ocp-Apim-Subscription-Key": KEY, "Content-Type": "application/ssml+xml",
                 "X-Microsoft-OutputFormat": "audio-48khz-192kbitrate-mono-mp3", "User-Agent": "seri-uretim"})
    open(path, "wb").write(urllib.request.urlopen(req).read())

def dur(path):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",path]))

tmp = tempfile.mkdtemp(); inputs = []; filt = []
for i, (a, b, text) in enumerate(VO):
    p = f"{tmp}/s{i}.mp3"; synth(text, p); d = dur(p); slot = b - a
    tempo = max(1.0, d / slot) if d > slot else 1.0
    print(f"parça {i}: {d:.2f} sn / slot {slot:.2f} sn" + (f"  -> atempo {tempo:.2f}" if tempo > 1 else ""))
    if tempo > 1.3: print("  UYARI: çok uzun, metni kısaltın.")
    inputs += ["-i", p]
    filt.append(f"[{i}:a]atempo={tempo:.3f},adelay={int(a*1000)}|{int(a*1000)}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(VO)))
filt.append(f"{mix}amix=inputs={len(VO)}:normalize=0,apad=whole_dur=30[out]")
subprocess.check_call(["ffmpeg","-y","-loglevel","error",*inputs,"-filter_complex",";".join(filt),
                       "-map","[out]","-t","30",os.path.join(os.path.dirname(os.path.abspath(__file__)),"bolum01_ses.mp3")])
print("Hazır: bolum01_ses.mp3")
