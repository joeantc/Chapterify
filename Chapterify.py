# %%
from vosk import Model, KaldiRecognizer, SetLogLevel
import sys
import os
from os import path
import wave
import json
import pandas as pd
from pandas.io.json import json_normalize
from pydub import AudioSegment
import subprocess
import mutagen
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from mutagen.wave import WAVE
import numpy as np
import time
from multiprocessing.dummy import Pool

# %%
#build the model 
model = Model("model")

# %%
src = r"C:\Users\Joe\Documents\Python Scripts\Chapterify\chapter36.mp3"
listwords = ["chapter",'epilogue']

# %%
base = os.path.basename(src)
path = src[:-len(base)]
filename, file_extension = os.path.splitext(base)
dst = path+filename+'.wav'
segtime = 900

# %%
#convert .mp3 into .wav
subprocess.call(['ffmpeg', '-i', src,'-ar','16000', '-ac','1',dst])

# %%
#split new .wav into chunks & remove .wav
subprocess.call(['ffmpeg', '-i', dst,'-f','segment', '-segment_time',str(segtime),'-c','copy','output%03d.wav'])
#os.remove(dst)

# %%
#get list of output files
audiolist = [f for f in os.listdir(path) if f.startswith('output') and f.endswith('wav')]
start_time = time.time()

# %%
def recognize(a):
    wf = wave.open(a, "rb")
    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)
    tempDict = {"JSON":[],"File":[]}
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            tempDict["JSON"].append(rec.Result())
            tempDict["File"].append(a)
    tempDF = pd.DataFrame(tempDict)
    wf.close()
    os.remove(path+a)
    print('completed '+a+"--- %s seconds ---" % (time.time() - start_time))
    return(tempDF)

# %%
p = Pool(3)
tempDF = p.map(recognize,audiolist)

# %%
df = pd.concat(tempDF)

# %%
master = pd.DataFrame()
for idx, row in df.iterrows():
    try:
        df1 = pd.read_json(row["JSON"])
        df1["File"] = row["File"]
        master = master.append(df1)
    except ValueError: #exception handling for blank JSON
        continue
master = master.reset_index()

# %%
#subset master into sentences with the word "chapter" & append "epilogue"
sentences = pd.DataFrame()
for a in listwords:
    sentences = sentences.append(master[master["text"].str.contains(a)])
#remove senteces with "chapter" in the middle
for idx, row in sentences.iterrows():
    t = row["text"]
    q = t[:t.find("chapter")]
    if len(t.split()) > 15: #where "chapter" is within first 3 words and sentence has less thatn 15 words
        sentences = sentences.drop(index=idx)
sentences = sentences.drop(columns="index")
sentences = sentences.reset_index()

# %%
chapters = pd.json_normalize(sentences["result"])
chapters['text'] = ''
chapters['File'] = ''
for idx, row in chapters.iterrows():
    chapters.at[idx,'text'] = sentences.at[idx,'text']
    chapters.at[idx,'File'] = sentences.at[idx,'File']

# %%
chapterDict = {"File":"length"}
i = 0
for idx, a in enumerate(audiolist):
    if idx == 0:
        chapterDict[a] = i
    else:
        i = i + segtime
        chapterDict[a] = i

# %%
def chapter(src,start,end,idx):
    chapter = f"{idx:02d}"
    subprocess.call(['ffmpeg', '-i', src,'-acodec','copy', '-ss',start,'-to',end,'chapter'+chapter+'.mp3'])
    audio = EasyID3(path+'chapter'+chapter+'.mp3')
    audio['tracknumber'] = chapter
    audio.save()

# %%
words = pd.DataFrame()
for a in listwords:
    words = words.append(chapters[chapters["word"].str.contains("chapter")])
#words = chapters[chapters["word"].str.contains("chapter")]
#words = words.append(chapters[chapters["word"].str.contains("epilogue")])
words = words.reset_index()
adj = 0
start = '0'
end = '0'
for idx, row in words.iterrows():
    #chapter = f"{idx:02d}"
    if idx > 0:
        end = str(round(words.loc[idx,'start'] + chapterDict.get(row['File']),3))
        chapter(src,start,end,idx)
        start = str(round(float(end)+.001,3))
audio = MP3(src)
end  = str(audio.info.length)
chapter(src,start,end,idx+1)

# %%



