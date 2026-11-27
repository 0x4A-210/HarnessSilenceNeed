FROM gcr.io/oss-fuzz-base/base-builder
RUN apt-get update && apt-get install -y make autoconf automake libtool
RUN git clone --depth 1 https://github.com/xiph/flac.git
WORKDIR flac
COPY build.sh $SRC/
