#!/bin/bash
# sequential experiment queue: processes specs/*.json listed in queue.txt without a status file
cd /home/claude/hd
while true; do
  next=""
  while read s; do
    [ -z "$s" ] && continue
    st="${s%.json}.status.json"
    [ -f "$st" ] && continue
    [ -f "$s.running" ] && continue
    next=$s; break
  done < queue.txt
  [ -z "$next" ] && { sleep 30; [ -f queue.stop ] && exit 0; continue; }
  touch "$next.running"
  python3 tools/make_case.py "$next" >> logs/$(basename ${next%.json}).txt 2>&1
  rm -f "$next.running"
done
