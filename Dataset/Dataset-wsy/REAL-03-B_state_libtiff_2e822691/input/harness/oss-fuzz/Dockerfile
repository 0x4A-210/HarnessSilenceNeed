FROM gcr.io/oss-fuzz-base/base-builder
RUN apt-get update && apt-get install -y make autoconf automake libtool
RUN git clone --depth 1 https://gitlab.com/libtiff/libtiff.git
WORKDIR libtiff
COPY build.sh $SRC/
