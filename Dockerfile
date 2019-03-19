FROM python:3.7.2-stretch
MAINTAINER Amane Katagiri
CMD [""]
ENTRYPOINT ["maruberu"]
WORKDIR /maruberu
RUN apt update \
  && apt install --no-install-recommends libusb-0.1-4 \
  && apt clean
COPY . /maruberu
RUN pip install -e . \
  && python -c "__import__('zipfile').ZipFile(__import__('io').BytesIO(__import__('urllib.request').request.urlopen('https://github.com/pavel-a/usb-relay-hid/releases/download/usb-relay-lib_v2.1/bin-Linux-x64.zip').read())).extract('bin-Linux-x64/hidusb-relay-cmd', '/tmp')" \
  && mv /tmp/bin-Linux-x64/hidusb-relay-cmd /bin/ \
  && chmod +x /bin/hidusb-relay-cmd \
  && rmdir /tmp/bin-Linux-x64
WORKDIR /maruberu/maruberu
