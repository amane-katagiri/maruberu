# maruberu

maruberu is a simple ??? server written in Python/Tornado.

## Demo

TODO: movie

## Requirement

* [丸ベル4型AC6VDC3V](https://www2.panasonic.biz/scvb/a2A/opnItemDetail?item_cd=EB04K&item_no=EB04K&catalog_view_flg=1&contents_view_flg=1&vcata_flg=1)

* [SODIAL(R)5V USBリレー1チャンネル](https://www.amazon.co.jp/dp/B00OPVQTY6/)

TODO: img

## Quick start on Docker

### Run with example config http://localhost:8000/.
```
docker run --rm $(for x in $(find /dev/bus/usb/ -type c); do echo --device $x; done) -p 8000:8000 amane/maruberu --admin_username="ADMIN" --admin_password="PASSWORD --debug=True"
```

If you don't have any USB relay module, bell or buzzer, add `--ring_command=:/bin/ring_dummy` and see stdout.

### Run with your own config.
Firstly, copy [:maruberu/example-server.conf](https://github.com/amane-katagiri/maruberu/blob/master/maruberu/example-server.conf) to `/path/to/your/conf/dir/server.conf`.

```
docker run --rm $(for x in $(find /dev/bus/usb/ -type c); do echo --device $x; done) -p 8000:8000 -v/path/to/your/conf/dir:/maruberu/maruberu/conf:ro amane/maruberu
```

## Save tokens permanently

Use Redis binding to save tokens.

```
docker run -d --name maruberu-redis redis --appendonly yes
docker run -d $(for x in $(find /dev/bus/usb/ -type c); do echo --device $x; done) -p 8000:8000 --link maruberu-redis:redis amane/maruberu --admin_username="ADMIN" --admin_password="PASSWORD" --database="redis:6379/0" --env="REDIS"
```

Or, pull this repository and run `make up`.

## Options

Use `-h` to see all options.

```
docker run --rm amane/maruberu -h
```

## Licence

[MIT](https://github.com/tcnksm/tool/blob/master/LICENCE)

## Author

[amane-katagiri](https://github.com/amane-katagiri)
