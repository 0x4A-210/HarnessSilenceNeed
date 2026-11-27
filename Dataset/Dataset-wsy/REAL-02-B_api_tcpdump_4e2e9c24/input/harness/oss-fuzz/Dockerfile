FROM gcr.io/oss-fuzz-base/base-builder
RUN apt-get update && apt-get install -y make autoconf automake libtool libpcap-dev
RUN git clone --depth 1 https://github.com/the-tcpdump-group/tcpdump.git
WORKDIR tcpdump
COPY build.sh $SRC/
