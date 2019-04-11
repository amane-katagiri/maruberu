# maruberu

maruberu is a simple resource-sharing server written in Python/Tornado.

## Demo

[![demo](https://user-images.githubusercontent.com/8361232/55939430-ad030d00-5c78-11e9-8ec3-4659a751942e.gif)](https://test.maruberu.ama.ne.jp/)

[:bell: emoji](https://abs.twimg.com/emoji/v2/svg/1f514.svg) is licensed under a [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) by Twitter, Inc and other contributors.

Let's visit [test.maruberu.ama.ne.jp](https://test.maruberu.ama.ne.jp/) and ring bell right now.

## Requirement

* [丸ベル4型AC6VDC3V](https://www2.panasonic.biz/scvb/a2A/opnItemDetail?item_cd=EB04K&item_no=EB04K&catalog_view_flg=1&contents_view_flg=1&vcata_flg=1)

[![maruberu](https://user-images.githubusercontent.com/8361232/55941494-4af8d680-5c7d-11e9-9ce6-b4f1a49acd87.jpg)](https://www.youtube.com/watch?v=xIkVAX1yXVA)

* [SODIAL(R)5V USBリレー1チャンネル](https://www.amazon.co.jp/dp/B00OPVQTY6/)

[![usb-relay](https://user-images.githubusercontent.com/8361232/55939883-e12afd80-5c79-11e9-892b-c00445e2210a.jpg)](https://www.youtube.com/watch?v=iL9tF8JH4SY)

## Quick start on Docker

### Run with example config http://localhost:8000/.
```
docker run --rm $(for x in $(find /dev/bus/usb/ -type c); do echo --device $x; done) -p 8000:8000 amane/maruberu --admin_username="ADMIN" --admin_password="PASSWORD --debug=True"
```

Let's access http://localhost:8000/admin/login and login with ADMIN:PASSWORD. You can list sample tokens in the bottom of the admin page.

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
