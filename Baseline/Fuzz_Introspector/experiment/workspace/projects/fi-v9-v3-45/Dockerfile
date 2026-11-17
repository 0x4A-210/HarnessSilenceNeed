FROM fi-official-v9-environment:20261114
COPY input.tar /opt/input.tar
COPY case.json /opt/case.json
COPY adapter /opt/adapter
WORKDIR /src
CMD ["python3", "/opt/adapter/entry.py"]
