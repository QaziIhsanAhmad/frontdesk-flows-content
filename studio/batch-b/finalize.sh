#!/bin/bash
# finalize.sh <id> : rebuild cover, prepend it (0.3s) to the rendered frames, mux audio -> out2/<id>_final.mp4
cd "$(dirname "$0")"
id=$1; W=work2/$id
python3 cine_build.py reels2/$id.json > /dev/null || exit 1
node cine_render.js $id cover > /dev/null || exit 1
n=$(ls $W/frames | wc -l); dur=$(python3 -c "print(round(0.3+$n/30,3))")
ffmpeg -v error -y -thread_queue_size 64 -loop 1 -framerate 30 -t 0.3 -i out2/${id}_cover.jpg -thread_queue_size 64 -framerate 30 -i $W/frames/%05d.jpg \
  -filter_complex "[0:v]scale=1080:1920,format=yuv420p,setsar=1,fps=30[c];[1:v]format=yuv420p,setsar=1,fps=30[f];[c][f]concat=n=2:v=1:a=0[v]" \
  -map "[v]" -c:v libx264 -crf 18 -preset medium -profile:v high -maxrate 4500k -bufsize 9000k -g 60 -pix_fmt yuv420p $W/v.mp4 || exit 1
ffmpeg -v error -y -i $W/v.mp4 -i $W/mix_norm.wav -filter_complex "[1:a]adelay=300|300,atrim=0:$dur[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 128k -ar 44100 -movflags +faststart out2/${id}_final.mp4 || exit 1
rm -f $W/v.mp4
echo "final $id $(ffprobe -v error -show_entries format=duration -of csv=p=0 out2/${id}_final.mp4)"
